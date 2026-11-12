"""Figure factory: fixed paper width, height that adapts to the content.

Widths, axes size and margins are read from PLOT_STYLE (plot_style.json); the
fonts are the global defaults set by plot_style.py. All the diagrams are
squares of the same size, whatever the legends, labels or titles around them.

Usage in a plotting function
----------------------------
    fig, axes = create_figure(n_cols=2, legend_rows=1)    # two square panels
    ...plot on axes[0], axes[1]...
    add_legend(fig, handles, ncol=len(handles))            # in the top margin
    if save_path is not None:
        save_figure(fig, save_path, f"{file_name}_lcoh_breakdown")
"""

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def _get_style(style=None):
    """PLOT_STYLE, imported lazily to avoid circular imports."""
    if style is not None:
        return style
    from src import PLOT_STYLE

    return PLOT_STYLE


def style_axes(ax, style=None):
    """Grid, spines, ticks and background of one axes (from PLOT_STYLE)."""
    style = _get_style(style)
    grid, axes, ticks = style["grid"], style["axes"], style["ticks"]
    ax.set_facecolor(axes["facecolor"])
    ax.grid(
        axis="y",
        alpha=grid["alpha"],
        linestyle="--",
        linewidth=grid["linewidth"],
    )
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color(axes["spine_color"])
        spine.set_linewidth(axes["spine_linewidth"])
    ax.tick_params(
        axis=ticks["axis"],
        which=ticks["which"],
        pad=ticks["pad"],
        color=ticks["color"],
        labelcolor=ticks["labelcolor"],
        direction=ticks["direction"],
    )


def create_figure(
    n_cols=1,
    n_rows=1,
    aspect=1.0,
    fill_width=False,
    legend_rows=0,
    titles=False,
    bottom_extra=0.0,
    right_extra=0.0,
    col_gap=None,
    row_gap=None,
    width=None,
    style=None,
):
    """Figure of fixed width whose height adapts to the content.

    The width is PLOT_STYLE["figure"]["width_single"] (one column of panels)
    or ["width_double"] (two columns). The axes are placed explicitly, in
    inches, so their size never depends on tick labels, legends or titles.

    Parameters
    ----------
    n_cols, n_rows : int
        Panels per row (1 or 2) and number of rows.
    aspect : float
        Axes height / axes width. 1 = square (all the diagrams).
    fill_width : bool
        False (default): every axes is "axes_size" wide and the gap between
        columns takes the rest of the width. True: the axes fill the width
        (e.g. the operational strategy plot, whose axes are not squares).
    legend_rows : int
        Rows of the legend placed above the axes (see `add_legend`); adds
        that much height at the top.
    titles : bool or int
        True if the panels have a title ("(a) DK1"): adds the room for it
        between the axes and the legend. An int is the number of lines of
        the titles (True = 1).
    bottom_extra : float
        Extra room below the axes [in], e.g. for rotated tick labels.
    right_extra : float
        Extra room to the right of the last column [in], e.g. for twin axes.
    col_gap, row_gap : float, optional
        Override the gap between columns / rows [in].
    width : "single" | "double", optional
        Paper width. Default: "single" for one column, "double" for two.
        Only for figures that need more room than their columns suggest
        (e.g. the operational strategy plot, with three y axes).

    Returns
    -------
    fig, axes
        `axes` follows the plt.subplots(squeeze=True) convention: one Axes
        for a 1x1 grid, a 1D array for one row or one column, otherwise a 2D
        array [row, column].
    """
    style = _get_style(style)
    cfg = style["figure"]
    m = cfg["margins"]

    if n_cols not in (1, 2):
        raise ValueError("`n_cols` must be 1 or 2 (paper widths: single, double).")
    if width is None:
        width = "single" if n_cols == 1 else "double"
    if width not in ("single", "double"):
        raise ValueError('`width` must be "single" or "double".')
    width = cfg["width_single"] if width == "single" else cfg["width_double"]

    left = m["left"]
    right = m["right"] + right_extra
    row_gap = m["row_gap"] if row_gap is None else row_gap

    if fill_width:
        col_gap = m["col_gap_min"] if col_gap is None else col_gap
        ax_w = (width - left - right - (n_cols - 1) * col_gap) / n_cols
    else:
        # side of the square axes; one size for single-column figures and one
        # for double-column ones (the double width limits how large it can be)
        ax_w = cfg.get(
            "axes_size_single" if n_cols == 1 else "axes_size_double",
            cfg["axes_size"],
        )
        free = width - left - right - n_cols * ax_w
        if n_cols == 1:
            col_gap = 0.0
            if free < 0:
                raise ValueError(
                    f"axes_size {ax_w} in does not fit in the {width} in width."
                )
        else:
            col_gap = free / (n_cols - 1) if col_gap is None else col_gap
            if col_gap < m["col_gap_min"]:
                raise ValueError(
                    f"The gap between the columns would be {col_gap:.2f} in "
                    f"(< col_gap_min {m['col_gap_min']} in): reduce axes_size "
                    "or the margins in plot_style.json."
                )
    ax_h = aspect * ax_w

    title_lines = 1 if titles is True else int(titles)
    title_strip = (
        m["title"] + (title_lines - 1) * m["title_line"] if title_lines else 0.0
    )
    top = m["top"] + legend_rows * m["legend_row"] + title_strip
    bottom = m["bottom"] + bottom_extra
    height = bottom + n_rows * ax_h + (n_rows - 1) * row_gap + top

    fig = plt.figure(
        figsize=(width, height),
        dpi=cfg["dpi"],
        facecolor=cfg["facecolor"],
    )

    axes = np.empty((n_rows, n_cols), dtype=object)
    for r in range(n_rows):
        y0 = height - top - (r + 1) * ax_h - r * row_gap
        for c in range(n_cols):
            x0 = left + c * (ax_w + col_gap)
            ax = fig.add_axes([x0 / width, y0 / height, ax_w / width, ax_h / height])
            style_axes(ax, style)
            axes[r, c] = ax

    fig._layout_in = {  # inches, for add_legend
        "width": width,
        "height": height,
        "title_strip": title_strip,
    }

    if n_rows == 1 and n_cols == 1:
        return fig, axes[0, 0]
    if n_rows == 1:
        return fig, axes[0]
    if n_cols == 1:
        return fig, axes[:, 0]
    return fig, axes


