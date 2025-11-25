"""
Student Stage Orchestrator

Handles student answer generation workflow:
1. Retrieve context from memory (if enabled)
2. Build prompt with question + hints + context
3. Generate answer
"""

from typing import Dict, Any, List
from ..settings import SETTINGS
from ...core.logger import get_logger
from ...prompts.student import build_student_prompt, extract_student_answer

logger = get_logger("refinement.student.stage")


class StudentStage:
    """
    Student stage orchestrator.
    
    This stage:
    - Retrieves context from memory
    - Generates student answers
    
    Plugins are lazy-loaded when needed.
    """
    
    def __init__(self, config: Dict[str, Any], student_client, memory_store, vector_index):
        """
        Initialize student stage.
        
        Args:
            config: Experiment configuration
            student_client: Student LLM client (LocalClient/GroqClient)
            memory_store: MemoryStore instance
            vector_index: VectorIndex instance
        """
        self.config = config
        self.student_client = student_client
        self.memory_store = memory_store
        self.vector_index = vector_index
        self.loaded_plugins = {}
        
        logger.info("StudentStage initialized")
    
    def _load_plugin(self, plugin_name: str):
        """
        Lazy load plugin when needed.
        
        Args:
            plugin_name: Name of plugin to load
        
        Returns:
            Plugin instance
        """
        if plugin_name not in self.loaded_plugins:
            if plugin_name == "memory_retrieval":
                from .plugins.memory_retrieval import MemoryRetrievalPlugin
                self.loaded_plugins[plugin_name] = MemoryRetrievalPlugin(
                    self.memory_store,
                    self.vector_index
                )
                logger.debug(f"Loaded plugin: {plugin_name}")
            
            elif plugin_name == "generator":
                from .plugins.generator import GeneratorPlugin
                self.loaded_plugins[plugin_name] = GeneratorPlugin(self.student_client)
                logger.debug(f"Loaded plugin: {plugin_name}")
        
        return self.loaded_plugins[plugin_name]
    
    def process(
        self,
        question: str,
        hints: List[str],
        iteration: int,
        previous_answer: str | None = None
    ) -> Dict[str, Any]:
        """
        Process student answer generation.
        
        Flow:
        1. Retrieve context from memory (if k > 0)
        2. Build prompt with question + hints + context + previous_answer
        3. Generate answer
        
        Args:
            question: Question text
            hints: List of previous hints
            iteration: Current iteration number
            previous_answer: Student's previous attempt (for learning from mistakes)
        
        Returns:
            {
                'answer': str,
                'context_used': bool,
                'context_ids': list,
                'tokens_used': int,
                'latency_ms': float
            }
        """
        logger.debug(f"Processing student generation for iteration {iteration}")
        
        # Step 1: Retrieve context (if k > 0)
        context = ""
        context_ids = []
        
        k = self.config.get("k", 3)
        if k > 0 and self.vector_index.index.ntotal > 0:
            logger.info("Retrieving context from memory...")
            retrieval = self._load_plugin("memory_retrieval")
            context, context_ids = retrieval.retrieve(question)
            
            if context:
                logger.info(f"Retrieved context from {len(context_ids)} records")
            else:
                logger.info("No relevant context found")
        else:
            logger.debug(f"Memory retrieval disabled (k={k}, index size={self.vector_index.index.ntotal})")
        
        # Step 2: Build prompt
        hints_text = "\n".join(hints) if hints else ""
        use_cot = self.config.get("use_cot_student", False)
        
        prompt = build_student_prompt(
            question=question,
            hints=hints_text,
            context=context,
            use_cot=use_cot,
            previous_answer=previous_answer or ""  # Pass previous attempt for feedback loop
        )
        
        logger.debug(f"Prompt built (length: {len(prompt)} chars, hints: {len(hints)}, cot: {use_cot})")
        
        # Step 3: Generate answer
        generator = self._load_plugin("generator")
        result = generator.generate(prompt)
        
        result["context_used"] = bool(context)
        result["context_ids"] = context_ids
        
        logger.info(f"Answer generated: {result['answer'][:80]}...")
        logger.info(f"Tokens: {result['tokens_used']}, Latency: {result['latency_ms']:.0f}ms")
        
        return result
