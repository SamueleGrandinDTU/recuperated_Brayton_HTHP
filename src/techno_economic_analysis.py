"""
src/techno_economic_analysis.py

Single entry point of the techno-economic assessment of the four HTHP layouts.

``run_techno_economic_assessment`` runs, for every requested layout, the chain

    plant model -> design simulation -> tables and diagrams -> exergy analysis
    -> tank sizing (TES layouts) -> component cost
    -> operational optimisation on 2025 prices -> LCOH (Energinet forecasts)

and, in the next development steps, the comparison figures.

Layouts
-------
    "S-BR"   : standalone, base recuperated
    "S-IR"   : standalone, intercooled recuperated
    "TES-BR" : TES-integrated, base recuperated
    "TES-IR" : TES-integrated, intercooled recuperated

Everything is saved under ``save_path`` with the structure

    <save_path>/plots/                       T-s and heat-exchanger diagrams
    <save_path>/tables/<table type>/         performance_parameters,
                                             sizing_parameters, connections,
                                             hx, components_exergy,
                                             components_cost, lcoh
    <save_path>/validation/                  validation against the reference

and the file names ``<S_BR | S_IR | TES_BR | TES_IR>_hthp_...``.

STATUS: the per-layout solution, post-processing, operational optimisation and
LCOH analysis are implemented. The week-1 operation results and the
`comparison` figures are still to be added.
"""

import warnings
from pathlib import Path
from typing import Optional, Sequence, Union
import re

import pandas as pd

from src import (
    create_configured_network,
    standalone_base_recup_hthp,
    standalone_base_recup_hthp_Benvenuti,
    standalone_interc_recup_hthp,
    tes_integr_base_recup_hthp,
    tes_integr_interc_recup_hthp,
    plot_ts_diagram,
    plot_hx_diagram,
    save_hx_table,
    generate_performance_parameters_table,
    generate_sizing_parameters_table,
    generate_connections_table,
    get_exergy_analysis,
    validate_plant,
    calculate_tanks_geometry,
    calculate_component_cost,
    optimize_operational_strategy,
    perform_lcoh_analysis,
    plot_exergy_plots,
    save_hx_table,
    plot_component_cost_stacked,
    plot_operational_strategy,
    plot_lcoh_scenarios_stacked,
    plot_delta_lcoh_analysis,
    plot_lcoh_breakdown_stacked,
)

# Allowed values of the three case-defining inputs.
VALID_LAYOUTS = ("S-BR", "S-IR", "TES-BR", "TES-IR")
VALID_PRICE_ZONES = ("DK1", "DE")
VALID_HEAT_DEMAND_SCHEDULES = ("fixed", "variable")

# The schedule is called "variable" in this interface and "free" in
# optimize_operational_strategy (heat_demand_profile) and in the saved LCOH
# tables ("DK1 free", ...).
SCHEDULE_ALIASES = {"fixed": "fixed", "variable": "free"}

VALID_SCENARIOS = ("low", "central", "high")

# Keys accepted in the `comparison` dictionary. The exergy key is a tuple
# because both plots are drawn on one figure.
VALID_COMPARISONS = (
    "ts_diagram",
    "hx_diagram",
    ("exergy_destruction", "exergy_efficiency"),
    "capex_breakdown",
    "operational_strategy",
    "lcoh_scenario",
    "delta_lcoh",
    "lcoh_breakdown",
)

# Reference data of the validation case (Benvenuti recuperated configuration).
VALIDATION_REFERENCE_CSV = "data/processed/Benvenuti_validation_recuperated.csv"

# Storage duration used to size the TES tanks [h].
TES_STORAGE_DURATION_H = 8

# TES energy capacity used in the operational optimisation [MWh]. Standalone
# layouts have no storage (0).
TES_CAPACITY_MWH = 8.0

# Reference year of the operational optimisation (prices of 2025).
REFERENCE_YEAR = 2025

# Week of 2025 (counted from 1 January) simulated for every layout, price zone
# and heat demand schedule, before the LCOH analysis.
OPERATION_WEEK = 1

# LCOH analysis: plant lifetime [years], and the market whose price forecast
# scales the 2025 electricity cost of EVERY price zone: "DK1" is the Energinet
# forecast, "DE" would be the vbw forecast.
LCOH_LIFETIME_YEARS = 25
LCOH_FORECAST_MARKET = "DK1"

