"""Entry-point script of the techno-economic assessment of the recuperated
Brayton high-temperature heat pump (HTHP) layouts.

Runs ``run_techno_economic_assessment`` for the four layouts:

    S-BR   : standalone, base recuperated
    S-IR   : standalone, intercooled recuperated
    TES-BR : TES-integrated, base recuperated
    TES-IR : TES-integrated, intercooled recuperated

For every layout it solves the design point, validates it where reference data
exist, and saves the tables (performance, sizing, connections, heat
exchangers, exergy, component cost) in ``results/paper``.

It then simulates the operation of week 1 of 2025 for every price zone (DK1
and DE) and heat demand schedule (fixed and variable), with E_TES = 0 MWh for
the standalone layouts and 8 MWh for the TES-integrated ones. The results are
kept in the dictionary returned by the function.

Then it calculates the LCOH on the same price zones and schedules (2025
prices, Energinet forecasts), with ``lcoh_results`` selecting how:

    lcoh_results=False : optimise the operation over the whole year 2025 for
                         every case (slow), calculate the LCOH, and save
                         results/paper/tables/lcoh/<layout>_lcoh.csv.
    lcoh_results=True  : skip the optimisation and read the saved LCOH tables
                         (fast), for the post-processing.

The week-1 operation is simulated in both cases. The LCOH tables are printed in
the command view in both cases. To test quickly, add ``week=1`` or ``month=1``
to optimise only that period instead of the whole year in the LCOH step (the
LCOH is then skipped).

Finally it builds the comparison figures requested in ``comparison`` from the
saved tables, in ``results/paper/plots``.

Run it from the repository root, with the virtual environment active:

    python -m main.Brayton_hthp_techno_economic_assessment
"""

from src import run_techno_economic_assessment

run_techno_economic_assessment(
    layouts=["S-BR", "S-IR", "TES-BR", "TES-IR"],
    price_zones=["DK1", "DE"],
    heat_demand_schedule=["fixed", "variable"],
    comparison={
        "ts_diagram_base": ["S-BR", "S-IR"],
        "ts_diagram": [["S-BR", "TES-BR"], ["S-IR", "TES-IR"]],
        "hx_diagram": ["S-BR", "S-IR"],
        ("exergy_destruction", "exergy_efficiency"): [
            "S-BR",
            "S-IR",
            "TES-BR",
            "TES-IR",
        ],
        "capex_breakdown": ["S-BR", "S-IR", "TES-BR", "TES-IR"],
        "operational_strategy": [
            ["S-BR", "TES-BR"],
            "DK1",
            ["fixed", "variable"],
            "week 1",
        ],
        "lcoh_scenario": [["S-BR", "S-IR", "TES-BR", "TES-IR"], "DK1", "fixed"],
        "delta_lcoh": [
            [["S-BR", "TES-BR"], ["S-IR", "TES-IR"]],
            ["DK1", "DE"],
            ["fixed", "variable"],
            ["low", "central", "high"],
        ],
        "lcoh_breakdown": [
            ["S-BR", "TES-BR", "S-IR", "TES-IR"],
            ["DK1", "DE"],
            "fixed",
            "central",
        ],
    },
    save_path="results/paper",
    lcoh_results=True,
)
