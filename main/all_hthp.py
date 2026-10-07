"""Cross-cycle post-processing for the four HTHP configurations.

Reads the per-cycle result tables already saved to disk by each plant's own
script (get_exergy_analysis / calculate_component_cost with save_path set)
and builds the comparison plots across all four cycles. This file never
touches TESPy/CoolProp — it only reads the CSVs each plant script already
produced, so it can be re-run instantly whenever a plot needs restyling
without re-solving any plant.
"""

from pathlib import Path

from src import (
    plot_exergy_destruction_stacked,
    plot_component_cost_stacked,
    plot_exergetic_efficiencies,
)

# One entry per cycle: "file_name" matches the file_name each plant script
# used when calling get_exergy_analysis / calculate_component_cost, and
# "label" is the display name used on the comparison plots' x-axis. Edit
# "label" freely; "file_name" must match what's on disk.
CYCLES = [
    {"file_name": "standalone_base_recup_hthp", "label": "Standalone Base Recuperated"},
    {
        "file_name": "standalone_interc_recup_hthp",
        "label": "Standalone Intercooled Recuperated",
    },
    {
        "file_name": "tes_integr_base_recup_hthp",
        "label": "TES-Integrated Base Recuperated",
    },
    {
        "file_name": "tes_integr_interc_recup_hthp",
        "label": "TES-Integrated Intercooled Recuperated",
    },
]

RESULTS_DIR = Path("results/tables")
FIGURES_DIR = Path("results/plots")

exergy_csv_paths = [
    RESULTS_DIR / "components_exergy" / f"{cycle['file_name']}_exergy_components.csv"
    for cycle in CYCLES
]
cost_csv_paths = [
    RESULTS_DIR / "components_cost" / f"{cycle['file_name']}_components_cost.csv"
    for cycle in CYCLES
]
cycle_labels = [cycle["label"] for cycle in CYCLES]

# 1. Exergy destruction, all four cycles side by side
plot_exergy_destruction_stacked(
    exergy_csv_paths,
    cycle_labels=cycle_labels,
    save_path=FIGURES_DIR,
    file_name="all_hthp",
)

# 2. Component cost, all four cycles side by side
plot_component_cost_stacked(
    cost_csv_paths,
    cycle_labels=cycle_labels,
    save_path=FIGURES_DIR,
    file_name="all_hthp",
)

# 3. Exergetic efficiencies plot for all four cycles
plot_exergetic_efficiencies(
    exergy_csv_paths,
    cycle_labels=cycle_labels,
    save_path=FIGURES_DIR,
    file_name="all_hthp",
)
