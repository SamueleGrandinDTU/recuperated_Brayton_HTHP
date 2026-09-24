"""Entry-point script for the standalone, intercooled, recuperated HTHP case.

Creates a TESPy network, builds the plant topology and parameters into
it via `standalone_interc_recup_hthp`, and validates it against reference data.

Solves the design-point simulation with case study selected parameters.

Post-processing include generation of TS diagram and hx diagram,
as well as resuming tables for performance and sizing parameters.

This file will be extended progressively as post-processing and
plotting steps are added.
"""

from src import (
    create_configured_network,
    standalone_interc_recup_hthp,
    plot_ts_diagram,
    plot_hx_diagram,
    generate_performance_parameters_table,
    generate_sizing_parameters_table,
    get_exergy_analysis,
    plot_exergy_destruction_stacked,
    calculate_component_cost,
)

# 1. Set and solve the simulation
plant_standalone_interc_recup = create_configured_network()
plant = standalone_interc_recup_hthp()
plant.build_into(plant_standalone_interc_recup)

plant_standalone_interc_recup.solve(mode="design")
plant_standalone_interc_recup.print_results()

# 3. Plot the T-s diagram and the hx diagram
plot_ts_diagram(
    plant_standalone_interc_recup,
    file_name="standalone_interc_recup_hthp",
    save_path="results/plots",
)

plot_hx_diagram(
    [
        plant_standalone_interc_recup.comps.loc["sink 1", "object"],
        plant_standalone_interc_recup.comps.loc["sink 2", "object"],
    ],
    file_name="standalone_interc_recup_hthp",
    save_path="results/plots",
)

# 4. Generate tables for performance and sizing parameters
generate_performance_parameters_table(
    plant_standalone_interc_recup,
    file_name="standalone_interc_recup_hthp",
    save_path="results/tables",
)

generate_sizing_parameters_table(
    plant_standalone_interc_recup,
    file_name="standalone_interc_recup_hthp",
    save_path="results/tables",
)

# 5. Perform exergy analysis, generate the exergy analysis table, and plot the exergy destruction stacked bar chart
exergy_results = get_exergy_analysis(plant_standalone_interc_recup)
plot_exergy_destruction_stacked(
    exergy_results["components"],
    save_path="results/plots",
    file_name="standalone_interc_recup_hthp",
)

# 6. Estimate the component costs
calculate_component_cost(plant_standalone_interc_recup)
