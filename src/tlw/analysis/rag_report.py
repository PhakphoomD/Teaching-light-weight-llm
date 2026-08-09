"""RAG ablation report (T3.4, rag-medquad-protocol §4/§6) — the {3B, 3B+RAG, 7B, 7B+RAG}
table + headline delta, reusing the Track-A statistics machinery.

Why a separate module from report.py: the Track-A report keys everything by the
ADR-002 **arm letter** (A/B/C/D) and enforces the V8 single-memory-type guard
(headline `none` runs must never mix with C'/D' `faiss` runs). The RAG ablation
is different on both axes:
  - every arm is **A** (single-pass); the conditions differ by
    (student_model, memory_type), so we key by a **RAG label** (3B / 3B+RAG / …).
  - the headline **intentionally** compares `memory none` (3B) vs `memory rag`
    (3B+RAG) — crossing memory.type is the DESIGN here (retrieval on vs off),
    not a V8 conflation. So this module does NOT apply the V8 guard.

Everything else is reused verbatim from report.py/stats.py (the CI machinery is
identical to Track A, so the RAG number is directly comparable): Wilson per
label, paired cluster bootstrap + exact McNemar for the delta, the pre-
registration honesty banner. Adds one RAG-only diagnostic column: faithfulness.
Correctness stays the headline; faithfulness/reference_match are NEVER merged
(ADR-019).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .loaders import RunRecord, build_cluster_table, load_rounds
from .report import (
    PRE_REGISTERED_N_QUESTIONS,
    PRE_REGISTERED_N_SEEDS,
    arm_descriptive,
    banner_for,
    reference_match_divergence,
    token_cost_per_arm,
)
from .stats import exact_mcnemar, paired_cluster_bootstrap, per_seed_deltas

# Explicit map for the two product models (ADR-015 floor 3B / ceiling 7B); the
# regex fallback covers any other `<n>b` model name.
_MODEL_LABEL = {"qwen2.5:3b": "3B", "qwen2.5:7b-instruct": "7B"}
_NB_RE = re.compile(r"(\d+(?:\.\d+)?)b")

# Default RAG comparisons (rag-medquad-protocol §6): headline first.
DEFAULT_RAG_COMPARISONS: Tuple[Tuple[str, str], ...] = (
    ("3B+RAG", "3B"),   # HEADLINE — the RAG effect
    ("7B+RAG", "7B"),   # does RAG still help a stronger model?
    ("3B+RAG", "7B"),   # can retrieval lift a 3B to a 7B's level?
)


def rag_label(run: RunRecord) -> str:
    """(student_model, memory_type) -> a RAG condition label, e.g. '3B+RAG'."""
    model = run.student_model or "?"
    short = _MODEL_LABEL.get(model)
    if short is None:
        m = _NB_RE.search(model.lower())
        short = (m.group(1) + "B") if m else model
    return f"{short}+RAG" if run.memory_type == "rag" else short


def group_by_rag_label(runs: Sequence[RunRecord]) -> Dict[str, List[RunRecord]]:
    """{RAG label: [runs]} — only arm-A runs (the RAG ablation is single-pass);
    a non-A run is ignored so a stray Track-A arm can't pollute the table."""
    out: Dict[str, List[RunRecord]] = {}
    for r in runs:
        if r.arm != "A":
            continue
        out.setdefault(rag_label(r), []).append(r)
    return out


def faithfulness_by_label(runs_by_label: Dict[str, List[RunRecord]]) -> Dict[str, Dict[str, Any]]:
    """Weighted-mean faithfulness per label from `summary.metrics.faithfulness`
    (rag labels only carry it; a `none` label reports None). Diagnostic only."""
    out: Dict[str, Dict[str, Any]] = {}
    for label, runs in runs_by_label.items():
        num = 0.0
        den = 0
        nulls = 0
        for r in runs:
            f = (r.summary.get("metrics", {}) or {}).get("faithfulness") or {}
            mean, n = f.get("mean"), int(f.get("n", 0) or 0)
            nulls += int(f.get("null", 0) or 0)
            if mean is not None and n > 0:
                num += mean * n
                den += n
        out[label] = {
            "faithfulness_mean": (num / den) if den else None,
            "n": den,
            "null": nulls,
        }
    return out


