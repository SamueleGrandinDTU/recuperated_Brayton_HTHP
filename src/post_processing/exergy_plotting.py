"""Exergy plotting, comparable across one or several cycles."""

import math
import re
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from src import PLOT_STYLE

# Component colors and stacking order (bottom to top) come from
# PLOT_STYLE["component_colors"] ({lower-case component name: color}); the
# match against the component names of the tables is case-insensitive.
_COMPONENT_COLORS = PLOT_STYLE["component_colors"]
_COMPONENT_ORDER = list(_COMPONENT_COLORS)
_UNKNOWN_COMPONENT_COLOR = "#7f7f7f"  # grey, for a component not in the scheme

# Legend of the exergy plots: font size shared by both plots, and the gap
# (axes coordinates) between the x-axis label and the legend below it.
_LEGEND_FONTSIZE = PLOT_STYLE["fonts"]["label"]
_LEGEND_PAD = 0.02

# Display names of the components (PLOT_STYLE["component_names"], e.g.
# "sink 2" -> "HX2"): only what is written on the plots changes, the names
# used inside the plants and in the CSV tables stay as they are. Keys are
# matched case-insensitively; a name not in the mapping is shown as it is.
_COMPONENT_NAMES = {k.lower(): v for k, v in PLOT_STYLE["component_names"].items()}


def _display_name(name):
    """Display name of a component (see _COMPONENT_NAMES)."""
    return _COMPONENT_NAMES.get(str(name).strip().lower(), name)


def _set_legend_spec(ax, handles, labels, ncol):
    """Remember what the legend of `ax` shows; _place_legends draws it."""
    ax._legend_spec = (handles, labels, ncol)


def _place_legends(axes):
    """Draw the legend of every axes in `axes` just below the lowest x-axis
    label among them, so the legends are aligned with each other and as close
    as possible to the labels (call after the axes are fully styled)."""
    fig = axes[0].figure
    fig.canvas.draw()  # the size of the labels is only known once drawn
    renderer = fig.canvas.get_renderer()
    y_pixels = min(ax.xaxis.label.get_window_extent(renderer).y0 for ax in axes)

    for ax in axes:
        handles, labels, ncol = ax._legend_spec
        y = ax.transAxes.inverted().transform((0, y_pixels))[1]
        ax.legend(
            handles,
            labels,
            fontsize=_LEGEND_FONTSIZE,
            framealpha=0.95,
            loc="upper center",
            bbox_to_anchor=(0.5, y - _LEGEND_PAD),
            ncol=ncol,
        )


# Colors of the four cycles for plot_exergetic_efficiencies (where color
# encodes the cycle rather than the component): PLOT_STYLE["cycle_colors"],
# dark for standalone and light for TES-integrated, blue for base and
# red / orange for intercooled.
_CYCLE_COLORS = PLOT_STYLE["cycle_colors"]
# Short cycle label -> key of cycle_colors, e.g. {"S-BR": "standalone_base"}
_CYCLE_LABEL_KEYS = PLOT_STYLE["cycle_label_keys"]


def _assign_cycle_colors(cycle_labels):
    """One color per cycle label, from PLOT_STYLE["cycle_colors"].

    The key is built from the label: "tes" in it -> TES-integrated, otherwise
    standalone; "interc" in it -> intercooled, otherwise base. A label that
    maps to no key (or a repeated one) falls back to tab10.
    """
    extra_cmap = plt.cm.tab10
    extra_idx = 0
    colors = []

    for label in cycle_labels:
        text = str(label).lower()
        # the short labels (S-BR, S-IR, TES-BR, TES-IR) are looked up directly;
        # long labels are recognised from their text
        key = _CYCLE_LABEL_KEYS.get(str(label).strip())
        if key is None:
            key = ("tes" if "tes" in text else "standalone") + (
                "_intercooled" if "interc" in text else "_base"
            )
        if key in _CYCLE_COLORS and _CYCLE_COLORS[key] not in colors:
            colors.append(_CYCLE_COLORS[key])
        else:
            colors.append(extra_cmap(extra_idx % 10))
            extra_idx += 1

    return colors


_CYCLE_LABEL = "S-BR"
_WRAP_WIDTH = 14

# Component labels used for a cycle-level summary row (e.g. the "cycle" row
# appended by get_exergy_analysis's CSV export): excluded from the stacked
# bars, since it duplicates the sum of the real component rows rather than
# being an additional component.
_SUMMARY_ROW_LABELS = {"cycle", "total"}


