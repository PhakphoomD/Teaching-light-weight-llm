"""WixQA T3.10: rank retriever variants by OFFLINE hit-rate@k. NO LLM calls.

The cheap de-risk before an expensive end-to-end run — the T2.7-pilot discipline
applied to retrieval. All the retrieval logic lives in `src.tlw.wixqa.retrieval`
(ADR-034 §A4: scripts drive, they do not define); this file is the CLI.

  HF_HUB_OFFLINE=1 python scripts/wixqa/build_retriever_ladder.py
  HF_HUB_OFFLINE=1 python scripts/wixqa/build_retriever_ladder.py --variants bge_chunk bm25
-> reports/rag-wixqa/retriever-hitrate.json
"""
import argparse, json, os, sys, time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.tlw.wixqa.retrieval import (
    CHUNK_WORDS, KS, OVERLAP, VARIANT_NAMES, build_ranked, hitrate, load_data,
)

OUT = ROOT / "reports/rag-wixqa"; OUT.mkdir(parents=True, exist_ok=True)
ALL = VARIANT_NAMES
_RANK_CACHE = {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+", default=ALL)
    a = ap.parse_args()

    arts, qa, kb_ids, gold = load_data()
    print(f"KB articles indexed: {len(arts)} (KB-only seal OK; QA answers NOT indexed)")
    print(f"questions: {len(qa)}  gold ids/q mean={np.mean([len(g) for g in gold]):.2f}  "
          f"(hit-rate ceiling = 100% — all gold in KB)\n")

    results = {}
    hybrid_dense = None
    for name in a.variants:
        t = time.time()
        out = build_ranked(name, arts, qa, _RANK_CACHE)
        if isinstance(out, tuple):
            ranked, hybrid_dense = out
        else:
            ranked = out
        _RANK_CACHE[name] = ranked
        res, ranks = hitrate(ranked, gold)
        results[name] = {"hitrate": res, "gold_ranks": ranks, "secs": round(time.time() - t, 1)}
        hdr = f"[{name}]" + (f" (dense={hybrid_dense})" if hybrid_dense and name == "hybrid_rrf" else "")
        print(f"{hdr:<34} " + "  ".join(f"@{k}={res[k]:.3f}" for k in KS) +
              f"  mrr={res['mrr']:.3f}  ({results[name]['secs']}s)")

    # merge into the on-disk table (so partial runs accumulate)
    tbl_path = OUT / "retriever-hitrate.json"
    table = json.loads(tbl_path.read_text()) if tbl_path.is_file() else {}
    for name, r in results.items():
        table[name] = {"hitrate": r["hitrate"], "secs": r["secs"], "gold_ranks": r["gold_ranks"]}
    table["_meta"] = {"n_articles": len(arts), "n_questions": len(qa), "ks": KS,
                      "chunk_words": CHUNK_WORDS, "overlap": OVERLAP, "baseline": "minilm_whole"}
    tbl_path.write_text(json.dumps(table, indent=2))

    # summary table vs baseline @3 (the headline k)
    base = table.get("minilm_whole", {}).get("hitrate", {}).get("3")
    base = table.get("minilm_whole", {}).get("hitrate", {}).get(3, base)
    print("\n=== hit-rate@3 vs baseline (minilm_whole) ===")
    for name in table:
        if name == "_meta":
            continue
        h3 = table[name]["hitrate"].get("3", table[name]["hitrate"].get(3))
        delta = f"{h3 - base:+.3f}" if base is not None else "  n/a"
        print(f"  {name:<16} @3={h3:.3f}  Δ={delta}")
    print(f"\nwrote {tbl_path}")


if __name__ == "__main__":
    main()
