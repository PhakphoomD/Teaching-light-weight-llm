"""FaissMemory tests (T2.5): round-trip persistence, ranking, tripwire
integration, per-run isolation, update_outcome math, and the phase6 red-team
fixture (schema.md Memory v2 contract; task spec docs/plan/T2.5-memory-block.md).

Uses the real sentence-transformers encoder + faiss (both installed in the
`tlw` env) — no mocking of the embedding path, since the tripwire's T-2 rule
depends on real cosine similarity behavior.
"""

import json
from pathlib import Path

import pytest

from src.tlw.memory.faiss_backend import FaissMemory
from src.tlw.registries import MEMORY_REGISTRY, build_memory_backend

REPO_ROOT = Path(__file__).resolve().parents[3]
GT_MEMORY_STORE = REPO_ROOT / "logs" / "experiments" / "phase6" / "gt_memory_store.jsonl"


def make_memory(tmp_path, name="run1", **kwargs):
    return FaissMemory(storage_dir=str(tmp_path / name), **kwargs)


# --- registration (also exercised end-to-end in test_registries.py) ---


def test_faiss_is_registered_in_memory_registry():
    assert "faiss" in MEMORY_REGISTRY.names()


def test_build_memory_backend_faiss_resolves(tmp_path):
    mem = build_memory_backend("faiss", storage_dir=str(tmp_path / "resolve"))
    assert isinstance(mem, FaissMemory)


# --- round-trip persistence ---


def test_round_trip_persistence(tmp_path):
    storage_dir = tmp_path / "roundtrip"
    mem = make_memory(tmp_path, "roundtrip")
    episode = {
        "question": "What raises blood sugar after meals?",
        "teaching_note": "Lead with the post-prandial mechanism, name 2-3 contributors, stay under 80 words.",
        "tags": ["diabetes"],
        "stats": {"attempts": 1, "success_count": 1, "success_rate": 1.0, "best_final_score": 0.81},
        "provenance": {"run_id": "test-run", "arm": "C", "teacher_model": "groq/qwen3-32b"},
    }
    record_id = mem.store(episode)
    assert record_id is not None

    # Reload from disk as a fresh instance -> same data available.
    reloaded = FaissMemory(storage_dir=str(storage_dir))
    results = reloaded.retrieve("What raises blood sugar after eating?", top_k=3)
    assert len(results) == 1
    assert results[0]["id"] == record_id
    assert "correct answer" not in results[0]["teaching_note"].lower()
    assert results[0]["teaching_note"] == episode["teaching_note"]

    stats = reloaded.stats()
    assert stats["total_episodes"] == 1
    assert stats["index_size"] == 1


# --- ranking order (success_rate desc, best_final_score desc, attempts desc, similarity desc) ---


def test_ranking_order_prefers_success_rate_then_score_then_attempts(tmp_path):
    mem = make_memory(tmp_path, "ranking")
    question = "How does insulin lower blood sugar?"

    def note(tag, success_rate, best_final_score, attempts):
        eid = mem.store(
            {
                "question": f"{question} ({tag})",
                "teaching_note": f"Coaching note {tag}: keep it mechanism-first and concise.",
                "stats": {
                    "attempts": attempts,
                    "success_count": int(round(success_rate * attempts)),
                    "success_rate": success_rate,
                    "best_final_score": best_final_score,
                },
            }
        )
        return eid

    low = note("low", 0.30, 0.50, 3)
    high = note("high", 0.90, 0.60, 2)
    mid = note("mid", 0.90, 0.80, 1)

    results = mem.retrieve(question, top_k=10)
    ids_in_order = [r["id"] for r in results]
    # mid (0.90, 0.80) beats high (0.90, 0.60) on best_final_score; low (0.30) trails both.
    assert ids_in_order.index(mid) < ids_in_order.index(high) < ids_in_order.index(low)


def test_retrieve_respects_similarity_and_success_floor(tmp_path):
    mem = make_memory(tmp_path, "floors", similarity_threshold=0.75, min_success_rate=0.30)
    mem.store(
        {
            "question": "What is the mechanism of metformin?",
            "teaching_note": "Focus on hepatic glucose output and insulin sensitivity, not a drug list.",
            "stats": {"attempts": 2, "success_count": 0, "success_rate": 0.0, "best_final_score": 0.2},
        }
    )
    # Below min_success_rate -> should not be offered even though it's the closest match.
    results = mem.retrieve("What is the mechanism of metformin?", top_k=3)
    assert results == []


def test_retrieve_empty_is_normal_on_fresh_store(tmp_path):
    mem = make_memory(tmp_path, "empty")
    assert mem.retrieve("anything", top_k=3) == []


# --- tripwire integration through store() ---


def test_store_rejects_the_exact_legacy_failure_mode(tmp_path):
    mem = make_memory(tmp_path, "tripwire")
    reference = "Metformin reduces hepatic glucose production and improves insulin sensitivity."
    episode = {
        "question": "How does metformin work?",
        "teaching_note": f"The correct answer is: {reference}",
    }
    result = mem.store(episode, reference_answer=reference)
    assert result is None
    # Nothing persisted: no episode, no vector.
    assert mem.stats()["total_episodes"] == 0
    assert mem.stats()["index_size"] == 0
    assert mem.stats()["rejects"] == 1
    assert mem.retrieve("How does metformin work?", top_k=3) == []


