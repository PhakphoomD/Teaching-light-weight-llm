"""
Hyperparameter Tuning Module

This module implements hyperparameter search strategies (grid and random)
to find optimal configuration for the teaching system.

Parameters tuned:
- temperature: Sampling temperature (0.0-1.0)
- max_tokens: Maximum output tokens
- max_attempts: Maximum refinement rounds
- memory_k: Top-k similar examples from memory

Usage:
    python -m src.experiments.tuning --strategy grid --params temperature max_tokens --limit 20
    python -m src.experiments.tuning --strategy random --n-trials 15 --limit 30
"""

import argparse
import json
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from itertools import product
import logging

from src.core.console import (
    print_header,
    print_info,
    print_success,
    print_error,
    print_warning,
    create_progress_bar,
    setup_rich_logging
)
from src.refinement.settings import SETTINGS
from src.providers.factory import build_client
from src.memory.store import MemoryStore
from src.memory.vector import VectorIndex
from src.critic.model import TeacherCritic
from src.eval.metrics import compute_all_metrics
from src.refinement.loop import run_loop
import jsonlines

# Setup logging
setup_rich_logging()
logger = logging.getLogger(__name__)


# ============================================================================
# Hyperparameter Search Space
# ============================================================================

PARAM_GRID = {
    "temperature": [0.0, 0.2, 0.5, 0.7, 1.0],
    "max_tokens": [128, 256, 512, 1024],
    "max_attempts": [2, 3, 5],
    "memory_k": [3, 5, 10]
}

PARAM_DESCRIPTIONS = {
    "temperature": "Sampling temperature (0.0=deterministic, 1.0=creative)",
    "max_tokens": "Maximum tokens in student output",
    "max_attempts": "Maximum refinement rounds",
    "memory_k": "Top-k similar examples from memory"
}


def validate_param_names(params: List[str]) -> None:
    """Validate that param names are in PARAM_GRID."""
    valid_params = set(PARAM_GRID.keys())
    invalid = [p for p in params if p not in valid_params]
    
    if invalid:
        raise ValueError(
            f"Invalid parameter names: {invalid}\n"
            f"Valid parameters: {list(valid_params)}"
        )


# ============================================================================
# Search Strategies
# ============================================================================

def grid_search(
    param_grid: Dict[str, List],
    limit: int = 20
) -> List[Tuple[Dict[str, Any], int]]:
    """
    Exhaustive grid search over parameter space.
    
    Args:
        param_grid: Dictionary mapping param names to value lists
        limit: Number of questions per configuration
    
    Returns:
        List of (config, trial_id) tuples
    
    Example:
        >>> grid = {"temperature": [0.2, 0.5], "max_tokens": [256, 512]}
        >>> configs = grid_search(grid)
        >>> len(configs)
        4  # 2 x 2 = 4 configurations
    """
    param_names = list(param_grid.keys())
    param_values = [param_grid[k] for k in param_names]
    
    configs = []
    for trial_id, values in enumerate(product(*param_values), 1):
        config = dict(zip(param_names, values))
        configs.append((config, trial_id))
    
    return configs


def random_search(
    param_grid: Dict[str, List],
    n_trials: int = 10,
    limit: int = 20
) -> List[Tuple[Dict[str, Any], int]]:
    """
    Random sampling of parameter space.
    
    Args:
        param_grid: Dictionary mapping param names to value lists
        n_trials: Number of random configurations to try
        limit: Number of questions per configuration
    
    Returns:
        List of (config, trial_id) tuples
    
    Example:
        >>> grid = {"temperature": [0.2, 0.5, 0.7], "max_tokens": [256, 512]}
        >>> configs = random_search(grid, n_trials=5)
        >>> len(configs)
        5
    """
    configs = []
    for trial_id in range(1, n_trials + 1):
        config = {
            param: random.choice(values)
            for param, values in param_grid.items()
        }
        configs.append((config, trial_id))
    
    return configs


# ============================================================================
# Tuning Runner
# ============================================================================

