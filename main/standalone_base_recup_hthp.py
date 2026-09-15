"""Entry-point script for the standalone, base, recuperated HTHP case.

Creates a TESPy network, builds the plant topology and parameters into
it via ``standalone_base_recup_hthp``, and solves the design-point simulation.

This file will be extended progressively as post-processing and
plotting steps are added.
"""

from src import create_configured_network, standalone_base_recup_hthp

# 1. Create the network and assemble the plant into it
my_plant_standalone_base_recup = create_configured_network()
plant = standalone_base_recup_hthp()
plant.build_into(my_plant_standalone_base_recup)

# 2. Solve the design-point simulation
my_plant_standalone_base_recup.solve(mode="design")
my_plant_standalone_base_recup.print_results()
