"""T3.3 RagMemory + grounding wiring + RAG-L3 leak guard.

Builds a tiny real index via the T3.2 builder (real MiniLM), then exercises the
`rag` backend and the loop's grounding path with fake student/judge clients so
no network/Ollama is needed.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.tlw.loop.core import grounding_block
from src.tlw.loop.strategies import BaselineArm
from src.tlw.registries import build_memory_backend
from tools.rag.builder import RagIndexBuilder


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


@pytest.fixture
def rag_index(tmp_path):
    train = [
        {"id": "t-1", "domain": "d", "question": "What is diabetes?",
         "answer": "Diabetes is a disease in which blood glucose stays too high over time."},
        {"id": "t-2", "domain": "d", "question": "What are kidney stones?",
         "answer": "Kidney stones are hard mineral deposits that form inside the kidneys."},
        {"id": "t-3", "domain": "d", "question": "What is a peptic ulcer?",
         "answer": "A peptic ulcer is an open sore in the lining of the stomach or duodenum."},
    ]
    tp = tmp_path / "train.jsonl"
    _write_jsonl(tp, train)
    out = tmp_path / "index"
    RagIndexBuilder(str(tp), str(out)).build()
    return out


class _FakeClient:
    """Records the last prompt it was asked to answer; returns a canned text."""

    def __init__(self, text="42"):
        self.text = text
        self.last_prompt = None

    def name(self):
        return "fake"

    def chat(self, messages, temperature=0.2, max_tokens=256, timeout_s=30, **kw):
        self.last_prompt = messages[-1]["content"]
        return SimpleNamespace(text=self.text, usage=None, error=None)


class _FakeJudge:
    def score(self, question, answer, mode):
        return {"score": 4, "normalized_score": 1.0, "passed": True, "null": False}


def test_rag_backend_resolves_and_retrieves(rag_index):
    backend = build_memory_backend("rag", corpus_path=str(rag_index), top_k=2, similarity_threshold=0.1)
    assert getattr(backend, "grounds_first_attempt", False) is True
    hits = backend.retrieve("Tell me about diabetes mellitus", top_k=2)
    assert hits, "expected at least one passage above the floor"
    assert "passage" in hits[0] and "teaching_note" not in hits[0]
    assert "diabetes" in hits[0]["passage"].lower()


def test_rag_store_and_update_are_noops(rag_index):
    backend = build_memory_backend("rag", corpus_path=str(rag_index))
    assert backend.store({"question": "q", "teaching_note": "n"}) is None
    assert backend.update_outcome("whatever", {"success": True}) is None
    s = backend.stats()
    assert s["backend"] == "rag" and s["corpus_size"] == 3


def test_similarity_floor_returns_empty(rag_index):
    backend = build_memory_backend("rag", corpus_path=str(rag_index), similarity_threshold=0.999)
    # An unrelated query cannot clear a 0.999 floor -> empty is normal.
    assert backend.retrieve("quantum chromodynamics lattice gauge theory", top_k=3) == []


def test_grounding_block_only_for_rag(rag_index):
    rag = build_memory_backend("rag", corpus_path=str(rag_index), similarity_threshold=0.1)
    block, dropped = grounding_block(rag, "What is diabetes?", top_k=2)
    assert block and "[1]" in block and dropped == 0
    # 'none' backend does not ground the first attempt.
    none_backend = build_memory_backend("none")
    assert grounding_block(none_backend, "What is diabetes?", top_k=2) == ("", 0)


def test_grounded_prompt_reaches_student(rag_index):
    rag = build_memory_backend("rag", corpus_path=str(rag_index), similarity_threshold=0.1)
    student, judge = _FakeClient(), _FakeJudge()
    arm = BaselineArm()
    records = arm.run(
        "What is diabetes?", student, teacher=None, memory=rag, judge=judge,
        params={"memory_top_k": 2, "student_temperature": 0.0},
    )
    assert records[0]["memory_used"] is True
    assert "REFERENCE PASSAGES" in student.last_prompt
    assert "diabetes" in student.last_prompt.lower()


def test_non_rag_run_is_ungrounded(rag_index):
    """A `none`-memory arm-A run renders the plain 'first' prompt (no regression)."""
    student, judge = _FakeClient(), _FakeJudge()
    arm = BaselineArm()
    records = arm.run(
        "What is diabetes?", student, teacher=None, memory=build_memory_backend("none"), judge=judge,
        params={"memory_top_k": 2, "student_temperature": 0.0},
    )
    assert records[0]["memory_used"] is False
    assert "REFERENCE PASSAGES" not in student.last_prompt


def test_rag_l3_filters_leaky_passage_and_continues():
    """RAG-L3 (hub decision 2026-07-16): a retrieved passage sharing a >=12-token
    shingle with the held-out gold is DROPPED from grounding (counted), and the
    run CONTINUES on the remaining passages — it does not abort. The student
    never sees the gold text."""

    gold = (
        "Gestational diabetes is a type of diabetes that develops only during "
        "pregnancy and usually goes away after the baby is born, but it raises risk later."
    )
    clean = "Type 2 diabetes is managed with diet, exercise, and sometimes medication like metformin."

    class _MixedRag:
        grounds_first_attempt = True

        def retrieve(self, query, top_k):
            return [
                {"passage": gold, "question": "q1", "similarity": 0.99},   # leaky -> filtered
                {"passage": clean, "question": "q2", "similarity": 0.60},  # clean -> kept
            ]

    student, judge = _FakeClient(), _FakeJudge()
    arm = BaselineArm()
    records = arm.run(
        "What is gestational diabetes?", student, teacher=None, memory=_MixedRag(), judge=judge,
        params={"memory_top_k": 3, "ground_truth": gold, "student_temperature": 0.0},
    )
    # ran to completion, one passage filtered, gold text never in the prompt
    assert records[0]["grounding_dropped"] == 1
    assert "goes away after the baby is born" not in student.last_prompt
    assert "metformin" in student.last_prompt  # the clean passage grounded the answer


def test_rag_l3_backstop_aborts_if_all_passages_leak():
    """If EVERY retrieved passage leaks, grounding is empty -> the plain 'first'
    prompt is used (ungrounded), which is gold-free, so the run still completes.
    The whole-prompt assert_gt_free backstop only fires if gold reaches the
    prompt through some other path."""
    gold = "Prolactinoma is a benign tumor of the pituitary gland that overproduces prolactin hormone daily."

    class _AllLeakRag:
        grounds_first_attempt = True

        def retrieve(self, query, top_k):
            return [{"passage": gold, "question": "q", "similarity": 0.99}]

    student, judge = _FakeClient(), _FakeJudge()
    arm = BaselineArm()
    records = arm.run(
        "What is prolactinoma?", student, teacher=None, memory=_AllLeakRag(), judge=judge,
        params={"memory_top_k": 3, "ground_truth": gold, "student_temperature": 0.0},
    )
    assert records[0]["grounding_dropped"] == 1
    assert records[0]["memory_used"] is False  # nothing survived -> ungrounded first prompt
    assert "REFERENCE PASSAGES" not in student.last_prompt
