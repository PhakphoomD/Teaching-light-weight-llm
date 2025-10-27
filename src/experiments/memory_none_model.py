"""
Memory-None Model Experiment - Memory without Retrieval

Evaluates TinyLlama 1.1B with memory system but WITHOUT retrieval.
Reflections are stored but never retrieved - tests memory storage overhead.

Usage:
    python -m src.experiments.memory_none_model
    
Environment variables:
    DATASET_PATH: Path to JSONL dataset (default: data/datasets/alpaca_20.jsonl)
    OUTPUT_DIR: Output directory (default: logs/experiments/tinyllama_1_1b/memory_none)
    MAX_ITERS: Max iterations per task (default: 3)
    STUDENT_PROVIDER: Provider name (default: local)
"""

import os
from datetime import datetime
from src.core.logger import get_logger
from src.pipeline.memory_pipeline import MemoryPipeline
from src.memory.retrieval import BaselineRetrieval

# Import providers to trigger registration
import src.providers.local_client  # noqa: F401
import src.providers.groq_client  # noqa: F401
import src.providers.gemini_client  # noqa: F401

logger = get_logger(__name__)


def main():
    """Run memory-without-retrieval experiment for TinyLlama 1.1B."""
    # Configuration
    dataset_path = os.getenv("DATASET_PATH", "data/datasets/alpaca_20.jsonl")
    output_dir = os.getenv("OUTPUT_DIR", "logs/experiments/tinyllama_1_1b/memory_none")
    max_iters = int(os.getenv("MAX_ITERS", "3"))
    student_provider = os.getenv("STUDENT_PROVIDER", "local")
    
    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(output_dir, f"run_{timestamp}")
    
    logger.info("=" * 80)
    logger.info("MEMORY-NONE EXPERIMENT - TinyLlama 1.1B (Memory but No Retrieval)")
    logger.info("=" * 80)
    logger.info(f"Dataset: {dataset_path}")
    logger.info(f"Output: {run_dir}")
    logger.info(f"Max iterations: {max_iters}")
    logger.info(f"Provider: {student_provider}")
    logger.info(f"Note: Memory stored but NOT retrieved (tests storage overhead)")
    logger.info("=" * 80)
    
    # Initialize pipeline with baseline retrieval (no retrieval)
    retrieval_strategy = BaselineRetrieval()
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
    logger.info("Memory-none experiment completed successfully!")
    logger.info(f"Results saved to: {run_dir}")
    
    return summary, results


if __name__ == "__main__":
    main()
