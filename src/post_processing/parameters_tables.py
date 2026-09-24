"""Energy analysis post-processing.
===================================
This module provides functions to generate tables of performance and sizing parameters,
in the command view, as .csv files, and (when a title is given) as .png files.

Both generate_* functions discover components dynamically (by TESpy component
type) rather than assuming fixed labels, so they work for a plant with a
single compressor/turbine/sink as well as one with several compressors,
turbines and heat exchangers (e.g. an intercooled or TES-integrated layout).
"""

import unicodedata
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src import PLOT_STYLE


def _visual_width(value):
    """Display width of `value`, ignoring zero-width combining marks.

    Labels such as "q̇_Sink" or "V̇" are built from a base letter plus a
    combining dot-above accent: two Unicode code points that render as a
    single glyph in a terminal or CSV viewer, but count as length 2 under
    plain len(). Padding by len() (what pandas' to_string does) therefore
    drifts out of alignment as soon as one of these accented labels appears.
    Counting only non-combining characters gives the width as it actually
    displays.
    """
    text = str(value)
    return sum(1 for ch in text if not unicodedata.combining(ch))


def _print_aligned_table(df):
    """Print a header-less DataFrame with columns right-aligned by visual
    width, so dot-accented labels (q̇, V̇) line up correctly with the rest
    of the table even though df.to_string() would misalign them.
    """
    rows = df.values.tolist()
    if not rows:
        return
    n_cols = len(rows[0])
    col_widths = [max(_visual_width(row[i]) for row in rows) for i in range(n_cols)]
    for row in rows:
        cells = []
        for i, value in enumerate(row):
            text = str(value)
            pad = col_widths[i] - _visual_width(text)
            cells.append(" " * pad + text)
        print("  ".join(cells))


def save_table_as_csv(df, save_path, file_name):
    """Save a table as a CSV file.

    Parameters
    ----------
    df : pd.DataFrame
        Table to save, in the same row/column layout used for the console view.
    save_path : str or Path
        Directory to save the file into.
    file_name : str
        Output file name, without extension.
    """
    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)
    csv_path = save_path / f"{file_name}.csv"
    df.to_csv(csv_path, index=False, header=False)
    print(f"✓ Table saved: {csv_path}")
    return df