def _load_dataframe(item):
    """Accept either a DataFrame or a path to a CSV saved by
    get_exergy_analysis (or any table with a "Component" column) and return
    a DataFrame either way, with the cycle-level summary row removed.
    """
    df = pd.read_csv(item) if isinstance(item, (str, Path)) else item

    if df is None or df.empty or "Component" not in df.columns:
        return df

    return df[~df["Component"].astype(str).str.lower().isin(_SUMMARY_ROW_LABELS)]


def _normalize_input(data):
    """Convert a single DataFrame/CSV path, or a list of them, into a list
    of DataFrames (loading any CSV paths, and dropping summary rows)."""
    if data is None:
        return None
    items = data if isinstance(data, list) else [data]
    return [_load_dataframe(item) for item in items]


def _resolve_cycle_labels(df_list, cycle_labels):
    if cycle_labels is None:
        cycle_labels = (
            [_CYCLE_LABEL]
            if len(df_list) == 1
            else [f"Cycle {i + 1}" for i in range(len(df_list))]
        )
    if len(cycle_labels) != len(df_list):
        raise ValueError(
            f"cycle_labels has {len(cycle_labels)} entries but "
            f"{len(df_list)} cycles were given."
        )
    return cycle_labels


def _ordered_components_present(df_list):
    """Components actually present, ordered per the fixed scheme; anything
    not in the scheme is appended (sorted)."""
    present = {comp for df in df_list for comp in df["Component"].values}
    present_lookup = {p.lower(): p for p in present}
    ordered_components = [
        present_lookup[c] for c in _COMPONENT_ORDER if c in present_lookup
    ]

    leftover = sorted(present - set(ordered_components))
    ordered_components += leftover

    return ordered_components


def _style_axes(ax):
    """Shared grid / spine / tick styling for the exergy plots."""
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


def _save_figure(fig, save_path, file_name, suffix, dpi=None):
    """Save `fig` as <save_path>/<file_name>_<suffix>.png (no-op if
    save_path is None)."""
    if save_path is None:
        return
    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)
    out = save_path / f"{file_name}_{suffix}.png"
    fig.savefig(
        out,
        dpi=dpi or PLOT_STYLE["figure"]["dpi"],
        bbox_inches="tight",
        facecolor=PLOT_STYLE["figure"]["facecolor"],
    )
    print(f"✓ Figure saved: {out}")


def _prepare(data, cycle_labels):
    """Load the data and resolve the labels; (None, None) if nothing to plot."""
    df_list = _normalize_input(data)
    if df_list is None or all(df.empty for df in df_list):
        print("Warning: No data provided")
        return None, None
    return df_list, _resolve_cycle_labels(df_list, cycle_labels)


# --------------------------------------------------------------------------
# Drawing functions: draw one plot on a given axes, no figure handling
# --------------------------------------------------------------------------


def _draw_exergy_destruction(ax, df_list, cycle_labels):
    """Stacked exergy destruction, one bar per cycle, on `ax`."""
    e_d_col = None
    for df in df_list:
        if not df.empty:
            e_d_col = [c for c in df.columns if "D" in c and "MW" in c][0]
            break

    ordered_components = _ordered_components_present(df_list)

    colors = {}
    for comp in ordered_components:
        key = comp.lower()
        if key in _COMPONENT_COLORS:
            colors[comp] = _COMPONENT_COLORS[key]
        else:
            print(
                f"Warning: no color for component '{comp}' in "
                f"PLOT_STYLE['component_colors'], using grey."
            )
            colors[comp] = _UNKNOWN_COMPONENT_COLOR

    wrapped_labels = [textwrap.fill(lbl, width=_WRAP_WIDTH) for lbl in cycle_labels]
    x = np.arange(len(df_list))

    bottoms = np.zeros(len(df_list))
    for comp in ordered_components:
        values = []
        for df in df_list:
            row = df[df["Component"] == comp]
            values.append(row[e_d_col].values[0] if not row.empty else 0.0)
        values = np.array(values)

        ax.bar(
            x,
            values,
            bottom=bottoms,
            width=0.6,
            label=_display_name(comp),
            color=colors[comp],
            edgecolor=PLOT_STYLE["colors"]["edge"],
            linewidth=PLOT_STYLE["lines_and_markers"]["linewidth"],
        )
        bottoms += values

    ax.set_ylabel(r"Exergy Destruction [MW]", fontsize=PLOT_STYLE["fonts"]["label"])
    ax.set_xlabel(r"Cycle", fontsize=PLOT_STYLE["fonts"]["label"])

    ax.set_xticks(x)
    ax.set_xticklabels(
        wrapped_labels,
        ha="center",
        rotation=0,
        fontsize=PLOT_STYLE["fonts"]["tick"],
    )
    ax.set_xlim(-0.75, len(df_list) - 1 + 0.75)

    # one legend entry per display name (e.g. "sink" and "sink 1" are both HX1)
    handles, labels = ax.get_legend_handles_labels()
    unique = {}
    for handle, label in zip(handles, labels):
        unique.setdefault(label, handle)

    _style_axes(ax)
    _set_legend_spec(
        ax, list(unique.values()), list(unique.keys()), ncol=min(len(unique), 4)
    )


