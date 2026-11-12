"""
Plot Style Loader
=================

Loads the plotting configuration from ``plot_style.json`` and sets the global
Matplotlib style from it.

Works with both versions of the JSON:
- new: a ``paper_fonts`` block (family, mathtext, title, label, tick, legend,
  annotation, in points) sets the global font defaults;
- old: no ``paper_fonts`` block, the original global style is used (serif,
  font size 11) and the plots set their own sizes.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt


def _load_plot_style():
    """Load the plotting configuration from the JSON file."""

    # JSON is stored in the same folder as this file
    json_path = Path(__file__).parent / "plot_style.json"

    if not json_path.exists():
        raise FileNotFoundError(f"plot_style.json not found at {json_path}")

    with open(json_path, "r") as f:
        config = json.load(f)

    # Convert figsize from JSON list to Python tuple (old plots use it)
    if "figsize" in config.get("figure", {}):
        config["figure"]["figsize"] = tuple(config["figure"]["figsize"])

    return config


def _setup_plot_style(config):
    """Set up global Matplotlib styling from the loaded configuration."""
    fonts = config.get("paper_fonts")

    if fonts is None:
        # old JSON: original global style
        plt.rcParams["font.family"] = "serif"
        plt.rcParams["mathtext.fontset"] = "dejavuserif"
        plt.rcParams["font.size"] = 11
        return

    # new JSON: one fixed size in points for each text role
    plt.rcParams.update(
        {
            "font.family": fonts.get("family", "serif"),
            "mathtext.fontset": fonts.get("mathtext", "dejavuserif"),
            "font.size": fonts["label"],
            "axes.titlesize": fonts["title"],
            "axes.labelsize": fonts["label"],
            "xtick.labelsize": fonts["tick"],
            "ytick.labelsize": fonts["tick"],
            "legend.fontsize": fonts["legend"],
            "figure.titlesize": fonts["title"],
        }
    )


# Load plotting configuration on import and set up Matplotlib styling
PLOT_STYLE = _load_plot_style()
_setup_plot_style(PLOT_STYLE)
