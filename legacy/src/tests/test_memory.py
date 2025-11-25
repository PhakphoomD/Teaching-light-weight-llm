"""
Memory Module Tests

Unit tests for MemoryStore, VectorIndex, and Summarizer components.
"""

import os
import sys
from pathlib import Path
import tempfile
import shutil
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.memory.store import MemoryStore
from src.memory.vector import VectorIndex
from src.memory.summarizer import (
    summarize_records,
    forget_old_records,
    merge_similar_records,
    get_memory_stats
)


def test_memory_store():
    """Test MemoryStore save and load operations."""
    print("\n=== Test 1: MemoryStore ===")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        store_path = Path(tmp_dir) / "test_store.jsonl"
        store = MemoryStore(file_path=str(store_path))
        
        # Test 1: Save records
        print("Test 1.1: Saving records...")
        record1 = {
            "question": "What is the capital of France?",
            "initial_answer": "I think it's Paris",
            "feedbacks": ["Correct! Paris is the capital."],
            "refined_answer": "Paris",
            "error_type": None,
            "meta": {"round": 1}
        }
        
        record2 = {
            "question": "What is 2+2?",
            "initial_answer": "5",
            "feedbacks": ["Incorrect. Try again.", "Think about basic addition."],
            "refined_answer": "4",
            "error_type": "calculation_error",
            "meta": {"round": 2}
        }
        
        store.save_record(record1)
        store.save_record(record2)
        print("  Saved 2 records")
        
        # Test 2: Load all records
        print("Test 1.2: Loading all records...")
        records = list(store.load_records())
        assert len(records) == 2, f"Expected 2 records, got {len(records)}"
        print(f"  Loaded {len(records)} records")
        
        # Test 3: Load with filter
        print("Test 1.3: Loading with filter...")
        error_records = list(store.load_records(
            filter_fn=lambda r: r.get("error_type") is not None
        ))
        assert len(error_records) == 1, f"Expected 1 error record, got {len(error_records)}"
        assert error_records[0]["question"] == "What is 2+2?"
        print(f"  Filtered to {len(error_records)} error records")
        
        # Test 4: Count records
        print("Test 1.4: Counting records...")
        count = store.count_records()
        assert count == 2, f"Expected count=2, got {count}"
        print(f"  Total count: {count}")
        
        # Test 5: Get by ID
        print("Test 1.5: Get record by ID...")
        first_record = records[0]
        rec_id = first_record["id"]
        retrieved = store.get_record_by_id(rec_id)
        assert retrieved is not None, "Failed to retrieve record by ID"
        assert retrieved["question"] == first_record["question"]
        print(f"  Retrieved record by ID: {rec_id}")
        
        # Test 6: Get stats
        print("Test 1.6: Getting stats...")
        stats = store.get_stats()
        assert stats["total_records"] == 2
        print(f"  Stats: {stats}")
        
        print("[OK] All MemoryStore tests passed!")


