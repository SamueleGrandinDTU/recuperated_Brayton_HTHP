"""
src/techno_economic_analysis.py

Single entry point of the techno-economic assessment of the four HTHP layouts.

``run_techno_economic_assessment`` runs, for every requested layout, the chain

    plant model -> design simulation -> tables and diagrams -> exergy analysis
    -> tank sizing (TES layouts) -> component cost

and, in the next development steps, the operational optimisation, the LCOH
analysis and the comparison figures.

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
                                             components_cost
    <save_path>/validation/                  validation against the reference

and the file names ``<S_BR | S_IR | TES_BR | TES_IR>_hthp_...``.

STATUS: the per-layout solution and post-processing are implemented. The
operational optimisation, the LCOH analysis and the `comparison` figures are
still to be added.
"""

import warnings
from pathlib import Path
from typing import Optional, Sequence, Union

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
    plot_ts_diagram(plant, file_name=file_name, save_path=plots)
    plot_hx_diagram(hx_components, file_name=file_name, save_path=plots)

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


def run_techno_economic_assessment(
    layouts: Sequence[str] = VALID_LAYOUTS,
    price_zones: Sequence[str] = VALID_PRICE_ZONES,
    heat_demand_schedule: Sequence[str] = VALID_HEAT_DEMAND_SCHEDULES,
    comparison: Optional[dict] = None,
    save_path: Union[str, Path] = "results/paper",
):
    """Run the techno-economic assessment and build the comparison figures.

    Implemented so far: for every layout, the design simulation, the
    validation (layouts with reference data), the T-s and heat-exchanger
    diagrams, the performance, sizing, connections and heat-exchanger tables,
    the exergy analysis, the TES tank sizing (TES layouts) and the component
    cost. `price_zones`, `heat_demand_schedule` and `comparison` are checked
    but not used yet.

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

        "ts_diagram" : [layouts]
            One T-s diagram with the listed cycles overlaid.
        "hx_diagram" : [[layouts], [layouts], ...]
            One heat-exchanger temperature-profile panel per inner list.
        ("exergy_destruction", "exergy_efficiency") : [layouts]
            Stacked exergy destruction and exergetic efficiency per
            component, on one figure.
        "capex_breakdown" : [layouts]
            Stacked component cost, one bar per layout.
        "operational_strategy" : [[layouts], zone, [schedules], "week n"]
            Grid of operation plots for week n of 2025: one column per
            layout, one row per schedule.
        "lcoh_scenario" : [[layouts], zone, schedule]
            LCOH per scenario (low, central, high), one bar per layout.
        "delta_lcoh" : [[[standalone, tes], ...], [zones], [schedules],
                        [scenarios]]
            LCOH(TES-integrated) - LCOH(standalone) for each layout pair.
        "lcoh_breakdown" : [[layouts], [zones], schedule, scenario]
            Stacked LCOH contributions (CAPEX, electricity, O&M, labour,
            decommissioning). Only the "central" scenario is available.

        Not implemented yet: a non-empty `comparison` is ignored with a
        warning.
    save_path : str or Path
        Root folder of the generated figures and tables (default
        "results/paper"). Created if missing.

    Returns
    -------
    dict
        One entry per layout, with keys "plant" (solved TESPy network),
        "exergy" (exergy analysis results), "tanks" (list of Tank objects, or
        None for standalone layouts) and "cost" (component cost table).
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
        _check_values("comparison key", list(comparison), VALID_COMPARISONS)
        warnings.warn(
            "`comparison` is not implemented yet: no comparison figure is built.",
            stacklevel=2,
        )
    save_root = Path(save_path)

    # 2. Solve and post-process every layout
    results = {}
    for layout in layouts:
        print(f"\n{'=' * 100}\n  LAYOUT {layout}\n{'=' * 100}")
        _validate_layout(layout, save_root)
        results[layout] = _run_layout(layout, save_root)

    # TODO (next steps, one at a time):
    #   3. for every layout, zone and schedule: operational optimisation and
    #      LCOH, saved as the tables read by the comparison plots
    #   4. for every key of `comparison`: build and save the figure
    return results
