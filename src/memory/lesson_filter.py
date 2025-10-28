"""
Lesson Quality Filter

Filters out low-quality reflections before storing in memory:
- Generic apologies ("Thank you", "I apologize")
- Long-winded preambles ("In this lesson", "We will discuss")
- Empty or too-short lessons
- Lessons without actionable content
"""

import re
from typing import Optional


# Patterns to reject
REJECT_PATTERNS = [
    r'^thank you',
    r'^i apologize',
    r'^in this lesson',
    r'^we will discuss',
    r'^welcome to',
    r'^hi there',
    r'^please provide',
    r'^the problem with',
    r'^incorrectly',
]

# Minimum quality thresholds
MIN_LESSON_LENGTH = 20  # characters
MAX_LESSON_LENGTH = 160  # characters for storage
MIN_SPECIFIC_WORDS = 2  # Must contain domain-specific terms


def clean_lesson(raw_reflection: str) -> str:
    """
    Extract clean lesson from raw reflection.
    
    Removes:
    - Preambles and apologies
    - Excessive whitespace
    - Generic phrases
    
    Args:
        raw_reflection: Raw reflection text from teacher
        
    Returns:
        Cleaned lesson (≤160 chars) or empty string if low quality
    """
    if not raw_reflection:
        return ""
    
    text = raw_reflection.strip().lower()
    
    # Remove common prefixes
    for pattern in REJECT_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            # Try to find the actual lesson after the preamble
            sentences = raw_reflection.split('.')
            if len(sentences) > 1:
                # Take later sentences that might contain actual content
                text = '. '.join(sentences[1:]).strip()
            else:
                return ""  # All fluff, no content
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Check length
    if len(text) < MIN_LESSON_LENGTH:
        return ""
    
    # Truncate if too long
    if len(text) > MAX_LESSON_LENGTH:
        # Try to end at sentence boundary
        truncated = text[:MAX_LESSON_LENGTH]
        last_period = truncated.rfind('.')
        if last_period > MIN_LESSON_LENGTH:
            text = truncated[:last_period + 1]
        else:
            text = truncated + "..."
    
    return text


def is_high_quality_lesson(lesson: str, error_keys: list) -> bool:
    """
    Check if lesson meets quality thresholds.
    
    Args:
        lesson: Cleaned lesson text
        error_keys: List of error keys
        
    Returns:
        True if lesson is worth storing
    """
    if not lesson or len(lesson) < MIN_LESSON_LENGTH:
        return False
    
    # Must have error context
    if not error_keys:
        return False
    
    # Count specific/technical words (heuristic: words with 6+ chars or underscores)
    words = lesson.split()
    specific_words = sum(1 for w in words if len(w) >= 6 or '_' in w)
    
    if specific_words < MIN_SPECIFIC_WORDS:
        return False
    
    # Check for action words (good lessons have actionable guidance)
    action_words = {'use', 'include', 'add', 'remove', 'check', 'ensure', 
                   'avoid', 'consider', 'remember', 'focus', 'specify'}
    has_action = any(word in lesson.lower() for word in action_words)
    
    if not has_action:
        return False
    
    return True


def extract_keywords_from_lesson(lesson: str) -> list:
    """
    Extract potential keyword concepts from lesson text.
    
    Used for generating concept_keys when canonical mapping isn't available.
    
    Args:
        lesson: Cleaned lesson text
        
    Returns:
        List of extracted keywords (2-4 most relevant terms)
    """
    if not lesson:
        return []
    
    # Remove common stop words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 
                 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were'}
    
    words = lesson.lower().split()
    
    # Filter and score words
    candidates = []
    for word in words:
        # Clean word
        word = re.sub(r'[^\w]', '', word)
        if len(word) < 4 or word in stop_words:
            continue
        candidates.append(word)
    
    # Return top keywords (prefer longer, rarer words)
    candidates.sort(key=lambda w: len(w), reverse=True)
    return candidates[:4]
