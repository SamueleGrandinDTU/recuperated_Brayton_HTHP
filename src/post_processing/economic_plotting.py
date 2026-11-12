"""
src/plotting.py

Plotting helpers for the results of ``plant_operation.optimize_operational_strategy``.

Same fixed paper width as the other figures (the double one, 6.18 in: three y
axes do not fit in the single width); the panels are not squares here, their
shape is PLOT_STYLE["operational_strategy"]["aspect"] (height / width), and the
height of the figure adapts to the rows, titles and legend.
"""

import math
from pathlib import Path
from typing import Optional, Union

import numpy as np

from src import PLOT_STYLE, add_legend, create_figure, save_figure

_COLORS = PLOT_STYLE["colors"]
_AXES = PLOT_STYLE["axes"]
_TICKS = PLOT_STYLE["ticks"]
_LINEWIDTH = PLOT_STYLE["lines_and_markers"]["linewidth"]

# Colors and layout of this figure (PLOT_STYLE["operational_strategy"]); the
# fonts are the global ones set by plot_style.py.
_OP = PLOT_STYLE["operational_strategy"]
_OP_COLORS = _OP["colors"]
_ASPECT = _OP["aspect"]  # panel height / panel width (two columns)
_ASPECT_SINGLE = _OP["aspect_single"]  # same, one column (wider panel)
_RIGHT_EXTRA = _OP["right_extra"]  # [in] room for the two right-hand axes
_COL_GAP = _OP["col_gap"]  # [in] between columns (right axes only in the last)
_TES_AXIS_OFFSET_PT = _OP["tes_axis_offset_pt"]  # TES axis, outward from the panel
_MAX_TIME_TICKS = _OP["max_time_ticks"]  # time axis: daily ticks, thinned out
_LINE_WIDTH = _LINEWIDTH + 0.6  # the curves are a bit thicker than the frame

_LEGEND_STYLE = dict(handlelength=2.0, columnspacing=1.5)


def _plant_E_TES(plant) -> float:
    """Read the TES capacity off `result.plant`, which may be a `Plant`
    dataclass instance or a plain dict - without needing to import the
    `Plant` type from `plant_operation`."""

    if isinstance(plant, dict):
        return float(plant["E_TES"])
    return float(plant.E_TES)


def _style_twin(ax, color=None) -> None:
    """Style of a twin (right-hand) axes: no grid, same spines and ticks as
    the main axes. `color` (optional) colours the right spine, ticks and tick
    labels."""

    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_color(_AXES["spine_color"])
        spine.set_linewidth(_AXES["spine_linewidth"])
    ax.tick_params(
        axis=_TICKS["axis"],
        which=_TICKS["which"],
        pad=_TICKS["pad"],
        color=color or _TICKS["color"],
        labelcolor=color or _TICKS["labelcolor"],
        direction=_TICKS["direction"],
    )
    if color is not None:
        ax.spines["right"].set_color(color)
        ax.spines["right"].set_linewidth(_LINEWIDTH + 0.5)


