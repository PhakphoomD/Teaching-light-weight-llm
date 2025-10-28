"""
Common prompt builders used by pipelines that are model-agnostic.

Phase 5 additions:
- build_reflection_prompt(): Structured prompt for reflection with previous attempts
"""

from typing import List, Optional
from src.memory.store import FeedbackLite


def build_answer_prompt(question: str, context: str = "") -> str:
    """Generic answer prompt with optional feedback context."""
    if context:
        return f"""Past feedback to consider:
{context}

Now answer the following question concisely and accurately:
{question}

Answer:"""
    else:
        return f"""{question}

Answer:"""


def build_reflection_prompt(
    question: str,
    previous_attempt: Optional[FeedbackLite] = None,
    similar_lessons: Optional[List[FeedbackLite]] = None
) -> str:
    """
    Build structured reflection prompt for attempt ≥2.
    
    Phase 5: Shows previous attempt errors and similar past lessons
    to guide the student toward correct answer.
    
    Args:
        question: The question to answer
        previous_attempt: Most recent feedback from this task (if any)
        similar_lessons: List of relevant lessons from past tasks
        
    Returns:
        Formatted prompt string with context
        
    Example output:
        Previous attempt:
        Your answer: "gradient descent is..."
        Errors detected: missing_keywords, incomplete
        Lesson to apply: Include both full term and abbreviation (e.g., "GD" and "gradient descent")
        
        Similar past lessons:
        - Always define abbreviations on first use
        - Include key concepts: optimization, learning rate
        
        Now answer this question accurately:
        Question: What is gradient descent?
        Answer:
    """
    sections = []
    
    # Previous attempt section
    if previous_attempt:
        sections.append("Previous attempt:")
        if previous_attempt.student_answer_short:
            sections.append(f'Your answer: "{previous_attempt.student_answer_short}"')
        if previous_attempt.error_keys:
            error_str = ", ".join(previous_attempt.error_keys)
            sections.append(f"Errors detected: {error_str}")
        if previous_attempt.lesson:
            sections.append(f"Lesson to apply: {previous_attempt.lesson}")
        sections.append("")  # Blank line
    
    # Similar past lessons section
    if similar_lessons and len(similar_lessons) > 0:
        sections.append("Similar past lessons:")
        for lesson_fb in similar_lessons:
            if lesson_fb.lesson:
                sections.append(f"- {lesson_fb.lesson}")
        sections.append("")  # Blank line
    
    # Question section
    sections.append("Now answer this question accurately:")
    sections.append(f"Question: {question}")
    sections.append("Answer:")
    
    return "\n".join(sections)

