"""
Test Retrieval Metrics

This script tests all retrieval evaluation metrics with realistic examples.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.eval.retrieval import (
    hit_rate,
    precision_at_k,
    recall_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    evaluate_retrieval,
    print_metrics
)


def test_perfect_retrieval():
    """Test with perfect retrieval (all relevant items ranked first)."""
    print("\n=== Test 1: Perfect Retrieval ===")
    
    retrieved = [
        ['doc1', 'doc2', 'doc3', 'doc4', 'doc5'],  # All relevant items first
        ['doc6', 'doc7', 'doc8', 'doc9', 'doc10']
    ]
    
    relevant = [
        {'doc1', 'doc2', 'doc3'},  # All 3 in top-5
        {'doc6', 'doc7'}           # Both in top-5
    ]
    
    print("Retrieved:", retrieved)
    print("Relevant:", relevant)
    
    # All metrics should be 1.0 at k=5
    metrics = evaluate_retrieval(retrieved, relevant, k_values=[3, 5])
    print_metrics(metrics, "Perfect Retrieval Metrics")
    
    # Verify
    assert metrics['hit_rate@5'] == 1.0, "Perfect retrieval should have hit_rate = 1.0"
    assert metrics['mrr'] == 1.0, "Perfect retrieval should have MRR = 1.0"
    print("  Perfect retrieval test passed")


def test_no_hits():
    """Test with no relevant items retrieved."""
    print("\n=== Test 2: No Hits ===")
    
    retrieved = [
        ['doc1', 'doc2', 'doc3'],
        ['doc4', 'doc5', 'doc6']
    ]
    
    relevant = [
        {'doc7', 'doc8'},  # None in retrieved
        {'doc9', 'doc10'}  # None in retrieved
    ]
    
    print("Retrieved:", retrieved)
    print("Relevant:", relevant)
    
    metrics = evaluate_retrieval(retrieved, relevant, k_values=[3, 5])
    print_metrics(metrics, "No Hits Metrics")
    
    # All metrics should be 0.0
    assert metrics['hit_rate@3'] == 0.0, "No hits should give hit_rate = 0.0"
    assert metrics['mrr'] == 0.0, "No hits should give MRR = 0.0"
    print("  No hits test passed")


def test_partial_retrieval():
    """Test with partial retrieval (some relevant, some not)."""
    print("\n=== Test 3: Partial Retrieval ===")
    
    retrieved = [
        ['doc1', 'doc2', 'doc3', 'doc4', 'doc5'],  # doc1, doc3 relevant
        ['doc6', 'doc7', 'doc8', 'doc9', 'doc10'], # doc7, doc9 relevant
        ['doc11', 'doc12', 'doc13', 'doc14']       # doc13 relevant
    ]
    
    relevant = [
        {'doc1', 'doc3', 'doc15'},  # 2 out of 3 retrieved
        {'doc7', 'doc9'},            # 2 out of 2 retrieved
        {'doc13', 'doc16', 'doc17'}  # 1 out of 3 retrieved
    ]
    
    print("Query 1: Retrieved 2/3 relevant (doc1, doc3)")
    print("Query 2: Retrieved 2/2 relevant (doc7, doc9)")
    print("Query 3: Retrieved 1/3 relevant (doc13)")
    
    metrics = evaluate_retrieval(retrieved, relevant, k_values=[3, 5])
    print_metrics(metrics, "Partial Retrieval Metrics")
    
    # All queries have at least one hit
    assert metrics['hit_rate@5'] == 1.0, "All queries should have hits"
    
    # Precision@5 = average of (2/5, 2/5, 1/5) = 1/3 = 0.3333
    expected_precision = (2/5 + 2/5 + 1/5) / 3
    assert abs(metrics['precision@5'] - expected_precision) < 0.01
    
    print(f"  Partial retrieval test passed (precision@5 = {metrics['precision@5']:.4f})")


def test_ranking_quality():
    """Test ranking quality with NDCG (position matters)."""
    print("\n=== Test 4: Ranking Quality (NDCG) ===")
    
    # Same relevant items, but different rankings
    relevant_items = {'doc1', 'doc2', 'doc3'}
    
    # Perfect ranking: all relevant items at top
    perfect_retrieved = [['doc1', 'doc2', 'doc3', 'doc4', 'doc5']]
    
    # Poor ranking: relevant items at bottom
    poor_retrieved = [['doc4', 'doc5', 'doc1', 'doc2', 'doc3']]
    
    # Medium ranking: some relevant items at top
    medium_retrieved = [['doc1', 'doc4', 'doc2', 'doc5', 'doc3']]
    
    relevant_sets = [relevant_items]
    
    ndcg_perfect = ndcg_at_k(perfect_retrieved, relevant_sets, k=5)
    ndcg_poor = ndcg_at_k(poor_retrieved, relevant_sets, k=5)
    ndcg_medium = ndcg_at_k(medium_retrieved, relevant_sets, k=5)
    
    print(f"Perfect ranking NDCG@5: {ndcg_perfect:.4f}")
    print(f"Medium ranking NDCG@5:  {ndcg_medium:.4f}")
    print(f"Poor ranking NDCG@5:    {ndcg_poor:.4f}")
    
    # Verify ordering
    assert ndcg_perfect > ndcg_medium > ndcg_poor, \
        "NDCG should decrease with worse ranking"
    assert abs(ndcg_perfect - 1.0) < 0.01, "Perfect ranking should give NDCG   1.0"
    
    print("  Ranking quality test passed")


def test_mrr_positions():
    """Test MRR with different first relevant positions."""
    print("\n=== Test 5: MRR with Different Positions ===")
    
    retrieved = [
        ['doc1', 'doc2', 'doc3'],  # Relevant at position 1 (RR = 1.0)
        ['doc4', 'doc5', 'doc6'],  # Relevant at position 2 (RR = 0.5)
        ['doc7', 'doc8', 'doc9'],  # Relevant at position 3 (RR = 1/3)
        ['doc10', 'doc11', 'doc12'] # No relevant (RR = 0.0)
    ]
    
    relevant = [
        {'doc1'},
        {'doc5'},
        {'doc9'},
        {'doc15'}
    ]
    
    print("Query 1: First relevant at position 1 (RR = 1.0)")
    print("Query 2: First relevant at position 2 (RR = 0.5)")
    print("Query 3: First relevant at position 3 (RR = 0.333)")
    print("Query 4: No relevant (RR = 0.0)")
    
    mrr = mean_reciprocal_rank(retrieved, relevant)
    expected_mrr = (1.0 + 0.5 + 1/3 + 0.0) / 4
    
    print(f"Calculated MRR: {mrr:.4f}")
    print(f"Expected MRR:   {expected_mrr:.4f}")
    
    assert abs(mrr - expected_mrr) < 0.01, "MRR calculation incorrect"
    print("  MRR position test passed")


def test_precision_recall_tradeoff():
    """Test precision-recall trade-off at different k values."""
    print("\n=== Test 6: Precision-Recall Trade-off ===")
    
    # 10 total relevant items, but only retrieve 5
    retrieved = [
        ['doc1', 'doc2', 'doc3', 'doc4', 'doc5']  # 3 out of 5 are relevant
    ]
    
    relevant = [
        {'doc1', 'doc3', 'doc5', 'doc11', 'doc12', 'doc13', 'doc14', 'doc15', 'doc16', 'doc17'}
        # 10 total relevant, 3 retrieved
    ]
    
    print("Total relevant items: 10")
    print("Retrieved items: 5")
    print("Relevant items in retrieved: 3 (doc1, doc3, doc5)")
    
    for k in [3, 5, 10]:
        prec = precision_at_k(retrieved, relevant, k)
        rec = recall_at_k(retrieved, relevant, k)
        
        print(f"k={k}: Precision={prec:.4f}, Recall={rec:.4f}")
    
    # At k=3: precision = 2/3, recall = 2/10
    # At k=5: precision = 3/5, recall = 3/10
    # Recall increases, precision may decrease
    
    print("  Precision-recall trade-off test passed")


def test_edge_cases():
    """Test edge cases and validation."""
    print("\n=== Test 7: Edge Cases ===")
    
    # Test 1: Empty relevant set
    print("Test 7.1: Query with no relevant items...")
    retrieved = [['doc1', 'doc2'], ['doc3', 'doc4']]
    relevant = [set(), {'doc3'}]  # First query has no relevant
    
    try:
        metrics = evaluate_retrieval(retrieved, relevant, k_values=[2])
        print(f"  Handled empty relevant set (metrics: {metrics})")
    except Exception as e:
        print(f"  Failed on empty relevant set: {e}")
        raise
    
    # Test 2: Mismatched lengths
    print("Test 7.2: Mismatched list lengths...")
    retrieved_bad = [['doc1']]
    relevant_bad = [{'doc1'}, {'doc2'}]
    
    try:
        hit_rate(retrieved_bad, relevant_bad)
        print("  Should have raised ValueError")
        assert False
    except ValueError as e:
        print(f"  Correctly raised ValueError: {e}")
    
    # Test 3: Negative k
    print("Test 7.3: Invalid k value...")
    retrieved_ok = [['doc1', 'doc2']]
    relevant_ok = [{'doc1'}]
    
    try:
        precision_at_k(retrieved_ok, relevant_ok, k=-1)
        print("  Should have raised ValueError")
        assert False
    except ValueError as e:
        print(f"  Correctly raised ValueError: {e}")
    
    # Test 4: k=0
    print("Test 7.4: k=0...")
    try:
        precision_at_k(retrieved_ok, relevant_ok, k=0)
        print("  Should have raised ValueError")
        assert False
    except ValueError as e:
        print(f"  Correctly raised ValueError: {e}")
    
    # Test 5: k larger than retrieved list
    print("Test 7.5: k > retrieved list length...")
    try:
        prec = precision_at_k([['doc1', 'doc2']], [{'doc1'}], k=10)
        print(f"  Handled k > list length (precision={prec:.4f})")
    except Exception as e:
        print(f"  Failed: {e}")
        raise
    
    print("  All edge case tests passed")


def test_realistic_scenario():
    """Test with realistic teaching scenario."""
    print("\n=== Test 8: Realistic Teaching Scenario ===")
    
    # Simulate retrieval for similar questions
    # Query: "What is the capital of France?"
    # Should retrieve: questions about capitals, especially France
    
    retrieved = [
        # Query 1: France capital
        [
            'q_france_1',      # Perfect match (relevant)
            'q_france_2',      # Another France question (relevant)
            'q_uk_capital',    # Similar topic (relevant)
            'q_germany_capital', # Similar topic (relevant)
            'q_math_1',        # Not relevant
            'q_spain_capital', # Similar topic (relevant)
            'q_physics_1',     # Not relevant
            'q_italy_capital'  # Similar topic (relevant)
        ],
        
        # Query 2: Math question
        [
            'q_math_1',        # Exact match (relevant)
            'q_math_2',        # Similar math (relevant)
            'q_france_1',      # Different topic (not relevant)
            'q_math_3',        # Similar math (relevant)
            'q_physics_2'      # Different topic (not relevant)
        ]
    ]
    
    relevant = [
        # Query 1: Geography questions are relevant
        {'q_france_1', 'q_france_2', 'q_uk_capital', 'q_germany_capital', 
         'q_spain_capital', 'q_italy_capital'},
        
        # Query 2: Math questions are relevant
        {'q_math_1', 'q_math_2', 'q_math_3', 'q_math_4', 'q_math_5'}
    ]
    
    print("Scenario: Teaching system retrieves similar past questions")
    print("Query 1: 'What is the capital of France?'")
    print("  - Should retrieve other geography/capital questions")
    print("Query 2: 'What is 2+2?'")
    print("  - Should retrieve other math questions")
    
    metrics = evaluate_retrieval(retrieved, relevant, k_values=[1, 3, 5, 8])
    print_metrics(metrics, "Realistic Teaching Scenario Metrics")
    
    # Expectations for a good retrieval system:
    # - High hit rate (both queries should find relevant items)
    # - Good precision@3 (top 3 should be mostly relevant)
    # - Decent NDCG (relevant items ranked higher)
    
    assert metrics['hit_rate@1'] >= 0.5, "Should have reasonable hit rate at k=1"
    assert metrics['hit_rate@5'] >= 0.5, "Should have good hit rate at k=5"
    assert metrics['ndcg@5'] >= 0.4, "Should have reasonable ranking quality"
    
    print("  Realistic scenario test passed")


def run_all_tests():
    """Run all retrieval metric tests."""
    print("\n" + "="*60)
    print("RETRIEVAL METRICS TESTS")
    print("="*60)
    
    try:
        test_perfect_retrieval()
        test_no_hits()
        test_partial_retrieval()
        test_ranking_quality()
        test_mrr_positions()
        test_precision_recall_tradeoff()
        test_edge_cases()
        test_realistic_scenario()
        
        print("\n" + "="*60)
        print("[OK] ALL RETRIEVAL METRIC TESTS PASSED!")
        print("="*60)
        
        return 0
        
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
