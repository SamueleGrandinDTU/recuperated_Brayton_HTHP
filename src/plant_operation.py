"""
src/plant_operation.py

Operational strategy optimization for an HTHP (+ TES) industrial heat plant.

The core function, ``optimize_operational_strategy``, is a MILP
(Pyomo + GLPK) that schedules a high-temperature heat pump (HTHP) coupled
with thermal energy storage (TES) against day-ahead electricity prices,
subject to:

    - a heat demand profile (see "Heat demand profiles" below)
    - a minimum continuous HTHP run time once it starts (12 h by default)
    - a TES energy balance with a finite storage capacity

Plant characterization
-----------------------
The plant is described by exactly three numbers, read off the ``plant``
input (a ``Plant`` dataclass instance, or a plain dict with the same
keys):

    COP     : coefficient of performance of the HTHP while coupled to the
              TES [-]
    Q_HTHP  : useful thermal power delivered by the HTHP when ON [MWth]
    E_TES   : maximum usable TES energy capacity [MWhth]

Heat demand profiles
---------------------
Selected with the ``heat_demand_profile`` input:

    "fixed" (default)
        1 MWth every day from 06:00 to 22:00, 0 otherwise. The profile is
        an input of the optimization.
    "free"
        The process still needs 16 hours of 1 MWth heat per calendar day
        (16 MWh/day), but WHEN those 16 hours happen is part of the
        optimization: the plant chooses, hour by hour, when the process
        takes heat, together with when the HTHP runs and the TES
        charges/discharges. All other constraints are unchanged. The 16
        hours need not be consecutive.

Weekly rolling horizon
-----------------------
The optimization always solves in <=168-hour (weekly) blocks.
When more than one block is required (a full month or the whole year),
blocks are solved *sequentially*, each one picking up where the previous
one left off:

    - the TES energy level at the end of a block becomes the initial TES
      energy of the next block;
    - if the HTHP was still in the middle of a mandatory 12-hour run when
      a block ended, the next block is forced to keep it running for the
      remaining hours before it is allowed to consider stopping again.

The HTHP is NOT forced to empty the TES or to finish a run by the end of
a block. A single isolated week (``week=<n>``) has no
predecessor, so it always starts from an empty TES and no pending run.
"""

import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, Union

import pyomo.environ as pyo

# ============================================================================
# PLANT DESCRIPTION
# ============================================================================


@dataclass
class Plant:
    """Minimal plant characterization needed for the scheduling MILP.

    Attributes
    ----------
    COP : float
        Coefficient of performance of the HTHP while operating together
        with the TES [-].
    Q_HTHP : float
        Useful thermal power delivered by the HTHP when it is ON [MWth].
    E_TES : float
        Maximum usable energy capacity of the thermal energy storage
        [MWhth].
    """

    COP: float
    Q_HTHP: float
    E_TES: float


PlantLike = Union[Plant, dict]


def _plant_param(plant: PlantLike, name: str) -> float:
    """Read a parameter off a ``Plant`` dataclass or an equivalent dict."""

    if isinstance(plant, dict):
        try:
            return float(plant[name])
        except KeyError as exc:
            raise KeyError(f"Plant input is missing required key '{name}'.") from exc

    try:
        return float(getattr(plant, name))
    except AttributeError as exc:
        raise AttributeError(
            f"Plant input is missing required attribute '{name}'."
        ) from exc


def _is_plant_like(plant) -> bool:
    """True for a ``Plant`` instance or a plain dict - i.e. something
    ``_plant_param`` can already read directly, as opposed to a raw
    TESPy ``Network`` that still needs COP/Q_HTHP derived from it."""

    return isinstance(plant, (Plant, dict))


# ============================================================================
# DERIVING A PLANT FROM A SOLVED TESPY NETWORK
# ============================================================================


