"""How much of a retrieved article reaches the prompt — the T3.14 Stage-1 lever.

This is the project's largest single finding, so it is worth stating plainly.
The original grounding showed the **first 900 characters** of each retrieved
article. Gold articles have a median length of 3,555 characters, so:

    92.5% of gold articles were truncated
    the student saw a median 25% of the gold article
    the shown text carried 36% of the expert answer's content words,
      while the full article carried 72%

"The gold article was retrieved" therefore did **not** mean "the answer is in the
prompt". Repairing that — a 2,400-character window centred on the chunk the
retriever actually matched — moved aggregate pass@>=3 from 0.340 to 0.470
(+0.130 [+0.072, +0.188], McNemar p = 3.5e-08) at zero inference cost, roughly
five times the entire retriever ladder's +0.025.

The 2x2 that isolates the two levers (offline, no LLM calls):

                   900 chars/article    2,400 chars/article
    article head   head900  0.412       head2400   0.612
    chunk-centred  chunk900 0.482       chunk2400  0.655   <- winner
    (numbers are the share of the expert answer's content words in context;
     the ceiling, the full gold article, is 0.726)

`chunk-centred` uses the retriever's own localisation: `bge_chunk` matches a
180-word chunk, so centring the window there instead of at the article head is
information we already had and were discarding.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np

from .retrieval import chunks_of, encode

#: Rough chars-per-word used to convert a character budget into a word window.
CHARS_PER_WORD = 5.5

#: The 2x2 grid: name -> (chars per article, centre on the matched chunk?).
#: `head900` is the ADR-030/T3.11 control and must not change — it defines the
#: baseline arm of a published comparison.
GROUNDINGS: Dict[str, Tuple[int, bool]] = {
    "head900": (900, False),
    "chunk900": (900, True),
    "head2400": (2400, False),
    "chunk2400": (2400, True),
}

#: What the runs after T3.14 Stage 1 should use.
DEFAULT_GROUNDING = "chunk2400"


def window(article: dict, budget_chars: int, centre_word: Optional[int] = None) -> str:
    """Render the grounding text for ONE article within a character budget.

    `centre_word=None` takes the article head (the original behaviour).
    Otherwise a word window of the same budget is centred on `centre_word` and
    clipped to the article, so a match near either end still yields a full window.
    """
    body = article.get("contents") or ""
    if centre_word is None:
        return body[:budget_chars]
    words = body.split()
    span = max(1, int(budget_chars / CHARS_PER_WORD))
    start = max(0, min(centre_word - span // 2, max(0, len(words) - span)))
    return " ".join(words[start:start + span])


def best_chunk_word_offset(article: dict, qvec: np.ndarray, enc: str = "bge") -> int:
    """Word offset of the article chunk that best matches the question vector."""
    chs = chunks_of(article)
    if len(chs) <= 1:
        return 0
    cv = encode(enc, chs, is_query=False)
    best = int(np.argmax(cv @ qvec))
    stride = 180 - 40  # CHUNK_WORDS - OVERLAP, matching retrieval.chunks_of
    return best * stride


def grounding_block(articles, budget_chars: int, offsets=None) -> str:
    """Render the full REFERENCE CONTEXT block for a set of retrieved articles.

    `offsets` maps an article id to a matched-chunk word offset; when it is None
    the article head is used. The `[n] Title` shape is part of the published
    prompt (ADR-030) — do not restyle it.
    """
    parts = []
    for k, art in enumerate(articles, start=1):
        centre = None if offsets is None else offsets.get(art["id"])
        parts.append(f"[{k}] {art.get('title', '')}\n{window(art, budget_chars, centre)}")
    return "\n\n".join(parts)


__all__ = [
    "CHARS_PER_WORD", "GROUNDINGS", "DEFAULT_GROUNDING",
    "window", "best_chunk_word_offset", "grounding_block",
]
