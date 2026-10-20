"""
Example for the simulation of the standalone base recuperated case working with a free heat demand profile on the DK1 and DE market for one week.
The simulation is performed without TES, and the operational strategy is optimized for the given heat demand profile.
"""

from src import (
    create_configured_network,
    standalone_base_recup_hthp,
    tes_integr_base_recup_hthp,
    optimize_operational_strategy,
    plot_operational_strategy,
)

# 1. Solve the standalone base recuperated case
plant_standalone_base_recup = create_configured_network()
plant = standalone_base_recup_hthp()
plant.build_into(plant_standalone_base_recup)

plant_standalone_base_recup.solve(mode="design")
plant_standalone_base_recup.print_results()

# 2. Optimize the operational strategy on the DK1 market and plot the results (no TES)
result = optimize_operational_strategy(
    plant_standalone_base_recup,
    E_TES=0.0,
    market="DK1",
    week=1,
    heat_demand_profile="free",
)

plot_operational_strategy(
    result,
    file_name="standalone_base_recup_hthp_free_demand_simulation",
    save_path="results/temporary",
)

# 3. Solve the TES-Integrated base recuperated case
plant_tes_integr_base_recup = create_configured_network()
plant = tes_integr_base_recup_hthp()
plant.build_into(plant_tes_integr_base_recup)

plant_tes_integr_base_recup.solve(mode="design")
plant_tes_integr_base_recup.print_results()

# 4. Optimize the operational strategy on the DK1 market and plot the results
result = optimize_operational_strategy(
    plant_tes_integr_base_recup,
    E_TES=8.0,
    market="DK1",
    week=1,
    heat_demand_profile="free",
)

plot_operational_strategy(
    result,
    file_name="tes_base_recup_hthp_free_demand_simulation",
    save_path="results/temporary",
)