def grounding_filtered_by_label(runs_by_label: Dict[str, List[RunRecord]]) -> Dict[str, int]:
    """Total RAG-L3 passages filtered per label (§0.1 observability)."""
    return {
        label: sum(int(r.summary.get("grounding_filtered_total", 0) or 0) for r in runs)
        for label, runs in runs_by_label.items()
    }


@dataclass
class RagComparisonResult:
    label_a: str
    label_b: str
    bootstrap: Any
    mcnemar: Any
    per_seed: Dict[int, float]
    banner: Optional[str]


def build_rag_comparison(
    runs_by_label: Dict[str, List[RunRecord]],
    label_a: str,
    label_b: str,
    n_resamples: int = 10_000,
    seed: int = 0,
    pre_registered_n: int = PRE_REGISTERED_N_QUESTIONS,
    pre_registered_seeds: int = PRE_REGISTERED_N_SEEDS,
) -> RagComparisonResult:
    """Paired delta `pass_rate(label_a) - pass_rate(label_b)` with 95% cluster
    bootstrap CI + exact McNemar, pooling seeds — the SAME machinery Track A
    used (comparability). No V8 guard: crossing memory.type is the design."""
    runs_a = runs_by_label.get(label_a, [])
    runs_b = runs_by_label.get(label_b, [])
    if not runs_a:
        raise ValueError(f"no runs found for RAG label {label_a!r}")
    if not runs_b:
        raise ValueError(f"no runs found for RAG label {label_b!r}")

    cluster_table, seed_index = build_cluster_table({label_a: runs_a, label_b: runs_b})
    bootstrap = paired_cluster_bootstrap(cluster_table, label_a, label_b, n_resamples=n_resamples, seed=seed)

    pairs: List[Tuple[bool, bool]] = []
    for _qid, labels in cluster_table.items():
        if label_a in labels and label_b in labels:
            for pa, pb in zip(labels[label_a], labels[label_b]):
                pairs.append((pa, pb))
    mcnemar = exact_mcnemar(pairs, arm_a=label_a, arm_b=label_b)

    all_seeds = sorted({r.seed for r in (*runs_a, *runs_b) if r.seed is not None})
    seed_deltas = per_seed_deltas(cluster_table, label_a, label_b, all_seeds, seed_index)
    banner = banner_for(list(runs_a) + list(runs_b), pre_registered_n, pre_registered_seeds)

    return RagComparisonResult(label_a, label_b, bootstrap, mcnemar, seed_deltas, banner)


def build_rag_report(
    runs: Sequence[RunRecord],
    comparisons: Sequence[Tuple[str, str]] = DEFAULT_RAG_COMPARISONS,
    n_resamples: int = 10_000,
    seed: int = 0,
    pre_registered_n: int = PRE_REGISTERED_N_QUESTIONS,
    pre_registered_seeds: int = PRE_REGISTERED_N_SEEDS,
) -> Dict[str, Any]:
    """Full RAG ablation report dict. Correctness (Wilson per label + the
    pre-registered delta) is the headline; faithfulness + reference_match are
    separate diagnostic columns, never merged (ADR-019)."""
    runs_by_label = group_by_rag_label(runs)

    comparisons_out: Dict[str, RagComparisonResult] = {}
    comparison_errors: Dict[str, str] = {}
    for a, b in comparisons:
        label = f"{a} - {b}"
        try:
            comparisons_out[label] = build_rag_comparison(
                runs_by_label, a, b, n_resamples=n_resamples, seed=seed,
                pre_registered_n=pre_registered_n, pre_registered_seeds=pre_registered_seeds,
            )
        except ValueError as exc:
            comparison_errors[label] = str(exc)

    return {
        "labels_present": sorted(runs_by_label),
        "descriptive": arm_descriptive(runs_by_label),  # generic over the key
        "comparisons": comparisons_out,
        "comparison_errors": comparison_errors,
        "reference_match": reference_match_divergence(runs_by_label),
        "faithfulness": faithfulness_by_label(runs_by_label),
        "grounding_filtered": grounding_filtered_by_label(runs_by_label),
        "token_cost": token_cost_per_arm(runs_by_label),
        "banner": banner_for(list(runs), pre_registered_n, pre_registered_seeds),
    }
