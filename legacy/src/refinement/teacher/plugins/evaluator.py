"""
Evaluator Plugin

Main plugin that combines:
1. Evaluation (via HybridCritic or TeacherCritic)
2. Hint generation (via distil_hint)

This is the PRIMARY evaluation plugin used by TeacherStage.
"""

from typing import Dict, Any, Optional
from ...settings import SETTINGS
from ....core.logger import get_logger

# Import critic components
from .aggregator import HybridCritic
from .simple_critic import TeacherCritic, CriticResult
from .schemas import CriticFeedback
from .hint_generator import distil_hint, filter_answer_leakage

logger = get_logger("refinement.teacher.evaluator")


class EvaluatorPlugin:
    """
    Evaluator plugin - combines evaluation + hint generation.
    
    This plugin:
    1. Calls critic.evaluate() (HybridCritic or TeacherCritic)
    2. Extracts hint from reasoning (distil_hint)
    3. Returns unified feedback
    
    Settings used:
    - SETTINGS.evaluator.temperature
    - SETTINGS.evaluator.max_tokens
    - SETTINGS.evaluator.hint_max_length
    """
    
    def __init__(self, critic):
        """
        Initialize evaluator.
        
        Args:
            critic: HybridCritic or TeacherCritic instance
        """
        self.critic = critic
        self.temperature = SETTINGS.evaluator.temperature
        self.max_tokens = SETTINGS.evaluator.max_tokens
        self.hint_max_length = SETTINGS.evaluator.hint_max_length
        
        critic_type = "HybridCritic" if isinstance(critic, HybridCritic) else "TeacherCritic"
        logger.info(f"EvaluatorPlugin initialized with {critic_type}")
    
    def evaluate_and_hint(
        self,
        question: str,
        answer: str,
        ground_truth: Optional[str],
        use_cot: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluate answer and generate hint.
        
        Flow:
        1. Call critic.evaluate() (with COT if enabled)
        2. Map to unified format
        3. Generate hint (if incorrect)
        
        Args:
            question: Question text
            answer: Student's answer
            ground_truth: Correct answer (optional)
            use_cot: Whether to use chain-of-thought reasoning
        
        Returns:
            {
                'is_correct': bool,
                'evaluation': str,  # "correct" | "incorrect"
                'reasoning': str,
                'hint': str,        # Generated hint
                'stop_score': float,
                'error_keys': list
            }
        """
        logger.debug(f"Evaluating answer for question: {question[:50]}... (COT={use_cot})")
        
        # Step 1: Call critic (with COT if HybridCritic)
        if isinstance(self.critic, HybridCritic):
            # New path: HybridCritic with COT support
            eval_result = self.critic.evaluate(question, answer, ground_truth, use_cot=use_cot)
        else:
            # Legacy path: TeacherCritic (no COT parameter)
            eval_result = self.critic.evaluate(question, answer, ground_truth or "")
        
        # Step 2: Map to unified format
        if isinstance(eval_result, CriticResult):
            # Legacy path (TeacherCritic)
            evaluation = eval_result.evaluation
            reasoning = eval_result.reasoning
            hint = eval_result.hint  # Already has hint
            stop_score = 1.0 if evaluation == "correct" else 0.0
            error_keys = []
            
            logger.debug(f"Legacy critic result: {evaluation}")
        
        else:
            # New path (HybridCritic -> CriticFeedback)
            is_correct = eval_result.stop_score >= 0.7
            evaluation = "correct" if is_correct else "incorrect"
            
            # Build reasoning from issues
            if eval_result.issues:
                issue_list = [f"{i+1}. {issue}" for i, issue in enumerate(eval_result.issues)]
                reasoning = "Issues found:\n" + "\n".join(issue_list)
            else:
                reasoning = "No critical issues found"
            
            # Build hint: combine issues + fixes (without revealing answer)
            hint_parts = []
            if eval_result.issues:
                hint_parts.append("Your answer has issues:")
                for i, issue in enumerate(eval_result.issues, 1):
                    hint_parts.append(f"  {i}. {issue}")
            
            if eval_result.fixes:
                hint_parts.append("\nHow to improve:")
                for fix in eval_result.fixes:
                    hint_parts.append(f"  - {fix}")
            
            hint = "\n".join(hint_parts) if hint_parts else "Please revise your answer."
            
            # Filter answer leakage (just in case)
            hint = distil_hint(hint)
            
            # Filter answer leakage (before truncation)
            hint, has_leakage = filter_answer_leakage(hint, known_answer=ground_truth or "")
            if has_leakage:
                logger.warning(f"Answer leakage detected and filtered in hint")
            
            # Truncate hint if too long
            if len(hint) > self.hint_max_length:
                hint = hint[:self.hint_max_length] + "..."
                logger.debug(f"Hint truncated to {self.hint_max_length} chars")
            
            stop_score = eval_result.stop_score
            error_keys = eval_result.error_keys
            
            logger.debug(f"HybridCritic result: {evaluation}, stop_score: {stop_score:.2f}")
        
        logger.debug(f"Hint: {hint[:80]}...")
        
        return {
            "is_correct": evaluation == "correct",
            "evaluation": evaluation,
            "reasoning": reasoning,
            "hint": hint,  # Filtered and safe hint
            "stop_score": stop_score,
            "error_keys": error_keys
        }
