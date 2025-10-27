"""
Base Pipeline - Abstract base class for all experiment pipelines

Defines the common interface and shared data structures for:
- Baseline experiments (no memory)
- Memory experiments (with retrieval)
- A/B testing experiments
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Any


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


@dataclass
class EvaluationSummary:
    """Summary of evaluation run."""
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
