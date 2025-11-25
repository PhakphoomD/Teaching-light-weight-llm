from pathlib import Path

from src.refinement.memory.plugins.store import MemoryStore
from src.refinement.memory.plugins.vector_index import VectorIndex
from src.refinement.memory.plugins.storage import StoragePlugin
from src.refinement.student.plugins.memory_retrieval import MemoryRetrievalPlugin


def seed_record(store: MemoryStore, index: VectorIndex, question: str, hint: str):
    sp = StoragePlugin(store, index)
    eval = {"evaluation": "incorrect", "reasoning": "", "hint": hint, "stop_score": 0.7, "error_keys": []}
    sp.save(question, "", eval)


def test_retrieval_structure_pipeline(tmp_path: Path):
    store_path = tmp_path / "store.jsonl"
    index_path = tmp_path / "faiss.index"
    store = MemoryStore(str(store_path))
    index = VectorIndex(embedding_model="all-MiniLM-L6-v2", index_path=str(index_path), dim=384)

    # Seed several compact cases
    seed_record(store, index, "Name 5 sports", "When listing n items, use numbered bullets.")
    seed_record(store, index, "List 10 numbered items", "Output exactly n items with numbers.")
    seed_record(store, index, "Calculate 15% of 200", "Use percentage formula: n% of x = ...")
    seed_record(store, index, "Split sentence: hello world", "Split by words, not characters.")

    retr = MemoryRetrievalPlugin(store, index)
    context, ids, stats = retr.retrieve_with_stats("List 3 numbered fruits")
    assert isinstance(context, str)
    assert isinstance(ids, list)
    assert "Task:" in context and "Structure:" in context
    assert stats.get("after_task", 0) >= stats.get("used", 0)
    # ensure max lines
    assert context.count("- ") <= 6 + 3  # include Important section bullets

