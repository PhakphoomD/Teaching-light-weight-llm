"""
Hint Distillation Module

This module provides functions to distill hints from teacher's reasoning.
The goal is to extract helpful guidance while filtering out direct answers.
"""

import re
import json
from typing import List, Tuple
from pathlib import Path
from datetime import datetime

from src.core.logger import get_logger

logger = get_logger("critic.hints")


def distil_hint(reasoning: str) -> str:
    """
    Distill a clean hint from teacher's chain-of-thought reasoning.
    
    This function processes the teacher's reasoning to extract educational hints
    while filtering out direct answers. It uses regex patterns to identify and
    remove phrases that reveal the answer.
    
    Args:
        reasoning: The teacher's full reasoning text (chain-of-thought)
    
    Returns:
        str: A distilled hint that guides without revealing the answer
    
    Strategy:
        1. Remove phrases that directly state the answer
        2. Keep comparative and guiding statements
        3. Preserve educational context
        4. Filter out exact answer patterns
    
    Patterns Filtered (English):
        - "the answer is X"
        - "the correct answer is X"
        - "it is X" / "this is X"
        - "X is the answer"
        - Direct statements like "Paris is the capital"
    
    Limitations:
        - May not catch all answer-revealing patterns
        - Context-dependent (what counts as "revealing" varies)
        - May need fine-tuning based on domain
    
    Example:
        >>> reasoning = '''
        ... The student answered London, but this is incorrect.
        ... The correct answer is Paris. Paris is the capital of France,
        ... located on the Seine river. It is known for the Eiffel Tower.
        ... '''
        >>> hint = distil_hint(reasoning)
        >>> print(hint)
        "The student answered London, but this is incorrect. Located on the Seine river.
        Known for the Eiffel Tower."
        (Note: "The correct answer is Paris" and "Paris is the capital" are filtered)
    """
    if not reasoning or not reasoning.strip():
        return ""
    
    # Start with the original reasoning
    text = reasoning.strip()
    
    
    if text.startswith("Issues found:"):
        return text
    
    # Pattern 1: Remove "the answer is X" patterns (case-insensitive)
    # Matches: "the answer is X", "the correct answer is X", etc.
    patterns_to_remove = [
        r"the\s+(correct\s+)?answer\s+is\s+[^.!?\n]+[.!?]?",
        r"it\s+is\s+[^.!?\n]+[.!?]?",
        r"this\s+is\s+[^.!?\n]+[.!?]?",
        r"[^.!?\n]+\s+is\s+the\s+(correct\s+)?answer[.!?]?",
    ]
    
    for pattern in patterns_to_remove:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    
    # Pattern 2: Remove direct factual statements that reveal the answer
    # This is tricky - we want to keep context but remove exact answers
    # Example: "Paris is the capital of France" -> keep "capital of France"
    # This requires more sophisticated NLP, so we'll use a simple heuristic
    
    # For now, remove sentences containing both proper nouns and "is the"
    # This catches "X is the Y" patterns
    # TODO: Improve this with better NER or semantic analysis
    
    # Pattern 3: Remove sentences with high confidence markers
    confidence_markers = [
        r"definitely",
        r"certainly",
        r"obviously",
        r"clearly\s+it\s+is",
        r"without\s+a\s+doubt",
    ]
    
    for marker in confidence_markers:
        # Remove the marker but keep the rest of the sentence
        text = re.sub(marker, "", text, flags=re.IGNORECASE)
    
    # Clean up extra whitespace and line breaks
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(\s*\n\s*)+", "\n", text)
    
    # Remove empty sentences (just punctuation)
    text = re.sub(r"[.!?]\s*[.!?]+", ".", text)
    
    return text.strip()


