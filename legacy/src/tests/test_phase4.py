"""
Phase 4 Integration Test - Teaching Pipeline

Tests the complete teaching pipeline with real models:
- Student: TinyLlama (local)
- Teacher: Gemini (API)
- Memory: FAISS + JSONL
- Strategies: Simple, Memory-Augmented, Adaptive
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.pipeline.orchestrator import TeachingOrchestrator


def test_simple_strategy():
    """Test teaching with SimpleStrategy (no memory)."""
    print("\n" + "="*60)
    print("TEST 1: Simple Strategy (No Memory)")
    print("="*60)
    
    try:
        # Create orchestrator with simple strategy
        print("\nInitializing orchestrator...")
        orchestrator = TeachingOrchestrator.from_config(
            student_provider="local",
            student_model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            teacher_provider="gemini",
            teacher_model="gemini-2.0-flash-lite",
            strategy_type="simple",
            max_rounds=3
        )
        
        print("  Orchestrator initialized")
        
        # Test single question
        print("\nTesting single question...")
        result = orchestrator.teach(
            question="What is the capital of France?"
        )
        
        print(f"\n--- Result ---")
        print(f"Initial Answer: {result['initial_answer']}")
        print(f"Final Answer: {result['final_answer']}")
        print(f"Success: {result['success']}")
        print(f"Rounds: {result['num_rounds']}")
        print(f"Improvement: {result['improvement']}")
        
        # Print stats
        orchestrator.print_stats()
        
        print("[OK] Simple strategy test passed!")
        return True
        
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_memory_augmented_strategy():
    """Test teaching with MemoryAugmentedStrategy."""
    print("\n" + "="*60)
    print("TEST 2: Memory-Augmented Strategy")
    print("="*60)
    
    try:
        # Create orchestrator with memory strategy
        print("\nInitializing orchestrator with memory...")
        orchestrator = TeachingOrchestrator.from_config(
            student_provider="local",
            student_model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            teacher_provider="gemini",
            teacher_model="gemini-2.0-flash-lite",
            strategy_type="memory",
            max_rounds=3,
            memory_dir="logs/memory_test",
            k=3
        )
        
        print("  Orchestrator initialized with memory")
        
        # Test batch of related questions
        print("\nTesting batch of questions...")
        questions = [
            "What is the capital of France?",
            "What is the capital of the United Kingdom?",
            "What is the capital of Germany?"
        ]
        
        results = orchestrator.teach_batch(questions)
        
        # Check that later questions benefit from memory
        print(f"\n--- Batch Results ---")
        for i, result in enumerate(results, 1):
            print(f"Q{i}: {result['num_rounds']} rounds, "
                  f"success={result['success']}")
        
        # Print stats
        orchestrator.print_stats()
        
        # Export results
        orchestrator.export_results("logs/phase4_memory_test.json")
        
        print("[OK] Memory-augmented strategy test passed!")
        return True
        
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_adaptive_strategy():
    """Test teaching with AdaptiveStrategy."""
    print("\n" + "="*60)
    print("TEST 3: Adaptive Strategy")
    print("="*60)
    
    try:
        # Create orchestrator with adaptive strategy
        print("\nInitializing orchestrator with adaptive strategy...")
        orchestrator = TeachingOrchestrator.from_config(
            student_provider="local",
            student_model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            teacher_provider="gemini",
            teacher_model="gemini-2.0-flash-lite",
            strategy_type="adaptive",
            max_rounds=5,
            memory_dir="logs/memory_adaptive_test",
            k=5,
            adapt_after=5
        )
        
        print("  Orchestrator initialized with adaptive strategy")
        
        # Test with mix of easy and hard questions
        print("\nTesting with mixed difficulty questions...")
        questions = [
            # Easy questions (should succeed quickly)
            "What is 2+2?",
            "What color is the sky?",
            "How many days in a week?",
            
            # Geography questions (medium)
            "What is the capital of Japan?",
            "What is the capital of Brazil?",
            
            # More complex (may need more rounds)
            "What is the largest planet in our solar system?",
            "Who wrote Romeo and Juliet?",
        ]
        
        results = orchestrator.teach_batch(questions)
        
        # Analyze adaptation
        print(f"\n--- Adaptation Analysis ---")
        for i, result in enumerate(results, 1):
            print(f"Q{i}: {result['num_rounds']} rounds, "
                  f"success={result['success']}, "
                  f"improvement={result['improvement']}")
        
        # Print stats
        orchestrator.print_stats()
        
        # Export results
        orchestrator.export_results("logs/phase4_adaptive_test.json")
        
        print("[OK] Adaptive strategy test passed!")
        return True
        
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all Phase 4 integration tests."""
    print("\n" + "="*60)
    print("PHASE 4 INTEGRATION TESTS")
    print("Testing Complete Teaching Pipeline")
    print("="*60)
    
    results = []
    
    # Test 1: Simple Strategy
    results.append(("Simple Strategy", test_simple_strategy()))
    
    # Test 2: Memory-Augmented Strategy
    results.append(("Memory-Augmented Strategy", test_memory_augmented_strategy()))
    
    # Test 3: Adaptive Strategy
    results.append(("Adaptive Strategy", test_adaptive_strategy()))
    
    # Summary
    print("\n" + "="*60)
    print("PHASE 4 TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "[OK] PASSED" if passed else "[FAIL] FAILED"
        print(f"{test_name:30s}: {status}")
    
    all_passed = all(passed for _, passed in results)
    
    print("="*60)
    if all_passed:
        print("[OK] ALL PHASE 4 TESTS PASSED!")
        print("="*60)
        return 0
    else:
        print("[FAIL] SOME TESTS FAILED")
        print("="*60)
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
