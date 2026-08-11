"""Synthetic run-dir fixture factory for analysis tests.

Writes the same three files `src/tlw/runner.py` writes
(`config_used.json`, `rounds.jsonl`, `summary.jsonl`), shaped exactly like
the real fields verified live against the n=5 dry-run artifacts
(`runs/trackA_p2_arm{A,C}_diabetes__seed42__*`). Synthetic fixtures are the
primary test vehicle (task instructions) -- the real dry-run dirs are
used only for a separate shapes-only loader smoke test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pytest


def _write_run(
    run_dir: Path,
    *,
    arm: str,
    seed: int,
    memory_type: str = "none",
    passed_flags: Sequence[bool] = (),
    student_model: str = "qwen2.5:7b-instruct",
    judge_model: str = "llama3.1:8b",
    question_ids: Optional[List[str]] = None,
    memory_used_flags: Optional[Sequence[bool]] = None,
    reference_match_semantic: Optional[Sequence[float]] = None,
    reference_match_rouge: Optional[Sequence[float]] = None,
    student_tokens: int = 100,
    teacher_tokens: int = 0,
    judge_tokens: int = 50,
    memory_episodes: int = 0,
    memory_rejects: int = 0,
    rounds_per_question: Optional[Sequence[int]] = None,
    faithfulness_mean: Optional[float] = None,  # RAG groundedness diagnostic
    grounding_filtered: int = 0,
) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    n = len(passed_flags)
    if question_ids is None:
        question_ids = [f"diabetes-{i:05d}" for i in range(n)]
    if memory_used_flags is None:
        memory_used_flags = [False] * n
    if reference_match_semantic is None:
        reference_match_semantic = [0.5] * n
    if reference_match_rouge is None:
        reference_match_rouge = [0.2] * n
    if rounds_per_question is None:
        rounds_per_question = [1] * n

    config_used: Dict[str, Any] = {
        "student": {"provider": "local", "model": student_model, "temperature": 0.3, "max_tokens": 256, "timeout": 60},
        "teacher": {"provider": "groq", "model": "qwen/qwen3-32b", "temperature": 0.0, "max_tokens": 256, "timeout": 60},
        "preset": {"student": "minimal", "teacher": "orca"},
        "memory": {"type": memory_type, "embedding": "minilm", "top_k": 3, "similarity_threshold": 0.75},
        "params": {"max_rounds": 3, "early_stopping": {"enabled": False}, "arm": arm, "seed": seed},
        "eval": {
            "judge": {"provider": "local", "model": judge_model, "temperature": 0.0, "max_tokens": 16, "timeout": 60},
            "mode": "blind",
            "pass_threshold": 0.75,
            "metrics": {"weights": {"blind_score": 1.0}},
        },
    }
    (run_dir / "config_used.json").write_text(json.dumps(config_used, indent=2), encoding="utf-8")

    rounds_path = run_dir / "rounds.jsonl"
    with open(rounds_path, "w", encoding="utf-8") as f:
        for i in range(n):
            n_rounds = rounds_per_question[i]
            for rnd in range(1, n_rounds + 1):
                is_final = rnd == n_rounds
                row = {
                    "run_id": run_dir.name,
                    "arm": arm,
                    "memory_type": memory_type,
                    "seed": seed,
                    "question_id": question_ids[i],
                    "question_idx": i + 1,
                    "domain": "diabetes",
                    "question": f"synthetic question {i}",
                    "round": rnd,
                    "answer": f"synthetic answer {i} round {rnd}",
                    "feedback": None,
                    "score": 4 if (is_final and passed_flags[i]) else 1,
                    "normalized_score": 1.0 if (is_final and passed_flags[i]) else 0.25,
                    "passed": bool(passed_flags[i]) if is_final else False,
                    "memory_used": bool(memory_used_flags[i]) if is_final else False,
                    "teacher_called": arm in ("C", "D") and rnd > 1,
                    "reference_match": {
                        "semantic_sim": reference_match_semantic[i],
                        "rouge_l": reference_match_rouge[i],
                    },
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    passed_count = sum(1 for p in passed_flags if p)
    num_q = n
    summary = {
        "run_id": run_dir.name,
        "experiment_id": run_dir.name,
        "config_path": f"experiments/synthetic_arm{arm}.yml",
        "arm": arm,
        "memory_type": memory_type,
        "num_questions": num_q,
        "passed_count": passed_count,
        "pass_rate": (passed_count / num_q) if num_q else 0.0,
        "null_rate": 0.0,
        "seed": seed,
        "avg_rounds": (sum(rounds_per_question) / num_q) if num_q else 0.0,
        "metrics": {
            "blind_score_mean_normalized": (passed_count / num_q) if num_q else None,
            "reference_match": {
                "semantic_sim_mean": (sum(reference_match_semantic) / n) if n else None,
                "rouge_l_mean": (sum(reference_match_rouge) / n) if n else None,
            },
            "faithfulness": {
                "mean": faithfulness_mean,
                "n": (n if faithfulness_mean is not None else 0),
                "null": 0,
            },
        },
        "grounding_filtered_total": grounding_filtered,
        "student_calls": {"calls": n, "tokens": student_tokens, "seconds": 1.0, "errors": 0},
        "teacher_calls": {"calls": 0, "tokens": teacher_tokens, "seconds": 0.0, "errors": 0},
        "judge_calls": {"calls": n, "tokens": judge_tokens, "seconds": 1.0, "errors": 0},
        "memory_stats": {
            "total_episodes": memory_episodes,
            "total_attempts": 0,
            "overall_success_rate": 0.0,
            "index_size": memory_episodes,
            "rejects": memory_rejects,
        },
        "data_path": "data/clean/synthetic.jsonl",
        "limit": num_q,
        "elapsed_seconds": 1.0,
        "git_commit": "deadbeef",
        "timestamp": "2026-07-14T00:00:00+00:00",
        "config_used": config_used,
    }
    with open(run_dir / "summary.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    return run_dir


@pytest.fixture
def make_run(tmp_path):
    """Factory fixture: `make_run(name, arm=..., seed=..., passed_flags=[...])`
    writes a synthetic `runs/<name>/` dir under `tmp_path` and returns its Path."""

    def _factory(name: str, **kwargs) -> Path:
        return _write_run(tmp_path / name, **kwargs)

    return _factory


@pytest.fixture
def runs_root(tmp_path) -> Path:
    return tmp_path
