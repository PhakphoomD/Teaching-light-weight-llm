"""Unit tests for the store-time tripwire (schema.md Memory v2 contract §2).

Pure logic tests — no encoder/faiss needed for T-1/T-3; T-2 is exercised with
a fake cosine value (the backend owns the real embedding call, tested in
test_faiss_backend.py)."""

from src.tlw.memory.tripwire import (
    check_t1_substring,
    check_t2_similarity,
    check_t3_length_overlap,
    run_tripwire,
)

REFERENCE = (
    "Metformin lowers blood glucose primarily by reducing hepatic glucose "
    "production and improving peripheral insulin sensitivity in the muscle."
)


def test_t1_rejects_exact_substring():
    note = f"The correct answer is: {REFERENCE}"
    assert check_t1_substring(note, REFERENCE) is True


def test_t1_rejects_long_shingle_even_without_full_substring():
    # A >=12-token contiguous run of the reference embedded in other text.
    shingle = " ".join(REFERENCE.split()[:14])
    note = f"Great coaching move: focus on this -> {shingle} <- and stop there."
    assert check_t1_substring(note, REFERENCE, shingle_n=12) is True


def test_t1_allows_a_short_paraphrase():
    note = "Lead with the mechanism (hepatic glucose + insulin sensitivity), keep it under 60 words."
    assert check_t1_substring(note, REFERENCE) is False


def test_t2_rejects_high_cosine():
    assert check_t2_similarity(0.95, gt_similarity_max=0.80) is True
    assert check_t2_similarity(0.80, gt_similarity_max=0.80) is True  # boundary: >= rejects


def test_t2_allows_low_cosine():
    assert check_t2_similarity(0.40, gt_similarity_max=0.80) is False


def test_t3_rejects_long_high_overlap_reword():
    # Same tokens, shuffled/lightly reworded -> length + overlap smell should
    # catch it even though it dodges the exact-substring/shingle rule.
    words = REFERENCE.rstrip(".").split()
    reordered = " ".join(words[::-1]) + "."
    assert check_t3_length_overlap(reordered, REFERENCE) is True


def test_t3_allows_short_distinct_note():
    note = "Anchor to the mechanism; keep answers concise."
    assert check_t3_length_overlap(note, REFERENCE) is False


def test_run_tripwire_no_reference_is_a_noop_pass():
    result = run_tripwire("anything at all, even the reference text", None, None)
    assert result.rejected is False
    assert result.reason is None


def test_run_tripwire_short_circuits_on_first_hit_t1():
    note = f"The correct answer is: {REFERENCE}"
    result = run_tripwire(note, REFERENCE, cosine_sim=0.0)  # T-2 would pass, T-1 must catch it
    assert result.rejected is True
    assert result.reason == "T-1"


def test_run_tripwire_catches_t2_when_t1_would_pass():
    note = "A short distinct paraphrase that shares no long run with the reference."
    result = run_tripwire(note, REFERENCE, cosine_sim=0.90, gt_similarity_max=0.80)
    assert result.rejected is True
    assert result.reason == "T-2"


def test_run_tripwire_passes_a_genuine_teaching_note():
    note = "Lead with the mechanism, name 2 contributors, keep it under 80 words."
    result = run_tripwire(note, REFERENCE, cosine_sim=0.20, gt_similarity_max=0.80)
    assert result.rejected is False
