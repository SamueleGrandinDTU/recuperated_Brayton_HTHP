"""LCOH of the four HTHP cycles for three market / forecast combinations.

Every cycle is simulated for the fixed and the free heat demand on both
markets (2025 prices), and the LCOH is then calculated with:

    DK1 Energinet : DK1 operation, Energinet forecast
    DE VBW        : DE operation,  vbw forecast
    DE Energinet  : DE operation,  Energinet forecast (the forecast is not the
                    one of the price zone analyzed: perform_lcoh_analysis warns)

Saved, in RESULTS_DIR:
    <cycle>_lcoh_<dk1_energinet | de_vbw | de_energinet>.csv
        rows Low / Central / High, columns "<market> fixed", "<market> free"
    lcoh_central_breakdown.csv
        discounted cost components of the central scenario of every case
"""

import contextlib
import io
from pathlib import Path

import pandas as pd

from src import (
    create_configured_network,
    standalone_base_recup_hthp,
    standalone_interc_recup_hthp,
    tes_integr_base_recup_hthp,
    tes_integr_interc_recup_hthp,
    calculate_component_cost,
    calculate_tanks_geometry,
    optimize_operational_strategy,
    perform_lcoh_analysis,
)

RESULTS_DIR = Path("results/tables/lcoh_forecasts")
LIFETIME = 25

CASES = [
    {
        "label": "Standalone Base Recuperated",
        "file_name": "standalone_base_recup_hthp",
        "build": standalone_base_recup_hthp,
        "E_TES": 0.0,
        "tes": False,
    },
    {
        "label": "Standalone Intercooled Recuperated",
        "file_name": "standalone_interc_recup_hthp",
        "build": standalone_interc_recup_hthp,
        "E_TES": 0.0,
        "tes": False,
    },
    {
        "label": "TES-Integrated Base Recuperated",
        "file_name": "tes_integr_base_recup_hthp",
        "build": tes_integr_base_recup_hthp,
        "E_TES": 8.0,
        "tes": True,
    },
    {
        "label": "TES-Integrated Intercooled Recuperated",
        "file_name": "tes_integr_interc_recup_hthp",
        "build": tes_integr_interc_recup_hthp,
        "E_TES": 8.0,
        "tes": True,
    },
]

MARKETS = ["DK1", "DE"]
DEMANDS = ["fixed", "free"]
SCENARIOS = ["low", "central", "high"]

# market: market operated (2025 cost); forecast_market: market whose forecast
# scales that cost (DK1 -> Energinet, DE -> vbw)
FORECAST_SETS = [
    {
        "name": "DK1 Energinet",
        "key": "dk1_energinet",
        "market": "DK1",
        "forecast_market": "DK1",
    },
    {"name": "DE VBW", "key": "de_vbw", "market": "DE", "forecast_market": "DE"},
    {
        "name": "DE Energinet",
        "key": "de_energinet",
        "market": "DE",
        "forecast_market": "DK1",
    },
]

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
breakdown_rows = []

for case in CASES:
    print(f"\n{'=' * 78}\n{case['label']}\n{'=' * 78}")

    # 1. Solve the design point
    network = create_configured_network()
    plant = case["build"]()
    plant.build_into(network)
    network.solve(mode="design")

    # 2. Component costs (TES cycles: with the two tanks)
    tanks = None
    if case["tes"]:
        tanks = list(
            calculate_tanks_geometry(network, ["t1", "t2"], storage_duration=8)
        )
    component_cost = calculate_component_cost(network, tanks)

    # 3. Operational strategy: both markets, fixed and free heat demand
    operation = {
        (market, demand): optimize_operational_strategy(
            network,
            E_TES=case["E_TES"],
            market=market,
            year=2025,
            heat_demand_profile=demand,
        )
        for market in MARKETS
        for demand in DEMANDS
    }

    # 4. LCOH for each market / forecast combination
    for fs in FORECAST_SETS:
        table = {}

        for demand in DEMANDS:
            # perform_lcoh_analysis prints long tables: keep the terminal readable
            with contextlib.redirect_stdout(io.StringIO()):
                result = perform_lcoh_analysis(
                    lifetime=LIFETIME,
                    component_cost=component_cost,
                    operational_result=operation[(fs["market"], demand)],
                    market=fs["forecast_market"],
                )

            table[f"{fs['market']} {demand}"] = [result.lcoh[s] for s in SCENARIOS]

            central = result.breakdown["central"]
            breakdown_rows.append(
                {
                    "Cycle": case["label"],
                    "Forecast": fs["name"],
                    "Demand": demand,
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

        df = pd.DataFrame(table, index=[s.capitalize() for s in SCENARIOS]).round(2)
        df.index.name = "scenario"

        out = RESULTS_DIR / f"{case['file_name']}_lcoh_{fs['key']}.csv"
        df.to_csv(out)
        print(f"\n{fs['name']} -> {out}")
        print(df.to_string())

# 5. Cost breakdown of every central case
breakdown = pd.DataFrame(breakdown_rows).round(2)
out = RESULTS_DIR / "lcoh_central_breakdown.csv"
breakdown.to_csv(out, index=False)
print(f"\n✓ Central-scenario breakdown saved: {out}")
