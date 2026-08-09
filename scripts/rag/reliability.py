"""Stratified RAG reliability analysis (no selection bias) — docs/EXPERIMENT_RESULTS.md §7.3.

Reads the full-125 x K-seed sweep (runs/rag-medquad-reliability/, both arms). Avoids the
regression-to-the-mean trap by a SEED SPLIT: classify each question's baseline
difficulty on the "classify" seeds, then measure baseline vs RAG reliability on
the DISJOINT "measure" seeds — so the RAG-lift-vs-difficulty curve is never
computed on the same seeds used to pick the difficulty stratum.

Reports, per baseline-difficulty stratum: per-attempt Δ, pass@k, reliable@k
(baseline vs RAG), each with a paired cluster bootstrap CI over questions.

  python scripts/rag/reliability.py --runs-dir runs_reliability --classify 1,2,3,4 --measure 5,6,7,8
"""

from __future__ import annotations

import argparse
import glob
import json
import random
from collections import defaultdict
from pathlib import Path


def load(pattern):
    d = defaultdict(dict)  # qid -> {seed: passed}
    for f in glob.glob(pattern):
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            d[r["question_id"]][int(r["seed"])] = bool(r["passed"])
    return d


def frac(d_q, seeds):
    vals = [d_q[s] for s in seeds if s in d_q]
    return (sum(vals) / len(vals)) if vals else None


def boot_ci(values, n=10000, seed=0):
    if not values:
        return (None, None)
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        s = [values[rng.randrange(len(values))] for _ in values]
        means.append(sum(s) / len(s))
    means.sort()
    return (means[int(0.025 * n)], means[int(0.975 * n)])


def load_any(runs_dir: str, patterns, label: str):
    """Load the first pattern that matches any run directory.

    ADR-034 renames run directories from config stems (`trackB_p3_3bRAG*`) to
    human labels (`with-rag__seed*`). Trying the new name first and falling back
    to the old one keeps this script correct on both sides of the migration.
    """
    for pat in patterns:
        got = load(f"{runs_dir}/{pat}/rounds.jsonl")
        if got:
            return got
    raise SystemExit(
        f"no {label} runs found under {runs_dir!r}; tried: {', '.join(patterns)}"
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", default="runs_reliability")
    ap.add_argument("--classify", default="1,2,3,4")
    ap.add_argument("--measure", default="5,6,7,8")
    args = ap.parse_args(argv)
    cls = [int(x) for x in args.classify.split(",")]
    mea = [int(x) for x in args.measure.split(",")]

    # Run discovery is LABEL-driven, with a fallback to the pre-ADR-034 config-stem
    # names so this works before and after the restructure. Fails loud rather than
    # printing an empty table on no match (it used to exit 0 with `questions: 0`).
    B = load_any(args.runs_dir, ["no-rag__seed*", "trackB_p3_3b_diabetes__seed*"], "baseline")
    R = load_any(args.runs_dir, ["with-rag__seed*", "trackB_p3_3bRAG*"], "RAG")
    qids = [q for q in B if q in R]
    if not qids:
        raise SystemExit(
            f"no paired questions found under {args.runs_dir!r} — the run directories "
            f"did not match any known naming scheme. Check --runs-dir."
        )
    print(f"questions: {len(qids)} | classify seeds {cls} | measure seeds {mea}\n")

    # difficulty stratum from CLASSIFY seeds only
    strata = {"gap (base 0/… on classify)": [], "hard (0-50%)": [], "mid (50-99%)": [], "easy (100%)": []}
    for q in qids:
        d = frac(B[q], cls)
        if d is None:
            continue
        if d == 0:
            strata["gap (base 0/… on classify)"].append(q)
        elif d < 0.5:
            strata["hard (0-50%)"].append(q)
        elif d < 1.0:
            strata["mid (50-99%)"].append(q)
        else:
            strata["easy (100%)"].append(q)

    kM = len(mea)
    print(f"{'stratum':32s} {'n':>3s} {'base_rel':>9s} {'rag_rel':>8s} {'Δrel':>7s}  {'Δrel 95% CI':>18s}  {'base r@k':>8s} {'rag r@k':>7s}")
    for name, qs in strata.items():
        if not qs:
            print(f"{name:32s}   0  (empty)")
            continue
        b_rel = [frac(B[q], mea) for q in qs]
        r_rel = [frac(R[q], mea) for q in qs]
        deltas = [r - b for b, r in zip(b_rel, r_rel)]
        lo, hi = boot_ci(deltas)
        b_reliable = sum(1 for q in qs if all(B[q].get(s) for s in mea)) / len(qs)
        r_reliable = sum(1 for q in qs if all(R[q].get(s) for s in mea)) / len(qs)
        print(f"{name:32s} {len(qs):>3d} {sum(b_rel)/len(qs):>9.3f} {sum(r_rel)/len(qs):>8.3f} "
              f"{sum(deltas)/len(deltas):>+7.3f}  [{lo:+.3f}, {hi:+.3f}]  {b_reliable:>8.2f} {r_reliable:>7.2f}")

    # overall (all questions, measure seeds) — the diluted aggregate for context
    b_all = [frac(B[q], mea) for q in qids]
    r_all = [frac(R[q], mea) for q in qids]
    d_all = [r - b for b, r in zip(b_all, r_all)]
    lo, hi = boot_ci(d_all)
    print(f"\n{'ALL 125 (diluted aggregate)':32s} {len(qids):>3d} {sum(b_all)/len(qids):>9.3f} "
          f"{sum(r_all)/len(qids):>8.3f} {sum(d_all)/len(d_all):>+7.3f}  [{lo:+.3f}, {hi:+.3f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