def _tespy_val_MW(container, component_label: str, attr_name: str) -> float:
    """Read a TESPy result property's ``.val`` (e.g. ``comp.P.val`` or
    ``comp.Q.val``). The plant's power unit is fixed to MW, so this is
    used as-is - no unit conversion.

    Raises a clear error if the property isn't there, or if it hasn't
    been computed yet (NaN - i.e. the network hasn't been solved).
    """

    try:
        value = container.val
    except AttributeError as exc:
        raise AttributeError(
            f"Component '{component_label}' does not expose a usable "
            f"'.{attr_name}.val' property."
        ) from exc

    if value is None or (isinstance(value, float) and math.isnan(value)):
        raise ValueError(
            f"Component '{component_label}' has no computed value for "
            f"'{attr_name}' yet. Make sure the TESPy network has been "
            "solved (e.g. network.solve('design')) before calling "
            "optimize_operational_strategy with it."
        )

    return value


def _tespy_components_by_type(network, type_name: str) -> list:
    """All components in a TESPy Network whose comp_type matches `type_name`
    (case-insensitive), e.g. type_name="Compressor"."""

    comps = network.comps
    matches = comps[comps["comp_type"].str.lower() == type_name.lower()]
    return list(matches["object"])


def _tespy_component_by_label_and_type(network, label: str, type_name: str):
    """Look up a component by label *and* component type, searching
    ``network.comps`` directly rather than ``network.get_comp`` (which
    has proven unreliable for finding components by label alone - see
    its own FutureWarning about returning None for a label that does
    exist). Matching is case/whitespace-insensitive on the label. Returns
    None if no component matches both conditions."""

    label_norm = label.strip().lower()
    type_norm = type_name.strip().lower()

    for comp, comp_type in zip(network.comps["object"], network.comps["comp_type"]):
        if comp.label.strip().lower() == label_norm and comp_type.lower() == type_norm:
            return comp
    return None


def derive_plant_from_tespy(
    network,
    E_TES: float,
    interface_hx_label: str = "interface hx",
    interface_hx_type: str = "HeatExchanger",
) -> Plant:
    """Derive COP and Q_HTHP from a solved TESPy network, and package
    them together with a supplied TES capacity into a ``Plant``.

    Rules
    -----
    - Electrical power input: the sum of the ``.P`` values of every
      Compressor and every Turbine in the network. TESPy's own sign
      convention (turbine power negative) means a recuperated cycle's
      power recovery is already netted out automatically.
    - Useful thermal effect (Q_HTHP): read off the component that is
      both of type `interface_hx_type` ("HeatExchanger" by default) and
      labeled `interface_hx_label` ("interface hx" by default), if one
      exists. Otherwise, the sum of the heat duties (``.Q``) of every
      `interface_hx_type` component whose label contains "sink"
      (case-insensitive) - e.g. "sink 1", "sink 2". A component like a
      "recuperator" is correctly excluded here since "sink" isn't in its
      label. If neither an interface heat exchanger nor any usable sink
      can be found, a ValueError is raised asking for Q_HTHP to be
      supplied directly instead (pass a ``Plant``/dict rather than a raw
      network).
    - COP = Q_HTHP / electrical power input.

    The network must already be solved before calling this - TESPy
    result properties read as NaN on an unsolved network, which raises
    a clear error here rather than silently producing garbage.

    Parameters
    ----------
    network : tespy.networks.Network
        A solved TESPy network describing the HTHP cycle.
    E_TES : float
        TES capacity [MWhth] - not something a thermodynamic network
        simulation can produce, so it's always supplied directly.
    interface_hx_label : str
        Label of the component representing the plant/process interface
        heat exchanger, if the topology has one.
    interface_hx_type : str
        TESPy component type that the interface heat exchanger and any
        fallback "sink" components are expected to be (default
        "HeatExchanger").
    """

    compressors = _tespy_components_by_type(network, "Compressor")
    turbines = _tespy_components_by_type(network, "Turbine")

    if not compressors and not turbines:
        raise ValueError(
            "No Compressor or Turbine components found in the TESPy "
            "network - cannot compute the HTHP's electrical power input."
        )

    electrical_power_MW = sum(
        _tespy_val_MW(comp.P, comp.label, "P") for comp in compressors + turbines
    )

    if electrical_power_MW == 0:
        raise ValueError(
            "The Compressor/Turbine components report zero net "
            "electrical power - cannot compute a COP from this network."
        )

    interface_hx = _tespy_component_by_label_and_type(
        network, interface_hx_label, interface_hx_type
    )

    if interface_hx is not None:
        if not hasattr(interface_hx, "Q"):
            raise AttributeError(
                f"Component '{interface_hx_label}' does not expose a "
                "'.Q' property, so it can't be used as the interface "
                "heat exchanger."
            )
        Q_HTHP_MW = abs(_tespy_val_MW(interface_hx.Q, interface_hx_label, "Q"))
    else:
        sink_like = [
            comp
            for comp, comp_type in zip(
                network.comps["object"], network.comps["comp_type"]
            )
            if comp_type.lower() == interface_hx_type.lower()
            and "sink" in comp.label.lower()
            and hasattr(comp, "Q")
        ]

        if not sink_like:
            raise ValueError(
                f"No {interface_hx_type} component labeled "
                f"'{interface_hx_label}' was found, and no "
                f"{interface_hx_type} component with 'sink' in its label "
                "exposes a usable '.Q' property either. Please provide "
                "Q_HTHP directly instead (pass a Plant/dict rather than "
                "a raw TESPy network)."
            )

        Q_HTHP_MW = sum(
            abs(_tespy_val_MW(comp.Q, comp.label, "Q")) for comp in sink_like
        )

    COP = Q_HTHP_MW / electrical_power_MW

    return Plant(COP=COP, Q_HTHP=Q_HTHP_MW, E_TES=E_TES)


