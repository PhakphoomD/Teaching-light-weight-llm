"""
Teaching Pipeline Orchestrator

This module provides the Orchestrator class that coordinates the complete
teaching pipeline:

1. Student generates initial answer
2. Teacher evaluates and provides feedback
3. Memory retrieval provides context from past examples
4. Refinement loop iterates until correct or max rounds
5. Results are saved to memory for future use

The Orchestrator is the main entry point for running the teaching system.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path

from ..core.logger import get_logger
from ..memory.store import MemoryStore
from ..memory.vector import VectorIndex
from ..refinement.loop import RefinementLoop
from ..refinement.strategies import (
    RefinementStrategy,
    SimpleStrategy,
    MemoryAugmentedStrategy,
    AdaptiveStrategy
)

logger = get_logger("pipeline.orchestrator")


class TeachingOrchestrator:
    """
    Orchestrates the complete teaching pipeline.
    
    This class brings together all components:
    - RefinementLoop (student + teacher interaction)
    - Memory system (store + vector index)
    - Refinement strategies (simple, memory-augmented, adaptive)
    
    Architecture:
        Input: Question
           
        [Strategy] -> Prepare Context (from memory)
           
        [RefinementLoop] -> Student attempts -> Teacher evaluates
                                 
                   Feedback      
            (repeat until correct/max rounds)
        [Strategy] -> Save to Memory
           
        Output: Refinement Result
    
    Example:
        >>> orchestrator = TeachingOrchestrator.from_config(
        ...     student_provider="local",
        ...     student_model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        ...     teacher_provider="gemini",
        ...     teacher_model="gemini-2.0-flash-lite",
        ...     strategy_type="memory"
        ... )
        >>> result = orchestrator.teach(
        ...     question="What is the capital of France?"
        ... )
        >>> print(result['final_answer'])
        'Paris'
    """
    
    def __init__(
        self,
        refinement_loop: RefinementLoop,
        strategy: RefinementStrategy,
        memory_store: Optional[MemoryStore] = None,
        vector_index: Optional[VectorIndex] = None
    ):
        """
        Initialize the orchestrator.
        
        Args:
            refinement_loop: Configured RefinementLoop instance
            strategy: Refinement strategy to use
            memory_store: Optional memory store (required for memory strategies)
            vector_index: Optional vector index (required for memory strategies)
        """
        self.refinement_loop = refinement_loop
        self.strategy = strategy
        self.memory_store = memory_store
        self.vector_index = vector_index
        
        # Performance tracking
        self.teaching_history: List[Dict[str, Any]] = []
        
        logger.info(
            f"TeachingOrchestrator initialized with {strategy.__class__.__name__}"
        )
    
    @classmethod
    def from_config(
        cls,
        student_provider: str,
        student_model: str,
        teacher_provider: str,
        teacher_model: str,
        strategy_type: str = "simple",
        max_rounds: int = 5,
        memory_dir: str = "logs/memory",
        **kwargs
    ) -> "TeachingOrchestrator":
        """
        Create orchestrator from configuration.
        
        This is the recommended way to create an orchestrator.
        
        Args:
            student_provider: Provider for student model
            student_model: Student model name
            teacher_provider: Provider for teacher model
            teacher_model: Teacher model name
            strategy_type: "simple", "memory", or "adaptive"
            max_rounds: Maximum refinement rounds
            memory_dir: Directory for memory files
            **kwargs: Additional arguments for strategy
        
        Returns:
            Configured TeachingOrchestrator instance
        
        Example:
            >>> orch = TeachingOrchestrator.from_config(
            ...     student_provider="local",
            ...     student_model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            ...     teacher_provider="gemini",
            ...     teacher_model="gemini-2.0-flash-lite",
            ...     strategy_type="adaptive",
            ...     max_rounds=5
            ... )
        """
        logger.info("Creating TeachingOrchestrator from config...")
        
        # Create refinement loop
        logger.info("Initializing refinement loop...")
        refinement_loop = RefinementLoop(
            student_provider=student_provider,
            student_model=student_model,
            teacher_provider=teacher_provider,
            teacher_model=teacher_model,
            max_rounds=max_rounds
        )
        
        # Create memory components if needed
        memory_store = None
        vector_index = None
        
        if strategy_type in ["memory", "adaptive"]:
            logger.info("Initializing memory system...")
            
            # Create memory directory
            memory_path = Path(memory_dir)
            memory_path.mkdir(parents=True, exist_ok=True)
            
            # Memory store
            store_path = memory_path / "store.jsonl"
            memory_store = MemoryStore(file_path=str(store_path))
            
            # Vector index
            index_path = memory_path / "faiss.index"
            vector_index = VectorIndex(
                embedding_model=kwargs.get("embedding_model", "all-MiniLM-L6-v2"),
                index_path=str(index_path)
            )
        
        # Create strategy
        logger.info(f"Creating {strategy_type} strategy...")
        
        if strategy_type == "simple":
            strategy = SimpleStrategy(max_rounds=max_rounds)
        
        elif strategy_type == "memory":
            if memory_store is None or vector_index is None:
                raise ValueError("Memory store and vector index required for memory strategy")
            
            strategy = MemoryAugmentedStrategy(
                memory_store=memory_store,
                vector_index=vector_index,
                k=kwargs.get("k", 5),
                max_rounds=max_rounds
            )
        
        elif strategy_type == "adaptive":
            if memory_store is None or vector_index is None:
                raise ValueError("Memory store and vector index required for adaptive strategy")
            
            strategy = AdaptiveStrategy(
                memory_store=memory_store,
                vector_index=vector_index,
                k=kwargs.get("k", 5),
                base_max_rounds=max_rounds,
                adapt_after=kwargs.get("adapt_after", 10)
            )
        
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
        
        return cls(
            refinement_loop=refinement_loop,
            strategy=strategy,
            memory_store=memory_store,
            vector_index=vector_index
        )
    
    def teach(
        self,
        question: str,
        ground_truth: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run the complete teaching pipeline for a single question.
        
        This method:
        1. Prepares context using strategy
        2. Runs refinement loop
        3. Saves to memory (if applicable)
        4. Records performance
        
        Args:
            question: Question to teach
            ground_truth: Optional ground truth answer
        
        Returns:
            Refinement result with additional metadata
        
        Example:
            >>> result = orchestrator.teach(
            ...     question="What is 2+2?",
            ...     ground_truth="4"
            ... )
            >>> print(result['success'])
            True
            >>> print(result['num_rounds'])
            2
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Teaching: {question[:80]}...")
        logger.info(f"{'='*60}")
        
        # Step 1: Prepare context from strategy
        logger.info("Step 1: Preparing context...")
        context = self.strategy.prepare_context(
            question=question,
            history=self.teaching_history
        )
        
        if context:
            logger.info(f"Context prepared ({len(context)} chars)")
        else:
            logger.info("No context available")
        
        # Step 2: Get max rounds from strategy
        max_rounds = self.strategy.get_max_rounds(
            question=question,
            history=self.teaching_history
        )
        
        logger.info(f"Max rounds for this question: {max_rounds}")
        
        # Temporarily update refinement loop max_rounds
        original_max_rounds = self.refinement_loop.max_rounds
        self.refinement_loop.max_rounds = max_rounds
        
        try:
            # Step 3: Run refinement loop
            logger.info("Step 2: Running refinement loop...")
            result = self.refinement_loop.refine_until_correct(
                question=question,
                context=context,
                ground_truth=ground_truth
            )
            
            # Step 4: Save to memory (if strategy supports it)
            if hasattr(self.strategy, 'save_to_memory'):
                logger.info("Step 3: Saving to memory...")
                self.strategy.save_to_memory(result)  # type: ignore
            
            # Step 5: Record performance for adaptive strategies
            if hasattr(self.strategy, 'record_performance'):
                self.strategy.record_performance(result)  # type: ignore
            
            # Step 6: Update teaching history
            self.teaching_history.append(result)
            
            # Log summary
            logger.info(f"\n{'='*60}")
            logger.info(f"Teaching Result:")
            logger.info(f"  Success: {result['success']}")
            logger.info(f"  Rounds: {result['num_rounds']}")
            logger.info(f"  Improvement: {result['improvement']}")
            logger.info(f"  Final Answer: {result['final_answer'][:100]}...")
            logger.info(f"{'='*60}\n")
            
            return result
            
        finally:
            # Restore original max_rounds
            self.refinement_loop.max_rounds = original_max_rounds
    
    def teach_batch(
        self,
        questions: List[str],
        ground_truths: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Run teaching pipeline on multiple questions.
        
        Args:
            questions: List of questions
            ground_truths: Optional list of ground truth answers
        
        Returns:
            List of refinement results
        
        Example:
            >>> questions = [
            ...     "What is the capital of France?",
            ...     "What is 2+2?"
            ... ]
            >>> results = orchestrator.teach_batch(questions)
            >>> print(len(results))
            2
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Batch Teaching: {len(questions)} questions")
        logger.info(f"{'='*60}\n")
        
        # Prepare ground truths
        if ground_truths is None:
            ground_truths_list = [""] * len(questions)
        else:
            ground_truths_list = ground_truths
        
        if len(ground_truths_list) != len(questions):
            raise ValueError(
                f"Ground truths length ({len(ground_truths_list)}) must match "
                f"questions ({len(questions)})"
            )
        
        results = []
        
        for i, (question, ground_truth) in enumerate(
            zip(questions, ground_truths_list), start=1
        ):
            logger.info(f"\n>>> Question {i}/{len(questions)} <<<")
            
            result = self.teach(
                question=question,
                ground_truth=ground_truth if ground_truth else None
            )
            
            results.append(result)
        
        # Print summary
        self._print_batch_summary(results)
        
        return results
    
    def _print_batch_summary(self, results: List[Dict[str, Any]]) -> None:
        """Print summary of batch teaching results."""
        if not results:
            return
        
        total = len(results)
        successes = sum(1 for r in results if r['success'])
        improvements = sum(1 for r in results if r['improvement'])
        avg_rounds = sum(r['num_rounds'] for r in results) / total
        
        print("\n" + "="*60)
        print("BATCH TEACHING SUMMARY")
        print("="*60)
        print(f"Total Questions:    {total}")
        print(f"Successes:          {successes} ({successes/total*100:.1f}%)")
        print(f"Improvements:       {improvements} ({improvements/total*100:.1f}%)")
        print(f"Average Rounds:     {avg_rounds:.2f}")
        print("="*60 + "\n")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get teaching statistics.
        
        Returns:
            Dict with statistics
        
        Example:
            >>> stats = orchestrator.get_stats()
            >>> print(stats['total_questions'])
            42
            >>> print(stats['success_rate'])
            0.75
        """
        if not self.teaching_history:
            return {
                'total_questions': 0,
                'success_rate': 0.0,
                'improvement_rate': 0.0,
                'avg_rounds': 0.0,
                'strategy_type': self.strategy.__class__.__name__
            }
        
        total = len(self.teaching_history)
        successes = sum(1 for r in self.teaching_history if r['success'])
        improvements = sum(1 for r in self.teaching_history if r['improvement'])
        avg_rounds = sum(r['num_rounds'] for r in self.teaching_history) / total
        
        stats = {
            'total_questions': total,
            'success_rate': successes / total,
            'improvement_rate': improvements / total,
            'avg_rounds': avg_rounds,
            'strategy_type': self.strategy.__class__.__name__
        }
        
        # Add strategy-specific stats if available
        if hasattr(self.strategy, 'get_stats'):
            strategy_stats = self.strategy.get_stats()  # type: ignore
            stats['strategy_stats'] = strategy_stats
        
        return stats
    
    def print_stats(self) -> None:
        """Print teaching statistics in a formatted way."""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print("TEACHING STATISTICS")
        print("="*60)
        print(f"Strategy:           {stats['strategy_type']}")
        print(f"Total Questions:    {stats['total_questions']}")
        print(f"Success Rate:       {stats['success_rate']:.1%}")
        print(f"Improvement Rate:   {stats['improvement_rate']:.1%}")
        print(f"Average Rounds:     {stats['avg_rounds']:.2f}")
        
        if 'strategy_stats' in stats:
            print("\nStrategy-Specific Stats:")
            for key, value in stats['strategy_stats'].items():
                if isinstance(value, float):
                    if key.endswith('_rate'):
                        print(f"  {key:20s}: {value:.1%}")
                    else:
                        print(f"  {key:20s}: {value:.2f}")
                else:
                    print(f"  {key:20s}: {value}")
        
        print("="*60 + "\n")
    
    def export_results(self, output_path: str) -> None:
        """
        Export teaching results to a JSON file.
        
        Args:
            output_path: Path to output file
        
        Example:
            >>> orchestrator.export_results("results.json")
        """
        import json
        from pathlib import Path
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        export_data = {
            'stats': self.get_stats(),
            'results': self.teaching_history
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results exported to: {output_path}")
        print(f"  Results exported to: {output_path}")
