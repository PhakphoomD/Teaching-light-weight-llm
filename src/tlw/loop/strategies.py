"""Arm strategies A/B/C/D (T2.4) — EVAL_SPEC.md §1 / ADR-002.

Each arm decides ONLY what feedback source feeds the student between
rounds; scoring is always delegated to the judge seam (no scoring logic
lives here, per T2.4 "Must NOT do"). No arm has a ground-truth-hint
fallback in any form — the legacy L1-L5 mechanism (LEAKAGE_CENSUS.md) does
not exist in this module at all, structurally, not just off-by-default.

Registers "A"/"B"/"C"/"D" into STRATEGY_REGISTRY on import (T2.2 pattern),
replacing the T2.2 `_PlaceholderArm` stand-ins registries.py used to
register under these same four names (deleted by this task).
"""

from typing import Any, Dict, List, Optional

from src.tlw.evaluation.diagnostics import reference_match as _diagnostic_reference_match

from ..registries import STRATEGY_REGISTRY, ArmStrategy, build_preset
from .core import (
    grounding_block,
    judge_answer,
    make_round_record,
    student_answer,
    teacher_feedback,
)

_DEFAULT_STUDENT_PRESET = "minimal"
_DEFAULT_TEACHER_PRESET = "orca"


def _reference_match(answer: str, ground_truth: Optional[str]) -> Optional[Dict[str, float]]:
    """Diagnostic-only, legal score-path use of GT (EVAL_SPEC §2, LEAKAGE_CENSUS
    L10-L12) — never fed back to the student, never gates pass/fail. `None`
    when no GT was supplied (the default for a headline arm run)."""
    if not ground_truth:
        return None
    return _diagnostic_reference_match(answer, ground_truth)


def _build_episode(
    question: str, note: str, arm: str, run_id: Optional[str], teacher_model: Optional[str]
) -> Dict[str, Any]:
    return {
        "question": question,
        "teaching_note": note,
        "tags": [],
        "links": [],
        "provenance": {"run_id": run_id, "arm": arm, "teacher_model": teacher_model},
    }


class _BaseArm(ArmStrategy):
    """Shared preset resolution — every arm needs a student preset; C/D also
    need a teacher preset. Presets are resolved lazily (first use), and are
    constructible with zero kwargs (`build_arm_strategy(arm)`, T2.2 pattern)
    while still allowing an experiment to name a different preset family."""

    def __init__(
        self,
        student_preset_name: str = _DEFAULT_STUDENT_PRESET,
        teacher_preset_name: str = _DEFAULT_TEACHER_PRESET,
        **_ignored: Any,
    ):
        self._student_preset_name = student_preset_name
        self._teacher_preset_name = teacher_preset_name
        self._student_preset = None
        self._teacher_preset = None

    def _student(self):
        if self._student_preset is None:
            self._student_preset = build_preset(self._student_preset_name)
        return self._student_preset

    def _teacher(self):
        if self._teacher_preset is None:
            self._teacher_preset = build_preset(self._teacher_preset_name)
        return self._teacher_preset

    def _first_prompt(self, question, memory, top_k, ground_truth=None):
        """Build the round-1 student prompt. If the memory backend grounds the
        first attempt (the `rag` backend, T3.3/ADR-026) and returns passages,
        render the `grounded_first` variant with them as {context}; otherwise
        the plain `first` variant — so a `none`/`faiss` run is byte-identical to
        its pre-RAG behaviour (no regression). `ground_truth` (rag runs only)
        drives the RAG-L3 per-passage leak filter inside `grounding_block`.
        Returns (prompt, grounded_flag, n_dropped, context) — `context` is the
        REFERENCE PASSAGES block (or "") persisted for the faithfulness diagnostic."""
        context, dropped = grounding_block(memory, question, top_k, ground_truth)
        if context:
            return (
                self._student().render("grounded_first", question=question, context=context),
                True,
                dropped,
                context,
            )
        return self._student().render("first", question=question), False, dropped, ""


