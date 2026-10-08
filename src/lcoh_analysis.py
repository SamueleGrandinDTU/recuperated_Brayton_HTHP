"""
src/lcoh_analysis.py

Building blocks for the LCOH (levelized cost of heat) analysis.

Currently contains ``calculate_future_costs``: it takes the annual
electricity cost computed for the reference year 2025 (e.g. the result of
``optimize_operational_strategy``) and extends it to the future by
multiplying it, year by year, with the electricity-price scaling factors
of a forecast source (currently "Energinet": low / central / high
scenarios, interpolated between the 2030, 2040 and 2050 anchors).

``perform_lcoh_analysis`` then turns those yearly costs into a levelized
cost of heat for each scenario.

Standalone by design: nothing is imported from ``plant_operation``;
result objects are read by duck typing.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

_DATA_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "electricity_prices"
)

# Forecast source -> scenario csv. Each file needs a "year" column and one
# "<scenario>_factor_vs_2025" column per scenario (low / central / high).
SCENARIO_FILES = {
    "Energinet": "dk1_energinet_2025_2050_scenarios.csv",
}

SCENARIOS = ("low", "central", "high")

REFERENCE_YEAR = 2025


def _load_scenario_factors(source: str) -> pd.DataFrame:
    """Scaling factors of a forecast source, indexed by year, one column
    per scenario (low / central / high)."""

    try:
        filename = SCENARIO_FILES[source]
    except KeyError as exc:
        raise ValueError(
            f"Unknown forecast source '{source}'. Available sources: "
            f"{sorted(SCENARIO_FILES)}"
        ) from exc

    path = _DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find the '{source}' scenario file at '{path}'."
        )

    df = pd.read_csv(path)

    factors = df.set_index("year")[[f"{s}_factor_vs_2025" for s in SCENARIOS]]
    factors.columns = list(SCENARIOS)
    return factors


def _future_costs(reference_cost, source: str):
    """Silent core of ``calculate_future_costs``: returns the DataFrame and
    the reference cost as a float."""

    if hasattr(reference_cost, "total_cost"):
        reference_cost = reference_cost.total_cost
    reference_cost = float(reference_cost)

    factors = _load_scenario_factors(source)

    costs = factors * reference_cost
    costs.index.name = "Year"
    costs.columns = [f"{s.capitalize()} [EUR]" for s in SCENARIOS]
    return costs, reference_cost


def calculate_future_costs(reference_cost, source: str = "Energinet") -> pd.DataFrame:
    """Extend the 2025 annual electricity cost to 2026-2050, per scenario.

    For every year and every scenario (low / central / high):

        cost(year, scenario) = reference_cost * factor(year, scenario)

    Parameters
    ----------
    reference_cost : float | object with `total_cost`
        Full-year 2025 electricity cost [EUR] - either the number itself,
        or the ``OperationalStrategyResult`` returned by
        ``optimize_operational_strategy`` (its `total_cost` is used).
    source : {"Energinet"}
        Forecast source providing the scaling factors.

    Returns
    -------
    pandas.DataFrame
        Index "Year"; columns "Low [EUR]", "Central [EUR]", "High [EUR]".
        The table is also printed in the terminal.
    """

    costs, reference_cost = _future_costs(reference_cost, source)

    print(
        f"Future costs calculated starting from {REFERENCE_YEAR} "
        f"(reference cost: {reference_cost:,.2f} EUR) with the {source} "
        "forecasting assumptions."
    )
    print(costs.to_string(float_format=lambda v: f"{v:,.2f}"))

    return costs


# ============================================================================
# LCOH
# ============================================================================

# Operation starts the year after the reference year: n = 0 is the
# investment (CAPEX), n = 1 is the first operating year (2026).
FIRST_OPERATION_YEAR = REFERENCE_YEAR + 1

# Operating-cost assumptions
OM_FRACTION_OF_CAPEX = 0.01  # O&M = 1 % of the initial CAPEX per year
FTE = 0.05  # full-time equivalent
N_PERSONNEL = 1
C_LABOUR = 50.0  # labour intensity [EUR/h]

# Keys / attribute names tried, in order, to read a total CAPEX off an
# object or dict (e.g. the output of `calculate_component_cost`).
_COMPONENT_COST_COLUMN = "Cost [M€]"  # column of calculate_component_cost's table
_CAPEX_NAMES = ("total_capex", "capex", "CAPEX", "total_cost", "total")


@dataclass
class LCOHResult:
    lcoh: dict  # scenario -> LCOH [EUR/MWh]
    cash_flows: dict  # scenario -> year-by-year DataFrame


def _capex_value(capex) -> float:
    """Total CAPEX [EUR] from a number, from the component cost table
    returned by ``calculate_component_cost`` (sum of its "Cost [M€]"
    column, i.e. the table's own "Total plant cost"), or from an
    object / dict exposing the total."""

    if isinstance(capex, pd.DataFrame):
        if _COMPONENT_COST_COLUMN not in capex.columns:
            raise ValueError(
                f"The component cost table has no '{_COMPONENT_COST_COLUMN}' "
                f"column (columns: {list(capex.columns)})."
            )
        return float(capex[_COMPONENT_COST_COLUMN].sum()) * 1e6

    for name in _CAPEX_NAMES:
        if isinstance(capex, dict) and name in capex:
            return float(capex[name])
        if hasattr(capex, name) and not callable(getattr(capex, name)):
            return float(getattr(capex, name))
    try:
        return float(capex)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "Could not read a total CAPEX from the given `capex` input. "
            "Pass the total as a number, or an object/dict with one of "
            f"these names: {list(_CAPEX_NAMES)}."
        ) from exc


def perform_lcoh_analysis(
    lifetime: int,
    component_cost=None,
    operational_result=None,
    capex=None,
    cost_2025=None,
    yearly_heat_production=None,
    operating_hours=None,
    source: str = "Energinet",
    discount_rate: float = 0.05,
    degradation_rate: float = 0.002,
    decommissioning: float = 0.015,
    future_costs: pd.DataFrame = None,
) -> LCOHResult:
    """Levelized cost of heat for the low / central / high scenarios.

        LCOH = [ CAPEX + sum_n OPEX_n / (1+d)^n + c_decomm / (1+d)^(N+1) ]
               / sum_n E_load * (1-eps)^n / (1+d)^n          n = 1 ... N

    with, for every operating year n:

        OPEX_n = electricity cost(n) + O&M + labour
        O&M    = 1 % of CAPEX
        labour = t_op * FTE * n_personnel * c_labour   (0.05, 1, 50 EUR/h)

    Year n = 1 is 2026 (the year after the 2025 reference year).

    Every plant-specific input can be given in two ways: pass the result
    object of the function that produces it and the value is taken from
    there, or pass the value itself. If both are given, the value passed
    directly wins.

        CAPEX                   <- component_cost       | capex
        2025 electricity cost   <- operational_result   | cost_2025
        yearly heat production  <- operational_result   | yearly_heat_production
        operating hours         <- operational_result   | operating_hours

    Parameters
    ----------
    lifetime : int
        Number of operating years N (at most 25, the forecast ends 2050).
    component_cost : object | dict, optional
        The component cost table returned by ``calculate_component_cost``;
        the total CAPEX is the sum of its "Cost [M€]" column, converted
        to EUR.
    operational_result : OperationalStrategyResult, optional
        Output of ``optimize_operational_strategy`` for a full year. Used:
        `total_cost` (2025 electricity cost), the sum of `Q_demand`
        (delivered heat) and `total_operating_hours`.
    capex : float, optional
        Total initial investment [EUR].
    cost_2025 : float, optional
        Full-year 2025 electricity cost [EUR].
    yearly_heat_production : float, optional
        Delivered heat in the first year E_load [MWh].
    operating_hours : float, optional
        Annual operating hours t_op [h], used for the labour cost.
    source : {"Energinet"}
        Reference electricity-price assumptions (forecast scenarios), as
        in ``calculate_future_costs``.
    discount_rate : float
        d, default 5 %.
    degradation_rate : float
        eps, yearly loss of delivered heat, default 0.2 %.
    decommissioning : float
        Decommissioning cost as a fraction of CAPEX, default 1.5 %.
    future_costs : DataFrame, optional
        Output of ``calculate_future_costs``. If None, it is calculated
        here from the 2025 cost with the `source` assumptions.

    Returns
    -------
    LCOHResult
        `lcoh` {scenario: EUR/MWh} and `cash_flows` {scenario: DataFrame}.
        The year-by-year tables and the LCOH values are also printed.
    """

    if source not in SCENARIO_FILES:
        raise ValueError(
            f"Unknown forecast source '{source}'. Available sources: "
            f"{sorted(SCENARIO_FILES)}"
        )

    def missing(name, from_result):
        return ValueError(
            f"`{name}` is missing: pass it directly, or pass {from_result}."
        )

    # ---- resolve the plant-specific inputs ------------------------------
    if capex is None:
        if component_cost is None:
            raise missing(
                "capex", "`component_cost` (the calculate_component_cost output)"
            )
        capex = component_cost
    capex_value = _capex_value(capex)

    if cost_2025 is None:
        if operational_result is None:
            raise missing(
                "cost_2025",
                "`operational_result` (the optimize_operational_strategy result)",
            )
        cost_2025 = operational_result.total_cost
    cost_value = float(cost_2025)

    if yearly_heat_production is None:
        if operational_result is None:
            raise missing(
                "yearly_heat_production",
                "`operational_result` (the optimize_operational_strategy result)",
            )
        yearly_heat_production = sum(operational_result.Q_demand)
    heat = float(yearly_heat_production)

    if operating_hours is None:
        if operational_result is None:
            raise missing(
                "operating_hours",
                "`operational_result` (the optimize_operational_strategy result)",
            )
        operating_hours = operational_result.total_operating_hours
    operating_hours = float(operating_hours)

    if lifetime != int(lifetime) or lifetime < 1:
        raise ValueError("`lifetime` must be a positive whole number of years.")
    lifetime = int(lifetime)
    if heat <= 0:
        raise ValueError("The yearly heat production must be positive.")

    if future_costs is None:
        future_costs, _ = _future_costs(cost_value, source)

    op_years = [FIRST_OPERATION_YEAR + n - 1 for n in range(1, lifetime + 1)]
    missing = [y for y in op_years if y not in future_costs.index]
    if missing:
        raise ValueError(
            f"No future electricity cost available for year(s) {missing}: the "
            f"forecast covers {future_costs.index.min()}-{future_costs.index.max()}."
        )

    om = OM_FRACTION_OF_CAPEX * capex_value
    labour = operating_hours * FTE * N_PERSONNEL * C_LABOUR
    c_decomm = decommissioning * capex_value
    d = discount_rate

    print(
        f"LCOH analysis: CAPEX {capex_value:,.0f} EUR | lifetime {lifetime} y "
        f"(operation {op_years[0]}-{op_years[-1]}) | discount rate {d:.1%} | "
        f"degradation {degradation_rate:.1%}/y | decommissioning "
        f"{c_decomm:,.0f} EUR ({decommissioning:.1%} of CAPEX)"
    )
    print(
        f"Yearly heat production: {heat:,.1f} MWh | operating hours: "
        f"{operating_hours:,.0f} h | O&M: {om:,.0f} EUR/y | labour: "
        f"{labour:,.0f} EUR/y"
    )

    lcoh_values = {}
    tables = {}
    breakdown = {}

    for scenario in SCENARIOS:
        col = f"{scenario.capitalize()} [EUR]"

        rows = [dict(n=0, Year=FIRST_OPERATION_YEAR - 1, invest=capex_value, heat=0.0)]
        for n, year in enumerate(op_years, start=1):
            rows.append(
                dict(
                    n=n,
                    Year=year,
                    electricity=float(future_costs.loc[year, col]),
                    om=om,
                    labour=labour,
                    heat=heat * (1 - degradation_rate) ** n,
                )
            )
        rows.append(
            dict(n=lifetime + 1, Year=op_years[-1] + 1, invest=c_decomm, heat=0.0)
        )

        df = pd.DataFrame(rows).fillna(0.0)
        df["cash"] = df[["invest", "electricity", "om", "labour"]].sum(axis=1)
        discount = (1 + d) ** df["n"]
        df["disc_cash"] = df["cash"] / discount
        df["disc_heat"] = df["heat"] / discount

        lcoh = float(df["disc_cash"].sum() / df["disc_heat"].sum())
        lcoh_values[scenario] = lcoh
        breakdown[scenario] = {
            "CAPEX": df["invest"][df["n"] == 0].sum(),
            "Electricity": (df["electricity"] / discount).sum(),
            "O&M": (df["om"] / discount).sum(),
            "Labour": (df["labour"] / discount).sum(),
            "Decommissioning": df["invest"][df["n"] == lifetime + 1].sum()
            / (1 + d) ** (lifetime + 1),
            "Total discounted cost": df["disc_cash"].sum(),
            "Discounted heat": df["disc_heat"].sum(),
        }

        out = df.rename(
            columns={
                "electricity": "Electricity",
                "om": "O&M",
                "labour": "Labour",
                "invest": "CAPEX/Decomm.",
                "cash": "Cash flow",
                "disc_cash": "Disc. cash flow",
                "heat": "Heat",
                "disc_heat": "Disc. heat",
            }
        )[
            [
                "n",
                "Year",
                "Electricity",
                "O&M",
                "Labour",
                "CAPEX/Decomm.",
                "Cash flow",
                "Disc. cash flow",
                "Heat",
                "Disc. heat",
            ]
        ]
        tables[scenario] = out

        money = lambda v: f"{v:,.0f}"
        print(
            f"\n{scenario.capitalize()} scenario  (costs in EUR, heat in MWh; "
            "n = 0 is the CAPEX, the last row the decommissioning)"
        )
        print(
            out.to_string(
                index=False,
                formatters={
                    "Electricity": money,
                    "O&M": money,
                    "Labour": money,
                    "CAPEX/Decomm.": money,
                    "Cash flow": money,
                    "Disc. cash flow": money,
                    "Heat": lambda v: f"{v:,.1f}",
                    "Disc. heat": lambda v: f"{v:,.1f}",
                },
            )
        )

    # ---- final summary -------------------------------------------------
    print("\n" + "=" * 78)
    print("LCOH RESULT")
    print("=" * 78)
    print(
        f"LCOH = (CAPEX + discounted OPEX + discounted decommissioning) / "
        f"discounted heat production"
    )
    print(
        f"Electricity prices: {source} forecast, 2025 reference cost "
        f"{cost_value:,.0f} EUR | operation {op_years[0]}-{op_years[-1]} "
        f"({lifetime} years)"
    )
    print(
        f"CAPEX {capex_value:,.0f} EUR | O&M {OM_FRACTION_OF_CAPEX:.0%} of CAPEX "
        f"({om:,.0f} EUR/y) | labour {labour:,.0f} EUR/y "
        f"({operating_hours:,.0f} h x {FTE} FTE x {N_PERSONNEL} person x "
        f"{C_LABOUR:.0f} EUR/h)"
    )
    print(
        f"Discount rate {d:.1%} | heat degradation {degradation_rate:.1%}/y | "
        f"decommissioning {c_decomm:,.0f} EUR ({decommissioning:.1%} of CAPEX, "
        f"paid in year {lifetime + 1}) | yearly heat {heat:,.1f} MWh"
    )

    summary = pd.DataFrame(breakdown)
    summary.columns = [s_.capitalize() for s_ in SCENARIOS]
    summary.loc["LCOH [EUR/MWh]"] = [lcoh_values[s_] for s_ in SCENARIOS]
    print("\nDiscounted costs [EUR], discounted heat [MWh] and resulting LCOH:")
    print(
        summary.to_string(
            formatters={
                c: (lambda v: f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}")
                for c in summary.columns
            }
        )
    )
    print(
        "\nLCOH: "
        + " | ".join(f"{s_} {lcoh_values[s_]:.2f}" for s_ in SCENARIOS)
        + " EUR/MWh"
    )

    return LCOHResult(lcoh=lcoh_values, cash_flows=tables)
