"""Shared round-loop primitives (T2.4) — the honest-by-construction core.

CONCEPTS salvaged (read-only) from `simplified_teaching_loop.py` per T2.4's
Read-first list: round bookkeeping (a list of per-round records) and
early-stop-on-pass. NONE of its ground-truth-hint machinery is ported —
LAST_CHANCE (L1-L3, L5), the "one last chance" forced round (L3), and the
GT-as-feedback memory write (L4) do not exist anywhere in this module or its
callers (LEAKAGE_CENSUS seal #4: "must not carry these branches forward as
toggleable dead code" — they are simply absent, not off-by-config).

`assert_gt_free` is a structural, defense-in-depth check (on top of, never
instead of, the leakage-seal tests in tests/tlw/loop/) that a
student-bound prompt cannot carry the reference answer, even if a preset
template or a misbehaving teacher model tries to put it there (this is what
seals arm D's "teacher legally saw GT, but its RETURNED feedback must still
be GT-free before the student sees it", EVAL_SPEC.md §1).
"""

from typing import Any, Dict, List, Optional

from src.tlw.evaluation.diagnostics import normalize_text

_MIN_SHINGLE_TOKENS = 12  # mirrors the Memory v2 tripwire's T-1 shingle size (schema.md §2)


class LeakageGuardError(RuntimeError):
    """A ground-truth string would reach a student-bound prompt (§0.2)."""


def _shingles(tokens: List[str], size: int) -> List[str]:
    if len(tokens) < size:
        return []
    return [" ".join(tokens[i : i + size]) for i in range(len(tokens) - size + 1)]


def assert_gt_free(prompt: str, ground_truth: Optional[str]) -> None:
    """Raise LeakageGuardError if `prompt` contains the reference answer,
    verbatim or via a long contiguous shingle (mirrors the Memory v2
    tripwire T-1 check, schema.md §2, at the loop layer instead of the
    memory layer). No-op when `ground_truth` is falsy (the headline arms
    A/B/C never have one at hand for the student path)."""
    if not ground_truth:
        return
    norm_prompt = normalize_text(prompt)
    norm_gt = normalize_text(ground_truth)
    if not norm_gt:
        return
    if norm_gt in norm_prompt:
        raise LeakageGuardError(
            "ground-truth text detected verbatim in a student-bound prompt (§0.2) — refusing to send it."
        )
    gt_tokens = norm_gt.split()
    prompt_tokens = norm_prompt.split()
    for shingle in _shingles(gt_tokens, _MIN_SHINGLE_TOKENS):
        if shingle in " ".join(prompt_tokens):
            raise LeakageGuardError(
                f"a {_MIN_SHINGLE_TOKENS}-token ground-truth shingle was detected in a "
                "student-bound prompt (§0.2) — refusing to send it."
            )


def _chat_text(client, messages: List[Dict[str, str]], temperature: float, max_tokens: int, timeout_s: int) -> str:
    response = client.chat(
        messages=messages, temperature=temperature, max_tokens=max_tokens, timeout_s=timeout_s
    )
    error = getattr(response, "error", None)
    return "" if error else (getattr(response, "text", "") or "")


def student_answer(
    student,
    prompt: str,
    ground_truth: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 256,
    timeout_s: int = 60,
) -> str:
    """Send `prompt` to the student model. `ground_truth`, when supplied by
    the caller, is used ONLY to run `assert_gt_free` — it is never itself
    placed in `prompt` by this function (the caller built `prompt` already;
    this is the seal, not the construction)."""
    assert_gt_free(prompt, ground_truth)
    return _chat_text(student, [{"role": "user", "content": prompt}], temperature, max_tokens, timeout_s)


def teacher_feedback(
    teacher,
    prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 256,
    timeout_s: int = 60,
) -> str:
    """Send `prompt` to the teacher model. No leakage guard here BY DESIGN:
    the teacher's own prompt may legally contain GT (§0.2, arm D) — the
    guard belongs on the STUDENT-bound prompt built from the teacher's
    *returned* feedback (`student_answer`'s `assert_gt_free` call), not here.
    """
    return _chat_text(teacher, [{"role": "user", "content": prompt}], temperature, max_tokens, timeout_s)


def judge_answer(judge, question: str, answer: str) -> Dict[str, Any]:
    """Score via the blind judge. No GT parameter exists to pass — the
    judge seam (`Judge.score(question, answer, mode)`, registries.py) is
    structurally incapable of receiving one (T2.3, tests/tlw/evaluation/
    test_leakage.py:test_score_signature_has_no_ground_truth_parameter)."""
    return judge.score(question, answer, mode="blind")


def make_round_record(
    round_num: int,
    answer: str,
    verdict: Dict[str, Any],
    feedback: Optional[str] = None,
    memory_used: bool = False,
    teacher_called: bool = False,
    reference_match: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """One per-round record, shaped to line up with schema.md's per-round
    debug record (score/passed/memory_used fields carry the same names)."""
    return {
        "round": round_num,
        "answer": answer,
        "feedback": feedback,
        "score": verdict.get("score"),
        "normalized_score": verdict.get("normalized_score"),
        "passed": bool(verdict.get("passed")),
        "memory_used": memory_used,
        "teacher_called": teacher_called,
        "reference_match": reference_match,
    }
