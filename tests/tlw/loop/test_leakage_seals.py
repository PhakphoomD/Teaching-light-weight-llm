"""Leakage-seal tests for the loop block (DoD step 3/4).

Proves, with mocked student/teacher/judge (no API calls), that no
student-bound or judge-bound prompt ever carries the reference answer in
arms A/B/C, and that arm D confines GT to the teacher-bound prompt only —
even structurally defending against a misbehaving teacher that tries to
echo it back (the L7/Trace-C failure mode, LEAKAGE_AUDIT.md).

See DoD accounting at the bottom of this file's companion report for the
full census-item -> test mapping (also restated in the spoke report).
"""

import pytest

from src.tlw.registries import build_arm_strategy, build_memory_backend
from src.tlw.loop.core import LeakageGuardError, assert_gt_free

PASS = {"score": 4, "normalized_score": 1.0, "passed": True}
FAIL = {"score": 1, "normalized_score": 0.25, "passed": False}

GT = "Insulin resistance causes blood sugar to rise sharply after a high-carbohydrate meal."


def _substring_hits(needle: str, haystack: str) -> bool:
    return needle.lower() in haystack.lower()


# --- Unit test for the guard function itself ---


def test_assert_gt_free_raises_on_verbatim_substring():
    with pytest.raises(LeakageGuardError):
        assert_gt_free(f"Guidance: {GT}", GT)


def test_assert_gt_free_raises_on_long_shingle_even_if_reworded_around_it():
    shingle = " ".join(GT.split()[:12])
    prompt = f"Guidance: here's a tip -- {shingle} -- which should help you."
    with pytest.raises(LeakageGuardError):
        assert_gt_free(prompt, GT)


def test_assert_gt_free_allows_unrelated_text():
    assert_gt_free("Guidance: focus on the mechanism, keep it under 80 words.", GT)  # no raise


def test_assert_gt_free_is_a_noop_without_ground_truth():
    assert_gt_free(f"Guidance: {GT}", None)  # no raise: nothing to compare against


# --- Arms A/B/C: student-bound prompts never contain GT, even when GT is
#     available in params (e.g. supplied only for the reference_match
#     diagnostic) — seals L1, L2, L3, L5, L6, L7(student side). ---


@pytest.mark.parametrize("arm", ["A", "B", "C"])
def test_student_bound_prompts_never_contain_gt(arm, make_client, make_judge):
    student = make_client(["draft v1", "self-critique or n/a", "draft v2"])
    teacher = make_client(["Critique: be more specific. Improvements: 1) ..."])
    judge = make_judge([FAIL, PASS])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy(arm)
    strategy.run(
        "What raises blood sugar after meals?", student, teacher, memory, judge,
        {"max_rounds": 3, "ground_truth": GT},
    )

    for prompt in student.prompts:
        assert not _substring_hits(GT, prompt), f"arm {arm} leaked GT into a student-bound prompt"


@pytest.mark.parametrize("arm", ["A", "B", "C"])
def test_judge_bound_calls_never_receive_gt(arm, make_client, make_judge):
    """The judge seam (Judge.score(question, answer, mode)) has no GT
    parameter at all (tests/tlw/evaluation/test_leakage.py) — this
    confirms the loop never even tries to smuggle one through `answer`
    beyond what the student itself produced."""
    student = make_client(["draft v1", "self-critique or n/a", "draft v2"])
    teacher = make_client(["Critique: be more specific."])
    judge = make_judge([FAIL, PASS])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy(arm)
    strategy.run("Q", student, teacher, memory, judge, {"max_rounds": 3, "ground_truth": GT})

    for call in judge.calls:
        assert call["mode"] == "blind"
        assert "ground_truth" not in call


# --- Arm D: GT appears ONLY in the teacher-bound prompt, never student-bound ---


def test_arm_d_gt_reaches_only_the_teacher_bound_prompt(make_client, make_judge):
    student = make_client(["draft v1", "draft v2 (better)"])
    teacher = make_client(["Critique: consider the mechanism. Improvements: 1) ..."])
    judge = make_judge([FAIL, PASS])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy("D")
    strategy.run("Q", student, teacher, memory, judge, {"max_rounds": 3, "ground_truth": GT})

    assert len(teacher.calls) == 1
    assert _substring_hits(GT, teacher.prompts[0])  # legal: teacher's own prompt (§0.2)

    for prompt in student.prompts:
        assert not _substring_hits(GT, prompt), "arm D leaked GT into a student-bound prompt"


def test_arm_d_raises_if_teacher_echoes_gt_into_returned_feedback(make_client, make_judge):
    """The L7/Trace-C failure mode: a misbehaving teacher (or a bad
    template) echoes GT back into its RETURNED feedback text. Arm D's
    student-bound refine prompt must refuse to carry it forward — the round
    raises instead of silently leaking (teaching-loop-protocol.md §1, loop/core.py
    structural seal, defense-in-depth on top of this file's tests)."""
    student = make_client(["draft v1"])  # only the first-attempt call happens
    teacher = make_client([f"Example: {GT}"])  # simulates the L7 echo defect
    judge = make_judge([FAIL])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy("D")
    with pytest.raises(LeakageGuardError):
        strategy.run("Q", student, teacher, memory, judge, {"max_rounds": 3, "ground_truth": GT})

    # The teacher WAS called (its own prompt legally saw GT) but the
    # leaked feedback never made it into a second student call.
    assert len(teacher.calls) == 1
    assert len(student.calls) == 1


def test_arm_c_blind_teacher_prompt_never_contains_gt_even_when_available(make_client, make_judge):
    """Arm C's teacher preset variant is 'blind' — its own prompt must not
    carry GT even though params['ground_truth'] is available (e.g. for the
    reference_match diagnostic only)."""
    student = make_client(["draft v1", "draft v2"])
    teacher = make_client(["Critique: ..."])
    judge = make_judge([FAIL, PASS])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy("C")
    strategy.run("Q", student, teacher, memory, judge, {"max_rounds": 3, "ground_truth": GT})

    assert len(teacher.calls) == 1
    assert not _substring_hits(GT, teacher.prompts[0])


# --- No last-chance / ground-truth-hint mechanism exists in this module at all ---


def test_no_ground_truth_hint_mechanism_in_loop_source():
    """Grep-proof DoD (LEAKAGE_AUDIT seal #4): no CODE IDENTIFIER for the
    retired L1/L3/L7 mechanisms exists anywhere in the loop block (prose
    mentions in docstrings/comments describing what was NOT ported are
    fine and expected — an actual function/variable/string literal that
    could execute the mechanism is not)."""
    import ast
    import inspect

    import src.tlw.loop.core as core_module
    import src.tlw.loop.strategies as strategies_module

    banned_identifiers = {"last_chance", "LAST_CHANCE", "difficult_question", "enable_last_chance"}

    for module in (core_module, strategies_module):
        source = inspect.getsource(module)
        assert "COPY THIS EXACTLY" not in source  # the literal L1 hint string, banned even in comments

        tree = ast.parse(source)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.arg):
                names.add(node.arg)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                names.add(node.value)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
        assert not (names & banned_identifiers), names & banned_identifiers
