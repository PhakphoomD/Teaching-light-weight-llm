"""CLI entrypoint (T2.8 build instruction 4):

    & "C:\\Users\\ham25\\.conda\\envs\\tlw\\python.exe" -m src.tlw.analysis \\
        --runs-dir runs --comparison C-B [--memory-type none] \\
        [--resamples 10000] [--seed 0]

Prints an HONEST table: correctness and reference_match on separate lines,
never merged (ADR-019); any comparison whose sample falls short of the
pre-registered 125 questions / 3 seeds gets the loud NOT-pre-registered
banner (report.py) so pilot/dry-run data can't be silently promoted into a
result (T2.8 build instruction 4 / §0.1).
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence

from .loaders import ConflationError, RunRecord, discover_runs
from .report import (
    PRE_REGISTERED_N_QUESTIONS,
    PRE_REGISTERED_N_SEEDS,
    ComparisonResult,
    build_report,
)


def _parse_comparison(text: str) -> tuple:
    parts = text.split("-")
    if len(parts) != 2 or not all(parts):
        raise argparse.ArgumentTypeError(f"--comparison must be '<ARM_A>-<ARM_B>', got {text!r}")
    return (parts[0].strip(), parts[1].strip())


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.tlw.analysis",
        description="Track-A analysis (T2.8 SCRIPT half) -- honest pass-rate deltas with CIs.",
    )
    parser.add_argument("--runs-dir", default="runs", help="directory containing runs/<run_id>/ (default: runs)")
    parser.add_argument(
        "--comparison",
        action="append",
        type=_parse_comparison,
        dest="comparisons",
        help="ARM_A-ARM_B, e.g. C-B (headline). Repeatable. Default: C-B, B-A, D-C.",
    )
    parser.add_argument(
        "--memory-type",
        default="none",
        choices=("none", "faiss", "rag"),
        help="which memory.type slice to compare (V8) -- headline=none, C'/D' ablation=faiss (default: none)",
    )
    parser.add_argument("--resamples", type=int, default=10_000, help="bootstrap resamples (default: 10000)")
    parser.add_argument("--seed", type=int, default=0, help="bootstrap RNG seed (default: 0, deterministic)")
    parser.add_argument(
        "--pre-registered-n",
        type=int,
        default=PRE_REGISTERED_N_QUESTIONS,
        help=f"pre-registered held-out size for the honesty banner (default: {PRE_REGISTERED_N_QUESTIONS})",
    )
    parser.add_argument(
        "--pre-registered-seeds",
        type=int,
        default=PRE_REGISTERED_N_SEEDS,
        help=f"pre-registered seed count for the honesty banner (default: {PRE_REGISTERED_N_SEEDS})",
    )
    return parser


def _fmt_pct(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def render_report(report: dict) -> str:
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append(f"Track-A analysis  --  memory.type = {report['memory_type']}")
    lines.append(f"arms present: {', '.join(report['arms_present']) or '(none)'}")
    lines.append("-" * 78)

    lines.append("Descriptive per-arm pass-rate (Wilson 95% CI):")
    for arm, wi in sorted(report["descriptive"].items()):
        lines.append(f"  arm {arm}: {wi.point:.3f}  [{wi.low:.3f}, {wi.high:.3f}]  (n={wi.n}, k={wi.k})")

    lines.append("-" * 78)
    lines.append("Headline deltas (paired cluster bootstrap, 95% CI) + McNemar p:")
    comp: ComparisonResult
    for label, comp in sorted(report["comparisons"].items()):
        bs = comp.bootstrap
        mc = comp.mcnemar
        label_note = " [LEAKAGE CEILING -- not a claimed result]" if "D" in (comp.arm_a, comp.arm_b) else ""
        lines.append(f"  {label}{label_note}: {bs.summary_line()}")
        lines.append(f"      McNemar: b={mc.b} c={mc.c} p={mc.p_value:.4f}")
        if comp.per_seed:
            spread = ", ".join(f"seed {s}: {d:+.3f}" for s, d in sorted(comp.per_seed.items()))
            lines.append(f"      per-seed deltas: {spread}")
        if comp.banner:
            lines.append(f"      {comp.banner}")
    for label, err in sorted(report.get("comparison_errors", {}).items()):
        lines.append(f"  {label}: SKIPPED -- {err}")

    lines.append("-" * 78)
    lines.append("correctness (HEADLINE) vs reference_match (DIAGNOSTIC ONLY, never merged, ADR-019):")
    for arm, row in sorted(report["reference_match"].items()):
        lines.append(
            f"  arm {arm}: correctness_pass_rate={_fmt_pct(row['correctness_pass_rate'])}   "
            f"reference_match: semantic_sim={_fmt_pct(row['reference_match_semantic_sim_mean'])}  "
            f"rouge_l={_fmt_pct(row['reference_match_rouge_l_mean'])}"
        )

    lines.append("-" * 78)
    lines.append("Rounds-to-pass distribution:")
    for arm, hist in sorted(report["rounds_to_pass"].items()):
        hist_str = ", ".join(f"{k}: {v}" for k, v in sorted(hist.items(), key=lambda kv: (kv[0] == "never", kv[0])))
        lines.append(f"  arm {arm}: {hist_str or '(no data)'}")

    lines.append("-" * 78)
    lines.append("Token cost per arm (student+teacher+judge):")
    for arm, tc in sorted(report["token_cost"].items()):
        lines.append(
            f"  arm {arm}: total={tc['total']}  student={tc['student']}  teacher={tc['teacher']}  judge={tc['judge']}"
        )

    lines.append("-" * 78)
    lines.append("Memory-note usage per arm:")
    for arm, mu in sorted(report["memory_usage"].items()):
        lines.append(
            f"  arm {arm}: memory_hit_rate={mu['memory_hit_rate']:.3f} "
            f"({mu['rounds_using_memory']}/{mu['total_rounds']} rounds)  "
            f"episodes_stored={mu['total_episodes_stored']}  rejects={mu['total_rejects']}"
        )

    if report.get("banner"):
        lines.append("=" * 78)
        lines.append(report["banner"])

    lines.append("=" * 78)
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    comparisons = args.comparisons or [("C", "B"), ("B", "A"), ("D", "C")]

    runs: List[RunRecord] = discover_runs(args.runs_dir)
    if not runs:
        print(f"No runs found under {args.runs_dir!r} (looked for */summary.jsonl).", file=sys.stderr)
        return 1

    try:
        report = build_report(
            runs,
            comparisons=comparisons,
            memory_type=args.memory_type,
            n_resamples=args.resamples,
            seed=args.seed,
            pre_registered_n=args.pre_registered_n,
            pre_registered_seeds=args.pre_registered_seeds,
        )
    except ConflationError as exc:
        print(f"REFUSED (V8 no-conflation rule): {exc}", file=sys.stderr)
        return 2

    print(render_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
