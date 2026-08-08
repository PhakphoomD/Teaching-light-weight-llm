"""
Judge comparison experiment: Groq (cloud) vs local Qwen (Ollama) for D4 quality.

Honest method — no human labels needed. Build candidates whose quality ordering we KNOW:
  GOOD      = the real cleaned answer
  WRONG     = a fluent answer taken from a DIFFERENT question (should score low)
  TRUNCATED = first ~12 words of the real answer (incomplete -> should score mid/low)

A better judge (a) scores GOOD high, WRONG/TRUNCATED low = larger *discrimination*,
and (b) is reasonably fast. We report both, plus inter-judge agreement.

Run (from repo root, tlw env; Ollama daemon must be up):
  & "C:\\Users\\ham25\\.conda\\envs\\tlw\\python.exe" scripts/calibration/compare_judges.py --n 8
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from statistics import fmean

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.dataset.judge import build_judge  # noqa: E402

CLEAN = Path("data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_clean.jsonl")


def load_sample(n: int, seed: int = 42):
    recs = [json.loads(l) for l in CLEAN.read_text(encoding="utf-8").splitlines() if l.strip()]
    rng = random.Random(seed)
    picked = rng.sample(recs, min(n, len(recs)))
    cands = []
    for i, r in enumerate(picked):
        other = picked[(i + 1) % len(picked)]  # a different question's answer
        words = r["answer"].split()
        cands.append({
            "q": r["question"],
            "good": r["answer"],
            "wrong": other["answer"],
            "truncated": " ".join(words[:12]),
        })
    return cands


def run_judge(judge, cands):
    t0 = time.time()
    rows = []
    for c in cands:
        rows.append({
            "good": judge.score(c["q"], c["good"]),
            "wrong": judge.score(c["q"], c["wrong"]),
            "truncated": judge.score(c["q"], c["truncated"]),
        })
    return rows, time.time() - t0


def _mean(rows, key):
    vals = [r[key] for r in rows if r[key] is not None]
    return fmean(vals) if vals else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    cands = load_sample(args.n, args.seed)
    print(f"Probe: {len(cands)} questions x 3 candidates (good/wrong/truncated)\n")

    results = {}
    for kind in ("groq", "ollama"):
        judge = build_judge(kind)
        rows, secs = run_judge(judge, cands)
        g, w, t = _mean(rows, "good"), _mean(rows, "wrong"), _mean(rows, "truncated")
        results[judge.label] = {"rows": rows, "good": g, "wrong": w, "trunc": t, "secs": secs}
        print(f"=== {judge.label} ===")
        print(f"  mean GOOD={g:.2f}  WRONG={w:.2f}  TRUNCATED={t:.2f}")
        print(f"  discrimination  GOOD-WRONG={g-w:+.2f}   GOOD-TRUNC={g-t:+.2f}")
        print(f"  time: {secs:.1f}s  ({secs/(len(cands)*3):.2f}s/call)\n")

    labels = list(results)
    if len(labels) == 2:
        a, b = results[labels[0]], results[labels[1]]
        pairs = [(ra[k], rb[k]) for ra, rb in zip(a["rows"], b["rows"])
                 for k in ("good", "wrong", "truncated") if ra[k] is not None and rb[k] is not None]
        if pairs:
            diffs = [abs(x - y) for x, y in pairs]
            print(f"inter-judge mean |score diff|: {fmean(diffs):.2f}  (lower = more agreement)")
        winner = max(labels, key=lambda L: (results[L]["good"] - results[L]["wrong"]))
        print(f"\nBigger correctness-discrimination (GOOD-WRONG): {winner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
