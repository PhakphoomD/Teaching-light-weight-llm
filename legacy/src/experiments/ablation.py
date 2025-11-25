"""
Ablation Study Module

This module implements ablation testing to measure the impact of individual features:
- Memory: JSONL store with similar example retrieval
- Chain-of-Thought (CoT): Enhanced prompting for reasoning
- FAISS: Vector-based semantic search

The ablation study tests all 8 combinations (2^3) to identify which features
contribute most to performance.

Usage:
    python -m src.experiments.ablation --features memory cot --limit 50
    python -m src.experiments.ablation --features all --limit 100
"""

import argparse
import json
import time
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
# Feature Combinations
# ============================================================================

FEATURES = {
    "memory": "JSONL memory store with retrieval",
    "cot": "Chain-of-Thought prompting",
    "faiss": "FAISS vector-based semantic search"
}


def get_all_combinations() -> List[Tuple[str, Dict[str, bool]]]:
    """
    Generate all 8 feature combinations (2^3).
    
    Returns:
        List of (name, config) tuples
        
    Example:
        [
            ("baseline", {"enable_memory": False, "enable_cot": False, "enable_faiss": False}),
            ("memory", {"enable_memory": True, "enable_cot": False, "enable_faiss": False}),
            ...
            ("all", {"enable_memory": True, "enable_cot": True, "enable_faiss": True})
        ]
    """
    combinations = []
    
    # Generate all boolean combinations
    for memory, cot, faiss in product([False, True], repeat=3):
        config = {
            "enable_memory": memory,
            "enable_cot": cot,
            "enable_faiss": faiss
        }
        
        # Generate name
        enabled = []
        if memory:
            enabled.append("memory")
        if cot:
            enabled.append("cot")
        if faiss:
            enabled.append("faiss")
        
        name = "_".join(enabled) if enabled else "baseline"
        combinations.append((name, config))
    
    return combinations


def filter_combinations(features: List[str]) -> List[Tuple[str, Dict[str, bool]]]:
    """
    Filter combinations to test specific features.
    
    Args:
        features: List of feature names or ["all"]
    
    Returns:
        List of (name, config) tuples
    """
    if "all" in features:
        return get_all_combinations()
    
    # Validate features
    valid_features = set(FEATURES.keys())
    invalid = [f for f in features if f not in valid_features]
    if invalid:
        raise ValueError(f"Invalid features: {invalid}. Valid: {list(valid_features)}")
    
    # Generate combinations with only specified features
    combinations = []
    feature_set = set(features)
    
    for name, config in get_all_combinations():
        # Check if this combination uses only the specified features
        enabled_features = {k.replace("enable_", "") for k, v in config.items() if v}
        
        # Include if enabled features are subset of requested features
        if enabled_features.issubset(feature_set):
            combinations.append((name, config))
    
    return combinations


# ============================================================================
# Ablation Runner
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


def run_ablation_experiment(
    combo_name: str,
    config: Dict[str, bool],
    questions: List[Dict[str, Any]],
    student_client,
    teacher_client,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Run one ablation experiment with specific feature configuration.
    
    Args:
        combo_name: Name of the combination (e.g., "memory_cot")
        config: Feature flags (enable_memory, enable_cot, enable_faiss)
        questions: List of questions to test
        student_client: Student LLM client
        teacher_client: Teacher LLM client
        verbose: Show detailed output
    
    Returns:
        Dictionary with aggregated results
    
    Note:
        Creates fresh memory store and index for each experiment to ensure isolation.
    """
    print_header(f"Testing Configuration: {combo_name}")
    print_info(f"Features: {', '.join([k.replace('enable_', '') for k, v in config.items() if v]) or 'none (baseline)'}")
    print_info(f"Questions: {len(questions)}")
    
    # Create fresh memory store and index for THIS experiment only
    import tempfile
    import os
    
    # Use temporary files with unique names for isolation
    temp_dir = tempfile.gettempdir()
    experiment_suffix = combo_name.replace('_', '')
    store_path = os.path.join(temp_dir, f"ablation_store_{experiment_suffix}.jsonl")
    index_path = os.path.join(temp_dir, f"ablation_index_{experiment_suffix}.faiss")
    
    # Delete old files to ensure clean slate
    if os.path.exists(store_path):
        os.remove(store_path)
    if os.path.exists(index_path):
        os.remove(index_path)
    
    store = MemoryStore(store_path)
    index = VectorIndex(
        embedding_model="all-MiniLM-L6-v2",
        index_path=index_path
    ) if config["enable_memory"] or config["enable_faiss"] else None
    
    # Create teacher critic
    teacher = TeacherCritic(
        provider="gemini",
        model_name=teacher_client.model_name if hasattr(teacher_client, 'model_name') else get_teacher_model_name()
    )
    
    # Prepare run_loop config
    loop_config = {
        "student_client": student_client,
        "teacher_client": teacher_client,
        "max_rounds": 3,
        "k": 5 if config["enable_memory"] else 0,
        "memory_type": "raw",
        "use_cot_student": config["enable_cot"],
        "use_cot_teacher": config["enable_cot"],
        "student_temperature": 0.7,
        "verbose": verbose,  # Pass verbose flag to run_loop
        "teacher_temperature": 0.2
    }
    
    # Note: FAISS is already used in VectorIndex, so enable_faiss just controls whether we use index
    # If enable_memory=False, we skip retrieval entirely (k=0)
    
    # Clear index if not using FAISS/memory
    if not config["enable_memory"] and not config["enable_faiss"]:
        # Don't use index at all
        # We'll pass empty context in run_loop by setting k=0
        pass
    
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
        progress = create_progress_bar(f"Testing {combo_name}")
        if progress:
            progress.start()
            task = progress.add_task(
                f"[cyan]{combo_name}",
                total=len(questions)
            )
    
    # Run each question through the loop
    experiment_id = f"ablation_{combo_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    for idx, q in enumerate(questions, 1):
        question_text = q.get('question', '')
        reference = q.get('reference', '')
        question_id = q.get('id', f'q{idx}')
        
        try:
            # Run refinement loop
            # Create dummy index if None (for baseline)
            actual_index = index if index is not None else VectorIndex(
                embedding_model="all-MiniLM-L6-v2",
                index_path=os.path.join(temp_dir, "dummy_index.faiss")
            )
            
            result = run_loop(
                question=question_text,
                config=loop_config,
                store=store,
                index=actual_index,
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
                print_info(f"[{idx}/{len(questions)}] {question_id}: Success={result['success']}, F1={metrics.get('f1', 0):.2f}")
        
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
        "combination": combo_name,
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
    
    print_success(f"Completed {combo_name}: Success rate {success_rate:.1%}, Avg F1 {avg_metrics['f1']:.3f}")
    
    return summary


# ============================================================================
# CLI and Main
# ============================================================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Ablation Study - Test feature combinations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Features:
  memory  - JSONL memory store with retrieval
  cot     - Chain-of-Thought prompting
  faiss   - FAISS vector-based semantic search
  all     - Test all 8 combinations (2^3)

Examples:
  # Test memory and CoT only
  python -m experiments.ablation --features memory cot --limit 50
  
  # Test all combinations
  python -m experiments.ablation --features all --limit 100
  
  # Test baseline (no features) vs full (all features)
  python -m experiments.ablation --features all --limit 20 --verbose
        """
    )
    
    parser.add_argument(
        "--features",
        nargs="+",
        required=True,
        help="Features to test (memory, cot, faiss, or 'all')"
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
        default=50,
        help="Number of questions to test per combination"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="logs/analysis/ablation_report",
        help="Output file prefix (will create .json)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output for each question"
    )
    
    parser.add_argument(
        "--student-model",
        type=str,
        default="local",
        help="Student model provider (default: local)"
    )
    
    parser.add_argument(
        "--teacher-model",
        type=str,
        default="g25_flash_lite",
        help="Teacher model name from models.yml (default: g25_flash_lite)"
    )
    
    return parser.parse_args()


