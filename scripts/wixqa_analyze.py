"""WixQA T3.9 (P3-E): 3-seed analysis — +RAG delta with CI, McNemar, gold-split.

Pools seeds {13,42,123} for both arms and reuses the PRE-REGISTERED statistics
machinery (src/tlw/analysis/stats.py: paired_cluster_bootstrap + exact_mcnemar +
wilson_interval) that produced the Track-A / RAG_RESULTS headline numbers.

Seed 42 = the ADR-030 published draw (runs/rag-wixqa/{baseline_norag,rag_top3}.jsonl,
already judged — exact continuity with the +13pt result). Seeds 13 & 123 =
scripts/wixqa_run3seed.py + wixqa_judge.py, identical prompts/judge/retrieval.

Headline metric = PASS iff score >= 3 (ADR-030 "correct"). Questions are paired
by idx (0..199, same order in expertwritten.jsonl). A (question,seed) replicate is
used only when BOTH arms have a non-null score (clean pairing); nulls are reported.

  python scripts/wixqa_analyze.py
"""
import json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.tlw.analysis.stats import (
    paired_cluster_bootstrap, exact_mcnemar, wilson_interval, per_seed_deltas,
)

RUNS = ROOT / "runs/rag-wixqa"
PASS = 3  # ADR-030 headline: score >= 3 = "correct"
SEEDS = [13, 42, 123]

# arm -> the ladder step that holds it (ADR-034 layout). Each step directory holds
# one file per seed, so the seed is the filename and the condition is the folder.
STEPS = {"baseline": "1-no-rag", "rag": "2-rag-basic"}


def load(arm, seed):
    """idx -> record, for one arm+seed run file."""
    p = RUNS / STEPS[arm] / f"seed{seed}.jsonl"
    if not p.is_file():
        return None
    return {d["idx"]: d for d in (json.loads(l) for l in p.open(encoding="utf-8") if l.strip())}


def passed(score):
    return None if score is None else bool(score >= PASS)