def _resolve_plant(
    plant,
    E_TES: Optional[float],
    interface_hx_label: str,
    interface_hx_type: str = "HeatExchanger",
) -> PlantLike:
    """Accept a ``Plant``/dict as-is, or derive one from a raw TESPy
    ``Network`` - this is what lets ``optimize_operational_strategy``
    take either kind of input for its `plant` argument."""

    if _is_plant_like(plant):
        return plant

    if not hasattr(plant, "comps"):
        raise TypeError(
            "`plant` must be a Plant instance, a dict with COP/Q_HTHP/"
            "E_TES keys, or a solved TESPy Network object."
        )

    if E_TES is None:
        raise ValueError(
            "When passing a TESPy Network directly as `plant`, you must "
            "also pass `E_TES` (the TES capacity is a design choice, not "
            "something a thermodynamic network simulation produces)."
        )

    return derive_plant_from_tespy(
        plant,
        E_TES=E_TES,
        interface_hx_label=interface_hx_label,
        interface_hx_type=interface_hx_type,
    )


# ============================================================================
# ELECTRICITY PRICE DATA
# ============================================================================

# Market name -> csv file name, relative to `data_dir`. Each file is
# expected to have a "Time" column (parseable as "%Y-%m-%d %H:%M") and a
# "Price [EUR/MWh]" column, one row per hour.
MARKET_PRICE_FILES = {
    "DK1": "dk1_electricity_prices_2025.csv",
    "DE": "de_electricity_prices_2025.csv",
}

DEFAULT_DATA_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "electricity_prices"
)


def _load_price_series(market: str, year: int, data_dir: Path):
    """Load the full-year hourly (timestamp, price) series for a market."""

    try:
        filename = MARKET_PRICE_FILES[market]
    except KeyError as exc:
        raise ValueError(
            f"Unknown market '{market}'. Available markets: "
            f"{sorted(MARKET_PRICE_FILES)}"
        ) from exc

    path = Path(data_dir) / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Could not find price data for market '{market}' at '{path}'."
        )

    timestamps = []
    prices = []

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.strptime(row["Time"], "%Y-%m-%d %H:%M")
            if ts.year != year:
                continue
            timestamps.append(ts)
            prices.append(float(row["Price [EUR/MWh]"]))

    if not timestamps:
        raise ValueError(
            f"No price data found for market '{market}', year {year} in '{path}'."
        )

    return timestamps, prices


