from src import create_configured_network, standalone_base_recup_hthp
from src import validate_plant

# 1. Create the network and assemble the plant into it
plant_standalone_base_recup = create_configured_network()
plant = standalone_base_recup_hthp()
plant.build_into(plant_standalone_base_recup)

# 2. Change the parameters to match the validation case assumptions
ct1 = plant_standalone_base_recup.conns.loc["t1", "object"]
ct1.set_attr(T=193)

# 3. Solve the design-point simulation
plant_standalone_base_recup.solve(mode="design")
plant_standalone_base_recup.print_results()

reference_plant_csv = "data/processed/Benvenuti_validation_recuperated.csv"

validate_plant(
    plant_standalone_base_recup,
    reference_plant_csv,
    title_name="Benvenuti Validation",
    file_name="standalone_base_recup_hthp_Benvenuti",
    save_path="results/validation",
)
