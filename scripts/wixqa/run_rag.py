"""WixQA 3B+RAG: same student/judge as wixqa_baseline.py, but the student is
grounded on top-k KB articles retrieved from the FAISS index. Compares against
the no-RAG baseline to measure RAG's value where a REAL knowledge gap exists.

Honest RAG (not leakage): the KB is the legitimate knowledge source; grounding
on the source article is the intended behaviour. Judge stays reference-comparing
(sees gold to score); student sees only the question + retrieved KB passages,
never the gold answer (§0.2 preserved).

  python scripts/wixqa/run_rag.py --limit 200 --top-k 3
"""
import argparse, json, re, sys
from pathlib import Path
import numpy as np
import faiss

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import src.tlw.providers  # noqa: registers Ollama under "local"
from src.providers.factory import build_client
from tools.dataset.embeddings import embed
from src.tlw.wixqa.prompts import JUDGE_SYS, judge_score

QA = ROOT / "data/external/wixqa/expertwritten.jsonl"
IDX = ROOT / "indexes/wixqa-help-centre"
MAX_PASSAGE_CHARS = 900  # per-article cap in the grounding block

def load_index():
    idx = faiss.read_index(str(IDX / "faiss.index"))
    passages = [json.loads(l) for l in (IDX / "passages.jsonl").open(encoding="utf-8")]
    return idx, passages

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--top-k", type=int, default=3)
    a = ap.parse_args()

    recs = [json.loads(l) for l in QA.open(encoding="utf-8")][: a.limit]
    idx, passages = load_index()
    student = build_client("local", model="qwen2.5:3b")
    judge = build_client("groq", model="llama-3.1-8b-instant")

    # retrieve for all questions at once
    qvecs = np.asarray(embed([r["question"] for r in recs]), dtype="float32")
    faiss.normalize_L2(qvecs)
    D, I = idx.search(qvecs, a.top_k)

    scores = []
    out = ROOT / "runs/rag-wixqa"; out.mkdir(exist_ok=True)
    log = (out / f"rag_top{a.top_k}.jsonl").open("w", encoding="utf-8")
    for i, r in enumerate(recs):
        q, ref = r["question"], r["answer"]
        hits = [passages[j] for j in I[i] if j >= 0]
        block = "\n\n".join(
            f"[{k+1}] {h['title']}\n{h['passage'][:MAX_PASSAGE_CHARS]}" for k, h in enumerate(hits)
        )
        sims = [round(float(D[i][k]), 3) for k in range(len(hits))]
        try:
            ans = student.chat(
                [{"role": "system", "content":
                  "You are a helpful Wix customer-support assistant. Use the REFERENCE CONTEXT below "
                  "(help-center articles) to answer the question accurately and concisely. "
                  "If the context is relevant, ground your answer in it."},
                 {"role": "user", "content": f"REFERENCE CONTEXT:\n{block}\n\nQUESTION: {q}"}],
                temperature=0.3, max_tokens=256, timeout_s=60,
            ).text
        except Exception as e:
            ans = ""; print(f"[{i}] student err: {e}")
        s = judge_score(judge, q, ref, ans)
        scores.append(s)
        log.write(json.dumps({"idx": i, "question": q, "answer": ans, "reference": ref,
                              "score": s, "retrieved_ids": [h["id"] for h in hits],
                              "sims": sims, "gold_article_ids": r.get("article_ids", [])},
                             ensure_ascii=False) + "\n")
        if (i + 1) % 20 == 0:
            v = [x for x in scores if x is not None]
            print(f"  {i+1}/{len(recs)}  pass@>=4={sum(x>=4 for x in v)/len(v):.3f}  pass@>=3={sum(x>=3 for x in v)/len(v):.3f}")
    log.close()

    v = [x for x in scores if x is not None]; n = len(v)
    print(f"\n=== WixQA 3B+RAG (top_k={a.top_k}) ===")
    print(f"n={n}")
    print(f"pass@>=4: {sum(x>=4 for x in v)}/{n} = {sum(x>=4 for x in v)/n:.3f}")
    print(f"pass@>=3: {sum(x>=3 for x in v)}/{n} = {sum(x>=3 for x in v)/n:.3f}")
    print(f"mean score: {sum(v)/n:.2f}")
    # retrieval hit-rate: did we retrieve a gold article?
    got_gold = 0
    for l in (out / f"rag_top{a.top_k}.jsonl").open(encoding="utf-8"):
        d = json.loads(l)
        if set(d["retrieved_ids"]) & set(d["gold_article_ids"]):
            got_gold += 1
    print(f"retrieval hit (gold article in top-{a.top_k}): {got_gold}/{n} = {got_gold/n:.3f}")

if __name__ == "__main__":
    main()
