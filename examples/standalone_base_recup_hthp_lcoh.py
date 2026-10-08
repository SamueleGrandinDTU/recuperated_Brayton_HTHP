"""
Example for the simulation of the standalone base recuperated case working with a fixed heat demand profile on the DK1 market for its whole lifetime.
The simulation is performed without TES, and the operational strategy is optimized for the given heat demand profile.
"""

from src import (
    create_configured_network,
    standalone_base_recup_hthp,
    calculate_component_cost,
    optimize_operational_strategy,
    calculate_future_costs,
    perform_lcoh_analysis,
)

# 1. Solve the standalone base recuperated case
plant_standalone_base_recup = create_configured_network()
plant = standalone_base_recup_hthp()
plant.build_into(plant_standalone_base_recup)

plant_standalone_base_recup.solve(mode="design")
plant_standalone_base_recup.print_results()

# 2. Estimate the component costs
component_cost = calculate_component_cost(
    plant_standalone_base_recup,
    file_name="standalone_base_recup_hthp",
    save_path="results/tables/components_cost",
)

# 3. Optimize the operational strategy and plot the results (no TES)
result = optimize_operational_strategy(
    plant_standalone_base_recup,
    E_TES=0.0,
    market="DK1",
    year=2025,
)

# 4. Perform the LCOH analysis
calculate_future_costs(result, source="Energinet")

perform_lcoh_analysis(
    lifetime=25,
    component_cost=component_cost,
    operational_result=result,
)
