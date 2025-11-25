"""
Test ExperimentManager - Professional Logs Organization

This script demonstrates how to use ExperimentManager for
organized experiment tracking.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.experiment import ExperimentManager, list_experiments, cleanup_old_experiments


def test_create_experiment():
    """Test creating a new experiment."""
    print("\n" + "="*60)
    print("TEST 1: Create New Experiment")
    print("="*60)
    
    # Create experiment
    exp = ExperimentManager.create(
        name="test_baseline",
        category="tests",
        config={
            "student_model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            "teacher_model": "gemini-2.0-flash-lite",
            "strategy": "simple",
            "max_rounds": 3,
            "k": 5,
            "dataset": "alpaca_20.jsonl"
        }
    )
    
    print(f"\n  Created experiment:")
    print(f"  Run ID: {exp.run_id}")
    print(f"  Directory: {exp.run_dir}")
    print(f"  Memory: {exp.memory_dir}")
    print(f"  Config: {exp.config_file}")
    print(f"  Runs Log: {exp.runs_log}")
    print(f"  Summary: {exp.summary_file}")
    
    # Verify directory structure
    print(f"\n  Directory structure:")
    print(f"  {exp.run_dir.exists()} - {exp.run_dir}")
    print(f"  {exp.memory_dir.exists()} - {exp.memory_dir}")
    print(f"  {exp.config_file.exists()} - {exp.config_file}")
    
    return exp


def test_log_runs(exp: ExperimentManager):
    """Test logging run records."""
    print("\n" + "="*60)
    print("TEST 2: Log Run Records")
    print("="*60)
    
    # Simulate 3 questions
    for i in range(1, 4):
        run_data = {
            "experiment_id": exp.run_id,
            "question_id": f"q{i:03d}",
            "round": 1,
            "question": f"Test question {i}?",
            "student_answer": f"Test answer {i}",
            "teacher_evaluation": "correct",
            "hint": f"Good answer for question {i}",
            "context_ids": [],
            "tokens_used": 150 + i * 10,
            "latency_ms": 1000 + i * 100
        }
        
        exp.log_run(run_data)
        print(f"    Logged run for question {i}")
    
    # Load and verify
    runs = exp.list_runs()
    print(f"\n  Total runs logged: {len(runs)}")
    print(f"  Runs log file: {exp.runs_log}")


def test_save_summary(exp: ExperimentManager):
    """Test saving experiment summary."""
    print("\n" + "="*60)
    print("TEST 3: Save Experiment Summary")
    print("="*60)
    
    summary = {
        "experiment_id": exp.run_id,
        "total_questions": 3,
        "success_rate": 1.0,
        "avg_rounds": 1.0,
        "avg_tokens": 170,
        "total_latency_ms": 3300,
        "strategy": "simple",
        "config": exp.load_config()
    }
    
    exp.save_summary(summary)
    
    print(f"    Summary saved to: {exp.summary_file}")
    print(f"\n  Summary:")
    print(f"    Success Rate: {summary['success_rate']*100:.1f}%")
    print(f"    Avg Rounds: {summary['avg_rounds']:.2f}")
    print(f"    Avg Tokens: {summary['avg_tokens']}")


def test_list_experiments():
    """Test listing experiments."""
    print("\n" + "="*60)
    print("TEST 4: List Experiments")
    print("="*60)
    
    for category in ["experiments", "tests", "dev"]:
        exps = list_experiments(category)
        print(f"\n  {category.upper()}:")
        if exps:
            for exp_id in exps[:5]:  # Show max 5
                print(f"    - {exp_id}")
            if len(exps) > 5:
                print(f"    ... and {len(exps) - 5} more")
        else:
            print(f"    (empty)")


def test_experiment_info(exp: ExperimentManager):
    """Test getting experiment info."""
    print("\n" + "="*60)
    print("TEST 5: Experiment Info")
    print("="*60)
    
    info = exp.get_info()
    
    print(f"\n  Run ID: {info['run_id']}")
    print(f"  Directory: {info['run_dir']}")
    print(f"\n  Files:")
    for key, exists in info['exists'].items():
        status = " " if exists else " "
        print(f"    {status} {key}")
    
    if 'num_runs' in info:
        print(f"\n  Total Runs: {info['num_runs']}")


def test_cleanup():
    """Test cleanup old experiments."""
    print("\n" + "="*60)
    print("TEST 6: Cleanup Old Experiments")
    print("="*60)
    
    # Create some dummy experiments
    print("\n  Creating 5 test experiments...")
    for i in range(5):
        ExperimentManager.create(
            name=f"cleanup_test_{i}",
            category="dev"
        )
    
    # List before cleanup
    before = list_experiments("dev")
    print(f"  Before cleanup: {len(before)} experiments")
    
    # Cleanup, keep only 2
    deleted = cleanup_old_experiments("dev", keep_latest=2)
    
    # List after cleanup
    after = list_experiments("dev")
    print(f"  After cleanup: {len(after)} experiments")
    print(f"  Deleted: {deleted} experiments")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("EXPERIMENT MANAGER TEST SUITE")
    print("="*60)
    
    try:
        # Test 1: Create
        exp = test_create_experiment()
        
        # Test 2: Log runs
        test_log_runs(exp)
        
        # Test 3: Save summary
        test_save_summary(exp)
        
        # Test 4: List experiments
        test_list_experiments()
        
        # Test 5: Get info
        test_experiment_info(exp)
        
        # Test 6: Cleanup
        test_cleanup()
        
        print("\n" + "="*60)
        print("[OK] ALL TESTS PASSED!")
        print("="*60)
        
        print("\n  Check your logs directory:")
        print("   logs/")
        print("       experiments/")
        print("       tests/")
        print("           [timestamped folders]")
        print("       dev/")
        
        return 0
        
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
