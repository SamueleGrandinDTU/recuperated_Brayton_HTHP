# recuperated_Brayton_HTHP

Repository for the development of a single case study: thermo-economic analysis of a recuperated Brayton High-Temperature Heat Pump (HTHP).

## User Guide

### 1. Set up the Python environment

It is recommended to use a dedicated Python virtual environment for this repository. This keeps the project's dependencies isolated from other Python projects installed on your computer.

From the root directory of the repository, create a virtual environment:

```bash
python -m venv tespy_env
```

Activate the virtual environment:

**Windows PowerShell:**

```powershell
.\tespy_env\Scripts\Activate.ps1
```

Once activated, the terminal should display `(tespy_env)` at the beginning of the command line.

### 2. Install the required packages

The Python packages required to run the code are listed in `requirements.txt`.

With the virtual environment activated, install all required packages by running:

```bash
python -m pip install -r requirements.txt
```

The `requirements.txt` file contains the external Python dependencies required by the repository. Python's standard-library modules, such as `os`, `json`, `pathlib`, and `re`, do not need to be installed separately.

Whenever a new external package is required by the repository, it should be added to `requirements.txt`.