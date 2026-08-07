"""The controlled variables of the WixQA study, and the pure retrieval helpers.

Two kinds of test here:

1. **Guards on published constants.** The prompts, decoding settings and chunking
   parameters are what makes runs comparable across ADR-030..033. A test that
   pins them turns "please do not edit this" into something the suite enforces.
2. **Behaviour of the pure helpers** — chunking, RRF, hit-rate and the retrieval
   record. None of these need a model, the KB, or a GPU.
"""

from __future__ import annotations

import pytest

from src.tlw.wixqa import prompts
from src.tlw.wixqa.retrieval import (
    CHUNK_WORDS,
    ENCODERS,
    KS,
    OVERLAP,
    chunks_of,
    hitrate,
    retrieval_record,
    rrf,
)


# --- controlled variables ----------------------------------------------------

def test_decoding_settings_are_the_published_ones():
    assert prompts.TEMPERATURE == 0.3
    assert prompts.MAX_TOKENS == 256
    assert prompts.MAX_PASSAGE_CHARS == 900  # the head900 control arm


def test_judge_rubric_defines_all_five_grades():
    """The 0-4 scale is what PASS>=3 ("correct") and PASS>=4 ("complete") mean."""
    for grade in ("4 =", "3 =", "2 =", "1 =", "0 ="):
        assert grade in prompts.JUDGE_SYS
    assert "Reply with ONLY the single digit." in prompts.JUDGE_SYS


def test_rag_prompt_lets_the_model_ignore_irrelevant_context():
    """~45% of retrievals miss the gold article, and a hardened "use the context"
    instruction backfired on MedQuAD (ADR-027: 0.80 -> 0.56)."""
    assert "If the context is relevant" in prompts.RAG_SYS


def test_baseline_prompt_mentions_no_context_at_all():
    """The no-RAG arm must not hint that context exists, or it is not a baseline."""
    lowered = prompts.BASELINE_SYS.lower()
    assert "context" not in lowered and "reference" not in lowered


def test_chunking_parameters_are_the_ladder_settings():
    assert (CHUNK_WORDS, OVERLAP) == (180, 40)
    assert KS == [1, 3, 5, 10]


def test_bge_keeps_its_query_instruction_prefix():
    """bge is trained with an instruction prefix on the query side; dropping it
    silently costs hit-rate, which is exactly the kind of regression that would
    look like a data problem."""
    assert ENCODERS["bge"]["q_prefix"].startswith("Represent this sentence")
    assert ENCODERS["bge"]["p_prefix"] == ""
    assert ENCODERS["minilm"]["q_prefix"] == ""


# --- judge parsing -----------------------------------------------------------

class _FakeJudge:
    def __init__(self, text):
        self.text = text
        self.seen = None

    def chat(self, messages, **kw):
        self.seen = (messages, kw)
        return type("R", (), {"text": self.text})()


@pytest.mark.parametrize("reply,expected", [("3", 3), ("Score: 4", 4), ("0", 0)])
def test_judge_score_parses_the_digit(reply, expected):
    assert prompts.judge_score(_FakeJudge(reply), "q", "ref", "cand") == expected


def test_judge_score_returns_none_when_no_digit_is_produced():
    assert prompts.judge_score(_FakeJudge("I cannot grade this"), "q", "r", "c") is None


def test_judge_is_called_deterministically_and_cheaply():
    j = _FakeJudge("3")
    prompts.judge_score(j, "q", "ref", "cand")
    _, kw = j.seen
    assert kw["temperature"] == 0.0   # a classification call, not a generation
    assert kw["max_tokens"] == 8      # thousands of these share a daily quota


def test_judge_sees_the_reference_and_the_student_never_does():
    """§0.2 for a closed domain: only the JUDGE may see the gold answer."""
    j = _FakeJudge("3")
    prompts.judge_score(j, "the question", "THE GOLD ANSWER", "the candidate")
    messages, _ = j.seen
    assert "THE GOLD ANSWER" in messages[1]["content"]
    assert "THE GOLD ANSWER" not in prompts.RAG_SYS + prompts.BASELINE_SYS


# --- pure retrieval helpers --------------------------------------------------

def test_chunks_prefix_every_piece_with_the_title():
    art = {"id": "a", "title": "Wix Stores", "contents": " ".join(f"w{i}" for i in range(400))}
    chunks = chunks_of(art)
    assert len(chunks) > 1
    assert all(c.startswith("Wix Stores. ") for c in chunks)


def test_chunks_overlap_so_a_fact_on_a_boundary_is_not_split_away():
    art = {"id": "a", "title": "T", "contents": " ".join(f"w{i}" for i in range(400))}
    first, second = chunks_of(art)[:2]
    assert set(first.split()) & set(second.split())


def test_chunks_of_an_empty_article_returns_the_title():
    assert chunks_of({"id": "a", "title": "Only a title", "contents": ""}) == ["Only a title"]


def test_hitrate_counts_a_hit_at_the_rank_the_gold_appears():
    ranked = [["x", "y", "gold"], ["gold", "a", "b"]]
    gold = [{"gold"}, {"gold"}]
    res, ranks = hitrate(ranked, gold)
    assert res[1] == 0.5      # only the second question has gold at rank 1
    assert res[3] == 1.0      # both have it within the top 3
    assert ranks == [3, 1]
    assert res["mrr"] == pytest.approx((1 / 3 + 1) / 2)


def test_hitrate_treats_a_miss_as_zero_reciprocal_rank():
    res, ranks = hitrate([["a", "b"]], [{"gold"}])
    assert res[3] == 0.0 and ranks == [None] and res["mrr"] == 0.0


def test_rrf_ranks_an_item_found_by_both_rankers_above_one_found_by_only_a_single_one():
    """`both` is 2nd in each list; `only_a`/`only_b` are 1st but in one list only.
    Two mid placements accumulate more reciprocal rank than one top placement."""
    fused = rrf([["only_a", "both"]], [["only_b", "both"]])[0]
    assert fused[0] == "both"


def test_rrf_prefers_the_extremes_when_two_rankers_disagree_completely():
    """With exactly opposite rankings, 1/60 + 1/62 > 2/61 — so the items each
    ranker put first tie ahead of the one both put in the middle. This is a real
    property of reciprocal-rank fusion, not a bug: it is why fusing a weak
    lexical ranker with a strong dense one HURT the ladder (0.605 < 0.665)."""
    fused = rrf([["a", "b", "c"]], [["c", "b", "a"]])[0]
    assert fused[-1] == "b"


def test_retrieval_record_reports_the_rank_of_the_first_gold():
    rec = retrieval_record(7, "q?", ["g1", "g2"], ["x", "g2", "y"], [0.9, 0.8, 0.7])
    assert rec["gold_rank"] == 2 and rec["gold_retrieved"] is True
    assert rec["idx"] == 7 and rec["top_sim"] == 0.9


def test_retrieval_record_marks_a_miss_with_minus_one():
    rec = retrieval_record(0, "q?", ["g1"], ["x", "y"], [0.5, 0.4])
    assert rec["gold_rank"] == -1 and rec["gold_retrieved"] is False


def test_retrieval_record_survives_an_empty_retrieval():
    rec = retrieval_record(0, "q?", ["g1"], [], [])
    assert rec["gold_retrieved"] is False and rec["top_sim"] is None
