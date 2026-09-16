"""
T-s Diagram Plotting Module
============================
Creates T-s diagrams for thermodynamic cycles.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from fluprodia import FluidPropertyDiagram

from src import PLOT_STYLE


def plot_ts_diagram(plant, file_name=None, save_path=None):
    """
    Create and save a T-s diagram for a single TESpy plant.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        The solved TESpy plant network to plot

    file_name : str, optional
        Base name for the saved file (will be saved as PNG)
    save_path : str or Path, optional
        Directory to save the figure. If None, the figure is not saved.
    plot_style : dict, optional
        Style dictionary controlling colors, sizes, fonts, etc.
        Defaults to PLOT_STYLE.

    Returns
    -------
    fig, ax : matplotlib figure and axis objects
    """

    plot_style = PLOT_STYLE

    fig, ax = plt.subplots(
        1, 1, figsize=plot_style["figure"]["figsize"], dpi=plot_style["figure"]["dpi"]
    )

    # Initialize the diagram
    diagram = FluidPropertyDiagram("air")
    diagram.set_unit_system(T="°C", p="bar", h="kJ/kg", s="kJ/kgK")

    # Extract plotting data from all components (computed cycle)
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

    # Extract all s and T values (both cycles) to determine axis limits
    temp_states = {}
    for key in result_dict.keys():
        datapoints = result_dict[key]["datapoints"]
        temp_states[key] = {"s": datapoints["s"][0], "T": datapoints["T"][0]}
        temp_states[f"{key}_outlet"] = {
            "s": datapoints["s"][-1],
            "T": datapoints["T"][-1],
        }

    all_s = [state["s"] for state in temp_states.values()]
    all_T = [state["T"] for state in temp_states.values()]

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

    plotted_states = {}

    # Plot T-s curves for each component (computed cycle, red)
    for key in result_dict.keys():
        datapoints = result_dict[key]["datapoints"]

        ax.plot(
            datapoints["s"],
            datapoints["T"],
            color=plot_style["colors"]["process"],
            linewidth=plot_style["lines_and_markers"]["linewidth"],
        )

        inlet_s = datapoints["s"][0]
        inlet_T = datapoints["T"][0]
        ax.scatter(
            inlet_s,
            inlet_T,
            color=plot_style["colors"]["process"],
            s=plot_style["lines_and_markers"]["point_size"],
            zorder=5,
        )
        plotted_states[key] = {"s": inlet_s, "T": inlet_T}

        outlet_s = datapoints["s"][-1]
        outlet_T = datapoints["T"][-1]
        ax.scatter(
            outlet_s,
            outlet_T,
            color=plot_style["colors"]["process"],
            s=plot_style["lines_and_markers"]["point_size"],
            zorder=5,
        )

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
                                plotted_states[outlet_conn.label] = {
                                    "s": outlet_s,
                                    "T": outlet_T,
                                }
                            break

    # Add state point labels (computed cycle only)
    custom_mults = plot_style.get("directional_labels", {})

    for conn_label, state in plotted_states.items():
        lbl_str = str(conn_label)

        if lbl_str in custom_mults:
            offset_x, offset_y = custom_mults[lbl_str]
        else:
            offset_x = plot_style["layout"]["label_x_offset"]
            offset_y = plot_style["layout"]["label_y_offset"]

        ha_val = "right" if offset_x < 0 else ("left" if offset_x > 0 else "center")
        va_val = "top" if offset_y < 0 else ("bottom" if offset_y > 0 else "center")

        ax.text(
            state["s"] + offset_x,
            state["T"] + offset_y,
            conn_label,
            fontsize=plot_style["fonts"]["value"],
            color=plot_style["colors"]["label"],
            ha=ha_val,
            va=va_val,
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

    fig.patch.set_facecolor(plot_style["figure"]["facecolor"])

    if save_path is not None:
        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            save_path / f"{file_name}_ts_diagram.png",
            dpi=plot_style["figure"]["dpi"],
            bbox_inches="tight",
            facecolor=plot_style["figure"]["facecolor"],
        )
        print(f"✓ Figure saved: {save_path / f'{file_name}_ts_diagram.png'}")
        if file_name is None:
            raise ValueError("file_name is required when save_path is given.")

    return fig, ax
