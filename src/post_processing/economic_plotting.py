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

_STYLE_WIDTH, _STYLE_HEIGHT = PLOT_STYLE["figure"]["figsize"]
_FIGSIZE = (_STYLE_WIDTH * 2, _STYLE_HEIGHT)


def _plant_E_TES(plant) -> float:
    """Read the TES capacity off `result.plant`, which may be a `Plant`
    dataclass instance or a plain dict - without needing to import the
    `Plant` type from `plant_operation`."""

    if isinstance(plant, dict):
        return float(plant["E_TES"])
    return float(plant.E_TES)


def _style_axes(ax) -> None:
    """Apply the shared grid / spine / tick styling to one axes."""

    ax.grid(
        True,
        color=_GRID["color"],
        linestyle=_GRID["linestyle"],
        linewidth=_GRID["linewidth"],
        alpha=_GRID["alpha"],
    )
    ax.set_facecolor(_AXES["facecolor"])
    for spine in ax.spines.values():
        spine.set_color(_AXES["spine_color"])
        spine.set_linewidth(_AXES["spine_linewidth"])
    ax.tick_params(
        axis=_TICKS["axis"],
        which=_TICKS["which"],
        pad=_TICKS["pad"],
        color=_TICKS["color"],
        labelcolor=_TICKS["labelcolor"],
        direction=_TICKS["direction"],
        labelsize=_FONTS["tick"],
    )


def _draw_operational_strategy(ax1, result, power_axis_max=None):
    """Draw price, demand, HTHP schedule and TES state of charge of one
    result on `ax1` (price, left axis) and on a twin axis (power / energy,
    right). The right axis runs from 0 to `power_axis_max` (default: the
    plant's TES capacity, at least 1.2). Returns (ax2, legend handles)."""

    t = list(range(len(result.time)))
    E_TES_MAX = _plant_E_TES(result.plant)

    line1 = ax1.step(
        t,
        result.el_price,
        where="post",
        color=_COLORS["reference"],
        linewidth=_LINEWIDTH,
        linestyle="--",
        label="Electricity price",
        zorder=3,
    )
    _style_axes(ax1)

    ax2 = ax1.twinx()

    ax2.fill_between(
        t,
        result.Q_demand,
        step="post",
        color=_COLORS["process"],
        alpha=0.25,
        label=r"$Q_{\mathrm{demand}}$",
        zorder=1,
    )

    line3 = ax2.step(
        t,
        result.Q_HTHP,
        where="post",
        color=_COLORS["fuel"],
        linewidth=_LINEWIDTH,
        linestyle="-",
        label=r"$Q_{\mathrm{HTHP}}$",
        zorder=3,
    )

    line4 = ax2.plot(
        range(len(result.E_TES)),
        result.E_TES,
        color=_COLORS["product"],
        linewidth=_LINEWIDTH,
        label=r"$E_{\mathrm{TES}}$",
        zorder=2,
    )

    ax2.set_ylim(
        0, power_axis_max if power_axis_max is not None else max(E_TES_MAX, 1.2)
    )
    _style_axes(ax2)

    line2 = ax2.collections[-1]
    return ax2, line1 + [line2] + line3 + line4


def plot_operational_strategy(
    result,
    file_name: Optional[str] = None,
    save_path: Optional[Union[str, Path]] = None,
    row_labels=None,
    col_labels=None,
    power_axis_max: Optional[float] = 8.5,
):
    """Plot price, demand, HTHP schedule and TES state of charge for one or
    several ``optimize_operational_strategy`` results, styled per
    ``PLOT_STYLE``.

    With one result the figure is a single plot. With several results the
    figure is a grid of subplots, one per result, in the order given.

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
        market, so the panels are directly comparable); the power / energy
        axis has the same range in every panel (see `power_axis_max`).
    file_name : str, optional
        Name of the plant configuration, e.g. "standalone_base_recup_hthp".
        The figure is saved as ``<file_name>_operational_strategy.png``.
        Required when `save_path` is given.
    save_path : str | Path, optional
        Directory the figure is saved in (created if missing; dpi and
        facecolor per ``PLOT_STYLE["figure"]``). If None, nothing is saved.
    row_labels, col_labels : list of str, optional
        Labels of the rows / columns of a grid; each panel is titled
        "<column> - <row>". Defaults for a 2x2 grid: rows "Fixed heat
        demand" / "Free heat demand", columns "Standalone" /
        "TES-Integrated". Without labels (other shapes) panels are untitled.
    power_axis_max : float, optional
        Upper limit [MWth / MWhth] of the power / TES energy axis, the same
        in every panel (and in the single plot), so all figures are directly
        comparable (default 8.5). None: each panel is scaled to its own
        plant's TES capacity.

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
        row_labels = row_labels or ["Fixed heat demand", "Free heat demand"]
        col_labels = col_labels or ["Standalone", "TES-Integrated"]
    if row_labels is not None and len(row_labels) != n_rows:
        raise ValueError("`row_labels` must have one label per row.")
    if col_labels is not None and len(col_labels) != n_cols:
        raise ValueError("`col_labels` must have one label per column.")

    figsize = (
        _FIGSIZE if single else (_STYLE_WIDTH * 1.25 * n_cols, _STYLE_HEIGHT * n_rows)
    )
    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=figsize,
        dpi=PLOT_STYLE["figure"]["dpi"],
        facecolor=PLOT_STYLE["figure"]["facecolor"],
        sharex=True,
        sharey=True,
        squeeze=False,
    )

    handles = None
    for r in range(n_rows):
        for c in range(n_cols):
            ax1 = axes[r, c]
            ax2, panel_handles = _draw_operational_strategy(
                ax1, grid[r][c], power_axis_max
            )
            handles = handles or panel_handles

            if r == n_rows - 1:
                ax1.set_xlabel("Time [h]", fontsize=_FONTS["label"])
            if c == 0:
                ax1.set_ylabel("Electricity price [€/MWh]", fontsize=_FONTS["label"])
            if c == n_cols - 1:
                ax2.set_ylabel(
                    "Power / TES energy [MWth / MWhth]", fontsize=_FONTS["label"]
                )

            title = " - ".join(
                x
                for x in (
                    col_labels[c] if col_labels else None,
                    row_labels[r] if row_labels else None,
                )
                if x
            )
            if title:
                ax1.set_title(title, fontsize=_FONTS["label"])

    labels = [h.get_label() for h in handles]
    if single:
        axes[0, 0].legend(handles, labels, loc="upper left", fontsize=_FONTS["legend"])
    else:
        fig.legend(
            handles,
            labels,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.0),
            ncol=len(handles),
            fontsize=_FONTS["legend"],
            framealpha=0.95,
        )

    fig.suptitle(
        f"Optimal HTHP-TES Scheduling ({grid[0][0].market})",
        fontsize=_FONTS["title"],
    )
    if single:
        fig.tight_layout()
    else:
        fig.tight_layout(rect=(0, 0.05, 1, 0.97))

    if save_path is not None:
        if file_name is None:
            raise ValueError("`file_name` is required when `save_path` is given.")
        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            save_path / f"{file_name}_operational_strategy.png",
            dpi=PLOT_STYLE["figure"]["dpi"],
            bbox_inches="tight",
            facecolor=PLOT_STYLE["figure"]["facecolor"],
        )
        print(f"✓ Figure saved: {save_path / f'{file_name}_operational_strategy.png'}")

    return fig