# ============================================================================
# DEMAND PROFILE (embedded default - see module docstring)
# ============================================================================

DEMAND_START_HOUR = 6  # inclusive
DEMAND_END_HOUR = 22  # exclusive
Q_DEMAND_DEFAULT = 1.0  # [MWth]


# Hours of heat demand per day (both profiles): 06:00-22:00 = 16 h
DAILY_DEMAND_HOURS = DEMAND_END_HOUR - DEMAND_START_HOUR

HEAT_DEMAND_PROFILES = ("fixed", "free")
DEFAULT_HEAT_DEMAND_PROFILE = HEAT_DEMAND_PROFILES[0]


def _check_heat_demand_profile(heat_demand_profile: str) -> str:
    """Return the canonical profile name (case/whitespace-insensitive) or
    raise a clear error listing the available ones."""

    normalized = " ".join(str(heat_demand_profile).lower().split())
    if normalized not in HEAT_DEMAND_PROFILES:
        raise ValueError(
            f"Unknown heat_demand_profile '{heat_demand_profile}'. "
            f"Available profiles: {list(HEAT_DEMAND_PROFILES)}"
        )
    return normalized


def _demand_profile(timestamps: Sequence[datetime], q_demand: float = Q_DEMAND_DEFAULT):
    """Constant industrial heat demand from 06:00 to 22:00, else zero."""

    return [
        q_demand if DEMAND_START_HOUR <= ts.hour < DEMAND_END_HOUR else 0.0
        for ts in timestamps
    ]


def _daily_demand_requirements(timestamps: Sequence[datetime]):
    """For the "free" profile: group the block's hours by calendar day and
    return [(indices, required_demand_hours), ...]: 16 hours for every
    day (a 23- or 25-hour daylight-saving day included). The free profile
    always solves blocks made of whole calendar days (see
    ``_chunk_into_calendar_weeks``), so no day is ever split."""

    days: dict = {}
    for i, ts in enumerate(timestamps):
        days.setdefault(ts.date(), []).append(i)

    return [(idx, min(DAILY_DEMAND_HOURS, len(idx))) for idx in days.values()]


# ============================================================================
# PERIOD SELECTION
# ============================================================================

WEEK_HOURS = 24 * 7


def _select_period_indices(timestamps, month=None, week=None, calendar_weeks=False):
    """Return the [start, end) index range for the requested period.

    - Nothing specified -> the whole year.
    - `month` (1-12) -> all hours whose timestamp falls in that calendar
      month.
    - `week` (1, 2, 3, ...) -> the n-th consecutive 168-hour block of the
      year, counted from 1-Jan 00:00 (NOT calendar weeks Mon-Sun). With
      `calendar_weeks` (free demand profile) it is the n-th block of 7
      whole calendar days instead - identical until the first daylight-
      saving change, then offset by one hour.
    """

    n = len(timestamps)

    if month is not None and week is not None:
        raise ValueError("Specify only one of `month` or `week`, not both.")

    if month is not None:
        if not (1 <= month <= 12):
            raise ValueError("`month` must be between 1 and 12.")
        idx = [i for i, ts in enumerate(timestamps) if ts.month == month]
        if not idx:
            raise ValueError(f"No data found for month {month}.")
        return idx[0], idx[-1] + 1

    if week is not None and calendar_weeks:
        days = _calendar_days(timestamps, 0, n)
        n_weeks = math.ceil(len(days) / 7)
        if not (1 <= week <= n_weeks):
            raise ValueError(f"`week` must be between 1 and {n_weeks}.")
        return days[(week - 1) * 7][0], days[min(week * 7, len(days)) - 1][1]

    if week is not None:
        n_weeks = math.ceil(n / WEEK_HOURS)
        if not (1 <= week <= n_weeks):
            raise ValueError(f"`week` must be between 1 and {n_weeks}.")
        start = (week - 1) * WEEK_HOURS
        end = min(start + WEEK_HOURS, n)
        return start, end

    # Nothing specified -> whole year
    return 0, n


