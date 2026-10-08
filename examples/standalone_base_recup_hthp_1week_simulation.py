"""
Example for the simulation of the standalone base recuperated case working with a fixed heat demand profile on the DK1 market for one week.
The simulation is performed without TES, and the operational strategy is optimized for the given heat demand profile.
"""

from src import (
    create_configured_network,
    standalone_base_recup_hthp,
    optimize_operational_strategy,
    plot_operational_strategy,
)

# 1. Solve the standalone base recuperated case
plant_standalone_base_recup = create_configured_network()
plant = standalone_base_recup_hthp()
plant.build_into(plant_standalone_base_recup)

plant_standalone_base_recup.solve(mode="design")
plant_standalone_base_recup.print_results()

# 2. Optimize the operational strategy and plot the results (no TES)
result = optimize_operational_strategy(
    plant_standalone_base_recup,
    E_TES=0.0,
    market="DK1",
    week=1,
)

plot_operational_strategy(
    result,
    file_name="standalone_base_recup_hthp_1week_simulation",
    save_path="results/temporary",
)
