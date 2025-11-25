"""
Experiment Visualization Tool

Creates plots comparing different experiment configurations.

Visualizations:
- Success Rate vs Token Usage
- Success Rate vs Latency
- Success Rate vs Rounds
- Token Usage Distribution
- Latency Distribution
- Configuration Impact (bar charts)

Usage:
    python -m src.analysis.visualize
    python -m src.analysis.visualize --experiments baseline memory_summary cot_enabled
    python -m src.analysis.visualize --output logs/analysis/plots
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
import argparse

# Try to import matplotlib
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import seaborn as sns
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not installed. Install with: pip install matplotlib seaborn")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logger import get_logger
from src.analysis.compare_experiments import load_experiment_summary, compute_comparison

logger = get_logger("analysis.visualize")


def setup_plot_style():
    """Set up consistent plot styling."""
    if not HAS_MATPLOTLIB:
        return
    
    sns.set_theme(style="whitegrid")
    plt.rcParams['figure.figsize'] = (12, 8)
    plt.rcParams['font.size'] = 10
    plt.rcParams['axes.labelsize'] = 12
    plt.rcParams['axes.titlesize'] = 14
    plt.rcParams['xtick.labelsize'] = 10
    plt.rcParams['ytick.labelsize'] = 10
    plt.rcParams['legend.fontsize'] = 10


def plot_success_vs_tokens(
    comparisons: List,
    output_dir: Path,
    show: bool = False
):
    """
    Plot success rate vs token usage.
    
    Args:
        comparisons: List of ExperimentComparison objects
        output_dir: Output directory for plots
        show: Whether to display plots interactively
    """
    if not HAS_MATPLOTLIB:
        logger.warning("Skipping plot (matplotlib not available)")
        return
    
    fig, ax = plt.subplots()
    
    # Extract data
    names = [c.name for c in comparisons]
    success_rates = [c.success_rate * 100 for c in comparisons]
    tokens = [c.avg_tokens_per_question for c in comparisons]
    
    # Create scatter plot
    scatter = ax.scatter(tokens, success_rates, s=200, alpha=0.6, c=range(len(names)), cmap='viridis')
    
    # Add labels for each point
    for i, name in enumerate(names):
        ax.annotate(name, (tokens[i], success_rates[i]), 
                   xytext=(5, 5), textcoords='offset points',
                   fontsize=9, alpha=0.8)
    
    ax.set_xlabel('Average Tokens per Question')
    ax.set_ylabel('Success Rate (%)')
    ax.set_title('Success Rate vs Token Usage')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_file = output_dir / 'success_vs_tokens.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    logger.info(f"Saved plot: {output_file}")
    
    if show:
        plt.show()
    plt.close()


def plot_success_vs_latency(
    comparisons: List,
    output_dir: Path,
    show: bool = False
):
    """
    Plot success rate vs latency.
    
    Args:
        comparisons: List of ExperimentComparison objects
        output_dir: Output directory for plots
        show: Whether to display plots interactively
    """
    if not HAS_MATPLOTLIB:
        logger.warning("Skipping plot (matplotlib not available)")
        return
    
    fig, ax = plt.subplots()
    
    names = [c.name for c in comparisons]
    success_rates = [c.success_rate * 100 for c in comparisons]
    latencies = [c.avg_latency_ms / 1000 for c in comparisons]  # Convert to seconds
    
    scatter = ax.scatter(latencies, success_rates, s=200, alpha=0.6, c=range(len(names)), cmap='plasma')
    
    for i, name in enumerate(names):
        ax.annotate(name, (latencies[i], success_rates[i]), 
                   xytext=(5, 5), textcoords='offset points',
                   fontsize=9, alpha=0.8)
    
    ax.set_xlabel('Average Latency (seconds)')
    ax.set_ylabel('Success Rate (%)')
    ax.set_title('Success Rate vs Latency')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_file = output_dir / 'success_vs_latency.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    logger.info(f"Saved plot: {output_file}")
    
    if show:
        plt.show()
    plt.close()


def plot_metrics_comparison(
    comparisons: List,
    output_dir: Path,
    show: bool = False
):
    """
    Plot bar chart comparing key metrics across experiments.
    
    Args:
        comparisons: List of ExperimentComparison objects
        output_dir: Output directory for plots
        show: Whether to display plots interactively
    """
    if not HAS_MATPLOTLIB:
        logger.warning("Skipping plot (matplotlib not available)")
        return
    
    # Sort by success rate
    comparisons = sorted(comparisons, key=lambda x: x.success_rate, reverse=True)
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    names = [c.name for c in comparisons]
    
    # Success Rate
    ax = axes[0, 0]
    success_rates = [c.success_rate * 100 for c in comparisons]
    bars = ax.barh(names, success_rates, color='skyblue')
    ax.set_xlabel('Success Rate (%)')
    ax.set_title('Success Rate Comparison')
    ax.grid(axis='x', alpha=0.3)
    
    # Add value labels
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2, 
               f'{width:.1f}%', ha='left', va='center', fontsize=9)
    
    # Token Usage
    ax = axes[0, 1]
    tokens = [c.avg_tokens_per_question for c in comparisons]
    bars = ax.barh(names, tokens, color='lightcoral')
    ax.set_xlabel('Avg Tokens per Question')
    ax.set_title('Token Usage Comparison')
    ax.grid(axis='x', alpha=0.3)
    
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2, 
               f'{width:.0f}', ha='left', va='center', fontsize=9)
    
    # Latency
    ax = axes[1, 0]
    latencies = [c.avg_latency_ms / 1000 for c in comparisons]
    bars = ax.barh(names, latencies, color='lightgreen')
    ax.set_xlabel('Avg Latency (seconds)')
    ax.set_title('Latency Comparison')
    ax.grid(axis='x', alpha=0.3)
    
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2, 
               f'{width:.2f}s', ha='left', va='center', fontsize=9)
    
    # Efficiency Score
    ax = axes[1, 1]
    efficiency = [c.efficiency_score for c in comparisons]
    bars = ax.barh(names, efficiency, color='plum')
    ax.set_xlabel('Efficiency Score (Success/1K tokens)')
    ax.set_title('Efficiency Comparison')
    ax.grid(axis='x', alpha=0.3)
    
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2, 
               f'{width:.4f}', ha='left', va='center', fontsize=9)
    
    plt.tight_layout()
    output_file = output_dir / 'metrics_comparison.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    logger.info(f"Saved plot: {output_file}")
    
    if show:
        plt.show()
    plt.close()


def plot_configuration_impact(
    comparisons: List,
    output_dir: Path,
    show: bool = False
):
    """
    Plot configuration impact relative to baseline.
    
    Args:
        comparisons: List of ExperimentComparison objects
        output_dir: Output directory for plots
        show: Whether to display plots interactively
    """
    if not HAS_MATPLOTLIB:
        logger.warning("Skipping plot (matplotlib not available)")
        return
    
    # Find baseline
    baseline = next((c for c in comparisons if 'baseline' in c.name.lower()), None)
    
    if baseline is None:
        logger.warning("No baseline found for configuration impact plot")
        return
    
    # Calculate deltas
    other_comps = [c for c in comparisons if c.name != baseline.name]
    
    if not other_comps:
        logger.warning("No other experiments to compare with baseline")
        return
    
    names = [c.name for c in other_comps]
    delta_success = [(c.success_rate - baseline.success_rate) * 100 for c in other_comps]
    delta_tokens = [((c.avg_tokens_per_question / baseline.avg_tokens_per_question) - 1) * 100 
                    if baseline.avg_tokens_per_question > 0 else 0 
                    for c in other_comps]
    delta_latency = [((c.avg_latency_ms / baseline.avg_latency_ms) - 1) * 100 
                     if baseline.avg_latency_ms > 0 else 0 
                     for c in other_comps]
    
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    
    # Success rate delta
    ax = axes[0]
    colors = ['green' if x > 0 else 'red' for x in delta_success]
    bars = ax.barh(names, delta_success, color=colors, alpha=0.6)
    ax.set_xlabel('Change in Success Rate (%)')
    ax.set_title(f'Success Rate Change (vs {baseline.name})')
    ax.axvline(x=0, color='black', linestyle='--', linewidth=1)
    ax.grid(axis='x', alpha=0.3)
    
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2, 
               f'{width:+.1f}%', ha='left' if width > 0 else 'right', 
               va='center', fontsize=9)
    
    # Token usage delta
    ax = axes[1]
    colors = ['green' if x < 0 else 'red' for x in delta_tokens]  # Lower is better
    bars = ax.barh(names, delta_tokens, color=colors, alpha=0.6)
    ax.set_xlabel('Change in Token Usage (%)')
    ax.set_title(f'Token Usage Change (vs {baseline.name})')
    ax.axvline(x=0, color='black', linestyle='--', linewidth=1)
    ax.grid(axis='x', alpha=0.3)
    
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2, 
               f'{width:+.1f}%', ha='left' if width > 0 else 'right', 
               va='center', fontsize=9)
    
    # Latency delta
    ax = axes[2]
    colors = ['green' if x < 0 else 'red' for x in delta_latency]  # Lower is better
    bars = ax.barh(names, delta_latency, color=colors, alpha=0.6)
    ax.set_xlabel('Change in Latency (%)')
    ax.set_title(f'Latency Change (vs {baseline.name})')
    ax.axvline(x=0, color='black', linestyle='--', linewidth=1)
    ax.grid(axis='x', alpha=0.3)
    
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2, 
               f'{width:+.1f}%', ha='left' if width > 0 else 'right', 
               va='center', fontsize=9)
    
    plt.tight_layout()
    output_file = output_dir / 'configuration_impact.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    logger.info(f"Saved plot: {output_file}")
    
    if show:
        plt.show()
    plt.close()


def create_all_plots(
    experiment_names: Optional[List[str]] = None,
    results_dir: str = "logs/experiments",
    output_dir: str = "logs/analysis/plots",
    show: bool = False
):
    """
    Create all visualization plots.
    
    Args:
        experiment_names: List of experiment names (None = all)
        results_dir: Directory containing results
        output_dir: Output directory for plots
        show: Whether to display plots interactively
    """
    if not HAS_MATPLOTLIB:
        logger.error("matplotlib is required for visualization. Install with: pip install matplotlib seaborn")
        return
    
    # Load experiments
    from src.analysis.compare_experiments import compare_experiments
    
    logger.info("Loading experiments...")
    comparisons = compare_experiments(experiment_names, results_dir)
    
    if not comparisons:
        logger.error("No experiments found")
        return
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Set up plotting style
    setup_plot_style()
    
    logger.info(f"Creating plots for {len(comparisons)} experiments...")
    
    # Generate plots
    plot_success_vs_tokens(comparisons, output_path, show)
    plot_success_vs_latency(comparisons, output_path, show)
    plot_metrics_comparison(comparisons, output_path, show)
    plot_configuration_impact(comparisons, output_path, show)
    
    logger.info(f"All plots saved to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Visualize experiment results",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--experiments',
        nargs='+',
        help='List of experiment names to visualize (default: all)'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='logs/experiments',
        help='Directory containing experiment results'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='logs/analysis/plots',
        help='Output directory for plots'
    )
    
    parser.add_argument(
        '--show',
        action='store_true',
        help='Display plots interactively'
    )
    
    args = parser.parse_args()
    
    create_all_plots(
        experiment_names=args.experiments,
        results_dir=args.results_dir,
        output_dir=args.output,
        show=args.show
    )


if __name__ == "__main__":
    main()
