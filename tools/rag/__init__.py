"""RAG retrieval-corpus tooling (ADR-026).

A reusable, config-driven block: point the builder at any `data/clean/*.jsonl`
to produce a FAISS retrieval index for that domain (the Lego-block rule —
swapping domain = re-point the source, not rewrite code). Reuses the project
MiniLM encoder and the same FAISS IndexFlatIP construction as
`src/tlw/memory/faiss_backend.py`; consumed at run time by the slot-D `rag`
backend.
"""

from tools.rag.builder import RagIndexBuilder, BuildReport

__all__ = ["RagIndexBuilder", "BuildReport"]