# Everything that differs between the layouts:
#   model            plant class of src.models
#   validation_model plant class with the parameters of the validation case
#                    (None: the layout has no reference data)
#   hx_components    labels of the heat exchangers shown in the hx diagram and
#                    saved in the hx table, in series order
#   tes              True: size the TES tanks (connections "t1" and "t2") and
#                    include them in the component cost
LAYOUT_SETUP = {
    "S-BR": {
        "model": standalone_base_recup_hthp,
        "validation_model": standalone_base_recup_hthp_Benvenuti,
        "hx_components": ["sink"],
        "tes": False,
    },
    "S-IR": {
        "model": standalone_interc_recup_hthp,
        "validation_model": None,
        "hx_components": ["sink 1", "sink 2"],
        "tes": False,
    },
    "TES-BR": {
        "model": tes_integr_base_recup_hthp,
        "validation_model": None,
        "hx_components": ["interface hx"],
        "tes": True,
    },
    "TES-IR": {
        "model": tes_integr_interc_recup_hthp,
        "validation_model": None,
        "hx_components": ["interface hx"],
        "tes": True,
    },
}


def _as_list(value):
    """A single string becomes a one-item list; other sequences become lists."""
    return [value] if isinstance(value, str) else list(value)


def _check_values(name, values, valid):
    """Raise a clear error if `values` contains something not in `valid`."""
    unknown = [v for v in values if v not in valid]
    if unknown:
        raise ValueError(f"Unknown {name} {unknown}. Valid values: {list(valid)}.")


def _file_name(layout):
    """Base file name of a layout: "S-BR" -> "S_BR_hthp"."""
    return f"{layout.replace('-', '_')}_hthp"


def _solve_design(model_class):
    """Build a plant model into a new network and solve the design point."""
    network = create_configured_network()
    model_class().build_into(network)
    network.solve(mode="design")
    network.print_results()
    return network


def _validate_layout(layout, save_root):
    """Solve the validation case of a layout and compare it with the
    reference data. Layouts without reference data are skipped."""
    validation_model = LAYOUT_SETUP[layout]["validation_model"]
    if validation_model is None:
        return None

    print(f"\n--- {layout}: validation against the reference data ---")
    plant_validation = _solve_design(validation_model)
    return validate_plant(
        plant_validation,
        VALIDATION_REFERENCE_CSV,
        title_name=f"{layout} validation",
        file_name=f"{_file_name(layout)}_Benvenuti",
        save_path=save_root / "validation",
    )


def _run_layout(layout, save_root):
    """Solve one layout at the design point and generate its diagrams and
    tables. Returns the solved network and the numerical results."""
    setup = LAYOUT_SETUP[layout]
    file_name = _file_name(layout)
    plots = save_root / "plots"
    tables = save_root / "tables"

    # 1. Solve the design point
    print(f"\n--- {layout}: design point ---")
    plant = _solve_design(setup["model"])

    # 2. T-s diagram and heat-exchanger diagram
    hx_components = [
        plant.comps.loc[label, "object"] for label in setup["hx_components"]
    ]
    # (not saved: the saved diagrams are the comparison ones)
    plot_ts_diagram(plant, file_name=file_name, save_path=None)
    plot_hx_diagram(hx_components, file_name=file_name, save_path=None)

    # 3. Performance, sizing, connections and heat-exchanger tables
    generate_performance_parameters_table(
        plant, file_name=file_name, save_path=tables / "performance_parameters"
    )
    generate_sizing_parameters_table(
        plant, file_name=file_name, save_path=tables / "sizing_parameters"
    )
    generate_connections_table(
        plant, file_name=file_name, save_path=tables / "connections"
    )
    save_hx_table(hx_components, file_name=file_name, save_path=tables / "hx")

    # 4. Exergy analysis
    exergy = get_exergy_analysis(
        plant, file_name=file_name, save_path=tables / "components_exergy"
    )

    # 5. TES tank sizing (TES layouts only) and component cost
    tanks = None
    if setup["tes"]:
        tanks = list(
            calculate_tanks_geometry(
                plant, ["t1", "t2"], storage_duration=TES_STORAGE_DURATION_H
            )
        )
    cost = calculate_component_cost(
        plant,
        tanks,
        file_name=file_name,
        save_path=tables / "components_cost",
    )

    return {"plant": plant, "exergy": exergy, "tanks": tanks, "cost": cost}


def _lcoh_file(layout, save_root):
    """Path of the LCOH table of a layout."""
    return save_root / "tables" / "lcoh" / f"{_file_name(layout)}_lcoh.csv"


def _simulate_week_operation(layout, layout_results, price_zones, schedules):
    """Optimise the operation of a layout during week OPERATION_WEEK of 2025,
    for every price zone and heat demand schedule. Returns the results as
    {(zone, schedule): operational result}."""
    setup = LAYOUT_SETUP[layout]
    e_tes = TES_CAPACITY_MWH if setup["tes"] else 0.0

    operation = {}
    for schedule in schedules:
        profile = SCHEDULE_ALIASES[schedule]
        for zone in price_zones:
            print(
                f"\n--- {layout}: week {OPERATION_WEEK} on {zone}, "
                f"{schedule} heat demand ---"
            )
            operation[(zone, schedule)] = optimize_operational_strategy(
                layout_results["plant"],
                E_TES=e_tes,
                market=zone,
                year=REFERENCE_YEAR,
                week=OPERATION_WEEK,
                heat_demand_profile=profile,
            )
    return operation