def filter_answer_leakage(
    hint: str,
    known_answer: str = "",
    sensitive_words: List[str] | None = None
) -> Tuple[str, bool]:
    """
    Enhanced leakage detection with multiple strategies.
    
    This function scans the hint for potential answer leakage using:
    - Exact match detection
    - First letter hints
    - Length hints
    - Word overlap analysis
    - Pattern matching
    
    Args:
        hint: The hint text to check
        known_answer: The correct answer to check against (optional)
        sensitive_words: Additional words that should not appear (optional)
    
    Returns:
        Tuple[str, bool]: (filtered_hint, has_leakage)
            - filtered_hint: Hint with sensitive parts removed or safe fallback
            - has_leakage: True if potential answer leakage was detected
    
    Example:
        >>> hint = "The answer is definitely Paris, the capital city"
        >>> filtered, leaked = filter_answer_leakage(hint, known_answer="Paris")
        >>> print(leaked)  # True
        >>> print(filtered)  # Safe fallback message
    """
    if not hint:
        return "", False
    
    if not known_answer:
        known_answer = ""
    
    hint_lower = hint.lower()
    answer_lower = known_answer.lower().strip()
    has_leakage = False
    original_hint = hint
    
    # Layer 1: Exact match
    if answer_lower and answer_lower in hint_lower:
        logger.error(f"LEAKAGE: Exact match '{known_answer}' in hint")
        has_leakage = True
        hint = hint.replace(known_answer, "[REDACTED]")
        hint = re.sub(re.escape(known_answer), "[REDACTED]", hint, flags=re.IGNORECASE)
    
    # Layer 2: First letter hints (e.g., "starts with P")
    if len(answer_lower) > 0:
        first_letter = answer_lower[0]
        first_letter_patterns = [
            f"starts with {first_letter}",
            f"begins with {first_letter}",
            f"first letter is {first_letter}",
            f"letter {first_letter}"
        ]
        for pattern in first_letter_patterns:
            if pattern in hint_lower:
                logger.warning(f"First letter hint detected: {pattern}")
                has_leakage = True
                break
    
    # Layer 3: Length hints
    if answer_lower:
        answer_length = len(answer_lower.split()[0])
        length_patterns = [
            f"{answer_length} letter",
            f"{answer_length}-letter",
            f"{answer_length} character"
        ]
        for pattern in length_patterns:
            if pattern in hint_lower:
                logger.warning(f"Length hint detected: {pattern}")
                has_leakage = True
                break
    
    # Layer 4: Word overlap analysis (>60% of answer words in hint)
    answer_words = set(w for w in answer_lower.split() if len(w) > 2)
    hint_words = set(w for w in hint_lower.split() if len(w) > 2)
    
    if len(answer_words) > 0:
        overlap = len(answer_words & hint_words)
        overlap_ratio = overlap / len(answer_words)
        
        if overlap_ratio > 0.6:
            logger.warning(
                f"High word overlap: {overlap}/{len(answer_words)} "
                f"({overlap_ratio:.1%})"
            )
            has_leakage = True
    
    # Layer 5: Direct patterns
    leak_patterns = [
        r"\bthe answer is\b",
        r"\bit is\s+\w+\b",
        r"\bshould be\s+\w+\b",
        r"\bcorrect answer:?\s+\w+\b",
        r"\bis the answer\b",
    ]
    
    if answer_lower:
        leak_patterns.extend([
            rf"\bthe answer is\s+{re.escape(answer_lower)}\b",
            rf"\bit is\s+{re.escape(answer_lower)}\b",
            rf"\bshould be\s+{re.escape(answer_lower)}\b",
        ])
    
    for pattern in leak_patterns:
        if re.search(pattern, hint_lower):
            logger.error(f"LEAKAGE PATTERN: {pattern}")
            has_leakage = True
            hint = re.sub(pattern, "[REDACTED]", hint, flags=re.IGNORECASE)
    
    # Layer 6: Sensitive words
    if sensitive_words:
        for word in sensitive_words:
            if word.lower() in hint_lower:
                logger.warning(f"Sensitive word detected: {word}")
                has_leakage = True
                hint = re.sub(re.escape(word), "[REDACTED]", hint, flags=re.IGNORECASE)
    
    # If leakage detected, log and use safe fallback
    if has_leakage:
        logger.error(
            f"LEAKAGE DETECTED!\n"
            f"  Original: {original_hint[:100]}\n"
            f"  Answer: {known_answer}"
        )
        
        # Log to file for review
        _log_leakage_incident(original_hint, known_answer)
        
        # Return safe generic hint
        hint = (
            "Review the question carefully and consider what it's asking for. "
            "Think about the key concepts and requirements."
        )
    else:
        # Clean up minor artifacts
        hint = re.sub(r"\s+", " ", hint).strip()
        hint = re.sub(r"\[REDACTED\]\s*", "", hint).strip()
    
    return hint, has_leakage


def _log_leakage_incident(hint: str, answer: str) -> None:
    """
    Log leakage incidents for manual review.
    
    Args:
        hint: The hint that contained leakage
        answer: The ground truth answer
    """
    log_path = Path("logs/leakage_incidents.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "hint": hint,
                "answer": answer,
                "severity": "HIGH"
            }, ensure_ascii=False) + '\n')
    except Exception as e:
        logger.error(f"Failed to log leakage incident: {e}")


def extract_educational_content(reasoning: str) -> str:
    """
    Extract educational and guiding content from reasoning.
    
    This function identifies and extracts parts of the reasoning that are
    educational (e.g., "Think about...", "Consider...", "Remember that...")
    while filtering out evaluative judgments and direct answers.
    
    Args:
        reasoning: The full reasoning text
    
    Returns:
        str: Educational content suitable for hints
    
    Educational Markers:
        - "Think about..."
        - "Consider..."
        - "Remember that..."
        - "Recall..."
        - "Note that..."
        - "Pay attention to..."
    
    TODO: Add Thai language markers:
        - "               ..."
        - "       ..."
        - "        ..."
    """
    if not reasoning:
        return ""
    
    educational_markers = [
        r"think\s+about[^.!?\n]+",
        r"consider[^.!?\n]+",
        r"remember\s+that[^.!?\n]+",
        r"recall[^.!?\n]+",
        r"note\s+that[^.!?\n]+",
        r"pay\s+attention\s+to[^.!?\n]+",
    ]
    
    educational_parts = []
    
    for marker in educational_markers:
        matches = re.findall(marker, reasoning, re.IGNORECASE)
        educational_parts.extend(matches)
    
    if educational_parts:
        return " ".join(educational_parts).strip()
    
    # If no educational markers found, return empty
    # (Better to have no hint than a bad hint)
    return ""


def multilingual_filter(text: str, language: str = "en") -> str:
    """
    Filter answer-revealing patterns for multiple languages.
    
    Currently supports: English (en), Thai (th)
    
    Args:
        text: Text to filter
        language: Language code ('en' or 'th')
    
    Returns:
        str: Filtered text
    
    TODO: Implement Thai language patterns
        Thai patterns to add:
        - "         X"
        - "                   X"
        - "     X"
        - "X         "
    
    Future: Add more languages as needed (Chinese, Japanese, etc.)
    """
    if language == "en":
        return distil_hint(text)
    elif language == "th":
        # TODO: Implement Thai-specific filtering
        logger.warning("Thai language filtering not yet implemented")
        return text
    else:
        logger.warning(f"Unsupported language: {language}, using English filter")
        return distil_hint(text)
