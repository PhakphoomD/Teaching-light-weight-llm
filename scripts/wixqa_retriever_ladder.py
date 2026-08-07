"""WixQA T3.10 (P3-E): offline retriever ladder, ranked by hit-rate@k. NO LLM.

Builds a small ladder of stronger retrievers over the SAME 6,221-article WixQA KB
and ranks them purely by OFFLINE hit-rate@k (did a gold KB article land in the
top-k articles for each of the 200 questions). This is the cheap de-risk that
decides whether the expensive 3-seed end-to-end run (T3.11) is worth it, and with
which retriever — the T2.7-pilot discipline applied to retrieval.

Levers (each variant changes ONE thing from the baseline where possible):
  V1 minilm_whole  — all-MiniLM-L6-v2, one vector per article        (T3.9 baseline)
  V2 minilm_chunk  — all-MiniLM-L6-v2, article split into chunks     (isolates CHUNKING)
  V3 bge_whole     — BAAI/bge-base-en-v1.5, one vector per article   (isolates ENCODER)
  V4 bge_chunk     — bge-base-en-v1.5 + chunking                     (combined)
  V5 bm25          — lexical BM25 over whole articles                (exact-term matches)
  V6 hybrid_rrf    — RRF(bm25, best-dense)                           (lexical + dense)

Honesty (§0.2 / P3-E): KB articles ONLY are indexed (never the 200 expert QA
answers). Gold ARTICLE IDS are used only to SCORE hit-rate — never the QA answer
text to pick chunks. Deterministic (exact FAISS IP + deterministic BM25); no seed
needed. The judge/student are not involved here (offline hit-rate only).

  HF_HUB_OFFLINE=1 python scripts/wixqa_retriever_ladder.py --variants minilm_whole minilm_chunk bm25 hybrid_rrf
  HF_HUB_OFFLINE=1 python scripts/wixqa_retriever_ladder.py --variants bge_whole bge_chunk
  python scripts/wixqa_retriever_ladder.py            # all variants
"""
import argparse, json, os, re, sys, time
from pathlib import Path

import numpy as np
import faiss

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

KB = ROOT / "data/external/wixqa/kb_corpus.jsonl"
QA = ROOT / "data/external/wixqa/expertwritten.jsonl"
OUT = ROOT / "reports/rag-wixqa"; OUT.mkdir(parents=True, exist_ok=True)

KS = [1, 3, 5, 10]          # hit-rate@k to report; k=3 is the headline (RAG top-k)
CHUNK_WORDS, OVERLAP = 180, 40   # ~256-token window; fits MiniLM(256) and bge(512)
RETRIEVE_CHUNKS = 200       # top chunks pulled before de-duping to unique articles

# per-encoder query/passage prefixes (wrong prefix -> silent hit-rate drop)
ENCODERS = {
    "minilm": {"model": "all-MiniLM-L6-v2", "q_prefix": "", "p_prefix": ""},
    "bge":    {"model": "BAAI/bge-base-en-v1.5",
               "q_prefix": "Represent this sentence for searching relevant passages: ", "p_prefix": ""},
}
_MODELS = {}


def get_model(enc):
    if enc not in _MODELS:
        from sentence_transformers import SentenceTransformer
        _MODELS[enc] = SentenceTransformer(ENCODERS[enc]["model"], device="cuda")
    return _MODELS[enc]


def encode(enc, texts, is_query):
    pref = ENCODERS[enc]["q_prefix"] if is_query else ENCODERS[enc]["p_prefix"]
    txt = [pref + t for t in texts] if pref else list(texts)
    v = get_model(enc).encode(txt, normalize_embeddings=True, batch_size=128,
                              show_progress_bar=False, convert_to_numpy=True)
    return np.asarray(v, dtype="float32")


def load_data():
    arts = [json.loads(l) for l in KB.open(encoding="utf-8")]
    qa = [json.loads(l) for l in QA.open(encoding="utf-8")]
    kb_ids = [a["id"] for a in arts]
    # KB-only seal: indexed ids are exactly the KB; QA answers are never indexed.
    assert len(set(kb_ids)) == len(kb_ids), "duplicate KB ids"
    gold = [set(q.get("article_ids", [])) for q in qa]
    assert all(g and g <= set(kb_ids) for g in gold), "a gold id is missing from the KB"
    return arts, qa, kb_ids, gold


def chunks_of(article):
    title = (article.get("title") or "").strip()
    words = (article.get("contents") or "").split()
    if not words:
        return [title] if title else [""]
    out, stride = [], CHUNK_WORDS - OVERLAP
    for s in range(0, len(words), stride):
        piece = " ".join(words[s:s + CHUNK_WORDS])
        out.append(f"{title}. {piece}" if title else piece)
        if s + CHUNK_WORDS >= len(words):
            break
    return out