def _calendar_days(timestamps, start: int, end: int):
    """[(first_index, last_index_exclusive), ...] of every calendar day in
    [start, end)."""

    days = []
    i = start
    while i < end:
        j = i
        while j < end and timestamps[j].date() == timestamps[i].date():
            j += 1
        days.append((i, j))
        i = j
    return days


def _chunk_into_calendar_weeks(timestamps, start: int, end: int):
    """Free profile: split [start, end) into blocks of 7 whole calendar
    days (the last one may be shorter). Unlike ``_chunk_into_weeks`` (168
    hours), a block never cuts a day in two, which the daily 16-hour
    demand requires - the data has 23/25-hour days around the daylight-
    saving changes, so 168-hour blocks drift away from midnight."""

    days = _calendar_days(timestamps, start, end)
    return [
        (days[k][0], days[min(k + 7, len(days)) - 1][1]) for k in range(0, len(days), 7)
    ]


def _chunk_into_weeks(start: int, end: int):
    """Split [start, end) into consecutive <=168h chunks."""

    chunks = []
    t = start
    while t < end:
        chunk_end = min(t + WEEK_HOURS, end)
        chunks.append((t, chunk_end))
        t = chunk_end
    return chunks


# ============================================================================
# SINGLE-BLOCK MILP
# ============================================================================


@dataclass
class _BlockResult:
    Q_HTHP: list
    Q_demand: list
    start: list
    E_TES: list
    cost: float
    final_hours_running: int