def run_ablation(
    features: List[str],
    dataset: str = "data/alpaca_20.jsonl",
    limit: int = 50,
    output: str = "logs/analysis/ablation_report",
    verbose: bool = False,
    student_model: str = "local",
    teacher_model: str = "g25_flash_lite"
):
    """
    Run ablation study.
    
    This is the main entry point that can be called from cli.hub
    or directly from command line.
    """
    print_header("Ablation Study")
    
    # Load configurations
    print_info("Loading configurations...")
    models_config = load_models_config()
    
    # Get teacher config
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
    
    # Note: Memory store and index will be created separately for each experiment
    # to ensure complete isolation between different feature combinations
    
    # Load dataset
    print_info(f"Loading dataset: {dataset}")
    questions = load_dataset(dataset, limit)
    
    # Get feature combinations
    print_info("Generating feature combinations...")
    combinations = filter_combinations(features)
    print_info(f"Testing {len(combinations)} combinations: {[c[0] for c in combinations]}")
    
    # Run experiments
    all_results = []
    start_time = time.time()
    
    for combo_name, config in combinations:
        result = run_ablation_experiment(
            combo_name=combo_name,
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
    print_header("Ablation Results Summary")
    
    from rich.table import Table
    from rich.console import Console
    
    console = Console()
    table = Table(title="Feature Combination Rankings")
    
    table.add_column("Rank", style="cyan", justify="right")
    table.add_column("Combination", style="bold")
    table.add_column("Success Rate", justify="right")
    table.add_column("F1", justify="right")
    table.add_column("EM", justify="right")
    table.add_column("BLEU", justify="right")
    table.add_column("ROUGE-L", justify="right")
    table.add_column("BERT-F1", justify="right")
    
    for rank, result in enumerate(all_results, 1):
        metrics = result['avg_metrics']
        table.add_row(
            str(rank),
            result['combination'],
            f"{result['success_rate']:.1%}",
            f"{metrics['f1']:.3f}",
            f"{metrics['exact_match']:.3f}",
            f"{metrics['bleu']:.3f}",
            f"{metrics['rouge_l']:.3f}",
            f"{metrics['bert_f1']:.3f}"
        )
    
    console.print(table)
    
    # Find best combination
    best = all_results[0]
    print_success(f"Best combination: {best['combination']}")
    print_info(f"  F1: {best['avg_metrics']['f1']:.3f}")
    print_info(f"  Success rate: {best['success_rate']:.1%}")
    
    # Export results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{output}_{timestamp}.json"
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    report = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "dataset": dataset,
            "questions_per_combo": limit,
            "combinations_tested": len(combinations),
            "total_time_seconds": round(total_time, 2)
        },
        "results": all_results
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print_success(f"Saved ablation report: {output_path}")
    print_info(f"Total time: {total_time:.1f}s")
    
    return report


def main():
    """Main entry point for command line."""
    args = parse_args()
    
    run_ablation(
        features=args.features,
        dataset=args.dataset,
        limit=args.limit,
        output=args.output,
        verbose=args.verbose,
        student_model=args.student_model,
        teacher_model=args.teacher_model
    )


if __name__ == "__main__":
    main()
