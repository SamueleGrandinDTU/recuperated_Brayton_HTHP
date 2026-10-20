"""Cost plotting, comparable across one or several cycles."""

import textwrap
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from src import PLOT_STYLE

# Style from plot_style
_COLORS = PLOT_STYLE["colors"]
_FONTS = PLOT_STYLE["fonts"]
_GRID = PLOT_STYLE["grid"]
_AXES = PLOT_STYLE["axes"]
_TICKS = PLOT_STYLE["ticks"]
_LINEWIDTH = PLOT_STYLE["lines_and_markers"]["linewidth"]

# Cycle colors (same scheme as in the exergy plots): shades of blue for base
# cycles, shades of red for labels mentioning "intercooled".
_CYCLE_BASE_COLORS = ["#3182bd", "#9ecae1"]  # blue, light blue
_CYCLE_INTERCOOLED_COLORS = ["#de2d26", "#fc9272"]  # red, light red

_DEMAND_MARKERS = {"fixed": "s", "free": "o"}  # square = fixed, circle = free

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
    ("tank 1", "#7f7f7f"),  # grey
    ("tank 2", "#c7c7c7"),  # light grey
    ("hitec salt", "#ff7f0e"),  # orange
]
_COMPONENT_ORDER = [c for c, _ in _COMPONENT_COLOR_ORDER]
_COMPONENT_COLORS = {c: color for c, color in _COMPONENT_COLOR_ORDER}

_CYCLE_LABEL = "Standalone Base Recuperated"
_WRAP_WIDTH = 14

# Component labels used for a cycle-level summary row (e.g. the "total" row
# appended by calculate_component_cost's CSV export): excluded from the
# stacked bars, since it duplicates the sum of the real component rows
# rather than being an additional component.
_SUMMARY_ROW_LABELS = {"cycle", "total"}


def _load_dataframe(item):
    """Accept either a DataFrame or a path to a CSV saved by
    calculate_component_cost (or any table with a "Component" column) and
    return a DataFrame either way, with the cycle-level summary row removed.
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


def plot_component_cost_stacked(
    component_cost,
    cycle_labels=None,
    save_path=None,
    file_name=None,
):
    """
    Plot component cost as one stacked bar per cycle. Component stacking
    order and colors follow a fixed, predefined scheme so they stay
    consistent across figures.

    Parameters
    ----------
    component_cost : pd.DataFrame, str/Path, or list of either
        The cost table from calculate_component_cost, or the path to a CSV
        it saved (its trailing cycle-level summary row, if present, is
        dropped automatically). Pass a list to plot several cycles side by
        side, one bar each.
    cycle_labels : list of str, optional
        One label per cycle, in the same order as `component_cost`, used as
        the x-axis tick labels. If not given, cycles are labeled "Cycle 1",
        "Cycle 2", etc. — except for a single cycle, which falls back to the
        fixed _CYCLE_LABEL for backward compatibility.
    save_path : str or Path, optional
        Directory to save the figure.
    file_name : str, optional
        Base name for the saved file.

    Returns
    -------
    fig, ax
    """
    df_list = _normalize_input(component_cost)
    if df_list is None or all(df.empty for df in df_list):
        print("Warning: No data provided")
        return None, None

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
            width=0.6,
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
        fontsize=PLOT_STYLE["fonts"]["small_label"],
    )
    # Scales to however many cycles are being compared, instead of the fixed
    # (-1, 1) that only ever fit a single bar.
    ax.set_xlim(-0.75, len(df_list) - 1 + 0.75)

    # Legend on the right, outside the plot area
    ax.legend(
        fontsize=PLOT_STYLE["fonts"]["legend"],
        framealpha=0.95,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=min(len(ordered_components), 4),
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


# ============================================================================
# LCOH plots
# ============================================================================


def _assign_cycle_colors(cycle_labels):
    """One color per cycle label: shades of red for a label mentioning
    "intercooled", shades of blue otherwise, falling back to tab10 once a
    group's fixed shades (2 each) run out."""
    extra_cmap = plt.cm.tab10
    base_idx = 0
    intercooled_idx = 0
    extra_idx = 0
    colors = []

    for label in cycle_labels:
        is_intercooled = "interc" in str(label).lower()
        palette = _CYCLE_INTERCOOLED_COLORS if is_intercooled else _CYCLE_BASE_COLORS
        idx = intercooled_idx if is_intercooled else base_idx

        if idx < len(palette):
            colors.append(palette[idx])
        else:
            colors.append(extra_cmap(extra_idx % 10))
            extra_idx += 1

        if is_intercooled:
            intercooled_idx += 1
        else:
            base_idx += 1

    return colors


