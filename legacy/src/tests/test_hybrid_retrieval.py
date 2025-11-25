#!/usr/bin/env python3
"""
Test HYBRID retrieval approach:
1. Hard filter by task_type (exact match)
2. Soft ranking by semantic similarity (within same task)

This guarantees 100% same-task retrieval.
"""

import importlib.util
import os
import sys

# Import task classifier directly
spec = importlib.util.spec_from_file_location(
    "task_classifier",
    os.path.join(os.path.dirname(__file__), 'src', 'refinement', 'memory', 'plugins', 'task_classifier.py')
)
task_classifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task_classifier)
extract_task_type = task_classifier.extract_task_type


def test_hybrid_approach():
    """Test that hybrid filtering works correctly."""
    
    print("="*80)
    print("HYBRID RETRIEVAL APPROACH TEST")
    print("="*80)
    
    # Simulate memory records with different task types
    memory_records = [
        {"id": "q1", "question": "Name 5 adventure sports", "task_type": "list_generation", "hint": "Think of extreme activities"},
        {"id": "q2", "question": "Name 3 subjects", "task_type": "list_generation", "hint": "Academic subjects"},
        {"id": "q3", "question": "List 10 countries", "task_type": "list_generation", "hint": "Think globally"},
        {"id": "q4", "question": "Split: Iamadoglover", "task_type": "text_splitting", "hint": "Look for capital letters"},
        {"id": "q5", "question": "Split: helloworld", "task_type": "text_splitting", "hint": "Find word boundaries"},
        {"id": "q6", "question": "Define: Algorithm", "task_type": "definition", "hint": "Step-by-step procedure"},
        {"id": "q7", "question": "Calculate 15% of 200", "task_type": "math_problem", "hint": "Use multiplication"},
    ]
    
    # Test queries
    test_queries = [
        "Name 8 countries in Asia",  # Should match list_generation only
        "Split: Javascriptisfun",     # Should match text_splitting only
        "Define: Photosynthesis",     # Should match definition only
        "Calculate 20% of 500",       # Should match math_problem only
    ]
    
    print("\n" + "="*80)
    print("STEP 1: Extract task types for queries")
    print("="*80)
    
    for query in test_queries:
        task_type, confidence = extract_task_type(query)
        print(f"\nQuery: {query}")
        print(f"  -> Task Type: {task_type} (confidence: {confidence})")
    
    print("\n" + "="*80)
    print("STEP 2: Simulate hybrid retrieval (filter + similarity)")
    print("="*80)
    
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print(f"{'='*80}")
        
        # Extract task type
        task_type, confidence = extract_task_type(query)
        print(f"Task Type: {task_type}")
        
        # HARD FILTER: Only same task type
        filtered = [rec for rec in memory_records if rec["task_type"] == task_type]
        
        print(f"\nFiltered Records ({len(filtered)}/{len(memory_records)}):")
        for rec in filtered:
            print(f"  - {rec['id']}: {rec['question']}")
        
        if not filtered:
            print("  [NO MATCHES - Would return empty context]")
        else:
            print(f"\n  [SUCCESS] Found {len(filtered)} same-task examples!")
            print(f"  Next step: Rank by similarity within these {len(filtered)} records")
    
    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)
    print("[HYBRID APPROACH BENEFITS]")
    print("  1. 100% guarantee same task type (hard filter)")
    print("  2. Best similarity ranking within same task (soft ranking)")
    print("  3. No need for task_type in embedding (simpler, faster)")
    print("  4. Handles edge cases (no same-task records -> empty context)")
    print("\n[ACCURACY]")
    print("  Task type classification: Fast regex (high confidence)")
    print("  Same-task filtering: Exact string match (100% accurate)")
    print("  Similarity ranking: Semantic search (within safe subset)")


if __name__ == "__main__":
    test_hybrid_approach()
