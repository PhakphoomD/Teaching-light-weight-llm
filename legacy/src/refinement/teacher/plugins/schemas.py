"""
Critic Feedback Schema

Standardized JSON schema for teacher critic feedback.
All critic implementations (rule-based, LLM, hybrid) must return CriticFeedback.

Schema Design:
- issues: List of identified problems (short, actionable)
- fixes: List of specific suggestions to improve
- lesson: 1-3 sentence summary of key learning point
- error_keys: Tags for error categorization (e.g., "grammar", "logic", "factual")
- scores: Dict with "overall", "rule", "llm" scores (all 0.0-1.0)
- stop_score: Calibrated score for stopping criterion (0.0-1.0)

Safety:
- validate_feedback() ensures ALL fields are present with valid types
- Missing keys -> use defaults
- Invalid scores -> clamp to [0.0, 1.0]
- Guarantees NO crashes from malformed input
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
import json
import logging

# Use standard logging (avoid circular import issues during testing)
logger = logging.getLogger("critic.schemas")


@dataclass
class CriticFeedback:
    """
    Standardized feedback structure from teacher critic.
    
    This is the ONE TRUE SCHEMA for all critic feedback.
    Rule-based, LLM-based, and hybrid critics all return this format.
    
    Attributes:
        issues: List of identified problems (e.g., "Answer too short", "Missing key term")
        fixes: List of actionable suggestions (e.g., "Add 2-3 more sentences")
        lesson: Key learning point in 1-3 sentences
        error_keys: Categorization tags (e.g., ["format", "incomplete"])
        scores: Dict with at minimum "overall" (0.0-1.0)
                Optional: "rule", "llm" for component scores
        stop_score: Calibrated score for loop stopping (0.0-1.0)
        metadata: Optional extra info (timestamp, model, etc.)
    
    Invariants:
        - All scores MUST be in [0.0, 1.0]
        - "overall" key MUST exist in scores
        - stop_score MUST be in [0.0, 1.0]
    
    Example:
        >>> feedback = CriticFeedback(
        ...     issues=["Answer is too brief", "Missing capital city name"],
        ...     fixes=["Elaborate with 1-2 more sentences", "Explicitly state 'Paris'"],
        ...     lesson="Paris is the capital of France",
        ...     error_keys=["incomplete", "factual"],
        ...     scores={"overall": 0.3, "rule": 0.2, "llm": 0.4},
        ...     stop_score=0.35
        ... )
    """
    issues: List[str] = field(default_factory=list)
    fixes: List[str] = field(default_factory=list)
    lesson: str = ""
    error_keys: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=lambda: {"overall": 0.0})
    stop_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate and clamp scores after initialization."""
        # Ensure "overall" exists
        if "overall" not in self.scores:
            logger.warning("Missing 'overall' in scores, defaulting to 0.0")
            self.scores["overall"] = 0.0
        
        # Clamp all scores to [0, 1]
        for key in self.scores:
            self.scores[key] = _clamp(self.scores[key], 0.0, 1.0)
        
        # Clamp stop_score
        self.stop_score = _clamp(self.stop_score, 0.0, 1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "issues": self.issues,
            "fixes": self.fixes,
            "lesson": self.lesson,
            "error_keys": self.error_keys,
            "scores": self.scores,
            "stop_score": self.stop_score,
            "metadata": self.metadata
        }
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CriticFeedback":
        """
        Create CriticFeedback from dictionary (with validation).
        
        This is the SAFE constructor that handles malformed input.
        Use validate_feedback() for maximum safety.
        """
        return validate_feedback(data)


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value to [min_val, max_val]."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        logger.warning(f"Invalid numeric value: {value}, defaulting to {min_val}")
        return min_val
    
    return max(min_val, min(max_val, value))


def validate_feedback(obj: Union[Dict[str, Any], CriticFeedback]) -> CriticFeedback:
    """
    Validate and normalize feedback object into CriticFeedback.
    
    This is the FORTRESS function that ensures:
    - ALL required fields exist (with defaults if missing)
    - ALL scores are clamped to [0.0, 1.0]
    - NO crashes from malformed input
    
    Handles:
    - Missing keys -> use defaults
    - Wrong types -> coerce or default
    - Invalid scores -> clamp to valid range
    - Nested dicts -> extract values
    - Noise from LLM output -> strip and parse
    
    Args:
        obj: Either a dict (from JSON) or existing CriticFeedback
    
    Returns:
        CriticFeedback: Validated and normalized feedback
    
    Examples:
        >>> # Missing keys
        >>> validate_feedback({})
        CriticFeedback(issues=[], fixes=[], lesson="", ...)
        
        >>> # Invalid scores
        >>> validate_feedback({"scores": {"overall": 1.5}})
        CriticFeedback(scores={"overall": 1.0}, ...)  # clamped
        
        >>> # Malformed nested
        >>> validate_feedback({"issues": "not a list"})
        CriticFeedback(issues=[], ...)  # default
    """
    # If already CriticFeedback, validate scores and return
    if isinstance(obj, CriticFeedback):
        obj.__post_init__()  # Re-validate
        return obj
    
    # Ensure obj is dict
    if not isinstance(obj, dict):
        logger.warning(f"Expected dict or CriticFeedback, got {type(obj)}, using defaults")
        obj = {}
    
    # Extract fields with safe defaults
    issues = _extract_list(obj.get("issues", []))
    fixes = _extract_list(obj.get("fixes", []))
    lesson = _extract_string(obj.get("lesson", ""))
    error_keys = _extract_list(obj.get("error_keys", []))
    scores = _extract_scores(obj.get("scores", {}))
    stop_score = _extract_float(obj.get("stop_score", 0.0))
    metadata = _extract_dict(obj.get("metadata", {}))
    
    # Build CriticFeedback (will auto-validate in __post_init__)
    return CriticFeedback(
        issues=issues,
        fixes=fixes,
        lesson=lesson,
        error_keys=error_keys,
        scores=scores,
        stop_score=stop_score,
        metadata=metadata
    )