def rank_articles_dense(enc, arts, qa, chunked):
    """Return, per question, a ranked list of unique article ids (best-first)."""
    if chunked:
        chunk_texts, chunk_aid = [], []
        for a in arts:
            for c in chunks_of(a):
                chunk_texts.append(c); chunk_aid.append(a["id"])
        pv = encode(enc, chunk_texts, is_query=False)
        topm = RETRIEVE_CHUNKS
    else:
        whole = [((a.get("title") or "") + "\n" + (a.get("contents") or "")) for a in arts]
        pv = encode(enc, whole, is_query=False)
        chunk_aid = [a["id"] for a in arts]
        topm = 50
    index = faiss.IndexFlatIP(pv.shape[1]); index.add(pv)
    qv = encode(enc, [q["question"] for q in qa], is_query=True)
    _, I = index.search(qv, topm)
    ranked = []
    for row in I:
        seen, order = set(), []
        for j in row:
            if j < 0:
                continue
            aid = chunk_aid[j]
            if aid not in seen:
                seen.add(aid); order.append(aid)
        ranked.append(order)
    return ranked


_tok = re.compile(r"[a-z0-9]+")
def _toks(s):
    return _tok.findall(s.lower())


def rank_articles_bm25(arts, qa):
    from rank_bm25 import BM25Okapi
    corpus = [_toks((a.get("title") or "") + " " + (a.get("contents") or "")) for a in arts]
    bm = BM25Okapi(corpus)
    aids = [a["id"] for a in arts]
    ranked = []
    for q in qa:
        scores = bm.get_scores(_toks(q["question"]))
        order = np.argsort(-scores)[:50]
        ranked.append([aids[j] for j in order])
    return ranked


def rerank_cross(base_ranked, arts, qa, topn=20,
                 model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"):
    """Cross-encoder re-rank of the top-N articles from a base dense ranking.
    Scores (question, article title+snippet) pairs jointly (no LLM generation)
    and re-orders the head; the tail (beyond topn) is kept in its original order.
    @10=0.845 for bge_chunk => lots of gold sits in ranks 4-10 that a reranker
    can lift into the top-3."""
    from sentence_transformers import CrossEncoder
    ce = CrossEncoder(model_name, device="cuda", max_length=512)
    aid2text = {a["id"]: ((a.get("title") or "") + ". " + (a.get("contents") or ""))[:2000] for a in arts}
    out = []
    for order, q in zip(base_ranked, qa):
        head = order[:topn]
        pairs = [(q["question"], aid2text[aid]) for aid in head]
        scores = ce.predict(pairs, batch_size=64, show_progress_bar=False)
        reranked = [aid for _, aid in sorted(zip(scores, head), key=lambda x: -x[0])]
        out.append(reranked + order[topn:])
    return out


def rrf(list_a, list_b, k0=60, cutoff=50):
    """Reciprocal-rank fusion of two per-question ranked article-id lists."""
    fused = []
    for ra, rb in zip(list_a, list_b):
        score = {}
        for rank, aid in enumerate(ra):
            score[aid] = score.get(aid, 0.0) + 1.0 / (k0 + rank)
        for rank, aid in enumerate(rb):
            score[aid] = score.get(aid, 0.0) + 1.0 / (k0 + rank)
        fused.append([a for a, _ in sorted(score.items(), key=lambda x: -x[1])[:cutoff]])
    return fused


def hitrate(ranked, gold):
    """hit@k for each k in KS + gold_rank stats (median rank of first gold, misses=inf)."""
    res = {}
    for k in KS:
        res[k] = sum(1 for order, g in zip(ranked, gold) if g & set(order[:k])) / len(gold)
    ranks = []
    for order, g in zip(ranked, gold):
        r = next((i + 1 for i, aid in enumerate(order) if aid in g), None)
        ranks.append(r)
    found = [r for r in ranks if r is not None]
    res["mrr"] = float(np.mean([1.0 / r for r in found] + [0.0] * (len(gold) - len(found))))
    return res, ranks


def build_ranked(name, arts, qa):
    if name == "minilm_whole":
        return rank_articles_dense("minilm", arts, qa, chunked=False)
    if name == "minilm_chunk":
        return rank_articles_dense("minilm", arts, qa, chunked=True)
    if name == "bge_whole":
        return rank_articles_dense("bge", arts, qa, chunked=False)
    if name == "bge_chunk":
        return rank_articles_dense("bge", arts, qa, chunked=True)
    if name == "bm25":
        return rank_articles_bm25(arts, qa)
    if name == "bge_chunk_rerank":
        dense = _RANK_CACHE.get("bge_chunk") or rank_articles_dense("bge", arts, qa, chunked=True)
        _RANK_CACHE["bge_chunk"] = dense
        return rerank_cross(dense, arts, qa)
    if name == "hybrid_rrf":
        # RRF(bm25, best available dense) — prefer bge_chunk if present, else minilm_chunk
        dense_name = "bge_chunk" if "bge_chunk" in _RANK_CACHE else (
            "minilm_chunk" if "minilm_chunk" in _RANK_CACHE else "minilm_whole")
        dense = _RANK_CACHE.get(dense_name) or build_ranked(dense_name, arts, qa)
        _RANK_CACHE[dense_name] = dense
        bm = _RANK_CACHE.get("bm25") or rank_articles_bm25(arts, qa)
        _RANK_CACHE["bm25"] = bm
        return rrf(bm, dense), dense_name
    raise SystemExit(f"unknown variant {name}")


_RANK_CACHE = {}
ALL = ["minilm_whole", "minilm_chunk", "bge_whole", "bge_chunk", "bm25", "hybrid_rrf", "bge_chunk_rerank"]


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
        out = build_ranked(name, arts, qa)
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
