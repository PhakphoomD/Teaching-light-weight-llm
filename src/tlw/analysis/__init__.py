"""the teaching-loop study analysis block (SCRIPT half — qa-engineer, per ADR-019/teaching-loop-protocol.md §4).

This package computes the **pre-registered** headline statistic — the loop
effect `pass_rate(C) - pass_rate(B)`, with a 95% paired cluster-bootstrap CI
over the held-out questions, seeds pooled, plus a McNemar p-value and
descriptive Wilson intervals per arm (teaching-loop-protocol.md §4.2/§4.3) — from real
`runs/<run_id>/{summary.jsonl,rounds.jsonl,config_used.json}` artifacts
written by `src/tlw/runner.py`.

It is a REUSABLE, TESTED block, not a throwaway notebook (step 1). It
does NOT write `docs/EXPERIMENT_RESULTS.md §7.1` — that is the report's job,
out of scope here because the full the teaching-loop study run has not happened yet (§0.1:
no results doc before real data). Only synthetic fixtures and the n=5
dry-run artifacts under `runs/trackA_p2_arm{A,C}_diabetes__seed42__*` back
these tests; a full pilot/headline run must re-validate the real numbers.

Modules:
  loaders  -- discover run dirs, parse summary/rounds, group by
              (arm, seed, preset, memory.type); V8 no-conflation guard.
  stats    -- Wilson interval (per-arm descriptive), paired cluster
              bootstrap (arm-delta effect + CI), exact McNemar (paired
              significance). Deterministic given a seed.
  report   -- secondary views (reference_match divergence, rounds-to-pass,
              token cost, memory-note usage) + the NOT-pre-registered
              banner logic + table assembly. correctness and
              reference_match are NEVER merged (ADR-019).
  cli      -- `python -m src.tlw.analysis --runs-dir runs --comparison C-B`
"""

from .loaders import (
    ConflationError,
    RunRecord,
    assert_single_memory_type,
    build_cluster_table,
    discover_runs,
    final_passes_by_question,
    group_runs,
    load_rounds,
    select_arm_runs,
)
from .report import ComparisonResult, banner_for, build_comparison, build_report
from .stats import (
    BootstrapResult,
    McNemarResult,
    WilsonInterval,
    exact_mcnemar,
    paired_cluster_bootstrap,
    wilson_interval,
)

__all__ = [
    "ConflationError",
    "RunRecord",
    "assert_single_memory_type",
    "build_cluster_table",
    "discover_runs",
    "final_passes_by_question",
    "group_runs",
    "load_rounds",
    "select_arm_runs",
    "ComparisonResult",
    "banner_for",
    "build_comparison",
    "build_report",
    "BootstrapResult",
    "McNemarResult",
    "WilsonInterval",
    "exact_mcnemar",
    "paired_cluster_bootstrap",
    "wilson_interval",
]
