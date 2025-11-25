"""
Reporting Module

This module provides tools for loading experiment results, computing comprehensive
metrics, and generating visualizations for analysis.

Functions:
- load_results: Load experiment results from JSONL files
- load_memory_store: Load teaching records from memory store
- compute_metrics: Calculate all metrics for experiment results
- generate_plots: Create visualization plots (accuracy, latency, tokens, etc.)
- generate_report: Create comprehensive markdown report

Supports:
- Text generation metrics (BLEU, ROUGE, F1, BERTScore)
- Retrieval metrics (Hit Rate, Precision@k, MRR, NDCG)
- Performance metrics (latency, tokens, cost estimation)
- Comparative analysis across experiments

Usage:
    >>> from src.eval.reports import load_results, compute_metrics, generate_plots
    >>> 
    >>> # Load experiment results
    >>> results = load_results("logs/experiments/20251109_004826_alpaca_20_adaptive")
    >>> 
    >>> # Compute metrics with ground truth
    >>> ground_truth = {"q1": "Paris", "q2": "London", ...}
    >>> metrics_df = compute_metrics(results, ground_truth)
    >>> 
    >>> # Generate plots
    >>> generate_plots(metrics_df, output_dir="logs/reports/")
"""

import json
import jsonlines
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False
    print("Warning: matplotlib/seaborn not available. Plotting features disabled.")
    print("Install with: pip install matplotlib seaborn")

from ..core.logger import get_logger
from . import metrics as text_metrics
from . import retrieval as retrieval_metrics

logger = get_logger("eval.reports")