@STRATEGY_REGISTRY.register("A")
class BaselineArm(_BaseArm):
    """A — single pass, no feedback, no teacher, no memory. The floor
    (EVAL_SPEC §1)."""

    def run(self, question, student, teacher, memory, judge, params) -> List[Dict[str, Any]]:
        ground_truth = params.get("ground_truth")
        s_temp = params.get("student_temperature", 0.3)
        s_tok = params.get("student_max_tokens", 256)
        top_k = params.get("memory_top_k", 3)

        prompt, grounded, dropped, context = self._first_prompt(question, memory, top_k, ground_truth)
        answer = student_answer(student, prompt, ground_truth=ground_truth, temperature=s_temp, max_tokens=s_tok)
        verdict = judge_answer(judge, question, answer)
        record = make_round_record(
            1, answer, verdict, memory_used=grounded, grounding_dropped=dropped,
            grounding_context=context, reference_match=_reference_match(answer, ground_truth),
        )
        return [record]


@STRATEGY_REGISTRY.register("B")
class SelfRefineArm(_BaseArm):
    """B — the student critiques its own previous answer between rounds.
    ZERO teacher calls (EVAL_SPEC §1) — this is the control arm C is
    measured against (C - B isolates the teacher-feedback effect)."""

    def run(self, question, student, teacher, memory, judge, params) -> List[Dict[str, Any]]:
        ground_truth = params.get("ground_truth")
        max_rounds = params.get("max_rounds", 3)
        s_temp = params.get("student_temperature", 0.3)
        s_tok = params.get("student_max_tokens", 256)
        top_k = params.get("memory_top_k", 3)

        prompt, grounded, dropped, context = self._first_prompt(question, memory, top_k, ground_truth)
        answer = student_answer(student, prompt, ground_truth=ground_truth, temperature=s_temp, max_tokens=s_tok)
        verdict = judge_answer(judge, question, answer)
        records = [
            make_round_record(
                1, answer, verdict, memory_used=grounded, grounding_dropped=dropped,
                grounding_context=context, reference_match=_reference_match(answer, ground_truth),
            )
        ]

        round_num = 1
        while not verdict.get("passed") and round_num < max_rounds:
            round_num += 1

            critique_prompt = self._student().render(
                "critique", question=question, previous_answer=answer
            )
            critique = student_answer(
                student, critique_prompt, ground_truth=ground_truth, temperature=s_temp, max_tokens=s_tok
            )

            refine_prompt = self._student().render(
                "refine", question=question, previous_answer=answer, feedback=critique
            )
            answer = student_answer(
                student, refine_prompt, ground_truth=ground_truth, temperature=s_temp, max_tokens=s_tok
            )
            verdict = judge_answer(judge, question, answer)
            records.append(
                make_round_record(
                    round_num,
                    answer,
                    verdict,
                    feedback=critique,
                    reference_match=_reference_match(answer, ground_truth),
                )
            )
        return records


