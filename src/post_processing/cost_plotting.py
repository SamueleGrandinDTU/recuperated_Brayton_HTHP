"""Cost plotting for the standalone base recuperated HTHP."""

import textwrap
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from src import PLOT_STYLE

# Fixed component order + colors (case-insensitive match on component name)
_COMPONENT_COLOR_ORDER = [
    ("compressor", "#08519c"),  # dark blue
    ("compressor 1", "#3182bd"),  # blue
    ("compressor 2", "#9ecae1"),  # light blue
    ("turbine", "#2ca02c"),  # green
    ("sink", "#67000d"),  # dark red
    ("sink 1", "#de2d26"),  # red
    ("sink 2", "#fc9272"),  # light red
    ("recuperator", "#8c564b"),  # brown
    ("interface hx", "#e377c2"),  # pink
]
_COMPONENT_ORDER = [c for c, _ in _COMPONENT_COLOR_ORDER]
_COMPONENT_COLORS = {c: color for c, color in _COMPONENT_COLOR_ORDER}

_CYCLE_LABEL = "Standalone Base Recuperated"
_WRAP_WIDTH = 14


def _normalize_input(data):
    """Convert single DataFrame or list of DataFrames to list."""
    if data is None:
        return None
    if isinstance(data, list):
        return data
    else:
        return [data]


def plot_component_cost_stacked(
    component_cost,
    save_path=None,
    file_name=None,
):
    """
    Plot component cost as a single stacked bar for the standalone base
    recuperated cycle. Component stacking order and colors follow a fixed,
    predefined scheme so they stay consistent
    across figures.

    Parameters
    ----------
    component_cost : pd.DataFrame
        The cost table from calculate_component_cost.
    save_path : str or Path, optional
        Directory to save the figure.
    file_name : str, default "component_cost_stacked"
        Base name for the saved file.

    Returns
    -------
    fig, ax
    """
    df_list = _normalize_input(component_cost)
    if df_list is None or all(df.empty for df in df_list):
        print("Warning: No data provided")
        return None, None

    cost_col = None
    for df in df_list:
        if not df.empty:
            cost_col = [c for c in df.columns if "Cost" in c and "M€" in c][0]
            break

    # Components actually present, ordered per the fixed scheme;
    # anything not in the scheme is appended (sorted) with a fallback color.
    present = {comp for df in df_list for comp in df["Component"].values}
    ordered_components = [
        c
        for c in _COMPONENT_ORDER
        if c in present or c.lower() in {p.lower() for p in present}
    ]
    # map back to the actual casing used in the data
    present_lookup = {p.lower(): p for p in present}
    ordered_components = [
        present_lookup[c] for c in ordered_components if c in present_lookup
    ]

    leftover = sorted(present - set(ordered_components))
    ordered_components += leftover

    extra_cmap = plt.cm.tab10
    colors = {}
    extra_idx = 0
    for comp in ordered_components:
        key = comp.lower()
        if key in _COMPONENT_COLORS:
            colors[comp] = _COMPONENT_COLORS[key]
        else:
            colors[comp] = extra_cmap(extra_idx % 10)
            extra_idx += 1

    cycle_labels = [_CYCLE_LABEL]
    wrapped_labels = [textwrap.fill(lbl, width=_WRAP_WIDTH) for lbl in cycle_labels]

    x = np.arange(len(df_list))

    fig, ax = plt.subplots(
        figsize=PLOT_STYLE["figure"]["figsize"], dpi=PLOT_STYLE["figure"]["dpi"]
    )

    bottoms = np.zeros(len(df_list))
    for comp in ordered_components:
        values = []
        for df in df_list:
            row = df[df["Component"] == comp]
            values.append(row[cost_col].values[0] if not row.empty else 0.0)
        values = np.array(values)

        ax.bar(
            x,
            values,
            bottom=bottoms,
            width=0.4,
            label=comp,
            color=colors[comp],
            edgecolor=PLOT_STYLE["colors"]["edge"],
            linewidth=PLOT_STYLE["lines_and_markers"]["linewidth"],
            alpha=0.85,
        )
        bottoms += values

    ax.set_ylabel(r"CAPEX [M€]", fontsize=PLOT_STYLE["fonts"]["label"])
    ax.set_xlabel(r"Cycle", fontsize=PLOT_STYLE["fonts"]["label"])

    ax.set_xticks(x)
    ax.set_xticklabels(
        wrapped_labels,
        ha="center",
        rotation=0,
        fontsize=PLOT_STYLE["fonts"]["tick"],
    )
    ax.set_xlim(-1, 1)

    # Legend on the right, outside the plot area
    ax.legend(
        fontsize=PLOT_STYLE["fonts"]["legend"],
        framealpha=0.95,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        ncol=1,
    )

    ax.grid(
        axis="y",
        alpha=PLOT_STYLE["grid"]["alpha"],
        linestyle="--",
        linewidth=PLOT_STYLE["grid"]["linewidth"],
    )
    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_color(PLOT_STYLE["axes"]["spine_color"])
        spine.set_linewidth(PLOT_STYLE["axes"]["spine_linewidth"])

    ax.tick_params(
        axis=PLOT_STYLE["ticks"]["axis"],
        pad=PLOT_STYLE["ticks"]["pad"],
        which=PLOT_STYLE["ticks"]["which"],
        color=PLOT_STYLE["ticks"]["color"],
        labelcolor=PLOT_STYLE["ticks"]["labelcolor"],
        direction=PLOT_STYLE["ticks"]["direction"],
    )

    ax.set_box_aspect(PLOT_STYLE["axes"]["box_aspect"])
    ax.set_facecolor(PLOT_STYLE["axes"]["facecolor"])
    fig.patch.set_facecolor(PLOT_STYLE["figure"]["facecolor"])

    if save_path is not None:
        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            save_path / f"{file_name}_cost_stacked.png",
            dpi=PLOT_STYLE["figure"]["dpi"],
            bbox_inches="tight",
            facecolor=PLOT_STYLE["figure"]["facecolor"],
        )
        print(f"✓ Figure saved: {save_path / f'{file_name}_cost_stacked.png'}")

    return fig, ax
