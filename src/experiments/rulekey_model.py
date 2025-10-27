"""
RuleKey Model Experiment - Memory with Rule-based Retrieval

Evaluates TinyLlama 1.1B with memory system using rule-key pattern matching retrieval.

Usage:
    python -m src.experiments.rulekey_model
    
Environment variables:
    DATASET_PATH: Path to JSONL dataset (default: data/datasets/alpaca_20.jsonl)
    OUTPUT_DIR: Output directory (default: logs/experiments/tinyllama_1_1b/memory_rulekey)
    MAX_ITERS: Max iterations per task (default: 3)
    STUDENT_PROVIDER: Provider name (default: local)
    RETRIEVAL_K: Number of feedbacks to retrieve (default: 3)
"""

import os
from datetime import datetime
from src.core.logger import get_logger
from src.pipeline.memory_pipeline import MemoryPipeline
from src.memory.retrieval import RuleKeyRetrieval

# Import providers to trigger registration
import src.providers.local_client  # noqa: F401
import src.providers.groq_client  # noqa: F401
import src.providers.gemini_client  # noqa: F401

logger = get_logger(__name__)


def main():
    """Run rule-key retrieval experiment for TinyLlama 1.1B."""
    # Configuration
    dataset_path = os.getenv("DATASET_PATH", "data/datasets/alpaca_20.jsonl")
    output_dir = os.getenv("OUTPUT_DIR", "logs/experiments/tinyllama_1_1b/memory_rulekey")
    max_iters = int(os.getenv("MAX_ITERS", "3"))
    student_provider = os.getenv("STUDENT_PROVIDER", "local")
    retrieval_k = int(os.getenv("RETRIEVAL_K", "3"))
    
    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(output_dir, f"run_{timestamp}")
    
    logger.info("=" * 80)
    logger.info("RULEKEY EXPERIMENT - TinyLlama 1.1B (Memory + Rule-based Retrieval)")
    logger.info("=" * 80)
    logger.info(f"Dataset: {dataset_path}")
    logger.info(f"Output: {run_dir}")
    logger.info(f"Max iterations: {max_iters}")
    logger.info(f"Provider: {student_provider}")
    logger.info(f"Retrieval K: {retrieval_k}")
    logger.info("=" * 80)
    
    # Initialize pipeline with rule-key retrieval
    retrieval_strategy = RuleKeyRetrieval(k=retrieval_k)
    pipeline = MemoryPipeline(
        student_provider=student_provider,
        retrieval_strategy=retrieval_strategy
    )
    
    # Run experiment
    summary, results = pipeline.run(
        dataset_path=dataset_path,
        output_dir=run_dir,
        max_iters=max_iters
    )
    
    logger.info("")
    logger.info("RuleKey experiment completed successfully!")
    logger.info(f"Results saved to: {run_dir}")
    
    return summary, results


if __name__ == "__main__":
    main()
