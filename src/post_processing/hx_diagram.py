"""
Heat Exchanger Diagram Plotting Module
=======================================
Creates heat exchanger temperature profile diagrams (Q-T diagrams).
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb
from matplotlib.legend_handler import HandlerTuple

from src import PLOT_STYLE

# Display names of the components (PLOT_STYLE["component_names"], e.g.
# "sink 2" -> "HX2"): only what is written on the plots changes, the names
# used inside the plants and in the CSV tables stay as they are. Keys are
# matched case-insensitively; a name not in the mapping is shown as it is.
_COMPONENT_NAMES = {k.lower(): v for k, v in PLOT_STYLE["component_names"].items()}


def _display_name(name):
    """Display name of a component (see _COMPONENT_NAMES)."""
    return _COMPONENT_NAMES.get(str(name).strip().lower(), name)


def _darken(color, factor=0.6):
    """A darker version of `color` (used for arrows and marker edges)."""
    r, g, b = to_rgb(color)
    return (r * factor, g * factor, b * factor)


def _display_label(conn):
    """Return a connection's label for display, bypassing a CycleCloser.

    A CycleCloser passes the fluid state through unchanged (its inlet and
    outlet are the same physical state), so its own boundary label is an
    artifact of closing the loop, not a meaningful point in the cycle. If
    `conn` sits right on a CycleCloser's boundary, this follows through to
    the label on the other side of it instead.
    """
    if conn.target.__class__.__name__ == "CycleCloser":
        return conn.target.outl[0].label
    if conn.source.__class__.__name__ == "CycleCloser":
        return conn.source.inl[0].label
    return conn.label


# Columns of the heat exchanger table written by save_hx_table (one row per
# heat exchanger, in series order) and read by plot_hx_diagram.
_TABLE_COLUMNS = [
    "Component",
    "Q [MW]",
    "T_hot_in [degC]",
    "T_hot_out [degC]",
    "T_cold_in [degC]",
    "T_cold_out [degC]",
    "hot_in",
    "hot_out",
    "cold_in",
    "cold_out",
]
_LABEL_COLUMNS = ["hot_in", "hot_out", "cold_in", "cold_out"]


def _hx_record_from_component(hx_comp):
    """Everything the diagram needs from one TESpy heat exchanger."""
    c_hot_in = hx_comp.inl[0]
    c_hot_out = hx_comp.outl[0]
    c_cold_in = hx_comp.inl[1]
    c_cold_out = hx_comp.outl[1]

    return {
        "comp_name": hx_comp.label,
        "T_hot_in": c_hot_in.T.val,
        "T_hot_out": c_hot_out.T.val,
        "T_cold_in": c_cold_in.T.val,
        "T_cold_out": c_cold_out.T.val,
        "m_hot": c_hot_in.m.val,
        "m_cold": c_cold_in.m.val,
        "Q": abs(hx_comp.Q.val),  # Heat transferred [MW]
        "hot_in_label": _display_label(c_hot_in),
        "hot_out_label": _display_label(c_hot_out),
        "cold_in_label": _display_label(c_cold_in),
        "cold_out_label": _display_label(c_cold_out),
    }


def _hx_records_from_table(item):
    """The heat exchangers of a table (CSV path or DataFrame written by
    save_hx_table), one record per row, in file order (= series order)."""
    if isinstance(item, (str, Path)):
        df = pd.read_csv(item, dtype={col: str for col in _LABEL_COLUMNS})
    else:
        df = item

    return [
        {
            "comp_name": str(row["Component"]),
            "T_hot_in": float(row["T_hot_in [degC]"]),
            "T_hot_out": float(row["T_hot_out [degC]"]),
            "T_cold_in": float(row["T_cold_in [degC]"]),
            "T_cold_out": float(row["T_cold_out [degC]"]),
            "m_hot": None,
            "m_cold": None,
            "Q": abs(float(row["Q [MW]"])),
            "hot_in_label": str(row["hot_in"]),
            "hot_out_label": str(row["hot_out"]),
            "cold_in_label": str(row["cold_in"]),
            "cold_out_label": str(row["cold_out"]),
        }
        for _, row in df.iterrows()
    ]


def save_hx_table(hx_components, file_name, save_path):
    """Save the heat exchangers of a solved plant as a table that
    plot_hx_diagram can plot later without TESpy.

    Parameters
    ----------
    hx_components : HeatExchanger component or list of them
        The heat exchangers to save, in series order (the same list you would
        give to plot_hx_diagram for one graph, e.g. [sink_1, sink_2]).
    file_name : str
        Base name; saved as <save_path>/<file_name>_hx_table.csv
    save_path : str or Path
        Directory to save the table in (created if missing).

    Returns
    -------
    pd.DataFrame
    """
    if not isinstance(hx_components, (list, tuple)):
        hx_components = [hx_components]

    rows = []
    for hx_comp in hx_components:
        r = _hx_record_from_component(hx_comp)
        rows.append(
            [
                r["comp_name"],
                round(r["Q"], 6),
                round(r["T_hot_in"], 4),
                round(r["T_hot_out"], 4),
                round(r["T_cold_in"], 4),
                round(r["T_cold_out"], 4),
                r["hot_in_label"],
                r["hot_out_label"],
                r["cold_in_label"],
                r["cold_out_label"],
            ]
        )
    df = pd.DataFrame(rows, columns=_TABLE_COLUMNS)

    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)
    out = save_path / f"{file_name}_hx_table.csv"
    df.to_csv(out, index=False)
    print(f"✓ Table saved: {out}")
    return df


def _draw_hx_panel(ax, hx_components):
    """Draw one or more heat exchangers in series on `ax`. Each item is a
    TESpy heat exchanger or a table (CSV path / DataFrame from
    save_hx_table, which stands for all of its rows)."""

    plot_style = PLOT_STYLE

    # Colours of the hot and cold side of each heat exchanger, in series
    # order: index 0 (dark) = first heat exchanger, index 1 (light) = second
    hot_colors = plot_style["hx_colors"]["hot"]
    cold_colors = plot_style["hx_colors"]["cold"]

    # Accept either a single item or a list of them.
    if not isinstance(hx_components, (list, tuple)):
        hx_components = [hx_components]

    # Extract temperature data for all heat exchangers
    hx_data = []
    for item in hx_components:
        if isinstance(item, (str, Path, pd.DataFrame)):
            hx_data.extend(_hx_records_from_table(item))
        else:
            hx_data.append(_hx_record_from_component(item))
    total_Q = sum(data["Q"] for data in hx_data)

    # Plot all heat exchangers
    hx_data_reversed = list(reversed(hx_data))
    cumulative_Q = 0

    all_temperatures = []
    legend_entries = []  # ((hot line, cold line), heat exchanger name)

    for idx, data in enumerate(hx_data_reversed):
        Q = data["Q"]
        q_array = np.linspace(0, Q, 100)
        q_array_shifted = q_array + cumulative_Q

        T_hot_profile = data["T_hot_out"] + (data["T_hot_in"] - data["T_hot_out"]) * (
            q_array / Q
        )
        T_cold_profile = data["T_cold_in"] + (
            data["T_cold_out"] - data["T_cold_in"]
        ) * (q_array / Q)

        all_temperatures.extend(T_hot_profile)
        all_temperatures.extend(T_cold_profile)

        # colours follow the series order: first heat exchanger = dark ones
        order = len(hx_data) - 1 - idx
        color_hot = hot_colors[order % len(hot_colors)]
        color_cold = cold_colors[order % len(cold_colors)]
        dark_hot = _darken(color_hot)
        dark_cold = _darken(color_cold)

        (line_hot,) = ax.plot(
            q_array_shifted,
            T_hot_profile,
            color=color_hot,
            linewidth=plot_style["lines_and_markers"]["linewidth"] + 1,
        )

        (line_cold,) = ax.plot(
            q_array_shifted,
            T_cold_profile,
            color=color_cold,
            linewidth=plot_style["lines_and_markers"]["linewidth"] + 1,
        )

        legend_entries.append(((line_hot, line_cold), _display_name(data["comp_name"])))

        # Mark inlet/outlet points
        ax.scatter(
            cumulative_Q + Q,
            data["T_hot_in"],
            color=color_hot,
            s=plot_style["lines_and_markers"]["point_size"] * 1.5,
            marker="^",
            edgecolors=dark_hot,
            linewidths=2,
            zorder=5,
        )

        ax.text(
            cumulative_Q + Q,
            data["T_hot_in"] + 1,
            f"  {data['hot_in_label']}",
            fontsize=plot_style["fonts"]["value"],
            ha="center",
            va="bottom",
            color="black",
        )

        ax.scatter(
            cumulative_Q,
            data["T_hot_out"],
            color=color_hot,
            s=plot_style["lines_and_markers"]["point_size"] * 1.5,
            marker="v",
            edgecolors=dark_hot,
            linewidths=2,
            zorder=5,
        )

        ax.text(
            cumulative_Q,
            data["T_hot_out"] + 1,
            f"{data['hot_out_label']}  ",
            fontsize=plot_style["fonts"]["value"],
            ha="center",
            va="bottom",
            color="black",
        )

        if idx == 0:
            ax.scatter(
                cumulative_Q,
                data["T_cold_in"],
                color=color_cold,
                s=plot_style["lines_and_markers"]["point_size"] * 1.5,
                marker="^",
                edgecolors=dark_cold,
                linewidths=2,
                zorder=5,
            )

            ax.text(
                cumulative_Q,
                data["T_cold_in"] - 1,
                f"{data['cold_in_label']}  ",
                fontsize=plot_style["fonts"]["value"],
                ha="center",
                va="top",
                color="black",
            )

        if idx < len(hx_data) - 1 or idx == len(hx_data) - 1:
            ax.scatter(
                cumulative_Q + Q,
                data["T_cold_out"],
                color=color_cold,
                s=plot_style["lines_and_markers"]["point_size"] * 1.5,
                marker="v",
                edgecolors=dark_cold,
                linewidths=2,
                zorder=5,
            )

            ax.text(
                cumulative_Q + Q,
                data["T_cold_out"] - 1,
                f"  {data['cold_out_label']}",
                fontsize=plot_style["fonts"]["value"],
                ha="center",
                va="top",
                color="black",
            )

        if idx < len(hx_data) - 1:
            ax.axvline(
                x=cumulative_Q + Q,
                color="gray",
                linestyle="--",
                linewidth=1.5,
                alpha=0.6,
            )

        cumulative_Q += Q

    # Legend: one entry per heat exchanger (hot and cold line side by side),
    # in series order
    legend_entries.reverse()
    ax.legend(
        [handles for handles, _ in legend_entries],
        [name for _, name in legend_entries],
        handler_map={tuple: HandlerTuple(ndivide=None, pad=0)},
        loc="best",
        fontsize=plot_style["fonts"]["value"],
        framealpha=0.95,
    )

    grid_style = plot_style["grid"]

    ax.grid(
        True,
        color=grid_style["color"],
        linestyle=grid_style["linestyle"],
        linewidth=grid_style["linewidth"],
        alpha=grid_style["alpha"],
    )

    for spine in ax.spines.values():
        spine.set_color(plot_style["axes"]["spine_color"])
        spine.set_linewidth(plot_style["axes"]["spine_linewidth"])

    ax.set_box_aspect(plot_style["axes"]["box_aspect"])
    ax.set_facecolor(plot_style["figure"]["facecolor"])

    y_min = min(all_temperatures) - 5
    y_max = max(all_temperatures) + 5
    ax.set_ylim(y_min, y_max)
    ax.set_xlim(-0.05, total_Q * 1.05)

    # Formatting
    ax.set_xlabel(
        r"Heat $[\mathrm{MW_{th}}]$",
        fontsize=plot_style["fonts"]["label"],
    )
    ax.set_ylabel(
        r"Temperature $[^\circ\mathrm{C}]$",
        fontsize=plot_style["fonts"]["label"],
    )

    ticks_style = plot_style["ticks"]

    ax.tick_params(
        axis=ticks_style["axis"],
        pad=ticks_style["pad"],
        which=ticks_style["which"],
        color=ticks_style["color"],
        labelcolor=ticks_style["labelcolor"],
        direction=ticks_style["direction"],
        labelsize=plot_style["fonts"]["tick"],
    )


def plot_hx_diagram(hx_components, file_name=None, save_path=None):
    """
    Plot heat exchanger diagrams: one graph, or several graphs side by side.

    Parameters
    ----------
    hx_components : HeatExchanger / CSV path / DataFrame, list, or list of lists
        Each item is a TESpy heat exchanger, or a table written by
        save_hx_table (CSV path or DataFrame) which stands for all the heat
        exchangers in it, in file order. Both kinds can be mixed.
        - one component: a single graph.
        - flat list ``[sink_1, sink_2]``: one graph with the heat exchangers
          in series, as before.
        - list of lists ``[[hx1], [hx2, hx3]]``: one graph per inner list,
          side by side from left to right, each graph with the heat
          exchangers of its inner list in series and labelled (a), (b), ...
          Each graph has its own axis limits.
    file_name : str, optional
        Base name for the saved file (will be saved as PNG)
    save_path : str or Path, optional
        Directory to save the figure. If None, the figure is not saved.

    Returns
    -------
    fig, ax : matplotlib figure and axis (single graph), or figure and array
        of axes (several graphs)
    """

    plot_style = PLOT_STYLE

    # normalise the input to a list of graphs, each a list of heat exchangers
    if isinstance(hx_components, (list, tuple)):
        if not hx_components:
            raise ValueError("`hx_components` is empty.")
        if isinstance(hx_components[0], (list, tuple)):
            panels = [list(p) for p in hx_components]
        else:
            panels = [list(hx_components)]
    else:
        panels = [[hx_components]]
    n_panels = len(panels)

    w, h = plot_style["figure"]["figsize"]
    fig, axes = plt.subplots(
        1,
        n_panels,
        figsize=(w * n_panels, h),
        dpi=plot_style["figure"]["dpi"],
        squeeze=False,
    )
    axes = axes.ravel()

    for k, (ax, panel) in enumerate(zip(axes, panels)):
        _draw_hx_panel(ax, panel)
        if n_panels > 1:
            ax.set_title(
                f"({chr(ord('a') + k)})", fontsize=plot_style["fonts"]["title"], pad=10
            )

    fig.patch.set_facecolor(plot_style["figure"]["facecolor"])
    if n_panels > 1:
        fig.tight_layout()

    if save_path is not None:
        if file_name is None:
            raise ValueError("file_name is required when save_path is given.")
        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            save_path / f"{file_name}_hx_diagram.png",
            dpi=plot_style["figure"]["dpi"],
            bbox_inches="tight",
            facecolor=plot_style["figure"]["facecolor"],
        )
        print(f"✓ Figure saved: {save_path / f'{file_name}_hx_diagram.png'}")

    if n_panels == 1:
        return fig, axes[0]
    return fig, axes
