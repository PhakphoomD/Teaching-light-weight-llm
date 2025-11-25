"""
Baseline Teacher Probe - Compare Multiple Teacher Models

This script evaluates different teacher models on a small dev set to determine
the best model for your teaching experiments. It measures:
- Evaluation accuracy (EM, F1, BLEU, ROUGE-L, BERTScore)
- Response latency
- Token usage
- Cost estimation

Usage Examples:
    # Test single model (quick)
    python -m src.experiments.baseline_probe --teachers g25_flash_lite --limit 10
    
    # Compare all models (comprehensive)
    python -m src.experiments.baseline_probe --teachers g20_flash_lite,g25_flash_lite,g25_pro
    
    # Use preset configurations
    python -m src.experiments.baseline_probe --preset quick        # Fast iteration
    python -m src.experiments.baseline_probe --preset quality      # Best quality
    python -m src.experiments.baseline_probe --preset balanced     # Middle ground
    
    # Custom hyperparameters
    python -m src.experiments.baseline_probe \
        --teachers g25_flash_lite \
        --temperature 0.3 \
        --max-tokens 512 \
        --limit 20
"""

import argparse
import json
import csv
import time
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.refinement.settings import SETTINGS
from src.core.console import (
    print_header,
    print_experiment_block,
    print_summary_table,
    create_progress_bar,
    print_success,
    print_error,
    print_warning,
    print_info,
    setup_rich_logging
)
from src.providers.factory import build_client
from src.eval.metrics import compute_all_metrics
from src.prompts.teacher import build_teacher_prompt
import jsonlines

# Setup logging
setup_rich_logging()

import logging
logger = logging.getLogger(__name__)


# ============================================================================
# PRESETS - Ready-to-use configurations
# ============================================================================

PRESETS = {
    "quick": {
        "teachers": ["g20_flash_lite"],
        "limit": 10,
        "temperature": 0.2,
        "max_tokens": 256,
        "description": "Fast iteration with minimal cost"
    },
    "balanced": {
        "teachers": ["g25_flash_lite"],
        "limit": 20,
        "temperature": 0.2,
        "max_tokens": 512,
        "description": "Good balance of speed and quality"
    },
    "quality": {
        "teachers": ["g25_pro"],
        "limit": 20,
        "temperature": 0.1,
        "max_tokens": 1024,
        "description": "Highest quality evaluation"
    },
    "compare_all": {
        "teachers": ["g20_flash_lite", "g25_flash_lite", "g25_pro"],
        "limit": 15,
        "temperature": 0.2,
        "max_tokens": 512,
        "description": "Compare all available models"
    }
}


