"""Exergy plotting, comparable across one or several cycles."""

import math
import re
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from src import PLOT_STYLE, add_legend, create_figure, save_figure

_COMPONENT_COLORS = PLOT_STYLE["component_colors"]
_COMPONENT_ORDER = list(_COMPONENT_COLORS)
_UNKNOWN_COMPONENT_COLOR = "#7f7f7f"
_CYCLE_COLORS = PLOT_STYLE["cycle_colors"]
_CYCLE_LABEL_KEYS = PLOT_STYLE["cycle_label_keys"]
_COMPONENT_NAMES = {k.lower(): v for k, v in PLOT_STYLE["component_names"].items()}

_LEGEND_COLUMNS = (
    4  # columns of the component legend (may exceed the axes, not the figure)
)
_ROTATED_LABELS_EXTRA = 0.40  # inches below the axes for rotated names
_CYCLE_LABEL = "S-BR"
_WRAP_WIDTH = 14
_SUMMARY_ROW_LABELS = {"cycle", "total"}


def _display_name(name):
    return _COMPONENT_NAMES.get(str(name).strip().lower(), name)


def _load_dataframe(item):
    df = pd.read_csv(item) if isinstance(item, (str, Path)) else item
    if df is None or df.empty or "Component" not in df.columns:
        return df
    return df[~df["Component"].astype(str).str.lower().isin(_SUMMARY_ROW_LABELS)]


def _normalize_input(data):
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
    present = {comp for df in df_list for comp in df["Component"].values}
    lookup = {p.lower(): p for p in present}
    ordered = [lookup[c] for c in _COMPONENT_ORDER if c in lookup]
    return ordered + sorted(present - set(ordered))


def _assign_cycle_colors(cycle_labels):
    colors, extra = [], 0
    for label in cycle_labels:
        text = str(label).lower()
        key = _CYCLE_LABEL_KEYS.get(str(label).strip())
        if key is None:
            key = ("tes" if "tes" in text else "standalone") + (
                "_intercooled" if "interc" in text else "_base"
            )
        if key in _CYCLE_COLORS and _CYCLE_COLORS[key] not in colors:
            colors.append(_CYCLE_COLORS[key])
        else:
            colors.append(plt.cm.tab10(extra % 10))
            extra += 1
    return colors


def _prepare(data, cycle_labels):
    df_list = _normalize_input(data)
    if df_list is None or all(df.empty for df in df_list):
        print("Warning: No data provided")
        return None, None
    return df_list, _resolve_cycle_labels(df_list, cycle_labels)


def _legend_rows(n_entries, ncol):
    return math.ceil(n_entries / ncol)


def _n_destruction_entries(df_list):
    return len({_display_name(c) for c in _ordered_components_present(df_list)})


def plot_exergy_destruction_stacked(
    exergy_destruction, cycle_labels=None, save_path=None, file_name=None, ax=None
):
    """Stacked exergy destruction, one bar per cycle.

    ax=None: own figure (single width, square axes, legend above, height
    adapts). ax given: draws on it, the caller handles figure and legend.
    """
    df_list, cycle_labels = _prepare(exergy_destruction, cycle_labels)
    if df_list is None:
        return None, None

    own_figure = ax is None
    if own_figure:
        fig, ax = create_figure(
            legend_rows=_legend_rows(_n_destruction_entries(df_list), _LEGEND_COLUMNS)
        )
    else:
        fig = ax.figure

    e_d_col = next(
        [c for c in df.columns if "D" in c and "MW" in c][0]
        for df in df_list
        if not df.empty
    )
    components = _ordered_components_present(df_list)
    x = np.arange(len(df_list))
    bottoms = np.zeros(len(df_list))
    for comp in components:
        values = np.array(
            [
                (
                    df[df["Component"] == comp][e_d_col].values[0]
                    if (df["Component"] == comp).any()
                    else 0.0
                )
                for df in df_list
            ]
        )
        ax.bar(
            x,
            values,
            bottom=bottoms,
            width=0.6,
            label=_display_name(comp),
            color=_COMPONENT_COLORS.get(comp.lower(), _UNKNOWN_COMPONENT_COLOR),
            edgecolor=PLOT_STYLE["colors"]["edge"],
            linewidth=PLOT_STYLE["lines_and_markers"]["linewidth"],
        )
        bottoms += values

    ax.set_ylabel(r"Exergy Destruction [MW]")
    ax.set_xlabel(r"Cycle")
    ax.set_xticks(x)
    ax.set_xticklabels(
        [textwrap.fill(l, width=_WRAP_WIDTH) for l in cycle_labels],
        ha="center",
        rotation=0,
    )
    ax.set_xlim(-0.75, len(df_list) - 1 + 0.75)

    if own_figure:
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
            _save(fig, save_path, file_name, "exergy_stacked")
    return fig, ax