def main():
    # --- load everything ------------------------------------------------------
    data = {arm: {s: load(arm, s) for s in SEEDS} for arm in STEPS}
    missing = [(arm, s) for arm in STEPS for s in SEEDS if data[arm][s] is None]
    if missing:
        print("MISSING run files (generate/judge first):", missing)
        return 1
    nulls = {arm: {s: sum(1 for d in data[arm][s].values() if d.get("score") is None) for s in SEEDS}
             for arm in STEPS}

    # --- gold-retrieved mask (seed-independent) from the retrieval log ---------
    rl = {d["idx"]: d for d in (json.loads(l) for l in (RUNS / "retrieval_log.jsonl").open(encoding="utf-8"))}
    hit = sum(1 for d in rl.values() if d["gold_retrieved"])
    n_rl = len(rl)

    # --- cluster table + seed index (rag vs baseline) -------------------------
    cluster = defaultdict(lambda: {"rag": [], "baseline": []})
    sindex = defaultdict(lambda: {"rag": [], "baseline": []})
    mcnemar_pairs = []
    for s in SEEDS:
        for idx in range(200):
            rb = data["baseline"][s].get(idx)
            rr = data["rag"][s].get(idx)
            if rb is None or rr is None:
                continue
            pb, pr = passed(rb.get("score")), passed(rr.get("score"))
            if pb is None or pr is None:
                continue
            cluster[idx]["baseline"].append(pb); sindex[idx]["baseline"].append(s)
            cluster[idx]["rag"].append(pr);      sindex[idx]["rag"].append(s)
            mcnemar_pairs.append((pr, pb))

    # --- per-seed & pooled pass rates ----------------------------------------
    def rate(arm, seed):
        v = [passed(d.get("score")) for d in data[arm][seed].values()]
        v = [x for x in v if x is not None]
        return sum(v), len(v)

    print("=" * 74)
    print("WixQA T3.9 — 3-seed RAG re-run (PASS = score >= 3)")
    print("=" * 74)
    print(f"retrieval hit-rate (gold KB article in top-3): {hit}/{n_rl} = {hit/n_rl:.3f}  [seed-independent]\n")

    print(f"{'arm':<9} " + " ".join(f"seed{sd:<6}" for sd in SEEDS) + "  pooled")
    pooled = {}
    for arm in ("baseline", "rag"):
        cells, pk, pn = [], 0, 0
        for sd in SEEDS:
            k, n = rate(arm, sd); pk += k; pn += n
            cells.append(f"{k/n:.3f}" if n else "  -  ")
        pooled[arm] = (pk, pn)
        print(f"{arm:<9} " + " ".join(f"{c:<10}" for c in cells) + f"  {pk/pn:.3f} ({pk}/{pn})")
    for arm in ("baseline", "rag"):
        k, n = pooled[arm]; w = wilson_interval(k, n)
        print(f"   {arm:<7} pooled Wilson 95%: {w.point:.3f} [{w.low:.3f}, {w.high:.3f}]  n={n}")
    print(f"   judge nulls per (arm,seed): "
          f"{ {arm: nulls[arm] for arm in STEPS} }")

    # --- HEADLINE: +RAG delta with paired cluster-bootstrap CI ----------------
    boot = paired_cluster_bootstrap(cluster, arm_a="rag", arm_b="baseline",
                                    n_resamples=10_000, seed=0)
    mc = exact_mcnemar(mcnemar_pairs, arm_a="rag", arm_b="baseline")
    print("\n" + "-" * 74)
    print("HEADLINE: 3B+RAG − 3B baseline (pooled over seeds; paired by question)")
    print("-" * 74)
    print("  " + boot.summary_line())
    print(f"  McNemar exact: b(rag✓/base✗)={mc.b}  c(rag✗/base✓)={mc.c}  "
          f"p={mc.p_value:.4g}  (n_pairs={mc.n_pairs})")
    psd = per_seed_deltas(cluster, "rag", "baseline", SEEDS, sindex)
    print("  per-seed delta (rag−baseline): " + ", ".join(f"seed{sd}={psd.get(sd, float('nan')):+.3f}" for sd in SEEDS))

    # --- gold-retrieved vs gold-missed split (pooled over seeds) ---------------
    print("\n" + "-" * 74)
    print("GOLD SPLIT (pooled over seeds): does the +27 / −4 pattern hold?")
    print("-" * 74)
    for label, want in (("gold-RETRIEVED", True), ("gold-MISSED", False)):
        idxs = [i for i in range(200) if i in rl and rl[i]["gold_retrieved"] == want]
        bk = bn = rk = rn = 0
        for s in SEEDS:
            for i in idxs:
                rb, rr = data["baseline"][s].get(i), data["rag"][s].get(i)
                pb, pr = passed(rb.get("score") if rb else None), passed(rr.get("score") if rr else None)
                if pb is not None:
                    bn += 1; bk += pb
                if pr is not None:
                    rn += 1; rk += pr
        base = bk / bn if bn else float("nan")
        rg = rk / rn if rn else float("nan")
        print(f"  {label:<15} n_q={len(idxs):>3}  baseline={base:.3f}  +RAG={rg:.3f}  "
              f"delta={rg-base:+.3f}   ({bn} base / {rn} rag replicates)")

    # secondary: pass@>=4 pooled (ADR-030 notes this is ~0 for a 3B + 1 article)
    def rate4(arm):
        k = n = 0
        for s in SEEDS:
            for d in data[arm][s].values():
                sc = d.get("score")
                if sc is not None:
                    n += 1; k += (sc >= 4)
        return k, n
    print("\nsecondary pass@>=4 (pooled): " + ", ".join(
        f"{arm}={ (lambda kn: f'{kn[0]/kn[1]:.3f}')(rate4(arm)) }" for arm in ("baseline", "rag")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
