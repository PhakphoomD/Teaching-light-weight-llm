"""reference_match diagnostics tests (T2.3): computed independently of, and
never merged into, correctness. Deterministic parts (rouge_l/tokenize) run
without any model download; semantic_sim tests are skipped if
sentence-transformers/the MiniLM weights aren't available offline."""

import pytest

from src.tlw.evaluation.diagnostics import normalize_text, reference_match, rouge_l, tokenize


def test_normalize_text_lowercases_and_strips_punctuation():
    assert normalize_text("Hello,  World!") == "hello world"


def test_tokenize_empty_and_none():
    assert tokenize(None) == []
    assert tokenize("") == []


def test_rouge_l_identical_text_is_one():
    assert rouge_l("the cat sat on the mat", "the cat sat on the mat") == pytest.approx(1.0)


def test_rouge_l_disjoint_text_is_zero():
    assert rouge_l("completely unrelated words here", "totally different reference text") == pytest.approx(0.0)


def test_rouge_l_empty_inputs_are_zero_not_crash():
    assert rouge_l("", "something") == 0.0
    assert rouge_l("something", "") == 0.0
    assert rouge_l("", "") == 0.0


def test_reference_match_returns_only_diagnostic_fields():
    result = reference_match("short answer", "a different reference", encoder=_NullEncoder())
    assert set(result) == {"semantic_sim", "rouge_l"}
    # No pass/fail, no weight, no threshold field anywhere in the diagnostic shape.
    assert "passed" not in result
    assert "score" not in result
    assert "weight" not in result


class _NullEncoder:
    """Fake encoder so this test doesn't require downloading MiniLM weights."""

    def encode(self, texts, convert_to_numpy=True):
        import numpy as np

        # Deterministic fake embedding: bag-of-first-letters, fixed width.
        vecs = []
        for t in texts:
            v = [0.0] * 26
            for ch in t.lower():
                if "a" <= ch <= "z":
                    v[ord(ch) - ord("a")] += 1.0
            vecs.append(v)
        return np.array(vecs)


def test_semantic_similarity_identical_text_is_one_with_fake_encoder():
    from src.tlw.evaluation.diagnostics import semantic_similarity

    sim = semantic_similarity("diabetes mellitus", "diabetes mellitus", encoder=_NullEncoder())
    assert sim == pytest.approx(1.0, abs=1e-6)


def test_semantic_similarity_missing_sentence_transformers_returns_zero(monkeypatch):
    """diagnostics must not crash a run if the encoder can't load."""
    import src.tlw.evaluation.diagnostics as diag

    def _boom():
        raise ImportError("no sentence-transformers")

    monkeypatch.setattr(diag, "get_default_encoder", _boom)
    assert diag.semantic_similarity("a", "b", encoder=None) == 0.0