def _draw_exergetic_efficiencies(ax, df_list, cycle_labels):
    """Grouped exergetic-efficiency bars (one group per component, one bar
    per cycle) on `ax`. Returns False if no efficiency column exists."""
    eff_col = None
    for df in df_list:
        if not df.empty:
            eff_col = [c for c in df.columns if "eff" in c.lower()][0]
            break

    if eff_col is None:
        print("Warning: No exergetic efficiency column found")
        return False

    ordered_components = _ordered_components_present(df_list)
    cycle_colors = _assign_cycle_colors(cycle_labels)

    # components with the same display name (e.g. "sink" and "sink 1", both
    # HX1) share one group of bars
    groups = {}
    for comp in ordered_components:
        groups.setdefault(_display_name(comp), []).append(comp)
    group_names = list(groups)

    n_components = len(group_names)
    n_cycles = len(df_list)
    group_width = 0.8
    bar_width = group_width / n_cycles

    family_keys = [re.sub(r"\s*\d+$", "", name).strip().lower() for name in group_names]
    family_gap = 0.6
    positions = [0.0]
    for k in range(1, n_components):
        step = 1.0 + (family_gap if family_keys[k] != family_keys[k - 1] else 0.0)
        positions.append(positions[-1] + step)
    x_groups = np.array(positions)

    for comp_idx, name in enumerate(group_names):
        present = []
        for i, df in enumerate(df_list):
            for comp in groups[name]:
                rows = df[df["Component"] == comp]
                if not rows.empty:
                    present.append((i, rows[eff_col].values[0]))
                    break
        if not present:
            continue

        n_present = len(present)
        for j, (i, value) in enumerate(present):
            offset = (j - (n_present - 1) / 2) * bar_width
            ax.bar(
                x_groups[comp_idx] + offset,
                value,
                width=bar_width,
                color=cycle_colors[i],
                edgecolor=PLOT_STYLE["colors"]["edge"],
                linewidth=PLOT_STYLE["lines_and_markers"]["linewidth"],
            )

    legend_handles = [
        mpatches.Patch(
            facecolor=cycle_colors[i],
            edgecolor=PLOT_STYLE["colors"]["edge"],
            label=cycle_labels[i],
        )
        for i in range(n_cycles)
    ]

    ax.set_ylabel(r"Exergy Efficiency [%]", fontsize=PLOT_STYLE["fonts"]["label"])
    ax.set_xlabel(r"Component", fontsize=PLOT_STYLE["fonts"]["label"])

    ax.set_xticks(x_groups)
    ax.set_xticklabels(
        group_names,
        ha="right",
        rotation=45,
        rotation_mode="anchor",
        fontsize=PLOT_STYLE["fonts"]["tick"],
    )
    ax.set_xlim(x_groups[0] - 0.5, x_groups[-1] + 0.5)

    _style_axes(ax)
    _set_legend_spec(
        ax,
        legend_handles,
        [h.get_label() for h in legend_handles],
        ncol=math.ceil(n_cycles / 2),
    )
    return True


# Registry: plot key -> (draw function, suffix of the saved file name)
_EXERGY_PLOTS = {
    "destruction": (_draw_exergy_destruction, "exergy_stacked"),
    "efficiencies": (_draw_exergetic_efficiencies, "exergetic_efficiencies"),
}


# --------------------------------------------------------------------------
# Public functions
# --------------------------------------------------------------------------