def _solve_block(
    prices,
    demand,
    plant: PlantLike,
    min_on_hours: int,
    initial_E_TES: float,
    initial_hours_remaining: int,
    solver_name: str,
    solver_options: dict,
    tee: bool,
    is_final_block: bool = True,
    free_demand_days: Optional[list] = None,
) -> _BlockResult:
    """Solve one block.

    Fixed demand profile: `demand` is the hourly demand [MWth] (input).
    Free demand profile: `demand` is None and `free_demand_days` holds
    [(hour indices of a day, required demand hours), ...]; the hourly
    demand becomes a decision variable.
    """

    n = len(prices)
    free_demand = free_demand_days is not None
    if not free_demand:
        assert len(demand) == n

    Q_HTHP_cap = _plant_param(plant, "Q_HTHP")
    COP = _plant_param(plant, "COP")
    E_TES_MAX = _plant_param(plant, "E_TES")

    if initial_E_TES > E_TES_MAX + 1e-9:
        raise ValueError(
            f"initial_E_TES ({initial_E_TES}) exceeds plant TES capacity "
            f"({E_TES_MAX})."
        )

    initial_hours_remaining = min(initial_hours_remaining, n)

    model = pyo.ConcreteModel()
    model.T = pyo.RangeSet(0, n - 1)

    model.Q_HTHP = pyo.Var(model.T, domain=pyo.Binary)
    model.start = pyo.Var(model.T, domain=pyo.Binary)
    model.E_TES = pyo.Var(range(n + 1), bounds=(0, E_TES_MAX))

    model.initial_storage = pyo.Constraint(expr=model.E_TES[0] == initial_E_TES)

    if free_demand:
        # process_on[t] = 1 -> the process takes Q_DEMAND_DEFAULT at hour t.
        # Exactly the required number of demand hours per calendar day.
        model.process_on = pyo.Var(model.T, domain=pyo.Binary)

        def daily_demand_rule(m, k):
            idx, hours = free_demand_days[k]
            return sum(m.process_on[t] for t in idx) == hours

        model.daily_demand = pyo.Constraint(
            range(len(free_demand_days)), rule=daily_demand_rule
        )

        def demand_at(m, t):
            return Q_DEMAND_DEFAULT * m.process_on[t]

    else:

        def demand_at(m, t):
            return demand[t]

    def tes_balance_rule(m, t):
        return m.E_TES[t + 1] == m.E_TES[t] + (
            Q_HTHP_cap * m.Q_HTHP[t] - demand_at(m, t)
        )

    model.tes_balance = pyo.Constraint(model.T, rule=tes_balance_rule)

    # Forced continuation of a run still in progress at the end of the
    # previous block.
    if initial_hours_remaining > 0:

        def forced_continuation_rule(m, t):
            if t < initial_hours_remaining:
                return m.Q_HTHP[t] == 1
            return pyo.Constraint.Skip

        model.forced_continuation = pyo.Constraint(
            model.T, rule=forced_continuation_rule
        )

    previous_on = 1 if initial_hours_remaining > 0 else 0

    def start_detection_rule(m, t):
        if t == 0:
            return m.start[t] >= m.Q_HTHP[t] - previous_on
        return m.start[t] >= m.Q_HTHP[t] - m.Q_HTHP[t - 1]

    model.start_detection = pyo.Constraint(model.T, rule=start_detection_rule)

    def minimum_runtime_rule(m, t):

        # A run that starts must stay ON for `min_on_hours`, UNLESS there
        # simply aren't that many hours left in the block - in that case
        # it must run continuously through to the last hour of the block
        # (never start and then stop early within that tail).
        #
        # This is the same requirement whether or not this is the final
        # block of the whole requested period:
        #   - non-final block: a run that only gets "window" hours here
        #     has its remaining mandatory hours forced at the start of
        #     the next block (see `forced_continuation_rule` /
        #     hours_remaining carried over by `optimize_operational_strategy`).
        #   - final block: a run that only gets "window" hours here runs
        #     right up to the true end of the requested period - there's
        #     nothing to chain into, so it's simply shorter than 12h, but
        #     it still may never start and stop within that tail without
        #     running continuously until the data ends.
        window = min(min_on_hours, n - t)
        return sum(m.Q_HTHP[t + k] for k in range(window)) >= window * m.start[t]

    model.minimum_runtime = pyo.Constraint(model.T, rule=minimum_runtime_rule)

    def objective_rule(m):
        return sum(prices[t] * (Q_HTHP_cap / COP) * m.Q_HTHP[t] for t in m.T)

    model.objective = pyo.Objective(rule=objective_rule, sense=pyo.minimize)

    solver = pyo.SolverFactory(solver_name)
    for key, value in (solver_options or {}).items():
        solver.options[key] = value

    result = solver.solve(model, tee=tee)

    status = str(result.solver.status)
    termination = str(result.solver.termination_condition)
    if status != "ok" or termination not in ("optimal", "feasible"):
        raise RuntimeError(
            "Solver did not find an acceptable solution "
            f"(status={status}, termination={termination})."
        )

    Q_HTHP_result = [round(pyo.value(model.Q_HTHP[t])) for t in model.T]
    if free_demand:
        Q_demand_result = [
            Q_DEMAND_DEFAULT * round(pyo.value(model.process_on[t])) for t in model.T
        ]
    else:
        Q_demand_result = [float(d) for d in demand]
    start_result = [round(pyo.value(model.start[t])) for t in model.T]
    E_TES_result = [pyo.value(model.E_TES[t]) for t in range(n + 1)]
    cost = pyo.value(model.objective)

    # Consecutive ON hours ending at the very last hour of the block.
    run_length = 0
    for q in reversed(Q_HTHP_result):
        if q == 1:
            run_length += 1
        else:
            break

    return _BlockResult(
        Q_HTHP=Q_HTHP_result,
        Q_demand=Q_demand_result,
        start=start_result,
        E_TES=E_TES_result,
        cost=cost,
        final_hours_running=run_length,
    )


# ============================================================================
# TOP-LEVEL RESULT CONTAINER
# ============================================================================


