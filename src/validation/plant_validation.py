"""
Plant Validation Module
=======================
Compare a solved TESpy plant against reference cycle-point data (temperature
and entropy), both as a temperature comparison table and as a T-s diagram
computed for both the simulated and the reference cycle.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from CoolProp.CoolProp import PropsSI
from fluprodia import FluidPropertyDiagram
from tespy.components import HeatExchanger
from tespy.components.turbomachinery.base import Turbomachine

from src import PLOT_STYLE

# --- Temperature comparison table -------------------------------------------


def extract_plant_temperatures(plant):
    """Extract temperature data from a solved TESpy plant.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        Solved plant network.

    Returns
    -------
    pd.DataFrame
        Columns: ``Point``, ``T [°C]``, ``T [K]``.
    """
    data = [
        {
            "Point": str(conn.label),
            "T [°C]": round(conn.T.val, 1),
            "T [K]": round(conn.T.val + 273.15, 2),
        }
        for conn in plant.conns["object"]
    ]
    return pd.DataFrame(data)


def read_reference_data(csv_path):
    """Read reference cycle-point data (temperature and entropy) from CSV.

    Parameters
    ----------
    csv_path : str or Path
        Path to reference CSV with columns for connection label,
        T [°C], and s [kJ/kgK].

    Returns
    -------
    pd.DataFrame
        Columns: ``Point``, ``T [°C]``, ``T [K]``, ``s [kJ/kgK]``.
    """
    df = pd.read_csv(csv_path)
    point_col = [
        c for c in df.columns if "connection" in c.lower() or "point" in c.lower()
    ][0]
    temp_col = [c for c in df.columns if "t [" in c.lower()][0]
    entropy_col = [c for c in df.columns if "s [" in c.lower()][0]

    df = df.rename(
        columns={point_col: "Point", temp_col: "T [°C]", entropy_col: "s [kJ/kgK]"}
    )
    df["Point"] = df["Point"].astype(str).str.strip()
    df["T [K]"] = df["T [°C]"] + 273.15

    return df[["Point", "T [°C]", "T [K]", "s [kJ/kgK]"]]


def compare_temperatures(plant, reference_csv):
    """Build a temperature comparison table between a solved plant and
    reference data.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        Solved plant network.
    reference_csv : str or Path
        Path to the reference CSV file (see ``read_reference_data``).

    Returns
    -------
    pd.DataFrame
        Columns: ``Point``, ``Reference T [K]``, ``Computed T [K]``,
        ``ΔT [K]``, ``Deviation [%]``.
    """
    df_plant = extract_plant_temperatures(plant)
    df_reference = read_reference_data(reference_csv)

    df_comp = pd.DataFrame()
    df_comp["Point"] = df_reference["Point"]
    df_comp["Reference T [K]"] = df_reference["T [K]"].values

    computed_temps = []
    for point_label in df_reference["Point"]:
        plant_row = df_plant[df_plant["Point"] == point_label]
        computed_temps.append(
            plant_row["T [K]"].values[0] if not plant_row.empty else np.nan
        )

    df_comp["Computed T [K]"] = computed_temps
    df_comp["ΔT [K]"] = df_comp["Computed T [K]"] - df_comp["Reference T [K]"]
    df_comp["Deviation [%]"] = (df_comp["ΔT [K]"] / df_comp["Reference T [K]"]) * 100

    return df_comp.round(2)


def save_table_as_png(df, title, save_path, file_name):
    """Save a comparison table as a PNG image.

    Parameters
    ----------
    df : pd.DataFrame
        Table to render.
    title : str
        Table title.
    save_path : str or Path
        Directory to save the figure into.
    file_name : str
        Output file name, without extension.
    """
    table_style = PLOT_STYLE["table"]

    fig, ax = plt.subplots(
        figsize=(
            table_style["fig_width"],
            max(
                table_style["min_fig_height"],
                len(df) * table_style["row_height"],
            ),
        )
    )

    fig.patch.set_facecolor(PLOT_STYLE["figure"]["facecolor"])
    ax.set_facecolor(PLOT_STYLE["axes"]["facecolor"])

    ax.axis("tight")
    ax.axis("off")

    table = ax.table(
        cellText=df.values, colLabels=df.columns, cellLoc="center", loc="center"
    )
    table.auto_set_font_size(False)
    table.set_fontsize(PLOT_STYLE["fonts"]["value"])
    table.scale(
        table_style["scale_x"],
        table_style["scale_y"],
    )

    # Style table borders and header
    for (row, _), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(weight="bold", fontsize=PLOT_STYLE["fonts"]["label"])
        cell.set_edgecolor(PLOT_STYLE["colors"]["edge"])
        cell.set_linewidth(PLOT_STYLE["lines_and_markers"]["linewidth"])

    ax.set_title(
        title,
        fontsize=PLOT_STYLE["fonts"]["title"],
        pad=table_style["title_pad"],
        fontweight="bold",
    )

    plt.tight_layout()

    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        save_path / f"{file_name}_temperature_comparison.png",
        dpi=PLOT_STYLE["figure"]["dpi"],
        bbox_inches="tight",
        facecolor=PLOT_STYLE["figure"]["facecolor"],
    )
    plt.close(fig)

    print(f"✓ Table saved: {save_path / f'{file_name}_temperature_comparison.png'}")


# --- T-s diagram: computed vs. reference cycle ------------------------------


def _reference_plotting_data(plant, ref_states, fluid="air"):
    """Build FluProDia plotting data for the reference cycle, computed
    entirely from the reference temperature and entropy at each point.

    The plant is only used for topology and component type: which point
    connects to which, and whether that component's process is traced
    via entropy (turbomachinery) or pressure (heat exchangers).

    Parameters
    ----------
    plant : tespy.networks.network.Network
        Solved plant network (used for topology/component type/fluid only).
    ref_states : dict
        Mapping of point label (str) to {"T": T[°C], "s": s[kJ/kgK]}.

    Returns
    -------
    dict
        Mapping of inlet point label to FluProDia plotting data, in the
        same format as ``get_plotting_data``.
    """
    fluid_by_label = {}
    for conn in plant.conns["object"]:
        fluid_val = conn.fluid.val
        if fluid_val:
            fluid_by_label[str(conn.label)] = max(fluid_val, key=fluid_val.get)

    # Pre-compute p and vol for every reference point from (T, s, fluid)
    props = {}
    for label, state in ref_states.items():
        fluid = fluid_by_label.get(label)
        if fluid is None:
            continue

        T_K = state["T"] + 273.15
        s_SI = state["s"] * 1000  # kJ/kgK -> J/kgK
        p_SI = PropsSI("P", "T", T_K, "S", s_SI, fluid)
        vol = 1 / PropsSI("D", "T", T_K, "S", s_SI, fluid)
        props[label] = {"s": state["s"], "p": p_SI / 1e5, "vol": vol}  # p in bar

    reference_dict = {}

    for comp in plant.comps["object"]:
        inlet_labels = [str(c.label) for c in comp.inl]
        outlet_labels = [str(c.label) for c in comp.outl]

        if isinstance(comp, Turbomachine):
            in_lbl, out_lbl = inlet_labels[0], outlet_labels[0]
            if in_lbl in props and out_lbl in props:
                reference_dict[in_lbl] = {
                    "isoline_property": "s",
                    "isoline_value": props[in_lbl]["s"],
                    "isoline_value_end": props[out_lbl]["s"],
                    "starting_point_property": "vol",
                    "starting_point_value": props[in_lbl]["vol"],
                    "ending_point_property": "vol",
                    "ending_point_value": props[out_lbl]["vol"],
                }

        elif isinstance(comp, HeatExchanger):
            for i in range(2):
                in_lbl, out_lbl = inlet_labels[i], outlet_labels[i]
                if in_lbl in props and out_lbl in props:
                    reference_dict[in_lbl] = {
                        "isoline_property": "p",
                        "isoline_value": props[in_lbl]["p"],
                        "isoline_value_end": props[out_lbl]["p"],
                        "starting_point_property": "vol",
                        "starting_point_value": props[in_lbl]["vol"],
                        "ending_point_property": "vol",
                        "ending_point_value": props[out_lbl]["vol"],
                    }

    return reference_dict


def plot_ts_diagram(
    plant, reference_csv, file_name=None, save_path=None, plot_style=None
):
    """
    Create and save a T-s diagram for a single TESpy plant and
    overlays it with a reference cycle read from a CSV file.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        The solved TESpy plant network to plot

    reference_csv : str or Path
        Path to a reference CSV with columns for connection label,
        T [°C], and s [kJ/kgK]. The reference cycle is plotted
        in blue alongside the computed cycle (red).
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

    # --- Reference cycle: built entirely from reference T/s -----------------
    reference_dict = {}

    if reference_csv is not None:
        df_ref = read_reference_data(reference_csv)
        ref_states = {
            row["Point"]: {"T": row["T [°C]"], "s": row["s [kJ/kgK]"]}
            for _, row in df_ref.iterrows()
        }

        reference_dict = _reference_plotting_data(plant, ref_states)

        for key, data in reference_dict.items():
            reference_dict[key]["datapoints"] = diagram.calc_individual_isoline(**data)

    # Extract all s and T values (both cycles) to determine axis limits
    temp_states = {}
    for key in result_dict.keys():
        datapoints = result_dict[key]["datapoints"]
        temp_states[key] = {"s": datapoints["s"][0], "T": datapoints["T"][0]}
        temp_states[f"{key}_outlet"] = {
            "s": datapoints["s"][-1],
            "T": datapoints["T"][-1],
        }
    for key in reference_dict.keys():
        datapoints = reference_dict[key]["datapoints"]
        temp_states[f"ref_{key}"] = {"s": datapoints["s"][0], "T": datapoints["T"][0]}
        temp_states[f"ref_{key}_outlet"] = {
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
            label="Computed" if key == list(result_dict.keys())[0] else None,
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

    # Plot T-s curves for the reference cycle (blue)
    first_ref_curve = True
    for key in reference_dict.keys():
        datapoints = reference_dict[key]["datapoints"]

        ax.plot(
            datapoints["s"],
            datapoints["T"],
            color=plot_style["colors"]["reference"],
            linewidth=plot_style["lines_and_markers"]["linewidth"],
            label="Reference" if first_ref_curve else None,
        )
        ax.scatter(
            [datapoints["s"][0], datapoints["s"][-1]],
            [datapoints["T"][0], datapoints["T"][-1]],
            color=plot_style["colors"]["reference"],
            s=plot_style["lines_and_markers"]["point_size"],
            zorder=5,
        )
        first_ref_curve = False

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

    if reference_csv is not None:
        ax.legend(loc="best", fontsize=plot_style["fonts"]["legend"])

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


# --- Combined validation workflow -------------------------------------------


def validate_plant(
    plant,
    reference_csv,
    title_name=None,
    file_name=None,
    save_path=None,
):
    """Validate a solved plant against reference data: a temperature
    comparison table and a T-s diagram comparing the computed and
    reference cycles.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        Solved plant network.
    reference_csv : str or Path
        Path to the reference CSV file, with columns for connection
        label, temperature [°C], and entropy [kJ/(kg K)].
    title_name : str, optional
        Title used for printed output and the saved table.
    file_name : str, optional
        Base file name used when saving the table and T-s diagram.
    save_path : str or Path, optional
        Directory to save the table and T-s diagram as PNG files.
        If None, nothing is saved to disk.

    Returns
    -------
    df_comp : pd.DataFrame
        Temperature comparison table.
    fig : matplotlib.figure.Figure
        T-s diagram comparing the computed and reference cycles.
    """
    print(f"\n{'='*100}")
    print(f"  PLANT VALIDATION: {title_name}".upper())
    print(f"{'='*100}\n")

    df_comp = compare_temperatures(plant, reference_csv)
    print("Temperature Comparison\n")
    print(df_comp.to_string(index=False))
    print("\n")

    if save_path is not None:
        if file_name is None:
            raise ValueError("file_name is required when save_path is given.")
        save_table_as_png(
            df_comp, f"{title_name} - Temperature Comparison", save_path, file_name
        )

    fig, _ = plot_ts_diagram(
        plant,
        file_name=file_name,
        reference_csv=reference_csv,
        save_path=save_path,
    )

    return df_comp, fig
