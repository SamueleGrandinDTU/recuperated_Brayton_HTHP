"""Energy analysis post-processing.
===================================
This module provides functions to generate tables of performance and sizing parameters,
both in the command view and as .jpg files.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src import PLOT_STYLE


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

    # Style table borders and header
    for (row, _), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(weight="bold", fontsize=PLOT_STYLE["fonts"]["label"])
            cell.set_height(cell.get_height() * 2)
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


def generate_performance_parameters_table(
    plant, title_name=None, file_name=None, save_path=None
):
    """Generate a table of performance parameters and save it as a PNG image.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        Solved plant network.
    title_name : str, optional
        Title used for printed output and the saved table.
    file_name : str, optional
        Base file name used when saving the table (characterisitc extension is added).
    save_path : str or Path, optional
        Directory to save the table as PNG files.
        If None, nothing is saved to disk.

    Returns
    -------
    df_perf : pd.DataFrame
        Performance parameters table.
    """

    compressor = plant.comps.loc["compressor", "object"]
    turbine = plant.comps.loc["turbine", "object"]
    sink = plant.comps.loc["sink", "object"]

    m = plant.conns.loc["0", "object"].m.val

    specific_power_compressor = abs(compressor.P.val * 1000 / m)
    specific_power_turbine = abs(turbine.P.val * 1000 / m)
    specific_power_sink = abs(sink.Q.val * 1000 / m)

    cop = abs(sink.Q.val) / (compressor.P.val + turbine.P.val)

    # Table version
    label_w_cp_table = r"$\mathbf{w_{cp}}$" + "\n[kJ/kg]"
    label_w_tu_table = r"$\mathbf{w_{tu}}$" + "\n[kJ/kg]"
    label_q_sink_table = r"$\mathbf{\dot{q}_{Sink}}$" + "\n[kJ/kg]"
    label_cop_table = "COP\n[-]"

    df_perf_table = pd.DataFrame(
        [
            [
                "Parameter",
                label_w_cp_table,
                label_w_tu_table,
                label_q_sink_table,
                label_cop_table,
            ],
            [
                "Value",
                round(specific_power_compressor, 2),
                round(specific_power_turbine, 2),
                round(specific_power_sink, 2),
                round(cop, 2),
            ],
        ]
    )

    # Command view version
    label_w_cp = "w_cp [kJ/kg]"
    label_w_tu = "w_tu [kJ/kg]"
    label_q_sink = "q̇_Sink [kJ/kg]"
    label_cop = "COP [-]"

    df_perf = pd.DataFrame(
        [
            ["Parameter", label_w_cp, label_w_tu, label_q_sink, label_cop],
            [
                "Value",
                round(specific_power_compressor, 2),
                round(specific_power_turbine, 2),
                round(specific_power_sink, 2),
                round(cop, 2),
            ],
        ]
    )

    print(f"\n{'='*100}")
    print("SPECIFIC POWER VALUES (kJ/kg) AND COP")
    print(f"{'='*100}")
    print(df_perf.to_string(index=False, header=False))
    print(f"{'='*100}")

    if save_path is not None:
        if file_name is None:
            raise ValueError("file_name is required when save_path is given.")
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
    """Generate a table of sizing parameters and save it as a PNG image.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        Solved plant network.
    title_name : str, optional
        Title used for printed output and the saved table.
    file_name : str, optional
        Base file name used when saving the table (characteristic extension is added).
    save_path : str or Path, optional
        Directory to save the table as PNG files.
        If None, nothing is saved to disk.

    Returns
    -------
    df_sizing : pd.DataFrame
        Sizing parameters table.
    """

    sink = plant.comps.loc["sink", "object"]
    recuperator = plant.comps.loc["recuperator", "object"]
    compressor = plant.comps.loc["compressor", "object"]
    turbine = plant.comps.loc["turbine", "object"]

    eff_sink = round(sink.eff_max.val, 2)
    kA_sink = round(sink.kA.val / 1000, 1)
    td_log_sink = round(sink.td_log.val, 1)

    eff_recup = round(recuperator.eff_max.val, 2)
    kA_recup = round(recuperator.kA.val / 1000, 1)
    td_log_recup = round(recuperator.td_log.val, 1)

    pr_compressor = round(compressor.pr.val, 2)
    v_compressor = round(compressor.inl[0].v.val, 2)

    pr_turbine = round(turbine.pr.val, 2)
    v_turbine = round(turbine.inl[0].v.val, 2)

    # Table version
    header_table = [
        "Component",
        r"$\mathbf{\varepsilon}$" + "\n[-]",
        r"$\mathbf{UA}$" + "\n[kW/K]",
        r"$\mathbf{\Delta T_{LMTD}}$" + "\n[K]",
        "Component",
        r"$\mathbf{pr}$" + "\n[-]",
        r"$\mathbf{\dot{V}}$" + "\n[m³/s]",
    ]

    rows = [
        [
            "Sink",
            eff_sink,
            kA_sink,
            td_log_sink,
            "Compressor",
            pr_compressor,
            v_compressor,
        ],
        [
            "Recuperator",
            eff_recup,
            kA_recup,
            td_log_recup,
            "Turbine",
            pr_turbine,
            v_turbine,
        ],
    ]

    df_sizing_table = pd.DataFrame([header_table] + rows)

    # Command view version
    header = [
        "Component",
        "ε [-]",
        "UA [kW/K]",
        "ΔT_LMTD [K]",
        "Component",
        "pr [-]",
        "V̇ [m³/s]",
    ]

    df_sizing = pd.DataFrame([header] + rows)

    print(f"\n{'='*100}")
    print("SIZING PARAMETERS")
    print(f"{'='*100}")
    print(df_sizing.to_string(index=False, header=False))
    print(f"{'='*100}")

    if save_path is not None:
        if file_name is None:
            raise ValueError("file_name is required when save_path is given.")
        save_table_as_png(
            df_sizing_table,
            f"{title_name} - Sizing Parameters",
            save_path,
            f"{file_name}_sizing_parameters",
        )

    return df_sizing
