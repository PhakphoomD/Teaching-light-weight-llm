"""
Simplified Early Stopping Module

Patience-based early stopping that starts checking from round 2 onwards.

Key features:
1. Start monitoring from round 2 (avoid fluke first round)
2. Patience: Stop if no improvement for N consecutive rounds
3. Min improvement: Require minimum score gain
4. Plateau detection: Stop if score is high enough (near perfect)

Logic:
- Round 1: Always continue (baseline)
- Round 2+: Check for improvement
  - If score improves by >= min_improvement: Reset patience
  - If score doesn't improve: Increment patience counter
  - If patience exhausted: Stop
  - If score >= plateau_threshold: Stop (good enough)
"""

from typing import List, Optional


class EarlyStopping:
    """
    Early stopping mechanism for teaching loop.
    
    Features:
    - Starts checking from round 2+ (not round 1)
    - Patience-based: stop after N rounds without improvement
    - Minimum improvement threshold
    - Plateau detection for high scores
    """
    
    def __init__(self,
                 patience: int = 2,
                 min_improvement: float = 0.05,
                 plateau_threshold: float = 0.9,
                 start_from_round: int = 2):
        """
        Initialize early stopping.
        
        Args:
            patience: Number of rounds without improvement before stopping (default: 2)
            min_improvement: Minimum score improvement required (default: 0.05)
            plateau_threshold: Score threshold for "good enough" (default: 0.9)
            start_from_round: Start checking from this round (default: 2)
        """
        self.patience = patience
        self.min_improvement = min_improvement
        self.plateau_threshold = plateau_threshold
        self.start_from_round = start_from_round
        
        # State
        self.score_history: List[float] = []
        self.patience_counter = 0
        self.best_score = 0.0
    
    def reset(self):
        """Reset state for new question."""
        self.score_history = []
        self.patience_counter = 0
        self.best_score = 0.0
    
    def check(self, round_num: int, score: float) -> bool:
        """
        Check if should stop early.
        
        Args:
            round_num: Current round number (1-indexed)
            score: Current score
        
        Returns:
            True if should stop, False if should continue
        
        Decision logic:
        1. If round < start_from_round: Continue (don't check yet)
        2. If score >= plateau_threshold: Stop (good enough!)
        3. If score improved by >= min_improvement: Continue (reset patience)
        4. If no improvement and patience exhausted: Stop
        5. Otherwise: Continue (increment patience)
        """
        # Record score
        self.score_history.append(score)
        
        # Don't check early stopping before start_from_round
        if round_num < self.start_from_round:
            self.best_score = max(self.best_score, score)
            return False
        
        # Check for plateau (score is high enough)
        if score >= self.plateau_threshold:
            return True
        
        # Check for improvement
        improvement = score - self.best_score
        
        if improvement >= self.min_improvement:
            # Significant improvement - reset patience
            self.best_score = score
            self.patience_counter = 0
            return False
        else:
            # No significant improvement - increment patience
            self.patience_counter += 1
            
            # Check if patience exhausted
            if self.patience_counter >= self.patience:
                return True
            
            return False
    
    def get_summary(self) -> dict:
        """
        Get summary of early stopping state.
        
        Returns:
            Dict with:
            - score_history: List of scores
            - best_score: Best score seen
            - patience_used: Current patience counter
            - should_have_stopped: Whether we would stop now
        """
        return {
            'score_history': self.score_history,
            'best_score': self.best_score,
            'patience_used': self.patience_counter,
            'total_rounds': len(self.score_history)
        }


# Example usage and testing
if __name__ == "__main__":
    print("="*80)
    print("Testing Early Stopping")
    print("="*80)
    
    # Test case 1: Improvement each round (should not stop)
    print("\n--- Test 1: Continuous Improvement ---")
    es = EarlyStopping(patience=2, min_improvement=0.05, plateau_threshold=0.9)
    
    test_scores = [0.6, 0.65, 0.72, 0.80]
    for round_num, score in enumerate(test_scores, start=1):
        print(f"\nRound {round_num}: Score = {score:.3f}")
        should_stop = es.check(round_num, score)
        print(f"Should stop: {should_stop}")
        if should_stop:
            break
    
    print(f"\nSummary: {es.get_summary()}")
    
    # Test case 2: Stuck after round 2 (should stop with patience)
    print("\n" + "="*80)
    print("--- Test 2: No Improvement (Patience) ---")
    es = EarlyStopping(patience=2, min_improvement=0.05, plateau_threshold=0.9)
    
    test_scores = [0.6, 0.62, 0.62, 0.63, 0.62]
    for round_num, score in enumerate(test_scores, start=1):
        print(f"\nRound {round_num}: Score = {score:.3f}")
        should_stop = es.check(round_num, score)
        print(f"Should stop: {should_stop}")
        if should_stop:
            break
    
    print(f"\nSummary: {es.get_summary()}")
    
    # Test case 3: High score on round 3 (plateau detection)
    print("\n" + "="*80)
    print("--- Test 3: Plateau Detection ---")
    es = EarlyStopping(patience=2, min_improvement=0.05, plateau_threshold=0.9)
    
    test_scores = [0.7, 0.75, 0.92]
    for round_num, score in enumerate(test_scores, start=1):
        print(f"\nRound {round_num}: Score = {score:.3f}")
        should_stop = es.check(round_num, score)
        print(f"Should stop: {should_stop}")
        if should_stop:
            break
    
    print(f"\nSummary: {es.get_summary()}")
    
    # Test case 4: Fluke first round (should not affect)
    print("\n" + "="*80)
    print("--- Test 4: Fluke First Round ---")
    print("(First round score ignored, checking starts from round 2)")
    es = EarlyStopping(patience=2, min_improvement=0.05, plateau_threshold=0.9, start_from_round=2)
    
    test_scores = [0.9, 0.4, 0.45, 0.46, 0.45]  # Fluke high score in round 1
    for round_num, score in enumerate(test_scores, start=1):
        print(f"\nRound {round_num}: Score = {score:.3f}")
        should_stop = es.check(round_num, score)
        print(f"Should stop: {should_stop}")
        if should_stop:
            break
    
    print(f"\nSummary: {es.get_summary()}")
    print("\nNote: First round (0.9) was ignored. Patience started from round 2.")
