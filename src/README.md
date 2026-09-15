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
- **`[next folder]/`** — description to be added.
- **`[next folder]/`** — description to be added.
- **`[next folder]/`** — description to be added.

### Input

The `input/` folder contains the functions and input data required to configure the plant model. It is organized around the definition of **components**, **connections**, and **plant parameters**, stored in JSON files and applied through the corresponding Python functions.

The plant network is initialized by **`network_creator.py`**, which creates the TESPy network with the predefined configuration and default units.

The input structure therefore separates the **plant configuration data** from the **source code used to build and parameterize the network**.