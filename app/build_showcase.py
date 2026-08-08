"""Capture a curated set of before/after demo examples -> reports/rag-wixqa/demo-showcase.jsonl.

These are the concrete "went from wrong -> right when the answer reached the prompt"
exhibits the narrative (T3.17) shows, and the set selector the demo UI offers. The set
is chosen to include BOTH honest cases:

  * gold-retrieved questions -> RAG has the material and helps
  * gold-missed questions    -> RAG is limited (kept, on purpose — honest, not cherry-picked)

Each record stores the answer from every compare-lane plus, if a judge is reachable,
its 0-4 score. Judge = Groq reference-comparing (only the JUDGE sees the gold answer,
§0.2); if no GROQ key / quota, answers are captured without scores (still useful).

  python app/build_showcase.py --per-set 3          # small, fast
  python app/build_showcase.py --per-set 4 --refine  # include the self-refine lane
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import faiss
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.engine import DemoEngine  # noqa: E402
from tools.dataset.embeddings import embed  # noqa: E402

QA_PATH = ROOT / "data" / "external" / "wixqa" / "expertwritten.jsonl"
OUT = ROOT / "reports" / "rag-wixqa" / "demo-showcase.jsonl"


def make_judge():
    """A reference-comparing Groq judge, or None if unreachable (offline-safe)."""
    try:
        import src.tlw.providers  # noqa: F401
        from src.providers.factory import build_client
        from src.tlw.wixqa.prompts import judge_score

        judge = build_client("groq", model="llama-3.1-8b-instant")
        # probe once so we degrade gracefully rather than mid-run
        judge_score(judge, "test?", "a test reference", "a test candidate")
        return judge, judge_score
    except Exception as e:  # noqa: BLE001
        print(f"[judge] unavailable ({e}); capturing answers without scores")
        return None, None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-set", type=int, default=3, help="questions per gold-retrieved / gold-missed set")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--refine", action="store_true", help="also capture the self-refine lane")
    a = ap.parse_args()

    qa = [json.loads(l) for l in QA_PATH.open(encoding="utf-8")]
    eng = DemoEngine()

    # one batched retrieval over all questions -> split by gold_retrieved (fast, no LLM)
    qv = np.asarray(embed([q["question"] for q in qa]), dtype="float32")
    faiss.normalize_L2(qv)
    _, I = eng.index.search(qv, a.top_k)
    retrieved = [{eng.passages[j]["id"] for j in row if j >= 0} for row in I]
    gold_hit = [bool(r & set(q.get("article_ids", []))) for r, q in zip(retrieved, qa)]

    picked = ([q for q, g in zip(qa, gold_hit) if g][: a.per_set]
              + [q for q, g in zip(qa, gold_hit) if not g][: a.per_set])
    print(f"curated {len(picked)} questions ({a.per_set} gold-retrieved + {a.per_set} gold-missed)")

    judge, judge_score = make_judge()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for n, q in enumerate(picked, 1):
            r = eng.compare(q["question"], top_k=a.top_k, refine=a.refine,
                            gold_ids=q.get("article_ids", []))
            rec = {"question": q["question"], "reference": q["answer"],
                   "gold_article_ids": q.get("article_ids", []),
                   "gold_retrieved": r["gold_retrieved"], "sources": r["sources"],
                   "lanes": r["lanes"], "latency_s": r["latency_s"]}
            if judge:
                rec["scores"] = {k: judge_score(judge, q["question"], q["answer"], v)
                                 for k, v in r["lanes"].items()}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            tag = "gold✓" if r["gold_retrieved"] else "gold✗"
            sc = rec.get("scores", {})
            print(f"  [{n}/{len(picked)}] {tag}  "
                  + (f"no_rag={sc.get('no_rag')} wide={sc.get('rag_wide')}" if sc else "captured"))
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
