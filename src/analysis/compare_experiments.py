"""
Compare Experiments

Compare results from different experiments (baseline, tfidf, rulekey, memory_none).
"""

import os
import json
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class ExperimentComparison:
    """Comparison of multiple experiments."""
    experiments: List[str]
    success_rates: List[float]
    avg_attempts: List[float]
    avg_retrieval_ms: List[float]
    avg_generation_ms: List[float]
    avg_total_ms: List[float]
    total_runtime_s: List[float]


def load_experiment_summary(experiment_dir: str, run_name: str | None = None) -> Dict[str, Any]:
    """
    Load experiment summary JSON.
    
    Args:
        experiment_dir: Path to experiment directory
        run_name: Specific run directory name (if None, uses latest)
        
    Returns:
        Summary dictionary
    """
    if run_name:
        summary_path = os.path.join(experiment_dir, run_name, "summary.json")
    else:
        # Find latest run
        runs = [d for d in os.listdir(experiment_dir) if d.startswith("run_")]
        if not runs:
            raise FileNotFoundError(f"No runs found in {experiment_dir}")
        latest_run = sorted(runs)[-1]
        summary_path = os.path.join(experiment_dir, latest_run, "summary.json")
    
    with open(summary_path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_experiments(
    model_name: str,
    experiments: List[str],
    base_dir: str = "logs/experiments"
) -> ExperimentComparison:
    """
    Compare multiple experiments for a model.
    
    Args:
        model_name: Model name (e.g., "tinyllama_1_1b")
        experiments: List of experiment names (e.g., ["baseline", "memory_tfidf"])
        base_dir: Base experiments directory
        
    Returns:
        ExperimentComparison object
    """
    success_rates = []
    avg_attempts = []
    avg_retrieval_ms = []
    avg_generation_ms = []
    avg_total_ms = []
    total_runtime_s = []
    
    for exp in experiments:
        exp_dir = os.path.join(base_dir, model_name, exp)
        summary = load_experiment_summary(exp_dir)
        
        success_rates.append(summary.get("success_rate", 0.0))
        avg_attempts.append(summary.get("avg_attempts", 0.0))
        avg_retrieval_ms.append(summary.get("avg_retrieval_ms", 0.0))
        avg_generation_ms.append(summary.get("avg_generation_ms", 0.0))
        avg_total_ms.append(summary.get("avg_total_ms", 0.0))
        total_runtime_s.append(summary.get("total_runtime_s", 0.0))
    
    return ExperimentComparison(
        experiments=experiments,
        success_rates=success_rates,
        avg_attempts=avg_attempts,
        avg_retrieval_ms=avg_retrieval_ms,
        avg_generation_ms=avg_generation_ms,
        avg_total_ms=avg_total_ms,
        total_runtime_s=total_runtime_s
    )


def print_comparison(comparison: ExperimentComparison) -> None:
    """
    Print comparison table.
    
    Args:
        comparison: ExperimentComparison object
    """
    print("\n" + "=" * 80)
    print("EXPERIMENT COMPARISON")
    print("=" * 80)
    
    # Header
    print(f"{'Experiment':<20} {'Success%':<12} {'Attempts':<12} {'Retrieval(ms)':<15} {'Gen(ms)':<12} {'Total(ms)':<12}")
    print("-" * 80)
    
    # Rows
    for i, exp in enumerate(comparison.experiments):
        print(
            f"{exp:<20} "
            f"{comparison.success_rates[i]*100:>10.1f}% "
            f"{comparison.avg_attempts[i]:>10.1f} "
            f"{comparison.avg_retrieval_ms[i]:>13.0f} "
            f"{comparison.avg_generation_ms[i]:>10.0f} "
            f"{comparison.avg_total_ms[i]:>10.0f}"
        )
    
    print("=" * 80)


if __name__ == "__main__":
    # Example usage
    comparison = compare_experiments(
        model_name="tinyllama_1_1b",
        experiments=["baseline", "memory_tfidf", "memory_rulekey", "memory_none"]
    )
    print_comparison(comparison)
