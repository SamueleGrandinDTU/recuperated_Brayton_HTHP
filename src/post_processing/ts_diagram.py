"""
T-s Diagram Plotting Module
============================
Creates T-s diagrams for thermodynamic cycles, from a solved TESpy plant or
from a CSV file of state points, for one cycle or several on the same graph.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fluprodia import FluidPropertyDiagram

from src import PLOT_STYLE

# Two consecutive state points whose pressures differ by less than this
# (relative) are joined by an isobar; otherwise by a straight segment
# (compressor / turbine, short and almost vertical in the T-s diagram).
_ISOBAR_TOL = 1e-3

# Colors of the cycles when several are drawn on the same graph: the first is
# PLOT_STYLE["colors"]["process"] (red), then these.
_EXTRA_CYCLE_COLORS = ["#1f77b4", "#2ca02c", "#ff7f0e"]

_DIAGRAM_FLUID = "air"

# Order in which the state points of a CSV are joined (labels not listed here
# are appended after these, in file order). The intercooled cycle runs
# 2 -> 2i (intercooler) -> 3i (second compressor) -> 3 (cooling) -> 4.
_CYCLE_ORDER = ["0", "1", "2", "2i", "3i", "3", "4", "5"]


def _find_column(df, name):
    """Column of a state table named `name` or "<name> [unit]"."""
    for col in df.columns:
        c = str(col).strip()
        if c == name or c.startswith(f"{name} ["):
            return col
    raise KeyError(f"No '{name}' column found in {list(df.columns)}")


def _cycle_from_plant(plant, diagram):
    """Curves and state points of a solved TESpy plant.

    Returns {"curves": [(s, T), ...], "states": {label: (s, T)}}.
    """
    result_dict = {}

    for comp in plant.comps["object"]:
        plotting_data = comp.get_plotting_data()

        if plotting_data is not None:
            for key in plotting_data.keys():
                inlet_conn = comp.inl[key - 1] if key <= len(comp.inl) else None

                if inlet_conn is not None:
                    conn_label = inlet_conn.label
                    result_dict[conn_label] = plotting_data[key]

    # Calculate individual isolines for each computed state
    for key, data in result_dict.items():
        result_dict[key]["datapoints"] = diagram.calc_individual_isoline(**data)

    curves = []
    states = {}

    for key in result_dict.keys():
        datapoints = result_dict[key]["datapoints"]
        curves.append((datapoints["s"], datapoints["T"]))

        states[key] = (datapoints["s"][0], datapoints["T"][0])
        outlet_s = datapoints["s"][-1]
        outlet_T = datapoints["T"][-1]

        for comp in plant.comps["object"]:
            plotting_data = comp.get_plotting_data()
            if plotting_data is not None:
                for plot_key in plotting_data.keys():
                    if plot_key != 0:
                        inlet_conn = (
                            comp.inl[plot_key - 1]
                            if plot_key <= len(comp.inl)
                            else None
                        )
                        if inlet_conn is not None and inlet_conn.label == key:
                            outlet_conn = (
                                comp.outl[plot_key - 1]
                                if plot_key <= len(comp.outl)
                                else None
                            )
                            if outlet_conn is not None:
                                states[outlet_conn.label] = (outlet_s, outlet_T)
                            break

    return {"curves": curves, "states": states}


def _cycle_from_csv(item, diagram, fluid=_DIAGRAM_FLUID):
    """Curves and state points of a cycle from a state table.

    `item` is a CSV path or a DataFrame with columns
    "Connection, T [degC], p [bar], s [kJ/kgK], h [kJ/kg], ..., fluid".
    Only the rows of the diagram's fluid are used (e.g. the HITEC rows of a
    TES-integrated cycle are skipped). The rows are put in the order of
    _CYCLE_ORDER and each row is joined to the next one: by an isobar when
    the pressure does not change, by a straight segment otherwise. The last row is not joined
    back to the first.

    Returns {"curves": [(s, T), ...], "states": {label: (s, T)}}.
    """
    df = pd.read_csv(item) if isinstance(item, (str, Path)) else item.copy()

    if "fluid" in df.columns:
        df = df[df["fluid"].astype(str).str.lower() == fluid.lower()]
    df = df.reset_index(drop=True)

    # put the rows in cycle order, not file order
    rank = {label: i for i, label in enumerate(_CYCLE_ORDER)}
    keys = df[df.columns[0]].astype(str).map(lambda lab: rank.get(lab, len(rank)))
    df = df.iloc[keys.argsort(kind="stable")].reset_index(drop=True)

    labels = df[df.columns[0]].astype(str).tolist()
    T = df[_find_column(df, "T")].astype(float).to_numpy()
    p = df[_find_column(df, "p")].astype(float).to_numpy()
    s = df[_find_column(df, "s")].astype(float).to_numpy()
    h = df[_find_column(df, "h")].astype(float).to_numpy()

    curves = []
    for i in range(len(df) - 1):
        if abs(p[i] - p[i + 1]) <= _ISOBAR_TOL * max(p[i], p[i + 1]):
            datapoints = diagram.calc_individual_isoline(
                isoline_property="p",
                isoline_value=p[i],
                isoline_value_end=p[i + 1],
                starting_point_property="h",
                starting_point_value=h[i],
                ending_point_property="h",
                ending_point_value=h[i + 1],
            )
            curves.append((datapoints["s"], datapoints["T"]))
        else:
            curves.append((np.array([s[i], s[i + 1]]), np.array([T[i], T[i + 1]])))

    states = {label: (s[i], T[i]) for i, label in enumerate(labels)}

    return {"curves": curves, "states": states}


def _draw_ts_panel(ax, items, cycle_labels, colors, label_all_states):
    """Draw the cycles `items` (plants / CSVs, overlaid) on one axes."""

    plot_style = PLOT_STYLE

    if cycle_labels is not None and len(cycle_labels) != len(items):
        raise ValueError(
            f"cycle_labels has {len(cycle_labels)} entries but "
            f"{len(items)} cycles were given."
        )
    if colors is None:
        colors = [plot_style["colors"]["process"]] + _EXTRA_CYCLE_COLORS
    if len(colors) < len(items):
        raise ValueError("Not enough colors for the number of cycles.")

    # Initialize the diagram
    diagram = FluidPropertyDiagram(_DIAGRAM_FLUID)
    diagram.set_unit_system(T="°C", p="bar", h="kJ/kg", s="kJ/kgK")

    # Curves and state points of every cycle
    cycles = []
    for item in items:
        if isinstance(item, (str, Path, pd.DataFrame)):
            cycles.append(_cycle_from_csv(item, diagram))
        else:
            cycles.append(_cycle_from_plant(item, diagram))

    # Extract all s and T values (all cycles) to determine axis limits
    all_s = []
    all_T = []
    for cycle in cycles:
        for s_curve, T_curve in cycle["curves"]:
            all_s += [s_curve[0], s_curve[-1]]
            all_T += [T_curve[0], T_curve[-1]]
        for s_state, T_state in cycle["states"].values():
            all_s.append(s_state)
            all_T.append(T_state)

    x_min = min(all_s) - plot_style["layout"]["auto_x_padding"]
    x_max = max(all_s) + plot_style["layout"]["auto_x_padding"]
    y_min = min(all_T) - plot_style["layout"]["auto_y_padding"]
    y_max = max(all_T) + plot_style["layout"]["auto_y_padding"]

    # Set isolines for T-s diagram
    isolines = {
        "Q": np.linspace(
            PLOT_STYLE["ts_diagram"]["isoline_quality"]["start"],
            PLOT_STYLE["ts_diagram"]["isoline_quality"]["end"],
            PLOT_STYLE["ts_diagram"]["isoline_quality"]["num"],
        ),
        "p": np.array([]),
        "v": np.array([]),
        "h": np.arange(
            PLOT_STYLE["ts_diagram"]["isoline_enthalpy"]["start"],
            PLOT_STYLE["ts_diagram"]["isoline_enthalpy"]["end"],
            PLOT_STYLE["ts_diagram"]["isoline_enthalpy"]["step"],
        ),
    }

    diagram.set_isolines(**isolines)
    diagram.calc_isolines()

    # Draw isolines
    diagram.draw_isolines(
        None,
        ax,
        "Ts",
        x_min=x_min,
        x_max=x_max,
        y_min=y_min,
        y_max=y_max,
    )

    # Adjust isoline label font size
    for text in ax.texts:
        text.set_fontsize(plot_style["fonts"]["isoline"])

    # Plot the T-s curves of each cycle, in the order given (later cycles
    # are drawn on top of earlier ones)
    for k, cycle in enumerate(cycles):
        for s_curve, T_curve in cycle["curves"]:
            ax.plot(
                s_curve,
                T_curve,
                color=colors[k],
                linewidth=plot_style["lines_and_markers"]["linewidth"],
            )
            ax.scatter(
                [s_curve[0], s_curve[-1]],
                [T_curve[0], T_curve[-1]],
                color=colors[k],
                s=plot_style["lines_and_markers"]["point_size"],
                zorder=5,
            )

    # Add state point labels (last cycle only, unless label_all_states)
    custom_mults = plot_style.get("directional_labels", {})
    labeled_cycles = cycles if label_all_states else cycles[-1:]

    for cycle in labeled_cycles:
        for conn_label, (s_state, T_state) in cycle["states"].items():
            lbl_str = str(conn_label)

            if lbl_str in custom_mults:
                offset_x, offset_y = custom_mults[lbl_str]
            else:
                offset_x = plot_style["layout"]["label_x_offset"]
                offset_y = plot_style["layout"]["label_y_offset"]

            ha_val = "right" if offset_x < 0 else ("left" if offset_x > 0 else "center")
            va_val = "top" if offset_y < 0 else ("bottom" if offset_y > 0 else "center")

            ax.text(
                s_state + offset_x,
                T_state + offset_y,
                conn_label,
                fontsize=plot_style["fonts"]["value"],
                color=plot_style["colors"]["label"],
                ha=ha_val,
                va=va_val,
            )

    # Legend (one line per cycle), upper left
    if cycle_labels is not None:
        for k, label in enumerate(cycle_labels):
            ax.plot(
                [],
                [],
                color=colors[k],
                linewidth=plot_style["lines_and_markers"]["linewidth"],
                label=label,
            )
        ax.legend(
            loc="upper left",
            fontsize=plot_style["fonts"]["legend"],
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

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)

    ax.set_xlabel(
        r"Entropy $\left[\mathrm{\frac{kJ}{kg\,K}}\right]$",
        fontsize=plot_style["fonts"]["label"],
    )
    ax.set_ylabel(
        r"Temperature $\left[^\circ\mathrm{C}\right]$",
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


def _draw_ts_panel(ax, items, cycle_labels, colors, label_all_states):
    """Draw the cycles `items` (plants / CSVs, overlaid) on one axes."""

    plot_style = PLOT_STYLE

    if cycle_labels is not None and len(cycle_labels) != len(items):
        raise ValueError(
            f"cycle_labels has {len(cycle_labels)} entries but "
            f"{len(items)} cycles were given."
        )
    if colors is None:
        colors = [plot_style["colors"]["process"]] + _EXTRA_CYCLE_COLORS
    if len(colors) < len(items):
        raise ValueError("Not enough colors for the number of cycles.")

    # Initialize the diagram
    diagram = FluidPropertyDiagram(_DIAGRAM_FLUID)
    diagram.set_unit_system(T="°C", p="bar", h="kJ/kg", s="kJ/kgK")

    # Curves and state points of every cycle
    cycles = []
    for item in items:
        if isinstance(item, (str, Path, pd.DataFrame)):
            cycles.append(_cycle_from_csv(item, diagram))
        else:
            cycles.append(_cycle_from_plant(item, diagram))

    # Extract all s and T values (all cycles) to determine axis limits
    all_s = []
    all_T = []
    for cycle in cycles:
        for s_curve, T_curve in cycle["curves"]:
            all_s += [s_curve[0], s_curve[-1]]
            all_T += [T_curve[0], T_curve[-1]]
        for s_state, T_state in cycle["states"].values():
            all_s.append(s_state)
            all_T.append(T_state)

    x_min = min(all_s) - plot_style["layout"]["auto_x_padding"]
    x_max = max(all_s) + plot_style["layout"]["auto_x_padding"]
    y_min = min(all_T) - plot_style["layout"]["auto_y_padding"]
    y_max = max(all_T) + plot_style["layout"]["auto_y_padding"]

    # Set isolines for T-s diagram
    isolines = {
        "Q": np.linspace(
            PLOT_STYLE["ts_diagram"]["isoline_quality"]["start"],
            PLOT_STYLE["ts_diagram"]["isoline_quality"]["end"],
            PLOT_STYLE["ts_diagram"]["isoline_quality"]["num"],
        ),
        "p": np.array([]),
        "v": np.array([]),
        "h": np.arange(
            PLOT_STYLE["ts_diagram"]["isoline_enthalpy"]["start"],
            PLOT_STYLE["ts_diagram"]["isoline_enthalpy"]["end"],
            PLOT_STYLE["ts_diagram"]["isoline_enthalpy"]["step"],
        ),
    }

    diagram.set_isolines(**isolines)
    diagram.calc_isolines()

    # Draw isolines
    diagram.draw_isolines(
        None,
        ax,
        "Ts",
        x_min=x_min,
        x_max=x_max,
        y_min=y_min,
        y_max=y_max,
    )

    # Adjust isoline label font size
    for text in ax.texts:
        text.set_fontsize(plot_style["fonts"]["isoline"])

    # Plot the T-s curves of each cycle, in the order given (later cycles
    # are drawn on top of earlier ones)
    for k, cycle in enumerate(cycles):
        for s_curve, T_curve in cycle["curves"]:
            ax.plot(
                s_curve,
                T_curve,
                color=colors[k],
                linewidth=plot_style["lines_and_markers"]["linewidth"],
            )
            ax.scatter(
                [s_curve[0], s_curve[-1]],
                [T_curve[0], T_curve[-1]],
                color=colors[k],
                s=plot_style["lines_and_markers"]["point_size"],
                zorder=5,
            )

    # Add state point labels (last cycle only, unless label_all_states)
    custom_mults = plot_style.get("directional_labels", {})
    labeled_cycles = cycles if label_all_states else cycles[-1:]

    for cycle in labeled_cycles:
        for conn_label, (s_state, T_state) in cycle["states"].items():
            lbl_str = str(conn_label)

            if lbl_str in custom_mults:
                offset_x, offset_y = custom_mults[lbl_str]
            else:
                offset_x = plot_style["layout"]["label_x_offset"]
                offset_y = plot_style["layout"]["label_y_offset"]

            ha_val = "right" if offset_x < 0 else ("left" if offset_x > 0 else "center")
            va_val = "top" if offset_y < 0 else ("bottom" if offset_y > 0 else "center")

            ax.text(
                s_state + offset_x,
                T_state + offset_y,
                conn_label,
                fontsize=plot_style["fonts"]["value"],
                color=plot_style["colors"]["label"],
                ha=ha_val,
                va=va_val,
            )

    # Legend (one line per cycle), upper left
    if cycle_labels is not None:
        for k, label in enumerate(cycle_labels):
            ax.plot(
                [],
                [],
                color=colors[k],
                linewidth=plot_style["lines_and_markers"]["linewidth"],
                label=label,
            )
        ax.legend(
            loc="upper left",
            fontsize=plot_style["fonts"]["legend"],
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

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)

    ax.set_xlabel(
        r"Entropy $\left[\mathrm{\frac{kJ}{kg\,K}}\right]$",
        fontsize=plot_style["fonts"]["label"],
    )
    ax.set_ylabel(
        r"Temperature $\left[^\circ\mathrm{C}\right]$",
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


def plot_ts_diagram(
    plant,
    file_name=None,
    save_path=None,
    cycle_labels=None,
    colors=None,
    label_all_states=False,
):
    """
    Create and save a T-s diagram: one graph, or several graphs side by side.

    Parameters
    ----------
    plant : Network, str/Path, DataFrame, or list / list of lists of them
        What to plot. Each item is either a solved TESpy network or a state
        table (CSV path / DataFrame with columns "Connection", "T [degC]",
        "p [bar]", "s [kJ/kgK]", "h [kJ/kg]", "fluid", ...); plants and CSVs
        can be mixed.
        - one item: a single graph.
        - flat list ``[a, b]``: one graph with both cycles overlaid.
        - list of lists ``[[a, b], [c, d]]``: one graph per inner list, side
          by side from left to right, each with its own cycles overlaid and
          labelled (a), (b), ... (here a and b on the left graph, c and d on
          the right one). Each graph has its own axis limits.
    file_name : str, optional
        Base name for the saved file (will be saved as PNG)
    save_path : str or Path, optional
        Directory to save the figure. If None, the figure is not saved.
    cycle_labels : list of str, or list of lists of str, optional
        Legend labels (one legend per graph, upper left). A list of lists
        matches `plant` ([[la, lb], [lc, ld]]); a flat list with a list of
        lists is used for every graph.
    colors : list of str, optional
        One color per cycle in a graph. Default: PLOT_STYLE process color
        (red) for the first cycle, then blue, green, orange.
    label_all_states : bool
        False (default): only the state points of the last cycle of each
        graph are labeled (points shared by several cycles would otherwise be
        labeled twice). True: label the state points of every cycle.

    Returns
    -------
    fig, ax : matplotlib figure and axis (single graph), or figure and array
        of axes (several graphs)
    """

    plot_style = PLOT_STYLE

    # normalise the input to a list of panels, each a list of cycles
    if isinstance(plant, (list, tuple)):
        if not plant:
            raise ValueError("`plant` is empty.")
        if isinstance(plant[0], (list, tuple)):
            panels = [list(p) for p in plant]
        else:
            panels = [list(plant)]
    else:
        panels = [[plant]]
    n_panels = len(panels)

    # labels of each panel
    if cycle_labels is None:
        panel_labels = [None] * n_panels
    elif isinstance(cycle_labels[0], (list, tuple)):
        if len(cycle_labels) != n_panels:
            raise ValueError("`cycle_labels` must have one list per graph.")
        panel_labels = [list(lab) for lab in cycle_labels]
    else:
        panel_labels = [list(cycle_labels)] * n_panels

    w, h = plot_style["figure"]["figsize"]
    fig, axes = plt.subplots(
        1,
        n_panels,
        figsize=(w * n_panels, h),
        dpi=plot_style["figure"]["dpi"],
        squeeze=False,
    )
    axes = axes.ravel()

    for k, (ax, items, labels) in enumerate(zip(axes, panels, panel_labels)):
        _draw_ts_panel(ax, items, labels, colors, label_all_states)
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
            save_path / f"{file_name}_ts_diagram.png",
            dpi=plot_style["figure"]["dpi"],
            bbox_inches="tight",
            facecolor=plot_style["figure"]["facecolor"],
        )
        print(f"✓ Figure saved: {save_path / f'{file_name}_ts_diagram.png'}")

    if n_panels == 1:
        return fig, axes[0]
    return fig, axes
