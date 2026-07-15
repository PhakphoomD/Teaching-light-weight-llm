"""BlindJudge (T2.3) — the Track-A headline correctness judge.

Implements EVAL_SPEC.md §3 exactly: an independent, blind (Q+answer only,
NEVER the reference) LLM judge that returns a 0-4 correctness verdict.
PASS iff score >= 3 (normalized pass_threshold = 0.75, base.yml).

§0.2 by construction: `score()` takes only (question, answer, mode) — there
is no parameter through which a reference/ground-truth string could reach
the prompt this module builds. Grep-proof: this file contains no
`ground_truth` identifier anywhere (correctness-path code, LEAKAGE_CENSUS
seal #1 spirit extended to the judge).

Registered into JUDGE_REGISTRY under "blind" on import of this module
(triggered by `src/tlw/evaluation/__init__.py`).
"""

import json
import re
from typing import Any, Dict, Optional

from src.providers.factory import build_client

from ..registries import JUDGE_REGISTRY, Judge

# --- Rubric prompt (EVAL_SPEC.md §3.2, verbatim) ---

RUBRIC_PROMPT = """You are a strict medical-QA evaluator. Judge the ANSWER to the QUESTION on its own merits.
You are NOT given a reference answer — judge correctness from your own medical knowledge.

QUESTION: {q}
ANSWER:   {a}

Score 0-4 on this scale:
  4 = fully correct AND complete: directly answers THIS question, medically accurate,
      nothing misleading, no important omissions.
  3 = correct and useful: right and on-topic, minor gaps or minor imprecision only.
  2 = partially correct: addresses the question but has a notable gap or a minor error.
  1 = mostly wrong / off-topic: touches the topic but misleading, incomplete, or largely
      incorrect.
  0 = wrong, irrelevant, empty, or harmful.

Output STRICT JSON on one line: {{"score": <0-4 integer>, "reason": "<=12 words"}}"""

_JSON_SCORE_RE = re.compile(r'"score"\s*:\s*(-?\d+)')
_FIRST_INT_RE = re.compile(r"-?\d+")

MIN_SCORE = 0
MAX_SCORE = 4


def _clamp_score(value: int) -> int:
    return max(MIN_SCORE, min(MAX_SCORE, value))


def parse_verdict(text: Optional[str]) -> Dict[str, Any]:
    """Parse a judge response into {score: int|None, reason: str|None}.

    The reasoning-first rubric asks the model to think out loud (STEP 1/2/3)
    and only emit the verdict JSON on its LAST line — a preamble may mention
    unrelated numbers (e.g. "score 3 out of 4 scale", a dose, a percentage),
    so parsing must find the FINAL verdict, never the first number it trips
    over. Parse order (extends EVAL_SPEC §3.2's strict-JSON-then-fallback
    posture with "last, not first"):
      1) whole-text strict JSON (covers old-style bare-JSON replies / tests)
      2) the LAST `{...}` object in the text that strict-parses with a
         "score" key
      3) the LAST `"score": <int>` occurrence via regex (near-JSON prose)
      4) the LAST integer anywhere in the text (prose fallback)
    Unparseable/empty -> score=None (excluded from the pass-rate denominator
    upstream; null-rate must stay < 2%).
    """
    if not text or not text.strip():
        return {"score": None, "reason": None}

    stripped = text.strip()

    # 1) Strict JSON parse of the whole reply (bare-JSON replies, incl. tests).
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict) and "score" in obj:
            raw = obj["score"]
            if isinstance(raw, bool):
                return {"score": None, "reason": obj.get("reason")}
            if isinstance(raw, (int, float)):
                return {"score": _clamp_score(int(round(raw))), "reason": obj.get("reason")}
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # 2) The LAST `{...}` object that strict-parses with a usable "score".
    last_obj_verdict = None
    for m in re.finditer(r"\{[^{}]*\}", stripped):
        try:
            obj = json.loads(m.group(0))
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if isinstance(obj, dict) and "score" in obj:
            raw = obj["score"]
            if isinstance(raw, bool):
                last_obj_verdict = {"score": None, "reason": obj.get("reason")}
            elif isinstance(raw, (int, float)):
                last_obj_verdict = {"score": _clamp_score(int(round(raw))), "reason": obj.get("reason")}
    if last_obj_verdict is not None:
        return last_obj_verdict

    # 3) The LAST `"score": <int>` occurrence inside a near-JSON / prose-wrapped reply.
    matches = list(_JSON_SCORE_RE.finditer(stripped))
    if matches:
        return {"score": _clamp_score(int(matches[-1].group(1))), "reason": None}

    # 4) First integer anywhere in the text (bare, no-JSON-at-all prose
    # fallback — kept as FIRST-match, unchanged from the original contract).
    # This layer only fires when the reply has no JSON-ish "score"-bearing
    # structure at all, which the new rubric's mandated last-line JSON
    # should make rare; the "extract the final verdict, not an earlier
    # distractor number" fix lives in layers 2/3 above, where a reasoning
    # preamble could otherwise plant a false match right next to the word
    # "score". For truly unstructured prose there is no reliable "which
    # number is the verdict" signal, so we keep the original, tested
    # first-integer heuristic rather than guess "last is safer."
    m = _FIRST_INT_RE.search(stripped)
    if m:
        return {"score": _clamp_score(int(m.group(0))), "reason": None}

    # 5) Unparseable.
    return {"score": None, "reason": None}


@JUDGE_REGISTRY.register("blind")
class BlindJudge(Judge):
    """The ADR-022 (b) headline judge: blind, deterministic, 0-4 -> PASS >= 3.

    Constructor accepts the slot-F judge model config (provider/model/
    temperature/max_tokens/timeout) plus `pass_threshold` (normalized 0-1,
    default 0.75 per base.yml) and an optional `client` for dependency
    injection (tests / calibration adapters never need a real network call
    or a real provider registration).
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 256,
        timeout: int = 60,
        pass_threshold: float = 0.75,
        client: Optional[Any] = None,
        **_ignored: Any,
    ):
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.pass_threshold = pass_threshold
        if client is not None:
            self._client = client
        elif provider is not None and model is not None:
            self._client = build_client(provider, model=model)
        else:
            self._client = None  # constructible for registry introspection only

    def score(self, question: str, answer: str, mode: str) -> Dict[str, Any]:
        """Blind correctness verdict. mode must be 'blind' (§0.2, ADR-022 (b) —
        gt_comparing is deliberately not built; see registries.py)."""
        if mode != "blind":
            raise NotImplementedError(
                f"BlindJudge only supports mode='blind' (ADR-022 (b): blind-only "
                f"headline judge); got mode={mode!r}"
            )
        if self._client is None:
            raise RuntimeError(
                "BlindJudge has no client — pass provider+model or client= explicitly"
            )

        prompt = RUBRIC_PROMPT.format(q=question, a=answer)
        messages = [{"role": "user", "content": prompt}]

        response = self._client.chat(
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout_s=self.timeout,
        )
        error = getattr(response, "error", None)
        raw_text = "" if error else (getattr(response, "text", "") or "")

        verdict = parse_verdict(raw_text)
        score = verdict["score"]
        normalized = None if score is None else score / MAX_SCORE
        passed = None if normalized is None else normalized >= self.pass_threshold

        return {
            "score": score,
            "normalized_score": normalized,
            "passed": passed,
            "reason": verdict["reason"],
            "raw_response": raw_text,
            "error": error,
            "null": score is None,
        }
