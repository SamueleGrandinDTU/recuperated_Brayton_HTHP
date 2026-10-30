"""ΔLCOH figure (TES-integrated - standalone) from the saved LCOH tables.

Reads the tables written by run_lcoh_forecasts.py and combines, for each
cycle, the DK1 columns (DK1 operation, Energinet forecast) with the DE
columns (DE operation, forecast chosen in DE_FORECAST) into one table with
the columns "scenario, DK1 fixed, DE fixed, DK1 free, DE free", which is what
plot_delta_lcoh_analysis expects.
"""

from pathlib import Path

import pandas as pd

from src import plot_delta_lcoh_analysis, plot_lcoh_breakdown_stacked

RESULTS_DIR = Path("results/tables/lcoh_forecasts")
FIGURES_DIR = Path("results/temporary")

# Forecast of the DE columns: "energinet" (DE cost scaled with the Energinet
# forecast) or "vbw" (the DE forecast). The DK1 columns always use Energinet.
DE_FORECAST = "energinet"

# Same order as in compare_cycles.py: 0/1 = standalone base/intercooled,
# 2/3 = TES-integrated base/intercooled.
CYCLE_FILE_NAMES = [
    "standalone_base_recup_hthp",
    "standalone_interc_recup_hthp",
    "tes_integr_base_recup_hthp",
    "tes_integr_interc_recup_hthp",
]


def load_lcoh_table(file_name):
    """DK1 and DE tables of one cycle merged into one LCOH table."""
    dk1 = pd.read_csv(RESULTS_DIR / f"{file_name}_lcoh_dk1_energinet.csv")
    de = pd.read_csv(RESULTS_DIR / f"{file_name}_lcoh_de_{DE_FORECAST}.csv")

    if list(dk1["scenario"]) != list(de["scenario"]):
        raise ValueError(
            f"{file_name}: the DK1 and DE tables have different scenarios."
        )

    return pd.DataFrame(
        {
            "scenario": dk1["scenario"],
            "DK1 fixed": dk1["DK1 fixed"],
            "DE fixed": de["DE fixed"],
            "DK1 free": dk1["DK1 free"],
            "DE free": de["DE free"],
        }
    )


tables = [load_lcoh_table(name) for name in CYCLE_FILE_NAMES]

plot_delta_lcoh_analysis(
    [
        [tables[0], tables[2]],  # base: standalone, TES-integrated
        [tables[1], tables[3]],  # intercooled: standalone, TES-integrated
    ],
    pair_labels=["Base", "Intercooled"],
    save_path=FIGURES_DIR,
    file_name=f"all_hthp_energinet_{DE_FORECAST}",
)

plot_lcoh_breakdown_stacked(
    RESULTS_DIR / "lcoh_central_breakdown.csv",
    save_path=FIGURES_DIR,
    file_name="all_hthp_de_energinet",
)