def load_results(experiment_path: str) -> List[Dict]:
    """
    Load experiment results from JSONL run log or memory store.
    
    Args:
        experiment_path: Path to experiment directory or specific JSONL file
    
    Returns:
        List of result dictionaries
    
    Example:
        >>> results = load_results("logs/experiments/20251109_004826_alpaca_20_adaptive")
        >>> print(f"Loaded {len(results)} records")
        >>> print(results[0].keys())
    
    Raises:
        FileNotFoundError: If file or directory doesn't exist
        ValueError: If no JSONL files found
    """
    path = Path(experiment_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {experiment_path}")
    
    results = []
    
    if path.is_file() and path.suffix == '.jsonl':
        # Load specific JSONL file
        logger.info(f"Loading results from file: {path}")
        with jsonlines.open(path) as reader:
            for record in reader:
                results.append(record)
    
    elif path.is_dir():
        # Try loading from memory/store.jsonl
        memory_store = path / "memory" / "store.jsonl"
        if memory_store.exists():
            logger.info(f"Loading results from memory store: {memory_store}")
            with jsonlines.open(memory_store) as reader:
                for record in reader:
                    results.append(record)
        else:
            # Look for any JSONL files in the directory
            jsonl_files = list(path.glob("*.jsonl"))
            if not jsonl_files:
                raise ValueError(f"No JSONL files found in {experiment_path}")
            
            # Load from first JSONL file
            logger.info(f"Loading results from: {jsonl_files[0]}")
            with jsonlines.open(jsonl_files[0]) as reader:
                for record in reader:
                    results.append(record)
    
    else:
        raise ValueError(f"Invalid path: {experiment_path} (must be file or directory)")
    
    logger.info(f"Loaded {len(results)} records")
    return results


def load_memory_store(experiment_path: str) -> List[Dict]:
    """
    Load teaching records from memory store.
    
    Args:
        experiment_path: Path to experiment directory
    
    Returns:
        List of teaching records with question, answer, refined_answer, evaluation, etc.
    
    Example:
        >>> records = load_memory_store("logs/experiments/20251109_004826_alpaca_20_adaptive")
        >>> print(f"Teaching records: {len(records)}")
        >>> print(f"Average rounds: {sum(r.get('round', 0) for r in records) / len(records)}")
    """
    path = Path(experiment_path)
    memory_store = path / "memory" / "store.jsonl"
    
    if not memory_store.exists():
        raise FileNotFoundError(f"Memory store not found: {memory_store}")
    
    return load_results(str(memory_store))


def compute_metrics(
    results: List[Dict],
    ground_truth: Optional[Dict[str, str]] = None,
    compute_text_metrics: bool = True,
    compute_retrieval_metrics: bool = False
) -> pd.DataFrame:
    """
    Compute comprehensive metrics for experiment results.
    
    Args:
        results: List of result dictionaries from load_results()
        ground_truth: Optional dict mapping question/id -> expected answer
                     If None, only performance metrics are computed
        compute_text_metrics: Whether to compute BLEU, ROUGE, F1, etc. (requires ground_truth)
        compute_retrieval_metrics: Whether to compute retrieval metrics (requires retrieval data)
    
    Returns:
        pandas DataFrame with metrics for each result
    
    Metrics computed:
    - Performance: latency_ms, tokens_used, cost_estimate
    - Success: success (bool), improvement (initial vs final)
    - Text Quality (if ground_truth): exact_match, f1, bleu, rouge-1/2/l, bert_f1
    - Retrieval (if available): precision@k, recall@k, mrr, ndcg
    
    Example:
        >>> results = load_results("logs/experiments/...")
        >>> ground_truth = {"What is the capital of France?": "Paris", ...}
        >>> df = compute_metrics(results, ground_truth)
        >>> print(df[['question', 'success', 'f1', 'latency_ms', 'tokens_used']].head())
    """
    logger.info(f"Computing metrics for {len(results)} results")
    
    metrics_data = []
    
    for i, result in enumerate(results):
        # Handle different field names for tokens and latency
        tokens = result.get('tokens_used', result.get('tokens', 0))
        latency = result.get('total_latency_ms', result.get('latency_ms', 0))
        
        # Determine success from evaluation field
        eval_data = result.get('evaluation', '')
        if isinstance(eval_data, dict):
            success = eval_data.get('correct', False)
        elif isinstance(eval_data, str):
            success = 'correct' in eval_data.lower()
        else:
            success = result.get('success', False)
        
        record = {
            'index': i,
            'question': result.get('question', ''),
            'answer': result.get('answer', ''),
            'refined_answer': result.get('refined_answer', ''),
            'success': success,
            'round': result.get('round', 0),
            'latency_ms': latency,
            'tokens_used': tokens,
        }
        
        # Extract evaluation if available
        if 'evaluation' in result:
            eval_data = result['evaluation']
            # Handle both dict and string formats
            if isinstance(eval_data, dict):
                record['correct'] = eval_data.get('correct', False)
                record['reasoning'] = eval_data.get('reasoning', '')
            elif isinstance(eval_data, str):
                # Parse string evaluation (e.g., "correct" or "incorrect")
                record['correct'] = 'correct' in eval_data.lower()
                record['reasoning'] = result.get('reasoning', eval_data)
        
        # Compute text generation metrics if ground truth provided
        if ground_truth and compute_text_metrics:
            question = result.get('question', '')
            predicted = result.get('refined_answer') or result.get('answer', '')
            
            if question in ground_truth:
                reference = ground_truth[question]
                
                # Exact match
                record['exact_match'] = text_metrics.exact_match(predicted, reference)
                
                # F1 score
                record['f1'] = text_metrics.f1(predicted, reference)
                
                # BLEU
                record['bleu'] = text_metrics.bleu(predicted, reference)
                
                # ROUGE scores
                rouge = text_metrics.rouge_scores(predicted, reference)
                record['rouge-1'] = rouge['rouge-1']
                record['rouge-2'] = rouge['rouge-2']
                record['rouge-l'] = rouge['rouge-l']
                
                # BERTScore
                try:
                    bert_p, bert_r, bert_f1 = text_metrics.bert_precision_recall_f1(predicted, reference)
                    record['bert_precision'] = bert_p
                    record['bert_recall'] = bert_r
                    record['bert_f1'] = bert_f1
                except Exception as e:
                    logger.warning(f"BERTScore computation failed: {e}")
                    record['bert_precision'] = 0.0
                    record['bert_recall'] = 0.0
                    record['bert_f1'] = 0.0
        
        # Compute retrieval metrics if available
        if compute_retrieval_metrics and 'retrieved_context' in result:
            # Extract retrieved and relevant IDs
            retrieved_ids = result.get('retrieved_ids', [])
            relevant_ids = result.get('relevant_ids', [])
            
            if retrieved_ids and relevant_ids:
                k = len(retrieved_ids)
                record['hit_rate'] = retrieval_metrics.hit_rate([retrieved_ids], [set(relevant_ids)])[0]
                record[f'precision@{k}'] = retrieval_metrics.precision_at_k([retrieved_ids], [set(relevant_ids)], k)[0]
                record[f'recall@{k}'] = retrieval_metrics.recall_at_k([retrieved_ids], [set(relevant_ids)], k)[0]
                record['mrr'] = retrieval_metrics.mean_reciprocal_rank([retrieved_ids], [set(relevant_ids)])[0]
                record[f'ndcg@{k}'] = retrieval_metrics.ndcg_at_k([retrieved_ids], [set(relevant_ids)], k)[0]
        
        metrics_data.append(record)
    
    df = pd.DataFrame(metrics_data)
    
    # Add summary statistics
    logger.info(f"\n=== Metrics Summary ===")
    logger.info(f"Total records: {len(df)}")
    logger.info(f"Success rate: {df['success'].mean():.2%}")
    logger.info(f"Avg latency: {df['latency_ms'].mean():.1f} ms")
    logger.info(f"Avg tokens: {df['tokens_used'].mean():.1f}")
    
    if 'f1' in df.columns:
        logger.info(f"Avg F1: {df['f1'].mean():.3f}")
    if 'bleu' in df.columns:
        logger.info(f"Avg BLEU: {df['bleu'].mean():.3f}")
    
    return df


def generate_plots(
    df: pd.DataFrame,
    output_dir: str,
    experiment_name: str = "experiment"
) -> None:
    """
    Generate visualization plots for experiment analysis.
    
    Creates multiple plots:
    1. Success rate by round
    2. Latency distribution
    3. Token usage distribution
    4. Accuracy vs latency scatter
    5. Metric comparison (F1, BLEU, ROUGE) if available
    
    Uses Matplotlib and Seaborn for professional-quality plots.
    
    Args:
        df: DataFrame from compute_metrics()
        output_dir: Directory to save plots (e.g., "logs/reports/")
        experiment_name: Name for plot titles and filenames
    
    Example:
        >>> df = compute_metrics(results, ground_truth)
        >>> generate_plots(df, "logs/reports/", "alpaca_20_adaptive")
        Saved: logs/reports/alpaca_20_adaptive_success_by_round.png
        Saved: logs/reports/alpaca_20_adaptive_latency_dist.png
        ...
    
    Note:
        Requires matplotlib and seaborn installed.
        Install with: pip install matplotlib seaborn
    """
    if not PLOTTING_AVAILABLE:
        logger.error("Matplotlib/Seaborn not available. Cannot generate plots.")
        logger.info("Install with: pip install matplotlib seaborn")
        return
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Generating plots in {output_dir}")
    
    # Set style
    sns.set_style("whitegrid")
    plt.rcParams['figure.figsize'] = (10, 6)
    plt.rcParams['font.size'] = 10
    
    # 1. Success rate by round
    if 'round' in df.columns and 'success' in df.columns:
        plt.figure()
        success_by_round = df.groupby('round')['success'].mean()
        plt.plot(success_by_round.index, success_by_round.values, marker='o', linewidth=2)
        plt.xlabel('Refinement Round')
        plt.ylabel('Success Rate')
        plt.title(f'{experiment_name}: Success Rate by Round')
        plt.ylim(0, 1.0)
        plt.grid(True, alpha=0.3)
        
        filename = output_path / f"{experiment_name}_success_by_round.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved: {filename}")
    
    # 2. Latency distribution
    if 'latency_ms' in df.columns:
        plt.figure()
        plt.hist(df['latency_ms'], bins=30, edgecolor='black', alpha=0.7)
        plt.xlabel('Latency (ms)')
        plt.ylabel('Frequency')
        plt.title(f'{experiment_name}: Latency Distribution')
        plt.axvline(df['latency_ms'].mean(), color='red', linestyle='--', 
                   label=f'Mean: {df["latency_ms"].mean():.1f} ms')
        plt.legend()
        
        filename = output_path / f"{experiment_name}_latency_dist.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved: {filename}")
    
    # 3. Token usage distribution
    if 'tokens_used' in df.columns:
        plt.figure()
        plt.hist(df['tokens_used'], bins=30, edgecolor='black', alpha=0.7, color='green')
        plt.xlabel('Tokens Used')
        plt.ylabel('Frequency')
        plt.title(f'{experiment_name}: Token Usage Distribution')
        plt.axvline(df['tokens_used'].mean(), color='red', linestyle='--',
                   label=f'Mean: {df["tokens_used"].mean():.1f} tokens')
        plt.legend()
        
        filename = output_path / f"{experiment_name}_tokens_dist.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved: {filename}")
    
    # 4. Accuracy vs Latency scatter
    if 'success' in df.columns and 'latency_ms' in df.columns:
        plt.figure()
        colors = ['red' if not s else 'green' for s in df['success']]
        plt.scatter(df['latency_ms'], df['success'], c=colors, alpha=0.6, s=50)
        plt.xlabel('Latency (ms)')
        plt.ylabel('Success (0=Fail, 1=Pass)')
        plt.title(f'{experiment_name}: Success vs Latency')
        plt.yticks([0, 1], ['Fail', 'Pass'])
        plt.grid(True, alpha=0.3)
        
        filename = output_path / f"{experiment_name}_success_vs_latency.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved: {filename}")
    
    # 5. Metric comparison (if text metrics available)
    metric_cols = ['f1', 'bleu', 'rouge-1', 'rouge-2', 'rouge-l', 'bert_f1']
    available_metrics = [col for col in metric_cols if col in df.columns]
    
    if available_metrics:
        plt.figure()
        means = [df[col].mean() for col in available_metrics]
        stds = [df[col].std() for col in available_metrics]
        
        x_pos = np.arange(len(available_metrics))
        plt.bar(x_pos, means, yerr=stds, align='center', alpha=0.7, 
               capsize=10, color='skyblue', edgecolor='black')
        plt.xticks(x_pos, available_metrics, rotation=45, ha='right')
        plt.ylabel('Score')
        plt.title(f'{experiment_name}: Text Generation Metrics')
        plt.ylim(0, 1.0)
        plt.grid(True, alpha=0.3, axis='y')
        
        filename = output_path / f"{experiment_name}_metrics_comparison.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved: {filename}")
    
    # 6. Round distribution
    if 'round' in df.columns:
        plt.figure()
        round_counts = df['round'].value_counts().sort_index()
        plt.bar(round_counts.index, round_counts.values, color='coral', edgecolor='black')
        plt.xlabel('Refinement Round')
        plt.ylabel('Number of Questions')
        plt.title(f'{experiment_name}: Distribution of Refinement Rounds')
        plt.xticks(round_counts.index)
        plt.grid(True, alpha=0.3, axis='y')
        
        filename = output_path / f"{experiment_name}_round_dist.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved: {filename}")
    
    logger.info(f"All plots saved to {output_dir}")


