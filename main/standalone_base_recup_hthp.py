"""Entry-point script for the standalone, base, recuperated HTHP case.

Creates a TESPy network, builds the plant topology and parameters into
it via `standalone_base_recup_hthp`, and validates it against reference data.

Solves the design-point simulation with case study selected parameters.

Post-processing include generation of TS diagram and hx diagram,
as well as resuming tables for performance and sizing parameters.

This file will be extended progressively as post-processing and
plotting steps are added.
"""

from src import (
    create_configured_network,
    standalone_base_recup_hthp,
    standalone_base_recup_hthp_Benvenuti,
    plot_ts_diagram,
    plot_hx_diagram,
    generate_performance_parameters_table,
    generate_sizing_parameters_table,
    get_exergy_analysis,
    plot_exergy_destruction_stacked,
    validate_plant,
    calculate_component_cost,
    plot_component_cost_stacked,
)

# 1. Create the validation network and assemble the plant into it
plant_standalone_base_recup_Benvenuti = create_configured_network()
plant = standalone_base_recup_hthp_Benvenuti()
plant.build_into(plant_standalone_base_recup_Benvenuti)

# 2. Solve the validation plant and compare the results with the refernce data
plant_standalone_base_recup_Benvenuti.solve(mode="design")
plant_standalone_base_recup_Benvenuti.print_results()

reference_plant_csv = "data/processed/Benvenuti_validation_recuperated.csv"

validate_plant(
    plant_standalone_base_recup_Benvenuti,
    reference_plant_csv,
    title_name="Benvenuti Validation",
    file_name="standalone_base_recup_hthp_Benvenuti",
    save_path="results/validation",
)

# 3. Change the parameters back to the design condition and solve the simulation
plant_standalone_base_recup = create_configured_network()
plant = standalone_base_recup_hthp()
plant.build_into(plant_standalone_base_recup)

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
    file_name="standalone_base_recup_hthp",
    save_path="results/tables",
)

generate_sizing_parameters_table(
    plant_standalone_base_recup,
    file_name="standalone_base_recup_hthp",
    save_path="results/tables",
)

# 5. Perform exergy analysis, generate the exergy analysis table
exergy_results = get_exergy_analysis(plant_standalone_base_recup)

# 6. Estimate the component costs and plot the component cost stacked bar chart
component_cost = calculate_component_cost(plant_standalone_base_recup)
plot_component_cost_stacked(
    component_cost,
    save_path="results/plots",
    file_name="standalone_base_recup_hthp",
)
