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

- **`input/`** — plant configuration, input data, and functions used to build and parameterize the plant network.
- **`models/`** — specific plant configurations assembled from the input data.
- **`plotting/`** — functions used to generate plots for the analysis and visualization of the plant cycle and its components.
- **`validation/`** — functions used to validate the plant models against reference data.
- **`[next folder]/`** — description to be added.

### Input

The `input/` folder contains the functions and input data required to configure the plant model. It is organized around the definition of **components**, **connections**, and **plant parameters**, stored in JSON files and applied through the corresponding Python functions.

The plant network is initialized by **`network_creator.py`**, which creates the TESPy network with the predefined configuration and default units.

The `input/` folder also contains `style_parameters/`, which stores the common plotting configuration used throughout the project.

The input structure therefore separates the **plant configuration data** from the **source code used to build and parameterize the network**.

### Models

The `models/` folder contains the specific plant configurations considered in the project. Each model assembles the corresponding components, connections, and plant parameters from the `input/` folder into a complete TESPy plant case.

Each plant configuration is defined in **`hthp_models.py`**, with the corresponding model class linking the model to its specific input files.

### Plotting

The `plotting/` folder contains the functions used to generate plots for the understanding and analysis of the plant cycle and its components.

The folder currently contains **`ts_diagram.py`** and **`hx_diagram.py`**, which provide the functions that generate T-s diagrams for the cycle and diagrams for the analysis of heat exchanger performance.

### Validation

The `validation/` folder contains the functions used to validate the plant models against reference data. 

Plant validation is performed through **`plant_validation.py`**, which provides functions for comparing calculated plant results with reference data, generating validation tables, and comparing the calculated and reference cycles on a T-s diagram.
