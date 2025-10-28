"""
Test script to demonstrate batch experiment summary
"""
from dataclasses import dataclass, field
from typing import List

@dataclass
class MockSummary:
    """Mock EvaluationSummary for testing"""
    experiment: str = "Test Experiment"
    total_tasks: int = 20
    passed: int = 17
    failed: int = 3
    success_rate: float = 0.85
    avg_attempts: float = 1.35
    first_attempt_pass_rate: float = 0.65
    mean_score: float = 0.78
    learning_gain: float = 0.125
    repeat_error_rate: float = 0.15
    memory_utilization_rate: float = 0.70
    cross_task_transfer: float = 0.45
    tokens_per_task: float = 1245.5
    tokens_per_success: float = 1056.2
    total_tokens: int = 24891
    total_cost: float = 0.0
    estimated_cost: float = 0.001616
    is_local_student: bool = True
    latency_per_task_ms: float = 850.5
    total_runtime_s: float = 345.67
    early_stopped_tasks: int = 2


def create_mock_experiments():
    """Create mock experiment results"""
    experiments = [
        MockSummary(
            experiment="Baseline (No Memory)",
            success_rate=0.65,
            first_attempt_pass_rate=0.60,
            mean_score=0.65,
            learning_gain=0.05,
            repeat_error_rate=0.35,
            memory_utilization_rate=0.0,
            cross_task_transfer=0.0,
            tokens_per_task=980.0,
            tokens_per_success=1200.0,
            total_tokens=19600,
            estimated_cost=0.001274,
            latency_per_task_ms=720.5,
            total_runtime_s=280.3,
            early_stopped_tasks=4,
        ),
        MockSummary(
            experiment="MultiKey TF-IDF",
            success_rate=0.85,
            first_attempt_pass_rate=0.65,
            mean_score=0.78,
            learning_gain=0.125,
            repeat_error_rate=0.15,
            memory_utilization_rate=0.70,
            cross_task_transfer=0.45,
            tokens_per_task=1245.5,
            tokens_per_success=1056.2,
            total_tokens=24891,
            estimated_cost=0.001616,
            latency_per_task_ms=850.5,
            total_runtime_s=345.67,
            early_stopped_tasks=2,
        ),
        MockSummary(
            experiment="Canonical Similarity",
            success_rate=0.90,
            first_attempt_pass_rate=0.70,
            mean_score=0.85,
            learning_gain=0.180,
            repeat_error_rate=0.10,
            memory_utilization_rate=0.85,
            cross_task_transfer=0.60,
            tokens_per_task=1350.0,
            tokens_per_success=1100.0,
            total_tokens=27000,
            estimated_cost=0.001753,
            latency_per_task_ms=920.0,
            total_runtime_s=390.5,
            early_stopped_tasks=1,
        ),
    ]
    
    return [(exp, []) for exp in experiments]