def _lcoh_columns(price_zones, schedules):
    """Column names of the LCOH table ("DK1 fixed", "DE fixed", "DK1 free",
    ...): schedule by schedule, price zone by price zone."""
    return [f"{zone} {SCHEDULE_ALIASES[s]}" for s in schedules for zone in price_zones]


def _simulate_operation_and_lcoh(
    layout, layout_results, price_zones, schedules, week, month, save_root
):
    """Optimise the operation of a layout on every price zone and heat demand
    schedule and, for full-year runs, calculate and save the LCOH.

    With a `week` or `month` only that period is optimised: the LCOH needs the
    yearly electricity cost, so it is skipped and nothing is saved.
    """
    setup = LAYOUT_SETUP[layout]
    plant = layout_results["plant"]
    e_tes = TES_CAPACITY_MWH if setup["tes"] else 0.0
    full_year = week is None and month is None

    operation, lcoh, table = {}, {}, {}
    for schedule in schedules:
        profile = SCHEDULE_ALIASES[schedule]
        for zone in price_zones:
            print(f"\n--- {layout}: operation on {zone}, {schedule} heat demand ---")
            result = optimize_operational_strategy(
                plant,
                E_TES=e_tes,
                market=zone,
                year=REFERENCE_YEAR,
                month=month,
                week=week,
                heat_demand_profile=profile,
            )
            operation[(zone, schedule)] = result
            if not full_year:
                continue

            # Every zone is scaled with the same forecast, chosen on purpose:
            # silence the warning for a forecast of another price zone.
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="The 2025 cost was calculated for the"
                )
                lcoh_result = perform_lcoh_analysis(
                    lifetime=LCOH_LIFETIME_YEARS,
                    component_cost=layout_results["cost"],
                    operational_result=result,
                    market=LCOH_FORECAST_MARKET,
                )
            lcoh[(zone, schedule)] = lcoh_result
            table[f"{zone} {profile}"] = [lcoh_result.lcoh[s] for s in VALID_SCENARIOS]

    layout_results["operation"] = operation
    if not full_year:
        print(f"\n{layout}: LCOH skipped (it needs the operation of the whole year).")
        return

    lcoh_table = pd.DataFrame(table, index=[s.capitalize() for s in VALID_SCENARIOS])
    lcoh_table = lcoh_table.round(2)
    lcoh_table.index.name = "scenario"
    path = _lcoh_file(layout, save_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lcoh_table.to_csv(path)
    print(f"✓ Table saved: {path}")

    layout_results["lcoh"] = lcoh
    _save_lcoh_breakdown(layout, lcoh, save_root)
    layout_results["lcoh_table"] = lcoh_table.reset_index()
    _print_lcoh_table(layout, layout_results["lcoh_table"])


def _read_lcoh_table(layout, price_zones, schedules, save_root):
    """Read the saved LCOH table of a layout (columns of the requested price
    zones and schedules) instead of simulating it."""
    path = _lcoh_file(layout, save_root)
    if not path.exists():
        raise FileNotFoundError(
            f"No saved LCOH table for {layout} at '{path}'. Run once with "
            "lcoh_results=False to generate it."
        )
    table = pd.read_csv(path)
    columns = _lcoh_columns(price_zones, schedules)
    missing = [c for c in columns if c not in table.columns]
    if missing:
        raise ValueError(
            f"'{path}' has no column(s) {missing}. Run with lcoh_results=False "
            "for these price zones and schedules."
        )
    return table[["scenario"] + columns]


def _print_lcoh_table(layout, table):
    """Show the LCOH table of a layout in the command view."""
    print(f"\n{'=' * 78}\n  LCOH {layout} [EUR/MWh]\n{'=' * 78}")
    print(table.to_string(index=False))


def _comparison_layouts(key, spec):
    """Layout names of a comparison entry: a list of layouts, or a list of
    lists of layouts."""
    error = ValueError(
        f"comparison['{key}'] must be a list of layouts or a list of lists of "
        f"layouts, e.g. ['S-BR', 'S-IR'] or [['S-BR', 'TES-BR'], ['S-IR', 'TES-IR']]."
    )
    if not isinstance(spec, (list, tuple)) or not spec:
        raise error
    groups = [spec] if all(isinstance(item, str) for item in spec) else list(spec)
    names = []
    for group in groups:
        if not isinstance(group, (list, tuple)) or not all(
            isinstance(layout, str) for layout in group
        ):
            raise error
        names.extend(group)
    return names


def _map_layouts(spec, function):
    """Apply `function` to every layout of a flat list or of a list of lists,
    keeping the structure."""
    if all(isinstance(item, str) for item in spec):
        return [function(layout) for layout in spec]
    return [[function(layout) for layout in group] for group in spec]


def _plot_ts_comparison(spec, results, save_root, file_name):
    """T-s diagrams from the saved connections tables. A flat list of layouts
    gives one diagram with all the cycles overlaid; a list of lists gives one
    diagram per inner list, side by side."""
    plot_ts_diagram(
        _map_layouts(
            spec,
            lambda layout: save_root
            / "tables"
            / "connections"
            / f"{_file_name(layout)}_connections.csv",
        ),
        cycle_labels=_map_layouts(spec, lambda layout: layout),
        save_path=save_root / "plots",
        file_name=file_name,
    )


def _plot_hx_comparison(spec, results, save_root, file_name):
    """Heat-exchanger diagrams from the saved hx tables: one diagram per
    layout, side by side."""
    plot_hx_diagram(
        [
            [save_root / "tables" / "hx" / f"{_file_name(layout)}_hx_table.csv"]
            for layout in spec
        ],
        save_path=save_root / "plots",
        file_name=file_name,
    )


def _plot_exergy_comparison(spec, results, save_root, file_name):
    """Exergy destruction (stacked, one bar per layout) and exergetic
    efficiency per component, side by side on one figure, from the saved
    exergy tables."""
    plot_exergy_plots(
        [
            save_root
            / "tables"
            / "components_exergy"
            / f"{_file_name(layout)}_exergy_components.csv"
            for layout in spec
        ],
        cycle_labels=list(spec),
        plots=["destruction", "efficiencies"],
        combined=True,
        layout="horizontal",
        save_path=save_root / "plots",
        file_name=file_name,
    )


def _plot_capex_comparison(spec, results, save_root, file_name):
    """Component cost, one stacked bar per layout, from the saved component
    cost tables."""
    plot_component_cost_stacked(
        [
            save_root
            / "tables"
            / "components_cost"
            / f"{_file_name(layout)}_components_cost.csv"
            for layout in spec
        ],
        cycle_labels=list(spec),
        save_path=save_root / "plots",
        file_name=file_name,
    )


# Row labels of the operational strategy figure, one per heat demand schedule.
SCHEDULE_LABELS = {
    "fixed": "Fixed heat demand schedule",
    "variable": "Variable heat demand schedule",
}


def _parse_operational_spec(spec):
    """Split the operational_strategy entry [layouts, price zone, heat demand
    schedules, "week n"] into (layouts, zone, schedules, week number)."""
    error = ValueError(
        "comparison['operational_strategy'] must be [layouts, price zone, heat "
        "demand schedules, 'week n'], e.g. "
        "[['S-BR', 'TES-BR'], 'DK1', ['fixed', 'variable'], 'week 1']."
    )
    if not isinstance(spec, (list, tuple)) or len(spec) != 4:
        raise error
    layouts, zone, schedules, week = spec
    if not isinstance(zone, str) or not isinstance(week, str):
        raise error
    match = re.fullmatch(r"week\s*(\d+)", week.strip().lower())
    if match is None:
        raise error
    return _as_list(layouts), zone, _as_list(schedules), int(match.group(1))


def _plot_operational_comparison(spec, results, save_root, file_name):
    """Operation of the week simulated for every layout: a grid with one
    column per layout and one row per heat demand schedule, from the
    operational results kept in `results`."""
    layouts, zone, schedules, _ = _parse_operational_spec(spec)
    grid = [
        [results[layout]["week_operation"][(zone, schedule)] for layout in layouts]
        for schedule in schedules
    ]
    plot_operational_strategy(
        grid,
        file_name=file_name,
        save_path=save_root / "plots",
        row_labels=[SCHEDULE_LABELS[schedule] for schedule in schedules],
        col_labels=list(layouts),
    )


def _lcoh_column(zone, schedule):
    """Column of the LCOH tables of a price zone and schedule ("DK1 fixed",
    "DE free", ...)."""
    return f"{zone} {SCHEDULE_ALIASES[schedule]}"


def _breakdown_file(layout, save_root):
    """Path of the central-scenario LCOH breakdown of a layout."""
    return save_root / "tables" / "lcoh" / f"{_file_name(layout)}_lcoh_breakdown.csv"


def _save_lcoh_breakdown(layout, lcoh, save_root):
    """Save the central-scenario breakdown of the LCOH (discounted costs
    [EUR] and heat [MWh]) of every price zone and schedule of a layout."""
    rows = []
    for (zone, schedule), result in lcoh.items():
        central = result.breakdown["central"]
        rows.append(
            {
                "Cycle": layout,
                "Forecast": zone,
                "Demand": SCHEDULE_ALIASES[schedule],
                "Electricity [EUR]": central["Electricity"],
                "O&M [EUR]": central["O&M"],
                "Labour [EUR]": central["Labour"],
                "CAPEX [EUR]": central["CAPEX"],
                "Decommissioning [EUR]": central["Decommissioning"],
                "Total discounted cost [EUR]": central["Total discounted cost"],
                "Discounted heat [MWh]": central["Discounted heat"],
                "LCOH [EUR/MWh]": result.lcoh["central"],
            }
        )
    path = _breakdown_file(layout, save_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).round(2).to_csv(path, index=False)
    print(f"✓ Table saved: {path}")


def _lcoh_table(results, layout):
    """LCOH table of a layout (scenario column + one column per case), as
    simulated or read in this run."""
    table = results[layout]["lcoh_table"].copy()
    table = table.rename(columns={table.columns[0]: "scenario"})
    return table


def _parse_lcoh_scenario_spec(spec):
    error = ValueError(
        "comparison['lcoh_scenario'] must be [layouts, price zone, heat demand "
        "schedule], e.g. [['S-BR', 'TES-BR'], 'DK1', 'fixed']."
    )
    if not isinstance(spec, (list, tuple)) or len(spec) != 3:
        raise error
    layouts, zone, schedule = spec
    if not isinstance(zone, str) or not isinstance(schedule, str):
        raise error
    return _as_list(layouts), zone, schedule


def _plot_lcoh_scenario_comparison(spec, results, save_root, file_name):
    """LCOH of the layouts for low / central / high scenarios, for one price
    zone and heat demand schedule."""
    layouts, zone, schedule = _parse_lcoh_scenario_spec(spec)
    plot_lcoh_scenarios_stacked(
        [_lcoh_table(results, layout) for layout in layouts],
        lcoh_kind=_lcoh_column(zone, schedule),
        cycle_labels=list(layouts),
        save_path=save_root / "plots",
        file_name=file_name,
    )


def _parse_delta_lcoh_spec(spec):
    error = ValueError(
        "comparison['delta_lcoh'] must be [pairs, price zones, heat demand "
        "schedules, scenarios], e.g. [[['S-BR', 'TES-BR'], ['S-IR', 'TES-IR']], "
        "['DK1', 'DE'], ['fixed', 'variable'], ['low', 'central', 'high']]."
    )
    if not isinstance(spec, (list, tuple)) or len(spec) != 4:
        raise error
    pairs, zones, schedules, scenarios = spec
    if (
        not isinstance(pairs, (list, tuple))
        or not pairs
        or not all(
            isinstance(pair, (list, tuple))
            and len(pair) == 2
            and all(isinstance(name, str) for name in pair)
            for pair in pairs
        )
    ):
        raise error
    return (
        [list(pair) for pair in pairs],
        _as_list(zones),
        _as_list(schedules),
        [s.lower() for s in _as_list(scenarios)],
    )


def _plot_delta_lcoh_comparison(spec, results, save_root, file_name):
    """LCOH change caused by the TES integration (TES-integrated minus
    standalone), for the price zones, schedules and scenarios requested."""
    pairs, zones, schedules, scenarios = _parse_delta_lcoh_spec(spec)
    columns = [_lcoh_column(z, s) for s in schedules for z in zones]

    def select(layout):
        table = _lcoh_table(results, layout)
        rows = table["scenario"].str.lower().isin(scenarios)
        return table.loc[rows, ["scenario"] + columns].reset_index(drop=True)

    plot_delta_lcoh_analysis(
        [[select(standalone), select(tes)] for standalone, tes in pairs],
        pair_labels=["Intercooled" if "IR" in tes else "Base" for _, tes in pairs],
        save_path=save_root / "plots",
        file_name=file_name,
    )


def _parse_lcoh_breakdown_spec(spec):
    error = ValueError(
        "comparison['lcoh_breakdown'] must be [layouts, price zones, heat demand "
        "schedule, scenario], e.g. [['S-BR', 'TES-BR'], ['DK1', 'DE'], 'fixed', "
        "'central']."
    )
    if not isinstance(spec, (list, tuple)) or len(spec) != 4:
        raise error
    layouts, zones, schedule, scenario = spec
    if not isinstance(schedule, str) or not isinstance(scenario, str):
        raise error
    return _as_list(layouts), _as_list(zones), schedule, scenario.lower()


def _plot_lcoh_breakdown_comparison(spec, results, save_root, file_name):
    """Contributions to the LCOH (central scenario) of the layouts, one panel
    per price zone, from the saved breakdown tables."""
    layouts, zones, schedule, _ = _parse_lcoh_breakdown_spec(spec)
    tables = []
    for layout in layouts:
        path = _breakdown_file(layout, save_root)
        if not path.exists():
            raise FileNotFoundError(
                f"No saved LCOH breakdown for {layout} at '{path}'. Run once "
                "with lcoh_results=False (whole year) to generate it."
            )
        tables.append(pd.read_csv(path))
    breakdown = pd.concat(tables, ignore_index=True)
    demand = SCHEDULE_ALIASES[schedule]
    available = set(zip(breakdown["Forecast"], breakdown["Demand"]))
    missing = [z for z in zones if (z, demand) not in available]
    if missing:
        raise ValueError(
            f"The saved breakdown has no {missing} with the {schedule} schedule. "
            "Run with lcoh_results=False for these price zones and schedules."
        )
    plot_lcoh_breakdown_stacked(
        breakdown,
        panels=[(zone, demand) for zone in zones],
        panel_titles=list(zones),
        cycle_labels=list(layouts),
        save_path=save_root / "plots",
        file_name=file_name,
    )


# Comparison figures that are implemented, and the function building each one.
COMPARISON_BUILDERS = {
    "ts_diagram": _plot_ts_comparison,
    "hx_diagram": _plot_hx_comparison,
    ("exergy_destruction", "exergy_efficiency"): _plot_exergy_comparison,
    "capex_breakdown": _plot_capex_comparison,
    "operational_strategy": _plot_operational_comparison,
    "operational_strategy": _plot_operational_comparison,
    "lcoh_scenario": _plot_lcoh_scenario_comparison,
    "delta_lcoh": _plot_delta_lcoh_comparison,
    "lcoh_breakdown": _plot_lcoh_breakdown_comparison,
}

# Key of the exergy comparison: both plots on one figure.
EXERGY_KEY = ("exergy_destruction", "exergy_efficiency")

# Comparison figures whose value is a flat list of layouts.
FLAT_LIST_FIGURES = ("hx_diagram", EXERGY_KEY, "capex_breakdown")


def _split_comparison_key(key):
    """Split a comparison key into the figure and its label.

    A key is a figure name, optionally followed by "_" and a label that
    distinguishes several figures of the same kind:
    "ts_diagram" -> ("ts_diagram", ""), "ts_diagram_base" -> ("ts_diagram",
    "base"). Returns (None, "") if the key is not a valid figure name.
    """
    if isinstance(key, tuple):
        return (key, "") if key in VALID_COMPARISONS else (None, "")
    for figure in VALID_COMPARISONS:
        if not isinstance(figure, str):
            continue
        if key == figure:
            return figure, ""
        if key.startswith(figure + "_") and len(key) > len(figure) + 1:
            return figure, key[len(figure) + 1 :]
    return None, ""


def _check_comparison(comparison, layouts, price_zones, schedules):
    """Check the `comparison` input before anything is simulated."""
    figures = {key: _split_comparison_key(key)[0] for key in comparison}

    unknown = [key for key, figure in figures.items() if figure is None]
    if unknown:
        raise ValueError(
            f"Unknown comparison key {unknown}. A key is one of "
            f"{[f for f in VALID_COMPARISONS]}, optionally followed by '_' and "
            "a label, e.g. 'ts_diagram_base'."
        )

    pending = [
        key for key, figure in figures.items() if figure not in COMPARISON_BUILDERS
    ]
    if pending:
        warnings.warn(
            f"Comparison figure(s) {pending} not implemented yet: skipped.",
            stacklevel=3,
        )

    for key, spec in comparison.items():
        if figures[key] not in COMPARISON_BUILDERS:
            continue

        if figures[key] == "operational_strategy":
            names, zone, key_schedules, week = _parse_operational_spec(spec)
            _check_values("layout", names, VALID_LAYOUTS)
            _check_values("price zone", [zone], VALID_PRICE_ZONES)
            _check_values(
                "heat demand schedule", key_schedules, VALID_HEAT_DEMAND_SCHEDULES
            )
            if week != OPERATION_WEEK:
                raise ValueError(
                    f"comparison['{key}']: only week {OPERATION_WEEK} is simulated, "
                    f"not week {week}."
                )
            not_run = (
                [n for n in dict.fromkeys(names) if n not in layouts]
                + [z for z in [zone] if z not in price_zones]
                + [x for x in key_schedules if x not in schedules]
            )
            if not_run:
                raise ValueError(
                    f"comparison['{key}'] uses {not_run}, which is not in "
                    "`layouts`, `price_zones` or `heat_demand_schedule`."
                )
            continue

        if figures[key] in ("lcoh_scenario", "delta_lcoh"):
            if figures[key] == "lcoh_scenario":
                names, zone_list, key_schedules = _parse_lcoh_scenario_spec(spec)
                zone_list, key_schedules = [zone_list], [key_schedules]
                scenario_list = []
            else:
                pairs, zone_list, key_schedules, scenario_list = _parse_delta_lcoh_spec(
                    spec
                )
                names = [name for pair in pairs for name in pair]
            _check_values("layout", names, VALID_LAYOUTS)
            _check_values("price zone", zone_list, VALID_PRICE_ZONES)
            _check_values(
                "heat demand schedule", key_schedules, VALID_HEAT_DEMAND_SCHEDULES
            )
            _check_values("scenario", scenario_list, VALID_SCENARIOS)
            not_run = (
                [n for n in dict.fromkeys(names) if n not in layouts]
                + [z for z in zone_list if z not in price_zones]
                + [x for x in key_schedules if x not in schedules]
            )
            if not_run:
                raise ValueError(
                    f"comparison['{key}'] uses {not_run}, which is not in "
                    "`layouts`, `price_zones` or `heat_demand_schedule`."
                )
            continue

        if figures[key] == "lcoh_breakdown":
            names, zone_list, schedule, scenario = _parse_lcoh_breakdown_spec(spec)
            _check_values("layout", names, VALID_LAYOUTS)
            _check_values("price zone", zone_list, VALID_PRICE_ZONES)
            _check_values(
                "heat demand schedule", [schedule], VALID_HEAT_DEMAND_SCHEDULES
            )
            if scenario != "central":
                raise ValueError(
                    f"comparison['{key}']: only the 'central' scenario has a "
                    f"breakdown, not '{scenario}'."
                )
            not_run = (
                [n for n in dict.fromkeys(names) if n not in layouts]
                + [z for z in zone_list if z not in price_zones]
                + [x for x in [schedule] if x not in schedules]
            )
            if not_run:
                raise ValueError(
                    f"comparison['{key}'] uses {not_run}, which is not in "
                    "`layouts`, `price_zones` or `heat_demand_schedule`."
                )
            continue

        names = _comparison_layouts(key, spec)
        _check_values("layout", names, VALID_LAYOUTS)
        not_run = [name for name in dict.fromkeys(names) if name not in layouts]
        if not_run:
            raise ValueError(
                f"comparison['{key}'] uses {not_run}, which is not in `layouts`."
            )
        if figures[key] in FLAT_LIST_FIGURES and not all(
            isinstance(layout, str) for layout in spec
        ):
            raise ValueError(
                f"comparison['{key}'] must be a flat list of layouts, e.g. "
                "['S-BR', 'S-IR']."
            )


def _build_comparison(comparison, results, save_root):
    """Build and save the implemented comparison figures. The file of each
    figure is comparison_<label>_<figure>.png, or comparison_<figure>.png
    if the key has no label."""
    for key, spec in comparison.items():
        figure, label = _split_comparison_key(key)
        builder = COMPARISON_BUILDERS.get(figure)
        if builder is None:
            continue
        print(f"\n--- Comparison: {key} ---")
        builder(
            spec, results, save_root, f"comparison_{label}" if label else "comparison"
        )


def run_techno_economic_assessment(
    layouts: Sequence[str] = VALID_LAYOUTS,
    price_zones: Sequence[str] = VALID_PRICE_ZONES,
    heat_demand_schedule: Sequence[str] = VALID_HEAT_DEMAND_SCHEDULES,
    comparison: Optional[dict] = None,
    save_path: Union[str, Path] = "results/paper",
    week: Optional[int] = None,
    month: Optional[int] = None,
    lcoh_results: bool = False,
):
    """Run the techno-economic assessment and build the comparison figures.

    Implemented so far: for every layout, the design simulation, the
    validation (layouts with reference data), the T-s and heat-exchanger
    diagrams, the performance, sizing, connections and heat-exchanger tables,
    the exergy analysis, the TES tank sizing (TES layouts), the component
    cost, and, for every price zone and heat demand schedule, the operational
    optimisation on 2025 prices and the LCOH analysis (Energinet forecasts for
    all price zones). `comparison` is checked but not used yet.

    Parameters
    ----------
    layouts : sequence of {"S-BR", "S-IR", "TES-BR", "TES-IR"}
        Plant layouts to simulate.
    price_zones : sequence of {"DK1", "DE"}
        Day-ahead price zones (2025 prices) on which each layout is operated.
    heat_demand_schedule : sequence of {"fixed", "variable"}
        "fixed": 1 MWth from 06:00 to 22:00 every day.
        "variable": the same 16 MWh per day, with the hours chosen by the
        optimisation (``heat_demand_profile="free"`` in
        ``optimize_operational_strategy``).
    comparison : dict, optional
        Figures to build across layouts. Each key is one figure and its value
        holds the arguments. Layout names, zones and schedules used here must
        also be listed in `layouts`, `price_zones` and
        `heat_demand_schedule`. A list of lists means one panel (or group)
        per inner list.

        "ts_diagram" : [layouts] or [[layouts], [layouts], ...]
            A flat list gives one T-s diagram with the listed cycles overlaid.
            A list of lists gives one diagram per inner list, side by side,
            each with its own cycles overlaid.
        "hx_diagram" : [layouts]
            One heat-exchanger temperature-profile diagram per layout, side
            by side.
        ("exergy_destruction", "exergy_efficiency") : [layouts]
            One figure with two panels side by side: (a) exergy destruction
            per component as one stacked bar per layout, (b) exergetic
            efficiency per component. Saved as comparison_exergy_combined.png.
        "capex_breakdown" : [layouts]
            Stacked component cost (compressors, turbines, heat exchangers
            and, for TES layouts, tanks and HITEC salt), one bar per layout.
            Saved as comparison_cost_stacked.png.
        "operational_strategy" : [[layouts], zone, [schedules], "week 1"]
            Grid of operation plots (price, heat demand, HTHP power, TES
            energy) for week 1 of 2025: one column per layout, one row per
            heat demand schedule. Only week 1 is simulated. Saved as
            comparison_operational_strategy.png.
        "lcoh_scenario" : [[layouts], zone, schedule]
            LCOH of the layouts for the low / central / high scenarios, for
            one price zone and heat demand schedule. Saved as
            comparison_lcoh_scenarios.png.
        "delta_lcoh" : [[[standalone, tes], ...], [zones], [schedules], [scenarios]]
            LCOH change from the TES integration (TES-integrated minus
            standalone) per pair, price zone, schedule and scenario. Saved
            as comparison_delta_lcoh.png.
        "lcoh_breakdown" : [[layouts], [zones], schedule, "central"]
            Contributions to the LCOH of the central scenario (CAPEX,
            electricity, O&M, labour, decommissioning), one panel per price
            zone, one bar per layout. Read from the breakdown tables saved
            with the LCOH. Saved as comparison_lcoh_breakdown.png.

    save_path : str or Path
        Root folder of the generated figures and tables (default
        "results/paper"). Created if missing.
    week : int, optional
        1-based week of 2025 to optimise instead of the whole year (a block of
        168 hours counted from 1 January). Mutually exclusive with `month`.
    month : int, optional
        Month of 2025 (1-12) to optimise instead of the whole year.
        If neither `week` nor `month` is given, the whole year 2025 is
        optimised. The LCOH needs the whole year, so with a `week` or `month`
        the LCOH analysis is skipped and no LCOH table is saved.
    lcoh_results : bool
        False (default): optimise the operation and calculate the LCOH, and
        save one table per layout, ``<save_path>/tables/lcoh/<layout>_lcoh.csv``,
        with the columns "scenario" and one per price zone and schedule
        ("DK1 fixed", "DE fixed", "DK1 free", "DE free").
        True: skip the optimisation and read the saved tables, to speed up
        the post-processing. The LCOH values are printed in both cases.

    Returns
    -------
    dict
        One entry per layout, with keys "plant" (solved TESPy network),
        "exergy" (exergy analysis results), "tanks" (list of Tank objects, or
        None for standalone layouts), "cost" (component cost table),
        "week_operation" ({(zone, schedule): operational result of week 1}),
        "operation" ({(zone, schedule): operational result}, empty with
        lcoh_results=True), "lcoh" ({(zone, schedule): LCOH result}) and
        "lcoh_table" (the LCOH table as a DataFrame).
    """
    # 1. Validate and normalise the inputs
    layouts = _as_list(layouts)
    price_zones = _as_list(price_zones)
    heat_demand_schedule = _as_list(heat_demand_schedule)
    _check_values("layout", layouts, VALID_LAYOUTS)
    _check_values("price zone", price_zones, VALID_PRICE_ZONES)
    _check_values(
        "heat demand schedule", heat_demand_schedule, VALID_HEAT_DEMAND_SCHEDULES
    )
    layouts = list(dict.fromkeys(layouts))  # drop repeats, keep the order
    if comparison:
        _check_comparison(comparison, layouts, price_zones, heat_demand_schedule)
    if week is not None and month is not None:
        raise ValueError("Give either `week` or `month`, not both.")
    save_root = Path(save_path)

    # 2. Solve and post-process every layout
    results = {}
    for layout in layouts:
        print(f"\n{'=' * 100}\n  LAYOUT {layout}\n{'=' * 100}")
        _validate_layout(layout, save_root)
        results[layout] = _run_layout(layout, save_root)

        # 3. Operation of week 1 of 2025 for every price zone and schedule
        results[layout]["week_operation"] = _simulate_week_operation(
            layout, results[layout], price_zones, heat_demand_schedule
        )

        # 4. LCOH: simulated over the period requested, or read from the saved tables
        if lcoh_results:
            table = _read_lcoh_table(
                layout, price_zones, heat_demand_schedule, save_root
            )
            results[layout]["operation"] = {}
            results[layout]["lcoh_table"] = table
            print(
                f"\n{layout}: LCOH analysis performed for {REFERENCE_YEAR}, "
                "LCOH values are taken from existing simulated results."
            )
            _print_lcoh_table(layout, table)
        else:
            _simulate_operation_and_lcoh(
                layout,
                results[layout],
                price_zones,
                heat_demand_schedule,
                week,
                month,
                save_root,
            )

    # 5. Comparison figures
    if comparison:
        _build_comparison(comparison, results, save_root)

    # TODO (next steps, one at a time):
    #   6. plots of the week-1 operation
    #   7. the other comparison figures
    return results
