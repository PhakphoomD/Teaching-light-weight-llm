"""WixQA: seeded + instrumented student generation for the 3-seed re-run.

Generates the 3B student's answers for ONE arm (baseline | rag) at a given seed,
with a per-question RETRIEVAL RECORD (rag arm) so the dose-response proof
can measure pass-rate vs hit-rate. Scores are left null here; scoring is a
SEPARATE, budget-aware pass (scripts/wixqa/judge.py) so Groq's org-wide TPD cap
never corrupts a run mid-flight (never destructive-judge on a
half-empty budget).

Comparability (ADR-030): prompts, retrieval config (top_k=3, MAX_PASSAGE_CHARS=900),
temperature (0.3), and max_tokens (256) are IDENTICAL to wixqa_baseline.py /
wixqa_rag.py. The judge (scripts/wixqa/judge.py) reuses the SAME JUDGE_SYS. The
ONLY new variable is Ollama's options.seed, so seeds {13,42,123} are
distinct-but-reproducible draws from the same temp-0.3 distribution (§0.3).

Honesty (ADR-030 / the retrieval-bottleneck study): the WixQA KB is the LEGITIMATE knowledge source;
grounding on the retrieved article is intended (not leakage). The STUDENT never
sees the gold answer; only the (separate) judge does. The index holds KB articles
only, never the 200 expert QA answers.

  HF_HUB_OFFLINE=1 python scripts/wixqa/run_three_seeds.py --arm rag      --seed 13
  HF_HUB_OFFLINE=1 python scripts/wixqa/run_three_seeds.py --arm baseline --seed 13
"""
import argparse, json, os, sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # MiniLM stall guard (memory: hf-offline-embedding-stall)

import numpy as np
import faiss

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import src.tlw.providers  # noqa: F401 — registers Ollama under "local"
from src.providers.factory import build_client
from tools.dataset.embeddings import embed

QA = ROOT / "data/external/wixqa/expertwritten.jsonl"
IDX = ROOT / "indexes/wixqa-help-centre"
OUT = ROOT / "runs/rag-wixqa"

# --- prompts / config, VERBATIM from ADR-030 scripts (do not drift) -----------
# baseline system prompt: wixqa_baseline.py:63
BASELINE_SYS = ("You are a helpful Wix customer-support assistant. "
                "Answer the user's question concisely and accurately.")
# rag system prompt: wixqa_rag.py:64-66
RAG_SYS = ("You are a helpful Wix customer-support assistant. Use the REFERENCE CONTEXT below "
           "(help-center articles) to answer the question accurately and concisely. "
           "If the context is relevant, ground your answer in it.")
MAX_PASSAGE_CHARS = 900   # wixqa_rag.py:28
TEMPERATURE = 0.3         # wixqa_baseline.py / wixqa_rag.py
MAX_TOKENS = 256
# ------------------------------------------------------------------------------


def load_index():
    idx = faiss.read_index(str(IDX / "faiss.index"))
    passages = [json.loads(l) for l in (IDX / "passages.jsonl").open(encoding="utf-8")]
    return idx, passages


def retrieval_record(idx_i, question, gold_ids, retrieved_ids, sims):
    """Per-question retrieval instrument (seed-independent): rank of the first
    retrieved gold article (1-based), whether any gold was retrieved, top sim."""
    gold_set = set(gold_ids)
    gold_rank = -1
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in gold_set:
            gold_rank = rank
            break
    return {
        "idx": idx_i,
        "question": question,
        "gold_article_ids": list(gold_ids),
        "retrieved_ids": list(retrieved_ids),
        "sims": sims,
        "gold_rank": gold_rank,
        "gold_retrieved": gold_rank != -1,
        "top_sim": sims[0] if sims else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["baseline", "rag"], required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--top-k", type=int, default=3)
    a = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    recs = [json.loads(l) for l in QA.open(encoding="utf-8")][: a.limit]
    student = build_client("local", model="qwen2.5:3b")

    # --- retrieval (rag arm only) — deterministic, seed-independent -----------
    ret_records = None
    if a.arm == "rag":
        idx, passages = load_index()
        qvecs = np.asarray(embed([r["question"] for r in recs]), dtype="float32")
        faiss.normalize_L2(qvecs)
        D, I = idx.search(qvecs, a.top_k)
        ret_records = []
        for i, r in enumerate(recs):
            hits = [passages[j] for j in I[i] if j >= 0]
            sims = [round(float(D[i][k]), 3) for k in range(len(hits))]
            ret_records.append((
                hits, sims,
                retrieval_record(i, r["question"], r.get("article_ids", []),
                                 [h["id"] for h in hits], sims),
            ))
        # canonical seed-independent retrieval log (write once; identical across seeds)
        rl = OUT / "retrieval_log.jsonl"
        with rl.open("w", encoding="utf-8") as f:
            for _, _, rr in ret_records:
                f.write(json.dumps(rr, ensure_ascii=False) + "\n")
        hit = sum(1 for _, _, rr in ret_records if rr["gold_retrieved"])
        print(f"retrieval: hit-rate = {hit}/{len(recs)} = {hit/len(recs):.3f}  -> {rl.name}")

    # --- generation (seeded student) -----------------------------------------
    out_path = OUT / f"{a.arm}__seed{a.seed}.jsonl"
    f = out_path.open("w", encoding="utf-8")
    fails = 0
    for i, r in enumerate(recs):
        q, ref = r["question"], r["answer"]
        if a.arm == "baseline":
            messages = [{"role": "system", "content": BASELINE_SYS},
                        {"role": "user", "content": q}]
            extra = {}
        else:
            hits, sims, rr = ret_records[i]
            block = "\n\n".join(
                f"[{k+1}] {h['title']}\n{h['passage'][:MAX_PASSAGE_CHARS]}" for k, h in enumerate(hits))
            messages = [{"role": "system", "content": RAG_SYS},
                        {"role": "user", "content": f"REFERENCE CONTEXT:\n{block}\n\nQUESTION: {q}"}]
            extra = {k: rr[k] for k in ("gold_article_ids", "retrieved_ids", "sims",
                                        "gold_rank", "gold_retrieved", "top_sim")}
        res = student.chat(messages, temperature=TEMPERATURE, max_tokens=MAX_TOKENS,
                           timeout_s=90, seed=a.seed)
        ans = res.text
        if res.error or not ans:
            fails += 1
            print(f"[{i}] student err/empty: {res.error}")
        rec = {"idx": i, "seed": a.seed, "arm": a.arm, "question": q,
               "reference": ref, "answer": ans, "score": None, **extra}
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        if (i + 1) % 25 == 0:
            print(f"  gen {i+1}/{len(recs)} (student_fails={fails})")
    f.close()
    print(f"\nwrote {out_path.name} ({len(recs)} records, score=null, student_fails={fails})")
    print("next: score with  scripts/wixqa/judge.py")


if __name__ == "__main__":
    main()
