"""Build a FAISS index over the WixQA KB corpus (6,221 articles) for RAG.

Doc-retrieval (NOT the MedQuAD question->answer scheme): embed each article's
title+contents, retrieve by the user question, ground on the article contents.
NO anti-leak scrub — the KB is the LEGITIMATE knowledge source (the expert answer
is distilled FROM it); filtering shared text would remove the very article we want.
That is the honest difference from MedQuAD (single-source QA where corpus==answer).

  python scripts/wixqa_build_index.py
-> indexes/wixqa-help-centre/{faiss.index, passages.jsonl, manifest.json}
"""
import json, sys
from pathlib import Path
import numpy as np
import faiss

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.dataset.embeddings import embed

KB = ROOT / "data/external/wixqa/kb_corpus.jsonl"
OUT = ROOT / "indexes/wixqa-help-centre"; OUT.mkdir(parents=True, exist_ok=True)
MAX_EMBED_CHARS = 2000  # MiniLM truncates ~256 tokens anyway; title leads

def main():
    arts = [json.loads(l) for l in KB.open(encoding="utf-8")]
    print(f"KB articles: {len(arts)}")
    # embedding text = title + contents (truncated); passage = full contents
    embed_texts = [((a.get("title") or "") + "\n" + (a.get("contents") or ""))[:MAX_EMBED_CHARS] for a in arts]
    vecs = np.asarray(embed(embed_texts), dtype="float32")
    faiss.normalize_L2(vecs)
    idx = faiss.IndexFlatIP(vecs.shape[1])
    idx.add(vecs)
    faiss.write_index(idx, str(OUT / "faiss.index"))
    with (OUT / "passages.jsonl").open("w", encoding="utf-8") as f:
        for row, a in enumerate(arts):
            f.write(json.dumps({
                "row": row, "id": a["id"], "title": a.get("title", ""),
                "passage": a.get("contents", ""), "article_type": a.get("article_type", ""),
            }, ensure_ascii=False) + "\n")
    (OUT / "manifest.json").write_text(json.dumps({
        "name": "wixqa_kb", "encoder": "all-MiniLM-L6-v2", "dim": int(vecs.shape[1]),
        "index_type": "IndexFlatIP", "n_indexed": len(arts), "anti_leak": "none (KB is the legitimate source)",
    }, indent=2), encoding="utf-8")
    print(f"indexed {idx.ntotal} articles (dim {vecs.shape[1]}) -> {OUT}")

if __name__ == "__main__":
    main()
