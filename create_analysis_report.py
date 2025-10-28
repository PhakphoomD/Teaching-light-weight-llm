"""
Analysis Report Generator

This script creates organized analysis reports with graphs and data tables
for selected experiments. Each report is stored in its own folder.
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
from typing import List, Dict, Any

class AnalysisReportGenerator:
    def __init__(self, results_dir: str = "results", output_dir: str = "analysis_reports"):
        self.results_dir = Path(results_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
    def list_available_experiments(self) -> Dict[str, List[str]]:
        """List all available experiments organized by model and strategy."""
        experiments = {}
        
        if not self.results_dir.exists():
            print(f"Results directory '{self.results_dir}' not found!")
            return experiments
            
        for model_dir in self.results_dir.iterdir():
            if not model_dir.is_dir() or model_dir.name == "tokens":
                continue
                
            experiments[model_dir.name] = []
            
            for strategy_dir in model_dir.iterdir():
                if not strategy_dir.is_dir():
                    continue
                    
                for run_dir in strategy_dir.iterdir():
                    if run_dir.is_dir() and run_dir.name.startswith("run_"):
                        exp_path = f"{model_dir.name}/{strategy_dir.name}/{run_dir.name}"
                        experiments[model_dir.name].append(exp_path)
        
        return experiments
    
    def display_experiments_menu(self, experiments: Dict[str, List[str]]) -> List[str]:
        """Display interactive menu for selecting experiments."""
        print("\n" + "="*70)
        print("Available Experiments")
        print("="*70)
        
        all_experiments = []
        idx = 1
        
        for model, exp_list in sorted(experiments.items()):
            print(f"\n{model.upper()}:")
            for exp in sorted(exp_list):
                parts = exp.split('/')
                strategy = parts[1]
                run = parts[2]
                print(f"  [{idx}] {strategy} - {run}")
                all_experiments.append(exp)
                idx += 1
        
        print("\n" + "="*70)
        print("Enter experiment numbers to analyze (comma-separated)")
        print("Example: 1,3,5  or  all  for all experiments")
        print("="*70)
        
        choice = input("\nYour selection: ").strip().lower()
        
        if choice == "all":
            return all_experiments
        
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            selected = [all_experiments[i] for i in indices if 0 <= i < len(all_experiments)]
            return selected
        except (ValueError, IndexError):
            print("Invalid selection. Please try again.")
            return []
    
    def load_experiment_data(self, exp_path: str) -> Dict[str, Any]:
        """Load experiment data from results directory."""
        full_path = self.results_dir / exp_path
        
        data = {
            "path": exp_path,
            "config": None,
            "summary": None,
            "results": []
        }
        
        # Load config
        config_file = full_path / "config.json"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                data["config"] = json.load(f)
        
        # Load summary
        summary_file = full_path / "summary.json"
        if summary_file.exists():
            with open(summary_file, 'r', encoding='utf-8') as f:
                data["summary"] = json.load(f)
        
        # Load detailed results
        results_file = full_path / "results.jsonl"
        if results_file.exists():
            with open(results_file, 'r', encoding='utf-8') as f:
                for line in f:
                    data["results"].append(json.loads(line.strip()))
        
        return data
    
    def create_report_folder(self, exp_paths: List[str]) -> Path:
        """Create a new report folder with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create a meaningful name based on experiments
        if len(exp_paths) == 1:
            parts = exp_paths[0].split('/')
            folder_name = f"{parts[0]}_{parts[1]}_{timestamp}"
        else:
            folder_name = f"comparison_{len(exp_paths)}_experiments_{timestamp}"
        
        report_dir = self.output_dir / folder_name
        report_dir.mkdir(exist_ok=True)
        
        return report_dir
    
    def generate_summary_table(self, experiments_data: List[Dict], report_dir: Path):
        """Generate summary table comparing experiments."""
        summary_data = []
        
        for exp_data in experiments_data:
            if exp_data["summary"]:
                summary = exp_data["summary"]
                parts = exp_data["path"].split('/')
                
                row = {
                    "Model": parts[0],
                    "Strategy": parts[1],
                    "Run": parts[2],
                    "Success Rate": f"{summary.get('success_rate', 0):.2%}",
                    "Avg Iterations": f"{summary.get('avg_iterations', 0):.2f}",
                    "Total Tasks": summary.get('total_tasks', 0),
                    "Successful": summary.get('successful_tasks', 0),
                    "Failed": summary.get('failed_tasks', 0)
                }
                
                if "avg_score" in summary:
                    row["Avg Score"] = f"{summary['avg_score']:.3f}"
                
                summary_data.append(row)
        
        # Save as CSV
        df = pd.DataFrame(summary_data)
        csv_path = report_dir / "summary_table.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        
        # Save as formatted text
        txt_path = report_dir / "summary_table.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("EXPERIMENT SUMMARY\n")
            f.write("="*80 + "\n\n")
            f.write(df.to_string(index=False))
            f.write("\n\n")
        
        print(f"  Summary table saved to: {csv_path.name} and {txt_path.name}")
        return df
    
    def generate_comparison_graphs(self, experiments_data: List[Dict], report_dir: Path):
        """Generate comparison graphs for multiple experiments."""
        
        # Extract data for plotting
        labels = []
        success_rates = []
        avg_iterations = []
        
        for exp_data in experiments_data:
            if exp_data["summary"]:
                parts = exp_data["path"].split('/')
                label = f"{parts[0]}\n{parts[1]}"
                labels.append(label)
                
                summary = exp_data["summary"]
                success_rates.append(summary.get('success_rate', 0) * 100)
                avg_iterations.append(summary.get('avg_iterations', 0))
        
        if not labels:
            print("  No data available for graphs")
            return
        
        # Create figure with subplots
        fig, axes = plt.subplots(2, 1, figsize=(12, 10))
        fig.suptitle('Experiment Comparison', fontsize=16, fontweight='bold')
        
        # Success Rate Graph
        ax1 = axes[0]
        bars1 = ax1.bar(range(len(labels)), success_rates, color='steelblue', alpha=0.7)
        ax1.set_xlabel('Experiments', fontsize=12)
        ax1.set_ylabel('Success Rate (%)', fontsize=12)
        ax1.set_title('Success Rate Comparison', fontsize=14)
        ax1.set_xticks(range(len(labels)))
        ax1.set_xticklabels(labels, rotation=45, ha='right')
        ax1.grid(axis='y', alpha=0.3)
        ax1.set_ylim([0, 100])
        
        # Add value labels on bars
        for bar in bars1:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}%', ha='center', va='bottom')
        
        # Average Iterations Graph
        ax2 = axes[1]
        bars2 = ax2.bar(range(len(labels)), avg_iterations, color='coral', alpha=0.7)
        ax2.set_xlabel('Experiments', fontsize=12)
        ax2.set_ylabel('Average Iterations', fontsize=12)
        ax2.set_title('Average Iterations Comparison', fontsize=14)
        ax2.set_xticks(range(len(labels)))
        ax2.set_xticklabels(labels, rotation=45, ha='right')
        ax2.grid(axis='y', alpha=0.3)
        
        # Add value labels on bars
        for bar in bars2:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}', ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save graph
        graph_path = report_dir / "comparison_graphs.png"
        plt.savefig(graph_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"  Comparison graphs saved to: {graph_path.name}")
    
    def generate_detailed_report(self, experiments_data: List[Dict], report_dir: Path):
        """Generate detailed report with all experiment information."""
        
        report_path = report_dir / "detailed_report.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("DETAILED EXPERIMENT REPORT\n")
            f.write("="*80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Number of Experiments: {len(experiments_data)}\n")
            f.write("="*80 + "\n\n")
            
            for i, exp_data in enumerate(experiments_data, 1):
                f.write(f"\n{'='*80}\n")
                f.write(f"EXPERIMENT {i}: {exp_data['path']}\n")
                f.write(f"{'='*80}\n\n")
                
                # Configuration
                if exp_data["config"]:
                    f.write("CONFIGURATION:\n")
                    f.write("-"*40 + "\n")
                    config = exp_data["config"]
                    for key, value in config.items():
                        if key != "results":
                            f.write(f"  {key}: {value}\n")
                    f.write("\n")
                
                # Summary Statistics
                if exp_data["summary"]:
                    f.write("SUMMARY STATISTICS:\n")
                    f.write("-"*40 + "\n")
                    summary = exp_data["summary"]
                    for key, value in summary.items():
                        if isinstance(value, float):
                            f.write(f"  {key}: {value:.4f}\n")
                        else:
                            f.write(f"  {key}: {value}\n")
                    f.write("\n")
                
                # Task Results
                if exp_data["results"]:
                    f.write(f"TASK RESULTS ({len(exp_data['results'])} tasks):\n")
                    f.write("-"*40 + "\n")
                    
                    for j, result in enumerate(exp_data["results"], 1):
                        status = "SUCCESS" if result.get("success", False) else "FAILED"
                        f.write(f"\n  Task {j}: {status}\n")
                        f.write(f"    Iterations: {result.get('num_iterations', 0)}\n")
                        
                        if "final_score" in result:
                            f.write(f"    Final Score: {result['final_score']:.3f}\n")
                        
                        if "question" in result:
                            question = result["question"][:100] + "..." if len(result["question"]) > 100 else result["question"]
                            f.write(f"    Question: {question}\n")
                
                f.write("\n")
        
        print(f"  Detailed report saved to: {report_path.name}")
    
    def generate_report(self, exp_paths: List[str]):
        """Generate complete analysis report for selected experiments."""
        
        if not exp_paths:
            print("No experiments selected.")
            return
        
        print(f"\nGenerating report for {len(exp_paths)} experiment(s)...")
        
        # Load all experiment data
        experiments_data = []
        for exp_path in exp_paths:
            print(f"  Loading: {exp_path}")
            data = self.load_experiment_data(exp_path)
            experiments_data.append(data)
        
        # Create report folder
        report_dir = self.create_report_folder(exp_paths)
        print(f"\nCreating report in: {report_dir.name}")
        
        # Generate summary table
        print("\nGenerating summary table...")
        self.generate_summary_table(experiments_data, report_dir)
        
        # Generate comparison graphs
        print("\nGenerating comparison graphs...")
        self.generate_comparison_graphs(experiments_data, report_dir)
        
        # Generate detailed report
        print("\nGenerating detailed report...")
        self.generate_detailed_report(experiments_data, report_dir)
        
        # Save experiment list
        list_path = report_dir / "experiments_analyzed.txt"
        with open(list_path, 'w', encoding='utf-8') as f:
            f.write("Experiments included in this report:\n\n")
            for exp_path in exp_paths:
                f.write(f"  - {exp_path}\n")
        
        print(f"\nReport generation complete!")
        print(f"Report location: {report_dir}")
        print(f"\nGenerated files:")
        print(f"  - summary_table.csv")
        print(f"  - summary_table.txt")
        print(f"  - comparison_graphs.png")
        print(f"  - detailed_report.txt")
        print(f"  - experiments_analyzed.txt")


def main():
    parser = argparse.ArgumentParser(description="Generate organized analysis reports")
    parser.add_argument("--results-dir", default="results", help="Results directory")
    parser.add_argument("--output-dir", default="analysis_reports", help="Output directory")
    parser.add_argument("--experiments", nargs="+", help="Specific experiments to analyze (e.g., tinyllama_1.1b/baseline/run_20251028_212825)")
    parser.add_argument("--non-interactive", action="store_true", help="Non-interactive mode (requires --experiments)")
    
    args = parser.parse_args()
    
    generator = AnalysisReportGenerator(args.results_dir, args.output_dir)
    
    # List available experiments
    experiments = generator.list_available_experiments()
    
    if not experiments:
        print("No experiments found in results directory.")
        return
    
    # Select experiments
    if args.experiments:
        selected = args.experiments
    elif args.non_interactive:
        print("Error: --non-interactive requires --experiments")
        return
    else:
        selected = generator.display_experiments_menu(experiments)
    
    if selected:
        generator.generate_report(selected)
    else:
        print("No experiments selected.")


if __name__ == "__main__":
    main()
