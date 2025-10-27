"""
Memory Pipeline - Self-reflection with pluggable retrieval strategies

Evaluation pipeline with memory system and configurable retrieval strategies:
- TF-IDF retrieval
- Rule-key retrieval  
- No retrieval (memory stored but not retrieved)
"""

import json
import time
import os
from typing import List, Dict, Any
from dataclasses import asdict

from src.pipeline.base import BasePipeline, TaskResult, EvaluationSummary
from src.memory.retrieval import RetrievalStrategy
from src.core.logger import get_logger
from src.providers.factory import build_client
from src.evaluation.critic import SimpleCritic, Critique
from src.memory.store import JsonMemoryStore, Feedback
from src.memory.utils import clean_feedback_message
from src.models.tinyllama_1_1b.prompts import build_reflection_prompt

logger = get_logger(__name__)


def build_prompt(question: str, context: str = "") -> str:
    """
    Build prompt for student with optional memory context.
    
    Args:
        question: The question to answer
        context: Retrieved structured reflection from memory
        
    Returns:
        Formatted prompt string
    """
    if context:
        return (
            f"You previously answered a similar question incorrectly.\n"
            f"Below is your self-reflection to help you improve:\n\n"
            f"{context}\n\n"
            f"Now answer this question, applying the lessons learned:\n"
            f"Question: {question}\n\n"
            f"Think step-by-step:\n"
            f"1. What did you learn from the reflection above?\n"
            f"2. What specific concepts must you include?\n"
            f"3. How should you structure your answer?\n\n"
            f"Your answer:"
        )
    return f"Question: {question}\n\nProvide a clear and concise answer."


class MemoryPipeline(BasePipeline):
    """
    Self-reflection pipeline with memory and pluggable retrieval.
    
    Uses SimpleCritic (Pure Checker) to validate answers and generates
    self-reflections for memory. Retrieval strategy determines how past
    reflections are retrieved and stored.
    """
    
    def __init__(
        self,
        student_provider: str,
        retrieval_strategy: RetrievalStrategy
    ):
        """
        Initialize memory pipeline.
        
        Args:
            student_provider: Provider name for student model
            retrieval_strategy: Strategy for retrieving/storing memory
        """
        self.student_provider = student_provider
        self.retrieval_strategy = retrieval_strategy
    
    def get_experiment_name(self) -> str:
        return f"memory_{self.retrieval_strategy.name}"
    
    def run(
        self,
        dataset_path: str,
        output_dir: str,
        max_iters: int = 3,
        **kwargs
    ) -> tuple[EvaluationSummary, List[TaskResult]]:
        """
        Run memory-based evaluation with retrieval.
        
        Args:
            dataset_path: Path to JSONL dataset
            output_dir: Directory to save results
            max_iters: Maximum iterations per task
            **kwargs: Strategy-specific parameters
            
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
        logger.info(f"Using retrieval strategy: {self.retrieval_strategy.name}")
        
        # Initialize components
        student = build_client(self.student_provider)
        critic = SimpleCritic()
        
        # Memory path
        memory_path = os.path.join(output_dir, "memory.json")
        memory = JsonMemoryStore(memory_path, cap_per_task=5, cap_per_rule=5)
        
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
            total_retrieval_ms = 0
            total_gen_ms = 0
            
            for attempt in range(1, max_iters + 1):
                attempts = attempt
                
                # Retrieve relevant feedback using strategy
                past_feedbacks, retrieval_time_ms = self.retrieval_strategy.retrieve(
                    memory, question, **kwargs
                )
                total_retrieval_ms += retrieval_time_ms
                
                # Build context from retrieved feedbacks
                use_cleaning = os.getenv("USE_CONTEXT_CLEANING", "true").lower() == "true"
                if use_cleaning and past_feedbacks:
                    cleaned_messages = [clean_feedback_message(fb.message) for fb in past_feedbacks]
                    context = "\n".join([f"- {msg}" for msg in cleaned_messages if msg])
                else:
                    context = "\n".join([f"- {fb.message}" for fb in past_feedbacks]) if past_feedbacks else ""
                
                # Debug logging
                if past_feedbacks:
                    logger.debug(f"  Retrieved {len(past_feedbacks)} feedbacks")
                else:
                    logger.debug(f"  No feedbacks retrieved")
                
                # Build prompt with context
                prompt = build_prompt(question, context)
                
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
                    f"retrieved={len(past_feedbacks)} | retrieval={retrieval_time_ms}ms | "
                    f"gen={gen_time_ms}ms | answer='{answer[:60]}...'"
                )
                
                if critique.satisfied:
                    passed = True
                    logger.info(f"Task {task_id} PASSED")
                    break
                else:
                    # Generate self-reflection using error details from SimpleCritic
                    use_self_reflection = os.getenv("USE_SELF_REFLECTION", "true").lower() == "true"
                    
                    if use_self_reflection:
                        reflection_prompt = build_reflection_prompt(question, answer, critique)
                        
                        reflection_resp = student.chat(
                            [{"role": "user", "content": reflection_prompt}],
                            max_tokens=200,
                            temperature=0.7
                        )
                        
                        self_reflection = reflection_resp.text.strip()
                        feedback_message = self_reflection
                        feedback_source = "self_reflection"
                        
                        logger.info(f"  Self-reflection generated ({len(self_reflection)} chars)")
                        logger.debug(f"  Content: {self_reflection}")
                    else:
                        # Fallback: create basic error description
                        if critique.error_type == "missing_keywords":
                            missing = critique.missing_keywords or []
                            feedback_message = f"Missing required concepts: {', '.join(missing)}"
                        elif critique.error_type == "exact_match_failed":
                            feedback_message = f"Expected exact answer: '{critique.expected_exact}'"
                        elif critique.error_type == "empty_answer":
                            feedback_message = "Answer was empty"
                        else:
                            feedback_message = "Answer was incorrect"
                        
                        feedback_source = "critic"
                        logger.info(f"  Using fallback feedback: {feedback_message}")
                    
                    # Store feedback using strategy
                    fb = Feedback(
                        task_id=task_id,
                        message=feedback_message,
                        source=feedback_source
                    )
                    self.retrieval_strategy.store_feedback(memory, question, fb)
            
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
                retrieval_time_ms=total_retrieval_ms,
                generation_time_ms=total_gen_ms,
                total_time_ms=task_time_ms
            ))
        
        # Compute summary
        passed_count = sum(1 for r in results if r.passed)
        failed_count = len(results) - passed_count
        success_rate = passed_count / len(results) if results else 0.0
        
        avg_attempts = sum(r.attempts for r in results) / len(results) if results else 0.0
        avg_retrieval_ms = sum(r.retrieval_time_ms for r in results) / len(results) if results else 0.0
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
        logger.info("MEMORY EVALUATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Experiment: {summary.experiment}")
        logger.info(f"Total tasks: {summary.total_tasks}")
        logger.info(f"Passed: {summary.passed}")
        logger.info(f"Failed: {summary.failed}")
        logger.info(f"Success rate: {summary.success_rate:.1%}")
        logger.info(f"Avg attempts: {summary.avg_attempts:.1f}")
        logger.info(f"Avg retrieval time: {summary.avg_retrieval_ms:.0f}ms")
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
        
        # Note: Memory is auto-saved via JsonMemoryStore._save()
        
        logger.info(f"Artifacts saved to {output_dir}/")
