"""Grounding-window behaviour — the Stage-1 lever.

These are the properties the +0.130 result depends on. They run offline with a
synthetic article; nothing here needs the WixQA data or a GPU.
"""

from __future__ import annotations

import pytest

from src.tlw.wixqa.grounding import (
    DEFAULT_GROUNDING,
    GROUNDINGS,
    grounding_block,
    window,
)


def _article(words: int, title: str = "Wix Stores: Shipping") -> dict:
    return {"id": "a1", "title": title,
            "contents": " ".join(f"w{i}" for i in range(words))}


def test_head_window_takes_the_start_of_the_article():
    art = _article(500)
    got = window(art, 100)
    assert got == art["contents"][:100]
    assert got.startswith("w0 ")


def test_head_window_of_a_short_article_returns_all_of_it():
    art = _article(3)
    assert window(art, 10_000) == art["contents"]


def test_chunk_centred_window_is_centred_on_the_match_not_the_head():
    """The whole point of chunk-centring: a match at word 400 must not return
    the article head, which is what was doing."""
    art = _article(1000)
    centred = window(art, 900, centre_word=400)
    assert "w400" in centred
    assert not centred.startswith("w0 ")


def test_chunk_centred_window_clips_at_the_start():
    art = _article(1000)
    assert window(art, 900, centre_word=0).startswith("w0 ")


def test_chunk_centred_window_clips_at_the_end_and_stays_full_length():
    """A match near the end must still yield a full-width window, not a stub."""
    art = _article(1000)
    at_end = window(art, 900, centre_word=999)
    middle = window(art, 900, centre_word=500)
    assert at_end.endswith("w999")
    assert len(at_end.split()) == len(middle.split())


@pytest.mark.parametrize("name,budget,centred", [
    ("head900", 900, False), ("chunk900", 900, True),
    ("head2400", 2400, False), ("chunk2400", 2400, True),
])
def test_grounding_table_is_the_published_2x2(name, budget, centred):
    """head900 is the control arm of a published comparison; changing any of
    these silently redefines what a reported number means."""
    assert GROUNDINGS[name] == (budget, centred)


def test_default_grounding_is_the_stage1_winner():
    assert DEFAULT_GROUNDING == "chunk2400"


def test_wider_budget_never_shows_less_of_the_article():
    art = _article(2000)
    assert len(window(art, 2400)) > len(window(art, 900))


def test_block_is_numbered_and_titled_in_the_published_shape():
    arts = [_article(50, "First"), _article(50, "Second")]
    arts[1]["id"] = "a2"
    block = grounding_block(arts, 900)
    assert block.startswith("[1] First\n")
    assert "\n\n[2] Second\n" in block


def test_block_uses_the_matched_chunk_when_offsets_are_supplied():
    art = _article(1000)
    without = grounding_block([art], 900)
    with_offset = grounding_block([art], 900, offsets={"a1": 400})
    assert without != with_offset
    assert "w400" in with_offset
