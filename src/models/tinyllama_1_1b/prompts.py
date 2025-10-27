"""
TinyLlama 1.1B specific prompts
"""
from src.evaluation.critic import Critique


def build_reflection_prompt(question: str, answer: str, critique: Critique) -> str:
    """
    Build reflection prompt for TinyLlama based on error details from SimpleCritic.
    
    Args:
        question: Original question
        answer: Student's incorrect answer
        critique: Critique object with error details
        
    Returns:
        Reflection prompt string
    """
    base_intro = (
        f"You answered the following question incorrectly:\n\n"
        f"Question: {question}\n"
        f"Your answer: {answer}\n\n"
    )
    
    # Build error hint based on error type
    if critique.error_type == "missing_keywords":
        missing = critique.missing_keywords or []
        expected = critique.expected_keywords or []
        present_kws = [k for k in expected if k not in missing]
        
        hint = (
            f"Analysis: Your answer is incomplete.\n"
            f"- Missing concepts: {', '.join(missing)}\n"
        )
        if present_kws:
            hint += f"- You mentioned: {', '.join(present_kws)}\n"
        hint += f"- Required concepts: {', '.join(expected)}\n"
        
    elif critique.error_type == "exact_match_failed":
        hint = (
            f"Analysis: Your answer doesn't match the expected format.\n"
            f"- Expected: '{critique.expected_exact}'\n"
            f"- You wrote: '{critique.student_answer}'\n"
        )
        
    elif critique.error_type == "empty_answer":
        hint = "Analysis: You provided an empty or blank answer.\n"
        
    else:
        hint = "Analysis: Your answer was marked as incorrect.\n"
    
    reflection_questions = (
        f"\n"
        f"Reflect deeply on your mistake:\n\n"
        f"1. What fundamental concept or principle did you miss or misunderstand?\n"
        f"2. Why did you think your answer was correct? What was your reasoning?\n"
        f"3. What is the CORRECT way to approach this type of question?\n"
        f"4. What key insight will help you solve similar problems in the future?\n\n"
        f"Write a thoughtful reflection (3-5 sentences) focusing on conceptual understanding, "
        f"not just listing keywords:"
    )
    
    return base_intro + hint + reflection_questions


def build_answer_prompt(question: str, context: str = "") -> str:
    """
    Build answer prompt for TinyLlama.
    
    Args:
        question: Question to answer
        context: Optional context from previous reflections
        
    Returns:
        Answer prompt string
    """
    if context:
        return f"""Past feedback to consider:
{context}

Now answer the following question concisely:
{question}

Answer:"""
    else:
        return f"""{question}

Answer:"""
