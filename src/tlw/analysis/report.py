"""Report assembly (T2.8 steps 1-2 + CLI table). Turns loaded runs into the
tables T2.8 asks for -- WITHOUT ever writing `docs/TRACK_A_RESULTS.md`
(that is the REPORT half of T2.8, out of scope: no full run exists yet).

Two hard rules enforced here, not just documented:
- **correctness and reference_match are NEVER merged** into one number
  (ADR-019, teaching-loop-protocol §2) -- they live in separate dict keys everywhere in
  this module and the CLI prints them as separate lines.
- **Sample-size honesty banner.** Any comparison built from fewer than the
  pre-registered 125 held-out questions or fewer than 3 seeds gets a loud
  "NOT the pre-registered sample" banner, so a pilot/dry-run (n=5, 1 seed)
  can never be silently read as the headline result (T2.8 build rule 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .loaders import (
    RunRecord,
    assert_single_memory_type,
    build_cluster_table,
    final_passes_by_question,
    load_rounds,
    select_arm_runs,
)
from .stats import (
    BootstrapResult,
    McNemarResult,
    WilsonInterval,
    exact_mcnemar,
    paired_cluster_bootstrap,
    per_seed_deltas,
    wilson_interval,
)

PRE_REGISTERED_N_QUESTIONS = 125  # teaching-loop-protocol.md §4.4 -- the held-out set size
PRE_REGISTERED_N_SEEDS = 3  # teaching-loop-protocol.md §4.1 -- {13, 42, 123}
NOT_PRE_REGISTERED_BANNER = (
    "*** NOT the pre-registered sample -- this is pilot/dry-run data "
    "(n<{n} questions and/or <{s} seeds). Do NOT read this as the Track-A "
    "headline result (teaching-loop-protocol.md §4.4, T2.8 Must-NOT). ***"
)


# --- descriptive per-arm view -------------------------------------------------


def pooled_pass_rate(runs: Sequence[RunRecord]) -> Tuple[int, int]:
    """(k, n) pooled across every run handed in (e.g. all seeds of one
    arm+memory.type). Uses `passed_count`/`num_questions` straight from
    `summary.jsonl`, so this number matches the source log by construction
    (§0.1) -- no independent recount from rounds.jsonl needed for k/n."""
    k = sum(int(r.passed_count or 0) for r in runs)
    n = sum(int(r.num_questions or 0) for r in runs)
    return k, n


def arm_descriptive(runs_by_arm: Dict[str, List[RunRecord]]) -> Dict[str, WilsonInterval]:
    """Wilson 95% interval per arm, pooling all seeds handed in for that
    arm (teaching-loop-protocol §4.2 "Secondary/descriptive -- Wilson score interval
    per arm")."""
    out: Dict[str, WilsonInterval] = {}
    for arm, runs in runs_by_arm.items():
        k, n = pooled_pass_rate(runs)
        out[arm] = wilson_interval(k, n)
    return out


# --- sample-size honesty banner ------------------------------------------------


def not_pre_registered_reasons(
    runs: Sequence[RunRecord],
    pre_registered_n: int = PRE_REGISTERED_N_QUESTIONS,
    pre_registered_seeds: int = PRE_REGISTERED_N_SEEDS,
) -> List[str]:
    """Concrete reasons a run group falls short of the pre-registered
    sample, or [] if it meets it. Every run must independently cover
    `pre_registered_n` questions (a short run doesn't average out) AND the
    group must cover `pre_registered_seeds` distinct seeds."""
    reasons: List[str] = []
    short_runs = [r for r in runs if r.num_questions < pre_registered_n]
    if short_runs:
        worst = min((r.num_questions for r in short_runs), default=0)
        reasons.append(
            f"{len(short_runs)} run(s) have num_questions < {pre_registered_n} "
            f"(smallest: {worst})"
        )
    seeds = {r.seed for r in runs if r.seed is not None}
    if len(seeds) < pre_registered_seeds:
        reasons.append(f"only {len(seeds)} distinct seed(s) present (need >= {pre_registered_seeds})")
    return reasons


def banner_for(
    runs: Sequence[RunRecord],
    pre_registered_n: int = PRE_REGISTERED_N_QUESTIONS,
    pre_registered_seeds: int = PRE_REGISTERED_N_SEEDS,
) -> Optional[str]:
    reasons = not_pre_registered_reasons(runs, pre_registered_n, pre_registered_seeds)
    if not reasons:
        return None
    return NOT_PRE_REGISTERED_BANNER.format(n=pre_registered_n, s=pre_registered_seeds) + " Reasons: " + "; ".join(
        reasons
    )


# --- secondary views (T2.8 step 2) --------------------------------------------


def reference_match_divergence(runs_by_arm: Dict[str, List[RunRecord]]) -> Dict[str, Dict[str, Optional[float]]]:
    """Per-arm correctness vs reference_match, SIDE BY SIDE, never merged
    (ADR-019). Divergence itself (correctness up, reference_match flat/
    down, or vice versa) is the finding teaching-loop-protocol §2 calls out -- this
    function just assembles the two columns; callers/CLI compute/print the
    divergence."""
    out: Dict[str, Dict[str, Optional[float]]] = {}
    for arm, runs in runs_by_arm.items():
        k, n = pooled_pass_rate(runs)
        correctness = (k / n) if n else None
        sem_vals = [
            r.summary.get("metrics", {}).get("reference_match", {}).get("semantic_sim_mean")
            for r in runs
        ]
        rouge_vals = [
            r.summary.get("metrics", {}).get("reference_match", {}).get("rouge_l_mean") for r in runs
        ]
        sem_vals = [v for v in sem_vals if v is not None]
        rouge_vals = [v for v in rouge_vals if v is not None]
        out[arm] = {
            "correctness_pass_rate": correctness,
            "reference_match_semantic_sim_mean": (sum(sem_vals) / len(sem_vals)) if sem_vals else None,
            "reference_match_rouge_l_mean": (sum(rouge_vals) / len(rouge_vals)) if rouge_vals else None,
        }
    return out


def rounds_to_pass_distribution(runs: Sequence[RunRecord]) -> Dict[str, int]:
    """Histogram of "which round did this question first pass on" across
    every run handed in. Key `"never"` counts questions whose final round
    never passed. Read directly from `rounds.jsonl` (`round`, `passed`)."""
    hist: Dict[str, int] = {}
    for run in runs:
        rounds = load_rounds(run.path)
        by_question: Dict[Any, List[Dict[str, Any]]] = {}
        for row in rounds:
            by_question.setdefault(row.get("question_id"), []).append(row)
        for qid, rows in by_question.items():
            rows_sorted = sorted(rows, key=lambda r: r.get("round", 0))
            first_pass = next((r.get("round") for r in rows_sorted if r.get("passed")), None)
            key = str(first_pass) if first_pass is not None else "never"
            hist[key] = hist.get(key, 0) + 1
    return hist


def token_cost_per_arm(runs_by_arm: Dict[str, List[RunRecord]]) -> Dict[str, Dict[str, int]]:
    """Total tokens (student + teacher + judge) per arm, summed across the
    runs handed in (`summary.jsonl`'s `{role}_calls.tokens`)."""
    out: Dict[str, Dict[str, int]] = {}
    for arm, runs in runs_by_arm.items():
        totals = {"student": 0, "teacher": 0, "judge": 0}
        for r in runs:
            for role in totals:
                totals[role] += int((r.summary.get(f"{role}_calls") or {}).get("tokens", 0) or 0)
        totals["total"] = sum(totals[role] for role in ("student", "teacher", "judge"))
        out[arm] = totals
    return out


def memory_note_usage(runs_by_arm: Dict[str, List[RunRecord]]) -> Dict[str, Dict[str, Any]]:
    """Memory-note usage per arm: how many rounds actually used a
    retrieved note (`memory_used` on rounds.jsonl rows) plus the store's
    own `memory_stats` from `summary.jsonl` (episodes/rejects). For
    headline (memory.type=none) arms this is expected to be all zero --
    a non-zero value there is itself a bug signal."""
    out: Dict[str, Dict[str, Any]] = {}
    for arm, runs in runs_by_arm.items():
        used = 0
        total_rounds = 0
        episodes = 0
        rejects = 0
        for r in runs:
            for row in load_rounds(r.path):
                total_rounds += 1
                if row.get("memory_used"):
                    used += 1
            stats = r.summary.get("memory_stats") or {}
            episodes += int(stats.get("total_episodes", 0) or 0)
            rejects += int(stats.get("rejects", 0) or 0)
        out[arm] = {
            "rounds_using_memory": used,
            "total_rounds": total_rounds,
            "memory_hit_rate": (used / total_rounds) if total_rounds else 0.0,
            "total_episodes_stored": episodes,
            "total_rejects": rejects,
        }
    return out


# --- comparison assembly -------------------------------------------------------


@dataclass
class ComparisonResult:
    arm_a: str
    arm_b: str
    memory_type: str
    bootstrap: BootstrapResult
    mcnemar: McNemarResult
    per_seed: Dict[int, float]
    banner: Optional[str]


def build_comparison(
    runs: Sequence[RunRecord],
    arm_a: str,
    arm_b: str,
    memory_type: str = "none",
    n_resamples: int = 10_000,
    seed: int = 0,
    pre_registered_n: int = PRE_REGISTERED_N_QUESTIONS,
    pre_registered_seeds: int = PRE_REGISTERED_N_SEEDS,
) -> ComparisonResult:
    """The headline machinery for one arm pair (e.g. C-B): select runs at
    `memory_type` for both arms (V8-guarded), pool seeds into a cluster
    table, run the paired bootstrap + McNemar, and attach the honesty
    banner if the sample falls short of the pre-registration."""
    runs_a = select_arm_runs(runs, arm_a, memory_type)
    runs_b = select_arm_runs(runs, arm_b, memory_type)
    if not runs_a:
        raise ValueError(f"no runs found for arm {arm_a!r} at memory.type={memory_type!r}")
    if not runs_b:
        raise ValueError(f"no runs found for arm {arm_b!r} at memory.type={memory_type!r}")

    # V8 guard: every run selected for THIS comparison must share one
    # memory.type (already true by construction via select_arm_runs, but
    # re-asserted here so a future refactor can't silently drop the filter).
    assert_single_memory_type(runs_a, context=f"arm {arm_a}")
    assert_single_memory_type(runs_b, context=f"arm {arm_b}")

    cluster_table, seed_index = build_cluster_table({arm_a: runs_a, arm_b: runs_b})
    bootstrap = paired_cluster_bootstrap(cluster_table, arm_a, arm_b, n_resamples=n_resamples, seed=seed)

    pairs: List[Tuple[bool, bool]] = []
    for qid, arms in cluster_table.items():
        if arm_a in arms and arm_b in arms:
            for pa, pb in zip(arms[arm_a], arms[arm_b]):
                pairs.append((pa, pb))
    mcnemar = exact_mcnemar(pairs, arm_a=arm_a, arm_b=arm_b)

    all_seeds = sorted({r.seed for r in (*runs_a, *runs_b) if r.seed is not None})
    seed_deltas = per_seed_deltas(cluster_table, arm_a, arm_b, all_seeds, seed_index)

    banner = banner_for(list(runs_a) + list(runs_b), pre_registered_n, pre_registered_seeds)

    return ComparisonResult(
        arm_a=arm_a,
        arm_b=arm_b,
        memory_type=memory_type,
        bootstrap=bootstrap,
        mcnemar=mcnemar,
        per_seed=seed_deltas,
        banner=banner,
    )


def build_report(
    runs: Sequence[RunRecord],
    comparisons: Sequence[Tuple[str, str]] = (("C", "B"), ("B", "A"), ("D", "C")),
    memory_type: str = "none",
    n_resamples: int = 10_000,
    seed: int = 0,
    pre_registered_n: int = PRE_REGISTERED_N_QUESTIONS,
    pre_registered_seeds: int = PRE_REGISTERED_N_SEEDS,
) -> Dict[str, Any]:
    """Assemble the full T2.8-step-1/2 report dict for one `memory_type`
    slice of the runs (headline = "none"; pass "faiss" for the C'/D'
    ablation -- callers must not mix the two in one `build_report` call,
    each comparison inside re-asserts V8 per-arm anyway)."""
    arms_present = sorted({r.arm for r in runs if r.memory_type == memory_type and r.arm})
    runs_by_arm = {arm: select_arm_runs(runs, arm, memory_type) for arm in arms_present}

    comparisons_out: Dict[str, ComparisonResult] = {}
    comparison_errors: Dict[str, str] = {}
    for arm_a, arm_b in comparisons:
        label = f"{arm_a}-{arm_b}"
        try:
            comparisons_out[label] = build_comparison(
                runs,
                arm_a,
                arm_b,
                memory_type=memory_type,
                n_resamples=n_resamples,
                seed=seed,
                pre_registered_n=pre_registered_n,
                pre_registered_seeds=pre_registered_seeds,
            )
        except ValueError as exc:
            comparison_errors[label] = str(exc)

    return {
        "memory_type": memory_type,
        "arms_present": arms_present,
        "descriptive": arm_descriptive(runs_by_arm),
        "comparisons": comparisons_out,
        "comparison_errors": comparison_errors,
        "reference_match": reference_match_divergence(runs_by_arm),
        "rounds_to_pass": {arm: rounds_to_pass_distribution(rs) for arm, rs in runs_by_arm.items()},
        "token_cost": token_cost_per_arm(runs_by_arm),
        "memory_usage": memory_note_usage(runs_by_arm),
        "banner": banner_for(list(runs), pre_registered_n, pre_registered_seeds),
    }
