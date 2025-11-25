"""
Critic Schema Tests

Tests for CriticFeedback dataclass and validate_feedback() function.
Ensures schema validation handles malformed input correctly.

Usage:
    pytest src/tests/test_critic_schema.py -v
"""

import pytest
from src.critic.schemas import CriticFeedback, validate_feedback, create_default_feedback


# ============================================================================
# Test CriticFeedback Dataclass
# ============================================================================

def test_critic_feedback_valid():
    """Test valid CriticFeedback creation."""
    feedback = CriticFeedback(
        issues=["Answer too short"],
        fixes=["Add more detail"],
        lesson="Paris is the capital of France",
        error_keys=["incomplete"],
        scores={"overall": 0.5, "rule": 0.6, "llm": 0.4},
        stop_score=0.55
    )
    
    assert feedback.issues == ["Answer too short"]
    assert feedback.scores["overall"] == 0.5
    assert feedback.stop_score == 0.55


def test_critic_feedback_clamp_scores():
    """Test that __post_init__ clamps scores to [0, 1]."""
    feedback = CriticFeedback(
        scores={"overall": 1.5, "llm": -0.2},  # Invalid scores
        stop_score=2.0  # Invalid stop_score
    )
    
    # Scores should be clamped
    assert feedback.scores["overall"] == 1.0  # clamped from 1.5
    assert feedback.scores["llm"] == 0.0  # clamped from -0.2
    assert feedback.stop_score == 1.0  # clamped from 2.0


def test_critic_feedback_default_overall():
    """Test that missing 'overall' key is added with default 0.0."""
    feedback = CriticFeedback(
        scores={"rule": 0.8}  # Missing 'overall'
    )
    
    assert "overall" in feedback.scores
    assert feedback.scores["overall"] == 0.0


def test_critic_feedback_to_dict():
    """Test to_dict() serialization."""
    feedback = CriticFeedback(
        issues=["Issue 1"],
        fixes=["Fix 1"],
        lesson="Lesson 1",
        error_keys=["key1"],
        scores={"overall": 0.7},
        stop_score=0.8
    )
    
    result = feedback.to_dict()
    
    assert isinstance(result, dict)
    assert result["issues"] == ["Issue 1"]
    assert result["scores"]["overall"] == 0.7
    assert result["stop_score"] == 0.8


# ============================================================================
# Test validate_feedback() Function
# ============================================================================

def test_validate_feedback_valid_dict():
    """Test validate_feedback with valid dictionary input."""
    data = {
        "issues": ["Issue 1"],
        "fixes": ["Fix 1"],
        "lesson": "Test lesson",
        "error_keys": ["error1"],
        "scores": {"overall": 0.6},
        "stop_score": 0.7
    }
    
    feedback = validate_feedback(data)
    
    assert isinstance(feedback, CriticFeedback)
    assert feedback.issues == ["Issue 1"]
    assert feedback.scores["overall"] == 0.6


def test_validate_feedback_missing_fields():
    """Test validate_feedback uses defaults for missing fields."""
    data = {
        "scores": {"overall": 0.5}
        # All other fields missing
    }
    
    feedback = validate_feedback(data)
    
    assert isinstance(feedback, CriticFeedback)
    assert feedback.issues == []  # default
    assert feedback.fixes == []  # default
    assert feedback.lesson == ""  # default
    assert feedback.scores["overall"] == 0.5


def test_validate_feedback_invalid_scores():
    """Test validate_feedback clamps invalid scores."""
    data = {
        "scores": {"overall": 2.5, "rule": -1.0},
        "stop_score": -0.5
    }
    
    feedback = validate_feedback(data)
    
    assert feedback.scores["overall"] == 1.0  # clamped
    assert feedback.scores["rule"] == 0.0  # clamped
    assert feedback.stop_score == 0.0  # clamped


def test_validate_feedback_wrong_types():
    """Test validate_feedback handles wrong types gracefully."""
    data = {
        "issues": "should be list",  # Wrong type (will be wrapped in list)
        "scores": {"overall": "not a number"},  # Wrong type
        "stop_score": "string"  # Wrong type
    }
    
    feedback = validate_feedback(data)
    
    # validate_feedback coerces types where possible
    assert isinstance(feedback.issues, list)  # String wrapped in list
    assert isinstance(feedback.scores, dict)
    assert "overall" in feedback.scores


def test_validate_feedback_empty_dict():
    """Test validate_feedback with empty dictionary."""
    data = {}
    
    feedback = validate_feedback(data)
    
    assert isinstance(feedback, CriticFeedback)
    assert feedback.issues == []
    assert feedback.fixes == []
    assert feedback.lesson == ""
    assert "overall" in feedback.scores
    assert feedback.scores["overall"] == 0.0


def test_validate_feedback_nested_metadata():
    """Test validate_feedback preserves metadata field."""
    data = {
        "scores": {"overall": 0.8},
        "metadata": {
            "model": "gemini-test",
            "timestamp": "2025-11-10T20:00:00"
        }
    }
    
    feedback = validate_feedback(data)
    
    assert feedback.metadata["model"] == "gemini-test"
    assert feedback.metadata["timestamp"] == "2025-11-10T20:00:00"


# ============================================================================
# Test create_default_feedback() Function
# ============================================================================

def test_create_default_feedback():
    """Test create_default_feedback returns valid default feedback."""
    feedback = create_default_feedback()
    
    assert isinstance(feedback, CriticFeedback)
    assert feedback.issues == ["No feedback available"]  # Has default reason
    assert feedback.fixes == ["Unable to generate specific suggestions"]
    assert feedback.lesson == "Could not evaluate answer"
    assert feedback.error_keys == ["error", "fallback"]
    assert feedback.scores == {"overall": 0.0}
    assert feedback.stop_score == 0.0
    assert feedback.metadata == {"fallback": True, "reason": "No feedback available"}


def test_create_default_feedback_with_reason():
    """Test create_default_feedback with custom reason."""
    feedback = create_default_feedback(reason="LLM timeout")
    
    assert feedback.metadata.get("reason") == "LLM timeout"
    assert feedback.issues == ["LLM timeout"]  # Reason becomes first issue


# ============================================================================
# Test JSON Serialization Round-trip
# ============================================================================

def test_feedback_json_roundtrip():
    """Test CriticFeedback can be serialized and deserialized."""
    import json
    
    original = CriticFeedback(
        issues=["Issue 1", "Issue 2"],
        fixes=["Fix 1"],
        lesson="Test lesson",
        error_keys=["key1", "key2"],
        scores={"overall": 0.75, "rule": 0.8, "llm": 0.7},
        stop_score=0.78,
        metadata={"test": "value"}
    )
    
    # Serialize to JSON
    json_str = json.dumps(original.to_dict(), ensure_ascii=False)
    
    # Deserialize back
    data = json.loads(json_str)
    reconstructed = validate_feedback(data)
    
    # Verify round-trip
    assert reconstructed.issues == original.issues
    assert reconstructed.fixes == original.fixes
    assert reconstructed.lesson == original.lesson
    assert reconstructed.error_keys == original.error_keys
    assert reconstructed.scores == original.scores
    assert reconstructed.stop_score == original.stop_score
    assert reconstructed.metadata == original.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