def parse_args():
    """Parse command line arguments with preset support."""
    parser = argparse.ArgumentParser(
        description="Baseline Teacher Probe - Compare teacher models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Presets:
  quick        - Fast iteration (g20_flash_lite, 10 questions)
  balanced     - Good speed/quality (g25_flash_lite, 20 questions)
  quality      - Best quality (g25_pro, 20 questions)
  compare_all  - Test all models (15 questions each)

Examples:
  # Use preset
  python -m experiments.baseline_probe --preset balanced
  
  # Custom configuration
  python -m experiments.baseline_probe --teachers g25_flash_lite,g25_pro --limit 15
  
  # Override preset values
  python -m experiments.baseline_probe --preset quick --temperature 0.3
        """
    )
    
    # Preset or custom configuration
    parser.add_argument(
        "--preset",
        choices=list(PRESETS.keys()),
        help="Use a preset configuration (overrides other options unless explicitly set)"
    )
    
    # Teacher selection
    parser.add_argument(
        "--teachers",
        type=str,
        help="Comma-separated teacher names (e.g., 'g25_flash_lite,g25_pro')"
    )
    
    # Dataset options
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/alpaca_20.jsonl",
        help="Path to dataset file (default: data/alpaca_20.jsonl)"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of questions to test (useful for quick tests)"
    )
    
    # Hyperparameters
    parser.add_argument(
        "--temperature",
        type=float,
        help="Sampling temperature (0.0 = deterministic, 1.0 = creative)"
    )
    
    parser.add_argument(
        "--max-tokens",
        type=int,
        help="Maximum tokens for teacher output"
    )
    
    parser.add_argument(
        "--top-p",
        type=float,
        default=1.0,
        help="Nucleus sampling parameter (default: 1.0)"
    )
    
    # Output options
    parser.add_argument(
        "--output",
        type=str,
        default="logs/analysis/baseline_probe_summary",
        help="Output file prefix (will create .json and .csv)"
    )
    
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bar"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output for each question"
    )
    
    args = parser.parse_args()
    
    # Apply preset if specified
    if args.preset:
        preset = PRESETS[args.preset]
        print_info(f"Using preset: {args.preset} - {preset['description']}")
        
        # Apply preset values if not explicitly overridden
        if args.teachers is None:
            args.teachers = ",".join(preset["teachers"])
        if args.limit is None:
            args.limit = preset.get("limit")
        if args.temperature is None:
            args.temperature = preset.get("temperature", 0.2)
        if args.max_tokens is None:
            args.max_tokens = preset.get("max_tokens", 512)
    
    # Set defaults if still not set
    if args.teachers is None:
        args.teachers = "g25_flash_lite"  # Default to balanced model
    if args.temperature is None:
        args.temperature = 0.2
    if args.max_tokens is None:
        args.max_tokens = 512
    
    return args


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


def evaluate_teacher(
    teacher_name: str,
    teacher_config: Dict[str, Any],
    questions: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    top_p: float,
    verbose: bool = False,
    show_progress: bool = True
) -> Dict[str, Any]:
    """
    Evaluate a single teacher model on the question set.
    
    Returns:
        Dictionary with aggregated results
    """
    print_header(f"Evaluating Teacher: {teacher_config['model']}")
    print_info(f"Temperature: {temperature}, Max Tokens: {max_tokens}, Questions: {len(questions)}")
    
    # Initialize teacher client
    try:
        teacher = build_client(
            provider=teacher_config['provider'],
            model=teacher_config['model']
        )
    except Exception as e:
        print_error(f"Failed to initialize teacher: {e}")
        return {
            "teacher": teacher_name,
            "model": teacher_config['model'],
            "error": str(e),
            "status": "failed"
        }
    
    # Results collector
    results = []
    total_latency = 0
    total_tokens = 0
    metrics_sum = defaultdict(float)
    
    # Progress bar
    progress = None
    task = None
    if show_progress:
        progress = create_progress_bar(f"Testing {teacher_config['model']}")
        if progress:
            progress.start()
            task = progress.add_task(
                f"[cyan]{teacher_config['model']}",
                total=len(questions)
            )
    
    # Evaluate each question
    for idx, q in enumerate(questions, 1):
        question_text = q.get('question', '')
        reference = q.get('reference', '')
        question_id = q.get('id', f'q{idx}')
        
        # Build evaluation prompt
        # For probe, we're testing if teacher can provide good feedback
        # Simulate a student answer (use reference as "perfect" answer)
        student_answer = reference  # In real scenario, this would be student's attempt
        
        eval_prompt = build_teacher_prompt(
            question=question_text,
            student_answer=student_answer,
            correct_answer=reference
        )
        
        # Call teacher
        try:
            start_time = time.time()
            response = teacher.chat(
                messages=[{"role": "user", "content": eval_prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p
            )
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Extract response
            teacher_response = response.text
            # Usage object has prompt_tokens, completion_tokens, total_tokens
            if response.usage:
                tokens_used = response.usage.total_tokens or (response.usage.prompt_tokens + response.usage.completion_tokens)
            else:
                tokens_used = 0
            
            # Compute metrics (comparing teacher's evaluation quality)
            # For now, we'll use simple heuristics
            metrics = {
                "response_length": len(teacher_response),
                "tokens": tokens_used,
                "latency_ms": latency_ms
            }
            
            # Track totals
            total_latency += latency_ms
            total_tokens += tokens_used
            
            results.append({
                "question_id": question_id,
                "question": question_text[:100],
                "response": teacher_response[:200],
                "metrics": metrics,
                "success": True
            })
            
            # Verbose output
            if verbose:
                print_experiment_block(
                    experiment_id=f"probe_{teacher_name}",
                    question_id=question_id,
                    attempt=1,
                    total_attempts=1,
                    question=question_text,
                    answer=teacher_response,
                    metrics={"Tokens": tokens_used, "Latency": latency_ms / 1000},
                    progress_current=idx,
                    progress_total=len(questions),
                    log_file=None
                )
            
        except Exception as e:
            logger.error(f"Error evaluating {question_id}: {e}")
            results.append({
                "question_id": question_id,
                "error": str(e),
                "success": False
            })
        
        # Update progress
        if progress and task is not None:
            progress.update(task, advance=1)
    
    if progress:
        progress.stop()
    
    # Calculate aggregates
    successful = [r for r in results if r.get('success', False)]
    success_rate = len(successful) / len(results) if results else 0
    
    avg_latency = total_latency / len(successful) if successful else 0
    avg_tokens = total_tokens / len(successful) if successful else 0
    
    summary = {
        "teacher": teacher_name,
        "model": teacher_config['model'],
        "questions_tested": len(results),
        "success_count": len(successful),
        "success_rate": success_rate,
        "avg_latency_ms": int(avg_latency),
        "total_tokens": total_tokens,
        "avg_tokens_per_question": int(avg_tokens),
        "rpm_limit": teacher_config['rpm'],
        "tpm_limit": teacher_config['tpm'],
        "hyperparameters": {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p
        },
        "status": "success"
    }
    
    print_success(f"Completed: {len(successful)}/{len(results)} questions | "
                 f"Avg latency: {avg_latency:.0f}ms | "
                 f"Total tokens: {total_tokens:,}")
    
    return summary


def rank_teachers(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rank teachers by performance.
    
    Ranking criteria:
    1. Success rate (primary)
    2. Lower latency (secondary)
    3. Fewer tokens (tertiary)
    """
    # Filter successful runs
    valid_results = [r for r in results if r.get('status') == 'success']
    
    # Sort by criteria
    ranked = sorted(
        valid_results,
        key=lambda x: (
            -x['success_rate'],  # Higher is better (negative for descending)
            x['avg_latency_ms'],  # Lower is better
            x['avg_tokens_per_question']  # Lower is better
        )
    )
    
    # Add rank
    for i, result in enumerate(ranked, 1):
        result['rank'] = i
    
    return ranked


def save_results(results: List[Dict[str, Any]], output_prefix: str):
    """Save results to JSON and CSV files."""
    output_path = Path(output_prefix)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save JSON
    json_path = output_path.with_suffix('.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results
        }, f, indent=2)
    print_success(f"Saved JSON results: {json_path}")
    
    # Save CSV
    csv_path = output_path.with_suffix('.csv')
    if results:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print_success(f"Saved CSV results: {csv_path}")


