"""
This file contains 4 different plants showing how standalone and TES Integrated layouts operate with fixed and free heat demand profiles.
"""

from src import (
    create_configured_network,
    standalone_base_recup_hthp,
    tes_integr_base_recup_hthp,
    optimize_operational_strategy,
    plot_operational_strategy,
)

# 1. Solve both standalone and tes- integrated base recuperated cases
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

# 2. Optimize the operational strategy on the DK1 market and plot the results for both standalone and TES-integrated cases (heat demand fixed)
result_standalone_fixed = optimize_operational_strategy(
    plant_standalone_base_recup,
    E_TES=0.0,
    market="DK1",
    week=1,
    heat_demand_profile="fixed",
)

result_tes_integr_fixed = optimize_operational_strategy(
    plant_tes_integr_base_recup,
    E_TES=8.0,
    market="DK1",
    week=1,
    heat_demand_profile="fixed",
)

# 3. Optimize the operational strategy on the DK1 market and plot the results for both standalone and TES-integrated cases (heat demand free)
result_standalone_free = optimize_operational_strategy(
    plant_standalone_base_recup,
    E_TES=0.0,
    market="DK1",
    week=1,
    heat_demand_profile="free",
)

result_tes_integr_free = optimize_operational_strategy(
    plant_tes_integr_base_recup,
    E_TES=8.0,
    market="DK1",
    week=1,
    heat_demand_profile="free",
)

# 4. Plot all the results in a 2x2 grid of subplots
plot_operational_strategy(
    [
        [result_standalone_fixed, result_tes_integr_fixed],
        [result_standalone_free, result_tes_integr_free],
    ],
    file_name="base_hthp_dk1_week1",
    save_path="results/temporary",
)
