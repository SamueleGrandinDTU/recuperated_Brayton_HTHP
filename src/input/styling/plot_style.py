"""
Plot Style Loader
=================

Sets the global Matplotlib style and loads the plotting configuration
from ``plot_style.json``.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt


def _setup_plot_style():
    """Set up global Matplotlib styling."""
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["mathtext.fontset"] = "dejavuserif"
    plt.rcParams["font.size"] = 11


def _load_plot_style():
    """Load the plotting configuration from the JSON file."""

    # JSON is stored in the same folder as this file
    json_path = Path(__file__).parent / "plot_style.json"

    if not json_path.exists():
        raise FileNotFoundError(f"plot_style.json not found at {json_path}")

    with open(json_path, "r") as f:
        config = json.load(f)

    # Convert figsize from JSON list to Python tuple
    config["figure"]["figsize"] = tuple(config["figure"]["figsize"])

    return config


# Set up Matplotlib styling automatically
_setup_plot_style()

# Load plotting configuration on import
PLOT_STYLE = _load_plot_style()
