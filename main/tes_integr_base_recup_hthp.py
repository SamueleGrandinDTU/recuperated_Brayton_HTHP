"""Entry-point script for the TES-Integrated, base, recuperated HTHP case.

Creates a TESPy network, builds the plant topology and parameters into
it via `tes_integr_base_recup_hthp`.

Solves the design-point simulation with case study selected parameters.

Post-processing include generation of TS diagram and hx diagram,
as well as resuming tables for performance and sizing parameters.

This file will be extended progressively as post-processing and
plotting steps are added.
"""

from src import (
    create_configured_network,
    tes_integr_base_recup_hthp,
    plot_ts_diagram,
    plot_hx_diagram,
    generate_performance_parameters_table,
    generate_sizing_parameters_table,
    get_exergy_analysis,
    calculate_component_cost,
    calculate_tanks_geometry,
)

# 1. Solve the simulation in the design condition
plant_tes_integr_base_recup_hthp = create_configured_network()
plant = tes_integr_base_recup_hthp()
plant.build_into(plant_tes_integr_base_recup_hthp)

plant_tes_integr_base_recup_hthp.solve(mode="design")
plant_tes_integr_base_recup_hthp.print_results()

# 2. Plot the T-s diagram and the hx diagram
plot_ts_diagram(
    plant_tes_integr_base_recup_hthp,
    file_name="tes_integr_base_recup_hthp",
    save_path="results/plots",
)

plot_hx_diagram(
    plant_tes_integr_base_recup_hthp.comps.loc["interface hx", "object"],
    file_name="tes_integr_base_recup_hthp",
    save_path="results/plots",
)

# 3. Generate tables for performance and sizing parameters
generate_performance_parameters_table(
    plant_tes_integr_base_recup_hthp,
    file_name="tes_integr_base_recup_hthp",
    save_path="results/tables",
)

generate_sizing_parameters_table(
    plant_tes_integr_base_recup_hthp,
    file_name="tes_integr_base_recup_hthp",
    save_path="results/tables",
)

# 4. Perform exergy analysis, generate the exergy analysis table
exergy_results = get_exergy_analysis(plant_tes_integr_base_recup_hthp)

# 5. Calculate the TES tank geometry
tank1, tank2 = calculate_tanks_geometry(
    plant_tes_integr_base_recup_hthp, ["t1", "t2"], storage_duration=8
)

# 6. Estimate the component costs
calculate_component_cost(plant_tes_integr_base_recup_hthp, [tank1, tank2])