def save_table_as_png(df, title, save_path, file_name):
    """Save a table as a PNG image.

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

    table = ax.table(cellText=df.values, cellLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(PLOT_STYLE["fonts"]["value"])
    table.scale(
        table_style["scale_x"],
        table_style["scale_y"],
    )

    # Style table borders and header. Growing the header row's height alone
    # does not move the rows below it (each cell keeps the fixed y-position
    # it was given when the table was built), so every other row is shifted
    # down by the same amount the header grows to keep the grid continuous.
    header_cell = table[0, 0]
    original_header_height = header_cell.get_height()
    new_header_height = original_header_height * 2
    height_delta = new_header_height - original_header_height

    for (row, _), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(weight="bold", fontsize=PLOT_STYLE["fonts"]["label"])
            cell.set_height(new_header_height)
        else:
            cell.set_y(cell.get_y() - height_delta)
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
        save_path / f"{file_name}.png",
        dpi=PLOT_STYLE["figure"]["dpi"],
        bbox_inches="tight",
        facecolor=PLOT_STYLE["figure"]["facecolor"],
    )
    plt.close(fig)

    print(f"✓ Table saved: {save_path / f'{file_name}.png'}")
    return df


def _get_components_by_type(plant):
    """Split the plant's components into compressors, turbines and heat
    exchangers, and identify the "interface hx" component if present.

    Returns
    -------
    compressors, turbines, heat_exchangers : lists of components
    interface_hx : component or None
    """
    compressors = []
    turbines = []
    heat_exchangers = []
    interface_hx = None

    for comp in plant.comps["object"]:
        comp_type = comp.__class__.__name__
        if comp_type == "Compressor":
            compressors.append(comp)
        elif comp_type == "Turbine":
            turbines.append(comp)
        elif comp_type == "HeatExchanger":
            heat_exchangers.append(comp)
            if "interface hx" in str(comp.label).lower():
                interface_hx = comp

    return compressors, turbines, heat_exchangers, interface_hx


def generate_performance_parameters_table(
    plant, title_name=None, file_name=None, save_path=None
):
    """Generate a table of performance parameters.

    Specific power [kJ/kg] is computed for every compressor, turbine and heat
    exchanger present in the plant (normalized by the mass flow of connection
    "0"). The COP's useful heat is taken from the "interface hx" component
    when present; otherwise it is the sum of the heat duty of every heat
    exchanger labeled "sink" (covering "sink", "sink 1", "sink 2", etc.). The
    COP's net power is the sum of every compressor's and turbine's power.

    The table is always saved as a CSV when save_path is given. It is also
    saved as a PNG image, but only when title_name is given.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        Solved plant network.
    title_name : str, optional
        Title used for the saved PNG table. If None, no PNG is generated.
    file_name : str, optional
        Base file name used when saving the table (characterisitc extension is added).
    save_path : str or Path, optional
        Directory to save the table as CSV / PNG files.
        If None, nothing is saved to disk.

    Returns
    -------
    df_perf : pd.DataFrame
        Performance parameters table.
    """

    compressors, turbines, heat_exchangers, interface_hx = _get_components_by_type(
        plant
    )

    m = plant.conns.loc["0", "object"].m.val

    if interface_hx is not None:
        useful_heat = abs(interface_hx.Q.val)
    else:
        sink_hxs = [hx for hx in heat_exchangers if "sink" in str(hx.label).lower()]
        useful_heat = sum(abs(hx.Q.val) for hx in sink_hxs)

    net_power = sum(c.P.val for c in compressors) + sum(t.P.val for t in turbines)
    cop = useful_heat / net_power

    labels_table = ["Parameter"]
    labels_plain = ["Parameter"]
    values = ["Value"]

    for comp in compressors + turbines:
        specific_power = abs(comp.P.val * 1000 / m)
        labels_table.append(
            rf"$\mathbf{{w_{{\mathrm{{{comp.label}}}}}}}$" + "\n[kJ/kg]"
        )
        labels_plain.append(f"w_{comp.label} [kJ/kg]")
        values.append(round(specific_power, 2))

    for hx in heat_exchangers:
        specific_heat = abs(hx.Q.val * 1000 / m)
        labels_table.append(
            rf"$\mathbf{{\dot{{q}}_{{\mathrm{{{hx.label}}}}}}}$" + "\n[kJ/kg]"
        )
        labels_plain.append(f"q_{hx.label} [kJ/kg]")
        values.append(round(specific_heat, 2))

    labels_table.append("COP\n[-]")
    labels_plain.append("COP [-]")
    values.append(round(cop, 2))

    df_perf_table = pd.DataFrame([labels_table, values])
    df_perf = pd.DataFrame([labels_plain, values])

    print(f"\n{'='*100}")
    print("SPECIFIC POWER VALUES (kJ/kg) AND COP")
    print(f"{'='*100}")
    _print_aligned_table(df_perf)
    print(f"{'='*100}")

    if save_path is not None:
        if file_name is None:
            raise ValueError("file_name is required when save_path is given.")

        save_table_as_csv(df_perf, save_path, f"{file_name}_performance_parameters")

        if title_name is not None:
            save_table_as_png(
                df_perf_table,
                f"{title_name} - Performance Parameters",
                save_path,
                f"{file_name}_performance_parameters",
            )

    return df_perf


def generate_sizing_parameters_table(
    plant, title_name=None, file_name=None, save_path=None
):
    """Generate a table of sizing parameters.

    A row is generated for every heat exchanger (ε, UA, ΔT_LMTD) and every
    compressor/turbine (pr, V̇) in the plant; columns that don't apply to a
    given component's type are filled with "-".

    The table is always saved as a CSV when save_path is given. It is also
    saved as a PNG image, but only when title_name is given.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        Solved plant network.
    title_name : str, optional
        Title used for the saved PNG table. If None, no PNG is generated.
    file_name : str, optional
        Base file name used when saving the table (characteristic extension is added).
    save_path : str or Path, optional
        Directory to save the table as CSV / PNG files.
        If None, nothing is saved to disk.

    Returns
    -------
    df_sizing : pd.DataFrame
        Sizing parameters table.
    """

    compressors, turbines, heat_exchangers, _ = _get_components_by_type(plant)

    header_table = [
        "Component",
        r"$\mathbf{\varepsilon}$" + "\n[-]",
        r"$\mathbf{UA}$" + "\n[kW/K]",
        r"$\mathbf{\Delta T_{LMTD}}$" + "\n[K]",
        r"$\mathbf{pr}$" + "\n[-]",
        r"$\mathbf{\dot{V}}$" + "\n[m³/s]",
    ]
    header_plain = [
        "Component",
        "eff [-]",
        "UA [kW/K]",
        "DT_LMTD [K]",
        "pr [-]",
        "VV [m^3/s]",
    ]

    rows = []

    for hx in heat_exchangers:
        eff = round(hx.eff_max.val, 2)
        kA = round(hx.kA.val / 1000, 1)
        td_log = round(hx.td_log.val, 1)
        rows.append([hx.label, eff, kA, td_log, "-", "-"])

    for comp in compressors + turbines:
        pr = round(comp.pr.val, 2)
        v = round(comp.inl[0].v.val, 2)
        rows.append([comp.label, "-", "-", "-", pr, v])

    df_sizing_table = pd.DataFrame([header_table] + rows)
    df_sizing = pd.DataFrame([header_plain] + rows)

    print(f"\n{'='*100}")
    print("SIZING PARAMETERS")
    print(f"{'='*100}")
    _print_aligned_table(df_sizing)
    print(f"{'='*100}")

    if save_path is not None:
        if file_name is None:
            raise ValueError("file_name is required when save_path is given.")

        save_table_as_csv(df_sizing, save_path, f"{file_name}_sizing_parameters")

        if title_name is not None:
            save_table_as_png(
                df_sizing_table,
                f"{title_name} - Sizing Parameters",
                save_path,
                f"{file_name}_sizing_parameters",
            )

    return df_sizing


def _get_connection_fluid(conn):
    """Return a connection's dominant fluid name (highest mass fraction), or
    "-" if the connection has no fluid composition set.
    """
    fluid_val = conn.fluid.val
    if not fluid_val:
        return "-"
    return max(fluid_val, key=fluid_val.get)


def generate_connections_table(plant, title_name=None, file_name=None, save_path=None):
    """Generate a table of connection state properties.

    One row is generated per connection with a defined state (temperature,
    pressure, entropy, enthalpy and mass flow all set); connections that
    haven't been solved are skipped.

    The table is always saved as a CSV when save_path is given. It is also
    saved as a PNG image, but only when title_name is given.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        Solved plant network.
    title_name : str, optional
        Title used for the saved PNG table. If None, no PNG is generated.
    file_name : str, optional
        Base file name used when saving the table (characteristic extension
        is added).
    save_path : str or Path, optional
        Directory to save the table as CSV / PNG files.
        If None, nothing is saved to disk.

    Returns
    -------
    df_connections : pd.DataFrame
        Connection state properties table.
    """

    header = [
        "Connection",
        "T [degC]",
        "p [bar]",
        "s [kJ/kgK]",
        "h [kJ/kg]",
        "m [kg/s]",
        "fluid",
    ]

    rows = []

    for conn in plant.conns["object"]:
        if (
            conn.T.val is None
            or conn.p.val is None
            or conn.s.val is None
            or conn.h.val is None
            or conn.m.val is None
        ):
            continue

        rows.append(
            [
                conn.label,
                round(conn.T.val, 1),
                round(conn.p.val, 2),
                round(conn.s.val, 3),
                round(conn.h.val, 2),
                round(conn.m.val, 3),
                _get_connection_fluid(conn),
            ]
        )

    df_connections = pd.DataFrame([header] + rows)

    print(f"\n{'='*100}")
    print("CONNECTION STATE PROPERTIES")
    print(f"{'='*100}")
    _print_aligned_table(df_connections)
    print(f"{'='*100}")

    if save_path is not None:
        if file_name is None:
            raise ValueError("file_name is required when save_path is given.")

        save_table_as_csv(df_connections, save_path, f"{file_name}_connections")

        if title_name is not None:
            save_table_as_png(
                df_connections,
                f"{title_name} - Connection Properties",
                save_path,
                f"{file_name}_connections",
            )

    return df_connections