def plot_exergy_destruction_stacked(
    exergy_destruction, cycle_labels=None, save_path=None, file_name=None
):
    """Exergy destruction as one stacked bar per cycle (own figure).
    Same behaviour and output file as before; see _draw_exergy_destruction."""
    df_list, cycle_labels = _prepare(exergy_destruction, cycle_labels)
    if df_list is None:
        return None, None

    fig, ax = plt.subplots(
        figsize=PLOT_STYLE["figure"]["figsize"], dpi=PLOT_STYLE["figure"]["dpi"]
    )
    _draw_exergy_destruction(ax, df_list, cycle_labels)
    _place_legends([ax])
    fig.patch.set_facecolor(PLOT_STYLE["figure"]["facecolor"])
    _save_figure(fig, save_path, file_name, "exergy_stacked")
    return fig, ax


def plot_exergetic_efficiencies(
    exergy_destruction, cycle_labels=None, save_path=None, file_name=None
):
    """Grouped exergetic efficiencies per component (own figure).
    Same behaviour and output file as before; see _draw_exergetic_efficiencies."""
    df_list, cycle_labels = _prepare(exergy_destruction, cycle_labels)
    if df_list is None:
        return None, None

    fig, ax = plt.subplots(
        figsize=PLOT_STYLE["figure"]["figsize"], dpi=PLOT_STYLE["figure"]["dpi"]
    )
    if not _draw_exergetic_efficiencies(ax, df_list, cycle_labels):
        plt.close(fig)
        return None, None
    _place_legends([ax])
    fig.patch.set_facecolor(PLOT_STYLE["figure"]["facecolor"])
    _save_figure(fig, save_path, file_name, "exergetic_efficiencies")
    return fig, ax


def plot_exergy_plots(
    exergy_destruction,
    cycle_labels=None,
    plots=("destruction", "efficiencies"),
    combined=True,
    layout="horizontal",
    save_path=None,
    file_name=None,
    dpi=None,
):
    """
    Produce one or several of the exergy plots, either on a single shared
    figure or as separate figures.

    Parameters
    ----------
    exergy_destruction, cycle_labels :
        As in plot_exergy_destruction_stacked.
    plots : str or sequence of str
        Which plots to produce, in panel order. Available keys:
        "destruction"  -> stacked exergy destruction per cycle
        "efficiencies" -> exergetic efficiency per component
        e.g. plots="efficiencies" or plots=["efficiencies", "destruction"].
    combined : bool
        True: all selected plots as panels (a), (b), ... of ONE figure,
        saved as <file_name>_exergy_combined.png. False: one separate figure
        (and file) per plot, exactly like calling the single functions.
    layout : "horizontal" | "vertical"
        Panel arrangement when combined (side by side or stacked).
    save_path, file_name :
        Where / under which base name to save.
    dpi : int, optional
        Resolution of the combined figure (default: PLOT_STYLE dpi).

    Returns
    -------
    fig, axes  (combined: one figure and an array of axes)
    list of (fig, ax)  (not combined)
    """
    plots = [plots] if isinstance(plots, str) else list(plots)
    unknown = [p for p in plots if p not in _EXERGY_PLOTS]
    if unknown:
        raise ValueError(
            f"Unknown plot(s) {unknown}; choose from {list(_EXERGY_PLOTS)}."
        )
    if layout not in ("horizontal", "vertical"):
        raise ValueError("layout must be 'horizontal' or 'vertical'.")

    df_list, cycle_labels = _prepare(exergy_destruction, cycle_labels)
    if df_list is None:
        return None, None

    if not combined or len(plots) == 1:
        singles = {
            "destruction": plot_exergy_destruction_stacked,
            "efficiencies": plot_exergetic_efficiencies,
        }
        return [
            singles[p](df_list, cycle_labels, save_path=save_path, file_name=file_name)
            for p in plots
        ]

    n = len(plots)
    w, h = PLOT_STYLE["figure"]["figsize"]
    dpi = dpi or PLOT_STYLE["figure"]["dpi"]
    fig, axes = plt.subplots(
        1 if layout == "horizontal" else n,
        n if layout == "horizontal" else 1,
        figsize=(w * n, h * 2) if layout == "horizontal" else (w, h * n * 1.15),
        dpi=dpi,
        squeeze=False,
    )
    axes = axes.ravel()

    for k, (ax, key) in enumerate(zip(axes, plots)):
        draw, _ = _EXERGY_PLOTS[key]
        draw(ax, df_list, cycle_labels)
        ax.set_title(
            f"({chr(ord('a') + k)})", fontsize=PLOT_STYLE["fonts"]["title"], pad=10
        )

    _place_legends(list(axes))
    fig.patch.set_facecolor(PLOT_STYLE["figure"]["facecolor"])
    fig.tight_layout()
    _save_figure(fig, save_path, file_name, "exergy_combined", dpi=dpi)
    return fig, axes
