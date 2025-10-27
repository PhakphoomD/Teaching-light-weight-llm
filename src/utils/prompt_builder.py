"""
Prompt Builder Utilities

Common prompt building functions.
"""

from typing import Optional


def build_answer_prompt(question: str, context: str = "") -> str:
    """
    Build prompt for answering questions.
    
    Args:
        question: Question to answer
        context: Optional context from memory
        
    Returns:
        Formatted prompt
    """
    if context:
        return (
            f"You previously answered similar questions. Here's relevant feedback:\n\n"
            f"{context}\n\n"
            f"Now answer this question concisely:\n"
            f"Question: {question}\n\n"
            f"Answer:"
        )
    return f"Question: {question}\n\nProvide a clear and concise answer."


def build_reflection_prompt_generic(
    question: str,
    answer: str,
    error_type: str,
    missing_keywords: Optional[list] = None,
    expected_keywords: Optional[list] = None,
    expected_exact: Optional[str] = None
) -> str:
    """
    Build generic reflection prompt.
    
    Args:
        question: Original question
        answer: Student's answer
        error_type: Type of error
        missing_keywords: Missing required keywords
        expected_keywords: All expected keywords
        expected_exact: Expected exact answer
        
    Returns:
        Reflection prompt
    """
    base = (
        f"You answered this question incorrectly:\n\n"
        f"Question: {question}\n"
        f"Your answer: {answer}\n\n"
    )
    
    if error_type == "missing_keywords" and missing_keywords:
        hint = f"You missed these important concepts: {', '.join(missing_keywords)}\n"
    elif error_type == "exact_match_failed" and expected_exact:
        hint = f"The expected answer was: '{expected_exact}'\n"
    elif error_type == "empty_answer":
        hint = "You provided an empty answer.\n"
    else:
        hint = "Your answer was incorrect.\n"
    
    reflection_prompt = (
        f"\nReflect on your mistake:\n"
        f"1. What concept did you miss?\n"
        f"2. Why did you think your answer was correct?\n"
        f"3. What's the correct approach?\n"
        f"4. What key insight will help you in the future?\n\n"
        f"Write a thoughtful reflection (3-5 sentences):"
    )
    
    return base + hint + reflection_prompt


def format_context(feedbacks: list, max_items: int = 3) -> str:
    """
    Format feedback list as context string.
    
    Args:
        feedbacks: List of Feedback objects
        max_items: Maximum number of items to include
        
    Returns:
        Formatted context string
    """
    if not feedbacks:
        return ""
    
    items = feedbacks[:max_items]
    return "\n".join([f"- {fb.message}" for fb in items])
