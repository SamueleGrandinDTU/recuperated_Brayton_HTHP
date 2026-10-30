"""
src/plotting.py

Plotting helpers for the results of ``plant_operation.optimize_operational_strategy``.


"""

from pathlib import Path
from typing import Optional, Union

import matplotlib.pyplot as plt

from src import PLOT_STYLE

_COLORS = PLOT_STYLE["colors"]
_FONTS = PLOT_STYLE["fonts"]
_GRID = PLOT_STYLE["grid"]
_AXES = PLOT_STYLE["axes"]
_TICKS = PLOT_STYLE["ticks"]
_LINEWIDTH = PLOT_STYLE["lines_and_markers"]["linewidth"]

# Colors, font sizes and layout of this figure (PLOT_STYLE["operational_strategy"]).
# The fonts are larger than the project-wide ones because the figure is large
# and gets scaled down to the width of a journal page.
_OP = PLOT_STYLE["operational_strategy"]
_OP_COLORS = _OP["colors"]
_OP_FONTS = _OP["fonts"]
_TES_AXIS_OFFSET = _OP["tes_axis_offset"]

_STYLE_WIDTH, _STYLE_HEIGHT = PLOT_STYLE["figure"]["figsize"]
_FIGSIZE = (_STYLE_WIDTH * 2.1, _STYLE_HEIGHT)

# Resolution of the operational strategy figure (higher than the project-wide
# PLOT_STYLE dpi, which is tuned for the compact diagrams).
_DPI = 300

# The time axis is labelled every 24 h (daily) as long as the period is at
# most this many days long; longer periods keep matplotlib's automatic ticks.
_MAX_DAILY_TICK_DAYS = 14


def _plant_E_TES(plant) -> float:
    """Read the TES capacity off `result.plant`, which may be a `Plant`
    dataclass instance or a plain dict - without needing to import the
    `Plant` type from `plant_operation`."""

    if isinstance(plant, dict):
        return float(plant["E_TES"])
    return float(plant.E_TES)


def _style_axes(ax, grid=True, color=None) -> None:
    """Apply the shared grid / spine / tick styling to one axes. `color`
    (optional) colours the right spine, ticks and tick labels."""

    if grid:
        ax.grid(
            True,
            color=_GRID["color"],
            linestyle=_GRID["linestyle"],
            linewidth=_GRID["linewidth"],
            alpha=_GRID["alpha"],
        )
    else:
        ax.grid(False)
    ax.set_facecolor(_AXES["facecolor"])
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
        labelsize=_OP_FONTS["tick"],
    )
    if color is not None:
        ax.spines["right"].set_color(color)
        ax.spines["right"].set_linewidth(1.5)


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
        linewidth=_LINEWIDTH + 0.6,
        linestyle="--",
        label="Electricity price",
        zorder=3,
    )
    _style_axes(ax1)

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
        linewidth=_LINEWIDTH + 0.6,
        linestyle="-",
        label=r"$\dot{Q}_{\mathrm{HTHP}}$",
        zorder=3,
    )

    ax2.set_ylim(0, power_axis_max if power_axis_max is not None else 3.0)
    _style_axes(ax2, grid=False)

    # TES energy, on its own axis in the colour of its line
    ax3 = ax1.twinx()
    ax3.spines["right"].set_position(("axes", _TES_AXIS_OFFSET))
    ax3.set_frame_on(True)
    ax3.patch.set_visible(False)
    for side in ("top", "left", "bottom"):
        ax3.spines[side].set_visible(False)

    line4 = ax3.plot(
        range(len(result.E_TES)),
        result.E_TES,
        color=_OP_COLORS["tes"],
        linewidth=_LINEWIDTH + 0.6,
        label=r"$E_{\mathrm{TES}}$",
        zorder=2,
    )

    ax3.set_ylim(
        0,
        energy_axis_max if energy_axis_max is not None else max(E_TES_MAX * 1.06, 1.2),
    )
    _style_axes(ax3, grid=False, color=_OP_COLORS["tes"])

    # daily time ticks: 0, 24, 48, 72, ...
    n_hours = len(result.time)
    if n_hours <= 24 * _MAX_DAILY_TICK_DAYS:
        ax1.set_xticks(range(0, n_hours + 1, 24))

    return ax2, ax3, line1 + [fill] + line3 + line4


