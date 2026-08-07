"""Memory block v2 (T2.5) — MemoryBackend implementations for slot D.

Importing this package registers the real 'faiss' backend into
`src.tlw.registries.MEMORY_REGISTRY` (mirrors how `none` is registered
directly in registries.py, T2.2). The runner (T2.6) must `import src.tlw.memory`
(or `from src.tlw.memory import FaissMemory`) before resolving `memory.type`
from config, exactly like it must import any other registry-populating module.
"""

from src.tlw.memory.faiss_backend import FaissMemory  # noqa: F401  (registers "faiss")
from src.tlw.memory.rag_backend import RagMemory  # noqa: F401  (registers "rag", T3.3)

__all__ = ["FaissMemory", "RagMemory"]
