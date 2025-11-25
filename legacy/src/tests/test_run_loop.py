"""
Test run_loop function - Config-based refinement with detailed logging

This script demonstrates the run_loop function which is a config-based
wrapper around RefinementLoop with detailed per-round logging.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.refinement.loop import run_loop
from src.providers.factory import build_client
from src.critic.model import TeacherCritic
from src.memory.store import MemoryStore
from src.memory.vector import VectorIndex


def test_run_loop_simple():
    """Test run_loop with simple questions."""
    print("\n" + "="*60)
    print("TEST: run_loop() with Config-based Approach")
    print("="*60)
    
    try:
        # Setup clients
        print("\n1. Initializing clients...")
        student_client = build_client(
            provider="local",
            model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            device="cuda"
        )
        
        teacher_client = build_client(
            provider="gemini",
            model="gemini-2.0-flash-lite"
        )
        
        print("  Student client: TinyLlama (CUDA)")
        print("  Teacher client: Gemini-2.0-Flash-Lite")
        
        # Setup memory
        print("\n2. Initializing memory system...")
        store = MemoryStore("logs/test_run_loop_memory/store.jsonl")
        index = VectorIndex(
            index_path="logs/test_run_loop_memory/faiss.index",
            embedding_model="all-MiniLM-L6-v2"
        )
        
        print(f"  Memory store: {store.file_path}")
        print(f"  Vector index: {index.index.ntotal} records")
        
        # Setup critic
        print("\n3. Initializing teacher critic...")
        critic = TeacherCritic(
            provider="gemini",
            model_name="gemini-2.0-flash-lite"
        )
        
        print("  TeacherCritic initialized")
        
        # Config
        config = {
            "student_client": student_client,
            "teacher_client": teacher_client,
            "max_rounds": 3,
            "k": 3,
            "memory_type": "raw",
            "use_cot_teacher": False,
            "use_cot_student": False,
            "student_temperature": 0.7,
            "teacher_temperature": 0.3
        }
        
        print("\n4. Config:")
        print(f"   - max_rounds: {config['max_rounds']}")
        print(f"   - k (retrieval): {config['k']}")
        print(f"   - memory_type: {config['memory_type']}")
        
        # Test questions
        questions = [
            "What is the capital of France?",
            "What is the capital of Japan?",
            "What is 5+3?"
        ]
        
        experiment_id = "test_run_loop_001"
        
        print(f"\n5. Running loop for {len(questions)} questions...")
        print(f"   Experiment ID: {experiment_id}")
        print(f"   Log file: logs/runs/{experiment_id}.jsonl")
        
        results = []
        
        for i, question in enumerate(questions, 1):
            print(f"\n{'='*60}")
            print(f"Question {i}/{len(questions)}: {question}")
            print(f"{'='*60}")
            
            result = run_loop(
                question=question,
                config=config,
                store=store,
                index=index,
                critic=critic,
                experiment_id=experiment_id,
                question_id=f"q{i:03d}"
            )
            
            results.append(result)
            
            print(f"\nResult:")
            print(f"    Success: {result['success']}")
            print(f"    Rounds: {result['num_rounds']}")
            print(f"    Improvement: {result['improvement']}")
            print(f"    Final answer: {result['final_answer'][:80]}...")
        
        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        
        total = len(results)
        successes = sum(1 for r in results if r['success'])
        improvements = sum(1 for r in results if r['improvement'])
        avg_rounds = sum(r['num_rounds'] for r in results) / total
        total_tokens = sum(r['total_tokens'] for r in results)
        total_latency = sum(r['total_latency_ms'] for r in results)
        
        print(f"Questions:     {total}")
        print(f"Successes:     {successes} ({successes/total*100:.1f}%)")
        print(f"Improvements:  {improvements} ({improvements/total*100:.1f}%)")
        print(f"Avg Rounds:    {avg_rounds:.2f}")
        print(f"Total Tokens:  {total_tokens}")
        print(f"Total Latency: {total_latency:.0f}ms")
        print(f"\nLog file: logs/runs/{experiment_id}.jsonl")
        print(f"Memory store: logs/test_run_loop_memory/store.jsonl")
        print(f"Vector index: {index.index.ntotal} records")
        
        print(f"\n{'='*60}")
        print("[OK] TEST PASSED!")
        print(f"{'='*60}")
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_run_loop_simple()
    sys.exit(0 if success else 1)
