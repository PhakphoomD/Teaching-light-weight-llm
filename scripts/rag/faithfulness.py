"""Offline RAG faithfulness diagnostic pass (T3.4/T3.5).

The full 3B+RAG run is executed with `--no-faithfulness` so the CORRECTNESS
judge (Groq) stays within its daily token cap and consistent with the reused
Track-A 3B baseline. Faithfulness is a DIAGNOSTIC (never the headline, ADR-019),
so it is computed here afterwards, off the critical path, with a LOCAL judge
(no Groq cap, no contention with the student — the student is not running now).

For every `rag` run under --runs-dir it: reads rounds.jsonl, scores each grounded
round (has `grounding_context`) with FaithfulnessJudge(answer, passages) — which
sees NO gold answer (§0.2) — writes `faithfulness` back into each round, and
rewrites `summary.metrics.faithfulness` = {mean, n, null, computed: "offline"}.
Idempotent: re-running recomputes from scratch.

Run (tlw python, HF offline):
  HF_HUB_OFFLINE=1 python scripts/rag/faithfulness.py --runs-dir runs \
      --judge local:llama3.1:8b
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# make `src` importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.providers.factory import build_client  # noqa: E402
import src.tlw.providers  # noqa: E402,F401  (registers "local" -> Ollama)
from src.tlw.evaluation.faithfulness import FaithfulnessJudge  # noqa: E402


def _iter_rag_runs(runs_dir: Path):
    for child in sorted(runs_dir.glob("*")):
        summ = child / "summary.jsonl"
        if not summ.is_file():
            continue
        with open(summ, encoding="utf-8") as f:
            line = next((l for l in f if l.strip()), None)
        if not line:
            continue
        s = json.loads(line)
        if s.get("memory_type") == "rag":
            yield child, s


def process_run(run_dir: Path, summary: dict, judge: FaithfulnessJudge) -> dict:
    rounds_path = run_dir / "rounds.jsonl"
    rows = [json.loads(l) for l in open(rounds_path, encoding="utf-8") if l.strip()]
    values, nulls = [], 0
    for r in rows:
        ctx = r.get("grounding_context")
        if not ctx:
            continue
        res = judge.score(r.get("answer", ""), ctx)
        r["faithfulness"] = res.get("faithfulness")
        if res.get("faithfulness") is None:
            nulls += 1
        else:
            values.append(res["faithfulness"])
    # rewrite rounds with faithfulness filled in
    with open(rounds_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary.setdefault("metrics", {})["faithfulness"] = {
        "mean": (sum(values) / len(values)) if values else None,
        "n": len(values),
        "null": nulls,
        "computed": "offline",
    }
    with open(run_dir / "summary.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary["metrics"]["faithfulness"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Offline RAG faithfulness diagnostic (T3.4/T3.5).")
    ap.add_argument("--runs-dir", default="runs")
    ap.add_argument("--judge", default="local:llama3.1:8b", help="provider:model (default local:llama3.1:8b)")
    args = ap.parse_args(argv)

    provider, model = args.judge.split(":", 1)
    judge = FaithfulnessJudge(client=build_client(provider, model=model))

    runs_dir = Path(args.runs_dir)
    found = 0
    for run_dir, summary in _iter_rag_runs(runs_dir):
        found += 1
        fa = process_run(run_dir, summary, judge)
        print(f"[faithfulness] {run_dir.name}: mean={fa['mean']} n={fa['n']} null={fa['null']}")
    if not found:
        print(f"no rag runs found under {runs_dir}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
