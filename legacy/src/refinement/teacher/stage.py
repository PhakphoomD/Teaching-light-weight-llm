"""
Teacher Stage Orchestrator

Handles teacher evaluation workflow:
1. Evaluate student answer (correct/incorrect)
2. Generate hint (if incorrect)
3. Check early stopping (if incorrect)
"""

from typing import Dict, Any, Optional
from ..settings import SETTINGS
from ...core.logger import get_logger

logger = get_logger("refinement.teacher.stage")


class TeacherStage:
    """
    Teacher stage orchestrator.
    
    This stage:
    - Evaluates student answers
    - Generates hints for incorrect answers
    - Checks early stopping conditions
    
    Plugins are lazy-loaded when needed.
    """
    
    def __init__(self, config: Dict[str, Any], critic):
        """
        Initialize teacher stage.
        
        Args:
            config: Experiment configuration
            critic: HybridCritic or TeacherCritic instance
        """
        self.config = config
        self.critic = critic
        self.loaded_plugins = {}
        
        logger.info("TeacherStage initialized")
    
    def _load_plugin(self, plugin_name: str):
        """
        Lazy load plugin when needed.
        
        Args:
            plugin_name: Name of plugin to load
        
        Returns:
            Plugin instance
        """
        if plugin_name not in self.loaded_plugins:
            if plugin_name == "evaluator":
                from .plugins.evaluator import EvaluatorPlugin
                self.loaded_plugins[plugin_name] = EvaluatorPlugin(self.critic)
                logger.debug(f"Loaded plugin: {plugin_name}")
            
            elif plugin_name == "early_stopping":
                from .plugins.early_stopping import EarlyStoppingPlugin
                self.loaded_plugins[plugin_name] = EarlyStoppingPlugin()
                logger.debug(f"Loaded plugin: {plugin_name}")
        
        return self.loaded_plugins[plugin_name]
    
    def process(
        self,
        question: str,
        student_answer: str,
        correct_answer: Optional[str],
        iteration: int
    ) -> Dict[str, Any]:
        """
        Process teacher evaluation.
        
        Flow:
        1. Evaluate answer + generate hint (combined)
        2. If correct -> return (no early stopping needed)
        3. If incorrect -> check early stopping
        
        Args:
            question: Question text
            student_answer: Student's answer
            correct_answer: Ground truth (optional)
            iteration: Current iteration number
        
        Returns:
            {
                'is_correct': bool,
                'evaluation': str,  # "correct" | "incorrect"
                'reasoning': str,
                'hint': str,
                'stop_score': float,
                'should_stop': bool,
                'error_keys': list
            }
        """
        logger.debug(f"Processing teacher evaluation for iteration {iteration}")
        
        # Step 1: Evaluate + Generate Hint (combined!)
        use_cot = self.config.get("use_cot_teacher", False)
        
        evaluator = self._load_plugin("evaluator")
        evaluation = evaluator.evaluate_and_hint(
            question=question,
            answer=student_answer,
            ground_truth=correct_answer,
            use_cot=use_cot
        )
        
        logger.info(f"Evaluation: {evaluation['evaluation']}, stop_score: {evaluation['stop_score']:.2f}")
        
        # Step 2: If correct -> return early (no early stopping check needed)
        if evaluation["is_correct"]:
            logger.info("Answer is correct, skipping early stopping check")
            evaluation["should_stop"] = False
            return evaluation
        
        # Step 3: If incorrect -> check early stopping
        logger.info("Answer is incorrect, checking early stopping...")
        
        early_stopping_enabled = self.config.get("early_stopping", True)
        
        if early_stopping_enabled:
            early_stopping = self._load_plugin("early_stopping")
            should_stop = early_stopping.should_stop(
                stop_score=evaluation["stop_score"],
                iteration=iteration
            )
            evaluation["should_stop"] = should_stop
            
            if should_stop:
                logger.info(f"Early stopping triggered at iteration {iteration}")
        else:
            evaluation["should_stop"] = False
            logger.debug("Early stopping disabled")
        
        return evaluation