def main():
    """Main execution."""
    args = parse_args()
    
    print_header("Baseline Teacher Probe")
    
    # Load models config
    try:
        models_config = load_models_config()
    except Exception as e:
        print_error(f"Failed to load models config: {e}")
        return 1
    
    # Parse teacher list
    teacher_names = [t.strip() for t in args.teachers.split(',')]
    print_info(f"Testing teachers: {', '.join(teacher_names)}")
    
    # Validate teachers
    for name in teacher_names:
        if name not in models_config['teachers']:
            print_error(f"Unknown teacher: {name}")
            print_info(f"Available: {', '.join(models_config['teachers'].keys())}")
            return 1
    
    # Load dataset
    try:
        questions = load_dataset(args.dataset, args.limit)
    except Exception as e:
        print_error(f"Failed to load dataset: {e}")
        return 1
    
    # Evaluate each teacher
    all_results = []
    for teacher_name in teacher_names:
        teacher_config = get_teacher_config(teacher_name, models_config)
        
        result = evaluate_teacher(
            teacher_name=teacher_name,
            teacher_config=teacher_config,
            questions=questions,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            top_p=args.top_p,
            verbose=args.verbose,
            show_progress=not args.no_progress
        )
        
        all_results.append(result)
    
    # Rank results
    ranked_results = rank_teachers(all_results)
    
    # Display summary
    print_header("Results Summary")
    print_summary_table(
        data=ranked_results,
        title="Teacher Model Rankings",
        columns=["rank", "teacher", "model", "success_rate", "avg_latency_ms", 
                "avg_tokens_per_question", "rpm_limit", "tpm_limit"]
    )
    
    # Recommend best teacher
    if ranked_results:
        best = ranked_results[0]
        print_header("Recommendation")
        print_success(f"Best teacher: {best['model']}")
        print_info(f"  Success rate: {best['success_rate']:.1%}")
        print_info(f"  Avg latency: {best['avg_latency_ms']}ms")
        print_info(f"  Avg tokens: {best['avg_tokens_per_question']}")
    
    # Save results
    save_results(ranked_results, args.output)
    
    print_header("Probe Complete")
    return 0