def _extract_list(value: Any) -> List[str]:
    """Extract list of strings, with fallback to empty list."""
    if isinstance(value, list):
        # Filter out non-strings
        return [str(item) for item in value if item]
    elif isinstance(value, str):
        # Single string -> wrap in list
        return [value] if value else []
    else:
        logger.debug(f"Expected list, got {type(value)}, defaulting to []")
        return []


def _extract_string(value: Any) -> str:
    """Extract string, with fallback to empty string."""
    if isinstance(value, str):
        return value
    elif value is None:
        return ""
    else:
        # Try to convert to string
        try:
            return str(value)
        except Exception:
            logger.debug(f"Could not convert {type(value)} to string, defaulting to ''")
            return ""


def _extract_float(value: Any, default: float = 0.0) -> float:
    """Extract float, with fallback to default."""
    try:
        return float(value)
    except (TypeError, ValueError):
        logger.debug(f"Could not convert {value} to float, defaulting to {default}")
        return default


def _extract_dict(value: Any) -> Dict[str, Any]:
    """Extract dict, with fallback to empty dict."""
    if isinstance(value, dict):
        return value
    else:
        logger.debug(f"Expected dict, got {type(value)}, defaulting to {{}}")
        return {}


def _extract_scores(value: Any) -> Dict[str, float]:
    """
    Extract scores dict with validation.
    
    Ensures:
    - Result is dict with string keys and float values
    - "overall" key exists
    - All values in [0.0, 1.0]
    """
    if not isinstance(value, dict):
        logger.warning(f"Expected dict for scores, got {type(value)}, defaulting to {{'overall': 0.0}}")
        return {"overall": 0.0}
    
    # Extract and clamp all numeric values
    scores = {}
    for key, val in value.items():
        try:
            scores[str(key)] = _clamp(float(val), 0.0, 1.0)
        except (TypeError, ValueError):
            logger.debug(f"Invalid score value for '{key}': {val}, skipping")
    
    # Ensure "overall" exists
    if "overall" not in scores:
        logger.warning("Missing 'overall' in scores, defaulting to 0.0")
        scores["overall"] = 0.0
    
    return scores


def create_default_feedback(
    reason: str = "No feedback available",
    overall_score: float = 0.0
) -> CriticFeedback:
    """
    Create a safe default feedback when critic fails completely.
    
    Use this when:
    - LLM timeout
    - JSON parsing fails
    - Network error
    - Any unrecoverable error
    
    Args:
        reason: Explanation for default feedback
        overall_score: Default score (usually 0.0)
    
    Returns:
        CriticFeedback: Valid feedback with default values
    """
    return CriticFeedback(
        issues=[reason],
        fixes=["Unable to generate specific suggestions"],
        lesson="Could not evaluate answer",
        error_keys=["error", "fallback"],
        scores={"overall": _clamp(overall_score, 0.0, 1.0)},
        stop_score=_clamp(overall_score, 0.0, 1.0),
        metadata={"fallback": True, "reason": reason}
    )


# Convenience function for backward compatibility with CriticResult
def from_critic_result(
    evaluation: str,
    reasoning: str,
    hint: str,
    raw_text: str = ""
) -> CriticFeedback:
    """
    Convert old CriticResult (XML-based) to new CriticFeedback (JSON-based).
    
    This bridges the old and new critic systems.
    
    Args:
        evaluation: "correct" or "incorrect"
        reasoning: Teacher's reasoning
        hint: Teacher's hint
        raw_text: Raw LLM output (optional)
    
    Returns:
        CriticFeedback: Converted feedback
    """
    is_correct = evaluation.lower() == "correct"
    
    # Extract issues and fixes from reasoning/hint
    issues = [] if is_correct else [reasoning[:100]]  # Truncate if too long
    fixes = [] if is_correct else [hint]
    lesson = reasoning[:200] if reasoning else ""  # Truncate
    
    # Simple binary score
    overall_score = 1.0 if is_correct else 0.0
    
    return CriticFeedback(
        issues=issues,
        fixes=fixes,
        lesson=lesson,
        error_keys=["legacy_xml"],
        scores={"overall": overall_score, "llm": overall_score},
        stop_score=overall_score,
        metadata={"source": "CriticResult", "raw_text": raw_text[:500]}
    )
