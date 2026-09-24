"""
economic_plotting.py

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


def plot_operational_strategy(
    result,
    save_path: Optional[Union[str, Path]] = None,
):
    """Plot price, demand, HTHP schedule and TES state of charge for one
    ``optimize_operational_strategy`` result, styled per ``PLOT_STYLE``.

    Parameters
    ----------
    result : OperationalStrategyResult
        The object returned by ``optimize_operational_strategy``. Only
        its attributes are used (time, el_price, Q_demand, Q_HTHP,
        E_TES, plant, market) - no import of that class is needed here.
    save_path : str | Path, optional
        If given, the figure is saved there (dpi and facecolor per
        ``PLOT_STYLE["figure"]``).

    Returns
    -------
    matplotlib.figure.Figure
    """

    t = list(range(len(result.time)))
    E_TES_MAX = _plant_E_TES(result.plant)

    fig, ax1 = plt.subplots(
        figsize=_FIGSIZE,
        dpi=PLOT_STYLE["figure"]["dpi"],
        facecolor=PLOT_STYLE["figure"]["facecolor"],
    )

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
    ax1.set_xlabel("Time [h]", fontsize=_FONTS["label"])
    ax1.set_ylabel("Electricity price [€/MWh]", fontsize=_FONTS["label"])
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

    ax2.set_ylabel("Power / TES energy [MWth / MWhth]", fontsize=_FONTS["label"])
    ax2.set_ylim(0, max(E_TES_MAX, 1.2))
    _style_axes(ax2)

    line2 = ax2.collections[-1]
    lines = line1 + [line2] + line3 + line4
    labels = [line.get_label() for line in lines]
    ax1.legend(lines, labels, loc="upper left", fontsize=_FONTS["legend"])

    fig.suptitle(
        f"Optimal HTHP-TES Scheduling ({result.market})",
        fontsize=_FONTS["title"],
    )
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(
            save_path,
            dpi=PLOT_STYLE["figure"]["dpi"],
            bbox_inches="tight",
            facecolor=PLOT_STYLE["figure"]["facecolor"],
        )

    return fig
