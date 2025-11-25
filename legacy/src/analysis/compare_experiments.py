"""
Experiment Comparison Tool

Loads experiment summaries and computes comparison metrics across different configurations.

Usage:
    python -m src.analysis.compare_experiments
    python -m src.analysis.compare_experiments --experiments baseline memory_summary cot_enabled
    python -m src.analysis.compare_experiments --output logs/analysis/comparison_report.json
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logger import get_logger

logger = get_logger("analysis.compare")


@dataclass
class ExperimentComparison:
    """Comparison metrics between experiments."""
    name: str
    success_rate: float
    avg_rounds: float
    total_tokens: int
    avg_tokens_per_question: float
    avg_latency_ms: float
    total_time_minutes: float
    num_questions: int
    errors: int
    
    # Derived metrics
    efficiency_score: float  # success_rate / (avg_tokens_per_question / 1000)
    speed_score: float  # success_rate / (avg_latency_ms / 1000)
    cost_score: float  # success_rate * 1000 / avg_tokens_per_question


def load_experiment_summary(experiment_name: str, results_dir: str = "logs/experiments") -> Optional[Dict]:
    """
    Load experiment summary from JSON file.
    
    Args:
        experiment_name: Name of the experiment
        results_dir: Directory containing results
    
    Returns:
        Summary dictionary or None if not found
    """
    summary_file = Path(results_dir) / f"{experiment_name}_summary.json"
    
    if not summary_file.exists():
        logger.warning(f"Summary file not found: {summary_file}")
        return None
    
    with open(summary_file, 'r') as f:
        return json.load(f)


def compute_comparison(summary: Dict) -> ExperimentComparison:
    """
    Compute comparison metrics from experiment summary.
    
    Args:
        summary: Experiment summary dictionary
    
    Returns:
        ExperimentComparison object
    """
    perf = summary['performance']
    dataset = summary['dataset']
    
    success_rate = perf['success_rate']
    avg_tokens = perf['avg_tokens_per_question']
    avg_latency = perf['avg_latency_ms']
    
    # Derived metrics (higher is better)
    efficiency_score = success_rate / (avg_tokens / 1000) if avg_tokens > 0 else 0
    speed_score = success_rate / (avg_latency / 1000) if avg_latency > 0 else 0
    cost_score = (success_rate * 1000) / avg_tokens if avg_tokens > 0 else 0
    
    return ExperimentComparison(
        name=summary['experiment_name'],
        success_rate=success_rate,
        avg_rounds=perf['avg_rounds'],
        total_tokens=perf['total_tokens'],
        avg_tokens_per_question=avg_tokens,
        avg_latency_ms=avg_latency,
        total_time_minutes=perf['total_time_minutes'],
        num_questions=dataset['processed'],
        errors=dataset['errors'],
        efficiency_score=efficiency_score,
        speed_score=speed_score,
        cost_score=cost_score
    )


def compare_experiments(
    experiment_names: Optional[List[str]] = None,
    results_dir: str = "logs/experiments"
) -> List[ExperimentComparison]:
    """
    Compare multiple experiments.
    
    Args:
        experiment_names: List of experiment names (None = all experiments in results_dir)
        results_dir: Directory containing results
    
    Returns:
        List of ExperimentComparison objects
    """
    results_path = Path(results_dir)
    
    # Find all summary files if no names specified
    if experiment_names is None:
        summary_files = list(results_path.glob("*_summary.json"))
        experiment_names = [f.stem.replace("_summary", "") for f in summary_files]
        logger.info(f"Found {len(experiment_names)} experiments")
    
    comparisons = []
    for name in experiment_names:
        logger.info(f"Loading experiment: {name}")
        summary = load_experiment_summary(name, results_dir)
        
        if summary is None:
            logger.warning(f"Skipping {name}: summary not found")
            continue
        
        comparison = compute_comparison(summary)
        comparisons.append(comparison)
    
    return comparisons


def print_comparison_table(comparisons: List[ExperimentComparison]):
    """
    Print formatted comparison table.
    
    Args:
        comparisons: List of ExperimentComparison objects
    """
    # Sort by success rate (descending)
    comparisons = sorted(comparisons, key=lambda x: x.success_rate, reverse=True)
    
    print("\n" + "="*120)
    print("EXPERIMENT COMPARISON")
    print("="*120)
    print(f"{'Name':<25} {'Success':<10} {'Rounds':<8} {'Tokens':<12} {'Latency (s)':<12} {'Efficiency':<12} {'Speed':<12}")
    print("-"*120)
    
    for comp in comparisons:
        print(
            f"{comp.name:<25} "
            f"{comp.success_rate*100:>6.1f}%   "
            f"{comp.avg_rounds:>6.2f}  "
            f"{comp.avg_tokens_per_question:>10.0f}  "
            f"{comp.avg_latency_ms/1000:>10.2f}  "
            f"{comp.efficiency_score:>10.4f}  "
            f"{comp.speed_score:>10.4f}"
        )
    
    print("-"*120)
    print(f"Total experiments: {len(comparisons)}")
    print("="*120 + "\n")


def print_detailed_analysis(comparisons: List[ExperimentComparison]):
    """
    Print detailed analysis with rankings.
    
    Args:
        comparisons: List of ExperimentComparison objects
    """
    print("\n" + "="*80)
    print("DETAILED ANALYSIS")
    print("="*80)
    
    # Best success rate
    best_success = max(comparisons, key=lambda x: x.success_rate)
    print(f"\n  Highest Success Rate: {best_success.name}")
    print(f"   Success: {best_success.success_rate*100:.1f}%")
    
    # Most efficient (best success per token)
    best_efficiency = max(comparisons, key=lambda x: x.efficiency_score)
    print(f"\n  Most Efficient: {best_efficiency.name}")
    print(f"   Efficiency Score: {best_efficiency.efficiency_score:.4f}")
    print(f"   (Success rate per 1K tokens)")
    
    # Fastest
    best_speed = max(comparisons, key=lambda x: x.speed_score)
    print(f"\n  Fastest: {best_speed.name}")
    print(f"   Speed Score: {best_speed.speed_score:.4f}")
    print(f"   Avg Latency: {best_speed.avg_latency_ms/1000:.2f}s")
    
    # Best cost-effectiveness
    best_cost = max(comparisons, key=lambda x: x.cost_score)
    print(f"\n  Best Cost-Effectiveness: {best_cost.name}")
    print(f"   Cost Score: {best_cost.cost_score:.4f}")
    print(f"   (Success rate * 1000 / avg tokens)")
    
    # Token usage comparison
    print(f"\n  Token Usage:")
    for comp in sorted(comparisons, key=lambda x: x.avg_tokens_per_question):
        print(f"   {comp.name:<25} {comp.avg_tokens_per_question:>8.0f} tokens/question")
    
    # Latency comparison
    print(f"\n    Latency:")
    for comp in sorted(comparisons, key=lambda x: x.avg_latency_ms):
        print(f"   {comp.name:<25} {comp.avg_latency_ms/1000:>8.2f}s/question")
    
    print("\n" + "="*80 + "\n")


def analyze_config_impact(comparisons: List[ExperimentComparison]):
    """
    Analyze impact of different configuration choices.
    
    Args:
        comparisons: List of ExperimentComparison objects
    """
    print("\n" + "="*80)
    print("CONFIGURATION IMPACT ANALYSIS")
    print("="*80)
    
    # Find baseline for comparison
    baseline = next((c for c in comparisons if 'baseline' in c.name.lower()), None)
    
    if baseline is None:
        logger.warning("No baseline experiment found for comparison")
        return
    
    print(f"\nBaseline: {baseline.name}")
    print(f"  Success Rate: {baseline.success_rate*100:.1f}%")
    print(f"  Avg Tokens: {baseline.avg_tokens_per_question:.0f}")
    print(f"  Avg Latency: {baseline.avg_latency_ms/1000:.2f}s")
    
    print("\nComparison to Baseline:")
    print(f"{'Experiment':<25} {'  Success':<12} {'  Tokens':<12} {'  Latency':<12}")
    print("-"*80)
    
    for comp in comparisons:
        if comp.name == baseline.name:
            continue
        
        delta_success = (comp.success_rate - baseline.success_rate) * 100
        delta_tokens = ((comp.avg_tokens_per_question / baseline.avg_tokens_per_question) - 1) * 100 if baseline.avg_tokens_per_question > 0 else 0
        delta_latency = ((comp.avg_latency_ms / baseline.avg_latency_ms) - 1) * 100 if baseline.avg_latency_ms > 0 else 0
        
        success_indicator = " " if delta_success > 0 else " " if delta_success < 0 else "  "
        tokens_indicator = " " if delta_tokens < 0 else " " if delta_tokens > 0 else "  "
        latency_indicator = " " if delta_latency < 0 else " " if delta_latency > 0 else "  "
        
        print(
            f"{comp.name:<25} "
            f"{success_indicator} {delta_success:>7.1f}%  "
            f"{tokens_indicator} {delta_tokens:>7.1f}%  "
            f"{latency_indicator} {delta_latency:>7.1f}%"
        )
    
    print("="*80 + "\n")


def save_comparison_report(
    comparisons: List[ExperimentComparison],
    output_file: str = "logs/analysis/comparison_report.json"
):
    """
    Save comparison report to JSON file.
    
    Args:
        comparisons: List of ExperimentComparison objects
        output_file: Output file path
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    report = {
        'timestamp': Path(output_file).stat().st_ctime if output_path.exists() else None,
        'num_experiments': len(comparisons),
        'comparisons': [asdict(comp) for comp in comparisons],
        'rankings': {
            'success_rate': sorted([c.name for c in comparisons], key=lambda n: next(c.success_rate for c in comparisons if c.name == n), reverse=True),
            'efficiency': sorted([c.name for c in comparisons], key=lambda n: next(c.efficiency_score for c in comparisons if c.name == n), reverse=True),
            'speed': sorted([c.name for c in comparisons], key=lambda n: next(c.speed_score for c in comparisons if c.name == n), reverse=True),
            'cost': sorted([c.name for c in comparisons], key=lambda n: next(c.cost_score for c in comparisons if c.name == n), reverse=True)
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Saved comparison report to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Compare experiment results",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--experiments',
        nargs='+',
        help='List of experiment names to compare (default: all)'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='logs/experiments',
        help='Directory containing experiment results (default: logs/experiments)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='logs/analysis/comparison_report.json',
        help='Output file for comparison report (default: logs/analysis/comparison_report.json)'
    )
    
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save comparison report to file'
    )
    
    args = parser.parse_args()
    
    # Load and compare experiments
    logger.info("Loading experiments...")
    comparisons = compare_experiments(
        experiment_names=args.experiments,
        results_dir=args.results_dir
    )
    
    if not comparisons:
        logger.error("No experiments found to compare")
        sys.exit(1)
    
    # Print comparison table
    print_comparison_table(comparisons)
    
    # Print detailed analysis
    print_detailed_analysis(comparisons)
    
    # Analyze configuration impact
    analyze_config_impact(comparisons)
    
    # Save report
    if not args.no_save:
        save_comparison_report(comparisons, args.output)
    
    logger.info("Comparison complete!")


if __name__ == "__main__":
    main()
