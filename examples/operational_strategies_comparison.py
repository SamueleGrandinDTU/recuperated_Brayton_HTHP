"""Example showing the operation of the S-BR and TES-BR HTHPs
with fixed and free heat demand profiles"""

from src import (
    create_configured_network,
    standalone_base_recup_hthp,
    tes_integr_base_recup_hthp,
    optimize_operational_strategy,
    plot_operational_strategy,
)

# 1. Load the S-BR and TES-BR HTHPs with the design parameters and solve the simulations
plant_standalone_base_recup = create_configured_network()
plant = standalone_base_recup_hthp()
plant.build_into(plant_standalone_base_recup)

plant_standalone_base_recup.solve(mode="design")
plant_standalone_base_recup.print_results()

plant_tes_integr_base_recup = create_configured_network()
plant = tes_integr_base_recup_hthp()
plant.build_into(plant_tes_integr_base_recup)

plant_tes_integr_base_recup.solve(mode="design")
plant_tes_integr_base_recup.print_results()

# 2. Optimize the operational strategy of S-BR and TES-BR on the DK1 market for week 1 (fixed demand profile)
result_S_BR_fixed = optimize_operational_strategy(
    plant_standalone_base_recup,
    E_TES=0.0,
    market="DK1",
    week=1,
    heat_demand_profile="fixed",
)

result_TES_BR_fixed = optimize_operational_strategy(
    plant_tes_integr_base_recup,
    E_TES=8.0,
    market="DK1",
    week=1,
    heat_demand_profile="fixed",
)

# 3. Optimize the operational strategy of S-BR and TES-BR on the DK1 market for week 1 (free demand profile)
result_S_BR_variable = optimize_operational_strategy(
    plant_standalone_base_recup,
    E_TES=0.0,
    market="DK1",
    week=1,
    heat_demand_profile="variable",
)

result_TES_BR_variable = optimize_operational_strategy(
    plant_tes_integr_base_recup,
    E_TES=8.0,
    market="DK1",
    week=1,
    heat_demand_profile="variable",
)

# 4. Plot the operational strategies in a 2x2 grid (rows: fixed and free demand, columns: S-BR and TES-BR), eventually save the figure as PNG file
plot_operational_strategy(
    [
        [result_S_BR_fixed, result_TES_BR_fixed],
        [result_S_BR_variable, result_TES_BR_variable],
    ],
    save_path=None,
)
