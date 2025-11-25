"""
Memory Stage Orchestrator

Handles memory storage and logging:
1. Store incorrect examples to memory
2. Add to vector index
3. Log to JSONL
"""

from typing import Dict, Any
from datetime import datetime
import uuid
from ...core.logger import get_logger

logger = get_logger("refinement.memory.stage")


class MemoryStage:
    """
    Memory stage orchestrator.
    
    This stage:
    - Stores incorrect examples (skips correct ones)
    - Adds to vector index for retrieval
    - Logs rounds to JSONL
    
    Plugins are lazy-loaded when needed.
    """
    
    def __init__(self, memory_store, vector_index):
        """
        Initialize memory stage.
        
        Args:
            memory_store: MemoryStore instance
            vector_index: VectorIndex instance
        """
        self.memory_store = memory_store
        self.vector_index = vector_index
        self.loaded_plugins = {}
        
        logger.info("MemoryStage initialized")
    
    def _load_plugin(self, plugin_name: str):
        """
        Lazy load plugin when needed.
        
        Args:
            plugin_name: Name of plugin to load
        
        Returns:
            Plugin instance
        """
        if plugin_name not in self.loaded_plugins:
            if plugin_name == "storage":
                from .plugins.storage import StoragePlugin
                self.loaded_plugins[plugin_name] = StoragePlugin(
                    self.memory_store,
                    self.vector_index
                )
                logger.debug(f"Loaded plugin: {plugin_name}")
            
            elif plugin_name == "logger":
                from .plugins.logger import LoggerPlugin
                self.loaded_plugins[plugin_name] = LoggerPlugin()
                logger.debug(f"Loaded plugin: {plugin_name}")
        
        return self.loaded_plugins[plugin_name]
    
    def process(
        self,
        question: str,
        student_answer: str,
        evaluation: Dict[str, Any],
        experiment_id: str,
        question_id: str,
        round_num: int
    ):
        """
        Process memory storage and logging.
        
        Flow:
        1. Check if answer is correct
        2. If incorrect -> save to store + vector index
        3. Log round to JSONL (always)
        
        Args:
            question: Question text
            student_answer: Student's answer
            evaluation: Teacher evaluation result
            experiment_id: Experiment ID
            question_id: Question ID
            round_num: Round number
        """
        logger.debug(f"Processing memory storage for round {round_num}")
        
        # Step 1: Check if correct (skip storage if correct)
        if evaluation["is_correct"]:
            logger.info("Answer correct, skipping memory storage")
        else:
            logger.info("Answer incorrect, storing to memory...")
            
            # Step 2: Store to memory (if incorrect)
            storage = self._load_plugin("storage")
            storage.save(
                question=question,
                answer=student_answer,
                evaluation=evaluation
            )
        
        # Step 3: Log round (always, regardless of correctness)
        logger_plugin = self._load_plugin("logger")
        logger_plugin.log(
            experiment_id=experiment_id,
            question_id=question_id,
            round_num=round_num,
            question=question,
            student_answer=student_answer,
            evaluation=evaluation
        )
        
        logger.debug("Memory stage processing complete")
