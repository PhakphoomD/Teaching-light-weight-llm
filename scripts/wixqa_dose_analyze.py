"""WixQA T3.11 (P3-E): the dose-response proof — pass-rate vs retrieval hit-rate.

Plots aggregate pass@>=3 against measured hit-rate@3 across retriever variants,
against the 0.400 gold-retrieved anchor. If pass-rate tracks hit-rate along the
predicted mixture line, ADR-030's law ("retrieval is the bottleneck") is
DEMONSTRATED, not asserted. Reuses the pre-registered src/tlw/analysis stats.

Variants (only the retriever changes between them — student/judge/PASS>=3/top-k
all fixed):
  no-RAG        hit~0      (T3.9 baseline_norag + baseline__seed{13,123})
  minilm_whole  hit 0.550  (T3.9 rag_top3 + rag__seed{13,123})            <- ADR-030 retriever
  minilm_chunk  hit 0.645  (T3.11 rag_minilm_chunk__seed{13,42,123})       [optional dose point]
  bge_chunk     hit 0.665  (T3.11 rag_bge_chunk__seed{13,42,123})          <- T3.10 winner

Skips variants whose run files are missing / not yet judged (reports what's ready).

  python scripts/wixqa_dose_analyze.py
"""
import json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.tlw.analysis.stats import paired_cluster_bootstrap, exact_mcnemar, wilson_interval

RUNS = ROOT / "runs/rag-wixqa"
PASS = 3
SEEDS = [13, 42, 123]

# The ladder, in the order the story is told (ADR-034 layout): each entry is a
# directory holding one file per seed. `step` is the directory; the retrieval log
# lives beside it. A missing step is reported, never silently skipped — a
# half-present ladder used to shrink n without saying so.
VARIANTS = [
    {"name": "no-RAG",       "step": "1-no-rag",              "hit_log": None},
    {"name": "minilm_whole", "step": "2-rag-basic",           "hit_log": "retrieval_log.jsonl"},
    {"name": "bge_chunk",    "step": "3-rag-better-retriever", "hit_log": "retrieval_log_bge_chunk.jsonl"},
    {"name": "bge_chunk_wider_context", "step": "4-rag-wider-context",
     "hit_log": "retrieval_log_bge_chunk.jsonl"},
]
ANCHOR = 0.400  # T3.9 gold-retrieved conditional (the ceiling the aggregate climbs toward)


def passed(sc):
    return None if sc is None else bool(sc >= PASS)


def load_variant(v):
    """Return {seed: {idx: passed_bool}} for judged records, + hit-rate + gold mask."""
    per_seed, absent = {}, []
    for s in SEEDS:
        p = RUNS / v["step"] / f"seed{s}.jsonl"
        if not p.is_file():
            absent.append(s)
            continue
        recs = {d["idx"]: d for d in (json.loads(l) for l in p.open(encoding="utf-8") if l.strip())}
        judged = {i: passed(d.get("score")) for i, d in recs.items() if d.get("score") is not None}
        if judged:
            per_seed[s] = judged
        else:
            absent.append(s)
    # Say it out loud. A silently-missing seed shrinks n and still prints a
    # plausible table — the exact failure mode flagged in MIGRATION_CHECKLIST §3.7.
    if absent and per_seed:
        print(f"  [warn] {v['name']}: no judged data for seed(s) {absent} "
              f"— this variant is computed on {len(per_seed)}/{len(SEEDS)} seeds")
    gold_mask, hit = None, None
    if v["hit_log"]:
        hp = RUNS / v["hit_log"]
        if hp.is_file():
            rl = {d["idx"]: d for d in (json.loads(l) for l in hp.open(encoding="utf-8"))}
            gold_mask = {i: d["gold_retrieved"] for i, d in rl.items()}
            hit = sum(1 for d in rl.values() if d["gold_retrieved"]) / len(rl)
    else:
        hit = 0.0
    return per_seed, hit, gold_mask


def pooled(per_seed):
    k = n = 0
    for s, d in per_seed.items():
        for i, pv in d.items():
            if pv is not None:
                n += 1; k += pv
    return k, n


def gold_split(per_seed, gold_mask):
    if gold_mask is None:
        return None
    out = {}
    for label, want in (("retrieved", True), ("missed", False)):
        k = n = 0
        for s, d in per_seed.items():
            for i, pv in d.items():
                if pv is not None and gold_mask.get(i) == want:
                    n += 1; k += pv
        out[label] = (k, n, k / n if n else float("nan"))
    return out