def test_vector_index():
    """Test VectorIndex add and retrieve operations."""
    print("\n=== Test 2: VectorIndex ===")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        index_path = Path(tmp_dir) / "test_index.faiss"
        
        print("Test 2.1: Initializing VectorIndex...")
        # Use a small model for faster testing
        index = VectorIndex(
            embedding_model="all-MiniLM-L6-v2",
            index_path=str(index_path)
        )
        print(f"  Index initialized with dim={index.dim}")
        
        # Test 2: Add records
        print("Test 2.2: Adding records...")
        texts = [
            "Paris is the capital of France",
            "London is the capital of the United Kingdom",
            "Berlin is the capital of Germany",
            "Madrid is the capital of Spain",
            "Rome is the capital of Italy"
        ]
        
        for i, text in enumerate(texts):
            rec_id = f"rec_{i+1}"
            index.add_record(rec_id, text)
        
        print(f"  Added {len(texts)} records")
        
        # Test 3: Retrieve similar records
        print("Test 2.3: Retrieving similar records...")
        
        # Query about France - should return Paris record
        query1 = "What is the capital of France?"
        results1 = index.retrieve(query1, k=3)
        print(f"Query: '{query1}'")
        print(f"Top results: {results1}")
        
        # rec_1 (Paris) should be top result
        assert "rec_1" in results1, "Expected rec_1 (Paris) in results"
        assert results1[0] == "rec_1", "Expected rec_1 to be top result"
        print("  Correct record retrieved")
        
        # Test 4: Retrieve with scores
        print("Test 2.4: Retrieving with scores...")
        results_with_scores = index.retrieve_with_scores(query1, k=3)
        print(f"Results with scores: {results_with_scores}")
        
        assert len(results_with_scores) == 3
        assert results_with_scores[0][0] == "rec_1"
        assert results_with_scores[0][1] > 0.5, "Expected high similarity score"
        print(f"  Top score: {results_with_scores[0][1]:.3f}")
        
        # Test 5: Test another query
        print("Test 2.5: Testing another query...")
        query2 = "German capital city"
        results2 = index.retrieve(query2, k=2)
        print(f"Query: '{query2}'")
        print(f"Top results: {results2}")
        
        # rec_3 (Berlin) should be top result
        assert "rec_3" in results2, "Expected rec_3 (Berlin) in results"
        print("  Correct record retrieved")
        
        # Test 6: Get stats
        print("Test 2.6: Getting index stats...")
        stats = index.get_stats()
        print(f"Stats: {stats}")
        assert stats["total_vectors"] == 5
        assert stats["dimension"] == index.dim
        print("  Stats correct")
        
        print("[OK] All VectorIndex tests passed!")


def test_summarizer():
    """Test summarization functions."""
    print("\n=== Test 3: Summarizer ===")
    
    # Create test records
    now = datetime.now()
    old_time = (now - timedelta(days=10)).isoformat()
    recent_time = (now - timedelta(days=2)).isoformat()
    
    records = [
        {
            "id": "r1",
            "question": "What is the capital of France?",
            "initial_answer": "Paris",
            "refined_answer": "Paris is the capital of France.",
            "feedbacks": ["Correct!"],
            "timestamp": old_time,
            "error_type": None,
            "meta": {}
        },
        {
            "id": "r2",
            "question": "What is 2+2?",
            "initial_answer": "5",
            "refined_answer": "4",
            "feedbacks": ["Incorrect", "Try again"],
            "timestamp": recent_time,
            "error_type": "calculation_error",
            "meta": {}
        },
        {
            "id": "r3",
            "question": "What is the capital of UK?",
            "initial_answer": "London",
            "refined_answer": "London is the capital of the United Kingdom.",
            "feedbacks": ["Correct!"],
            "timestamp": recent_time,
            "error_type": None,
            "meta": {}
        }
    ]
    
    # Test 1: Summarize with concat
    print("Test 3.1: Summarize (concat method)...")
    summary_concat = summarize_records(records, method="concat")
    print(f"Summary: {summary_concat[:100]}...")
    assert len(summary_concat) > 0
    assert "Paris" in summary_concat or "France" in summary_concat
    print("  Concat summary generated")
    
    # Test 2: Summarize with bullets
    print("Test 3.2: Summarize (bullets method)...")
    summary_bullets = summarize_records(records, method="bullets")
    print(f"Summary:\n{summary_bullets}")
    assert " " in summary_bullets
    assert "\n" in summary_bullets  # Multi-line
    print("  Bullet summary generated")
    
    # Test 3: Forget old records
    print("Test 3.3: Forget old records...")
    kept = forget_old_records(records, days=7)
    print(f"Before: {len(records)} records")
    print(f"After: {len(kept)} records")
    
    # Should keep r2 and r3 (recent), forget r1 (old)
    assert len(kept) == 2, f"Expected 2 records, got {len(kept)}"
    kept_ids = [r["id"] for r in kept]
    assert "r2" in kept_ids
    assert "r3" in kept_ids
    assert "r1" not in kept_ids
    print("  Old records forgotten")
    
    # Test 4: Keep important records
    print("Test 3.4: Keep important records...")
    records[0]["meta"]["important"] = True  # Mark r1 as important
    kept_important = forget_old_records(records, days=7, keep_important=True)
    print(f"Kept {len(kept_important)} records (including important)")
    
    # Should keep all 3 (r1 is important)
    assert len(kept_important) == 3
    print("  Important records kept")
    
    # Test 5: Merge similar records
    print("Test 3.5: Merge similar records...")
    duplicate_records = records + [
        {
            "id": "r4",
            "question": "What is the capital of France?",  # Duplicate
            "initial_answer": "Paris",
            "refined_answer": "Paris",
            "feedbacks": [],
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "error_type": None,
            "meta": {}
        }
    ]
    
    merged = merge_similar_records(duplicate_records)
    print(f"Before merge: {len(duplicate_records)} records")
    print(f"After merge: {len(merged)} records")
    
    # Should merge r1 and r4 (same question), keep r4 (more recent)
    assert len(merged) == 3  # r4, r2, r3
    print("  Similar records merged")
    
    # Test 6: Get memory stats
    print("Test 3.6: Get memory stats...")
    stats = get_memory_stats(records)
    print(f"Stats: {stats}")
    
    assert stats["total_records"] == 3
    assert stats["date_range"][0] is not None
    assert stats["date_range"][1] is not None
    assert "error_types" in stats
    assert stats["error_types"]["calculation_error"] == 1
    print("  Stats computed correctly")
    
    print("[OK] All Summarizer tests passed!")