def _load_lcoh_table(source) -> pd.DataFrame:
    """LCOH table of one cycle: a DataFrame or the path to the csv saved as
    ``<cycle>_lcoh.csv`` (rows = scenarios, columns = "scenario" + one
    column per market / heat-demand case, e.g. "DK1 fixed")."""

    if isinstance(source, pd.DataFrame):
        return source
    return pd.read_csv(source)


def plot_lcoh_scenarios_stacked(
    cycles,
    lcoh_kind: str,
    cycle_labels=None,
    save_path: Optional[Union[str, Path]] = None,
    file_name: Optional[str] = None,
    y_min: float = 100.0,
):
    """Grouped vertical bar chart of the LCOH: one group per scenario
    (low / central / high), one bar per cycle inside each group. Color
    encodes the cycle (blue shades for base, red shades for intercooled),
    so a cycle keeps its color in every group.

    Parameters
    ----------
    cycles : list of str / Path / pd.DataFrame
        One LCOH table (or its csv path) per cycle.
    lcoh_kind : str
        Column of the LCOH tables to plot, e.g. "DK1 fixed", "DE fixed",
        "DK1 free", "DE free".
    cycle_labels : list of str, optional
        One label per cycle, same order as `cycles` (legend and colors).
        Default: "Cycle 1", "Cycle 2", ...
    save_path : str | Path, optional
        Directory the figure is saved in.
    file_name : str, optional
        Base name; saved as ``<file_name>_lcoh_scenarios.png``. Required
        when `save_path` is given.
    y_min : float
        Start of the LCOH axis [EUR/MWh] (default 100, to make the
        differences between cycles visible). The bars are therefore
        truncated - say so in the caption.

    Returns
    -------
    fig, ax
    """

    if not isinstance(cycles, (list, tuple)):
        cycles = [cycles]
    tables = [_load_lcoh_table(c) for c in cycles]
    if not tables:
        print("Warning: No data provided")
        return None, None

    n_cycles = len(tables)
    if cycle_labels is None:
        cycle_labels = [f"Cycle {i + 1}" for i in range(n_cycles)]
    if len(cycle_labels) != n_cycles:
        raise ValueError("`cycle_labels` must have one label per cycle.")

    for label, df in zip(cycle_labels, tables):
        if lcoh_kind not in df.columns:
            raise ValueError(
                f"'{lcoh_kind}' not found for '{label}'. Available: "
                f"{[c for c in df.columns if c != 'scenario']}"
            )

    scenarios = list(tables[0]["scenario"])
    for df in tables[1:]:
        if list(df["scenario"]) != scenarios:
            raise ValueError("All cycles must list the same scenarios.")

    colors = _assign_cycle_colors(cycle_labels)
    group_width = 0.8
    bar_w = group_width / n_cycles
    x_groups = np.arange(len(scenarios), dtype=float)

    fig, ax = plt.subplots(
        figsize=PLOT_STYLE["figure"]["figsize"],
        dpi=PLOT_STYLE["figure"]["dpi"],
        facecolor=PLOT_STYLE["figure"]["facecolor"],
    )

    for g in range(len(scenarios)):
        for i, df in enumerate(tables):
            value = float(df[lcoh_kind].iloc[g])
            x = x_groups[g] + (i - (n_cycles - 1) / 2) * bar_w
            ax.bar(
                x,
                value - y_min,
                bottom=y_min,
                width=bar_w,
                color=colors[i],
                edgecolor=_COLORS["edge"],
                linewidth=_LINEWIDTH,
                alpha=0.85,
            )
            ax.text(
                x,
                value + 0.4,
                f"{value:.1f}",
                va="bottom",
                ha="center",
                fontsize=_FONTS["small_label"],
            )

    all_values = [float(df[lcoh_kind].max()) for df in tables]
    ax.set_ylim(y_min, max(all_values) * 1.06)
    ax.set_xticks(x_groups)
    ax.set_xticklabels([str(s).capitalize() for s in scenarios])
    ax.set_ylabel("LCOH [€/MWh]", fontsize=_FONTS["label"])
    ax.set_xlabel("Scenario", fontsize=_FONTS["label"])

    ax.legend(
        handles=[
            mpatches.Patch(
                facecolor=colors[i], edgecolor=_COLORS["edge"], label=cycle_labels[i]
            )
            for i in range(n_cycles)
        ],
        fontsize=_FONTS["legend"],
        framealpha=0.95,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=int(np.ceil(n_cycles / 2)),
    )

    ax.grid(
        axis="y",
        alpha=_GRID["alpha"],
        linestyle="--",
        linewidth=_GRID["linewidth"],
    )
    ax.set_axisbelow(True)
    ax.set_facecolor(_AXES["facecolor"])
    for spine in ax.spines.values():
        spine.set_color(_AXES["spine_color"])
        spine.set_linewidth(_AXES["spine_linewidth"])
    ax.tick_params(
        axis=_TICKS["axis"],
        pad=_TICKS["pad"],
        which=_TICKS["which"],
        color=_TICKS["color"],
        labelcolor=_TICKS["labelcolor"],
        direction=_TICKS["direction"],
        labelsize=_FONTS["small_label"],
    )
    fig.tight_layout()

    if save_path is not None:
        if file_name is None:
            raise ValueError("`file_name` is required when `save_path` is given.")
        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)
        out = save_path / f"{file_name}_lcoh_scenarios.png"
        fig.savefig(
            out,
            dpi=PLOT_STYLE["figure"]["dpi"],
            bbox_inches="tight",
            facecolor=PLOT_STYLE["figure"]["facecolor"],
        )
        print(f"✓ Figure saved: {out}")

    return fig, ax


