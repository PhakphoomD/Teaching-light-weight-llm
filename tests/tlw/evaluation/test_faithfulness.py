"""T3.4 faithfulness diagnostic tests (rag-medquad-protocol §4.2).

Faithfulness is a DIAGNOSTIC (never gates pass/fail) and is §0.2-safe: its
prompt sees (answer, passages) only, never the gold answer.
"""

from types import SimpleNamespace

from src.tlw.evaluation.faithfulness import (
    FAITHFULNESS_PROMPT,
    FaithfulnessJudge,
    parse_faithfulness,
)


def test_parse_strict_json():
    r = parse_faithfulness('{"supported": 3, "total": 4}')
    assert r["supported"] == 3 and r["total"] == 4 and abs(r["faithfulness"] - 0.75) < 1e-9


def test_parse_prose_wrapped():
    r = parse_faithfulness('Reasoning... final: {"supported": 2, "total": 2} done')
    assert r["faithfulness"] == 1.0


def test_parse_zero_total_is_null():
    assert parse_faithfulness('{"supported": 0, "total": 0}')["faithfulness"] is None


def test_parse_unparseable_is_null():
    assert parse_faithfulness("no json here")["faithfulness"] is None


def test_parse_clamps_supported_over_total():
    r = parse_faithfulness('{"supported": 9, "total": 4}')
    assert r["supported"] == 4 and r["faithfulness"] == 1.0


class _FakeClient:
    def __init__(self, text):
        self.text = text
        self.last_prompt = None

    def chat(self, messages, temperature=0.0, max_tokens=256, timeout_s=60, **kw):
        self.last_prompt = messages[-1]["content"]
        return SimpleNamespace(text=self.text, usage=None, error=None)


def test_grounded_answer_scores_high():
    client = _FakeClient('{"supported": 3, "total": 3}')
    j = FaithfulnessJudge(client=client)
    r = j.score("The kidneys filter blood.", ["The kidneys filter waste from the blood."])
    assert r["faithfulness"] == 1.0


def test_hallucinated_answer_scores_low():
    client = _FakeClient('{"supported": 0, "total": 3}')
    j = FaithfulnessJudge(client=client)
    r = j.score("Kidneys produce insulin and cure diabetes.", ["The kidneys filter waste."])
    assert r["faithfulness"] == 0.0


def test_no_passages_returns_null_without_calling_model():
    client = _FakeClient('{"supported": 1, "total": 1}')
    j = FaithfulnessJudge(client=client)
    r = j.score("some answer", [])
    assert r["faithfulness"] is None and r["null"] is True
    assert client.last_prompt is None  # never called the model


def test_prompt_never_contains_a_ground_truth_slot():
    # §0.2: the faithfulness prompt template has no gold-answer placeholder.
    assert "ground_truth" not in FAITHFULNESS_PROMPT
    assert "reference" not in FAITHFULNESS_PROMPT.lower()
    client = _FakeClient('{"supported": 1, "total": 1}')
    FaithfulnessJudge(client=client).score("ans", ["passage text about kidneys"])
    assert "passage text about kidneys" in client.last_prompt
    assert "ans" in client.last_prompt
