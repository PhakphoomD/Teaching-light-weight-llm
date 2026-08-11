"""Retrieval over the WixQA knowledge base — the seven variants of the retriever comparison.

Moved verbatim from `scripts/wixqa/build_retriever_ladder.py`, which four other scripts
imported. Behaviour is unchanged: the chunk size, the encoder prefixes and the
candidate depths are the controlled variables behind the published hit-rates
 and the dose-response proof.

Measured hit-rate@3 over the 200 questions, for reference:

    bge_chunk         0.665   <- the winner, used for the end-to-end runs
    minilm_chunk      0.645          chunking is the dominant lever
    bge_chunk_rerank  0.640          a wash at k=3: better recall@10, worse @3
    bge_whole         0.620
    hybrid_rrf        0.605          fusing weak lexical HURTS a strong dense
    minilm_whole      0.550   <- the ADR-030 retriever
    bm25              0.465

**KB-only seal.** `load_data` asserts that every gold article id exists in the KB
and that ids are unique. The 200 expert answers are never embedded, never
indexed, and never reach a student prompt — only the judge sees them.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .paths import KB_PATH, QA_PATH

#: hit-rate@k reported by the ladder; k=3 is the headline (it is the RAG top-k).
KS = [1, 3, 5, 10]

#: ~256-token window: fits MiniLM's 256-token limit and leaves room under bge's 512.
CHUNK_WORDS, OVERLAP = 180, 40

#: chunk candidates pulled before de-duplicating down to unique articles.
RETRIEVE_CHUNKS = 200

#: Query/passage prefixes are NOT cosmetic — bge is trained with an instruction
#: prefix on the query side, and omitting it silently costs hit-rate.
ENCODERS = {
    "minilm": {"model": "all-MiniLM-L6-v2", "q_prefix": "", "p_prefix": ""},
    "bge": {
        "model": "BAAI/bge-base-en-v1.5",
        "q_prefix": "Represent this sentence for searching relevant passages: ",
        "p_prefix": "",
    },
}

_MODELS: Dict[str, object] = {}


def get_model(enc: str):
    """Load an encoder once per process (they are hundreds of MB)."""
    if enc not in _MODELS:
        from sentence_transformers import SentenceTransformer

        _MODELS[enc] = SentenceTransformer(ENCODERS[enc]["model"], device="cuda")
    return _MODELS[enc]


def clear_models() -> None:
    """Drop cached encoders so a caller can free GPU memory before generation.

    The 8 GB card cannot hold an encoder and the student model at once; a run
    that skips this stalls instead of failing (learned the hard way).
    """
    _MODELS.clear()
    try:
        import gc

        import torch

        gc.collect()
        torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001 - best-effort cleanup, never fatal
        pass


def encode(enc: str, texts: Sequence[str], is_query: bool) -> np.ndarray:
    """L2-normalised embeddings, with the encoder's own prefix convention applied."""
    pref = ENCODERS[enc]["q_prefix"] if is_query else ENCODERS[enc]["p_prefix"]
    txt = [pref + t for t in texts] if pref else list(texts)
    v = get_model(enc).encode(
        txt, normalize_embeddings=True, batch_size=128,
        show_progress_bar=False, convert_to_numpy=True,
    )
    return np.asarray(v, dtype="float32")


def load_data() -> Tuple[List[dict], List[dict], List[str], List[set]]:
    """Return (articles, qa, kb_ids, gold_id_sets), asserting the KB-only seal."""
    arts = [json.loads(l) for l in KB_PATH.open(encoding="utf-8")]
    qa = [json.loads(l) for l in QA_PATH.open(encoding="utf-8")]
    kb_ids = [a["id"] for a in arts]
    assert len(set(kb_ids)) == len(kb_ids), "duplicate KB ids"
    gold = [set(q.get("article_ids", [])) for q in qa]
    assert all(g and g <= set(kb_ids) for g in gold), "a gold id is missing from the KB"
    return arts, qa, kb_ids, gold


def chunks_of(article: dict) -> List[str]:
    """Split one article into overlapping, title-prefixed windows.

    The title leads every chunk because a mid-article chunk is otherwise
    context-free — the encoder cannot tell which product the steps belong to.
    """
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


def rank_articles_dense(enc: str, arts, qa, chunked: bool) -> List[List[str]]:
    """Per question, a ranked list of unique article ids, best first."""
    import faiss

    if chunked:
        chunk_texts, chunk_aid = [], []
        for a in arts:
            for c in chunks_of(a):
                chunk_texts.append(c)
                chunk_aid.append(a["id"])
        pv = encode(enc, chunk_texts, is_query=False)
        topm = RETRIEVE_CHUNKS
    else:
        whole = [((a.get("title") or "") + "\n" + (a.get("contents") or "")) for a in arts]
        pv = encode(enc, whole, is_query=False)
        chunk_aid = [a["id"] for a in arts]
        topm = 50

    index = faiss.IndexFlatIP(pv.shape[1])
    index.add(pv)
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
                seen.add(aid)
                order.append(aid)
        ranked.append(order)
    return ranked


_tok = re.compile(r"[a-z0-9]+")


def _toks(s: str) -> List[str]:
    return _tok.findall(s.lower())


