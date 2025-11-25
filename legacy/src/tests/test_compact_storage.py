import json
from pathlib import Path

from src.refinement.memory.plugins.store import MemoryStore
from src.refinement.memory.plugins.vector_index import VectorIndex
from src.refinement.memory.plugins.storage import StoragePlugin


def test_compact_storage(tmp_path: Path):
    store_path = tmp_path / "store.jsonl"
    index_path = tmp_path / "faiss.index"

    store = MemoryStore(str(store_path))
    index = VectorIndex(embedding_model="all-MiniLM-L6-v2", index_path=str(index_path), dim=384)
    plugin = StoragePlugin(store, index)

    evaluation = {
        "evaluation": "incorrect",
        "reasoning": "...",
        "hint": "When listing 5 items, use numbered bullets.",
        "stop_score": 1.2,  # will be clamped
        "error_keys": ["format"],
    }

    plugin.save("Name 5 sports", "bad answer", evaluation)

    # Read last line
    lines = list(store.load_records())
    assert lines, "no records saved"
    rec = lines[-1]
    assert rec.get("schema_version") == "mem.v1"
    # no question/answer content
    assert "question" not in rec and "answer" not in rec
    # clamp
    assert 0.0 <= float(rec.get("stop_score", 0.0)) <= 1.0
    # rule length
    assert len(rec.get("semantic_rule", "")) <= 153