@dataclass
class OperationalStrategyResult:
    time: list  # datetime, one per hour
    Q_demand: list  # [MWth]
    Q_HTHP: list  # [MWth] (0 or Q_HTHP_cap)
    E_TES: list  # [MWhth], length len(time) + 1
    el_price: list  # [EUR/MWh]
    Q_TES: list  # net TES charge power [MWth] (+charging / -discharging)
    start: list  # 1 at hours where the HTHP starts a new run
    Q_el: list  # electricity power drawn by the HTHP [MWel]
    cost: list  # hourly electricity cost [EUR]
    total_cost: float
    total_operating_hours: float
    plant: PlantLike
    market: str
    heat_demand_profile: str = DEFAULT_HEAT_DEMAND_PROFILE


# ============================================================================
# TOP-LEVEL FUNCTION
# ============================================================================


def optimize_operational_strategy(
    plant,
    market: str = "DK1",
    month: Optional[int] = None,
    week: Optional[int] = None,
    year: int = 2025,
    heat_demand_profile: str = DEFAULT_HEAT_DEMAND_PROFILE,
    min_on_hours: int = 12,
    E_TES: Optional[float] = None,
    interface_hx_label: str = "interface hx",
    data_dir: Union[str, Path] = DEFAULT_DATA_DIR,
    solver_name: str = "glpk",
    solver_options: Optional[dict] = None,
    tee: bool = False,
    verbose: bool = True,
) -> OperationalStrategyResult:
    """Optimize the HTHP + TES operational strategy against day-ahead prices.

    Parameters
    ----------
    plant : Plant | dict | tespy.networks.Network
        Either a ``Plant`` instance / dict with COP, Q_HTHP [MWth] and
        E_TES [MWhth] directly, or a solved TESPy ``Network`` object, in
        which case COP and Q_HTHP are derived automatically (see
        ``derive_plant_from_tespy``) and `E_TES` below must be supplied.
    market : {"DK1", "DE"}
        Which day-ahead electricity price series to use.
    month : int, optional
        1-12. If given, the optimization runs over that calendar month
        only (as a sequence of chained weekly blocks). Mutually exclusive
        with `week`.
    week : int, optional
        1-based index of a single 168-hour block, counted from 1-Jan
        00:00 of `year`. Mutually exclusive with `month`. Runs as a
        single, standalone block (empty TES, no pending run at t=0).
    year : int
        Year to pull prices for (must match what's in the CSV; default
        2025).
    heat_demand_profile : {"fixed", "free"}
        Heat demand profile to simulate (see the module docstring).
        "fixed": 1 MWth from 06:00 to 22:00 every day.
        "free": 16 h of 1 MWth per day, with the hours
        chosen by the optimization. Its weekly blocks (and `week`) are 7
        whole calendar days instead of 168 hours, so a day is never split
        between two blocks.
    min_on_hours : int
        Minimum number of consecutive hours the HTHP must run once
        started. Fixed at 12 per the current plant specification.
    E_TES : float, optional
        TES capacity [MWhth]. Required (and only used) when `plant` is a
        raw TESPy Network rather than a Plant/dict - ignored otherwise.
    interface_hx_label : str
        Label of the interface heat exchanger component to look for when
        `plant` is a raw TESPy Network (default "interface hx").
    data_dir : str | Path
        Directory containing the market price CSVs.
    solver_name : str
        Pyomo solver name (default "glpk").
    solver_options : dict, optional
        Passed through to the solver (default: {"tmlim": 360,
        "mipgap": 0.01}).
    tee : bool
        If True, stream solver output for every block.
    verbose : bool
        If True (default), print a one-line banner describing the run
        before solving, and the total operating hours / total cost after.

    Returns
    -------
    OperationalStrategyResult
        Q_demand, Q_HTHP, E_TES, el_price and Q_TES (plus a few extra,
        convenience fields) for the whole requested period.

    Notes
    -----
    Internally the optimization is always solved in <=168-hour blocks.
    When the requested period spans more than one block (a month or the
    whole year), blocks are solved sequentially and chained: the TES
    energy level and any still-in-progress mandatory HTHP run carry over
    from one block into the next. See the module docstring for details.
    """

    if solver_options is None:
        solver_options = {"tmlim": 360, "mipgap": 0.01}

    heat_demand_profile = _check_heat_demand_profile(heat_demand_profile)
    free_demand = heat_demand_profile == "free"

    plant = _resolve_plant(plant, E_TES=E_TES, interface_hx_label=interface_hx_label)

    if verbose:
        if week is not None:
            period_desc = f"week {week}, {year}"
        elif month is not None:
            period_desc = f"month {month}, {year}"
        else:
            period_desc = f"year {year}"
        print(
            f"Optimizing plant dispatch strategy for {period_desc} "
            f"on the {market} market (heat demand profile: "
            f"{heat_demand_profile})..."
        )

    timestamps, prices = _load_price_series(market, year, Path(data_dir))
    demand = _demand_profile(timestamps)

    start_idx, end_idx = _select_period_indices(
        timestamps, month=month, week=week, calendar_weeks=free_demand
    )
    if free_demand:
        chunks = _chunk_into_calendar_weeks(timestamps, start_idx, end_idx)
    else:
        chunks = _chunk_into_weeks(start_idx, end_idx)

    Q_HTHP_cap = _plant_param(plant, "Q_HTHP")
    COP = _plant_param(plant, "COP")

    all_time: list = []
    all_Q_demand: list = []
    all_Q_HTHP: list = []
    all_E_TES: list = []
    all_el_price: list = []
    all_Q_TES: list = []
    all_start: list = []
    all_Q_el: list = []
    all_cost: list = []

    E_TES_state = 0.0
    hours_remaining_state = 0

    for i, (c_start, c_end) in enumerate(chunks):

        chunk_prices = prices[c_start:c_end]
        chunk_demand = demand[c_start:c_end]
        chunk_time = timestamps[c_start:c_end]

        block = _solve_block(
            chunk_prices,
            None if free_demand else chunk_demand,
            plant,
            min_on_hours=min_on_hours,
            initial_E_TES=E_TES_state,
            initial_hours_remaining=hours_remaining_state,
            solver_name=solver_name,
            solver_options=solver_options,
            tee=tee,
            is_final_block=(i == len(chunks) - 1),
            free_demand_days=(
                _daily_demand_requirements(chunk_time) if free_demand else None
            ),
        )

        all_time.extend(chunk_time)
        all_Q_demand.extend(block.Q_demand)
        all_Q_HTHP.extend(block.Q_HTHP)
        all_start.extend(block.start)
        all_el_price.extend(chunk_prices)

        Q_TES_chunk = [Q_HTHP_cap * q - d for q, d in zip(block.Q_HTHP, block.Q_demand)]
        all_Q_TES.extend(Q_TES_chunk)

        Q_el_chunk = [Q_HTHP_cap * q / COP for q in block.Q_HTHP]
        all_Q_el.extend(Q_el_chunk)

        cost_chunk = [p * qel for p, qel in zip(chunk_prices, Q_el_chunk)]
        all_cost.extend(cost_chunk)

        # E_TES has n+1 points per block; drop the duplicated boundary
        # point for every block after the first.
        if i == 0:
            all_E_TES.extend(block.E_TES)
        else:
            all_E_TES.extend(block.E_TES[1:])

        E_TES_state = block.E_TES[-1]
        hours_remaining_state = (
            max(0, min_on_hours - block.final_hours_running)
            if block.final_hours_running > 0
            else 0
        )

    if verbose:
        print(f"Total HTHP operating hours: {sum(all_Q_HTHP):.0f} h")
        print(f"Total electricity cost: {sum(all_cost):.2f} EUR")

    return OperationalStrategyResult(
        time=all_time,
        Q_demand=all_Q_demand,
        Q_HTHP=all_Q_HTHP,
        E_TES=all_E_TES,
        el_price=all_el_price,
        Q_TES=all_Q_TES,
        start=all_start,
        Q_el=all_Q_el,
        cost=all_cost,
        total_cost=sum(all_cost),
        total_operating_hours=sum(all_Q_HTHP),
        plant=plant,
        market=market,
        heat_demand_profile=heat_demand_profile,
    )
