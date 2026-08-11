"""RagMemory — slot D 'rag' backend (rag-medquad-protocol §2 / schema.md slot-D rag).

The third MemoryBackend implementation: a corpus-backed, READ-ONLY retriever
over a prebuilt index (`tools/rag/`). It satisfies the SAME seam as
`faiss`/`none` (`store`/`retrieve`/`update_outcome`/`stats`, registries.py) so
the runner is unchanged — but it differs on three points (schema.md slot-D rag):
  - payload = domain PASSAGES (train answers), not run-written teaching notes
  - `store()` / `update_outcome()` are no-ops (the corpus is immutable at run time)
  - `grounds_first_attempt = True` -> the loop injects its passages into the
    FIRST answer attempt (grounding = knowledge, useful up front), whereas
    `faiss` notes are refinement-only (Memory v2 §3).

Anti-leak (rag-medquad-protocol §5): the corpus was built held-out-free at index time
(RAG-L1 id exclusion + RAG-L2 near-dup scrub, `tools/rag/builder.py`). The
run-time guard RAG-L3 (`assert_gt_free` on the grounded student prompt vs the
held-out gold answer, `src/tlw/loop/core.py`) is the last line of defence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from src.tlw.registries import MEMORY_REGISTRY, MemoryBackend

# Aspect-aware rerank (aspect-aware reranking): MiniLM retrieval is disease-name-
# dominated, so "treatments for X" retrieves "symptoms of X" (90% wrong aspect,
# measured). Classifying the query/passage ASPECT and keeping only same-aspect
# passages fixes it (corpus coverage verified at 99%). Order matters (specific
# before generic 'what is').
_ASPECT_PATTERNS = [
    (re.compile(r"treatment|therap", re.I), "treatment"),
    (re.compile(r"symptom", re.I), "symptom"),
    (re.compile(r"\bcause", re.I), "cause"),
    (re.compile(r"diagnos", re.I), "diagnosis"),
    (re.compile(r"prevent", re.I), "prevention"),
    (re.compile(r"how many|affected|how common", re.I), "epidemiology"),
    (re.compile(r"who is at risk|risk for", re.I), "risk"),
    (re.compile(r"what to do|living with|manage", re.I), "management"),
    (re.compile(r"complication", re.I), "complication"),
    (re.compile(r"what (is|are)", re.I), "definition"),
]


def _aspect(question: str) -> str:
    for pat, name in _ASPECT_PATTERNS:
        if pat.search(question or ""):
            return name
    return "other"


@MEMORY_REGISTRY.register("rag")
class RagMemory(MemoryBackend):
    """Read-only retrieval over a `tools/rag/` index directory (faiss.index +
    passages.jsonl). Domain-agnostic: point `corpus_path` at any built index."""

    #: Read by the loop (`src/tlw/loop/core.py::grounding_block`) — RAG passages
    #: enter the first answer attempt; `none`/`faiss` lack this attr -> False.
    grounds_first_attempt = True

    def __init__(
        self,
        corpus_path: Optional[str] = None,
        embedding: str = "minilm",
        top_k: int = 3,
        similarity_threshold: float = 0.35,
        aspect_rerank: bool = False,
        **_ignored: Any,
    ):
        self.aspect_rerank = aspect_rerank
        if not corpus_path:
            raise ValueError(
                "RagMemory requires corpus_path (a `tools/rag/` index dir) — "
                "set memory.corpus_path in the experiment config (rag-medquad-protocol §2)."
            )
        self.corpus_dir = Path(corpus_path)
        if not self.corpus_dir.exists():
            raise FileNotFoundError(
                f"RAG corpus_path does not exist: {self.corpus_dir} "
                "(build it first with `python -m tools.rag.cli`, T3.2)."
            )
        self.embedding = embedding
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

        self.index_path = self.corpus_dir / "faiss.index"
        self.passages_path = self.corpus_dir / "passages.jsonl"

        self._index = None
        self._passages: List[Dict[str, Any]] = []
        self._loaded = False

    # --- lazy load (mirrors faiss_backend's lazy heavy deps) ---

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        import faiss

        if not self.index_path.exists() or not self.passages_path.exists():
            raise FileNotFoundError(
                f"RAG corpus at {self.corpus_dir} is missing faiss.index or "
                "passages.jsonl (rebuild with `python -m tools.rag.cli`)."
            )
        self._index = faiss.read_index(str(self.index_path))
        with open(self.passages_path, "r", encoding="utf-8") as f:
            self._passages = [json.loads(line) for line in f if line.strip()]
        if self._index.ntotal != len(self._passages):
            raise ValueError(
                f"RAG corpus inconsistent: index has {self._index.ntotal} vectors "
                f"but passages.jsonl has {len(self._passages)} rows ({self.corpus_dir})."
            )
        self._loaded = True

    def _embed(self, text: str) -> np.ndarray:
        from tools.dataset.embeddings import embed

        return embed([text]).astype("float32")  # (1, d), L2-normalized

    # --- MemoryBackend interface ---

    def store(self, episode: Dict[str, Any], reference_answer: Any = None) -> None:
        """No-op: the RAG corpus is prebuilt, read-only knowledge — a run never
        writes into it (schema.md slot-D rag). Returns None like a rejected store."""
        return None

    def retrieve(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Top-k passages for `query`, filtered by the similarity floor
        (rag-medquad-protocol §1.3). Empty is normal (no train neighbour cleared the floor)
        -> the student answers un-grounded for that question."""
        self._ensure_loaded()
        k = top_k if top_k is not None else self.top_k
        if k <= 0 or self._index.ntotal == 0:
            return []
        qvec = self._embed(query)
        # With aspect rerank, search a LARGER pool so same-aspect passages (which
        # the disease-name-dominated embedding ranks below the wrong-aspect twin)
        # can surface; then filter. Without it, behaviour is unchanged (top-k).
        pool = min(max(k, 20) if self.aspect_rerank else k, self._index.ntotal)
        scores, idxs = self._index.search(qvec, pool)
        cands: List[Dict[str, Any]] = []
        for row, sim in zip(idxs[0], scores[0]):
            if row < 0 or row >= len(self._passages):
                continue
            if float(sim) < self.similarity_threshold:
                continue
            p = self._passages[int(row)]
            cands.append(
                {
                    "id": p.get("id"),
                    "passage": p.get("passage"),
                    "question": p.get("question"),
                    "similarity": round(float(sim), 4),
                    "source_id": p.get("source_id"),
                }
            )
        if self.aspect_rerank:
            aq = _aspect(query)
            same = [c for c in cands if _aspect(c["question"]) == aq]
            # ground ONLY on same-aspect passages; if none exist, return nothing
            # (better un-grounded than grounded on the wrong aspect, FLAW-2).
            cands = same
        return cands[:k]

    def update_outcome(self, episode_id: str, scores: Dict[str, float]) -> None:
        """No-op: nothing is learned into a read-only corpus."""
        return None

    def stats(self) -> Dict[str, Any]:
        corpus_size = 0
        index_size = 0
        try:
            self._ensure_loaded()
            corpus_size = len(self._passages)
            index_size = self._index.ntotal
        except (FileNotFoundError, ValueError):
            pass
        return {
            "backend": "rag",
            "corpus_path": str(self.corpus_dir),
            "corpus_size": corpus_size,
            "index_size": index_size,
            "similarity_threshold": self.similarity_threshold,
        }