def plot_exergetic_efficiencies(
    exergy_destruction, cycle_labels=None, save_path=None, file_name=None, ax=None
):
    """Grouped exergetic efficiencies (one group per component, one bar per
    cycle). Same ax convention as plot_exergy_destruction_stacked."""
    df_list, cycle_labels = _prepare(exergy_destruction, cycle_labels)
    if df_list is None:
        return None, None

    eff_col = next(
        ([c for c in df.columns if "eff" in c.lower()] or [None])[0]
        for df in df_list
        if not df.empty
    )
    if eff_col is None:
        print("Warning: No exergetic efficiency column found")
        return None, None

    n_cycles = len(df_list)
    own_figure = ax is None
    if own_figure:
        fig, ax = create_figure(
            legend_rows=_legend_rows(n_cycles, math.ceil(n_cycles / 2)),
            bottom_extra=_ROTATED_LABELS_EXTRA,
        )
    else:
        fig = ax.figure

    cycle_colors = _assign_cycle_colors(cycle_labels)
    groups = {}
    for comp in _ordered_components_present(df_list):
        groups.setdefault(_display_name(comp), []).append(comp)
    names = list(groups)

    bar_width = 0.8 / n_cycles
    families = [re.sub(r"\s*\d+$", "", n).strip().lower() for n in names]
    pos = [0.0]
    for k in range(1, len(names)):
        pos.append(pos[-1] + 1.0 + (0.6 if families[k] != families[k - 1] else 0.0))
    x_groups = np.array(pos)

    for k, name in enumerate(names):
        present = []
        for i, df in enumerate(df_list):
            for comp in groups[name]:
                rows = df[df["Component"] == comp]
                if not rows.empty:
                    present.append((i, rows[eff_col].values[0]))
                    break
        for j, (i, value) in enumerate(present):
            offset = (j - (len(present) - 1) / 2) * bar_width
            ax.bar(
                x_groups[k] + offset,
                value,
                width=bar_width,
                color=cycle_colors[i],
                edgecolor=PLOT_STYLE["colors"]["edge"],
                linewidth=PLOT_STYLE["lines_and_markers"]["linewidth"],
            )

    ax.set_ylabel(r"Exergy Efficiency [%]")
    ax.set_xlabel(r"Component")
    ax.set_xticks(x_groups)
    ax.set_xticklabels(names, ha="right", rotation=45, rotation_mode="anchor")
    ax.set_xlim(x_groups[0] - 0.5, x_groups[-1] + 0.5)

    if own_figure:
        handles = [
            mpatches.Patch(
                facecolor=cycle_colors[i],
                edgecolor=PLOT_STYLE["colors"]["edge"],
                label=cycle_labels[i],
            )
            for i in range(n_cycles)
        ]
        add_legend(fig, handles, ncol=math.ceil(n_cycles / 2), ax=ax)
        if save_path is not None:
            _save(fig, save_path, file_name, "exergetic_efficiencies")
    return fig, ax


def _save(fig, save_path, file_name, suffix):
    if file_name is None:
        raise ValueError("`file_name` is required when `save_path` is given.")
    save_figure(fig, save_path, f"{file_name}_{suffix}")


def plot_exergy_plots(
    exergy_destruction,
    cycle_labels=None,
    plots=("destruction", "efficiencies"),
    combined=True,
    layout="horizontal",
    save_path=None,
    file_name=None,
    dpi=None,  # ignored, kept for compatibility
):
    """One or two exergy plots; combined=True puts them as panels (a), (b) of
    one figure (horizontal: double width; vertical: single width, stacked)."""
    funcs = {
        "destruction": plot_exergy_destruction_stacked,
        "efficiencies": plot_exergetic_efficiencies,
    }
    plots = [plots] if isinstance(plots, str) else list(plots)
    unknown = [p for p in plots if p not in funcs]
    if unknown:
        raise ValueError(f"Unknown plot(s) {unknown}; choose from {list(funcs)}.")

    df_list, cycle_labels = _prepare(exergy_destruction, cycle_labels)
    if df_list is None:
        return None, None

    if not combined or len(plots) == 1:
        return [funcs[p](df_list, cycle_labels, save_path, file_name) for p in plots]

    n = len(plots)
    n_cycles = len(df_list)
    # legend rows of the panels (the tallest legend sets the top margin)
    rows = max(
        (
            _legend_rows(_n_destruction_entries(df_list), _LEGEND_COLUMNS)
            if p == "destruction"
            else _legend_rows(n_cycles, math.ceil(n_cycles / 2))
        )
        for p in plots
    )
    extra = _ROTATED_LABELS_EXTRA if "efficiencies" in plots else 0.0

    if layout == "horizontal":
        fig, axes = create_figure(
            n_cols=n, titles=True, legend_rows=rows, bottom_extra=extra
        )
    else:
        fig, axes = create_figure(
            n_rows=n,
            titles=True,
            legend_rows=rows,
            bottom_extra=extra,
            row_gap=PLOT_STYLE["figure"]["margins"]["row_gap"]
            + extra
            + rows * PLOT_STYLE["figure"]["margins"]["legend_row"],
        )
    axes = np.atleast_1d(axes)

    for k, (ax, key) in enumerate(zip(axes, plots)):
        funcs[key](df_list, cycle_labels, ax=ax)
        ax.set_title(f"({chr(ord('a') + k)})", pad=4)
        handles, labels = ax.get_legend_handles_labels()
        if key == "destruction":
            unique = dict(zip(labels, handles))
            add_legend(
                fig,
                list(unique.values()),
                list(unique.keys()),
                ncol=min(len(unique), _LEGEND_COLUMNS),
                ax=ax,
            )
        else:
            cc = _assign_cycle_colors(cycle_labels)
            hs = [
                mpatches.Patch(
                    facecolor=cc[i],
                    edgecolor=PLOT_STYLE["colors"]["edge"],
                    label=cycle_labels[i],
                )
                for i in range(n_cycles)
            ]
            add_legend(fig, hs, ncol=math.ceil(n_cycles / 2), ax=ax)

    if save_path is not None:
        _save(fig, save_path, file_name, "exergy_combined")
    return fig, axes
