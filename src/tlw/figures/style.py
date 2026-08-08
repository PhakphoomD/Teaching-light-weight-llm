"""The one place look-and-feel is decided, so it cannot drift figure to figure.

Two rules that shaped this module:

**No titles on the plot.** A short on-chart title ("Two testbeds") is unreadable
to someone opening the file cold, and the journal convention puts the title in
the caption anyway. Panels carry axis labels and, when there is more than one,
a bare `(a)` / `(b)` tag. Everything else -- what was tested, on what, and what
came out -- lives in the caption below, which is generated from the same call
that saves the figure so the two can never separate.

**Every figure renders light and dark.** The previous version saved with a hard
white background, which is a white slab in a dark README. A figure is built by
a function and that function is called once per theme, so the two variants are
the same code rather than a light one and a hand-patched dark one.

Palette is Okabe-Ito, chosen because it stays distinguishable under all three
common colour-vision deficiencies. Hues are semantic and fixed: gray is always
the baseline / the "before", blue is the change under test, green a confirmed
gain, vermillion a regression, sky an intermediate rung of a ladder.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
FIGDIR = ROOT / "reports" / "figures"
TABDIR = ROOT / "reports" / "tables"

# Okabe-Ito. Identical in both themes: these are mid-lightness, mid-chroma hues
# that hold their identity against a white or a near-black surface.
BLUE = "#0072B2"  # the condition under test
GREEN = "#009E73"  # a confirmed gain
VERM = "#D55E00"  # a regression / a negative result
SKY = "#56B4E9"  # an intermediate rung
AMBER = "#E69F00"  # a prediction, or a bound
PURPLE = "#CC79A7"  # a fourth series, used sparingly


@dataclass(frozen=True)
class Theme:
    name: str
    face: str
    ink: str  # primary text
    muted: str  # axis ticks, secondary labels
    grid: str
    baseline: str  # the "before" / untreated series
    zero: str  # the no-effect rule on a difference axis


THEMES: Dict[str, Theme] = {
    "light": Theme(
        name="light",
        face="#ffffff",
        ink="#1a1a1a",
        muted="#5c5c5c",
        grid="#e8e8e8",
        baseline="#9a9a9a",
        zero="#3d3d3d",
    ),
    "dark": Theme(
        name="dark",
        face="#0d1117",  # GitHub's dark canvas, so a README figure sits flush
        ink="#e6edf3",
        muted="#9198a1",
        grid="#22272e",
        baseline="#6e7681",
        zero="#b1bac4",
    ),
}

_active: Theme = THEMES["light"]


def active() -> Theme:
    """The theme the figure currently being built is rendering for."""
    return _active


@contextmanager
def theme(name: str) -> Iterator[Theme]:
    global _active
    previous, _active = _active, THEMES[name]
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 150,
            "font.size": 10.5,
            "figure.facecolor": _active.face,
            "axes.facecolor": _active.face,
            "savefig.facecolor": _active.face,
            "text.color": _active.ink,
            "axes.labelcolor": _active.ink,
            "axes.labelsize": 10.5,
            "axes.edgecolor": _active.grid,
            "axes.linewidth": 0.8,
            "axes.grid": True,
            "axes.axisbelow": True,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "grid.color": _active.grid,
            "grid.linewidth": 0.8,
            "grid.linestyle": "-",  # never dashed: a dashed grid reads as a threshold
            "xtick.color": _active.muted,
            "ytick.color": _active.muted,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "legend.frameon": False,
            "legend.fontsize": 9.5,
            "legend.labelcolor": _active.ink,
        }
    )
    try:
        yield _active
    finally:
        _active = previous


# --------------------------------------------------------------------------
# output + the caption registry
# --------------------------------------------------------------------------

Caption = Tuple[str, str, str, str]  # (objective, slug, title, body)
_figures: List[Caption] = []
_tables: List[Caption] = []

# Words the slug spells lowercase that a reader expects to see cased.
_ACRONYMS = {
    "medquad": "MedQuAD", "wixqa": "WixQA", "rag": "RAG", "lora": "LoRA",
    "v1": "V1", "bge": "BGE", "apa": "APA", "vs": "vs",
}
_MINOR = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with"}


def apa_label(slug: str) -> Tuple[str, str]:
    """`tab-06-medquad-rag-results` -> ("Table 6", "MedQuAD RAG Results").

    APA 7 numbers a table or figure and gives it a short title in title case;
    the interpretation goes in a *Note* underneath. The slug already carries
    both, so deriving them here means the label can never disagree with the
    filename -- which is the failure a hand-written title invites.
    """
    kind, number, *rest = slug.split("-")
    label = f"{'Figure' if kind == 'fig' else 'Table'} {int(number)}"
    words = []
    for i, word in enumerate(rest):
        if word in _ACRONYMS:
            words.append(_ACRONYMS[word])
        elif word in _MINOR and i not in (0, len(rest) - 1):
            words.append(word)
        else:
            words.append(word.capitalize())
    return label, " ".join(words)


def render(build: Callable[[], "plt.Figure"], slug: str, objective: str, title: str, body: str) -> None:
    """Build the figure once per theme, save four files, record the caption.

    `title` is the one-line claim the figure makes; `body` says what was
    tested, what was measured (with n), what came out (with interval), and
    where the number came from. Neither is drawn on the plot.
    """
    FIGDIR.mkdir(parents=True, exist_ok=True)
    for name in ("light", "dark"):
        with theme(name):
            fig = build()
            suffix = "" if name == "light" else "-dark"
            for ext in ("png", "svg"):
                fig.savefig(FIGDIR / f"{slug}{suffix}.{ext}", bbox_inches="tight")
            plt.close(fig)
    _figures.append((objective, slug, title, body))
    print(f"  fig  {slug}")


def write_table(slug: str, objective: str, title: str, body: str, markdown: str) -> None:
    """Write one table in APA 7 shape: the number, an italic title, the table
    itself, then a *Note* carrying the claim and where the numbers came from."""
    TABDIR.mkdir(parents=True, exist_ok=True)
    label, apa_title = apa_label(slug)
    header = f"**{label}**\n\n*{apa_title}*\n\n"
    note = f"\n\n*Note.* {title} {body}\n"
    (TABDIR / f"{slug}.md").write_text(header + markdown.rstrip() + note, encoding="utf-8")
    _tables.append((objective, slug, title, body))
    print(f"  tbl  {slug}")


def figures() -> List[Caption]:
    return list(_figures)


def tables() -> List[Caption]:
    return list(_tables)


# --------------------------------------------------------------------------
# small shared helpers
# --------------------------------------------------------------------------


def panel_tag(ax, text: str) -> None:
    """`(a)` / `(b)` in the corner. Multi-panel figures need to be referable
    from the caption; they do not need a descriptive heading each."""
    ax.text(
        -0.02,
        1.06,
        text,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        color=active().muted,
    )


def strip_spines(ax, keep: Tuple[str, ...] = ("left", "bottom")) -> None:
    for side, spine in ax.spines.items():
        spine.set_visible(side in keep)


def annotate(ax, x: float, y: float, text: str, *, color: str | None = None, **kwargs) -> None:
    ax.annotate(
        text,
        (x, y),
        color=color or active().ink,
        fontsize=9.5,
        **kwargs,
    )
