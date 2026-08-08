"""The five plot primitives the form rule maps onto.

The form is chosen from the data's shape, before colour and before layout:

    paired difference + CI ....... forest
    group proportions ............ dot_ci
    ordered ladder (>=3 points) .. ladder
    polarity about a baseline .... diverging
    before -> after, per item .... dumbbell

Differences are drawn as a point with its interval on a zero axis, not as a
bar. A bar encodes magnitude from zero, which a *difference* does not have --
and position along a common scale is the encoding people read most accurately,
so the interval, which is the actual result, stays legible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .style import BLUE, GREEN, SKY, VERM, active, strip_spines


@dataclass(frozen=True)
class Effect:
    """One measured difference: the estimate, its interval, and its label."""

    label: str
    value: float
    ci: Optional[Tuple[float, float]] = None
    color: Optional[str] = None
    note: str = ""  # p-value, n, or a caveat -- rendered right of the interval

    @property
    def crosses_zero(self) -> bool:
        return self.ci is None or (self.ci[0] <= 0.0 <= self.ci[1])


@dataclass(frozen=True)
class Level:
    """One measured proportion with its Wilson interval."""

    label: str
    value: float
    ci: Optional[Tuple[float, float]] = None
    color: Optional[str] = None
    note: str = ""


def effect_color(effect: Effect) -> str:
    """Colour carries the verdict, so a reader who skims the shapes still gets
    it right: a gain whose interval clears zero is green, a loss vermillion,
    and anything whose interval spans zero stays neutral -- an inconclusive
    result must not be dressed as a win."""
    if effect.color:
        return effect.color
    if effect.crosses_zero:
        return active().baseline
    return GREEN if effect.value > 0 else VERM


def forest(ax, effects: Sequence[Effect], *, xlabel: str, xlim: Optional[Tuple[float, float]] = None) -> None:
    """Differences on a zero axis, most-recent-first order preserved."""
    theme = active()
    ys = list(range(len(effects)))[::-1]

    ax.axvline(0.0, color=theme.zero, linewidth=1.0, zorder=1)
    for y, eff in zip(ys, effects):
        color = effect_color(eff)
        if eff.ci:
            ax.plot(eff.ci, [y, y], color=color, linewidth=2.0, solid_capstyle="round", zorder=2)
            for bound in eff.ci:
                ax.plot([bound], [y], marker="|", markersize=7, color=color, zorder=2)
        ax.plot([eff.value], [y], marker="o", markersize=7, color=color, zorder=3)

    ax.set_yticks(ys)
    ax.set_yticklabels([e.label for e in effects], color=theme.ink)
    ax.set_xlabel(xlabel)
    if xlim:
        ax.set_xlim(*xlim)
    ax.set_ylim(-0.7, len(effects) - 0.3)  # rows sit close; no drifting apart in a tall axes
    ax.grid(axis="y", visible=False)
    strip_spines(ax, keep=("bottom",))

    right = ax.get_xlim()[1]
    for y, eff in zip(ys, effects):
        text = f"{eff.value:+.3f}"
        if eff.ci:
            text += f"  [{eff.ci[0]:+.3f}, {eff.ci[1]:+.3f}]"
        if eff.note:
            text += f"   {eff.note}"
        ax.text(
            right + (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.03,
            y,
            text,
            va="center",
            fontsize=9,
            color=theme.muted if eff.crosses_zero else theme.ink,
        )


def dot_ci(
    ax,
    levels: Sequence[Level],
    *,
    xlabel: str,
    xlim: Tuple[float, float] = (0.0, 1.0),
    xticks: Optional[Sequence[float]] = None,
    show_values: bool = True,
) -> None:
    """Absolute levels with their intervals -- for arms, conditions, rungs.

    Values are written to the right of each interval rather than above the
    dot: stacked rows are close together, and a label above one row lands on
    top of the row above it.
    """
    theme = active()
    ys = list(range(len(levels)))[::-1]

    for y, lvl in zip(ys, levels):
        color = lvl.color or BLUE
        if lvl.ci:
            ax.plot(lvl.ci, [y, y], color=color, linewidth=2.0, solid_capstyle="round", zorder=2)
        ax.plot([lvl.value], [y], marker="o", markersize=7, color=color, zorder=3)

    ax.set_yticks(ys)
    ax.set_yticklabels([l.label for l in levels], color=theme.ink)
    ax.set_xlim(*xlim)
    if xticks is not None:
        ax.set_xticks(list(xticks))
    ax.set_xlabel(xlabel)
    ax.set_ylim(-0.7, len(levels) - 0.3)
    ax.grid(axis="y", visible=False)
    strip_spines(ax, keep=("bottom",))

    if show_values:
        span = xlim[1] - xlim[0]
        for y, lvl in zip(ys, levels):
            right = max(lvl.value, lvl.ci[1] if lvl.ci else lvl.value)
            ax.text(
                right + span * 0.03,
                y,
                f"{lvl.value:.3f}" + (f"   {lvl.note}" if lvl.note else ""),
                va="center",
                fontsize=9,
                color=theme.ink,
            )


def ladder(
    ax,
    xs: Sequence[float],
    ys: Sequence[float],
    labels: Sequence[str],
    *,
    xlabel: str,
    ylabel: str,
    predicted: Optional[Sequence[Optional[float]]] = None,
    colors: Optional[Sequence[str]] = None,
    label_offset: Tuple[float, float] = (0.0, 0.022),
    label_positions: Optional[Sequence[Tuple[float, float, str, str]]] = None,
) -> None:
    """An ordered progression: each rung contains the one before it.

    A predicted series, when supplied, is drawn as hollow amber markers so a
    reader can see the prediction and the outcome at once rather than being
    told in prose that they agreed.
    """
    theme = active()
    ax.plot(xs, ys, color=theme.baseline, linewidth=1.4, zorder=1)
    for i, (x, y, label) in enumerate(zip(xs, ys, labels)):
        color = (colors[i] if colors else None) or (BLUE if i == len(xs) - 1 else SKY)
        ax.plot([x], [y], marker="o", markersize=8, color=color, zorder=3)
        # Rungs of a ladder sit close together by construction, so a fixed
        # label offset makes adjacent labels collide. Callers may place each.
        dx, dy, ha, va = (
            label_positions[i] if label_positions else (*label_offset, "center", "bottom")
        )
        ax.text(
            x + dx,
            y + dy,
            f"{label}\n{y:.3f}",
            ha=ha,
            va=va,
            fontsize=9,
            color=theme.ink,
            linespacing=1.35,
        )
    if predicted:
        pxs = [x for x, p in zip(xs, predicted) if p is not None]
        pys = [p for p in predicted if p is not None]
        ax.plot(
            pxs,
            pys,
            linestyle="none",
            marker="o",
            markersize=11,
            markerfacecolor="none",
            markeredgecolor="#E69F00",
            markeredgewidth=1.6,
            zorder=2,
            label="predicted before the run",
        )
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)


def diverging(
    ax,
    labels: Sequence[str],
    values: Sequence[float],
    *,
    ylabel: str,
    notes: Optional[Sequence[str]] = None,
    colors: Optional[Sequence[str]] = None,
) -> None:
    """Movement above and below a no-change line, one bar per bucket.

    Used where the story is polarity rather than magnitude: an intervention
    that helps one group and taxes another nets to nothing, and a chart that
    shows only the net hides the whole mechanism.
    """
    theme = active()
    xs = list(range(len(labels)))
    bar_colors = list(colors) if colors else [GREEN if v > 0 else VERM if v < 0 else theme.baseline for v in values]

    ax.axhline(0.0, color=theme.zero, linewidth=1.0, zorder=2)
    ax.bar(xs, values, width=0.56, color=bar_colors, zorder=3)
    for x, v in zip(xs, values):
        ax.text(
            x,
            v + (0.012 if v >= 0 else -0.012),
            f"{v:+.2f}",
            ha="center",
            va="bottom" if v >= 0 else "top",
            fontsize=9.5,
            color=theme.ink,
        )
    if notes:
        low = ax.get_ylim()[0]
        for x, note in zip(xs, notes):
            ax.text(x, low, note, ha="center", va="bottom", fontsize=8.5, color=theme.muted)

    ax.set_xticks(xs)
    ax.set_xticklabels(labels, color=theme.ink)
    ax.set_ylabel(ylabel)
    ax.grid(axis="x", visible=False)
    strip_spines(ax, keep=("left",))


def dumbbell(
    ax,
    labels: Sequence[str],
    before: Sequence[float],
    after: Sequence[float],
    *,
    xlabel: str,
    before_label: str = "before",
    after_label: str = "after",
    after_color: str = BLUE,
    xlim: Optional[Tuple[float, float]] = None,
    fmt: str = "{:.3f}",
    legend_loc: str = "lower right",
) -> None:
    """Before and after for each item, joined -- so the size of each change is
    a length the reader can compare directly, and no item is averaged away."""
    theme = active()
    ys = list(range(len(labels)))[::-1]

    span = (xlim[1] - xlim[0]) if xlim else (max(after) - min(before)) or 1.0
    for y, b, a in zip(ys, before, after):
        ax.plot([b, a], [y, y], color=theme.baseline, linewidth=1.6, zorder=1, solid_capstyle="round")
        ax.plot([b], [y], marker="o", markersize=7.5, color=theme.baseline, zorder=3)
        ax.plot([a], [y], marker="o", markersize=7.5, color=after_color, zorder=3)
        # When the change is small the two markers overlap, and two centred
        # labels print on top of each other. Push them outward instead -- the
        # near-zero cases are exactly the ones a reader must be able to read.
        close = abs(a - b) < span * 0.10
        pad = span * 0.015
        ax.text(
            b - pad if close else b, y + 0.26, fmt.format(b),
            ha="right" if close else "center", va="bottom", fontsize=8.8, color=theme.muted,
        )
        ax.text(
            a + pad if close else a, y + 0.26, fmt.format(a),
            ha="left" if close else "center", va="bottom", fontsize=8.8, color=theme.ink,
        )

    ax.set_yticks(ys)
    ax.set_yticklabels(labels, color=theme.ink)
    ax.set_ylim(-0.7, len(labels) - 0.25)
    if xlim:
        ax.set_xlim(*xlim)
    ax.set_xlabel(xlabel)
    ax.grid(axis="y", visible=False)
    strip_spines(ax, keep=("bottom",))

    handles = [
        ax.plot([], [], marker="o", linestyle="none", color=theme.baseline, label=before_label)[0],
        ax.plot([], [], marker="o", linestyle="none", color=after_color, label=after_label)[0],
    ]
    ax.legend(handles=handles, loc=legend_loc)
