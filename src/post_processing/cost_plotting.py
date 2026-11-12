"""Cost plotting, comparable across one or several cycles."""

import math
import textwrap
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from src import PLOT_STYLE, add_legend, create_figure, save_figure

# Style from plot_style (fonts are the global ones set by plot_style.py)
_COLORS = PLOT_STYLE["colors"]
_LINEWIDTH = PLOT_STYLE["lines_and_markers"]["linewidth"]
_ANNOTATION_FONT = PLOT_STYLE["paper_fonts"]["annotation"]  # values on the plots
_MARKER_SIZE = 5  # [pt] markers of the delta plot

# Cycle colors (same scheme as in the T-s and exergy plots):
# PLOT_STYLE["cycle_colors"], dark for standalone and light for TES-integrated,
# blue for base and red / orange for intercooled.
_CYCLE_COLORS = PLOT_STYLE["cycle_colors"]
# Short cycle label -> key of cycle_colors, e.g. {"S-BR": "standalone_base"}
_CYCLE_LABEL_KEYS = PLOT_STYLE["cycle_label_keys"]

_DEMAND_MARKERS = {"fixed": "s", "free": "o"}  # square = fixed, circle = free
_DEMAND_LABELS = {
    "fixed": "Fixed heat demand schedule",
    "free": "Variable heat demand schedule",
}

# Component colors and stacking order (bottom to top) come from
# PLOT_STYLE["component_colors"] ({lower-case component name: color}); the
# match against the component names of the tables is case-insensitive.
_COMPONENT_COLORS = PLOT_STYLE["component_colors"]
_COMPONENT_ORDER = list(_COMPONENT_COLORS)
_UNKNOWN_COMPONENT_COLOR = "#7f7f7f"  # grey, for a component not in the scheme

# Columns of the legend of the CAPEX plot (inside the axes)
_LEGEND_COLUMNS = 4

# Display names of the components (PLOT_STYLE["component_names"], e.g.
# "sink 2" -> "HX2"): only what is written on the plots changes, the names
# used inside the plants and in the CSV tables stay as they are. Keys are
# matched case-insensitively; a name not in the mapping is shown as it is.
_COMPONENT_NAMES = {k.lower(): v for k, v in PLOT_STYLE["component_names"].items()}


def _display_name(name):
    """Display name of a component (see _COMPONENT_NAMES)."""
    return _COMPONENT_NAMES.get(str(name).strip().lower(), name)


_CYCLE_LABEL = "S-BR"
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
    order and colors follow the scheme PLOT_STYLE["component_colors"] so they
    stay consistent across figures.

    The figure has the fixed single-column paper width and square axes of the
    same size as all the other diagrams; the legend is above the axes (the figure grows in height).

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
        Base name for the saved file; saved as ``<file_name>_cost_stacked.png``.

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
    # anything not in the scheme is appended (sorted) with a grey fallback.
    present = {comp for df in df_list for comp in df["Component"].values}
    present_lookup = {p.lower(): p for p in present}
    ordered_components = [
        present_lookup[c] for c in _COMPONENT_ORDER if c in present_lookup
    ]

    leftover = sorted(present - set(ordered_components))
    ordered_components += leftover

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

    # one legend entry per display name (e.g. "sink" and "sink 1" are both HX1)
    n_entries = len({_display_name(c) for c in ordered_components})
    fig, ax = create_figure(legend_rows=math.ceil(n_entries / _LEGEND_COLUMNS))

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
            label=_display_name(comp),
            color=colors[comp],
            edgecolor=PLOT_STYLE["colors"]["edge"],
            linewidth=PLOT_STYLE["lines_and_markers"]["linewidth"],
        )
        bottoms += values

    ax.set_ylabel(r"CAPEX [M€]")
    ax.set_xlabel(r"Cycle")

    ax.set_xticks(x)
    ax.set_xticklabels(wrapped_labels, ha="center", rotation=0)
    # Scales to however many cycles are being compared, instead of the fixed
    # (-1, 1) that only ever fit a single bar.
    ax.set_xlim(-0.75, len(df_list) - 1 + 0.75)

    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    add_legend(
        fig,
        list(unique.values()),
        list(unique.keys()),
        ncol=min(len(unique), _LEGEND_COLUMNS),
        ax=ax,
    )

    if save_path is not None:
        if file_name is None:
            raise ValueError("`file_name` is required when `save_path` is given.")
        save_figure(fig, save_path, f"{file_name}_cost_stacked")

    return fig, ax


