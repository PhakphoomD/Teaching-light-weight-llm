"""
Baseline Pipeline - No memory, no retrieval

Pure evaluation loop without any memory system.
Used as baseline to measure improvement from memory-based approaches.
"""

import json
import time
import os
from typing import List, Dict, Any
from dataclasses import asdict

from src.pipeline.base import BasePipeline, TaskResult, EvaluationSummary
from src.core.logger import get_logger
from src.providers.factory import build_client
from src.evaluation.critic import SimpleCritic, Critique

logger = get_logger(__name__)


class BaselinePipeline(BasePipeline):
    """
    Baseline experiment pipeline without memory.
    
    Evaluates model performance without any learning/reflection mechanism.
    """
    
    def __init__(self, student_provider: str):
        """
        Initialize baseline pipeline.
        
        Args:
            student_provider: Provider name for student model
        """
        self.student_provider = student_provider
    
    def get_experiment_name(self) -> str:
        return "baseline_no_memory"
    
    def run(
        self,
        dataset_path: str,
        output_dir: str,
        max_iters: int = 3,
        **kwargs
    ) -> tuple[EvaluationSummary, List[TaskResult]]:
        """
        Run baseline evaluation without memory.
        
        Args:
            dataset_path: Path to JSONL dataset
            output_dir: Directory to save results
            max_iters: Maximum iterations per task (typically 1 for baseline)
            **kwargs: Ignored for baseline
            
        Returns:
            Tuple of (EvaluationSummary, List[TaskResult])
        """
        start_time = time.time()
        
        # Load dataset
        dataset: List[Dict[str, Any]] = []
        with open(dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                dataset.append(json.loads(line))
        
        logger.info(f"Loaded {len(dataset)} tasks from {dataset_path}")
        logger.info(f"Running baseline evaluation (no memory)")
        
        # Initialize components
        student = build_client(self.student_provider)
        critic = SimpleCritic()
        
        # Track results
        results: List[TaskResult] = []
        
        for idx, item in enumerate(dataset):
            task_id = item["id"]
            question = item["question"]
            expected_keywords = item.get("expected_keywords", [])
            expected_exact = item.get("expected_exact")
            
            logger.info(f"Task {idx+1}/{len(dataset)}: {task_id}")
            
            task_start = time.time()
            passed = False
            final_answer = ""
            attempts = 0
            total_gen_ms = 0
            
            for attempt in range(1, max_iters + 1):
                attempts = attempt
                
                # Simple prompt without any context
                prompt = f"Question: {question}\n\nProvide a clear and concise answer."
                
                # Student generates answer
                gen_start = time.time()
                resp = student.chat(
                    [{"role": "user", "content": prompt}],
                    max_tokens=200,
                    temperature=0.3
                )
                gen_time_ms = int((time.time() - gen_start) * 1000)
                total_gen_ms += gen_time_ms
                
                answer = resp.text.strip()
                final_answer = answer
                
                # Critic evaluates
                critique: Critique = critic.evaluate(
                    {
                        "expected_keywords": expected_keywords,
                        "expected_exact": expected_exact
                    },
                    answer
                )
                
                logger.info(
                    f"  Attempt {attempt}: satisfied={critique.satisfied} | "
                    f"gen={gen_time_ms}ms | answer='{answer[:60]}...'"
                )
                
                if critique.satisfied:
                    passed = True
                    logger.info(f"Task {task_id} PASSED")
                    break
            
            if not passed:
                logger.info(f"Task {task_id} FAILED after {attempts} attempt(s)")
            
            task_time_ms = int((time.time() - task_start) * 1000)
            
            # Record result
            results.append(TaskResult(
                task_id=task_id,
                question=question,
                passed=passed,
                attempts=attempts,
                final_answer=final_answer,
                retrieval_time_ms=0,  # No retrieval in baseline
                generation_time_ms=total_gen_ms,
                total_time_ms=task_time_ms
            ))
        
        # Compute summary
        passed_count = sum(1 for r in results if r.passed)
        failed_count = len(results) - passed_count
        success_rate = passed_count / len(results) if results else 0.0
        
        avg_attempts = sum(r.attempts for r in results) / len(results) if results else 0.0
        avg_retrieval_ms = 0.0  # No retrieval
        avg_generation_ms = sum(r.generation_time_ms for r in results) / len(results) if results else 0.0
        avg_total_ms = sum(r.total_time_ms for r in results) / len(results) if results else 0.0
        
        total_runtime_s = time.time() - start_time
        
        summary = EvaluationSummary(
            experiment=self.get_experiment_name(),
            total_tasks=len(results),
            passed=passed_count,
            failed=failed_count,
            success_rate=success_rate,
            avg_attempts=avg_attempts,
            avg_retrieval_ms=avg_retrieval_ms,
            avg_generation_ms=avg_generation_ms,
            avg_total_ms=avg_total_ms,
            total_runtime_s=total_runtime_s
        )
        
        # Save artifacts
        self._save_artifacts(summary, results, output_dir)
        
        # Log summary
        logger.info("=" * 80)
        logger.info("BASELINE EVALUATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total tasks: {summary.total_tasks}")
        logger.info(f"Passed: {summary.passed}")
        logger.info(f"Failed: {summary.failed}")
        logger.info(f"Success rate: {summary.success_rate:.1%}")
        logger.info(f"Avg attempts: {summary.avg_attempts:.1f}")
        logger.info(f"Avg generation time: {summary.avg_generation_ms:.0f}ms")
        logger.info(f"Avg total time per task: {summary.avg_total_ms:.0f}ms")
        logger.info(f"Total runtime: {summary.total_runtime_s:.1f}s")
        logger.info("=" * 80)
        
        return summary, results
    
    def _save_artifacts(
        self,
        summary: EvaluationSummary,
        results: List[TaskResult],
        output_dir: str
    ) -> None:
        """Save evaluation artifacts to disk."""
        os.makedirs(output_dir, exist_ok=True)
        
        # Save summary
        summary_path = os.path.join(output_dir, "summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(asdict(summary), f, indent=2)
        
        # Save detailed results
        results_path = os.path.join(output_dir, "results.jsonl")
        with open(results_path, "w", encoding="utf-8") as f:
            for result in results:
                f.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
        
        logger.info(f"Artifacts saved to {output_dir}/")