def cluster_between(va, vb):
    """paired {idx: {A:[bools], B:[bools]}} over shared seeds, for the bootstrap."""
    ca = defaultdict(lambda: {"A": [], "B": []})
    pairs = []
    for s in SEEDS:
        da, db = va.get(s), vb.get(s)
        if not da or not db:
            continue
        for i in set(da) & set(db):
            if da[i] is None or db[i] is None:
                continue
            ca[i]["A"].append(da[i]); ca[i]["B"].append(db[i])
            pairs.append((da[i], db[i]))
    return ca, pairs


def main():
    loaded = []
    for v in VARIANTS:
        per_seed, hit, gm = load_variant(v)
        if not per_seed:
            print(f"[skip] {v['name']}: no judged run files yet")
            continue
        loaded.append({**v, "per_seed": per_seed, "hit": hit, "gold_mask": gm})

    print("=" * 78)
    print("WixQA T3.11 — dose-response: aggregate pass@>=3 vs retrieval hit-rate@3")
    print(f"(PASS = score>=3; gold-retrieved anchor = {ANCHOR}; only the retriever changes)")
    print("=" * 78)

    print(f"\n{'variant':<14} {'hit@3':>7} {'pass':>7}  {'Wilson 95%':<20} {'seeds':<8} pred(mix)")
    for v in loaded:
        k, n = pooled(v["per_seed"])
        w = wilson_interval(k, n)
        pred = v["hit"] * ANCHOR + (1 - v["hit"]) * 0.211 if v["hit"] is not None else float("nan")
        nseed = len([s for s in v["per_seed"]])
        v["pass"] = k / n if n else float("nan"); v["n"] = n
        hitstr = f"{v['hit']:.3f}" if v["hit"] is not None else "  ?  "
        print(f"{v['name']:<14} {hitstr:>7} {v['pass']:>7.3f}  "
              f"[{w.low:.3f}, {w.high:.3f}]      {nseed} ({n:>3})  {pred:.3f}")

    # gold split (the mechanism: does P(pass|retrieved) stay ~0.400 across retrievers?)
    print(f"\n--- gold split per RAG variant (P(pass|retrieved) should stay ~{ANCHOR}) ---")
    for v in loaded:
        gs = gold_split(v["per_seed"], v["gold_mask"])
        if gs:
            r, m = gs["retrieved"], gs["missed"]
            print(f"  {v['name']:<14} retrieved={r[2]:.3f} (n={r[1]:>3})   missed={m[2]:.3f} (n={m[1]:>3})")

    # dose-response monotonicity + the anchor
    rag = [v for v in loaded if v["hit"] is not None]
    rag.sort(key=lambda x: x["hit"])
    print("\n--- dose-response (sorted by hit-rate) ---")
    prev = None
    mono = True
    for v in rag:
        arrow = "" if prev is None else ("  UP" if v["pass"] >= prev - 1e-9 else "  DOWN (!)")
        if prev is not None and v["pass"] < prev - 1e-9:
            mono = False
        print(f"  hit={v['hit']:.3f} -> pass={v['pass']:.3f}{arrow}")
        prev = v["pass"]
    print(f"  monotonic non-decreasing: {mono}   (anchor P(pass|retrieved)={ANCHOR})")

    # headline pairwise: best improved retriever vs minilm_whole (both RAG)
    byname = {v["name"]: v for v in loaded}
    if "bge_chunk" in byname and "minilm_whole" in byname:
        ca, pairs = cluster_between(byname["bge_chunk"]["per_seed"], byname["minilm_whole"]["per_seed"])
        if pairs:
            boot = paired_cluster_bootstrap(ca, "A", "B", n_resamples=10000, seed=0)
            mc = exact_mcnemar(pairs, "A", "B")
            print("\n--- headline: bge_chunk (hit 0.665) - minilm_whole (hit 0.550), paired ---")
            print(f"  delta pass = {boot.point_estimate:+.3f} [{boot.ci_low:+.3f}, {boot.ci_high:+.3f}]"
                  f"  McNemar p={mc.p_value:.3g}  (n_pairs={mc.n_pairs})")
            print(f"  predicted by mixture: +{(0.665-0.550)*(ANCHOR-0.211):.3f} "
                  f"(hit +0.115 x (0.400-0.211))")


if __name__ == "__main__":
    main()