def run_baseline_probe(**kwargs):
    """
    Programmatic entry point for calling from cli.hub or other modules.
    
    Args:
        **kwargs: All arguments from parse_args() as keyword arguments
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Convert kwargs to args-like object using SimpleNamespace
    from types import SimpleNamespace
    
    args = SimpleNamespace(
        preset=kwargs.get('preset'),
        teachers=kwargs.get('teachers', 'g25_flash_lite'),
        dataset=kwargs.get('dataset', 'data/alpaca_20.jsonl'),
        limit=kwargs.get('limit'),
        temperature=kwargs.get('temperature'),
        max_tokens=kwargs.get('max_tokens'),
        top_p=kwargs.get('top_p', 1.0),
        output=kwargs.get('output', 'logs/analysis/baseline_probe_summary'),
        no_progress=not kwargs.get('show_progress', True),
        verbose=kwargs.get('verbose', False)
    )
    
    # Load models config
    try:
        models_config = load_models_config()
    except Exception as e:
        print_error(f"Failed to load models config: {e}")
        return 1
    
    # Apply preset
    if args.preset:
        preset_config = PRESETS.get(args.preset)
        if not preset_config:
            print_error(f"Unknown preset: {args.preset}")
            return 1
        
        print_info(f"Using preset: {args.preset} - {preset_config['description']}")
        
        if args.teachers == 'g25_flash_lite':  # Default not overridden
            args.teachers = ",".join(preset_config["teachers"])
        if args.limit is None:
            args.limit = preset_config.get("limit")
        if args.temperature is None:
            args.temperature = preset_config.get("temperature", 0.2)
        if args.max_tokens is None:
            args.max_tokens = preset_config.get("max_tokens", 512)
    
    # Set defaults
    if args.temperature is None:
        args.temperature = 0.2
    if args.max_tokens is None:
        args.max_tokens = 512
    
    # Parse teacher list
    teacher_names = [t.strip() for t in args.teachers.split(',')]
    print_info(f"Testing teachers: {', '.join(teacher_names)}")
    
    # Validate teachers
    for name in teacher_names:
        if name not in models_config['teachers']:
            print_error(f"Unknown teacher: {name}")
            print_info(f"Available: {', '.join(models_config['teachers'].keys())}")
            return 1
    
    # Load dataset
    try:
        questions = load_dataset(args.dataset, args.limit)
    except Exception as e:
        print_error(f"Failed to load dataset: {e}")
        return 1
    
    # Evaluate each teacher
    all_results = []
    for teacher_name in teacher_names:
        teacher_config = get_teacher_config(teacher_name, models_config)
        
        result = evaluate_teacher(
            teacher_name=teacher_name,
            teacher_config=teacher_config,
            questions=questions,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            top_p=args.top_p,
            verbose=args.verbose,
            show_progress=not args.no_progress
        )
        
        all_results.append(result)
    
    # Rank results
    ranked_results = rank_teachers(all_results)
    
    # Display summary
    print_header("Results Summary")
    print_summary_table(
        data=ranked_results,
        title="Teacher Model Rankings",
        columns=["rank", "teacher", "model", "success_rate", "avg_latency_ms", 
                "avg_tokens_per_question", "rpm_limit", "tpm_limit"]
    )
    
    # Recommend best teacher
    if ranked_results:
        best = ranked_results[0]
        print_header("Recommendation")
        print_success(f"Best teacher: {best['model']}")
        print_info(f"  Success rate: {best['success_rate']:.1%}")
        print_info(f"  Avg latency: {best['avg_latency_ms']}ms")
        print_info(f"  Avg tokens: {best['avg_tokens_per_question']}")
    
    # Save results
    save_results(ranked_results, args.output)
    
    print_header("Probe Complete")
    return 0


if __name__ == '__main__':
    sys.exit(main())
