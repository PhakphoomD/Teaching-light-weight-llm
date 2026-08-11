"""The composition root: config -> six slots -> arm run -> summary.jsonl.

"we run this one file, and settings A(student)/B(teacher)/C(preset)/D(memory)/
E(params)/F(eval) decide everything; we only edit which one to use"
(docs/EXPERIMENT_RESULTS.md §5.3). This module is the ONLY place that builds a
client/memory/preset/judge/arm from a config and wires them together; every
block is imported only through its registry (registries.py) or `build_client`
(src/providers/factory.py) — never constructed by hand, never hardcoded.

Usage (with the `tlw` conda environment active):
    python run.py \\
        --config experiments/trackA_p2_armC_diabetes.yml [--data <jsonl>] [--limit N]

Outputs land under `runs/<run_id>/` (repo-root `runs/`, NOT `logs/experiments/`
— that dir is immutable evidence per structure.md and is guard-blocked for
writes, ADR-012):
    runs/<run_id>/config_used.json   # the fully-merged, resolved config (§0.3/§0.4)
    runs/<run_id>/rounds.jsonl       # one line per round per question
    runs/<run_id>/summary.jsonl      # one line, schema.md experiment-summary shape
    runs/<run_id>/memory/            # only created when memory.type != 'none'

`run_id = <config-stem>__seed<seed>__<UTC timestamp>` — arm and memory.type
are recorded explicitly in both the run_id's config stem and the summary body
so a headline (memory-off) run and a C'/D' memory-on ablation run can never be
conflated (schema.md Memory v2 contract §5, Config Contract V8).
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# --- Provider override ------------------------------------------------------
# MUST be imported before any build_client("local", ...) call in this module:
# it re-registers "local" -> Ollama (see src/tlw/providers.py docstring for
# why the existing "local" entry, LocalTinyLlama, is not what providers.md
# means by "local", and why silent re-registration is safe/verified here).
import src.tlw.providers  # noqa: F401,E402

# --- Registry-populating imports --------------------------------------------
# Each import is a side effect: it registers real implementations into the
# slot registries (registries.py). Importing all four before resolving any
# config value is required so params.arm / preset.* / memory.type / eval.mode
# never fall back to a missing/placeholder registration.
import src.tlw.evaluation  # noqa: F401,E402  registers "blind" judge
import src.tlw.memory  # noqa: F401,E402  registers "faiss" backend
import src.tlw.prompts  # noqa: F401,E402  registers "minimal"/"orca" presets
import src.tlw.loop  # noqa: F401,E402  registers "A"/"B"/"C"/"D" arm strategies

from src.providers.factory import build_client  # noqa: E402
from src.tlw.config.loader import load_config  # noqa: E402
from src.tlw.config.schema import ExperimentConfig  # noqa: E402
from src.tlw.evaluation.diagnostics import reference_match  # noqa: E402
from src.tlw.registries import (  # noqa: E402
    build_arm_strategy,
    build_judge,
    build_memory_backend,
)

# runner.py -> tlw -> src -> <project root>
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = (
    PROJECT_ROOT / "data" / "clean" / "Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl"
)
RUNS_ROOT = PROJECT_ROOT / "runs"


# --- small helpers -----------------------------------------------------------


def make_run_id(config_path: Path, seed: int, now: Optional[datetime] = None) -> str:
    """`<config-stem>__seed<seed>__<UTC timestamp>` (§0.3)."""
    ts = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return f"{Path(config_path).stem}__seed{seed}__{ts}"


def _git_commit_hash() -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:  # noqa: BLE001 - a missing git binary must not crash a run
        pass
    return None


def load_dataset(path: "os.PathLike[str] | str", limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Load a cleaned-record JSONL (schema.md "Cleaned record" shape:
    {id, domain, question, answer, ...}). Deterministic file order — no
    shuffling; `--limit N` takes the first N records so smoke/dry runs are
    exactly reproducible from (path, limit) alone."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"dataset not found: {p}")
    records: List[Dict[str, Any]] = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
            if limit is not None and len(records) >= limit:
                break
    return records


class _TokenCounter:
    """Thin proxy over an LLMClient that records call count / token usage /
    wall-clock seconds into a shared sink dict, keyed by role. Never changes
    behavior (`.chat(...)` args and return value pass straight through) — it
    exists purely so the runner can report honest timing/token numbers
     without editing the frozen loop-core call
    sites (`src/tlw/loop/core.py::_chat_text` discards `response.usage`)."""

    def __init__(self, client: Any, sink: Dict[str, Dict[str, Any]], key: str):
        self._client = client
        self._sink = sink
        self._key = key
        sink.setdefault(key, {"calls": 0, "tokens": 0, "seconds": 0.0, "errors": 0})

    def name(self) -> str:
        return self._client.name()

    def chat(self, messages, temperature=0.2, max_tokens=256, timeout_s=30, **kwargs):
        bucket = self._sink[self._key]
        t0 = time.time()
        result = self._client.chat(
            messages=messages, temperature=temperature, max_tokens=max_tokens, timeout_s=timeout_s
        )
        bucket["seconds"] += time.time() - t0
        bucket["calls"] += 1
        usage = getattr(result, "usage", None)
        total = getattr(usage, "total_tokens", 0) if usage else 0
        bucket["tokens"] += total or 0
        if getattr(result, "error", None):
            bucket["errors"] += 1
        return result


_EMPTY_FALLBACK_STATS: Dict[str, int] = {
    "count": 0,
    "primary_errors": 0,
    "retries": 0,
    "exhausted_no_fallback": 0,
}


def _parse_retry_after_seconds(error_text: Optional[str]) -> Optional[float]:
    """Best-effort extraction of a Retry-After hint from a provider's
    stringified error (`LLMClient.chat`'s contract is "never raise" — errors
    arrive as text, so we never see a raw HTTP header here). Matches shapes
    like "retry after 12.5s", "retry-after: 5", "Retry-After=3.2"."""
    if not error_text:
        return None
    m = re.search(r"retry[-_ ]?after[:=\s]+(\d+(?:\.\d+)?)", error_text, re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


class _FallbackClient:
    """Provider resilience for the long full run (hub request 2026-07-14,
    extended 2026-07-15 for the teacher AND judge slots): try a primary
    client; on error (returned `.error` or a raised exception), retry the
    SAME prompt on the primary with backoff (honoring a parsed Retry-After
    hint when the error text carries one, else exponential backoff capped at
    `max_backoff`) for up to `max_retries` attempts. If the primary is still
    failing and a `fallback` client is configured, the LAST attempt switches
    to it and the hit is counted into `sink[sink_key]['count']` so the
    summary shows honestly how many calls were served by the fallback (§0.1
    — a run where fallback fired a lot is flagged, not hidden). If NO
    fallback is configured (the Groq-70B case — hub instruction: never fall
    back to local for a 70B, an 8GB card can't run it), the call degrades to
    a null/error `ChatResult`-shaped result instead of raising, so one
    exhausted call never aborts a multi-hour run; that is counted into
    `sink[sink_key]['exhausted_no_fallback']`.

    Used for the teacher (B) and judge (F) slots only — see run.py's
    `--teacher-fallback` / `--judge-fallback` flags. NOT used for the student
    (always local, no fallback needed — hub design)."""

    def __init__(
        self,
        primary: Any,
        fallback: Optional[Any],
        sink: Dict[str, Dict[str, Any]],
        sink_key: str = "teacher_fallback",
        max_retries: int = 2,
        backoff_base: float = 1.0,
        max_backoff: float = 20.0,
        sleep_fn: Any = time.sleep,
    ):
        self._primary = primary
        self._fallback = fallback
        self._sink = sink
        self._sink_key = sink_key
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._max_backoff = max_backoff
        self._sleep = sleep_fn
        sink.setdefault(sink_key, dict(_EMPTY_FALLBACK_STATS))

    def name(self) -> str:
        return self._primary.name()

    def chat(self, messages, temperature=0.2, max_tokens=256, timeout_s=30, **kwargs):
        bucket = self._sink[self._sink_key]
        last_error_text: Optional[str] = None
        attempt = 0
        while True:
            try:
                result = self._primary.chat(
                    messages=messages, temperature=temperature, max_tokens=max_tokens, timeout_s=timeout_s
                )
                if not getattr(result, "error", None):
                    return result
                last_error_text = result.error
            except Exception as e:  # noqa: BLE001 — a long run must survive any primary failure
                last_error_text = str(e)
            bucket["primary_errors"] += 1
            if attempt >= self._max_retries:
                break
            wait = _parse_retry_after_seconds(last_error_text)
            if wait is None:
                wait = min(self._backoff_base * (2**attempt), self._max_backoff)
            bucket["retries"] += 1
            self._sleep(wait)
            attempt += 1

        if self._fallback is not None:
            bucket["count"] += 1
            try:
                return self._fallback.chat(
                    messages=messages, temperature=temperature, max_tokens=max_tokens, timeout_s=timeout_s
                )
            except Exception as e:  # noqa: BLE001 — the fallback itself must never abort the run
                return SimpleNamespace(text="", usage=None, error=f"fallback also failed: {e}")

        bucket["exhausted_no_fallback"] += 1
        return SimpleNamespace(
            text="", usage=None, error=f"primary exhausted retries, no fallback configured: {last_error_text}"
        )


def _build_params(cfg: ExperimentConfig, run_id: str, ground_truth: Optional[str]) -> Dict[str, Any]:
    """One question's `params` dict for `ArmStrategy.run(...)` (registries.py
    seam). `ground_truth` is included ONLY for arm D (its own teacher prompt
    may legally see it, §0.2) — absent/None for A/B/C so arm C stays blind by
    construction and the memory tripwire path is inert for the headline
    memory-off arms ("REQUIRED for arm D, absent/None
    elsewhere"). `reference_match` diagnostics for ALL arms are computed
    separately, post-hoc, by the runner (see `_diagnose_round` below) — that
    is a distinct, runner-only, legal score-path use of GT (teaching-loop-protocol.md §2,
    L10-L12) that never enters this params dict or any prompt."""
    params: Dict[str, Any] = {
        "run_id": run_id,
        "seed": cfg.params.seed,
        "max_rounds": cfg.params.max_rounds or 3,
        "student_temperature": cfg.student.temperature if cfg.student.temperature is not None else 0.3,
        "student_max_tokens": cfg.student.max_tokens or 256,
        "teacher_temperature": cfg.teacher.temperature if cfg.teacher.temperature is not None else 0.0,
        "teacher_max_tokens": cfg.teacher.max_tokens or 256,
        "memory_top_k": cfg.memory.top_k or 3,
        "teacher_model": cfg.teacher.model,
    }
    # ground_truth is passed to the arm ONLY as a guard input (never into a
    # prompt): arm D's teacher may legally see it (§0.2), and a rag run needs it
    # for the RAG-L3 leak guard on the grounded student prompt (ADR-026 —
    # a retrieved passage carrying a 12-token gold shingle aborts the run; the
    # build-time RAG-L1/L2 scrub is the primary seal, this is defence-in-depth).
    if cfg.params.arm == "D" or cfg.memory.type == "rag":
        params["ground_truth"] = ground_truth
    return params


def _diagnose_round(round_record: Dict[str, Any], ground_truth: Optional[str]) -> Optional[Dict[str, float]]:
    """Runner-level `reference_match` (teaching-loop-protocol.md §2, diagnostic-only,
    legal score-path use of GT) computed AFTER the arm/judge have already
    produced the round record, from a separate call site — this is what lets
    every arm (including A/B/C, which never receive `ground_truth` in
    `params`, see `_build_params`) still get an honest reference_match column
    without the GT ever reaching a student-bound prompt."""
    if not ground_truth:
        return None
    return reference_match(round_record.get("answer", ""), ground_truth)


# --- composition root ---------------------------------------------------------


def run_experiment(
    cfg: ExperimentConfig,
    config_path: Path,
    data_path: Path,
    limit: Optional[int],
    run_dir: Path,
    teacher_fallback: Optional[Tuple[str, str]] = None,
    judge_fallback: Optional[Tuple[str, str]] = None,
    compute_faithfulness: bool = True,
) -> Dict[str, Any]:
    """Build the six slots from `cfg` via the registries, run every question
    in `data_path` (first `limit` records if given) through the configured
    arm strategy, write `rounds.jsonl` + `summary.jsonl` under `run_dir`, and
    return the summary dict.

    `teacher_fallback` / `judge_fallback` are optional `(provider, model)`
    pairs (from `run.py --teacher-fallback` / `--judge-fallback`, format
    `provider:model`, e.g. `local:qwen2.5:7b-instruct`) — runtime resilience
    for the Groq-primary full run, not part of experiment identity (kept out
    of the Config Contract, build decision 3 precedent for `--data`)."""
    random.seed(cfg.params.seed)
    try:
        import numpy as np

        np.random.seed(cfg.params.seed)
    except ImportError:
        pass

    records = load_dataset(data_path, limit)
    if not records:
        raise RuntimeError(f"no records loaded from {data_path} (limit={limit})")

    run_id = run_dir.name
    call_stats: Dict[str, Dict[str, Any]] = {}

    # A / B — student / teacher clients (ProviderRegistry, slot A/B).
    student = _TokenCounter(build_client(cfg.student.provider, model=cfg.student.model), call_stats, "student")
    teacher_client = build_client(cfg.teacher.provider, model=cfg.teacher.model)
    if teacher_fallback:
        # Wrap so a Groq failure (after retry/backoff) transparently falls to
        # the given provider:model (hub request 2026-07-14). build_client
        # resolves "local" to Ollama here because src.tlw.providers is
        # imported at module top (see line ~43).
        fb_provider, fb_model = teacher_fallback
        teacher_client = _FallbackClient(
            teacher_client,
            build_client(fb_provider, model=fb_model),
            call_stats,
            sink_key="teacher_fallback",
        )
    teacher = _TokenCounter(teacher_client, call_stats, "teacher")

    # F — judge (JudgeRegistry via ProviderRegistry-built client, DI'd in so
    # its calls are counted too). Same fallback wrapping as the teacher —
    # §0.2's family check (V2) runs at config-validation time against the
    # PRIMARY judge only; a runtime fallback is a resilience concern, not
    # experiment identity (2026-07-15 hub note).
    judge_client_raw = build_client(cfg.eval.judge.provider, model=cfg.eval.judge.model)
    if judge_fallback:
        fb_provider, fb_model = judge_fallback
        judge_client_raw = _FallbackClient(
            judge_client_raw,
            build_client(fb_provider, model=fb_model),
            call_stats,
            sink_key="judge_fallback",
        )
    judge_client = _TokenCounter(judge_client_raw, call_stats, "judge")
    judge = build_judge(
        cfg.eval.mode,
        client=judge_client,
        temperature=cfg.eval.judge.temperature if cfg.eval.judge.temperature is not None else 0.0,
        max_tokens=cfg.eval.judge.max_tokens or 16,
        timeout=cfg.eval.judge.timeout or 60,
        pass_threshold=cfg.eval.pass_threshold if cfg.eval.pass_threshold is not None else 0.75,
    )

    # D — memory (MemoryRegistry). Per-run isolated storage_dir under this
    # run's own directory (schema.md Memory v2 §5); 'none' ignores it.
    memory_kwargs: Dict[str, Any] = {
        "embedding": cfg.memory.embedding,
        "top_k": cfg.memory.top_k,
        "similarity_threshold": cfg.memory.similarity_threshold,
        "min_success_rate": cfg.memory.min_success_rate,
        "max_episodes": cfg.memory.max_episodes,
        "gt_substring_shingle": cfg.memory.gt_substring_shingle,
        "gt_similarity_max": cfg.memory.gt_similarity_max,
        "seed_from": cfg.memory.seed_from,
        "corpus_path": cfg.memory.corpus_path,  # rag backend; ignored by none/faiss
        "max_passage_words": cfg.memory.max_passage_words,
        "aspect_rerank": bool(cfg.memory.aspect_rerank),  # aspect-aware reranking
    }
    if cfg.memory.type != "none":
        memory_kwargs["storage_dir"] = str(run_dir / "memory")
    memory = build_memory_backend(cfg.memory.type, **memory_kwargs)

    # Faithfulness diagnostic (rag-medquad-protocol §4.2) — built ONLY for rag runs
    # (it needs retrieved passages). Reuses the SAME judge model as the blind
    # correctness judge for one consistent evaluator; it sees (answer, passages)
    # only, never the gold answer (§0.2). Computed post-hoc like reference_match,
    # NEVER merged into pass/fail (ADR-019). Uses the same faithfulness client
    # as the correctness judge so its calls are counted in judge_calls.
    faithfulness_judge = None
    if cfg.memory.type == "rag" and compute_faithfulness:
        from src.tlw.evaluation.faithfulness import FaithfulnessJudge

        faithfulness_judge = FaithfulnessJudge(
            client=judge_client,
            temperature=cfg.eval.judge.temperature if cfg.eval.judge.temperature is not None else 0.0,
            max_tokens=cfg.eval.judge.max_tokens or 256,
            timeout=cfg.eval.judge.timeout or 60,
        )

    # C + E — preset names + arm strategy (PresetRegistry resolved lazily
    # inside the arm; StrategyRegistry here).
    arm = build_arm_strategy(
        cfg.params.arm,
        student_preset_name=cfg.preset.student,
        teacher_preset_name=cfg.preset.teacher,
    )

    rounds_path = run_dir / "rounds.jsonl"
    passed_flags: List[bool] = []
    null_count = 0
    round_counts: List[int] = []
    final_normalized: List[float] = []
    ref_semantic: List[float] = []
    ref_rouge: List[float] = []
    grounding_filtered_total = 0  # RAG-L3 passages dropped across the run (§0.1 observability)
    faithfulness_values: List[float] = []  # RAG groundedness diagnostic (rag runs only)
    faithfulness_null = 0

    t_start = time.time()
    with open(rounds_path, "w", encoding="utf-8") as rf:
        for idx, rec in enumerate(records, start=1):
            question = rec["question"]
            ground_truth = rec.get("answer")

            params = _build_params(cfg, run_id, ground_truth)
            round_records = arm.run(question, student, teacher, memory, judge, params)

            final = round_records[-1] if round_records else None
            final_passed = bool(final.get("passed")) if final else False
            passed_flags.append(final_passed)
            round_counts.append(len(round_records))
            if final is not None and final.get("score") is None:
                null_count += 1
            if final is not None and final.get("normalized_score") is not None:
                final_normalized.append(final["normalized_score"])

            for r in round_records:
                grounding_filtered_total += r.get("grounding_dropped", 0) or 0
                diag = _diagnose_round(r, ground_truth)
                r["reference_match"] = diag
                if diag:
                    ref_semantic.append(diag["semantic_sim"])
                    ref_rouge.append(diag["rouge_l"])
                # Faithfulness (rag only) — groundedness of this answer vs the
                # passages it was shown; diagnostic, never gates (rag-medquad-protocol §4.2).
                if faithfulness_judge is not None and r.get("grounding_context"):
                    fscore = faithfulness_judge.score(r.get("answer", ""), r["grounding_context"])
                    r["faithfulness"] = fscore.get("faithfulness")
                    if fscore.get("faithfulness") is None:
                        faithfulness_null += 1
                    else:
                        faithfulness_values.append(fscore["faithfulness"])
                row = {
                    "run_id": run_id,
                    "arm": cfg.params.arm,
                    "memory_type": cfg.memory.type,
                    "seed": cfg.params.seed,
                    "question_id": rec.get("id"),
                    "question_idx": idx,
                    "domain": rec.get("domain"),
                    "question": question,
                    **r,
                }
                rf.write(json.dumps(row, ensure_ascii=False) + "\n")

    elapsed = time.time() - t_start

    num_q = len(records)
    passed_count = sum(1 for p in passed_flags if p)
    pass_rate = (passed_count / num_q) if num_q else 0.0
    avg_rounds = (sum(round_counts) / num_q) if num_q else 0.0

    summary = {
        "run_id": run_id,
        "experiment_id": run_id,
        "config_path": str(config_path),
        "arm": cfg.params.arm,
        "memory_type": cfg.memory.type,
        "num_questions": num_q,
        "passed_count": passed_count,
        "pass_rate": pass_rate,
        "null_rate": (null_count / num_q) if num_q else 0.0,
        "seed": cfg.params.seed,
        "avg_rounds": avg_rounds,
        "metrics": {
            "blind_score_mean_normalized": (
                sum(final_normalized) / len(final_normalized) if final_normalized else None
            ),
            "reference_match": {
                "semantic_sim_mean": (sum(ref_semantic) / len(ref_semantic)) if ref_semantic else None,
                "rouge_l_mean": (sum(ref_rouge) / len(ref_rouge)) if ref_rouge else None,
            },
            "faithfulness": {  # RAG groundedness diagnostic (rag runs only)
                "mean": (sum(faithfulness_values) / len(faithfulness_values)) if faithfulness_values else None,
                "n": len(faithfulness_values),
                "null": faithfulness_null,
            },
        },
        "student_calls": call_stats.get("student", {}),
        "teacher_calls": call_stats.get("teacher", {}),
        "teacher_fallback": call_stats.get("teacher_fallback", dict(_EMPTY_FALLBACK_STATS)),
        "teacher_fallback_configured": (
            f"{teacher_fallback[0]}:{teacher_fallback[1]}" if teacher_fallback else None
        ),
        "judge_calls": call_stats.get("judge", {}),
        "judge_fallback": call_stats.get("judge_fallback", dict(_EMPTY_FALLBACK_STATS)),
        "judge_fallback_configured": f"{judge_fallback[0]}:{judge_fallback[1]}" if judge_fallback else None,
        "memory_stats": memory.stats(),
        "grounding_filtered_total": grounding_filtered_total,
        "data_path": str(data_path),
        "limit": limit,
        "elapsed_seconds": elapsed,
        "git_commit": _git_commit_hash(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config_used": cfg.to_dict(),
    }

    with open(run_dir / "summary.jsonl", "w", encoding="utf-8") as sf:
        sf.write(json.dumps(summary, ensure_ascii=False) + "\n")

    return summary


def print_summary(summary: Dict[str, Any]) -> None:
    """Honest console summary: correctness AND reference_match as SEPARATE
    columns, never merged (teaching-loop-protocol.md §2, ADR-019)."""
    rm = summary["metrics"]["reference_match"]
    sem = rm["semantic_sim_mean"]
    rouge = rm["rouge_l_mean"]
    blind_mean = summary["metrics"]["blind_score_mean_normalized"]

    print("\n" + "=" * 72)
    print(f"run_id    : {summary['run_id']}")
    print(f"config    : {summary['config_path']}")
    print(f"arm       : {summary['arm']}   memory.type = {summary['memory_type']}")
    print(f"data      : {summary['data_path']}  (limit={summary['limit']})")
    print(f"seed      : {summary['seed']}")
    print("-" * 72)
    print(
        f"correctness  (HEADLINE, blind judge, PASS>=threshold)  "
        f"pass_rate = {summary['pass_rate']:.3f}  "
        f"({summary['passed_count']}/{summary['num_questions']})   "
        f"null_rate = {summary['null_rate']:.3f}   "
        f"mean_normalized = {'n/a' if blind_mean is None else f'{blind_mean:.3f}'}"
    )
    print(
        f"reference_match (DIAGNOSTIC ONLY — never merged, ADR-019)   "
        f"semantic_sim = {'n/a' if sem is None else f'{sem:.3f}'}   "
        f"rouge_l = {'n/a' if rouge is None else f'{rouge:.3f}'}"
    )
    faith = summary["metrics"].get("faithfulness") or {}
    if faith.get("n"):
        print(
            f"faithfulness   (DIAGNOSTIC ONLY — RAG groundedness, never gates)   "
            f"mean = {faith['mean']:.3f}  (n={faith['n']}, null={faith['null']})   "
            f"grounding_filtered = {summary.get('grounding_filtered_total', 0)}"
        )
    print("-" * 72)
    print(f"avg_rounds       : {summary['avg_rounds']:.2f}")
    print(f"elapsed_seconds  : {summary['elapsed_seconds']:.1f}")
    for role in ("student", "teacher", "judge"):
        c = summary.get(f"{role}_calls") or {}
        if c.get("calls"):
            print(
                f"  {role:8s} calls={c['calls']:<5d} tokens={c['tokens']:<8d} "
                f"seconds={c['seconds']:.1f}  errors={c.get('errors', 0)}"
            )
    for role in ("teacher", "judge"):
        configured = summary.get(f"{role}_fallback_configured")
        fb = summary.get(f"{role}_fallback") or {}
        if configured:
            print(
                f"  {role:8s} fallback={configured}  served={fb.get('count', 0)}  "
                f"retries={fb.get('retries', 0)}  primary_errors={fb.get('primary_errors', 0)}  "
                f"exhausted_no_fallback={fb.get('exhausted_no_fallback', 0)}"
            )
    print("=" * 72 + "\n")


def _parse_provider_model(spec: str) -> Tuple[str, str]:
    """`provider:model` -> (provider, model). Splits on the FIRST colon only
    — Ollama model tags themselves contain colons (e.g. `qwen2.5:7b-instruct`),
    so `local:qwen2.5:7b-instruct` must split to `("local", "qwen2.5:7b-instruct")`,
    not three pieces."""
    if ":" not in spec:
        raise argparse.ArgumentTypeError(
            f"expected 'provider:model' (e.g. 'local:qwen2.5:7b-instruct'), got {spec!r}"
        )
    provider, model = spec.split(":", 1)
    provider, model = provider.strip(), model.strip()
    if not provider or not model:
        raise argparse.ArgumentTypeError(f"expected 'provider:model', got {spec!r}")
    return provider, model


def main(argv: Optional[List[str]] = None) -> int:
    load_dotenv()  # GROQ_API_KEY, same convention as calibration.py / legacy loop

    parser = argparse.ArgumentParser(
        description=(
            "Track-A runner (T2.6): run.py --config experiments/<file>.yml "
            "[--data <jsonl>] [--limit N]. Dataset selection is a CLI concern, "
            "not a config slot (T2.6 build decision 3, no slot G)."
        )
    )
    parser.add_argument("--config", required=True, help="experiments/*.yml override (Config Contract v1)")
    parser.add_argument(
        "--data",
        default=None,
        help="dataset JSONL path (default: Diabetes heldout, data/clean/*_heldout.jsonl). "
        "Smoke/dry runs MUST pass the *_train.jsonl split (§0.2 — never held-out).",
    )
    parser.add_argument("--limit", type=int, default=None, help="only run the first N records")
    parser.add_argument(
        "--runs-dir", default=None, help="override the runs/ output root (tests only, not for real runs)"
    )
    parser.add_argument(
        "--teacher-fallback",
        default=None,
        type=_parse_provider_model,
        metavar="provider:model",
        help="fallback client for the teacher slot (B) if the primary errors "
        "after retry/backoff — resilience for the Groq-primary full run (hub "
        "request 2026-07-14/2026-07-15). e.g. local:qwen2.5:7b-instruct. "
        "NEVER point this at a 70B (hub instruction — can't run locally on 8GB). "
        "Off by default (no fallback = retry/backoff only, then a null result).",
    )
    parser.add_argument(
        "--judge-fallback",
        default=None,
        type=_parse_provider_model,
        metavar="provider:model",
        help="fallback client for the judge slot (F) if the primary errors "
        "after retry/backoff. e.g. local:llama3.1:8b. §0.2's judge-family "
        "check (V2) runs against the config-declared PRIMARY judge only — a "
        "runtime fallback is a resilience concern, not experiment identity. "
        "Off by default.",
    )
    parser.add_argument(
        "--no-faithfulness",
        action="store_true",
        help="skip the inline RAG faithfulness diagnostic (T3.4). Use for the full "
        "rag run so the correctness judge (Groq) stays within the daily token cap "
        "and consistent — faithfulness is computed offline afterward (a diagnostic, "
        "never the headline). No effect on non-rag runs.",
    )
    parser.add_argument(
        "--teacher-fallback-model",
        default=None,
        help="DEPRECATED alias for '--teacher-fallback local:<model>' (T2.6 "
        "original flag, local-only). Prefer --teacher-fallback. Ignored if "
        "--teacher-fallback is also given.",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    cfg = load_config(config_path)

    data_path = Path(args.data) if args.data else DEFAULT_DATA_PATH
    runs_root = Path(args.runs_dir) if args.runs_dir else RUNS_ROOT

    teacher_fallback = args.teacher_fallback
    if teacher_fallback is None and args.teacher_fallback_model:
        teacher_fallback = ("local", args.teacher_fallback_model)

    run_id = make_run_id(config_path, cfg.params.seed)
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Record the exact merged/resolved config alongside the run (§0.3/§0.4) —
    # in addition to `config_used` inside summary.jsonl, as a standalone file
    # for quick inspection without parsing JSONL.
    (run_dir / "config_used.json").write_text(
        json.dumps(cfg.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    summary = run_experiment(
        cfg, config_path, data_path, args.limit, run_dir,
        teacher_fallback=teacher_fallback,
        judge_fallback=args.judge_fallback,
        compute_faithfulness=not args.no_faithfulness,
    )
    print_summary(summary)
    print(f"rounds  -> {run_dir / 'rounds.jsonl'}")
    print(f"summary -> {run_dir / 'summary.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
