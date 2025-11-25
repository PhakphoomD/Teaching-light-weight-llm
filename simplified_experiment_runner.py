"""
Simplified Experiment Runner

Runs experiments on the simplified teaching loop system with configurable
datasets and parameters. Provides detailed logging, progress tracking,
and performance metrics.

Usage:
    python simplified_experiment_runner.py
    python simplified_experiment_runner.py --questions 5
    python simplified_experiment_runner.py --config config/simplified_config.yml
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from simplified_teaching_loop import SimplifiedTeachingLoop


def load_questions(dataset_path: str, num_questions: int = -1) -> List[Dict[str, Any]]:
    """
    Load questions from JSONL dataset.
    
    Args:
        dataset_path: Path to JSONL file
        num_questions: Number of questions to load (-1 for all)
    
    Returns:
        List of question dicts
    """
    questions = []
    
    try:
        with open(dataset_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if num_questions > 0 and i >= num_questions:
                    break
                
                if line.strip():
                    data = json.loads(line)
                    
                    # Extract question and answer (handle different schemas)
                    # Try different field names
                    question = (data.get('instruction') or 
                               data.get('question') or 
                               data.get('input') or
                               data.get('text'))
                    
                    answer = (data.get('output') or 
                             data.get('answer') or 
                             data.get('response') or
                             data.get('reference') or  # Alpaca uses 'reference'
                             data.get('target'))
                    
                    if question and answer:
                        questions.append({
                            'id': data.get('id', f'q_{i}'),
                            'question': question,
                            'ground_truth': answer
                        })
        
        print(f"[OK] Loaded {len(questions)} questions from {dataset_path}")
        return questions
        
    except FileNotFoundError:
        print(f"[FAIL] Dataset not found: {dataset_path}")
        return []
    except Exception as e:
        print(f"[FAIL] Error loading dataset: {e}")
        return []


def run_test(config_path: str = "config/simplified_config.yml",
             num_questions: int = 10):
    """
    Run batch testing experiment on the simplified teaching loop system.
    
    This function orchestrates a complete experiment run including:
    - System initialization with configuration
    - Dataset loading and question preparation
    - Progress tracking with visual feedback
    - Error handling and recovery for individual question failures
    - Comprehensive metrics collection and reporting
    
    Args:
        config_path: Path to YAML configuration file containing system parameters
        num_questions: Maximum number of questions to process from dataset
    """
    # ===== SYSTEM INITIALIZATION =====
    # Create teaching loop instance with all components (student, teacher, memory, metrics)
    try:
        loop = SimplifiedTeachingLoop(config_path=config_path)
    except Exception as e:
        print(f"[FAIL] Failed to initialize loop: {e}")
        return
    
    # ===== DATASET LOADING =====
    # Load questions from configured JSONL dataset file
    dataset_path = loop.config.get('dataset', {}).get('path', 'data/alpaca_20.jsonl')
    questions = load_questions(dataset_path, num_questions)
    
    if not questions:
        print("[FAIL] No questions to test")
        return
    
    # ===== EXPERIMENT HEADER =====
    # Display experiment configuration and parameters (includes 3-second countdown)
    loop.ui.print_header(loop.config, experiment_name="Simplified Teaching Loop")
    
    # Log configuration to structured debug file for post-experiment analysis
    loop.debug_logger.log_parameters(loop.config)
    
    # ===== PROGRESS TRACKING =====
    # Initialize progress bar for visual feedback during long experiments
    progress = loop.ui.create_progress_bar(len(questions), desc="Processing")
    
    # ===== MAIN EXPERIMENT LOOP =====
    # Process each question through the teaching loop system
    for i, q in enumerate(questions, 1):
        # Update progress display with current question preview
        loop.ui.update_progress(i, q['question'])
        
        try:
            # ===== RUN TEACHING LOOP FOR SINGLE QUESTION =====
            # Execute full iterative teaching process:
            # 1. Search memory for similar successful teaching experiences
            # 2. Generate student answer with appropriate prompt
            # 3. Evaluate with hybrid metrics (deterministic + LLM judges)
            # 4. If failed, generate teaching feedback
            # 5. Repeat until success, early stop, or max rounds reached
            result = loop.run(
                question=q['question'],
                ground_truth=q['ground_truth'],
                question_id=q['id'],
                question_idx=i,
                max_rounds=loop.config['loop']['max_rounds']
            )
            
            # ===== PREPARE DETAILED RESULTS FOR DISPLAY =====
            # Extract round-by-round data for comprehensive result visualization
            rounds_data = []
            for r in result['history']:
                rounds_data.append({
                    'round': r['round'],
                    'mode': r.get('mode', 'REFINE'),  # FIRST, REFINE, or LAST_CHANCE
                    'student_answer': r['answer'],
                    'feedback': r.get('generated_feedback', ''),
                    'scores': r['scores'],  # All metric scores
                    'flags': r.get('flags', [])  # Special flags (repetition, etc.)
                })
            
            # ===== DISPLAY QUESTION RESULTS =====
            # Print formatted table showing all rounds, scores, and final outcome
            loop.ui.print_question_result(
                question_idx=i,
                total_questions=len(questions),
                question=q['question'],
                ground_truth=q['ground_truth'],
                rounds=rounds_data,
                passed=result['success'],
                final_score=result['final_score']
            )
            
        except Exception as e:
            # ===== ERROR HANDLING =====
            # Gracefully handle failures without stopping entire experiment
            # Log error details for debugging while continuing to next question
            from src.simplified.terminal_ui import format_error_summary
            error_summary = format_error_summary(e, loop.config.get('teacher', {}).get('model', ''))
            loop.ui.log_error(error_summary, str(e))
            loop.debug_logger.log_error(str(e))
            
            print(f"\n[FAIL] ERROR on question {i}: {error_summary}")
            import traceback
            traceback.print_exc()
    
    # ===== FINALIZE PROGRESS TRACKING =====
    # Close progress bar UI component
    loop.ui.close_progress()
    
    # ===== SAVE STRUCTURED METRICS =====
    # Export metrics to JSON for data analysis and visualization tools
    loop.logger.save_metrics_json()
    
    # ===== DISPLAY AGGREGATED WARNINGS/ERRORS =====
    # Show summary of any issues encountered during experiment
    loop.ui.print_warnings_errors()
    
    # ===== AGGREGATE EXPERIMENT STATISTICS =====
    # Generate comprehensive performance report from all processed questions
    report = loop.get_performance_report()
    
    # ===== CALCULATE AVERAGE METRICS =====
    # Extract and average all metric scores across rounds and questions
    # This provides insight into which metrics correlate with success
    all_metric_keys = set()
    all_scores = []
    if hasattr(loop.monitor, 'results') and loop.monitor.results:
        for result in loop.monitor.results:
            for round_data in result.get('history', []):
                if 'scores' in round_data:
                    all_scores.append(round_data['scores'])
                    all_metric_keys.update(round_data['scores'].keys())
    
    # Initialize metrics dictionary with discovered metric types
    # Default to 0.0 for any missing values
    avg_metrics = {key: 0.0 for key in all_metric_keys}
    if not avg_metrics:
        # Fallback metric set if no scores were collected (edge case)
        avg_metrics = {
            'semantic_sim': 0.0,
            'rouge_l': 0.0,
            'exact_match': 0.0,
            'final': 0.0
        }
    
    # Compute mean value for each metric type across all collected scores
    if all_scores:
        for key in avg_metrics.keys():
            avg_metrics[key] = sum(s.get(key, 0) for s in all_scores) / len(all_scores)
    
    # ===== DISPLAY FINAL SUMMARY =====
    # Print comprehensive experiment results with all key metrics
    # Includes success rate, efficiency metrics, and average scores
    loop.ui.print_summary(
        success_rate=report['success_rate'] * 100,
        total_passed=report['success_count'],
        total_questions=report['total_questions'],
        avg_rounds=report['avg_rounds'],
        memory_hit_rate=report['memory_hit_rate'] * 100,
        total_time=report['total_time_seconds'],
        avg_time_per_question=report['avg_time_per_question_ms'],
        avg_metrics=avg_metrics
    )
    
    # ===== FINALIZE DEBUG LOGGING =====
    # Close debug log file and write final summary
    loop.debug_logger.finalize(report)
    
    # ===== SAVE PERFORMANCE REPORT =====
    # Export comprehensive results to JSON for detailed analysis
    output_path = "logs/simplified/test_results.json"
    loop.save_performance_report(output_path)
    
    print(f"[OK] Performance report saved to: {output_path}")
    print(f"[OK] Debug log saved to: {loop.debug_logger.get_log_path()}\n")


def compare_with_old_system():
    """
    Compare results with old system (if available).
    
    This is a placeholder for future implementation.
    """
    print("="*80)
    print("COMPARISON WITH OLD SYSTEM")
    print("="*80)
    print("[WARNING] Comparison not yet implemented")
    print("To enable:")
    print("1. Run old system on same questions")
    print("2. Load results from logs/experiments/")
    print("3. Compare success rates, rounds, etc.")
    print("="*80 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Simplified Experiment Runner - Run teaching loop experiments")
    parser.add_argument(
        '--config',
        type=str,
        default='config/simplified_config.yml',
        help='Path to config file'
    )
    parser.add_argument(
        '--questions',
        type=int,
        default=10,
        help='Number of questions to test'
    )
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Compare with old system results'
    )
    
    args = parser.parse_args()
    
    # Run test
    run_test(
        config_path=args.config,
        num_questions=args.questions
    )
    
    # Optional comparison
    if args.compare:
        compare_with_old_system()


if __name__ == "__main__":
    main()