def test_reject_log_never_contains_the_note_or_reference_text(tmp_path):
    storage_dir = tmp_path / "rejectlog"
    mem = FaissMemory(storage_dir=str(storage_dir))
    reference = "Insulin resistance is a hallmark of type 2 diabetes."
    mem.store(
        {"question": "q", "teaching_note": f"The correct answer is: {reference}"},
        reference_answer=reference,
    )
    log_path = storage_dir / "memory_rejects.jsonl"
    assert log_path.exists()
    raw = log_path.read_text(encoding="utf-8")
    assert reference not in raw
    assert "correct answer" not in raw.lower()
    entry = json.loads(raw.strip().splitlines()[0])
    assert entry["event"] == "memory_reject"
    assert entry["reason"] == "T-1"
    assert "note_hash" in entry


def test_store_accepts_a_genuine_teaching_note_with_reference_present(tmp_path):
    mem = make_memory(tmp_path, "accept")
    reference = "Insulin resistance is a hallmark of type 2 diabetes."
    episode = {
        "question": "What is insulin resistance?",
        "teaching_note": "Define resistance as reduced cell response to insulin; give one consequence.",
    }
    record_id = mem.store(episode, reference_answer=reference)
    assert record_id is not None
    assert mem.stats()["total_episodes"] == 1
    assert mem.stats()["rejects"] == 0


def test_store_without_reference_answer_is_not_tripwire_gated(tmp_path):
    """Preferred design (§2): a caller with no GT at hand just omits it."""
    mem = make_memory(tmp_path, "no_ref")
    record_id = mem.store(
        {"question": "q", "teaching_note": "Any note text, since there is no reference to check against."}
    )
    assert record_id is not None


# --- per-run isolation ---


def test_per_run_isolation_no_cross_talk(tmp_path):
    run_a = make_memory(tmp_path, "run_a")
    run_b = make_memory(tmp_path, "run_b")

    run_a.store({"question": "shared question text", "teaching_note": "note from run A"})
    assert run_a.stats()["total_episodes"] == 1
    assert run_b.stats()["total_episodes"] == 0
    assert run_b.retrieve("shared question text", top_k=3) == []


# --- update_outcome math ---


def test_update_outcome_recomputes_success_rate_and_best_score(tmp_path):
    mem = make_memory(tmp_path, "outcome")
    record_id = mem.store(
        {
            "question": "q",
            "teaching_note": "a generic coaching note",
            "stats": {"attempts": 1, "success_count": 1, "success_rate": 1.0, "best_final_score": 0.5},
        }
    )
    mem.update_outcome(record_id, {"success": False, "final_score": 0.4})
    record = mem._id_to_record[record_id]
    assert record["stats"]["attempts"] == 2
    assert record["stats"]["success_count"] == 1
    assert record["stats"]["success_rate"] == pytest.approx(0.5)
    assert record["stats"]["best_final_score"] == pytest.approx(0.5)  # 0.4 does not beat 0.5

    mem.update_outcome(record_id, {"success": True, "final_score": 0.9})
    record = mem._id_to_record[record_id]
    assert record["stats"]["attempts"] == 3
    assert record["stats"]["success_count"] == 2
    assert record["stats"]["success_rate"] == pytest.approx(2 / 3)
    assert record["stats"]["best_final_score"] == pytest.approx(0.9)


def test_update_outcome_unknown_id_is_a_noop(tmp_path):
    mem = make_memory(tmp_path, "noop")
    mem.update_outcome("does-not-exist", {"success": True, "final_score": 1.0})  # must not raise


# --- red-team fixture: the phase6 GT-seeded memory store must be rejected 100% ---


@pytest.mark.skipif(not GT_MEMORY_STORE.exists(), reason="phase6/gt_memory_store.jsonl not present")
def test_red_team_phase6_gt_memory_store_rejected_100_percent(tmp_path):
    mem = make_memory(tmp_path, "redteam")
    lines = GT_MEMORY_STORE.read_text(encoding="utf-8").splitlines()
    sample = [json.loads(line) for line in lines if line.strip()][:15]  # bounded for test speed
    assert sample, "fixture produced no usable records"

    checked = 0
    for record in sample:
        feedback = record.get("teaching_feedback", "")
        marker = "Correct Answer:"
        if marker not in feedback:
            continue
        reference = feedback.split(marker, 1)[1].strip()
        if not reference:
            continue
        result = mem.store(
            {"question": record["question"], "teaching_note": feedback},
            reference_answer=reference,
        )
        assert result is None, f"tripwire failed to reject a known GT-bearing legacy record: {record['id']}"
        checked += 1

    assert checked > 0, "no phase6 records matched the expected 'Correct Answer:' shape"
    assert mem.stats()["total_episodes"] == 0
    assert mem.stats()["rejects"] == checked
