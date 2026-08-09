"""WixQA T3.14 Stage-1 (P3-E): OFFLINE grounding ladder — answer-coverage@budget. NO LLM.

The T3.11 diagnostic found we truncate the answer out of the prompt ourselves:
gold articles are median 3,555 chars but grounding shows only the first 900, so
the student sees ~25% of the gold article and only ~36% of the expert answer's
content words (the full article holds ~72%). This script ranks grounding
variants by how much of the answer actually REACHES the prompt — the exact
analogue of T3.10's offline hit-rate ladder, and the cheap gate before any
end-to-end run.

2x2 factorial (isolates the two levers independently):
                     budget 900/article      budget 2400/article
  article HEAD       G1 head900 (= T3.11)    G3 head2400
  CHUNK-centred      G2 chunk900             G4 chunk2400
`chunk-centred` uses the retriever's OWN localisation: bge_chunk matches a
180-word chunk, so we centre the window on that chunk instead of the article
head (T3.11 discarded this — the matched chunk can sit mid-article).

HONESTY (§0.2): the reference answer is used ONLY here, offline, by the analyst,
to SCORE coverage — exactly the same status as using gold article-ids to score
hit-rate. Runtime grounding never sees the reference; nothing here selects
content using the answer.

  HF_HUB_OFFLINE=1 python scripts/wixqa/build_grounding_ladder.py
-> reports/rag-wixqa/context-window-coverage.json
"""
import argparse, json, os, re, sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.tlw.wixqa.retrieval import encode, load_data
from src.tlw.wixqa.grounding import (GROUNDINGS, STOP_WORDS, best_chunk_word_offset,
                                     window)

RL = ROOT / "runs/rag-wixqa/retrieval_log_bge_chunk.jsonl"   # the T3.11 retrieval (article ids per question)
OUT = ROOT / "reports/rag-wixqa"; OUT.mkdir(parents=True, exist_ok=True)

def content(text: str):
    return set(w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP_WORDS and len(w) > 2)






def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+",
                    default=["head900", "chunk900", "head2400", "chunk2400"])
    a = ap.parse_args()

    arts, qa, kb_ids, gold = load_data()
    id2art = {x["id"]: x for x in arts}
    rl = {d["idx"]: d for d in (json.loads(l) for l in RL.open(encoding="utf-8"))}

    # question vectors once (bge query prefix handled inside encode)
    qvecs = encode("bge", [q["question"] for q in qa], is_query=True)

    # matched-chunk offsets for every (question, retrieved article) — only the
    # ~500 retrieved articles are encoded, not the whole 6,221-article KB.
    print("locating the matched chunk inside each retrieved article ...")
    offsets = {}
    for i, q in enumerate(qa):
        for aid in rl[i]["retrieved_ids"]:
            if (i, aid) not in offsets:
                offsets[(i, aid)] = best_chunk_word_offset(id2art[aid], qvecs[i])
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(qa)}")

    SPEC = GROUNDINGS

    results = {}
    for name in a.variants:
        budget, centred = SPEC[name]
        cov_block, cov_gold, blk_chars = [], [], []
        for i, q in enumerate(qa):
            r = rl[i]
            ref = content(q["answer"])
            if not ref:
                continue
            parts, gold_part = [], ""
            for aid in r["retrieved_ids"]:
                art = id2art[aid]
                txt = window(art, budget, offsets[(i, aid)] if centred else None)
                parts.append(f"{art.get('title','')}\n{txt}")
                if aid in set(q.get("article_ids", [])):
                    gold_part = txt
            block = "\n\n".join(parts)
            blk_chars.append(len(block))
            cov_block.append(len(ref & content(block)) / len(ref))
            if r["gold_retrieved"]:
                cov_gold.append(len(ref & content(gold_part)) / len(ref))
        results[name] = {
            "budget_chars_per_article": budget, "chunk_centred": centred,
            "coverage_block_mean": float(np.mean(cov_block)),
            "coverage_block_median": float(np.median(cov_block)),
            "coverage_gold_mean": float(np.mean(cov_gold)),
            "coverage_gold_median": float(np.median(cov_gold)),
            "n_gold_retrieved": len(cov_gold),
            "block_chars_mean": float(np.mean(blk_chars)),
        }
        r0 = results[name]
        print(f"[{name:<10}] block-coverage mean={r0['coverage_block_mean']:.3f} "
              f"med={r0['coverage_block_median']:.3f} | gold-article coverage "
              f"mean={r0['coverage_gold_mean']:.3f} | prompt {r0['block_chars_mean']:.0f} chars")

    # ceiling reference: the FULL gold article (what is achievable at any budget)
    full = []
    for i, q in enumerate(qa):
        if not rl[i]["gold_retrieved"]:
            continue
        ref = content(q["answer"])
        gid = next((g for g in q.get("article_ids", []) if g in rl[i]["retrieved_ids"]), None)
        if gid and ref:
            full.append(len(ref & content(id2art[gid].get("contents") or "")) / len(ref))
    ceiling = float(np.mean(full))

    (OUT / "context-window-coverage.json").write_text(json.dumps(
        {**results, "_meta": {"ceiling_full_gold_article_coverage": ceiling,
                              "baseline": "head900", "n_questions": len(qa)}}, indent=2))

    print(f"\n=== gold-article answer-coverage vs the T3.11 baseline (head900) ===")
    base = results.get("head900", {}).get("coverage_gold_mean")
    for n, r in results.items():
        d = f"{r['coverage_gold_mean'] - base:+.3f}" if base else "  n/a"
        print(f"  {n:<10} {r['coverage_gold_mean']:.3f}  Δ={d}   (prompt {r['block_chars_mean']:.0f} chars)")
    print(f"  CEILING (full gold article) = {ceiling:.3f}")
    print(f"\nwrote {OUT/'context-window-coverage.json'}")


if __name__ == "__main__":
    main()