def _draw_operational_strategy(ax1, result, power_axis_max=None, energy_axis_max=None):
    """Draw price, demand, HTHP schedule and TES state of charge of one
    result: the price on `ax1` (left axis), the thermal power of the heat
    demand and of the HTHP on a first twin axis (right) and the TES energy
    on a second twin axis (further right, in the colour of the TES line).

    The thermal power axis runs from 0 to `power_axis_max` (default 3) and
    the TES energy axis from 0 to `energy_axis_max` (default: 1.06 x the
    plant's TES capacity, at least 1.2).

    Returns (ax_power, ax_energy, legend handles).
    """

    t = list(range(len(result.time)))
    E_TES_MAX = _plant_E_TES(result.plant)

    line1 = ax1.step(
        t,
        result.el_price,
        where="post",
        color=_OP_COLORS["electricity_price"],
        linewidth=_LINE_WIDTH,
        linestyle="--",
        label="Electricity price",
        zorder=3,
    )

    # thermal power: heat demand and HTHP
    ax2 = ax1.twinx()

    fill = ax2.fill_between(
        t,
        result.Q_demand,
        step="post",
        color=_OP_COLORS["heat_demand"],
        alpha=0.55,
        label=r"$\dot{Q}_{\mathrm{demand}}$",
        zorder=1,
    )

    line3 = ax2.step(
        t,
        result.Q_HTHP,
        where="post",
        color=_OP_COLORS["hthp"],
        linewidth=_LINE_WIDTH,
        linestyle="-",
        label=r"$\dot{Q}_{\mathrm{HTHP}}$",
        zorder=3,
    )

    ax2.set_ylim(0, power_axis_max if power_axis_max is not None else 3.0)
    _style_twin(ax2)

    # TES energy, on its own axis in the colour of its line
    ax3 = ax1.twinx()
    ax3.spines["right"].set_position(("outward", _TES_AXIS_OFFSET_PT))
    ax3.set_frame_on(True)
    ax3.patch.set_visible(False)
    for side in ("top", "left", "bottom"):
        ax3.spines[side].set_visible(False)

    line4 = ax3.plot(
        range(len(result.E_TES)),
        result.E_TES,
        color=_OP_COLORS["tes"],
        linewidth=_LINE_WIDTH,
        label=r"$E_{\mathrm{TES}}$",
        zorder=2,
    )

    ax3.set_ylim(
        0,
        energy_axis_max if energy_axis_max is not None else max(E_TES_MAX * 1.06, 1.2),
    )
    _style_twin(ax3, color=_OP_COLORS["tes"])

    # daily time ticks (0, 24, 48, ...), thinned out for long periods
    n_hours = len(result.time)
    n_days = math.ceil(n_hours / 24)
    step = 24 * math.ceil(n_days / _MAX_TIME_TICKS)
    ax1.set_xticks(range(0, n_hours + 1, step))

    return ax2, ax3, line1 + [fill] + line3 + line4


