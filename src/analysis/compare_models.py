"""
Compare Models

Compare same experiment across different models (e.g., TinyLlama vs Llama2).
"""

import os
from typing import Dict, List
from src.analysis.compare_experiments import load_experiment_summary, ExperimentComparison


def compare_models(
    models: List[str],
    experiment: str,
    base_dir: str = "logs/experiments"
) -> ExperimentComparison:
    """
    Compare same experiment across different models.
    
    Args:
        models: List of model names (e.g., ["tinyllama_1_1b", "llama2_7b"])
        experiment: Experiment name (e.g., "baseline")
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
    
    for model in models:
        exp_dir = os.path.join(base_dir, model, experiment)
        try:
            summary = load_experiment_summary(exp_dir)
            
            success_rates.append(summary.get("success_rate", 0.0))
            avg_attempts.append(summary.get("avg_attempts", 0.0))
            avg_retrieval_ms.append(summary.get("avg_retrieval_ms", 0.0))
            avg_generation_ms.append(summary.get("avg_generation_ms", 0.0))
            avg_total_ms.append(summary.get("avg_total_ms", 0.0))
            total_runtime_s.append(summary.get("total_runtime_s", 0.0))
        except FileNotFoundError:
            print(f"Warning: No results found for {model}/{experiment}")
            success_rates.append(0.0)
            avg_attempts.append(0.0)
            avg_retrieval_ms.append(0.0)
            avg_generation_ms.append(0.0)
            avg_total_ms.append(0.0)
            total_runtime_s.append(0.0)
    
    return ExperimentComparison(
        experiments=models,
        success_rates=success_rates,
        avg_attempts=avg_attempts,
        avg_retrieval_ms=avg_retrieval_ms,
        avg_generation_ms=avg_generation_ms,
        avg_total_ms=avg_total_ms,
        total_runtime_s=total_runtime_s
    )


def print_model_comparison(comparison: ExperimentComparison, experiment: str) -> None:
    """
    Print model comparison table.
    
    Args:
        comparison: ExperimentComparison object
        experiment: Experiment name being compared
    """
    print("\n" + "=" * 80)
    print(f"MODEL COMPARISON - {experiment.upper()}")
    print("=" * 80)
    
    # Header
    print(f"{'Model':<20} {'Success%':<12} {'Attempts':<12} {'Retrieval(ms)':<15} {'Gen(ms)':<12} {'Total(ms)':<12}")
    print("-" * 80)
    
    # Rows
    for i, model in enumerate(comparison.experiments):
        print(
            f"{model:<20} "
            f"{comparison.success_rates[i]*100:>10.1f}% "
            f"{comparison.avg_attempts[i]:>10.1f} "
            f"{comparison.avg_retrieval_ms[i]:>13.0f} "
            f"{comparison.avg_generation_ms[i]:>10.0f} "
            f"{comparison.avg_total_ms[i]:>10.0f}"
        )
    
    print("=" * 80)


if __name__ == "__main__":
    # Example usage
    comparison = compare_models(
        models=["tinyllama_1_1b", "llama2_7b"],
        experiment="baseline"
    )
    print_model_comparison(comparison, "baseline")
