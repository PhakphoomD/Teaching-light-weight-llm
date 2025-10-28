"""
Unified Pipeline - Single configurable pipeline for all experiment types

This replaces separate pipelines with one configurable implementation.
"""

import json
import time
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict
from datetime import datetime

from src.pipelines.base import BasePipeline, TaskResult, EvaluationSummary
from src.core.logger import get_logger
from src.model_factory import get_prompt_builder
from src.evaluation.critic import SimpleCritic, Critique
from src.memory.store import JsonMemoryStore, Feedback, FeedbackMetadata
from src.memory.utils import clean_feedback_message
from src.memory.key_generator import MultiKeyGenerator
from src.memory.retrieval import TFIDFRetrieval, RuleKeyRetrieval, EnhancedRuleKeyRetrieval
from src.memory.lesson_filter import clean_lesson, is_high_quality_lesson
from src.memory.token_tracker import TokenTracker
from src.providers.factory import build_client

logger = get_logger(__name__)


class UnifiedPipeline(BasePipeline):
    """
    Unified experiment pipeline with configurable features.

    Features are toggled through strategy configuration:
    - memory: Enable/disable memory storage
    - reflection: Enable/disable self-reflection
    - canonical: Enable/disable canonical concept mapping
    - retrieval: Choose retrieval strategy (tfidf, multikey, multikey_tfidf, none)
    """

    def __init__(
        self,
        student_model: Any,  # ModelConfig
        teacher_model: Any,  # ModelConfig
        strategy_config: dict,
        output_dir: str,
    ):
        self.student_model = student_model
        self.teacher_model = teacher_model
        self.strategy_config = strategy_config
        self.output_dir = output_dir

        # Extract feature flags
        self.features = strategy_config.get('features', {})
        self.params = strategy_config.get('params', {})

        # Initialize model clients from config
        self.student_client = self._build_client_from_model_config(self.student_model)
        self.teacher_client = self._build_client_from_model_config(self.teacher_model)
        self.prompts = get_prompt_builder(self.student_model.key)

        # Initialize critic (always needed)
        self.critic = SimpleCritic()

        # Initialize memory components (if enabled)
        self.memory_store: Optional[JsonMemoryStore] = None
        self.key_generator: Optional[MultiKeyGenerator] = None
        self.retrieval = None

        if self.features.get('memory'):
            memory_path = os.path.join(output_dir, "memory_store.jsonl")
            self.memory_store = JsonMemoryStore(memory_path)

            if self.features.get('canonical'):
                self.key_generator = MultiKeyGenerator()

            # Initialize retrieval strategy
            retrieval_flag = self.features.get('retrieval')
            if retrieval_flag and retrieval_flag != 'none':
                self.retrieval = self._init_retrieval(retrieval_flag)

        # Initialize token tracker
        self.token_tracker = TokenTracker(
            student_model_name=self.student_model.key,
            teacher_model_name=self.teacher_model.key,
            strategy_name=strategy_config.get('name', 'unknown'),
            experiment_id=os.path.basename(output_dir),
        )

        logger.info("Initialized UnifiedPipeline:")
        logger.info(f"  Strategy: {strategy_config.get('name', '')}")
        logger.info(f"  Student: {self.student_model.key}")
        logger.info(f"  Teacher: {self.teacher_model.key}")
        logger.info(f"  Features: {self.features}")

    def _build_client_from_model_config(self, model: Any):  # ModelConfig
        """Instantiate a provider client from a ModelConfig."""
        if model.type == 'local':
            device = model.params.get('device')
            if device == 'auto':
                device = None
            return build_client('local', model=model.model_id, device=device)
        elif model.type == 'api':
            provider = model.params.get('provider')
            if not provider:
                raise ValueError(f"API model '{model.key}' missing provider field")
            return build_client(provider, model=model.model_id)
        else:
            raise ValueError(f"Unknown model type: {model.type}")

    def _init_retrieval(self, retrieval_type: str):
        if retrieval_type == 'tfidf':
            return TFIDFRetrieval(k=self.params.get('k', 3))
        elif retrieval_type == 'multikey':
            # Use EnhancedRuleKeyRetrieval for canonical multi-key
            return EnhancedRuleKeyRetrieval(
                k=self.params.get('k_similar', 2),
                tfidf_threshold=self.params.get('tfidf_min_cosine', 0.30)
            )
        elif retrieval_type == 'multikey_tfidf':
            # Full system with EnhancedRuleKeyRetrieval (includes TF-IDF fallback)
            return EnhancedRuleKeyRetrieval(
                k=self.params.get('k_similar', 2),
                tfidf_threshold=self.params.get('tfidf_min_cosine', 0.30)
            )
        else:
            return None

    def get_experiment_name(self) -> str:
        return self.strategy_config.get('short_name', self.strategy_config.get('name', 'experiment'))

    def run(
        self,
        dataset_path: str,
        output_dir: str,
        max_iters: Optional[int] = None,
        **kwargs,
    ) -> Tuple[EvaluationSummary, List[TaskResult]]:
        start_time = time.time()

        if max_iters is None:
            max_iters = int(self.params.get('max_iters', 1))

        # Load dataset
        dataset: List[Dict[str, Any]] = []
        with open(dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                dataset.append(json.loads(line))

        logger.info("=" * 80)
        logger.info(f"Running: {self.strategy_config.get('name', '')}")
        logger.info("=" * 80)
        logger.info(f"Dataset: {dataset_path} ({len(dataset)} tasks)")
        logger.info(f"Student: {self.student_model.key}")
        logger.info(f"Teacher: {self.teacher_model.key}")
        logger.info(f"Max iterations: {max_iters}")
        logger.info(f"Output: {output_dir}")
        logger.info("=" * 80)

        results: List[TaskResult] = []
        total_tasks = len(dataset)

        for task_idx, task in enumerate(dataset, 1):
            logger.info(f"\n[Task {task_idx}/{total_tasks}] ID: {task.get('id', 'unknown')}")
            task_start = time.time()
            task_result = self._process_task(task, max_iters)
            task_duration = time.time() - task_start
            results.append(task_result)

            if task_result.passed:
                logger.info(f"   Success after {task_result.attempts} attempt(s)")
                logger.info(f"    Total time: {task_duration:.2f}s | Avg: {task_duration/task_result.attempts:.2f}s/attempt")
                if len(task_result.scores) > 1:
                    learning = task_result.scores[-1] - task_result.scores[0]
                    logger.info(f"    Learning Gain: {learning:+.2f} | Memory Used: {task_result.used_memory}")
            else:
                logger.info(f"   Failed after {task_result.attempts} attempt(s)")
                logger.info(f"    Total time: {task_duration:.2f}s | Avg: {task_duration/task_result.attempts:.2f}s/attempt")
                if len(task_result.scores) > 1:
                    learning = task_result.scores[-1] - task_result.scores[0]
                    logger.info(f"    Learning Gain: {learning:+.2f} | Repeat Error: {task_result.attempts > 1}")

        duration = time.time() - start_time
        summary = self._calculate_summary(results, duration)

        self._save_results(output_dir, summary, results)
        
        # Save token usage
        token_filepath = self.token_tracker.save(output_dir)
        logger.info(f"Token usage saved to: {token_filepath}")
        
        # Print token summary
        self.token_tracker.print_summary()
        
        # Print cost summary
        self._print_cost_summary(summary)

        logger.info("\n" + "=" * 80)
        logger.info("EXPERIMENT COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Success rate: {summary.success_rate:.1%} ({summary.passed}/{summary.total_tasks})")
        logger.info(f"  - First attempt: {summary.first_attempt_success}/{summary.total_tasks} ({summary.first_attempt_pass_rate:.1%})")
        logger.info(f"  - Improved on retry: {summary.improved_on_retry}/{summary.total_tasks}")
        if summary.early_stopped_tasks > 0:
            logger.info(f"  - Early stopped: {summary.early_stopped_tasks}/{summary.total_tasks} (no improvement detected)")
        logger.info(f"Avg attempts: {summary.avg_attempts:.2f}")
        
        # Learning metrics summary
        logger.info(f"\nLearning Metrics:")
        logger.info(f"  - Learning Gain (ΔScore): {summary.learning_gain:+.3f} per attempt")
        logger.info(f"  - Repeat-Error Rate: {summary.repeat_error_rate:.1%} (tasks with same error)")
        logger.info(f"  - Reflection Utilisation: {summary.memory_utilization_rate:.1%} (tasks using memory)")
        logger.info(f"  - Cross-Task Transfer: {summary.cross_task_transfer:.1%} (memory helped)")
        
        if summary.memory_enabled:
            logger.info(f"\nMemory System: {' Canonical' if summary.canonical_enabled else ' Basic'}")
            logger.info(f"  - Retrieval hit rate: {summary.retrieval_hit_rate:.1%}")
            logger.info(f"  - Memory size: {summary.memory_size} entries")
            logger.info(f"  - Avg retrieval time: {summary.avg_retrieval_ms:.1f}ms")
        
        logger.info(f"\nPerformance:")
        logger.info(f"  - Avg generation time: {summary.avg_generation_ms:.1f}ms")
        logger.info(f"  - Total time: {summary.total_runtime_s:.2f}s")
        
        # Show token and cost summary at the end
        logger.info(f"\nToken Usage:")
        logger.info(f"  - Total tokens: {summary.total_tokens:,}")
        logger.info(f"  - Prompt tokens: {summary.total_prompt_tokens:,}")
        logger.info(f"  - Completion tokens: {summary.total_completion_tokens:,}")
        logger.info(f"  - Avg per task: {summary.avg_total_tokens:.1f} tokens")
        
        logger.info(f"\nResults saved to: {output_dir}")
        logger.info("=" * 80)

        return summary, results

    def _process_task(self, task: Dict[str, Any], max_iters: int) -> TaskResult:
        task_id = task.get('id', 'unknown')
        question = task['question']

        attempts_data: List[Dict[str, Any]] = []
        success = False
        retrieval_ms_total = 0.0
        generation_ms_total = 0.0
        last_context: List[str] = []  # Track last retrieved context
        
        # Early stop tracking
        no_improvement_count = 0
        max_no_improvement = 3  # Stop if no improvement for 3 consecutive attempts
        previous_answers: List[str] = []

        for iteration in range(1, max_iters + 1):
            attempt_start = time.time()
            logger.info(f"  Attempt {iteration}/{max_iters}")

            # Retrieve context
            context: List[str] = []
            if self.features.get('memory') and self.retrieval and iteration > 1:
                t0 = time.time()
                context = self._retrieve_context(task, task_id)
                last_context = context  # Save for later use
                retrieval_ms_total += (time.time() - t0) * 1000.0
                if context:
                    logger.info(f"    Retrieved {len(context)} memory items")

            # Generate answer
            t1 = time.time()
            answer = self._generate_answer(question, context)
            generation_ms_total += (time.time() - t1) * 1000.0

            # Evaluate answer
            critique = self.critic.evaluate(task, answer)
            success = critique.satisfied
            
            attempt_duration = time.time() - attempt_start
            logger.info(f"    Time: {attempt_duration:.2f}s | Success: {success}")

            attempts_data.append(
                {
                    'iteration': iteration,
                    'answer': answer,
                    'success': success,
                    'error_type': critique.error_type,
                    'missing_keywords': critique.missing_keywords or [],
                }
            )
            
            # Check for repeated answers (no learning)
            if iteration > 1 and answer.strip().lower() in [a.strip().lower() for a in previous_answers]:
                no_improvement_count += 1
                logger.info(f"    WARNING: Repeated answer (no improvement: {no_improvement_count}/{max_no_improvement})")
            else:
                no_improvement_count = 0  # Reset if answer changed
            
            previous_answers.append(answer)

            # Reflection and memory storage
            if self.features.get('reflection') and not success and iteration < max_iters:
                reflection = self._generate_reflection(question, answer, critique)
                if self.features.get('memory') and self.memory_store:
                    self._store_feedback(task, task_id, answer, critique, reflection)
                logger.info(f"    Reflection generated & stored")

            if success:
                logger.info(f"     Correct!")
                break
            
            # Early stop if no improvement for multiple attempts
            if no_improvement_count >= max_no_improvement:
                logger.info(f"     Early stop: No improvement after {max_no_improvement} attempts")
                break
        
        # Determine if early stopped
        early_stopped = no_improvement_count >= max_no_improvement
        
        # Calculate score progression for learning gain
        scores = []
        for attempt in attempts_data:
            # Simple score: 1.0 if success, 0.0 if failed
            # In real system, you might get score from critic
            score = 1.0 if attempt['success'] else 0.0
            scores.append(score)
        
        # Check if first attempt passed
        first_attempt_passed = attempts_data[0]['success'] if attempts_data else False
        
        # Check if memory was used and helped
        used_memory = len(last_context) > 0
        memory_helped = used_memory and success and not first_attempt_passed

        return TaskResult(
            task_id=task_id,
            question=question,
            passed=success,
            attempts=len(attempts_data),
            final_answer=attempts_data[-1]['answer'] if attempts_data else "",
            retrieval_time_ms=int(retrieval_ms_total),
            generation_time_ms=int(generation_ms_total),
            total_time_ms=int(retrieval_ms_total + generation_ms_total),
            error_type=attempts_data[-1].get('error_type', '') if attempts_data else '',
            missing_keywords=attempts_data[-1].get('missing_keywords', []) if attempts_data else [],
            scores=scores,
            first_attempt_passed=first_attempt_passed,
            used_memory=used_memory,
            memory_helped=memory_helped,
            early_stopped=early_stopped
        )

        return TaskResult(
            task_id=task_id,
            question=question,
            passed=success,
            attempts=len(attempts_data),
            final_answer=attempts_data[-1]['answer'] if attempts_data else "",
            retrieval_time_ms=int(retrieval_ms_total),
            generation_time_ms=int(generation_ms_total),
            total_time_ms=int(retrieval_ms_total + generation_ms_total),
            error_type=attempts_data[-1].get('error_type', '') if attempts_data else '',
            missing_keywords=attempts_data[-1].get('missing_keywords', []) if attempts_data else [],
            scores=scores,
            first_attempt_passed=first_attempt_passed,
            used_memory=used_memory,
            memory_helped=memory_helped
        )

    def _generate_answer(self, question: str, context: Optional[List[str]] = None) -> str:
        # Join retrieved context (list of strings) into a single context block
        ctx_str = "\n".join(context) if context else ""
        prompt = self.prompts.build_answer_prompt(question, context=ctx_str)

        params = self.student_model.params
        max_tokens = params.get('max_new_tokens') or params.get('max_tokens') or 256
        temperature = params.get('temperature', 0.7)
        resp = self.student_client.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=int(max_tokens),
            temperature=float(temperature),
        )
        
        # Track student token usage
        self.token_tracker.track_student(
            resp.usage.prompt_tokens,
            resp.usage.completion_tokens
        )
        
        return (resp.text or "").strip()

    def _generate_reflection(self, question: str, answer: str, critique: Critique) -> str:
        temp = self.params.get('temperature_reflection', 0.25)
        max_tokens = self.params.get('max_tokens_reflection', 160)

        # Build simple reflection prompt
        # Since build_reflection_prompt expects FeedbackLite, we'll use a simpler approach
        missing = critique.missing_keywords or []
        if missing:
            hint = f"Your answer is missing these important keywords: {', '.join(missing)}"
        else:
            hint = "Your answer doesn't match the expected format or content."
        
        prompt = f"""Question: {question}

Your answer: {answer}

Problem: {hint}

Provide a concise lesson (2-3 sentences) on what was wrong and how to fix it:"""

        resp = self.teacher_client.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=int(max_tokens),
            temperature=float(temp),
        )
        
        # Track teacher token usage
        self.token_tracker.track_teacher(
            resp.usage.prompt_tokens,
            resp.usage.completion_tokens
        )
        
        return clean_feedback_message(resp.text or "")

    def _retrieve_context(self, task: Dict[str, Any], task_id: str) -> List[str]:
        if not self.retrieval or not self.memory_store:
            return []

        question = task['question']
        
        # Retrieve using the strategy's retrieve method
        feedbacks, _ = self.retrieval.retrieve(
            memory=self.memory_store,
            question=question,
            task_id=task_id,
            k_task=int(self.params.get('k_task', 2)),
        )

        # Format as context strings
        context: List[str] = []
        for fb in feedbacks:
            context.append(f"Previous mistake: {fb.message}")
        return context

    def _store_feedback(
        self,
        task: Dict[str, Any],
        task_id: str,
        answer: str,
        critique: Critique,
        reflection: str,
    ):
        if not self.memory_store:
            return
        
        # Clean and validate lesson quality
        clean_lesson_text = clean_lesson(reflection)
        
        # Generate error keys from critique
        error_keys = []
        if critique.error_type:
            error_keys.append(f"error:{critique.error_type}")
        if critique.missing_keywords:
            error_keys.append("error:missing_keywords")
        
        # Quality check
        if not is_high_quality_lesson(clean_lesson_text, error_keys):
            logger.debug(f"Skipping low-quality lesson for task {task_id}")
            return
        
        # Create base Feedback object with cleaned lesson
        feedback = Feedback(
            task_id=task_id,
            message=clean_lesson_text,  # Use cleaned lesson
            source="teacher_reflection"
        )
        
        # Use canonical multi-key indexing if enabled
        if self.features.get('canonical') and self.key_generator:
            # Generate multi-keys using canonical concepts
            keys_result = self.key_generator.generate_keys(
                question=task['question'],
                task_id=task_id
            )
            
            # Add error keys
            all_keys = keys_result.all_keys.copy()
            for err_key in error_keys:
                all_keys.add(err_key)
            
            # Create metadata
            metadata = FeedbackMetadata(
                score=0.0,
                timestamp=datetime.now().isoformat(),
                concept_ids=[],
                source="teacher_reflection",
                error_types=error_keys
            )
            
            # Use add_feedback_multi_key for canonical indexing
            self.memory_store.add_feedback_multi_key(
                keys=all_keys,
                fb=feedback,
                metadata=metadata
            )
            self.memory_store.add_feedback_multi_key(
                keys=keys_result.all_keys,
                fb=feedback,
                metadata=metadata
            )
        else:
            # Legacy storage for non-canonical strategies
            self.memory_store.add_feedback(feedback)
        # Also index into strategy-specific storage for future retrieval
        if self.retrieval is not None:
            try:
                self.retrieval.store_feedback(self.memory_store, task['question'], feedback)
            except Exception:
                # Retrieval strategies should be robust; ignore store issues
                pass

    def _calculate_summary(self, results: List[TaskResult], duration: float) -> EvaluationSummary:
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        avg_attempts = (sum(r.attempts for r in results) / total) if total else 0.0
        avg_retrieval = (sum(r.retrieval_time_ms for r in results) / total) if total else 0.0
        avg_generation = (sum(r.generation_time_ms for r in results) / total) if total else 0.0
        avg_total = (sum(r.total_time_ms for r in results) / total) if total else 0.0
        
        # === 1. PERFORMANCE METRICS ===
        # Calculate mean score across all tasks
        all_scores = []
        for r in results:
            if r.scores:
                all_scores.extend(r.scores)
        mean_score = (sum(all_scores) / len(all_scores)) if all_scores else 0.0
        
        # Pass rates at different thresholds
        # For now, binary: passed = score 1.0 (100%), failed = 0.0
        # In future, you can use actual critic scores (0-10 scale)
        pass_rate_at_7 = (passed / total) if total else 0.0  # Placeholder
        pass_rate_at_8 = (passed / total) if total else 0.0  # Placeholder
        
        # First attempt success
        first_attempt_success = sum(1 for r in results if r.first_attempt_passed)
        first_attempt_pass_rate = (first_attempt_success / total) if total > 0 else 0.0
        
        # === 2. LEARNING & GENERALISATION METRICS ===
        # Learning gain (ΔScore per attempt)
        learning_gains = []
        for r in results:
            if len(r.scores) > 1:
                # Calculate improvement from first to last
                gain = r.scores[-1] - r.scores[0]
                learning_gains.append(gain)
        learning_gain = (sum(learning_gains) / len(learning_gains)) if learning_gains else 0.0
        
        # Repeat error rate (tasks that failed with same error multiple times)
        repeat_errors = 0
        for r in results:
            if r.attempts > 1 and not r.passed:
                # Check if error type is same across attempts (simplified)
                # In real system, track error_type per attempt
                repeat_errors += 1
        repeat_error_rate = (repeat_errors / max(failed, 1)) if failed > 0 else 0.0
        
        # Memory utilization rate
        memory_used_count = sum(1 for r in results if r.used_memory)
        memory_utilization_rate = (memory_used_count / total) if total > 0 else 0.0
        
        # Cross-task transfer (tasks helped by memory from other tasks)
        cross_task_transfer = sum(1 for r in results if r.memory_helped)
        cross_task_transfer_rate = (cross_task_transfer / total) if total > 0 else 0.0
        
        # Retrieval metrics
        tasks_with_retrieval = sum(1 for r in results if r.retrieval_time_ms > 0)
        retrieval_hit_rate = (tasks_with_retrieval / total) if total > 0 else 0.0
        
        # === 3. EFFICIENCY METRICS ===
        # Get token usage from tracker
        token_summary = self.token_tracker.get_summary()
        
        # Tokens per task
        tokens_per_task = token_summary.total_tokens() / max(total, 1)
        
        # Tokens per success
        tokens_per_success = token_summary.total_tokens() / max(passed, 1) if passed > 0 else 0.0
        
        # Latency per task
        latency_per_task_ms = avg_total
        
        # Memory size (count entries in memory store if available)
        memory_size = 0
        if self.memory_store:
            try:
                # Count entries in memory store
                memory_size = len(self.memory_store._data.get('entries', {}))
            except:
                memory_size = 0
        
        # Calculate improved on retry
        improved_on_retry = sum(1 for r in results if r.passed and r.attempts > 1)
        
        # Count early stopped tasks
        early_stopped_tasks = sum(1 for r in results if r.early_stopped)
        
        return EvaluationSummary(
            experiment=self.strategy_config.get('name', 'experiment'),
            total_tasks=total,
            passed=passed,
            failed=failed,
            success_rate=(passed / total) if total else 0.0,
            avg_attempts=avg_attempts,
            avg_retrieval_ms=avg_retrieval,
            avg_generation_ms=avg_generation,
            avg_total_ms=avg_total,
            total_runtime_s=duration,
            
            # === 1. PERFORMANCE METRICS ===
            mean_score=mean_score,
            pass_rate_at_7=pass_rate_at_7,
            pass_rate_at_8=pass_rate_at_8,
            first_attempt_success=first_attempt_success,
            first_attempt_pass_rate=first_attempt_pass_rate,
            
            # === 2. LEARNING & GENERALISATION METRICS ===
            learning_gain=learning_gain,
            repeat_error_rate=repeat_error_rate,
            memory_utilization_rate=memory_utilization_rate,
            retrieval_precision_at_3=0.0,  # TODO: Calculate from retrieval results
            cross_task_transfer=cross_task_transfer_rate,
            
            # === 3. EFFICIENCY METRICS ===
            tokens_per_task=tokens_per_task,
            tokens_per_success=tokens_per_success,
            latency_per_task_ms=latency_per_task_ms,
            retrieval_hit_rate=retrieval_hit_rate,
            memory_size=memory_size,
            
            # Token usage
            total_prompt_tokens=token_summary.total_prompt_tokens(),
            total_completion_tokens=token_summary.total_completion_tokens(),
            total_tokens=token_summary.total_tokens(),
            avg_prompt_tokens=token_summary.total_prompt_tokens() / max(total, 1),
            avg_completion_tokens=token_summary.total_completion_tokens() / max(total, 1),
            avg_total_tokens=token_summary.total_tokens() / max(total, 1),
            
            # Cost information (will be calculated in _print_cost_summary)
            student_model=self.student_model.key,
            teacher_model=self.teacher_model.key,
            student_tokens=token_summary.student_usage.total_tokens,
            teacher_tokens=token_summary.teacher_usage.total_tokens if token_summary.teacher_usage else 0,
            student_cost=0.0,  # Calculated below
            teacher_cost=0.0,  # Calculated below
            total_cost=0.0,  # Calculated below
            estimated_cost=0.0,  # Calculated below
            is_local_student=True,  # Calculated below
            is_local_teacher=True,  # Calculated below
            
            # Legacy metrics
            memory_enabled=self.features.get('memory', False),
            canonical_enabled=self.features.get('canonical', False),
            total_retrievals=tasks_with_retrieval,
            avg_retrieved_per_task=(tasks_with_retrieval / total) if total > 0 else 0.0,
            improved_on_retry=improved_on_retry,
            early_stopped_tasks=early_stopped_tasks
        )
        
        # Calculate and populate cost information
        self._populate_cost_info(summary)
        return summary
    
    def _populate_cost_info(self, summary: EvaluationSummary):
        """Populate cost information in the summary"""
        PRICING = {
            "tinyllama_1.1b": {"input": 0, "output": 0},
            "llama2_7b": {"input": 0, "output": 0},
            "llama3_8b": {"input": 0, "output": 0},
            "groq_llama3_70b": {"input": 0.59, "output": 0.79},
            "groq_llama3_8b": {"input": 0.05, "output": 0.08},
            "gemini_1.5_pro": {"input": 1.25, "output": 5.00},
            "gemini_1.5_flash": {"input": 0.075, "output": 0.30},
        }
        
        token_summary = self.token_tracker.get_summary()
        student_model = summary.student_model
        teacher_model = summary.teacher_model
        
        # Student cost
        summary.is_local_student = student_model in PRICING and PRICING[student_model]['input'] == 0
        if not summary.is_local_student:
            student_usage = token_summary.student_usage
            summary.student_cost = (
                (student_usage.prompt_tokens / 1_000_000) * PRICING[student_model]['input'] +
                (student_usage.completion_tokens / 1_000_000) * PRICING[student_model]['output']
            )
        else:
            # Estimate cost if using API equivalent
            baseline_price = PRICING.get('groq_llama3_8b', {'input': 0.05, 'output': 0.08})
            student_usage = token_summary.student_usage
            student_estimated = (
                (student_usage.prompt_tokens / 1_000_000) * baseline_price['input'] +
                (student_usage.completion_tokens / 1_000_000) * baseline_price['output']
            )
            summary.estimated_cost += student_estimated
        
        # Teacher cost (if different)
        summary.is_local_teacher = teacher_model in PRICING and PRICING[teacher_model]['input'] == 0
        if token_summary.teacher_usage:
            if not summary.is_local_teacher:
                teacher_usage = token_summary.teacher_usage
                summary.teacher_cost = (
                    (teacher_usage.prompt_tokens / 1_000_000) * PRICING[teacher_model]['input'] +
                    (teacher_usage.completion_tokens / 1_000_000) * PRICING[teacher_model]['output']
                )
            else:
                baseline_price = PRICING.get('groq_llama3_70b', {'input': 0.59, 'output': 0.79})
                teacher_usage = token_summary.teacher_usage
                teacher_estimated = (
                    (teacher_usage.prompt_tokens / 1_000_000) * baseline_price['input'] +
                    (teacher_usage.completion_tokens / 1_000_000) * baseline_price['output']
                )
                summary.estimated_cost += teacher_estimated
        
        summary.total_cost = summary.student_cost + summary.teacher_cost
    
    def _print_cost_summary(self, summary: EvaluationSummary):
        """Print comprehensive metrics summary (no emojis)"""
        token_summary = self.token_tracker.get_summary()
        
        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("METRICS SUMMARY")
        logger.info("=" * 80)
        
        # === 1. PERFORMANCE METRICS ===
        logger.info("\n[1] PERFORMANCE METRICS")
        logger.info("-" * 80)
        logger.info(f"Success Rate:        {summary.success_rate:.1%} ({summary.passed}/{summary.total_tasks})")
        logger.info(f"Mean Score:          {summary.mean_score:.2f}/1.0")
        logger.info(f"First Pass Rate:     {summary.first_attempt_pass_rate:.1%} ({summary.first_attempt_success}/{summary.total_tasks})")
        logger.info(f"Pass Rate @7+:       {summary.pass_rate_at_7:.1%}")
        logger.info(f"Pass Rate @8+:       {summary.pass_rate_at_8:.1%}")
        
        # === 2. LEARNING & GENERALISATION ===
        logger.info("\n[2] LEARNING & GENERALISATION METRICS")
        logger.info("-" * 80)
        logger.info(f"Learning Gain (ΔScore):  {summary.learning_gain:+.3f} per attempt")
        logger.info(f"Repeat Error Rate:       {summary.repeat_error_rate:.1%}")
        logger.info(f"Memory Utilization:      {summary.memory_utilization_rate:.1%}")
        logger.info(f"Cross-Task Transfer:     {summary.cross_task_transfer:.1%}")
        logger.info(f"Retrieval Precision@3:   {summary.retrieval_precision_at_3:.2f}")
        logger.info(f"Memory Size:             {summary.memory_size} entries")
        
        # === 3. EFFICIENCY METRICS ===
        logger.info("\n[3] EFFICIENCY METRICS")
        logger.info("-" * 80)
        logger.info(f"Tokens/Task:         {summary.tokens_per_task:.0f}")
        logger.info(f"Tokens/Success:      {summary.tokens_per_success:.0f}")
        logger.info(f"Latency/Task:        {summary.latency_per_task_ms:.1f}ms")
        logger.info(f"Retrieval Hit Rate:  {summary.retrieval_hit_rate:.1%}")
        logger.info(f"Avg Attempts:        {summary.avg_attempts:.2f}")
        
        # === COST SUMMARY ===
        logger.info("\n[4] COST SUMMARY")
        logger.info("-" * 80)
        
        # Student
        if summary.is_local_student:
            logger.info(f"Student ({summary.student_model}): FREE (local)")
            logger.info(f"  Tokens (estimated): {summary.student_tokens:,}")
            if summary.estimated_cost > 0:
                logger.info(f"  Estimated cost if using API: ~${summary.estimated_cost:.6f}")
        else:
            logger.info(f"Student ({summary.student_model}): ${summary.student_cost:.6f}")
            logger.info(f"  Tokens: {summary.student_tokens:,}")
        
        # Teacher
        if token_summary.teacher_usage:
            if summary.is_local_teacher:
                logger.info(f"Teacher ({summary.teacher_model}): FREE (local)")
                logger.info(f"  Tokens (estimated): {summary.teacher_tokens:,}")
            else:
                logger.info(f"Teacher ({summary.teacher_model}): ${summary.teacher_cost:.6f}")
                logger.info(f"  Tokens: {summary.teacher_tokens:,}")
        
        logger.info("-" * 80)
        if summary.total_cost > 0:
            logger.info(f"TOTAL COST: ${summary.total_cost:.6f}")
            logger.info(f"  Total Tokens: {summary.total_tokens:,}")
            logger.info(f"  Cost/Task:    ${summary.total_cost / max(summary.total_tasks, 1):.6f}")
            if summary.passed > 0:
                logger.info(f"  Cost/Success: ${summary.total_cost / summary.passed:.6f}")
        else:
            logger.info(f"TOTAL COST: FREE (local)")
            logger.info(f"  Total Tokens (estimated): {summary.total_tokens:,}")
            if summary.estimated_cost > 0:
                logger.info(f"  Estimated cost if using API: ~${summary.estimated_cost:.6f}")
        
        logger.info("=" * 80)

    def _save_results(self, output_dir: str, summary: EvaluationSummary, results: List[TaskResult]):
        os.makedirs(output_dir, exist_ok=True)

        summary_path = os.path.join(output_dir, "summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(asdict(summary), f, indent=2, ensure_ascii=False)

        results_path = os.path.join(output_dir, "results.jsonl")
        with open(results_path, "w", encoding="utf-8") as f:
            for result in results:
                f.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")

        config_path = os.path.join(output_dir, "config.json")
        config_data = {
            'strategy': self.strategy_config,
            'student_model': self.student_model.key,
            'teacher_model': self.teacher_model.key,
            'timestamp': datetime.now().isoformat(),
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
