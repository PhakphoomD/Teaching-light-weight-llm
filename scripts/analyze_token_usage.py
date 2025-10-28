"""
Analyze token usage and calculate costs from experiment results

Usage:
    python analyze_token_usage.py <experiment_dir>
    python analyze_token_usage.py  # Analyzes latest run
"""

import sys
import json
from pathlib import Path
from src.memory.token_tracker import load_token_usage, calculate_cost

# Token pricing (per 1M tokens) - UPDATE THESE WITH ACTUAL PRICES
PRICING = {
    # Local models - Free
    "tinyllama_1.1b": {"input": 0, "output": 0},
    "llama2_7b": {"input": 0, "output": 0},
    "llama3_8b": {"input": 0, "output": 0},
    
    # Groq API (as of 2024)
    "groq_llama3_70b": {"input": 0.59, "output": 0.79},
    "groq_llama3_8b": {"input": 0.05, "output": 0.08},
    
    # Google Gemini (as of 2024)
    "gemini_1.5_pro": {"input": 1.25, "output": 5.00},
    "gemini_1.5_flash": {"input": 0.075, "output": 0.30},
}


def find_latest_experiment(results_dir: str = "results") -> Path:
    """Find the most recent experiment directory"""
    results_path = Path(results_dir)
    
    # Find all run directories
    run_dirs = []
    for model_dir in results_path.iterdir():
        if model_dir.is_dir() and model_dir.name != "tokens":
            for strategy_dir in model_dir.iterdir():
                if strategy_dir.is_dir():
                    for run_dir in strategy_dir.iterdir():
                        if run_dir.is_dir() and run_dir.name.startswith("run_"):
                            # Check if token_usage.json exists
                            if (run_dir / "token_usage.json").exists():
                                run_dirs.append(run_dir)
    
    if not run_dirs:
        raise FileNotFoundError("No experiment directories with token_usage.json found")
    
    # Sort by modification time, newest first
    run_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return run_dirs[0]


