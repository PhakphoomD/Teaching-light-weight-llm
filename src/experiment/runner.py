"""
Experiment Runner - Orchestrates experiment execution

Manages running experiments with unified pipeline.
"""

import os
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.core.logger import get_logger
from src.pipelines.unified_pipeline import UnifiedPipeline
from src.experiment.config import ExperimentConfig, ModelConfig, StrategyConfig, DatasetConfig

logger = get_logger(__name__)


class ExperimentRunner:
    """
    Orchestrates experiment execution with unified pipeline.
    
    Handles:
    - Running single or multiple experiments
    - Output directory management
    - Progress tracking and logging
    - Result aggregation
    """
    
    def __init__(self, config: ExperimentConfig, base_output_dir: str = "results"):
        """
        Initialize experiment runner.
        
        Args:
            config: Experiment configuration
            base_output_dir: Base directory for all results
        """
        self.config = config
        self.base_output_dir = base_output_dir
        os.makedirs(base_output_dir, exist_ok=True)
    
    def run_single_experiment(
        self,
        student_model: ModelConfig,
        teacher_model: ModelConfig,
        strategy: StrategyConfig,
        dataset: DatasetConfig,
        max_iters: Optional[int] = None
    ) -> tuple[Any, List[Any]]:
        """
        Run a single experiment.
        
        Args:
            student_model: Student model configuration
            teacher_model: Teacher model configuration
            strategy: Strategy configuration
            dataset: Dataset configuration
            max_iters: Override max iterations (optional)
            
        Returns:
            Tuple of (summary, results)
        """
        logger.info("\n" + "=" * 80)
        logger.info("STARTING EXPERIMENT")
        logger.info("=" * 80)
        logger.info(f"Student: {student_model.display_name}")
        logger.info(f"Teacher: {teacher_model.display_name}")
        logger.info(f"Strategy: {strategy.display_name}")
        logger.info(f"Dataset: {dataset.name} ({dataset.size} items)")
        logger.info("=" * 80)
        
        # Create output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(
            self.base_output_dir,
            student_model.key,
            strategy.short_name,
            f"run_{timestamp}"
        )
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize pipeline
        pipeline = UnifiedPipeline(
            student_model=student_model,
            teacher_model=teacher_model,
            strategy_config={
                'name': strategy.name,
                'short_name': strategy.short_name,
                'features': strategy.features,
                'params': strategy.params
            },
            output_dir=output_dir
        )
        
        # Run experiment
        start_time = time.time()
        summary, results = pipeline.run(
            dataset_path=dataset.path,
            output_dir=output_dir,
            max_iters=max_iters
        )
        duration = time.time() - start_time
        
        logger.info(f"\nExperiment completed in {duration:.2f}s")
        logger.info(f"Results saved to: {output_dir}")
        
        return summary, results
    
    def run_multiple_experiments(
        self,
        student_model: ModelConfig,
        teacher_model: ModelConfig,
        strategies: List[StrategyConfig],
        dataset: DatasetConfig,
        max_iters: Optional[int] = None
    ) -> List[tuple[Any, List[Any]]]:
        """
        Run multiple experiments (different strategies).
        
        Args:
            student_model: Student model configuration
            teacher_model: Teacher model configuration
            strategies: List of strategy configurations
            dataset: Dataset configuration
            max_iters: Override max iterations (optional)
            
        Returns:
            List of (summary, results) tuples
        """
        logger.info("\n" + "=" * 80)
        logger.info("BATCH EXPERIMENT RUN")
        logger.info("=" * 80)
        logger.info(f"Student: {student_model.display_name}")
        logger.info(f"Teacher: {teacher_model.display_name}")
        logger.info(f"Strategies: {len(strategies)}")
        for s in strategies:
            logger.info(f"  - {s.display_name}")
        logger.info(f"Dataset: {dataset.name}")
        logger.info("=" * 80)
        
        all_results = []
        
        for idx, strategy in enumerate(strategies, 1):
            logger.info(f"\n[{idx}/{len(strategies)}] Running: {strategy.name}")
            
            try:
                summary, results = self.run_single_experiment(
                    student_model=student_model,
                    teacher_model=teacher_model,
                    strategy=strategy,
                    dataset=dataset,
                    max_iters=max_iters
                )
                all_results.append((summary, results))
                
            except Exception as e:
                logger.error(f"Error running {strategy.name}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        logger.info("\n" + "=" * 80)
        logger.info("BATCH EXPERIMENT COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Completed: {len(all_results)}/{len(strategies)} experiments")
        
        # Print comprehensive summary comparison
        if all_results:
            self._print_batch_summary(all_results)
        
        return all_results
    
    def _print_batch_summary(self, all_results: List[tuple[Any, List[Any]]]) -> None:
        """Print comprehensive comparison of multiple experiments."""
        logger.info("\n" + "=" * 80)
        logger.info("COMPREHENSIVE SUMMARY COMPARISON")
        logger.info("=" * 80)
        
        # Extract data from all experiments
        experiments_data = []
        for summary, _ in all_results:
            experiments_data.append({
                'name': getattr(summary, 'experiment', 'experiment'),
                'success_rate': getattr(summary, 'success_rate', 0.0),
                'passed': getattr(summary, 'passed', 0),
                'total': getattr(summary, 'total_tasks', 0),
                'first_attempt_pass_rate': getattr(summary, 'first_attempt_pass_rate', 0.0),
                'avg_attempts': getattr(summary, 'avg_attempts', 0.0),
                'mean_score': getattr(summary, 'mean_score', 0.0),
                'learning_gain': getattr(summary, 'learning_gain', 0.0),
                'repeat_error_rate': getattr(summary, 'repeat_error_rate', 0.0),
                'memory_utilization': getattr(summary, 'memory_utilization_rate', 0.0),
                'cross_task_transfer': getattr(summary, 'cross_task_transfer', 0.0),
                'tokens_per_task': getattr(summary, 'tokens_per_task', 0.0),
                'tokens_per_success': getattr(summary, 'tokens_per_success', 0.0),
                'total_tokens': getattr(summary, 'total_tokens', 0),
                'total_cost': getattr(summary, 'total_cost', 0.0),
                'estimated_cost': getattr(summary, 'estimated_cost', 0.0),
                'is_local': getattr(summary, 'is_local_student', True),
                'latency_ms': getattr(summary, 'latency_per_task_ms', 0.0),
                'total_runtime_s': getattr(summary, 'total_runtime_s', 0.0),
                'early_stopped': getattr(summary, 'early_stopped_tasks', 0),
            })
        
        # === 1. PERFORMANCE COMPARISON ===
        logger.info("\n[1] PERFORMANCE METRICS")
        logger.info("-" * 80)
        logger.info(f"{'Strategy':<40} | {'Success':<8} | {'1st Pass':<8} | {'Mean Score':<10} | {'Avg Attempts':<12}")
        logger.info("-" * 80)
        for data in experiments_data:
            logger.info(
                f"{data['name']:<40} | "
                f"{data['success_rate']:>6.1%}   | "
                f"{data['first_attempt_pass_rate']:>6.1%}   | "
                f"{data['mean_score']:>8.3f}   | "
                f"{data['avg_attempts']:>10.2f}"
            )
        
        # === 2. LEARNING METRICS ===
        logger.info("\n[2] LEARNING & GENERALISATION METRICS")
        logger.info("-" * 80)
        logger.info(f"{'Strategy':<40} | {'ΔScore':<9} | {'Repeat-Err':<10} | {'Memory Use':<10} | {'Transfer':<9}")
        logger.info("-" * 80)
        for data in experiments_data:
            logger.info(
                f"{data['name']:<40} | "
                f"{data['learning_gain']:>+7.3f}   | "
                f"{data['repeat_error_rate']:>8.1%}   | "
                f"{data['memory_utilization']:>8.1%}   | "
                f"{data['cross_task_transfer']:>7.1%}"
            )
        
        # === 3. EFFICIENCY METRICS ===
        logger.info("\n[3] EFFICIENCY METRICS")
        logger.info("-" * 80)
        logger.info(f"{'Strategy':<40} | {'Tokens/Task':<12} | {'Tokens/Succ':<12} | {'Latency(ms)':<12} | {'Runtime(s)':<11}")
        logger.info("-" * 80)
        for data in experiments_data:
            logger.info(
                f"{data['name']:<40} | "
                f"{data['tokens_per_task']:>10.0f}   | "
                f"{data['tokens_per_success']:>10.0f}   | "
                f"{data['latency_ms']:>10.1f}   | "
                f"{data['total_runtime_s']:>9.1f}"
            )
        
        # === 4. COST COMPARISON ===
        logger.info("\n[4] COST COMPARISON")
        logger.info("-" * 80)
        logger.info(f"{'Strategy':<40} | {'Total Tokens':<13} | {'Cost':<20}")
        logger.info("-" * 80)
        for data in experiments_data:
            if data['is_local']:
                cost_str = f"FREE (est: ~${data['estimated_cost']:.6f})"
            else:
                cost_str = f"${data['total_cost']:.6f}"
            logger.info(
                f"{data['name']:<40} | "
                f"{data['total_tokens']:>11,}   | "
                f"{cost_str}"
            )
        
        # === 5. BEST PERFORMERS ===
        logger.info("\n[5] BEST PERFORMERS")
        logger.info("-" * 80)
        
        # Best success rate
        best_success = max(experiments_data, key=lambda x: x['success_rate'])
        logger.info(f" Highest Success Rate:  {best_success['name']} ({best_success['success_rate']:.1%})")
        
        # Best learning gain
        best_learning = max(experiments_data, key=lambda x: x['learning_gain'])
        logger.info(f" Best Learning Gain:    {best_learning['name']} ({best_learning['learning_gain']:+.3f})")
        
        # Most efficient (tokens per success)
        if any(d['tokens_per_success'] > 0 for d in experiments_data):
            best_efficient = min([d for d in experiments_data if d['tokens_per_success'] > 0], 
                                key=lambda x: x['tokens_per_success'])
            logger.info(f" Most Efficient:        {best_efficient['name']} ({best_efficient['tokens_per_success']:.0f} tokens/success)")
        
        # Fastest
        best_speed = min(experiments_data, key=lambda x: x['latency_ms'])
        logger.info(f" Fastest:               {best_speed['name']} ({best_speed['latency_ms']:.1f}ms/task)")
        
        # Best transfer learning
        if any(d['cross_task_transfer'] > 0 for d in experiments_data):
            best_transfer = max(experiments_data, key=lambda x: x['cross_task_transfer'])
            logger.info(f" Best Transfer:         {best_transfer['name']} ({best_transfer['cross_task_transfer']:.1%})")
        
        logger.info("=" * 80)
    
    def run_experiments_from_selection(
        self,
        student_key: str,
        teacher_key: str,
        strategy_keys: List[str],
        dataset_name: str,
        max_iters: Optional[int] = None
    ) -> List[tuple[Any, List[Any]]]:
        """
        Run experiments from user selection (keys/names).
        
        Args:
            student_key: Student model key
            teacher_key: Teacher model key
            strategy_keys: List of strategy keys
            dataset_name: Dataset name
            max_iters: Override max iterations (optional)
            
        Returns:
            List of (summary, results) tuples
        """
        # Get configurations
        student = self.config.models.get(student_key)
        teacher = self.config.models.get(teacher_key)
        
        if not student:
            raise ValueError(f"Unknown student model: {student_key}")
        if not teacher:
            raise ValueError(f"Unknown teacher model: {teacher_key}")
        
        # Get strategies
        strategies = []
        for key in strategy_keys:
            strategy = self.config.strategies.get(key)
            if strategy:
                strategies.append(strategy)
            else:
                logger.warning(f"Unknown strategy: {key}, skipping")
        
        if not strategies:
            raise ValueError("No valid strategies provided")
        
        # Find dataset
        dataset = None
        for ds in self.config.datasets:
            if ds.name.lower() == dataset_name.lower() or dataset_name in ds.path:
                dataset = ds
                break
        
        if not dataset:
            raise ValueError(f"Unknown dataset: {dataset_name}")
        
        # Run experiments
        if len(strategies) == 1:
            summary, results = self.run_single_experiment(
                student_model=student,
                teacher_model=teacher,
                strategy=strategies[0],
                dataset=dataset,
                max_iters=max_iters
            )
            return [(summary, results)]
        else:
            return self.run_multiple_experiments(
                student_model=student,
                teacher_model=teacher,
                strategies=strategies,
                dataset=dataset,
                max_iters=max_iters
            )
