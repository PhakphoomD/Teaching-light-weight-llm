"""WixQA T3.14 Stage-1: paired comparison of two grounding variants.

Compares a treatment run (e.g. chunk2400) against the T3.11 control (head900) on
the SAME questions and seeds, paired by idx. Reports the judge bars AND a
continuous, judge-free completeness metric.

Why the continuous metric (finding F3): the judge's pass@>=4 ("all key facts from
the reference present") is near-unreachable here — the full gold article only
covers ~72% of the reference's content words, so ~28% is unattainable even with
the whole article in context. With a floor of 0.010, pass@>=4 has very little
statistical power. `reference_coverage` = |content(reference) & content(answer)| /
|content(reference)| is continuous, free to compute, needs no judge, and measures
exactly what "complete" means here.

  python scripts/wixqa_grounding_compare.py \
      --control 'runs/rag-wixqa/rag_bge_chunk__seed42.jsonl' \
      --treat   'runs/rag-wixqa/rag_bge_chunk_chunk2400_pilot__seed42.jsonl'
"""
import argparse, glob, json, math, re, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.tlw.analysis.stats import paired_cluster_bootstrap, exact_mcnemar, wilson_interval

STOP = set(
    "a an the is are was were be been being of to in for on with and or as at by from this that these "
    "those it its you your can will may if not no do does did have has had how what when where which "
    "who why about into over under more most other some such only own same so than too very s t just".split()
)


def content(t):
    return set(w for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in STOP and len(w) > 2)


def load(pattern):
    """{(idx, seed): record} across all files matching the pattern."""
    out = {}
    for p in glob.glob(pattern):
        for l in open(p, encoding="utf-8"):
            if l.strip():
                d = json.loads(l)
                out[(d["idx"], d["seed"])] = d
    return out


def cov(d):
    ref = content(d["reference"])
    return len(ref & content(d.get("answer") or "")) / len(ref) if ref else None


def boot_mean_diff(pairs, n=10000, seed=0):
    """Paired bootstrap CI for a mean difference (continuous metric)."""
    v = np.array([t - c for t, c in pairs], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(v), size=(n, len(v)))
    d = v[idx].mean(axis=1)
    return float(v.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", required=True)
    ap.add_argument("--treat", required=True)
    ap.add_argument("--label-control", default="control")
    ap.add_argument("--label-treat", default="treatment")
    ap.add_argument("--gold-only", action="store_true", help="restrict to gold-retrieved questions")
    a = ap.parse_args()

    C, T = load(a.control), load(a.treat)
    keys = sorted(set(C) & set(T))
    if a.gold_only:
        keys = [k for k in keys if C[k].get("gold_retrieved")]
    judged = [k for k in keys if C[k].get("score") is not None and T[k].get("score") is not None]

    print("=" * 76)
    print(f"Stage-1 grounding comparison: {a.label_treat} vs {a.label_control}")
    print(f"paired on {len(keys)} (question,seed) cells; {len(judged)} judged in BOTH"
          + ("  [gold-retrieved only]" if a.gold_only else ""))
    print("=" * 76)

    # prompt size (context cost)
    for lbl, D in ((a.label_control, C), (a.label_treat, T)):
        pc = [d.get("prompt_chars") for k, d in D.items() if k in keys and d.get("prompt_chars")]
        if pc:
            print(f"  {lbl:<12} prompt {np.mean(pc):.0f} chars avg")

    # continuous completeness (judge-free -> uses ALL paired cells, not just judged)
    pairs_cov = [(cov(T[k]), cov(C[k])) for k in keys if cov(T[k]) is not None and cov(C[k]) is not None]
    if pairs_cov:
        m, lo, hi = boot_mean_diff(pairs_cov)
        mc = np.mean([c for _, c in pairs_cov]); mt = np.mean([t for t, _ in pairs_cov])
        print(f"\n  reference-coverage (continuous, judge-free, n={len(pairs_cov)}):")
        print(f"    {a.label_control}={mc:.3f}  {a.label_treat}={mt:.3f}   "
              f"delta={m:+.3f} [{lo:+.3f}, {hi:+.3f}]"
              + ("  <-- CI excludes 0" if lo > 0 or hi < 0 else "  (CI spans 0)"))
    # answer length (is it just writing more?)
    wl_c = np.mean([len((C[k].get("answer") or "").split()) for k in keys])
    wl_t = np.mean([len((T[k].get("answer") or "").split()) for k in keys])
    print(f"    answer length: {wl_c:.0f} -> {wl_t:.0f} words")

    # EXTRACTION RATIO = how much of what the CONTEXT offers the model actually
    # puts in the answer. Separates the two candidate causes of the ~0.41 ceiling:
    # a high ratio means the context was the binding constraint (the model used
    # nearly all it was given); a low ratio means the MODEL is now binding.
    ctx_cov = {"head900": 0.412, "chunk900": 0.482, "head2400": 0.612, "chunk2400": 0.655}
    gc = ctx_cov.get(next(iter([C[k].get("grounding") or "head900" for k in keys]), "head900"))
    gt_ = ctx_cov.get(next(iter([T[k].get("grounding") or "head900" for k in keys]), "head900"))
    if pairs_cov and gc and gt_:
        print(f"    extraction ratio (answer-cov / context-cov): "
              f"{a.label_control} {mc/gc:.0%}  ->  {a.label_treat} {mt/gt_:.0%}")

    if not judged:
        print("\n  (no judged cells yet — run scripts/wixqa_judge.py to score, then re-run)")
        return 0

    # judge bars
    for bar in (3, 4):
        ct = {"A": [], "B": []}
        cluster, mpairs = {}, []
        for k in judged:
            pt, pc_ = T[k]["score"] >= bar, C[k]["score"] >= bar
            cluster.setdefault(k[0], {"A": [], "B": []})
            cluster[k[0]]["A"].append(pt); cluster[k[0]]["B"].append(pc_)
            mpairs.append((pt, pc_)); ct["A"].append(pt); ct["B"].append(pc_)
        kt, kc, n = sum(ct["A"]), sum(ct["B"]), len(judged)
        wt, wc = wilson_interval(kt, n), wilson_interval(kc, n)
        b = paired_cluster_bootstrap(cluster, "A", "B", n_resamples=10000, seed=0)
        mn = exact_mcnemar(mpairs, "A", "B")
        print(f"\n  pass@>={bar}:  {a.label_control}={kc/n:.3f} [{wc.low:.3f},{wc.high:.3f}]   "
              f"{a.label_treat}={kt/n:.3f} [{wt.low:.3f},{wt.high:.3f}]")
        print(f"    delta={b.point_estimate:+.3f} [{b.ci_low:+.3f}, {b.ci_high:+.3f}]  "
              f"McNemar p={mn.p_value:.3g} (fixed {mn.b} / broke {mn.c})")

    ms_c = np.mean([C[k]["score"] for k in judged]); ms_t = np.mean([T[k]["score"] for k in judged])
    print(f"\n  mean judge score: {ms_c:.2f} -> {ms_t:.2f}")
    cat_c = sum(1 for k in judged if C[k]["score"] <= 1) / len(judged)
    cat_t = sum(1 for k in judged if T[k]["score"] <= 1) / len(judged)
    print(f"  catastrophe rate (score<=1): {cat_c:.3f} -> {cat_t:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