def test_integration():
    """Integration test: Store + Vector + Summarizer."""
    print("\n=== Test 4: Integration Test ===")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Setup
        store_path = Path(tmp_dir) / "store.jsonl"
        index_path = Path(tmp_dir) / "index.faiss"
        
        store = MemoryStore(file_path=str(store_path))
        index = VectorIndex(
            embedding_model="all-MiniLM-L6-v2",
            index_path=str(index_path)
        )
        
        print("Test 4.1: Save and index records...")
        
        # Create teaching records
        qa_pairs = [
            ("What is the capital of France?", "Paris"),
            ("What is the capital of UK?", "London"),
            ("What is 2+2?", "4"),
            ("What is the largest planet?", "Jupiter"),
        ]
        
        saved_ids = []
        for question, answer in qa_pairs:
            record = {
                "question": question,
                "initial_answer": answer,
                "refined_answer": answer,
                "feedbacks": ["Good answer"],
                "error_type": None,
                "meta": {"round": 1}
            }
            
            # Save to store
            store.save_record(record)
            
            # Get the ID (last saved)
            records = list(store.load_records())
            rec_id = records[-1]["id"]
            saved_ids.append(rec_id)
            
            # Add to vector index
            text = f"{question} {answer}"
            index.add_record(rec_id, text)
        
        print(f"  Saved and indexed {len(qa_pairs)} records")
        
        print("Test 4.2: Retrieve and load...")
        
        # Query for similar records
        query = "French capital"
        similar_ids = index.retrieve(query, k=2)
        print(f"Query: '{query}'")
        print(f"Similar IDs: {similar_ids}")
        
        # Load the records from store
        similar_records = []
        for rec_id in similar_ids:
            rec = store.get_record_by_id(rec_id)
            if rec:
                similar_records.append(rec)
        
        print(f"  Retrieved {len(similar_records)} similar records")
        assert len(similar_records) > 0
        
        # First result should be about France
        assert "France" in similar_records[0]["question"]
        print(f"  Top result: {similar_records[0]['question']}")
        
        print("Test 4.3: Summarize retrieved records...")
        
        summary = summarize_records(similar_records, method="bullets")
        print(f"Summary:\n{summary}")
        assert "Paris" in summary or "France" in summary
        print("  Summary generated")
        
        print("[OK] Integration test passed!")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("MEMORY MODULE TESTS")
    print("="*60)
    
    try:
        test_memory_store()
        test_vector_index()
        test_summarizer()
        test_integration()
        
        print("\n" + "="*60)
        print("[OK] ALL TESTS PASSED!")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