# ============================================================================
# LCOH plots
# ============================================================================


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
    encodes the cycle, so a cycle keeps its color in every group.

    Single-column paper width, square axes, legend above the axes (the
    figure grows in height).

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

    legend_cols = math.ceil(n_cycles / 2)
    fig, ax = create_figure(legend_rows=math.ceil(n_cycles / legend_cols))

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
            )
            # the value is written vertically: the bars are too narrow for it
            ax.text(
                x,
                value + 0.01 * (max(float(d[lcoh_kind].max()) for d in tables) - y_min),
                f"{value:.1f}",
                va="bottom",
                ha="center",
                rotation=90,
                fontsize=_ANNOTATION_FONT,
            )

    top = max(float(df[lcoh_kind].max()) for df in tables)
    ax.set_ylim(y_min, y_min + (top - y_min) * 1.2)  # room for the values
    ax.set_xticks(x_groups)
    ax.set_xticklabels([str(s).capitalize() for s in scenarios])
    ax.set_ylabel("LCOH [€/MWh]")
    ax.set_xlabel("Scenario")

    handles = [
        mpatches.Patch(
            facecolor=colors[i], edgecolor=_COLORS["edge"], label=cycle_labels[i]
        )
        for i in range(n_cycles)
    ]
    add_legend(fig, handles, ncol=legend_cols, ax=ax)

    if save_path is not None:
        if file_name is None:
            raise ValueError("`file_name` is required when `save_path` is given.")
        save_figure(fig, save_path, f"{file_name}_lcoh_scenarios")

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

    One square panel per market (DK1 | DE; one or two markets). Inside each
    panel the x-axis holds the scenarios (low / central / high); the marker
    shape encodes the heat demand (square = fixed, circle = free) and the
    color encodes the layout. Paper width: single for one market, double for
    two; the legend is above the axes.

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
    pad = 0.1 * (hi - lo if hi > lo else 1.0)  # margin above / below the markers
    ylim = (lo - pad, hi + pad)

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
            markersize=_MARKER_SIZE,
            markerfacecolor="white",
            markeredgecolor=_COLORS["edge"],
            label=_DEMAND_LABELS.get(d, f"{d.capitalize()} heat demand schedule"),
        )
        for d in demands
    ]
    # one row of legend in the double-width figure; in the single-width one
    # the long labels of the heat demands only fit one per row
    legend_cols = len(handles) if len(markets) > 1 else 1

    fig, axes = create_figure(
        n_cols=len(markets),
        titles=True,
        legend_rows=math.ceil(len(handles) / legend_cols),
    )
    axes = np.atleast_1d(axes)

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
                ax.scatter(
                    x_groups + dx,
                    delta[col].to_numpy(),
                    s=_MARKER_SIZE**2,
                    marker=_DEMAND_MARKERS.get(demand, "D"),
                    color=colors[p],
                    edgecolor=_COLORS["edge"],
                    linewidth=_LINEWIDTH,
                    zorder=3,
                )

        ax.set_ylim(*ylim)
        ax.set_xlim(-0.6, len(scenarios) - 1 + 0.6)
        ax.set_xticks(x_groups)
        ax.set_xticklabels([str(s).capitalize() for s in scenarios])
        ax.set_xlabel("Scenario")
        ax.set_title(f"({chr(ord('a') + k)}) {market}", pad=4)
        if k > 0:  # same y axis as the first panel
            ax.tick_params(labelleft=False)

    axes[0].set_ylabel("ΔLCOH [€/MWh]")  # TES − standalone, see docstring
    add_legend(fig, handles, ncol=legend_cols)

    if save_path is not None:
        if file_name is None:
            raise ValueError("`file_name` is required when `save_path` is given.")
        save_figure(fig, save_path, f"{file_name}_delta_lcoh")

    return fig, axes


# Colors of the LCOH cost categories, in stacking order (bottom to top):
# PLOT_STYLE["lcoh_category_colors"] ({category: color}; the names must be
# CAPEX, Electricity, O&M, Labour and Decommissioning).
_LCOH_CATEGORY_COLORS = PLOT_STYLE["lcoh_category_colors"]

# A segment thinner than this fraction of the y axis gets no percentage.
_MIN_LABEL_HEIGHT = 0.045


def _load_breakdown(breakdown):
    """Breakdown table as one DataFrame.

    Accepts a DataFrame, a str/Path to a CSV, or a list/tuple of these
    (concatenated in order).
    """
    if isinstance(breakdown, (list, tuple)):
        return pd.concat([_load_breakdown(b) for b in breakdown], ignore_index=True)
    if isinstance(breakdown, (str, Path)):
        return pd.read_csv(breakdown)
    return breakdown