def generate_report(
    experiment_path: str,
    ground_truth: Optional[Dict[str, str]] = None,
    output_dir: Optional[str] = None
) -> Tuple[pd.DataFrame, str]:
    """
    Generate comprehensive analysis report for an experiment.
    
    Performs full pipeline:
    1. Load results from experiment directory
    2. Compute all metrics
    3. Generate plots
    4. Create markdown report
    
    Args:
        experiment_path: Path to experiment directory
        ground_truth: Optional dict mapping questions -> expected answers
        output_dir: Optional output directory (default: experiment_path/analysis/)
    
    Returns:
        Tuple of (metrics_df, report_path)
    
    Example:
        >>> df, report = generate_report(
        ...     "logs/experiments/20251109_004826_alpaca_20_adaptive",
        ...     ground_truth={"What is the capital of France?": "Paris", ...}
        ... )
        >>> print(f"Report saved to: {report}")
        >>> print(df.describe())
    """
    experiment_path = Path(experiment_path)
    
    if output_dir is None:
        output_dir = experiment_path / "analysis"
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Generating report for experiment: {experiment_path.name}")
    
    # Load results
    results = load_memory_store(str(experiment_path))
    
    # Compute metrics
    df = compute_metrics(
        results,
        ground_truth=ground_truth,
        compute_text_metrics=(ground_truth is not None)
    )
    
    # Save metrics to CSV
    csv_path = output_dir / "metrics.csv"
    df.to_csv(csv_path, index=False)
    logger.info(f"Saved metrics CSV: {csv_path}")
    
    # Generate plots
    generate_plots(df, str(output_dir), experiment_name=experiment_path.name)
    
    # Create markdown report
    report_path = output_dir / "ANALYSIS_REPORT.md"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# Analysis Report: {experiment_path.name}\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Overview\n\n")
        f.write(f"- **Total Records**: {len(df)}\n")
        f.write(f"- **Success Rate**: {df['success'].mean():.2%}\n")
        f.write(f"- **Avg Latency**: {df['latency_ms'].mean():.1f} ms\n")
        f.write(f"- **Avg Tokens**: {df['tokens_used'].mean():.1f}\n")
        f.write(f"- **Avg Rounds**: {df['round'].mean():.2f}\n\n")
        
        if 'f1' in df.columns:
            f.write("## Text Generation Metrics\n\n")
            f.write(f"- **Exact Match**: {df['exact_match'].mean():.2%}\n")
            f.write(f"- **F1 Score**: {df['f1'].mean():.3f}\n")
            f.write(f"- **BLEU**: {df['bleu'].mean():.3f}\n")
            f.write(f"- **ROUGE-1**: {df['rouge-1'].mean():.3f}\n")
            f.write(f"- **ROUGE-2**: {df['rouge-2'].mean():.3f}\n")
            f.write(f"- **ROUGE-L**: {df['rouge-l'].mean():.3f}\n")
            if 'bert_f1' in df.columns:
                f.write(f"- **BERTScore F1**: {df['bert_f1'].mean():.3f}\n")
            f.write("\n")
        
        f.write("## Performance Distribution\n\n")
        f.write("### Latency Statistics\n")
        f.write(f"```\n{df['latency_ms'].describe()}\n```\n\n")
        
        f.write("### Token Usage Statistics\n")
        f.write(f"```\n{df['tokens_used'].describe()}\n```\n\n")
        
        f.write("## Visualizations\n\n")
        f.write("See generated plots in this directory:\n\n")
        
        plot_files = sorted(output_dir.glob("*.png"))
        for plot_file in plot_files:
            f.write(f"- `{plot_file.name}`\n")
        
        f.write("\n## Data Files\n\n")
        f.write(f"- Full metrics: `metrics.csv`\n")
        f.write(f"- Raw results: `{experiment_path}/memory/store.jsonl`\n")
    
    logger.info(f"Saved report: {report_path}")
    
    return df, str(report_path)
