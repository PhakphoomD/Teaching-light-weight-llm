"""BlindJudge unit tests (T2.3): score-parsing edge cases + scoring contract.

No network calls — every test injects a FakeClient via BlindJudge(client=...).
"""

from dataclasses import dataclass
from typing import List, Optional

import pytest

from src.tlw.evaluation.judge import BlindJudge, parse_verdict


@dataclass
class FakeResponse:
    text: str
    error: Optional[str] = None


class FakeClient:
    """Duck-types the LLMClient.chat() surface used by BlindJudge."""

    def __init__(self, reply: str, error: Optional[str] = None):
        self.reply = reply
        self.error = error
        self.calls: List[dict] = []

    def chat(self, messages, temperature, max_tokens, timeout_s):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout_s": timeout_s,
            }
        )
        return FakeResponse(text=self.reply, error=self.error)


# --- parse_verdict edge cases (DoD step 5) ---


def test_parse_strict_json():
    v = parse_verdict('{"score": 3, "reason": "correct and on-topic"}')
    assert v == {"score": 3, "reason": "correct and on-topic"}


def test_parse_prose_reply_extracts_first_integer():
    v = parse_verdict("I would rate this a 2 out of 4 because it's incomplete.")
    assert v["score"] == 2


def test_parse_empty_reply_is_null():
    assert parse_verdict("") == {"score": None, "reason": None}
    assert parse_verdict(None) == {"score": None, "reason": None}
    assert parse_verdict("   ") == {"score": None, "reason": None}


def test_parse_out_of_range_score_is_clamped():
    assert parse_verdict('{"score": 9, "reason": "x"}')["score"] == 4
    assert parse_verdict('{"score": -3, "reason": "x"}')["score"] == 0


def test_parse_integer_with_explanation_prose():
    v = parse_verdict("Score: 4. Fully correct and complete answer.")
    assert v["score"] == 4


def test_parse_no_digits_anywhere_is_null():
    v = parse_verdict("The answer looks great, no issues at all.")
    assert v["score"] is None


def test_parse_json_embedded_in_extra_prose():
    v = parse_verdict('Sure, here it is: {"score": 1, "reason": "off-topic"} thanks!')
    assert v["score"] == 1


def test_parse_boolean_score_is_null_not_truthy_int():
    # JSON true/false would otherwise silently become 1/0 via int(bool) — must not.
    v = parse_verdict('{"score": true, "reason": "x"}')
    assert v["score"] is None


# --- BlindJudge.score() contract ---


def test_score_passes_at_threshold():
    client = FakeClient('{"score": 3, "reason": "correct"}')
    judge = BlindJudge(client=client, pass_threshold=0.75)
    result = judge.score("What is diabetes?", "A chronic condition of high blood sugar.", mode="blind")
    assert result["score"] == 3
    assert result["normalized_score"] == pytest.approx(0.75)
    assert result["passed"] is True
    assert result["null"] is False


def test_score_below_threshold_fails():
    client = FakeClient('{"score": 2, "reason": "gap"}')
    judge = BlindJudge(client=client, pass_threshold=0.75)
    result = judge.score("q", "a", mode="blind")
    assert result["passed"] is False


def test_score_unparseable_is_null_and_excluded_from_pass():
    client = FakeClient("I cannot answer that.")
    judge = BlindJudge(client=client)
    result = judge.score("q", "a", mode="blind")
    assert result["score"] is None
    assert result["null"] is True
    assert result["passed"] is None  # not False — excluded from the denominator, not counted as fail


def test_score_client_error_produces_null_verdict():
    client = FakeClient("", error="timeout")
    judge = BlindJudge(client=client)
    result = judge.score("q", "a", mode="blind")
    assert result["score"] is None
    assert result["error"] == "timeout"


def test_gt_comparing_mode_not_implemented():
    client = FakeClient('{"score": 4}')
    judge = BlindJudge(client=client)
    with pytest.raises(NotImplementedError, match="blind"):
        judge.score("q", "a", mode="gt_comparing")


def test_deterministic_call_params_forwarded():
    client = FakeClient('{"score": 4}')
    judge = BlindJudge(client=client, temperature=0.0, max_tokens=16, timeout=60)
    judge.score("q", "a", mode="blind")
    call = client.calls[0]
    assert call["temperature"] == 0.0
    assert call["max_tokens"] == 16
    assert call["timeout_s"] == 60