def plot_operational_strategy(
    result,
    file_name: Optional[str] = None,
    save_path: Optional[Union[str, Path]] = None,
    row_labels=None,
    col_labels=None,
    power_axis_max: Optional[float] = 3.0,
    energy_axis_max: Optional[float] = 8.5,
    dpi=None,
):
    """Plot price, demand, HTHP schedule and TES state of charge for one or
    several ``optimize_operational_strategy`` results, styled per
    ``PLOT_STYLE``.

    Each panel has three y axes: electricity price (left), thermal power of
    the heat demand and of the HTHP (right) and TES energy (further right, in
    the colour of the TES line). With several results the figure is a grid of
    subplots, one per result, in the order given, each labelled (a), (b),
    (c), ... plus its name.

    The figure has the fixed double paper width and the height adapts to the
    rows, titles and legend; the legend is above the panels.

    Parameters
    ----------
    result : OperationalStrategyResult, or list of them, or list of lists
        The object returned by ``optimize_operational_strategy``. Only
        its attributes are used (time, el_price, Q_demand, Q_HTHP,
        E_TES, plant, market) - no import of that class is needed here.
        - one result: single plot.
        - list of lists ``[[a, b], [c, d]]``: grid, one row per inner list
          (here a is top-left, b top-right, c bottom-left, d bottom-right).
        - flat list ``[a, b, c]``: one row of subplots.
        At most two columns. In a grid the price and time axes are shared
        (same period and market, so the panels are directly comparable); the
        thermal power and TES energy axes have the same range in every panel
        (see `power_axis_max` and `energy_axis_max`). Only the last column
        shows the right-hand axes.
    file_name : str, optional
        Name of the plant configuration, e.g. "standalone_base_recup_hthp".
        The figure is saved as ``<file_name>_operational_strategy.png``.
        Required when `save_path` is given.
    save_path : str | Path, optional
        Directory the figure is saved in (created if missing). If None,
        nothing is saved.
    row_labels, col_labels : list of str, optional
        Labels of the rows / columns of a grid; each panel is titled
        "(a) <column>" and, on a second line, "<row>" (keep the labels
        short: the panels are narrow). Defaults for a 2x2 grid: rows
        "Fixed demand" / "Variable demand", columns "Standalone" /
        "TES-Integrated". Without labels (other shapes) panels are titled
        just "(a)", "(b)", ...
    power_axis_max : float, optional
        Upper limit [MWth] of the thermal power axis, the same in every
        panel (default 3, so that the 1 MWth of the heat demand stays in the
        lower third of the panel, below the price curve). None: 3.
    energy_axis_max : float, optional
        Upper limit [MWhth] of the TES energy axis, the same in every panel
        (default 8.5). None: each panel is scaled to its own plant's TES
        capacity.
    dpi :
        Kept for compatibility and ignored: the resolution comes from
        PLOT_STYLE["figure"]["dpi"].

    Returns
    -------
    matplotlib.figure.Figure
    """

    # normalise the input to a grid of results: grid[row][col]
    if isinstance(result, (list, tuple)):
        if not result:
            raise ValueError("`result` is empty.")
        if isinstance(result[0], (list, tuple)):
            grid = [list(row) for row in result]
        else:
            grid = [list(result)]
    else:
        grid = [[result]]

    n_rows, n_cols = len(grid), len(grid[0])
    if any(len(row) != n_cols for row in grid):
        raise ValueError("All rows of `result` need the same number of results.")
    single = n_rows * n_cols == 1

    if (n_rows, n_cols) == (2, 2):
        row_labels = row_labels or ["Fixed demand", "Variable demand"]
        col_labels = col_labels or ["Standalone", "TES-Integrated"]
    if row_labels is not None and len(row_labels) != n_rows:
        raise ValueError("`row_labels` must have one label per row.")
    if col_labels is not None and len(col_labels) != n_cols:
        raise ValueError("`col_labels` must have one label per column.")

    # the 4 entries of the legend in one row
    n_entries = 4
    legend_cols = n_entries
    # titles with a second line when there is a row label
    title_lines = 0 if single else (2 if row_labels else 1)
    margins = PLOT_STYLE["figure"]["margins"]
    # the gap between rows holds the title of the lower row
    row_gap = (
        margins["title"] + (max(title_lines, 1) - 1) * margins["title_line"] + 0.12
    )

    fig, axes = create_figure(
        n_cols=n_cols,
        n_rows=n_rows,
        aspect=_ASPECT if n_cols == 2 else _ASPECT_SINGLE,
        fill_width=True,
        width="double",
        legend_rows=math.ceil(n_entries / legend_cols),
        titles=title_lines,
        right_extra=_RIGHT_EXTRA,
        col_gap=_COL_GAP,
        row_gap=row_gap,
    )
    axes = np.asarray(axes, dtype=object).reshape(n_rows, n_cols)

    # price and time axes shared between the panels
    for r in range(n_rows):
        for c in range(n_cols):
            if (r, c) != (0, 0):
                axes[r, c].sharex(axes[0, 0])
                axes[r, c].sharey(axes[0, 0])

    handles = None
    for r in range(n_rows):
        for c in range(n_cols):
            ax1 = axes[r, c]
            ax2, ax3, panel_handles = _draw_operational_strategy(
                ax1, grid[r][c], power_axis_max, energy_axis_max
            )
            handles = handles or panel_handles

            if r == n_rows - 1:
                ax1.set_xlabel("Time [h]")
            else:
                ax1.tick_params(labelbottom=False)
            if c == 0:
                ax1.set_ylabel("Electricity price [€/MWh]")
            else:
                ax1.tick_params(labelleft=False)
            if c == n_cols - 1:
                ax2.set_ylabel(r"Thermal power [$\mathrm{MW_{th}}$]")
                ax3.set_ylabel(
                    r"TES energy [$\mathrm{MWh_{th}}$]",
                    color=_OP_COLORS["tes"],
                    labelpad=4,
                )
            else:
                # right-hand axes only on the last column
                ax2.tick_params(labelright=False, right=False)
                ax3.tick_params(labelright=False, right=False)
                ax3.spines["right"].set_visible(False)

            if not single:
                letter = f"({chr(ord('a') + r * n_cols + c)})"
                first = f"{letter} {col_labels[c]}" if col_labels else letter
                title = f"{first}\n{row_labels[r]}" if row_labels else first
                ax1.set_title(title, pad=4)

    labels = [h.get_label() for h in handles]
    add_legend(fig, handles, labels, ncol=legend_cols, **_LEGEND_STYLE)

    if save_path is not None:
        if file_name is None:
            raise ValueError("`file_name` is required when `save_path` is given.")
        save_figure(fig, save_path, f"{file_name}_operational_strategy")

    return fig