def load_dataset(dataset_path: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Load dataset from JSONL file."""
    dataset_file = Path(dataset_path)
    
    if not dataset_file.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_file}")
    
    questions = []
    with jsonlines.open(dataset_file) as reader:
        for i, record in enumerate(reader):
            if limit and i >= limit:
                break
            questions.append(record)
    
    logger.info(f"Loaded {len(questions)} questions from {dataset_file}")
    return questions


def run_tuning_trial(
    trial_id: int,
    config: Dict[str, Any],
    questions: List[Dict[str, Any]],
    student_client,
    teacher_client,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Run one tuning trial with specific hyperparameters.
    
    Args:
        trial_id: Trial number
        config: Hyperparameter configuration
        questions: List of questions to test
        student_client: Student LLM client
        teacher_client: Teacher LLM client
        verbose: Show detailed output
    
    Returns:
        Dictionary with trial results
    """
    config_str = ", ".join([f"{k}={v}" for k, v in config.items()])
    print_info(f"Trial {trial_id}: {config_str}")
    
    # Create fresh memory store and index for THIS trial
    import tempfile
    import os
    
    temp_dir = tempfile.gettempdir()
    store_path = os.path.join(temp_dir, f"tuning_store_trial{trial_id}.jsonl")
    index_path = os.path.join(temp_dir, f"tuning_index_trial{trial_id}.faiss")
    
    # Delete old files to ensure clean slate
    if os.path.exists(store_path):
        os.remove(store_path)
    if os.path.exists(index_path):
        os.remove(index_path)
    
    store = MemoryStore(store_path)
    index = VectorIndex(
        embedding_model="all-MiniLM-L6-v2",
        index_path=index_path
    )
    
    # Create teacher critic
    teacher = TeacherCritic(
        provider="gemini",
        model_name=teacher_client.model_name if hasattr(teacher_client, 'model_name') else get_teacher_model_name()
    )
    
    # Prepare run_loop config with hyperparameters
    loop_config = {
        "student_client": student_client,
        "teacher_client": teacher_client,
        "max_rounds": config.get("max_attempts", 3),
        "k": config.get("memory_k", 5),
        "memory_type": "raw",
        "use_cot_student": False,
        "use_cot_teacher": False,
        "student_temperature": config.get("temperature", 0.7),
        "teacher_temperature": 0.2,
        "verbose": verbose
    }
    
    # Note: max_tokens is passed to chat() calls, not run_loop config
    # We'll need to modify run_loop to accept max_tokens parameter
    # For now, use default (512)
    
    # Results collector
    results = []
    total_tokens = 0
    total_latency = 0
    metrics_sum = {
        "exact_match": 0.0,
        "f1": 0.0,
        "bleu": 0.0,
        "rouge_l": 0.0,
        "bert_f1": 0.0
    }
    
    # Progress bar
    progress = None
    task = None
    if not verbose:
        progress = create_progress_bar(f"Trial {trial_id}")
        if progress:
            progress.start()
            task = progress.add_task(
                f"[cyan]Trial {trial_id}",
                total=len(questions)
            )
    
    # Run each question
    experiment_id = f"tuning_trial{trial_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    for idx, q in enumerate(questions, 1):
        question_text = q.get('question', '')
        reference = q.get('reference', '')
        question_id = q.get('id', f'q{idx}')
        
        try:
            # Run refinement loop
            result = run_loop(
                question=question_text,
                config=loop_config,
                store=store,
                index=index,
                critic=teacher,
                experiment_id=experiment_id,
                question_id=question_id,
                correct_answer=reference
            )
            
            # Compute final metrics
            final_answer = result.get('final_answer', '')
            if reference and final_answer:
                metrics = compute_all_metrics(final_answer, reference)
            else:
                metrics = {}
            
            # Accumulate
            total_tokens += result.get('total_tokens', 0)
            total_latency += result.get('total_latency_ms', 0)
            
            for key in metrics_sum:
                metrics_sum[key] += metrics.get(key, 0)
            
            results.append({
                "question_id": question_id,
                "success": result.get('success', False),
                "num_rounds": result.get('num_rounds', 0),
                "improvement": result.get('improvement', False),
                "metrics": metrics,
                "tokens": result.get('total_tokens', 0),
                "latency_ms": result.get('total_latency_ms', 0)
            })
            
            if verbose:
                print_info(f"[{idx}/{len(questions)}] {question_id}: F1={metrics.get('f1', 0):.3f}")
        
        except Exception as e:
            logger.error(f"Error processing {question_id}: {e}")
            results.append({
                "question_id": question_id,
                "error": str(e)
            })
        
        # Update progress
        if progress and task is not None:
            progress.update(task, advance=1)
    
    if progress:
        progress.stop()
    
    # Calculate aggregates
    successful = [r for r in results if r.get('success', False)]
    success_rate = len(successful) / len(results) if results else 0
    
    avg_metrics = {
        key: val / len(results) if results else 0
        for key, val in metrics_sum.items()
    }
    
    summary = {
        "trial_id": trial_id,
        "config": config,
        "questions_tested": len(results),
        "success_count": len(successful),
        "success_rate": success_rate,
        "avg_metrics": avg_metrics,
        "total_tokens": total_tokens,
        "total_latency_ms": total_latency,
        "avg_latency_ms": total_latency / len(results) if results else 0,
        "results": results
    }
    
    print_success(f"Trial {trial_id} complete: F1={avg_metrics['f1']:.3f}, Success={success_rate:.1%}")
    
    return summary


# ============================================================================
# CLI and Main
# ============================================================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Hyperparameter Tuning - Find optimal configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Search Strategies:
  grid   - Exhaustive grid search (tests all combinations)
  random - Random sampling (faster, good for large spaces)

Parameters:
  temperature   - Sampling temperature (0.0-1.0)
  max_tokens    - Maximum output tokens
  max_attempts  - Maximum refinement rounds
  memory_k      - Top-k similar examples

Examples:
  # Grid search over temperature and max_tokens
  python -m experiments.tuning --strategy grid --params temperature max_tokens --limit 20
  
  # Random search with 15 trials
  python -m experiments.tuning --strategy random --n-trials 15 --limit 30
  
  # Tune all parameters with grid search
  python -m experiments.tuning --strategy grid --limit 10
        """
    )
    
    parser.add_argument(
        "--strategy",
        choices=["grid", "random"],
        default="grid",
        help="Search strategy (default: grid)"
    )
    
    parser.add_argument(
        "--params",
        nargs="+",
        help="Parameters to tune (default: all). Options: temperature, max_tokens, max_attempts, memory_k"
    )
    
    parser.add_argument(
        "--n-trials",
        type=int,
        default=10,
        help="Number of trials for random search (default: 10)"
    )
    
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/alpaca_20.jsonl",
        help="Path to dataset file"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of questions per trial"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="logs/analysis/tuning_report",
        help="Output file prefix"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output"
    )
    
    parser.add_argument(
        "--student-model",
        type=str,
        default="local",
        help="Student model provider"
    )
    
    parser.add_argument(
        "--teacher-model",
        type=str,
        default="g25_flash_lite",
        help="Teacher model name from models.yml"
    )
    
    return parser.parse_args()


def run_tuning(
    strategy: str = "grid",
    params: Optional[List[str]] = None,
    n_trials: int = 10,
    dataset: str = "data/alpaca_20.jsonl",
    limit: int = 20,
    output: str = "logs/analysis/tuning_report",
    verbose: bool = False,
    student_model: str = "local",
    teacher_model: str = "g25_flash_lite"
):
    """
    Run hyperparameter tuning.
    
    This is the main entry point that can be called from cli.hub
    or directly from command line.
    """
    print_header(f"Hyperparameter Tuning ({strategy.upper()} Search)")
    
    # Filter parameter grid
    if params:
        validate_param_names(params)
        param_grid = {k: v for k, v in PARAM_GRID.items() if k in params}
        print_info(f"Tuning parameters: {', '.join(params)}")
    else:
        param_grid = PARAM_GRID
        print_info("Tuning all parameters")
    
    for param, values in param_grid.items():
        print_info(f"  {param}: {values} ({PARAM_DESCRIPTIONS[param]})")
    
    # Generate configurations
    if strategy == "grid":
        configs = grid_search(param_grid, limit)
        print_info(f"Grid search: {len(configs)} configurations")
    else:
        configs = random_search(param_grid, n_trials, limit)
        print_info(f"Random search: {n_trials} trials")
    
    # Load configurations
    print_info("Loading model configurations...")
    models_config = load_models_config()
    
    teacher_config = models_config.get('teachers', {}).get(teacher_model)
    if not teacher_config:
        print_error(f"Teacher model '{teacher_model}' not found in models.yml")
        return
    
    # Initialize clients
    print_info(f"Initializing student: {student_model}")
    student_client = build_client(provider=student_model, model=get_student_model())
    
    print_info(f"Initializing teacher: {teacher_config['model']}")
    teacher_client = build_client(
        provider=teacher_config['provider'],
        model=teacher_config['model']
    )
    
    # Note: Memory store and index will be created separately for each trial
    # to ensure complete isolation between different hyperparameter configurations
    
    # Load dataset
    print_info(f"Loading dataset: {dataset}")
    questions = load_dataset(dataset, limit)
    
    # Run trials
    all_results = []
    start_time = time.time()
    
    for config, trial_id in configs:
        result = run_tuning_trial(
            trial_id=trial_id,
            config=config,
            questions=questions,
            student_client=student_client,
            teacher_client=teacher_client,
            verbose=verbose
        )
        all_results.append(result)
    
    total_time = time.time() - start_time
    
    # Sort by F1 score
    all_results.sort(key=lambda x: x['avg_metrics']['f1'], reverse=True)
    
    # Print summary table
    print_header("Tuning Results Summary")
    
    from rich.table import Table
    from rich.console import Console
    
    console = Console()
    table = Table(title="Top 10 Configurations")
    
    table.add_column("Rank", style="cyan", justify="right")
    table.add_column("Trial", justify="right")
    table.add_column("Config", style="dim")
    table.add_column("F1", justify="right", style="bold")
    table.add_column("Success Rate", justify="right")
    table.add_column("Latency (ms)", justify="right")
    
    for rank, result in enumerate(all_results[:10], 1):
        config_str = ", ".join([f"{k}={v}" for k, v in result['config'].items()])
        table.add_row(
            str(rank),
            str(result['trial_id']),
            config_str,
            f"{result['avg_metrics']['f1']:.3f}",
            f"{result['success_rate']:.1%}",
            f"{result['avg_latency_ms']:.0f}"
        )
    
    console.print(table)
    
    # Find best configuration
    best = all_results[0]
    print_success("Best Configuration Found:")
    for param, value in best['config'].items():
        print_info(f"  {param}: {value}")
    print_info(f"  F1 Score: {best['avg_metrics']['f1']:.3f}")
    print_info(f"  Success Rate: {best['success_rate']:.1%}")
    
    # Export results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{output}_{strategy}_{timestamp}.json"
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    report = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "strategy": strategy,
            "param_grid": param_grid,
            "n_trials": len(configs),
            "dataset": dataset,
            "questions_per_trial": limit,
            "total_time_seconds": round(total_time, 2)
        },
        "best_config": best['config'],
        "best_metrics": best['avg_metrics'],
        "all_results": all_results
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print_success(f"Saved tuning report: {output_path}")
    print_info(f"Total time: {total_time:.1f}s")
    
    return report


def main():
    """Main entry point for command line."""
    args = parse_args()
    
    run_tuning(
        strategy=args.strategy,
        params=args.params,
        n_trials=args.n_trials,
        dataset=args.dataset,
        limit=args.limit,
        output=args.output,
        verbose=args.verbose,
        student_model=args.student_model,
        teacher_model=args.teacher_model
    )


if __name__ == "__main__":
    main()
