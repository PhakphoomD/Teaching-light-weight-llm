"""
Early Stopping Plugin

Implements early stopping logic:
1. Stop if stop_score >= tau (high confidence)
2. Stop if no improvement for patience rounds
"""

from ...settings import SETTINGS
from ....core.logger import get_logger

logger = get_logger("refinement.teacher.early_stopping")


class EarlyStoppingPlugin:
    """
    Early stopping plugin.
    
    Tracks score history and decides when to stop refinement early.
    
    Settings used:
    - SETTINGS.early_stopping.tau (threshold for high confidence)
    - SETTINGS.early_stopping.patience (rounds without improvement)
    - SETTINGS.early_stopping.epsilon_gain (minimum improvement delta)
    """
    
    def __init__(self):
        """Initialize early stopping plugin"""
        self.tau = SETTINGS.early_stopping.tau
        self.patience = SETTINGS.early_stopping.patience
        self.epsilon_gain = SETTINGS.early_stopping.epsilon_gain
        
        # Track history
        self.score_history = []
        self.no_improvement_count = 0
        
        logger.info(
            f"EarlyStoppingPlugin initialized: "
            f"tau={self.tau}, patience={self.patience}, epsilon_gain={self.epsilon_gain}"
        )
    
    def should_stop(self, stop_score: float, iteration: int) -> bool:
        """
        Check if should stop early.
        
        Conditions:
        1. stop_score >= tau (high confidence)
        2. No improvement for patience rounds
        
        Args:
            stop_score: Current stop score (0-1)
            iteration: Current iteration number
        
        Returns:
            True if should stop early
        """
        self.score_history.append(stop_score)
        
        # Condition 1: High confidence
        if stop_score >= self.tau:
            logger.info(
                f"Early stop: stop_score={stop_score:.2f} >= tau={self.tau} "
                f"(iteration {iteration})"
            )
            return True
        
        # Condition 2: No improvement
        if len(self.score_history) > 1:
            prev_score = self.score_history[-2]
            improvement = stop_score - prev_score
            
            if improvement < self.epsilon_gain:
                self.no_improvement_count += 1
                logger.debug(
                    f"No improvement: {improvement:.3f} < epsilon={self.epsilon_gain} "
                    f"(count: {self.no_improvement_count}/{self.patience})"
                )
            else:
                self.no_improvement_count = 0
                logger.debug(f"Improvement detected: {improvement:.3f}")
            
            if self.no_improvement_count >= self.patience:
                logger.info(
                    f"Early stop: no improvement for {self.patience} rounds "
                    f"(gain={improvement:.3f} < epsilon={self.epsilon_gain}, "
                    f"iteration {iteration})"
                )
                return True
        
        return False
    
    def reset(self):
        """Reset state for new question"""
        self.score_history = []
        self.no_improvement_count = 0
        logger.debug("Early stopping state reset")
