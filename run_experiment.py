#!/usr/bin/env python3
"""
Teaching Lightweight LLM - Unified Experiment Runner

Main entry point for running experiments with the new unified system.

Usage:
    # Interactive mode (recommended)
    python run_experiment.py
    
    # CLI mode with arguments
    python run_experiment.py --student tinyllama_1.1b --teacher groq_llama3_70b --strategy baseline --dataset "Quick Test"
    
    # Multiple strategies
    python run_experiment.py --student llama3_8b --teacher groq_llama3_70b --strategy baseline,memory_multikey_tfidf --dataset "Medium Test"
    
    # Run strategy group
    python run_experiment.py --student tinyllama_1.1b --teacher groq_llama3_70b --group quick_comparison --dataset "Quick Test"
"""

import sys
import argparse
from src.experiment.console import InteractiveConsole
from src.experiment.config import load_experiment_config
from src.experiment.runner import ExperimentRunner


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Teaching Lightweight LLM - Unified Experiment Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python run_experiment.py
  
  # Single experiment
  python run_experiment.py --student tinyllama_1.1b --teacher groq_llama3_70b --strategy baseline --dataset "Quick Test"
  
  # Multiple strategies
  python run_experiment.py --student llama3_8b --teacher groq_llama3_70b --strategy baseline,memory_multikey_tfidf --dataset "Medium Test"
  
  # Strategy group
  python run_experiment.py --student tinyllama_1.1b --teacher groq_llama3_70b --group quick_comparison --dataset "Quick Test"

Available Models:
  Students: tinyllama_1.1b, llama2_7b, llama3_8b, groq_llama3_8b, gemini_flash
  Teachers: groq_llama3_70b, gemini_pro, llama3_8b

Available Strategies:
  - baseline              : No memory, no reflection
  - baseline_reflection   : Reflection without memory
  - memory_multikey_tfidf : Full system (recommended)
  - memory_tfidf_only     : TF-IDF retrieval only
  - memory_multikey_only  : Multi-key retrieval only
  - memory_none           : Memory storage without retrieval

Available Strategy Groups:
  - all                   : All strategies
  - quick_comparison      : baseline, memory_multikey_tfidf, memory_tfidf_only
  - memory_ablation       : baseline, memory_tfidf_only, memory_multikey_only, memory_multikey_tfidf
  - reflection_test       : baseline, baseline_reflection

Available Datasets:
  - "Quick Test"    : 20 items (fast)
  - "Medium Test"   : 100 items
  - "Full Dataset"  : 52K items
        """
    )
    
    parser.add_argument(
        '--student',
        type=str,
        help='Student model key (e.g., tinyllama_1.1b, llama3_8b)'
    )
    
    parser.add_argument(
        '--teacher',
        type=str,
        help='Teacher model key (e.g., groq_llama3_70b, gemini_pro)'
    )
    
    parser.add_argument(
        '--strategy',
        type=str,
        help='Strategy key(s), comma-separated (e.g., baseline,memory_multikey_tfidf)'
    )
    
    parser.add_argument(
        '--group',
        type=str,
        help='Strategy group name (e.g., quick_comparison, all)'
    )
    
    parser.add_argument(
        '--dataset',
        type=str,
        help='Dataset name (e.g., "Quick Test", "Medium Test", "Full Dataset")'
    )
    
    parser.add_argument(
        '--max-iters',
        type=int,
        help='Override max iterations per task'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='results',
        help='Base output directory (default: results)'
    )
    
    args = parser.parse_args()
    
    # If no arguments provided, run interactive mode
    if not any([args.student, args.teacher, args.strategy, args.group, args.dataset]):
        print("No arguments provided. Starting interactive mode...\n")
        console = InteractiveConsole()
        console.run()
        return
    
    # Validate CLI arguments
    if not all([args.student, args.teacher, args.dataset]):
        parser.error("CLI mode requires --student, --teacher, and --dataset")
    
    if not (args.strategy or args.group):
        parser.error("CLI mode requires either --strategy or --group")
    
    if args.strategy and args.group:
        parser.error("Cannot use both --strategy and --group")
    
    # Load configuration
    try:
        config = load_experiment_config()
        runner = ExperimentRunner(config, base_output_dir=args.output_dir)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)
    
    # Get strategy keys
    if args.group:
        strategy_keys = config.strategy_groups.get(args.group, [])
        if not strategy_keys:
            print(f"Unknown strategy group: {args.group}")
            print(f"Available groups: {', '.join(config.strategy_groups.keys())}")
            sys.exit(1)
    else:
        strategy_keys = [s.strip() for s in args.strategy.split(',')]
    
    # Run experiments
    try:
        results = runner.run_experiments_from_selection(
            student_key=args.student,
            teacher_key=args.teacher,
            strategy_keys=strategy_keys,
            dataset_name=args.dataset,
            max_iters=args.max_iters
        )
        
        print(f"\nCompleted {len(results)} experiment(s)")
        print(f"Results saved to: {args.output_dir}/")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

