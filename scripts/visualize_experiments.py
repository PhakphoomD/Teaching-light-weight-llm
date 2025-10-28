"""
Comprehensive Experiment Visualization

Load all experiment summaries and create comprehensive visualizations.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
from datetime import datetime


class ExperimentVisualizer:
    """Visualize multiple experiment results."""
    
    def __init__(self, results_dir: str = "results"):
        """
        Initialize visualizer.
        
        Args:
            results_dir: Base results directory
        """
        self.results_dir = Path(results_dir)
        self.experiments = []
        
    def load_experiments(
        self,
        model_name: Optional[str] = None,
        strategy_name: Optional[str] = None,
        latest_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Load experiment summaries from results directory.
        
        Args:
            model_name: Filter by model (None = all models)
            strategy_name: Filter by strategy (None = all strategies)
            latest_only: Only load latest run for each model/strategy combo
            
        Returns:
            List of experiment data dictionaries
        """
        experiments = []
        
        if not self.results_dir.exists():
            print(f"Results directory not found: {self.results_dir}")
            return experiments
        
        # Iterate through model directories
        for model_dir in self.results_dir.iterdir():
            if not model_dir.is_dir():
                continue
            
            if model_name and model_dir.name != model_name:
                continue
            
            # Iterate through strategy directories
            for strategy_dir in model_dir.iterdir():
                if not strategy_dir.is_dir():
                    continue
                
                if strategy_name and strategy_dir.name != strategy_name:
                    continue
                
                # Find run directories
                runs = sorted([d for d in strategy_dir.iterdir() if d.is_dir() and d.name.startswith("run_")])
                
                if not runs:
                    continue
                
                # Get latest or all runs
                target_runs = [runs[-1]] if latest_only else runs
                
                for run_dir in target_runs:
                    summary_file = run_dir / "summary.json"
                    if not summary_file.exists():
                        continue
                    
                    try:
                        with open(summary_file, 'r', encoding='utf-8') as f:
                            summary = json.load(f)
                        
                        experiments.append({
                            'model': model_dir.name,
                            'strategy': strategy_dir.name,
                            'run': run_dir.name,
                            'path': str(run_dir),
                            'summary': summary
                        })
                    except Exception as e:
                        print(f"Error loading {summary_file}: {e}")
        
        self.experiments = experiments
        return experiments
    
    def create_performance_chart(self, output_file: str = "performance_comparison.png"):
        """Create performance metrics comparison chart."""
        if not self.experiments:
            print("No experiments loaded")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Performance Metrics Comparison', fontsize=16, fontweight='bold')
        
        # Extract data
        labels = [f"{exp['model']}\n{exp['strategy']}" for exp in self.experiments]
        success_rates = [exp['summary'].get('success_rate', 0) * 100 for exp in self.experiments]
        mean_scores = [exp['summary'].get('mean_score', 0) for exp in self.experiments]
        first_pass_rates = [exp['summary'].get('first_attempt_pass_rate', 0) * 100 for exp in self.experiments]
        avg_attempts = [exp['summary'].get('avg_attempts', 0) for exp in self.experiments]
        
        # Plot 1: Success Rate
        axes[0, 0].bar(range(len(labels)), success_rates, color='green', alpha=0.7)
        axes[0, 0].set_title('Success Rate (%)')
        axes[0, 0].set_ylabel('Success Rate (%)')
        axes[0, 0].set_xticks(range(len(labels)))
        axes[0, 0].set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        axes[0, 0].grid(axis='y', alpha=0.3)
        
        # Plot 2: Mean Score
        axes[0, 1].bar(range(len(labels)), mean_scores, color='blue', alpha=0.7)
        axes[0, 1].set_title('Mean Score')
        axes[0, 1].set_ylabel('Mean Score (0-1)')
        axes[0, 1].set_xticks(range(len(labels)))
        axes[0, 1].set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        axes[0, 1].grid(axis='y', alpha=0.3)
        
        # Plot 3: First Pass Rate
        axes[1, 0].bar(range(len(labels)), first_pass_rates, color='orange', alpha=0.7)
        axes[1, 0].set_title('First Attempt Pass Rate (%)')
        axes[1, 0].set_ylabel('Pass Rate (%)')
        axes[1, 0].set_xticks(range(len(labels)))
        axes[1, 0].set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        axes[1, 0].grid(axis='y', alpha=0.3)
        
        # Plot 4: Average Attempts
        axes[1, 1].bar(range(len(labels)), avg_attempts, color='red', alpha=0.7)
        axes[1, 1].set_title('Average Attempts')
        axes[1, 1].set_ylabel('Attempts')
        axes[1, 1].set_xticks(range(len(labels)))
        axes[1, 1].set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        axes[1, 1].grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f" Performance chart saved: {output_file}")
        plt.close()
    
    def create_learning_chart(self, output_file: str = "learning_comparison.png"):
        """Create learning metrics comparison chart."""
        if not self.experiments:
            print("No experiments loaded")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Learning & Generalisation Metrics', fontsize=16, fontweight='bold')
        
        labels = [f"{exp['model']}\n{exp['strategy']}" for exp in self.experiments]
        learning_gains = [exp['summary'].get('learning_gain', 0) for exp in self.experiments]
        repeat_errors = [exp['summary'].get('repeat_error_rate', 0) * 100 for exp in self.experiments]
        memory_util = [exp['summary'].get('memory_utilization_rate', 0) * 100 for exp in self.experiments]
        transfer = [exp['summary'].get('cross_task_transfer', 0) * 100 for exp in self.experiments]
        
        # Plot 1: Learning Gain
        colors = ['green' if x > 0 else 'red' for x in learning_gains]
        axes[0, 0].bar(range(len(labels)), learning_gains, color=colors, alpha=0.7)
        axes[0, 0].set_title('Learning Gain (ΔScore per attempt)')
        axes[0, 0].set_ylabel('ΔScore')
        axes[0, 0].set_xticks(range(len(labels)))
        axes[0, 0].set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        axes[0, 0].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        axes[0, 0].grid(axis='y', alpha=0.3)
        
        # Plot 2: Repeat Error Rate
        axes[0, 1].bar(range(len(labels)), repeat_errors, color='red', alpha=0.7)
        axes[0, 1].set_title('Repeat Error Rate (%)')
        axes[0, 1].set_ylabel('Error Rate (%)')
        axes[0, 1].set_xticks(range(len(labels)))
        axes[0, 1].set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        axes[0, 1].grid(axis='y', alpha=0.3)
        
        # Plot 3: Memory Utilization
        axes[1, 0].bar(range(len(labels)), memory_util, color='purple', alpha=0.7)
        axes[1, 0].set_title('Memory Utilization Rate (%)')
        axes[1, 0].set_ylabel('Utilization (%)')
        axes[1, 0].set_xticks(range(len(labels)))
        axes[1, 0].set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        axes[1, 0].grid(axis='y', alpha=0.3)
        
        # Plot 4: Cross-Task Transfer
        axes[1, 1].bar(range(len(labels)), transfer, color='cyan', alpha=0.7)
        axes[1, 1].set_title('Cross-Task Transfer (%)')
        axes[1, 1].set_ylabel('Transfer Rate (%)')
        axes[1, 1].set_xticks(range(len(labels)))
        axes[1, 1].set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        axes[1, 1].grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f" Learning chart saved: {output_file}")
        plt.close()
    
    def create_efficiency_chart(self, output_file: str = "efficiency_comparison.png"):
        """Create efficiency metrics comparison chart."""
        if not self.experiments:
            print("No experiments loaded")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Efficiency Metrics', fontsize=16, fontweight='bold')
        
        labels = [f"{exp['model']}\n{exp['strategy']}" for exp in self.experiments]
        tokens_per_task = [exp['summary'].get('tokens_per_task', 0) for exp in self.experiments]
        tokens_per_success = [exp['summary'].get('tokens_per_success', 0) for exp in self.experiments]
        latency = [exp['summary'].get('latency_per_task_ms', 0) for exp in self.experiments]
        runtime = [exp['summary'].get('total_runtime_s', 0) for exp in self.experiments]
        
        # Plot 1: Tokens per Task
        axes[0, 0].bar(range(len(labels)), tokens_per_task, color='blue', alpha=0.7)
        axes[0, 0].set_title('Tokens per Task')
        axes[0, 0].set_ylabel('Tokens')
        axes[0, 0].set_xticks(range(len(labels)))
        axes[0, 0].set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        axes[0, 0].grid(axis='y', alpha=0.3)
        
        # Plot 2: Tokens per Success
        axes[0, 1].bar(range(len(labels)), tokens_per_success, color='green', alpha=0.7)
        axes[0, 1].set_title('Tokens per Success')
        axes[0, 1].set_ylabel('Tokens')
        axes[0, 1].set_xticks(range(len(labels)))
        axes[0, 1].set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        axes[0, 1].grid(axis='y', alpha=0.3)
        
        # Plot 3: Latency per Task
        axes[1, 0].bar(range(len(labels)), latency, color='orange', alpha=0.7)
        axes[1, 0].set_title('Latency per Task (ms)')
        axes[1, 0].set_ylabel('Latency (ms)')
        axes[1, 0].set_xticks(range(len(labels)))
        axes[1, 0].set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        axes[1, 0].grid(axis='y', alpha=0.3)
        
        # Plot 4: Total Runtime
        axes[1, 1].bar(range(len(labels)), runtime, color='red', alpha=0.7)
        axes[1, 1].set_title('Total Runtime (seconds)')
        axes[1, 1].set_ylabel('Runtime (s)')
        axes[1, 1].set_xticks(range(len(labels)))
        axes[1, 1].set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        axes[1, 1].grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f" Efficiency chart saved: {output_file}")
        plt.close()
    
    def create_comprehensive_report(self, output_dir: str = "analysis_reports"):
        """Create all charts and save to directory."""
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print(f"\n Generating comprehensive visualization report...")
        print(f"Loaded {len(self.experiments)} experiments")
        
        # Create all charts
        self.create_performance_chart(os.path.join(output_dir, f"performance_{timestamp}.png"))
        self.create_learning_chart(os.path.join(output_dir, f"learning_{timestamp}.png"))
        self.create_efficiency_chart(os.path.join(output_dir, f"efficiency_{timestamp}.png"))
        
        # Create summary text report
        report_file = os.path.join(output_dir, f"summary_{timestamp}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("EXPERIMENT SUMMARY REPORT\n")
            f.write("=" * 80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Experiments: {len(self.experiments)}\n\n")
            
            for exp in self.experiments:
                f.write("-" * 80 + "\n")
                f.write(f"Model: {exp['model']}\n")
                f.write(f"Strategy: {exp['strategy']}\n")
                f.write(f"Run: {exp['run']}\n")
                f.write(f"Path: {exp['path']}\n\n")
                
                s = exp['summary']
                f.write(f"Performance:\n")
                f.write(f"  Success Rate: {s.get('success_rate', 0):.1%}\n")
                f.write(f"  Mean Score: {s.get('mean_score', 0):.3f}\n")
                f.write(f"  First Pass Rate: {s.get('first_attempt_pass_rate', 0):.1%}\n\n")
                
                f.write(f"Learning:\n")
                f.write(f"  Learning Gain: {s.get('learning_gain', 0):+.3f}\n")
                f.write(f"  Repeat Error Rate: {s.get('repeat_error_rate', 0):.1%}\n")
                f.write(f"  Memory Utilization: {s.get('memory_utilization_rate', 0):.1%}\n")
                f.write(f"  Cross-Task Transfer: {s.get('cross_task_transfer', 0):.1%}\n\n")
                
                f.write(f"Efficiency:\n")
                f.write(f"  Tokens/Task: {s.get('tokens_per_task', 0):.0f}\n")
                f.write(f"  Tokens/Success: {s.get('tokens_per_success', 0):.0f}\n")
                f.write(f"  Latency: {s.get('latency_per_task_ms', 0):.1f}ms\n")
                f.write(f"  Runtime: {s.get('total_runtime_s', 0):.1f}s\n\n")
        
        print(f" Summary report saved: {report_file}")
        print(f"\n All reports saved to: {output_dir}/")
        print(f"   - performance_{timestamp}.png")
        print(f"   - learning_{timestamp}.png")
        print(f"   - efficiency_{timestamp}.png")
        print(f"   - summary_{timestamp}.txt")


def main():
    """Main entry point for visualization."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Visualize experiment results")
    parser.add_argument('--model', type=str, help='Filter by model name')
    parser.add_argument('--strategy', type=str, help='Filter by strategy name')
    parser.add_argument('--output', type=str, default='analysis_reports', help='Output directory')
    parser.add_argument('--all-runs', action='store_true', help='Include all runs (not just latest)')
    
    args = parser.parse_args()
    
    viz = ExperimentVisualizer()
    experiments = viz.load_experiments(
        model_name=args.model,
        strategy_name=args.strategy,
        latest_only=not args.all_runs
    )
    
    if not experiments:
        print(" No experiments found!")
        print("\nTip: Make sure you have run some experiments first:")
        print("  python run_experiment.py")
        return
    
    viz.create_comprehensive_report(output_dir=args.output)


if __name__ == "__main__":
    main()
