"""
Base Pipeline - Abstract base class for all experiment pipelines

Defines the common interface and shared data structures for:
- Baseline experiments (no memory)
- Memory experiments (with retrieval)
- A/B testing experiments
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class TaskResult:
    """Result for a single task."""
    task_id: str
    question: str
    passed: bool
    attempts: int
    final_answer: str
    retrieval_time_ms: int
    generation_time_ms: int
    total_time_ms: int
    # Additional details
    error_type: str = ""
    missing_keywords: List[str] = field(default_factory=list)
    # Score tracking per attempt
    scores: List[float] = field(default_factory=list)  # Score per attempt
    first_attempt_passed: bool = False
    used_memory: bool = False  # Whether memory was retrieved
    memory_helped: bool = False  # Whether memory improved the answer
    early_stopped: bool = False  # Whether stopped early due to no improvement


@dataclass
class EvaluationSummary:
    """Summary of evaluation run with comprehensive metrics."""
    experiment: str
    total_tasks: int
    passed: int
    failed: int
    success_rate: float
    avg_attempts: float
    avg_retrieval_ms: float
    avg_generation_ms: float
    avg_total_ms: float
    total_runtime_s: float
    
    # === 1. PERFORMANCE METRICS ===
    mean_score: float = 0.0  # Average score across all tasks
    pass_rate_at_7: float = 0.0  # % tasks with score >= 7
    pass_rate_at_8: float = 0.0  # % tasks with score >= 8
    first_attempt_success: int = 0  # Tasks passed on first try
    first_attempt_pass_rate: float = 0.0  # % passed on first try
    
    # === 2. LEARNING & GENERALISATION METRICS ===
    learning_gain: float = 0.0  # Average score improvement per attempt (ΔScore)
    repeat_error_rate: float = 0.0  # % tasks that failed with same error multiple times
    memory_utilization_rate: float = 0.0  # % tasks that successfully used memory
    retrieval_precision_at_3: float = 0.0  # Precision of top-3 memory retrieval
    cross_task_transfer: float = 0.0  # % tasks helped by memories from other tasks
    
    # === 3. EFFICIENCY METRICS ===
    tokens_per_task: float = 0.0  # Average tokens per task
    tokens_per_success: float = 0.0  # Average tokens per successful task
    latency_per_task_ms: float = 0.0  # Average latency per task
    retrieval_hit_rate: float = 0.0  # % tasks that found relevant memories
    memory_size: int = 0  # Total entries in memory store
    
    # === LEGACY/DETAILED METRICS ===
    memory_enabled: bool = False
    canonical_enabled: bool = False
    total_retrievals: int = 0
    avg_retrieved_per_task: float = 0.0
    improved_on_retry: int = 0  # Tasks that passed after reflection
    early_stopped_tasks: int = 0  # Tasks that stopped early due to no improvement
    avg_retrieved_per_task: float = 0.0
    improved_on_retry: int = 0  # Tasks that passed after reflection
    
    # Token usage
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    avg_prompt_tokens: float = 0.0
    avg_completion_tokens: float = 0.0
    avg_total_tokens: float = 0.0
    
    # Cost information
    student_model: str = ""
    teacher_model: str = ""
    student_tokens: int = 0  # Total student tokens
    teacher_tokens: int = 0  # Total teacher tokens (if used)
    student_cost: float = 0.0  # Actual cost (0 for local)
    teacher_cost: float = 0.0  # Actual cost (0 for local)
    total_cost: float = 0.0  # Total actual cost
    estimated_cost: float = 0.0  # Estimated cost if using API (for local models)
    is_local_student: bool = True
    is_local_teacher: bool = True
    
    # Additional analysis
    canonical_coverage: float = 0.0  
    drift_to_fallback_rate: float = 0.0


class BasePipeline(ABC):
    """
    Abstract base class for experiment pipelines.
    
    Defines the interface that all experiment runners must implement.
    """
    
    @abstractmethod
    def run(
        self,
        dataset_path: str,
        output_dir: str,
        max_iters: int = 3,
        **kwargs
    ) -> tuple[EvaluationSummary, List[TaskResult]]:
        """
        Run the experiment pipeline.
        
        Args:
            dataset_path: Path to JSONL dataset
            output_dir: Directory to save results
            max_iters: Maximum iterations per task
            **kwargs: Pipeline-specific parameters
            
        Returns:
            Tuple of (EvaluationSummary, List[TaskResult])
        """
        pass
    
    @abstractmethod
    def get_experiment_name(self) -> str:
        """Return the experiment name for logging."""
        pass
