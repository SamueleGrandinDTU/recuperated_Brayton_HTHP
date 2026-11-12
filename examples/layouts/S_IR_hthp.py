"""Example showing the solution and post-processing of the standalone intercooled recuperated HTHP (S-IR)"""

from src import (
    create_configured_network,
    standalone_interc_recup_hthp,
    plot_ts_diagram,
    plot_hx_diagram,
    generate_performance_parameters_table,
    generate_sizing_parameters_table,
    generate_connections_table,
    save_hx_table,
    get_exergy_analysis,
    calculate_component_cost,
    optimize_operational_strategy,
    perform_lcoh_analysis,
)

# 1. Loading the HTHP with the design parameters and solving the simulation
plant_standalone_interc_recup = create_configured_network()
plant = standalone_interc_recup_hthp()
plant.build_into(plant_standalone_interc_recup)

plant_standalone_interc_recup.solve(mode="design")
plant_standalone_interc_recup.print_results()

# 2. Plot the T-s diagram and the hx diagram (eventually save them as PNG files)
plot_ts_diagram(
    plant_standalone_interc_recup,
    file_name="S_IR_hthp",
    save_path="results/examples/plots",
)

plot_hx_diagram(
    [
        plant_standalone_interc_recup.comps.loc["sink 1", "object"],
        plant_standalone_interc_recup.comps.loc["sink 2", "object"],
    ],
    file_name="S_IR_hthp",
    save_path="results/examples/plots",
)

# 3. Generate sizing, performance, connections, and hx parameters tables (eventually save them as CSV files)
generate_performance_parameters_table(
    plant_standalone_interc_recup,
    file_name="S_IR_hthp",
    save_path="results/examples/tables/performance_parameters",
)

generate_sizing_parameters_table(
    plant_standalone_interc_recup,
    file_name="S_IR_hthp",
    save_path="results/examples/tables/sizing_parameters",
)

generate_connections_table(
    plant_standalone_interc_recup,
    file_name="S_IR_hthp",
    save_path="results/examples/tables/connections",
)


save_hx_table(
    [
        plant_standalone_interc_recup.comps.loc["sink 1", "object"],
        plant_standalone_interc_recup.comps.loc["sink 2", "object"],
    ],
    file_name="S_IR_hthp",
    save_path="results/examples/tables/hx",
)


# 4. Perform exergy analysis (eventually save results as csv files)
exergy_results = get_exergy_analysis(
    plant_standalone_interc_recup,
    file_name="S_IR_hthp",
    save_path="results/examples/tables/components_exergy",
)

# 5. Estimate the component costs (eventually save results as csv files)
component_cost = calculate_component_cost(
    plant_standalone_interc_recup,
    file_name="S_IR_hthp",
    save_path="results/examples/tables/components_cost",
)

# 6. Optimize the operational strategy on the DK1 market for 2025 and perform the LCOH analysis (fixed demand profile)
result_dk1 = optimize_operational_strategy(
    plant_standalone_interc_recup,
    E_TES=0.0,
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

# 7. Optimize the operational strategy on the DE market for 2025 and perform the LCOH analysis (fixed demand profile)
result_de = optimize_operational_strategy(
    plant_standalone_interc_recup,
    E_TES=0.0,
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

# 8. Optimize the operational strategy on the DK1 market for 2025 and perform the LCOH analysis (free demand profile)
result_dk1 = optimize_operational_strategy(
    plant_standalone_interc_recup,
    E_TES=0.0,
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

# 9. Optimize the operational strategy on the DE market for 2025 and perform the LCOH analysis (free demand profile)
result_de = optimize_operational_strategy(
    plant_standalone_interc_recup,
    E_TES=0.0,
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
