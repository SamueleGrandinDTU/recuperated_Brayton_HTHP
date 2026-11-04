"""Example showing the solution and post-processing of the TES-integrated intercooled recuperated HTHP (TES-IR)"""

from src import (
    create_configured_network,
    tes_integr_interc_recup_hthp,
    plot_ts_diagram,
    plot_hx_diagram,
    generate_performance_parameters_table,
    generate_sizing_parameters_table,
    generate_connections_table,
    get_exergy_analysis,
    calculate_component_cost,
    calculate_tanks_geometry,
    optimize_operational_strategy,
    perform_lcoh_analysis,
)

# 1. Loading the HTHP with the design parameters and solving the simulation
plant_tes_integr_interc_recup_hthp = create_configured_network()
plant = tes_integr_interc_recup_hthp()
plant.build_into(plant_tes_integr_interc_recup_hthp)

plant_tes_integr_interc_recup_hthp.solve(mode="design")
plant_tes_integr_interc_recup_hthp.print_results()

# 2. Plot the T-s diagram and the hx diagram (eventually save them as PNG files)
plot_ts_diagram(
    plant_tes_integr_interc_recup_hthp,
    file_name="TES_IR_hthp",
    save_path="results/examples/plots",
)

plot_hx_diagram(
    plant_tes_integr_interc_recup_hthp.comps.loc["interface hx", "object"],
    file_name="TES_IR_hthp",
    save_path="results/examples/plots",
)

# 3. Generate sizing, performance, connections, and hx parameters tables (eventually save them as CSV files)
generate_performance_parameters_table(
    plant_tes_integr_interc_recup_hthp,
    file_name="TES_IR_hthp",
    save_path="results/examples/tables/performance_parameters",
)

generate_sizing_parameters_table(
    plant_tes_integr_interc_recup_hthp,
    file_name="TES_IR_hthp",
    save_path="results/examples/tables/sizing_parameters",
)

generate_connections_table(
    plant_tes_integr_interc_recup_hthp,
    file_name="TES_IR_hthp",
    save_path="results/examples/tables/connections",
)

# 4. Perform exergy analysis (eventually save results as csv files)
exergy_results = get_exergy_analysis(
    plant_tes_integr_interc_recup_hthp,
    file_name="TES_IR_hthp",
    save_path="results/examples/tables/components_exergy",
)

# 5. Calculate the TES tank geometry
tank1, tank2 = calculate_tanks_geometry(
    plant_tes_integr_interc_recup_hthp, ["t1", "t2"], storage_duration=8
)

# 6. Estimate the component costs (eventually save results as csv files)
component_cost = calculate_component_cost(
    plant_tes_integr_interc_recup_hthp,
    [tank1, tank2],
    file_name="TES_IR_hthp",
    save_path="results/examples/tables/components_cost",
)

# 7. Optimize the operational strategy on the DK1 market for 2025 and perform the LCOH analysis (fixed demand profile)
result_dk1 = optimize_operational_strategy(
    plant_tes_integr_interc_recup_hthp,
    E_TES=8.0,
    market="DK1",
    year=2025,
    heat_demand_profile="fixed",
)

perform_lcoh_analysis(
    lifetime=25,
    component_cost=component_cost,
    operational_result=result_dk1,
    market="DK1",
)

# 8. Optimize the operational strategy on the DE market and perform the LCOH analysis (fixed demand profile)
result_de = optimize_operational_strategy(
    plant_tes_integr_interc_recup_hthp,
    E_TES=8.0,
    market="DE",
    year=2025,
    heat_demand_profile="fixed",
)

perform_lcoh_analysis(
    lifetime=25,
    component_cost=component_cost,
    operational_result=result_de,
    market="DK1",
)

# 9. Optimize the operational strategy on the DK1 market for 2025 and perform the LCOH analysis (free demand profile)
result_dk1 = optimize_operational_strategy(
    plant_tes_integr_interc_recup_hthp,
    E_TES=8.0,
    market="DK1",
    year=2025,
    heat_demand_profile="free",
)

perform_lcoh_analysis(
    lifetime=25,
    component_cost=component_cost,
    operational_result=result_dk1,
    market="DK1",
)

# 10. Optimize the operational strategy on the DE market for 2025 and perform the LCOH analysis (free demand profile)
result_de = optimize_operational_strategy(
    plant_tes_integr_interc_recup_hthp,
    E_TES=8.0,
    market="DE",
    year=2025,
    heat_demand_profile="free",
)

perform_lcoh_analysis(
    lifetime=25,
    component_cost=component_cost,
    operational_result=result_de,
    market="DK1",
)