def rank_articles_bm25(arts, qa) -> List[List[str]]:
    from rank_bm25 import BM25Okapi

    corpus = [_toks((a.get("title") or "") + " " + (a.get("contents") or "")) for a in arts]
    bm = BM25Okapi(corpus)
    aids = [a["id"] for a in arts]
    return [[aids[j] for j in np.argsort(-bm.get_scores(_toks(q["question"])))[:50]] for q in qa]


def rerank_cross(base_ranked, arts, qa, topn: int = 20,
                 model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> List[List[str]]:
    """Cross-encoder re-rank of the top-N of a dense ranking (no LLM generation).

    Scores (question, article) jointly and re-orders the head; the tail keeps its
    original order. bge_chunk reaches @10 = 0.845, so plenty of gold sits in ranks
    4-10 -- but at k=3 this trades precision for that recall and comes out level.
    """
    from sentence_transformers import CrossEncoder

    ce = CrossEncoder(model_name, device="cuda", max_length=512)
    aid2text = {
        a["id"]: ((a.get("title") or "") + ". " + (a.get("contents") or ""))[:2000] for a in arts
    }
    out = []
    for order, q in zip(base_ranked, qa):
        head = order[:topn]
        scores = ce.predict([(q["question"], aid2text[aid]) for aid in head],
                            batch_size=64, show_progress_bar=False)
        out.append([aid for _, aid in sorted(zip(scores, head), key=lambda x: -x[0])] + order[topn:])
    return out


def rrf(list_a, list_b, k0: int = 60, cutoff: int = 50) -> List[List[str]]:
    """Reciprocal-rank fusion of two per-question rankings (Cormack 2009)."""
    fused = []
    for ra, rb in zip(list_a, list_b):
        score: Dict[str, float] = {}
        for rank, aid in enumerate(ra):
            score[aid] = score.get(aid, 0.0) + 1.0 / (k0 + rank)
        for rank, aid in enumerate(rb):
            score[aid] = score.get(aid, 0.0) + 1.0 / (k0 + rank)
        fused.append([a for a, _ in sorted(score.items(), key=lambda x: -x[1])[:cutoff]])
    return fused


def hitrate(ranked, gold) -> Tuple[dict, List]:
    """hit@k for each k in KS, plus MRR and the rank of the first gold per question."""
    res = {k: sum(1 for order, g in zip(ranked, gold) if g & set(order[:k])) / len(gold) for k in KS}
    ranks = [next((i + 1 for i, aid in enumerate(order) if aid in g), None)
             for order, g in zip(ranked, gold)]
    found = [r for r in ranks if r is not None]
    res["mrr"] = float(np.mean([1.0 / r for r in found] + [0.0] * (len(gold) - len(found))))
    return res, ranks


#: The retriever variants compared offline, in ranked order.
VARIANT_NAMES = [
    "minilm_whole", "minilm_chunk", "bge_whole", "bge_chunk",
    "bm25", "hybrid_rrf", "bge_chunk_rerank",
]


def build_ranked(name: str, arts, qa, cache: Dict[str, List[List[str]]] | None = None):
    """Build one variant's ranking. `cache` lets composite variants reuse a base.

    Returns a ranking, or (ranking, dense_variant_used) for `hybrid_rrf` so the
    caller can report which dense retriever it fused with.
    """
    cache = {} if cache is None else cache
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
        dense = cache.get("bge_chunk") or rank_articles_dense("bge", arts, qa, chunked=True)
        cache["bge_chunk"] = dense
        return rerank_cross(dense, arts, qa)
    if name == "hybrid_rrf":
        dense_name = ("bge_chunk" if "bge_chunk" in cache
                      else "minilm_chunk" if "minilm_chunk" in cache else "minilm_whole")
        dense = cache.get(dense_name) or build_ranked(dense_name, arts, qa, cache)
        cache[dense_name] = dense
        bm = cache.get("bm25") or rank_articles_bm25(arts, qa)
        cache["bm25"] = bm
        return rrf(bm, dense), dense_name
    raise ValueError(f"unknown retriever variant {name!r}; known: {VARIANT_NAMES}")


def retrieval_record(idx: int, question: str, gold_ids, retrieved_ids, sims) -> dict:
    """The per-question hit-rate instrument, seed-independent.

    Retrieval is a deterministic embedding lookup, so this record is identical
    across seeds — which is what lets the analysis split any run by whether the
    answer-bearing article was actually found, the split that proved the law.
    `gold_rank` is 1-based, or -1 when no gold article was retrieved.
    """
    gold_set = set(gold_ids)
    gold_rank = -1
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in gold_set:
            gold_rank = rank
            break
    return {
        "idx": idx,
        "question": question,
        "gold_article_ids": list(gold_ids),
        "retrieved_ids": list(retrieved_ids),
        "sims": sims,
        "gold_rank": gold_rank,
        "gold_retrieved": gold_rank != -1,
        "top_sim": sims[0] if sims else None,
    }


__all__ = [
    "KS", "CHUNK_WORDS", "OVERLAP", "RETRIEVE_CHUNKS", "ENCODERS", "VARIANT_NAMES",
    "get_model", "clear_models", "encode", "load_data", "chunks_of",
    "rank_articles_dense", "rank_articles_bm25", "rerank_cross", "rrf",
    "hitrate", "build_ranked", "retrieval_record",
]
