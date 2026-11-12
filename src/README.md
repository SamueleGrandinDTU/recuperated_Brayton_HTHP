# src/

## Source code

Contains all **source code** (scripts) of the project, reflecting models, solvers, and utilities.

Examples: this directory contains the core source code:

- Physical models and mathematical formulations
- Numerical solvers and algorithms
- Utility functions
- Data processing and analysis tools

Scripts are well-documented and include docstrings.

The `src/` folder is subdivided into the following main sections:

- **`geometry/`** — sizing of the TES tanks.
- **`input/`** — plant configuration (components, connections, parameters) and plot style.
- **`models/`** — specific plant configurations assembled from the input data.
- **`post_processing/`** — plots, parameters tables and plant validation generated in the post-process stage.
- **Analysis modules** — `cost_analysis.py`, `exergy_analysis.py`, `lcoh_analysis.py`, `network_creator.py`, `plant_operation.py`, and `techno_economic_analysis.py`.

### Geometry

**`geometry/tanks.py`** provides `calculate_tanks_geometry`, which sizes the TES tanks (volume, mass, height, diameter, energy) for HITEC molten salt from the solved plant and a storage duration.

### Input

The `input/` folder contains the functions and input data required to configure the plant model. `components/`, `connections/` and `parameters/` each hold one JSON file per layout and the function that applies it (`set_plant_components`, `set_plant_connections`, `set_plant_parameters`).

The plant network is initialized by **`network_creator.py`** (in `src/`), whose `create_configured_network()` returns an empty TESPy network with the default units.

The `styling/` folder stores the common plotting configuration used throughout the project: `plot_style.json` (all style values), `plot_style.py` (loads it as `PLOT_STYLE`) and `create_figure.py` (creates the figures and diagrams with the specifications from `PLOT_STYLE`).

### Models

The `models/` folder contains the plant layouts considered in the project (S-BR, S-IR, TES-BR, TES-IR). Each layout is defined in **`hthp_models.py`** as a model class pointing to its three JSON files; `build_into(network)` assembles components, connections and parameters into a complete TESPy plant case. `standalone_base_recup_hthp_Benvenuti` reuses the S-BR topology with the parameters of the validation case.

### Post-processing

The `post_processing/` folder contains the functions used to generate plots and tables for the case study:

- `cost_plotting.py`: component cost, LCOH and ΔLCOH figures;
- `economic_plotting.py`: operational strategy plot;
- `exergy_plotting.py`: exergy destruction and exergetic efficiency plots;
- `parameters_tables.py`: performance, sizing and connection tables;
- `plant_validation.py`: `validate_plant`, which compares the calculated plant with the reference data, generates validation tables and the T-s comparison;
- `ts_diagram.py` and `hx_diagram.py`: T-s diagrams of the cycles and heat exchanger diagrams.

### Analysis

- `cost_analysis.py`: `calculate_component_cost`, component and tank cost estimate;
- `exergy_analysis.py`: `get_exergy_analysis`, component exergy destruction and exergetic efficiencies;
- `lcoh_analysis.py`: `calculate_future_costs` and `perform_lcoh_analysis`, levelized cost of heat for the low, central and high price scenarios;
- `plant_operation.py`: `optimize_operational_strategy`, mixed-integer optimization (Pyomo, GLPK) of the HTHP and TES operation against hourly day-ahead prices;
- `techno_economic_analysis.py`: `run_techno_economic_assessment`, the techno-economic analysis of the paper.
