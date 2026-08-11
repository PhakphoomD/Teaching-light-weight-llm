"""Call-pattern tests for arm strategies A/B/C/D (DoD step 5).

All mocked — no API calls. Proves: A = exactly one student call, zero
teacher calls. B = zero teacher calls, ever. C/D = teacher called between
rounds. All arms stop as soon as the judge passes.
"""

import pytest

from src.tlw.registries import build_arm_strategy, build_memory_backend

PASS = {"score": 4, "normalized_score": 1.0, "passed": True}
FAIL = {"score": 1, "normalized_score": 0.25, "passed": False}


def test_arm_a_exactly_one_student_call_zero_teacher_calls(make_client, make_judge, make_memory):
    student = make_client(["a decent first draft"])
    teacher = make_client([])
    judge = make_judge([PASS])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy("A")
    records = strategy.run("What raises blood sugar?", student, teacher, memory, judge, {"max_rounds": 3})

    assert len(records) == 1
    assert records[0]["passed"] is True
    assert len(student.calls) == 1
    assert len(teacher.calls) == 0


def test_arm_a_stays_one_round_even_when_it_fails(make_client, make_judge, make_memory):
    """A is single-pass by construction — it never loops, pass or fail."""
    student = make_client(["a weak draft"])
    teacher = make_client([])
    judge = make_judge([FAIL])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy("A")
    records = strategy.run("Q", student, teacher, memory, judge, {"max_rounds": 3})

    assert len(records) == 1
    assert records[0]["passed"] is False
    assert len(student.calls) == 1
    assert len(teacher.calls) == 0


def test_arm_b_zero_teacher_calls_across_multiple_rounds(make_client, make_judge, make_memory):
    student = make_client(["draft v1", "self-critique text", "draft v2 (better)"])
    teacher = make_client([])  # any .chat() call here would IndexError-pop from empty list
    judge = make_judge([FAIL, PASS])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy("B")
    records = strategy.run("Q", student, teacher, memory, judge, {"max_rounds": 3})

    assert len(records) == 2
    assert records[-1]["passed"] is True
    assert len(teacher.calls) == 0
    # 3 student calls: first attempt, self-critique, refine.
    assert len(student.calls) == 3


def test_arm_b_early_stops_on_first_round_pass(make_client, make_judge, make_memory):
    student = make_client(["already correct"])
    teacher = make_client([])
    judge = make_judge([PASS])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy("B")
    records = strategy.run("Q", student, teacher, memory, judge, {"max_rounds": 3})

    assert len(records) == 1
    assert len(student.calls) == 1
    assert len(teacher.calls) == 0


def test_arm_c_teacher_called_between_rounds(make_client, make_judge, make_memory):
    student = make_client(["draft v1", "draft v2 (better)"])
    teacher = make_client(["Critique: be more specific. Improvements: 1) ..."])
    judge = make_judge([FAIL, PASS])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy("C")
    records = strategy.run("Q", student, teacher, memory, judge, {"max_rounds": 3})

    assert len(records) == 2
    assert records[-1]["passed"] is True
    assert len(teacher.calls) == 1
    assert records[1]["teacher_called"] is True
    assert records[0]["teacher_called"] is False


def test_arm_c_early_stop_means_zero_teacher_calls(make_client, make_judge, make_memory):
    student = make_client(["already correct"])
    teacher = make_client([])
    judge = make_judge([PASS])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy("C")
    records = strategy.run("Q", student, teacher, memory, judge, {"max_rounds": 3})

    assert len(records) == 1
    assert len(teacher.calls) == 0


def test_arm_c_never_stores_to_memory_when_memory_type_is_none(make_client, make_judge):
    """Headline arms use memory.type=none (ADR-022 (c)) — store() is a no-op
    by construction (NoneMemory), not by the strategy checking a flag."""
    student = make_client(["draft v1", "draft v2 (better)"])
    teacher = make_client(["Critique: ..."])
    judge = make_judge([FAIL, PASS])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy("C")
    strategy.run("Q", student, teacher, memory, judge, {"max_rounds": 3})

    assert memory.stats()["total_episodes"] == 0


def test_arm_c_stores_a_note_on_pass_with_a_real_backend(make_client, make_judge, make_memory):
    """With a mock memory backend standing in for the C'/D' ablation's real
    faiss backend, arm C stores a note only on a passing round, never on
    a failing one (Memory v2 §5: 'store only what worked')."""
    student = make_client(["draft v1 (fails)", "draft v2 (passes)"])
    teacher = make_client(["Critique: be more specific."])
    judge = make_judge([FAIL, PASS])
    memory = make_memory()

    strategy = build_arm_strategy("C")
    strategy.run("Q", student, teacher, memory, judge, {"max_rounds": 3})

    assert len(memory.store_calls) == 1
    stored_episode = memory.store_calls[0]["episode"]
    assert stored_episode["provenance"]["arm"] == "C"
    assert "teaching_note" in stored_episode


def test_arm_d_requires_ground_truth(make_client, make_judge, make_memory):
    student = make_client([])
    teacher = make_client([])
    judge = make_judge([])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy("D")
    with pytest.raises(ValueError, match="requires params\\['ground_truth'\\]"):
        strategy.run("Q", student, teacher, memory, judge, {"max_rounds": 3})


def test_arm_d_teacher_called_between_rounds_with_gt(make_client, make_judge, make_memory):
    student = make_client(["draft v1", "draft v2 (better)"])
    teacher = make_client(["Critique: consider the mechanism. Improvements: 1) ..."])
    judge = make_judge([FAIL, PASS])
    memory = build_memory_backend("none")

    strategy = build_arm_strategy("D")
    records = strategy.run(
        "Q", student, teacher, memory, judge,
        {"max_rounds": 3, "ground_truth": "Insulin resistance raises blood sugar after meals."},
    )

    assert len(records) == 2
    assert len(teacher.calls) == 1
