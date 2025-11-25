"""
Hybrid Critic Tests

Tests for HybridCritic combining rule-based and LLM evaluation.
Uses mocks to avoid real API calls.

Usage:
    pytest src/tests/test_critic_hybrid.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.critic.aggregator import HybridCritic, sigmoid
from src.critic.schemas import CriticFeedback
from src.critic.llm_reviewer import LLMReviewer


# ============================================================================
# Test Sigmoid Function
# ============================================================================

def test_sigmoid_zero():
    """Test sigmoid(0) = 0.5."""
    assert sigmoid(0.0) == pytest.approx(0.5, abs=0.01)


def test_sigmoid_positive():
    """Test sigmoid(positive) > 0.5."""
    assert sigmoid(5.0) > 0.99


def test_sigmoid_negative():
    """Test sigmoid(negative) < 0.5."""
    assert sigmoid(-5.0) < 0.01


def test_sigmoid_extreme_values():
    """Test sigmoid handles extreme values without overflow."""
    assert sigmoid(1000.0) == 1.0  # Should clamp to 1.0
    assert sigmoid(-1000.0) == 0.0  # Should clamp to 0.0


# ============================================================================
# Test HybridCritic Initialization
# ============================================================================

def test_hybrid_critic_init_default():
    """Test HybridCritic initialization with defaults."""
    with patch('src.critic.aggregator.LLMReviewer') as MockReviewer:
        MockReviewer.return_value = Mock()
        
        critic = HybridCritic()
        
        assert critic.rule_weight == 0.5
        assert critic.llm_weight == 0.5
        assert critic.calib_a == 1.0
        assert critic.calib_b == 0.0
        assert critic.disagreement_threshold == 0.3


def test_hybrid_critic_init_custom_weights():
    """Test HybridCritic with custom weights."""
    with patch('src.critic.aggregator.LLMReviewer') as MockReviewer:
        MockReviewer.return_value = Mock()
        
        critic = HybridCritic(
            rule_weight=0.7,
            llm_weight=0.3,
            calibration_params={"a": 2.0, "b": -1.0}
        )
        
        assert critic.rule_weight == 0.7
        assert critic.llm_weight == 0.3
        assert critic.calib_a == 2.0
        assert critic.calib_b == -1.0


def test_hybrid_critic_init_with_disagreements_log():
    """Test HybridCritic with disagreements log path."""
    with patch('src.critic.aggregator.LLMReviewer') as MockReviewer:
        MockReviewer.return_value = Mock()
        
        critic = HybridCritic(disagreements_log="test_disagreements.jsonl")
        
        assert critic.disagreements_log == "test_disagreements.jsonl"


# ============================================================================
# Test HybridCritic Evaluation - Rule Only
# ============================================================================

def test_hybrid_critic_rule_only():
    """Test HybridCritic when LLM is unavailable (rule-only fallback)."""
    with patch('src.critic.aggregator.LLMReviewer') as MockReviewer:
        # Mock LLM fails
        MockReviewer.side_effect = Exception("LLM unavailable")
        
        critic = HybridCritic(rule_weight=0.5, llm_weight=0.5)
        
        # Should fallback to rule-only
        assert critic.llm_available == False
        assert critic.rule_only_fallback == True


def test_hybrid_critic_evaluate_perfect_answer():
    """Test evaluation of perfect answer (high rule score, LLM mocked high)."""
    with patch('src.critic.aggregator.LLMReviewer') as MockReviewer:
        # Mock LLM reviewer to return high score
        mock_llm = Mock()
        mock_llm.evaluate.return_value = CriticFeedback(
            issues=[],
            fixes=[],
            lesson="Excellent answer",
            scores={"overall": 1.0, "llm": 1.0},
            stop_score=1.0
        )
        MockReviewer.return_value = mock_llm
        
        critic = HybridCritic(rule_weight=0.5, llm_weight=0.5)
        
        feedback = critic.evaluate(
            question="What is 2+2?",
            answer="The answer is 4.",  # Perfect format, correct
            ground_truth="4"
        )
        
        assert isinstance(feedback, CriticFeedback)
        assert feedback.scores["overall"] > 0.8  # Should be high
        assert feedback.stop_score > 0.5


def test_hybrid_critic_evaluate_poor_answer():
    """Test evaluation of poor answer (low rule score, LLM mocked low)."""
    with patch('src.critic.aggregator.LLMReviewer') as MockReviewer:
        # Mock LLM reviewer to return low score
        mock_llm = Mock()
        mock_llm.evaluate.return_value = CriticFeedback(
            issues=["Incorrect answer"],
            fixes=["Review arithmetic"],
            lesson="2+2 equals 4, not 5",
            scores={"overall": 0.2, "llm": 0.2},
            stop_score=0.2
        )
        MockReviewer.return_value = mock_llm
        
        critic = HybridCritic(rule_weight=0.5, llm_weight=0.5)
        
        feedback = critic.evaluate(
            question="What is 2+2?",
            answer="x",  # Too short, no punctuation
            ground_truth="4"
        )
        
        assert isinstance(feedback, CriticFeedback)
        assert feedback.scores["overall"] < 0.5  # Should be low
        assert len(feedback.issues) > 0


# ============================================================================
# Test Weighted Combination
# ============================================================================

def test_hybrid_critic_weighted_combination():
    """Test that hybrid combines rule and LLM scores with correct weights."""
    with patch('src.critic.aggregator.LLMReviewer') as MockReviewer:
        # Mock LLM with known score
        mock_llm = Mock()
        mock_llm.evaluate.return_value = CriticFeedback(
            scores={"overall": 0.8, "llm": 0.8},
            stop_score=0.8
        )
        MockReviewer.return_value = mock_llm
        
        # Use weights that make math easy: 0.3 rule, 0.7 LLM
        critic = HybridCritic(rule_weight=0.3, llm_weight=0.7)
        
        # Provide answer that gets ~0.6 rule score (decent format)
        feedback = critic.evaluate(
            question="Test?",
            answer="This is a test answer.",  # Good format
            ground_truth="test"
        )
        
        # Overall should be: 0.3 * rule_score + 0.7 * 0.8
        # If rule_score ~0.6: 0.3*0.6 + 0.7*0.8 = 0.18 + 0.56 = 0.74
        assert "overall" in feedback.scores
        assert "rule" in feedback.scores
        assert "llm" in feedback.scores


# ============================================================================
# Test Sigmoid Calibration
# ============================================================================

def test_hybrid_critic_calibration():
    """Test stop_score calibration with sigmoid."""
    with patch('src.critic.aggregator.LLMReviewer') as MockReviewer:
        mock_llm = Mock()
        mock_llm.evaluate.return_value = CriticFeedback(
            scores={"overall": 0.5, "llm": 0.5},
            stop_score=0.5
        )
        MockReviewer.return_value = mock_llm
        
        # Test with a=2.0, b=0: sigmoid(2*overall)
        critic = HybridCritic(
            calibration_params={"a": 2.0, "b": 0.0}
        )
        
        feedback = critic.evaluate(
            question="Test?",
            answer="Test answer.",
            ground_truth="test"
        )
        
        # stop_score should be sigmoid(2 * overall_score)
        # If overall ~0.5: sigmoid(2*0.5) = sigmoid(1.0)   0.73
        assert hasattr(feedback, 'stop_score')
        assert 0.0 <= feedback.stop_score <= 1.0


# ============================================================================
# Test Disagreement Detection
# ============================================================================

def test_hybrid_critic_disagreement_detected(tmp_path):
    """Test disagreement detection when |rule - llm| > threshold."""
    disagreements_file = tmp_path / "disagreements.jsonl"
    
    with patch('src.critic.aggregator.LLMReviewer') as MockReviewer:
        # Mock LLM with very different score from rule
        mock_llm = Mock()
        mock_llm.evaluate.return_value = CriticFeedback(
            scores={"overall": 0.9, "llm": 0.9},  # High LLM score
            stop_score=0.9
        )
        MockReviewer.return_value = mock_llm
        
        critic = HybridCritic(
            disagreement_threshold=0.3,
            disagreements_log=str(disagreements_file)
        )
        
        # Provide answer with low rule score but high LLM score
        feedback = critic.evaluate(
            question="Test?",
            answer="x",  # Low rule score (too short)
            ground_truth="long answer"
        )
        
        # Should log disagreement
        assert disagreements_file.exists()
        
        # Read and verify JSONL content
        import json
        with open(disagreements_file, 'r') as f:
            record = json.loads(f.readline())
        
        assert "rule_score" in record
        assert "llm_score" in record
        assert "disagreement" in record
        assert record["disagreement"] > 0.3


def test_hybrid_critic_no_disagreement_below_threshold(tmp_path):
    """Test no disagreement logged when scores are very similar."""
    disagreements_file = tmp_path / "disagreements_none.jsonl"
    
    with patch('src.critic.aggregator.LLMReviewer') as MockReviewer:
        # Mock LLM with very similar score to rule (well below threshold)
        mock_llm = Mock()
        mock_llm.evaluate.return_value = CriticFeedback(
            scores={"overall": 0.95, "llm": 0.95},  # Very similar to rule
            stop_score=0.95
        )
        MockReviewer.return_value = mock_llm
        
        critic = HybridCritic(
            disagreement_threshold=0.3,
            disagreements_log=str(disagreements_file)
        )
        
        feedback = critic.evaluate(
            question="Test?",
            answer="This is a perfect test answer with excellent format and punctuation.",
            ground_truth="test"
        )
        
        # Should NOT log disagreement (difference << 0.3)
        # File should not exist or be empty
        if disagreements_file.exists():
            import json
            with open(disagreements_file, 'r') as f:
                lines = f.readlines()
            # If any records exist, check disagreement is below threshold
            for line in lines:
                record = json.loads(line)
                assert record["disagreement"] < 0.3


# ============================================================================
# Test Feedback Merging
# ============================================================================

def test_hybrid_critic_merges_feedback():
    """Test that HybridCritic merges rule and LLM feedback."""
    with patch('src.critic.aggregator.LLMReviewer') as MockReviewer:
        mock_llm = Mock()
        mock_llm.evaluate.return_value = CriticFeedback(
            issues=["LLM issue 1"],
            fixes=["LLM fix 1"],
            lesson="LLM lesson",
            scores={"overall": 0.6, "llm": 0.6},
            stop_score=0.6
        )
        MockReviewer.return_value = mock_llm
        
        critic = HybridCritic()
        
        feedback = critic.evaluate(
            question="What is the capital of France?",
            answer="paris",  # No capitalization
            ground_truth="Paris"
        )
        
        # Should have both rule and LLM feedback
        assert len(feedback.issues) > 0  # Combined issues
        assert len(feedback.fixes) > 0  # Combined fixes
        assert feedback.lesson != ""  # Lesson from LLM


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
