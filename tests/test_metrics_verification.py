"""
Test script to verify all metrics are properly calculated and saved
"""
import json
from pathlib import Path

def test_metrics_completeness():
    """Check if all metrics are properly saved in summary.json"""
    
    # Find latest run
    results_dir = Path("results/tinyllama_1.1b/multikey_tfidf")
    if not results_dir.exists():
        print(" No results directory found")
        return
    
    runs = sorted(results_dir.glob("run_*"))
    if not runs:
        print(" No runs found")
        return
    
    latest_run = runs[-1]
    print(f" Checking latest run: {latest_run.name}\n")
    
    # Load summary.json
    summary_path = latest_run / "summary.json"
    if not summary_path.exists():
        print(" summary.json not found")
        return
    
    with open(summary_path) as f:
        summary = json.load(f)
    
    print("=" * 80)
    print("METRICS VERIFICATION")
    print("=" * 80)
    
    # Check Performance Metrics
    print("\n[1] PERFORMANCE METRICS")
    print("-" * 80)
    perf_metrics = ['mean_score', 'pass_rate_at_7', 'pass_rate_at_8', 
                    'first_attempt_success', 'first_attempt_pass_rate']
    for metric in perf_metrics:
        value = summary.get(metric, "MISSING")
        status = "" if metric in summary else ""
        print(f"{status} {metric:30s}: {value}")
    
    # Check Learning Metrics
    print("\n[2] LEARNING & GENERALISATION METRICS")
    print("-" * 80)
    learning_metrics = ['learning_gain', 'repeat_error_rate', 'memory_utilization_rate',
                       'retrieval_precision_at_3', 'cross_task_transfer']
    for metric in learning_metrics:
        value = summary.get(metric, "MISSING")
        status = "" if metric in summary else ""
        if metric == 'retrieval_precision_at_3' and value == 0.0:
            status = ""  # Placeholder
        print(f"{status} {metric:30s}: {value}")
    
    # Check Efficiency Metrics
    print("\n[3] EFFICIENCY METRICS")
    print("-" * 80)
    efficiency_metrics = ['tokens_per_task', 'tokens_per_success', 'latency_per_task_ms',
                         'retrieval_hit_rate', 'memory_size']
    for metric in efficiency_metrics:
        value = summary.get(metric, "MISSING")
        status = "" if metric in summary else ""
        print(f"{status} {metric:30s}: {value}")
    
    # Check Cost Information
    print("\n[4] COST INFORMATION")
    print("-" * 80)
    cost_metrics = ['student_model', 'teacher_model', 'student_tokens', 'teacher_tokens',
                   'student_cost', 'teacher_cost', 'total_cost', 'estimated_cost',
                   'is_local_student', 'is_local_teacher']
    for metric in cost_metrics:
        value = summary.get(metric, "MISSING")
        status = "" if metric in summary else ""
        print(f"{status} {metric:30s}: {value}")
    
    # Check Token Usage
    print("\n[5] TOKEN USAGE")
    print("-" * 80)
    token_metrics = ['total_prompt_tokens', 'total_completion_tokens', 'total_tokens',
                    'avg_prompt_tokens', 'avg_completion_tokens', 'avg_total_tokens']
    for metric in token_metrics:
        value = summary.get(metric, "MISSING")
        status = "" if metric in summary else ""
        print(f"{status} {metric:30s}: {value}")
    
    # Summary
    print("\n" + "=" * 80)
    all_metrics = perf_metrics + learning_metrics + efficiency_metrics + cost_metrics + token_metrics
    found = sum(1 for m in all_metrics if m in summary)
    print(f"TOTAL: {found}/{len(all_metrics)} metrics found in summary.json")
    
    # Check if token_usage.json exists
    token_usage_path = latest_run / "token_usage.json"
    if token_usage_path.exists():
        print(f" token_usage.json found")
        with open(token_usage_path) as f:
            token_data = json.load(f)
        print(f"   - Student tokens: {token_data.get('student_usage', {}).get('total_tokens', 'N/A')}")
        print(f"   - Teacher tokens: {token_data.get('teacher_usage', {}).get('total_tokens', 'N/A')}")
    else:
        print(f" token_usage.json not found")
    
    # Check results.jsonl
    results_path = latest_run / "results.jsonl"
    if results_path.exists():
        with open(results_path) as f:
            lines = f.readlines()
        print(f" results.jsonl found ({len(lines)} tasks)")
        
        # Check first task result
        if lines:
            first_task = json.loads(lines[0])
            print(f"\n   Sample TaskResult (first task):")
            print(f"   - task_id: {first_task.get('task_id', 'N/A')}")
            print(f"   - passed: {first_task.get('passed', 'N/A')}")
            print(f"   - attempts: {first_task.get('attempts', 'N/A')}")
            print(f"   - scores: {first_task.get('scores', 'N/A')}")
            print(f"   - first_attempt_passed: {first_task.get('first_attempt_passed', 'N/A')}")
            print(f"   - used_memory: {first_task.get('used_memory', 'N/A')}")
            print(f"   - memory_helped: {first_task.get('memory_helped', 'N/A')}")
    else:
        print(f" results.jsonl not found")
    
    print("=" * 80)

if __name__ == "__main__":
    test_metrics_completeness()
