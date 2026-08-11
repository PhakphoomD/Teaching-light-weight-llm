"""Re-judge a run's answers with a single consistent judge (data-integrity fix).

The 7B ablation (2026-07-16) exhausted Groq's daily token cap partway, so ~40% of
those judge calls fell back to the LOCAL llama3.1:8b judge — which scores
differently from Groq llama-3.1-8b-instant. That makes the 7B+RAG − 7B
comparison confounded by a mixed judge. This script re-scores the affected runs'
answers with a single Groq judge (deterministic, temp 0 → runs already fully
Groq-judged are unchanged), restoring one consistent evaluator across all arms.

Only the JUDGING is redone — student answers (generated locally) are untouched.
Re-scores every round, rewrites rounds.jsonl (score/normalized_score/passed) and
recomputes summary.jsonl (passed_count/pass_rate/null_rate/blind mean), and stamps
a `rejudged` provenance block (§0.1 — the fix is recorded, not hidden).

  HF_HUB_OFFLINE=1 python scripts/rag/rejudge.py --runs-dir runs_rag \
      --pattern 'trackB_p3_7b*' --judge groq:llama-3.1-8b-instant --pass-threshold 1.0 \
      --only-contaminated
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parents[2] / ".env")  # GROQ_API_KEY

import src.tlw.providers  # noqa: E402,F401
from src.providers.factory import build_client  # noqa: E402
from src.tlw.evaluation.judge import BlindJudge  # noqa: E402


def rejudge_run(run_dir: Path, judge: BlindJudge, gate_provider_model: str) -> dict:
    rounds_path = run_dir / "rounds.jsonl"
    summary_path = run_dir / "summary.jsonl"
    rows = [json.loads(l) for l in open(rounds_path, encoding="utf-8") if l.strip()]

    passed_flags, null_count, normalized = [], 0, []
    # rounds.jsonl is one row per (question, round); re-score each. For these
    # single-pass rag runs there is exactly one round per question, so the last
    # row per question is its final — but we re-score EVERY row for correctness.
    per_q_final = {}
    for r in rows:
        verdict = judge.score(r["question"], r.get("answer", ""), mode="blind")
        r["score"] = verdict["score"]
        r["normalized_score"] = verdict["normalized_score"]
        r["passed"] = bool(verdict["passed"])
        per_q_final[r["question_id"]] = r  # last row wins = final round

    with open(rounds_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    for r in per_q_final.values():
        passed_flags.append(bool(r["passed"]))
        if r["score"] is None:
            null_count += 1
        if r["normalized_score"] is not None:
            normalized.append(r["normalized_score"])

    summary = json.load(open(summary_path)) if summary_path.suffix == ".json" else json.loads(
        next(l for l in open(summary_path, encoding="utf-8") if l.strip())
    )
    nq = summary["num_questions"]
    passed = sum(passed_flags)
    summary["passed_count"] = passed
    summary["pass_rate"] = passed / nq if nq else 0.0
    summary["null_rate"] = null_count / nq if nq else 0.0
    summary["metrics"]["blind_score_mean_normalized"] = (
        sum(normalized) / len(normalized) if normalized else None
    )
    # the re-judge is pure Groq now -> the old fallback no longer applies
    summary["judge_fallback"] = {"count": 0, "primary_errors": 0, "retries": 0, "exhausted_no_fallback": 0}
    summary["rejudged"] = {
        "judge": gate_provider_model,
        "date": str(date.today()),
        "reason": "original run hit Groq TPD cap; ~40% judged by local fallback -> re-judged on fresh Groq for a single consistent judge",
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Re-judge runs with one consistent judge.")
    ap.add_argument("--runs-dir", default="runs_rag")
    ap.add_argument("--pattern", default="trackB_p3_7b*")
    ap.add_argument("--judge", default="groq:llama-3.1-8b-instant")
    ap.add_argument("--pass-threshold", type=float, default=1.0)
    ap.add_argument("--only-contaminated", action="store_true",
                    help="only re-judge runs whose summary.judge_fallback.count > 0")
    ap.add_argument("--only-nulls", action="store_true",
                    help="only re-judge runs that currently have >0 null-score rounds "
                    "(robust to a prior failed re-judge that cleared the fallback flag)")
    args = ap.parse_args(argv)

    provider, model = args.judge.split(":", 1)
    judge = BlindJudge(client=build_client(provider, model=model), pass_threshold=args.pass_threshold,
                       temperature=0.0, max_tokens=256)

    runs = sorted(Path(args.runs_dir).glob(args.pattern))
    done = 0
    for run_dir in runs:
        if not (run_dir / "summary.jsonl").is_file():
            continue
        s = json.loads(next(l for l in open(run_dir / "summary.jsonl", encoding="utf-8") if l.strip()))
        if args.only_contaminated and (s.get("judge_fallback", {}) or {}).get("count", 0) == 0:
            print(f"[rejudge] SKIP (clean) {run_dir.name}: pass={s['pass_rate']:.3f}")
            continue
        if args.only_nulls:
            nulls = sum(
                1 for l in open(run_dir / "rounds.jsonl", encoding="utf-8")
                if l.strip() and json.loads(l).get("score") is None
            )
            if nulls == 0:
                print(f"[rejudge] SKIP (no nulls) {run_dir.name}: pass={s['pass_rate']:.3f}")
                continue
        old = s["pass_rate"]
        ns = rejudge_run(run_dir, judge, args.judge)
        done += 1
        print(f"[rejudge] {run_dir.name}: pass {old:.3f} -> {ns['pass_rate']:.3f} (re-judged {ns['num_questions']} on {args.judge})")
    print(f"[rejudge] re-judged {done} run(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
