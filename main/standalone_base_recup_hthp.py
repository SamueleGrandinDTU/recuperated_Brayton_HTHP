"""Entry-point script for the standalone, base, recuperated HTHP case.

Creates a TESPy network, builds the plant topology and parameters into
it via `standalone_base_recup_hthp`, and solves the design-point simulation.

Post-processing and plotting phases include generation of TS diagram and hx diagram,
as well as resuming tables for performance and sizing parameters.

This file will be extended progressively as post-processing and
plotting steps are added.
"""

from src import (
    create_configured_network,
    standalone_base_recup_hthp,
    plot_ts_diagram,
    plot_hx_diagram,
    generate_performance_parameters_table,
    generate_sizing_parameters_table,
    get_exergy_analysis,
    plot_exergy_destruction_stacked,
)

# 1. Create the network and assemble the plant into it
plant_standalone_base_recup = create_configured_network()
plant = standalone_base_recup_hthp()
plant.build_into(plant_standalone_base_recup)

# 2. Solve the design-point simulation
plant_standalone_base_recup.solve(mode="design")
plant_standalone_base_recup.print_results()

# 3. Plot the T-s diagram and the hx diagram
plot_ts_diagram(
    plant_standalone_base_recup,
    file_name="standalone_base_recup_hthp",
    save_path="results/plots",
)

plot_hx_diagram(
    plant_standalone_base_recup.comps.loc["sink", "object"],
    file_name="standalone_base_recup_hthp",
    save_path="results/plots",
)

# 4. Generate tables for performance and sizing parameters
generate_performance_parameters_table(
    plant_standalone_base_recup,
    title_name="Standalone Base Recuperated HTHP",
    file_name="standalone_base_recup_hthp",
    save_path="results/tables",
)

generate_sizing_parameters_table(
    plant_standalone_base_recup,
    title_name="Standalone Base Recuperated HTHP",
    file_name="standalone_base_recup_hthp",
    save_path="results/tables",
)

# 5. Perform exergy analysis, generate the exergy analysis table, and plot the exergy destruction stacked bar chart
exergy_results = get_exergy_analysis(plant_standalone_base_recup)
plot_exergy_destruction_stacked(
    exergy_results["components"],
    save_path="results/plots",
    file_name="standalone_base_recup_hthp",
)