def _split_lcoh_kind(column: str):
    """ "DK1 fixed" -> ("DK1", "fixed")."""
    market, _, demand = str(column).rpartition(" ")
    return market, demand.lower()


def plot_delta_lcoh_analysis(
    cycle_pairs,
    pair_labels=None,
    save_path: Optional[Union[str, Path]] = None,
    file_name: Optional[str] = None,
):
    """Plot the LCOH change caused by the TES integration, per scenario and
    market: delta = LCOH(TES-integrated) - LCOH(standalone). Positive means
    the LCOH increased with the TES, negative means it decreased.

    One panel per market (DK1 | DE). Inside each panel the x-axis holds the
    scenarios (low / central / high); the marker shape encodes the heat
    demand (square = fixed, circle = free) and the color encodes the layout
    (blue shades for base, red shades for intercooled).

    Parameters
    ----------
    cycle_pairs : list of [standalone, tes_integrated]
        One pair per layout, e.g.
        ``[[standalone_base_csv, tes_integr_base_csv],
        [standalone_interc_csv, tes_integr_interc_csv]]``. Each item is an
        LCOH table (or its csv path). The market / heat-demand cases are
        read from the table columns ("DK1 fixed", "DE free", ...).
    pair_labels : list of str, optional
        One label per pair (legend and colors), e.g. ["Base", "Intercooled"].
        A label containing "interc" gets a red shade, any other a blue one.
        Default: "Layout 1", "Layout 2", ...
    save_path : str | Path, optional
        Directory the figure is saved in.
    file_name : str, optional
        Base name; saved as ``<file_name>_delta_lcoh.png``. Required when
        `save_path` is given.

    Returns
    -------
    fig, axes
    """

    if not cycle_pairs:
        print("Warning: No data provided")
        return None, None
    if not isinstance(cycle_pairs[0], (list, tuple)):
        cycle_pairs = [cycle_pairs]  # a single [standalone, tes] pair

    n_pairs = len(cycle_pairs)
    if pair_labels is None:
        pair_labels = [f"Layout {i + 1}" for i in range(n_pairs)]
    if len(pair_labels) != n_pairs:
        raise ValueError("`pair_labels` must have one label per pair.")

    # delta tables: scenario x case, TES - standalone
    deltas = []
    for pair in cycle_pairs:
        if len(pair) != 2:
            raise ValueError("Each pair must be [standalone, tes_integrated].")
        standalone, tes = (_load_lcoh_table(p) for p in pair)
        cases = [c for c in standalone.columns if c != "scenario"]
        if list(standalone["scenario"]) != list(tes["scenario"]) or cases != [
            c for c in tes.columns if c != "scenario"
        ]:
            raise ValueError("Both tables of a pair must share scenarios and columns.")
        deltas.append((standalone["scenario"], tes[cases] - standalone[cases]))

    scenarios = list(deltas[0][0])
    cases = list(deltas[0][1].columns)
    markets = list(dict.fromkeys(_split_lcoh_kind(c)[0] for c in cases))
    demands = list(dict.fromkeys(_split_lcoh_kind(c)[1] for c in cases))

    colors = _assign_cycle_colors(pair_labels)

    all_vals = np.concatenate([d.to_numpy().ravel() for _, d in deltas])
    lo, hi = min(0.0, all_vals.min()), max(0.0, all_vals.max())
    pad = 0.25 * (hi - lo if hi > lo else 1.0)  # room for the region labels
    ylim = (lo - pad, hi + pad)

    fig_w, fig_h = PLOT_STYLE["figure"]["figsize"]
    fig, axes = plt.subplots(
        1,
        len(markets),
        figsize=(fig_w * len(markets), fig_h),
        dpi=PLOT_STYLE["figure"]["dpi"],
        facecolor=PLOT_STYLE["figure"]["facecolor"],
        sharey=True,
        squeeze=False,
    )
    axes = axes[0]

    x_groups = np.arange(len(scenarios), dtype=float)
    step = 0.3  # horizontal spacing between layouts inside a scenario

    for k, (ax, market) in enumerate(zip(axes, markets)):
        ax.axhline(0, color=_COLORS["edge"], linewidth=_LINEWIDTH, zorder=2)

        for p, (_, delta) in enumerate(deltas):
            dx = (p - (n_pairs - 1) / 2) * step
            for demand in demands:
                col = f"{market} {demand}"
                if col not in delta.columns:
                    continue
                y = delta[col].to_numpy()
                ax.scatter(
                    x_groups + dx,
                    y,
                    s=80,
                    marker=_DEMAND_MARKERS.get(demand, "D"),
                    color=colors[p],
                    edgecolor=_COLORS["edge"],
                    linewidth=_LINEWIDTH,
                    alpha=0.9,
                    zorder=3,
                )
                # label on the outer side of the marker so it never runs
                # into the neighbouring layout's marker
                side = -1 if dx < 0 else 1
                for xi, yi in zip(x_groups + dx, y):
                    ax.text(
                        xi + side * 0.07,
                        yi,
                        f"{yi:+.1f}",
                        va="center",
                        ha="left" if side > 0 else "right",
                        fontsize=_FONTS["small_label"],
                    )

        ax.set_ylim(*ylim)
        ax.set_xlim(-0.6, len(scenarios) - 1 + 0.75)
        ax.set_xticks(x_groups)
        ax.set_xticklabels([str(s).capitalize() for s in scenarios])
        ax.set_xlabel("Scenario", fontsize=_FONTS["label"])
        ax.set_title(f"({chr(ord('a') + k)}) {market}", fontsize=_FONTS["label"])

        # which side of the zero line means what
        ax.text(
            0.02,
            0.98,
            "TES increases LCOH",
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=_FONTS["small_label"],
            style="italic",
            color="gray",
        )
        ax.text(
            0.02,
            0.02,
            "TES decreases LCOH",
            transform=ax.transAxes,
            va="bottom",
            ha="left",
            fontsize=_FONTS["small_label"],
            style="italic",
            color="gray",
        )

        ax.grid(
            axis="y",
            alpha=_GRID["alpha"],
            linestyle="--",
            linewidth=_GRID["linewidth"],
        )
        ax.set_axisbelow(True)
        ax.set_facecolor(_AXES["facecolor"])
        for spine in ax.spines.values():
            spine.set_color(_AXES["spine_color"])
            spine.set_linewidth(_AXES["spine_linewidth"])
        ax.tick_params(
            axis=_TICKS["axis"],
            pad=_TICKS["pad"],
            which=_TICKS["which"],
            color=_TICKS["color"],
            labelcolor=_TICKS["labelcolor"],
            direction=_TICKS["direction"],
            labelsize=_FONTS["small_label"],
        )
        ax.set_box_aspect(_AXES["box_aspect"])

    axes[0].set_ylabel("ΔLCOH (TES − standalone) [€/MWh]", fontsize=_FONTS["label"])

    handles = [
        mpatches.Patch(
            facecolor=colors[i], edgecolor=_COLORS["edge"], label=pair_labels[i]
        )
        for i in range(n_pairs)
    ] + [
        Line2D(
            [],
            [],
            linestyle="none",
            marker=_DEMAND_MARKERS.get(d, "D"),
            markersize=8,
            markerfacecolor="white",
            markeredgecolor=_COLORS["edge"],
            label=f"{d.capitalize()} heat demand",
        )
        for d in demands
    ]
    fig.legend(
        handles=handles,
        fontsize=_FONTS["legend"],
        framealpha=0.95,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        ncol=len(handles),
    )
    fig.tight_layout()

    if save_path is not None:
        if file_name is None:
            raise ValueError("`file_name` is required when `save_path` is given.")
        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)
        out = save_path / f"{file_name}_delta_lcoh.png"
        fig.savefig(
            out,
            dpi=PLOT_STYLE["figure"]["dpi"],
            bbox_inches="tight",
            facecolor=PLOT_STYLE["figure"]["facecolor"],
        )
        print(f"✓ Figure saved: {out}")

    return fig, axes