def analyze_experiment(experiment_dir: Path):
    """Analyze token usage for an experiment"""
    token_file = experiment_dir / "token_usage.json"
    summary_file = experiment_dir / "summary.json"
    
    if not token_file.exists():
        print(f" No token_usage.json found in {experiment_dir}")
        return
    
    # Load token usage
    token_data = load_token_usage(str(token_file))
    
    # Load summary for additional context
    summary = {}
    if summary_file.exists():
        with open(summary_file, 'r') as f:
            summary = json.load(f)
    
    print("=" * 80)
    print(f" TOKEN USAGE ANALYSIS")
    print("=" * 80)
    print(f"Experiment: {experiment_dir.name}")
    print(f"Strategy: {token_data['strategy_name']}")
    print(f"Student Model: {token_data['student_model']}")
    print(f"Teacher Model: {token_data['teacher_model']}")
    print(f"Timestamp: {token_data['timestamp']}")
    print()
    
    # Student usage
    print(" STUDENT MODEL USAGE")
    print("-" * 80)
    student = token_data['student_usage']
    is_local_student = token_data['student_model'] not in PRICING or PRICING[token_data['student_model']]['input'] == 0
    
    print(f"Model: {student['model_name']}")
    if is_local_student:
        print(f"Type: Local Model (estimated tokens)")
    print(f"Calls: {student['num_calls']:,}")
    print(f"Prompt Tokens (avg): {student['prompt_tokens']:,}")
    print(f"Completion Tokens (avg): {student['completion_tokens']:,}")
    print(f"Total Tokens (avg): {student['total_tokens']:,}")
    print(f"Avg per call: {student['total_tokens'] / max(student['num_calls'], 1):.1f} tokens")
    if is_local_student:
        print(f"Note: These are estimated counts from local tokenizer for baseline comparison")
    print()
    
    # Teacher usage (if different)
    if 'teacher_usage' in token_data:
        print(" TEACHER MODEL USAGE")
        print("-" * 80)
        teacher = token_data['teacher_usage']
        is_local_teacher = token_data['teacher_model'] not in PRICING or PRICING[token_data['teacher_model']]['input'] == 0
        
        print(f"Model: {teacher['model_name']}")
        if is_local_teacher:
            print(f"Type: Local Model (estimated tokens)")
        print(f"Calls: {teacher['num_calls']:,}")
        print(f"Prompt Tokens (avg): {teacher['prompt_tokens']:,}")
        print(f"Completion Tokens (avg): {teacher['completion_tokens']:,}")
        print(f"Total Tokens (avg): {teacher['total_tokens']:,}")
        print(f"Avg per call: {teacher['total_tokens'] / max(teacher['num_calls'], 1):.1f} tokens")
        if is_local_teacher:
            print(f"Note: These are estimated counts from local tokenizer for baseline comparison")
        print()
    
    # Total
    print("=" * 80)
    print(f" TOTAL TOKENS (avg): {token_data['total_tokens']:,}")
    print(f"   Prompt (avg): {token_data['total_prompt_tokens']:,}")
    print(f"   Completion (avg): {token_data['total_completion_tokens']:,}")
    print("=" * 80)
    print()
    
    # Calculate costs
    costs = calculate_cost(token_data, PRICING)
    
    print(" COST BREAKDOWN")
    print("-" * 80)
    
    student_model = token_data['student_model']
    if student_model in PRICING and PRICING[student_model]['input'] > 0:
        student_price = PRICING[student_model]
        print(f"Student Model ({student_model}):")
        print(f"  Input:  ${costs['student_cost'] * student_price['input'] / (student_price['input'] + student_price['output']):.6f} @ ${student_price['input']}/1M tokens")
        print(f"  Output: ${costs['student_cost'] * student_price['output'] / (student_price['input'] + student_price['output']):.6f} @ ${student_price['output']}/1M tokens")
        print(f"  Total:  ${costs['student_cost']:.6f}")
    else:
        # Show estimated cost if it were an API model
        student_usage = token_data['student_usage']
        print(f"Student Model ({student_model}): FREE (local model)")
        print(f"  Estimated tokens (avg): {student_usage['total_tokens']:,} (baseline for API comparison)")
        print(f"  If using API equivalent:")
        # Use Groq 8B as baseline comparison for local models
        baseline_price = PRICING.get('groq_llama3_8b', {'input': 0.05, 'output': 0.08})
        estimated_cost = (
            (student_usage['prompt_tokens'] / 1_000_000) * baseline_price['input'] +
            (student_usage['completion_tokens'] / 1_000_000) * baseline_price['output']
        )
        print(f"    Groq Llama3 8B would cost: ~${estimated_cost:.6f}")
    
    print()
    
    if 'teacher_usage' in token_data:
        teacher_model = token_data['teacher_model']
        if teacher_model in PRICING and PRICING[teacher_model]['input'] > 0:
            teacher_price = PRICING[teacher_model]
            print(f"Teacher Model ({teacher_model}):")
            print(f"  Input:  ${costs['teacher_cost'] * teacher_price['input'] / (teacher_price['input'] + teacher_price['output']):.6f} @ ${teacher_price['input']}/1M tokens")
            print(f"  Output: ${costs['teacher_cost'] * teacher_price['output'] / (teacher_price['input'] + teacher_price['output']):.6f} @ ${teacher_price['output']}/1M tokens")
            print(f"  Total:  ${costs['teacher_cost']:.6f}")
        else:
            teacher_usage = token_data['teacher_usage']
            print(f"Teacher Model ({teacher_model}): FREE (local model)")
            print(f"  Estimated tokens (avg): {teacher_usage['total_tokens']:,} (baseline for API comparison)")
            print(f"  If using API equivalent:")
            # Use Groq 70B as baseline for teacher models
            baseline_price = PRICING.get('groq_llama3_70b', {'input': 0.59, 'output': 0.79})
            estimated_cost = (
                (teacher_usage['prompt_tokens'] / 1_000_000) * baseline_price['input'] +
                (teacher_usage['completion_tokens'] / 1_000_000) * baseline_price['output']
            )
            print(f"    Groq Llama3 70B would cost: ~${estimated_cost:.6f}")
    
    print()
    print("=" * 80)
    print(f" GRAND TOTAL: ${costs['total_cost']:.6f}")
    print("=" * 80)
    
    # Cost per task
    if summary:
        num_tasks = summary.get('total_tasks', 1)
        passed = summary.get('passed', 0)
        print(f"\nPer-task metrics:")
        print(f"  Cost per task: ${costs['total_cost'] / num_tasks:.6f}")
        if passed > 0:
            print(f"  Cost per success: ${costs['total_cost'] / passed:.6f}")
        print(f"  Tokens per task: {token_data['total_tokens'] / num_tasks:.1f}")
    
    print()


def main():
    if len(sys.argv) > 1:
        experiment_dir = Path(sys.argv[1])
    else:
        print(" Finding latest experiment with token usage...")
        experiment_dir = find_latest_experiment()
        print(f" Found: {experiment_dir}\n")
    
    analyze_experiment(experiment_dir)


if __name__ == "__main__":
    main()