def plot_operational_strategy(
    result,
    file_name: Optional[str] = None,
    save_path: Optional[Union[str, Path]] = None,
    row_labels=None,
    col_labels=None,
    power_axis_max: Optional[float] = 3.0,
    energy_axis_max: Optional[float] = 8.5,
    dpi: int = _DPI,
):
    """Plot price, demand, HTHP schedule and TES state of charge for one or
    several ``optimize_operational_strategy`` results, styled per
    ``PLOT_STYLE``.

    Each panel has three y axes: electricity price (left), thermal power of
    the heat demand and of the HTHP (right) and TES energy (further right, in
    the colour of the TES line). With several results the figure is a grid of
    subplots, one per result, in the order given, each labelled (a), (b),
    (c), ... plus its name.

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
        In a grid the price and time axes are shared (same period and
        market, so the panels are directly comparable); the thermal power
        and TES energy axes have the same range in every panel (see
        `power_axis_max` and `energy_axis_max`). Only the last column shows
        the right-hand axes.
    file_name : str, optional
        Name of the plant configuration, e.g. "standalone_base_recup_hthp".
        The figure is saved as ``<file_name>_operational_strategy.png``.
        Required when `save_path` is given.
    save_path : str | Path, optional
        Directory the figure is saved in (created if missing; facecolor per
        ``PLOT_STYLE["figure"]``). If None, nothing is saved.
    row_labels, col_labels : list of str, optional
        Labels of the rows / columns of a grid; each panel is titled
        "(a) <column> - <row>". Defaults for a 2x2 grid: rows "Fixed heat
        demand schedule" / "Variable heat demand schedule", columns
        "Standalone" / "TES-Integrated". Without labels (other shapes) panels are titled
        just "(a)", "(b)", ...
    power_axis_max : float, optional
        Upper limit [MWth] of the thermal power axis, the same in every
        panel (default 3, so that the 1 MWth of the heat demand stays in the
        lower third of the panel, below the price curve). None: 3.
    energy_axis_max : float, optional
        Upper limit [MWhth] of the TES energy axis, the same in every panel
        (default 8.5). None: each panel is scaled to its own plant's TES
        capacity.
    dpi : int
        Resolution of the figure and of the saved file (default 300).

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
        row_labels = row_labels or [
            "Fixed heat demand schedule",
            "Variable heat demand schedule",
        ]
        col_labels = col_labels or ["Standalone", "TES-Integrated"]
    if row_labels is not None and len(row_labels) != n_rows:
        raise ValueError("`row_labels` must have one label per row.")
    if col_labels is not None and len(col_labels) != n_cols:
        raise ValueError("`col_labels` must have one label per column.")

    figsize = (
        _FIGSIZE if single else (_STYLE_WIDTH * 1.5 * n_cols, _STYLE_HEIGHT * n_rows)
    )
    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=figsize,
        dpi=dpi,
        facecolor=PLOT_STYLE["figure"]["facecolor"],
        sharex=True,
        sharey=True,
        squeeze=False,
    )

    handles = None
    for r in range(n_rows):
        for c in range(n_cols):
            ax1 = axes[r, c]
            ax2, ax3, panel_handles = _draw_operational_strategy(
                ax1, grid[r][c], power_axis_max, energy_axis_max
            )
            handles = handles or panel_handles

            if r == n_rows - 1:
                ax1.set_xlabel("Time [h]", fontsize=_OP_FONTS["label"])
            if c == 0:
                ax1.set_ylabel("Electricity price [€/MWh]", fontsize=_OP_FONTS["label"])
            if c == n_cols - 1:
                ax2.set_ylabel(
                    r"Thermal power [$\mathrm{MW_{th}}$]",
                    fontsize=_OP_FONTS["label"],
                )
                ax3.set_ylabel(
                    r"TES energy [$\mathrm{MWh_{th}}$]",
                    fontsize=_OP_FONTS["label"],
                    color=_OP_COLORS["tes"],
                    labelpad=8,
                )
            else:
                # right-hand axes only on the last column
                ax2.tick_params(labelright=False, right=False)
                ax3.tick_params(labelright=False, right=False)
                ax3.spines["right"].set_visible(False)

            if not single:
                letter = f"({chr(ord('a') + r * n_cols + c)})"
                name = " - ".join(
                    x
                    for x in (
                        col_labels[c] if col_labels else None,
                        row_labels[r] if row_labels else None,
                    )
                    if x
                )
                ax1.set_title(
                    f"{letter} {name}" if name else letter, fontsize=_FONTS["title"]
                )

    labels = [h.get_label() for h in handles]
    legend_style = dict(
        fontsize=_OP_FONTS["legend"],
        framealpha=0.95,
        handlelength=2.6,
        columnspacing=2.0,
    )
    if single:
        axes[0, 0].legend(handles, labels, loc="upper left", **legend_style)
        fig.tight_layout()
    else:
        fig.legend(
            handles,
            labels,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.0),
            ncol=len(handles),
            **legend_style,
        )
        fig.tight_layout(rect=(0, 0.07, 1, 1))

    if save_path is not None:
        if file_name is None:
            raise ValueError("`file_name` is required when `save_path` is given.")
        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            save_path / f"{file_name}_operational_strategy.png",
            dpi=dpi,
            bbox_inches="tight",
            facecolor=PLOT_STYLE["figure"]["facecolor"],
        )
        print(f"✓ Figure saved: {save_path / f'{file_name}_operational_strategy.png'}")

    return fig
