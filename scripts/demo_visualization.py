"""
Demo: Visualize Experiment Results

This script demonstrates the visualization capabilities by creating
sample visualizations from existing experiment results.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import from scripts
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from scripts.visualize_experiments import ExperimentVisualizer


def main():
    """Run visualization demo."""
    print("=" * 80)
    print("EXPERIMENT VISUALIZATION DEMO")
    print("=" * 80)
    print()
    
    # Initialize visualizer
    viz = ExperimentVisualizer(results_dir="results")
    
    # Load experiments
    print(" Loading experiments from results/...")
    experiments = viz.load_experiments(latest_only=True)
    
    if not experiments:
        print(" No experiments found in results/ directory")
        print()
        print("To generate experiments, run:")
        print("  python run_experiment.py")
        print()
        print("Or use the test data:")
        print("  Results should be in: results/[model]/[strategy]/run_*/summary.json")
        return
    
    print(f" Found {len(experiments)} experiment(s)")
    print()
    
    # Show loaded experiments
    print("Loaded Experiments:")
    for i, exp in enumerate(experiments, 1):
        print(f"  {i}. {exp['model']} - {exp['strategy']}")
        print(f"     Success Rate: {exp['summary'].get('success_rate', 0):.1%}")
        print(f"     Mean Score: {exp['summary'].get('mean_score', 0):.3f}")
        print()
    
    # Generate visualizations
    print("-" * 80)
    print(" Generating visualizations...")
    print()
    
    output_dir = "analysis_reports"
    viz.create_comprehensive_report(output_dir=output_dir)
    
    print()
    print("=" * 80)
    print(" DEMO COMPLETE!")
    print("=" * 80)
    print()
    print(f" Check the '{output_dir}/' directory for:")
    print("   • Performance comparison charts")
    print("   • Learning metrics visualization")
    print("   • Efficiency analysis graphs")
    print("   • Text summary report")
    print()


if __name__ == "__main__":
    main()