def print_batch_summary(all_results):
    """Simulate the batch summary printing"""
    from src.core.logger import get_logger
    logger = get_logger(__name__)
    
    logger.info("\n" + "=" * 80)
    logger.info("COMPREHENSIVE SUMMARY COMPARISON")
    logger.info("=" * 80)
    
    # Extract data from all experiments
    experiments_data = []
    for summary, _ in all_results:
        experiments_data.append({
            'name': summary.experiment,
            'success_rate': summary.success_rate,
            'passed': summary.passed,
            'total': summary.total_tasks,
            'first_attempt_pass_rate': summary.first_attempt_pass_rate,
            'avg_attempts': summary.avg_attempts,
            'mean_score': summary.mean_score,
            'learning_gain': summary.learning_gain,
            'repeat_error_rate': summary.repeat_error_rate,
            'memory_utilization': summary.memory_utilization_rate,
            'cross_task_transfer': summary.cross_task_transfer,
            'tokens_per_task': summary.tokens_per_task,
            'tokens_per_success': summary.tokens_per_success,
            'total_tokens': summary.total_tokens,
            'total_cost': summary.total_cost,
            'estimated_cost': summary.estimated_cost,
            'is_local': summary.is_local_student,
            'latency_ms': summary.latency_per_task_ms,
            'total_runtime_s': summary.total_runtime_s,
            'early_stopped': summary.early_stopped_tasks,
        })
    
    # === 1. PERFORMANCE COMPARISON ===
    logger.info("\n[1] PERFORMANCE METRICS")
    logger.info("-" * 80)
    logger.info(f"{'Strategy':<40} | {'Success':<8} | {'1st Pass':<8} | {'Mean Score':<10} | {'Avg Attempts':<12}")
    logger.info("-" * 80)
    for data in experiments_data:
        logger.info(
            f"{data['name']:<40} | "
            f"{data['success_rate']:>6.1%}   | "
            f"{data['first_attempt_pass_rate']:>6.1%}   | "
            f"{data['mean_score']:>8.3f}   | "
            f"{data['avg_attempts']:>10.2f}"
        )
    
    # === 2. LEARNING METRICS ===
    logger.info("\n[2] LEARNING & GENERALISATION METRICS")
    logger.info("-" * 80)
    logger.info(f"{'Strategy':<40} | {'ΔScore':<9} | {'Repeat-Err':<10} | {'Memory Use':<10} | {'Transfer':<9}")
    logger.info("-" * 80)
    for data in experiments_data:
        logger.info(
            f"{data['name']:<40} | "
            f"{data['learning_gain']:>+7.3f}   | "
            f"{data['repeat_error_rate']:>8.1%}   | "
            f"{data['memory_utilization']:>8.1%}   | "
            f"{data['cross_task_transfer']:>7.1%}"
        )
    
    # === 3. EFFICIENCY METRICS ===
    logger.info("\n[3] EFFICIENCY METRICS")
    logger.info("-" * 80)
    logger.info(f"{'Strategy':<40} | {'Tokens/Task':<12} | {'Tokens/Succ':<12} | {'Latency(ms)':<12} | {'Runtime(s)':<11}")
    logger.info("-" * 80)
    for data in experiments_data:
        logger.info(
            f"{data['name']:<40} | "
            f"{data['tokens_per_task']:>10.0f}   | "
            f"{data['tokens_per_success']:>10.0f}   | "
            f"{data['latency_ms']:>10.1f}   | "
            f"{data['total_runtime_s']:>9.1f}"
        )
    
    # === 4. COST COMPARISON ===
    logger.info("\n[4] COST COMPARISON")
    logger.info("-" * 80)
    logger.info(f"{'Strategy':<40} | {'Total Tokens':<13} | {'Cost':<20}")
    logger.info("-" * 80)
    for data in experiments_data:
        if data['is_local']:
            cost_str = f"FREE (est: ~${data['estimated_cost']:.6f})"
        else:
            cost_str = f"${data['total_cost']:.6f}"
        logger.info(
            f"{data['name']:<40} | "
            f"{data['total_tokens']:>11,}   | "
            f"{cost_str}"
        )
    
    # === 5. BEST PERFORMERS ===
    logger.info("\n[5] BEST PERFORMERS")
    logger.info("-" * 80)
    
    # Best success rate
    best_success = max(experiments_data, key=lambda x: x['success_rate'])
    logger.info(f"Highest Success Rate:  {best_success['name']} ({best_success['success_rate']:.1%})")
    
    # Best learning gain
    best_learning = max(experiments_data, key=lambda x: x['learning_gain'])
    logger.info(f"Best Learning Gain:    {best_learning['name']} ({best_learning['learning_gain']:+.3f})")
    
    # Most efficient (tokens per success)
    if any(d['tokens_per_success'] > 0 for d in experiments_data):
        best_efficient = min([d for d in experiments_data if d['tokens_per_success'] > 0], 
                            key=lambda x: x['tokens_per_success'])
        logger.info(f"Most Efficient:        {best_efficient['name']} ({best_efficient['tokens_per_success']:.0f} tokens/success)")
    
    # Fastest
    best_speed = min(experiments_data, key=lambda x: x['latency_ms'])
    logger.info(f"Fastest:               {best_speed['name']} ({best_speed['latency_ms']:.1f}ms/task)")
    
    # Best transfer learning
    if any(d['cross_task_transfer'] > 0 for d in experiments_data):
        best_transfer = max(experiments_data, key=lambda x: x['cross_task_transfer'])
        logger.info(f"Best Transfer:         {best_transfer['name']} ({best_transfer['cross_task_transfer']:.1%})")
    
    logger.info("=" * 80)


if __name__ == "__main__":
    mock_results = create_mock_experiments()
    print_batch_summary(mock_results)