class _TeacherArm(_BaseArm):
    """Shared round structure for C (blind) / D (sighted) — the teacher's
    own prompt (GT visibility) and preset variant are the only difference
    between the two (EVAL_SPEC §1). Memory notes (from any prior question)
    are only ever folded into a REFINEMENT prompt, never the first attempt
    (schema.md Memory v2 §3) — with `memory.type: none` (the headline for
    all four arms, ADR-022 (c)) `memory.retrieve(...)` always returns `[]`,
    making this naturally inert for the measured run.
    """

    ARM_NAME = "?"
    TEACHER_VARIANT = "?"
    REQUIRE_GT = False

    def run(self, question, student, teacher, memory, judge, params) -> List[Dict[str, Any]]:
        ground_truth = params.get("ground_truth")
        if self.REQUIRE_GT and not ground_truth:
            raise ValueError(
                f"Arm {self.ARM_NAME} (sighted-teacher) requires params['ground_truth'] "
                "for the teacher's own prompt (§0.2 legal use) — none was provided."
            )
        max_rounds = params.get("max_rounds", 3)
        top_k = params.get("memory_top_k", 3)
        s_temp = params.get("student_temperature", 0.3)
        s_tok = params.get("student_max_tokens", 256)
        t_temp = params.get("teacher_temperature", 0.0)
        t_tok = params.get("teacher_max_tokens", 256)

        prompt, grounded, dropped, context = self._first_prompt(question, memory, top_k, ground_truth)
        answer = student_answer(student, prompt, ground_truth=ground_truth, temperature=s_temp, max_tokens=s_tok)
        verdict = judge_answer(judge, question, answer)
        records = [
            make_round_record(
                1, answer, verdict, memory_used=grounded, grounding_dropped=dropped,
                grounding_context=context, reference_match=_reference_match(answer, ground_truth),
            )
        ]

        round_num = 1
        while not verdict.get("passed") and round_num < max_rounds:
            round_num += 1

            notes = memory.retrieve(question, top_k) if memory is not None else []
            memory_used = bool(notes)

            teacher_kwargs: Dict[str, Any] = {"question": question, "student_answer": answer}
            if self.TEACHER_VARIANT == "sighted":
                teacher_kwargs["ground_truth"] = ground_truth
            t_prompt = self._teacher().render(self.TEACHER_VARIANT, **teacher_kwargs)
            feedback = teacher_feedback(teacher, t_prompt, temperature=t_temp, max_tokens=t_tok)

            combined_feedback = feedback
            # Only faiss teaching-NOTES fold into refinement feedback here; RAG
            # passages (which lack `teaching_note`) are grounded at round 1 via
            # `_first_prompt`, never re-injected as "prior guidance" (T3.3).
            if notes and notes[0].get("teaching_note"):
                combined_feedback = f"{feedback}\n\nPrior guidance: {notes[0]['teaching_note']}"

            refine_prompt = self._student().render(
                "refine", question=question, previous_answer=answer, feedback=combined_feedback
            )
            # Structural seal (defense-in-depth on TOP OF the leakage-seal
            # tests, tests/tlw/loop/test_leakage_seals.py): arm D's teacher
            # legally saw GT, but its RETURNED feedback must still be
            # GT-free before it reaches the student (EVAL_SPEC §1). Raises
            # LeakageGuardError otherwise — the round never sends the prompt.
            answer = student_answer(
                student, refine_prompt, ground_truth=ground_truth, temperature=s_temp, max_tokens=s_tok
            )
            verdict = judge_answer(judge, question, answer)
            records.append(
                make_round_record(
                    round_num,
                    answer,
                    verdict,
                    feedback=feedback,
                    memory_used=memory_used,
                    teacher_called=True,
                    reference_match=_reference_match(answer, ground_truth),
                )
            )

            if verdict.get("passed") and memory is not None:
                # Store-only-what-worked (Memory v2 §5): a failing round
                # never writes. `reference_answer=ground_truth` is used ONLY
                # by the backend's store-time tripwire (schema.md §2) — it
                # is never itself persisted (MemoryBackend.store contract,
                # registries.py). With memory.type=none (all headline arms)
                # this call is a no-op regardless.
                episode = _build_episode(
                    question,
                    feedback,
                    self.ARM_NAME,
                    run_id=params.get("run_id"),
                    teacher_model=params.get("teacher_model"),
                )
                memory.store(episode, reference_answer=ground_truth)

        return records


@STRATEGY_REGISTRY.register("C")
class BlindTeacherArm(_TeacherArm):
    """C — an independent teacher gives feedback WITHOUT seeing GT (the
    treatment). C - B isolates the teacher-feedback effect (EVAL_SPEC §0)."""

    ARM_NAME = "C"
    TEACHER_VARIANT = "blind"
    REQUIRE_GT = False


@STRATEGY_REGISTRY.register("D")
class SightedTeacherArm(_TeacherArm):
    """D — teacher gives feedback WITH GT visible to the teacher (legal
    §0.2 use, its own prompt only). LEAKAGE CEILING — an upper bound on
    what's reachable by cheating, printed for context, NEVER a claimed
    result (EVAL_SPEC §1: "labeled leakage-ceiling")."""

    ARM_NAME = "D"
    TEACHER_VARIANT = "sighted"
    REQUIRE_GT = True