def add_legend(fig, handles, labels=None, ncol=None, ax=None, **kwargs):
    """Legend in the top margin of a figure made by create_figure.

    ax=None: centred at the top of the figure. ax given: centred above that
    axes (and above its title, if the figure has titles), so each panel can
    have its own legend.

    The `legend_rows` given to create_figure must be at least
    ceil(n_entries / ncol).
    """
    lay = fig._layout_in
    ncol = len(handles) if ncol is None else ncol
    if ax is None:
        loc = "upper center"
        anchor = (0.5, 1 - 0.05 / lay["height"])
    else:
        pos = ax.get_position()
        loc = "lower center"
        anchor = (
            pos.x0 + pos.width / 2,
            pos.y1 + (lay["title_strip"] + 0.04) / lay["height"],
        )
    legend_kwargs = dict(
        loc=loc,
        bbox_to_anchor=anchor,
        ncol=ncol,
        framealpha=0.95,
        borderpad=0.3,
        handlelength=1.2,
        columnspacing=1.0,
    )
    legend_kwargs.update(kwargs)
    if labels is None:
        leg = fig.legend(handles=handles, **legend_kwargs)
    else:
        leg = fig.legend(handles, labels, **legend_kwargs)

    # The legend may stick out of the axes, but never out of the figure:
    # if it does, shift it back inside the width.
    fig.canvas.draw()
    box = leg.get_window_extent().transformed(fig.transFigure.inverted())
    pad = 0.01
    shift = max(pad - box.x0, 0.0) - max(box.x1 - (1 - pad), 0.0)
    if shift:
        x, y = legend_kwargs["bbox_to_anchor"]
        leg.set_bbox_to_anchor((x + shift, y), transform=fig.transFigure)
    return leg


def save_figure(fig, save_path, file_name, style=None):
    """Save the figure as a PNG at its exact size (no bbox_inches="tight")."""
    style = _get_style(style)
    cfg = style["figure"]
    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)
    out = save_path / f"{file_name}.png"
    fig.savefig(out, dpi=cfg["dpi"], facecolor=cfg["facecolor"])
    print(f"✓ Figure saved: {out}")