def plot_lcoh_breakdown_stacked(
    breakdown,
    panels=(("DK1 Energinet", "fixed"), ("DE Energinet", "fixed")),
    panel_titles=("DK1", "DE"),
    cycle_labels=None,
    save_path=None,
    file_name=None,
):
    """
    Plot the contributions to the LCOH [EUR/MWh] of the central scenario as
    one stacked bar per cycle (CAPEX, the OPEX items electricity, O&M and
    labour, and decommissioning), with their percentage share of the LCOH.
    One square panel per entry of `panels` (one or two): double paper width
    for two panels, single for one; the legend is above the axes.

    Parameters
    ----------
    breakdown : pd.DataFrame or str/Path
        The central-scenario breakdown table (lcoh_central_breakdown.csv)
        with the columns Cycle, Forecast, Demand, Electricity [EUR],
        O&M [EUR], Labour [EUR], CAPEX [EUR], Decommissioning [EUR] and
        Discounted heat [MWh]. A list of tables is concatenated.
    panels : sequence of (forecast, demand)
        One panel per entry, left to right, e.g. ("DK1 Energinet", "fixed").
        Default: DK1 and DE with the Energinet forecast, fixed heat demand.
    panel_titles : sequence of str
        One title per panel; panels are labelled "(a) <title>", ...
    cycle_labels : list of str, optional
        x-axis labels, one per cycle in the order of the table. Default: the
        "Cycle" names of the table.
    save_path : str or Path, optional
        Directory to save the figure.
    file_name : str, optional
        Base name; saved as ``<file_name>_lcoh_breakdown.png``.

    Returns
    -------
    fig, axes
    """
    df = _load_breakdown(breakdown)
    if df is None or df.empty:
        print("Warning: No data provided")
        return None, None

    panels = list(panels)
    if panel_titles is None:
        panel_titles = [f"{forecast} {demand}" for forecast, demand in panels]
    if len(panel_titles) != len(panels):
        raise ValueError("`panel_titles` must have one title per panel.")

    cycles = list(dict.fromkeys(df["Cycle"]))
    if cycle_labels is None:
        cycle_labels = cycles
    if len(cycle_labels) != len(cycles):
        raise ValueError(
            f"cycle_labels has {len(cycle_labels)} entries but "
            f"{len(cycles)} cycles are in the table."
        )
    wrapped_labels = [textwrap.fill(lbl, width=_WRAP_WIDTH) for lbl in cycle_labels]
    x = np.arange(len(cycles))

    # LCOH contributions [EUR/MWh] of every cycle, per panel
    contributions = []
    for forecast, demand in panels:
        rows = df[(df["Forecast"] == forecast) & (df["Demand"] == demand)]
        if rows.empty:
            # Tables that only carry the price zone ("DK1", "DE"): match the
            # zone part of the requested forecast ("DK1 Energinet" -> "DK1").
            zone = str(forecast).split()[0]
            rows = df[(df["Forecast"] == zone) & (df["Demand"] == demand)]
        if rows.empty:
            raise ValueError(
                f"No rows for forecast '{forecast}' and demand '{demand}'."
            )
        if rows["Cycle"].duplicated().any():
            raise ValueError(
                f"Several rows per cycle for forecast '{forecast}' and demand "
                f"'{demand}'; check the breakdown tables."
            )
        rows = rows.set_index("Cycle").loc[cycles]
        heat = rows["Discounted heat [MWh]"]
        contributions.append(
            pd.DataFrame(
                {
                    "CAPEX": rows["CAPEX [EUR]"] / heat,
                    "Electricity": rows["Electricity [EUR]"] / heat,
                    "O&M": rows["O&M [EUR]"] / heat,
                    "Labour": rows["Labour [EUR]"] / heat,
                    "Decommissioning": rows["Decommissioning [EUR]"] / heat,
                }
            )
        )

    y_max = max(c.sum(axis=1).max() for c in contributions)
    y_top = y_max * 1.05

    handles = [
        mpatches.Patch(facecolor=color, edgecolor=_COLORS["edge"], label=label)
        for label, color in _LCOH_CATEGORY_COLORS.items()
    ]
    # one legend row in the double-width figure, two in the single one
    legend_cols = len(handles) if len(panels) > 1 else math.ceil(len(handles) / 2)

    fig, axes = create_figure(
        n_cols=len(panels),
        titles=True,
        legend_rows=math.ceil(len(handles) / legend_cols),
    )
    axes = np.atleast_1d(axes)

    for k, (ax, contrib, title) in enumerate(zip(axes, contributions, panel_titles)):
        total = contrib.sum(axis=1).to_numpy()
        bottoms = np.zeros(len(cycles))

        for category, color in _LCOH_CATEGORY_COLORS.items():
            values = contrib[category].to_numpy()
            ax.bar(
                x,
                values,
                bottom=bottoms,
                width=0.8,
                color=color,
                edgecolor=_COLORS["edge"],
                linewidth=_LINEWIDTH,
            )
            # percentage share of the LCOH inside each segment (thin
            # segments get none: it would not fit)
            for xi, v, b, t in zip(x, values, bottoms, total):
                if v >= _MIN_LABEL_HEIGHT * y_top:
                    ax.text(
                        xi,
                        b + v / 2,
                        f"{100 * v / t:.1f} %",
                        ha="center",
                        va="center",
                        fontsize=_ANNOTATION_FONT,
                        color="black",
                    )
            bottoms += values

        ax.set_ylim(0, y_top)
        ax.set_xticks(x)
        ax.set_xticklabels(wrapped_labels, ha="center", rotation=0)
        ax.set_xlim(-0.6, len(cycles) - 1 + 0.6)
        ax.set_xlabel("Cycle")
        ax.set_title(f"({chr(ord('a') + k)}) {title}", pad=4)
        if k > 0:  # same y axis as the first panel
            ax.tick_params(labelleft=False)

    axes[0].set_ylabel("LCOH [€/MWh]")
    add_legend(fig, handles, ncol=legend_cols)

    if save_path is not None:
        if file_name is None:
            raise ValueError("`file_name` is required when `save_path` is given.")
        save_figure(fig, save_path, f"{file_name}_lcoh_breakdown")

    return fig, axes
