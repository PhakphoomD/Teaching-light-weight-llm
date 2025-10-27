"""
Llama2 7B specific prompts

Prompts optimized for Llama2 7B model.
"""

from src.evaluation.critic import Critique


def build_reflection_prompt(question: str, answer: str, critique: Critique) -> str:
    """
    Build reflection prompt for Llama2 7B.
    
    Llama2 can handle more detailed analysis than TinyLlama.
    
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
    
    # Build detailed error analysis
    if critique.error_type == "missing_keywords":
        missing = critique.missing_keywords or []
        expected = critique.expected_keywords or []
        present_kws = [k for k in expected if k not in missing]
        
        hint = (
            f"Error Analysis:\n"
            f"- Your answer is incomplete and missing key concepts\n"
            f"- Missing required concepts: {', '.join(missing)}\n"
        )
        if present_kws:
            hint += f"- Concepts you correctly identified: {', '.join(present_kws)}\n"
        hint += f"- All required concepts: {', '.join(expected)}\n\n"
        
    elif critique.error_type == "exact_match_failed":
        hint = (
            f"Error Analysis:\n"
            f"- Your answer doesn't match the expected format\n"
            f"- Expected answer: '{critique.expected_exact}'\n"
            f"- Your answer: '{critique.student_answer}'\n\n"
        )
        
    elif critique.error_type == "empty_answer":
        hint = "Error Analysis:\n- You provided an empty or blank answer\n\n"
        
    else:
        hint = "Error Analysis:\n- Your answer was marked as incorrect\n\n"
    
    reflection_questions = (
        f"Provide a detailed reflection on your mistake:\n\n"
        f"1. Conceptual Understanding: What fundamental principle or concept did you miss?\n"
        f"2. Reasoning Analysis: What was your thought process? Why did it lead you astray?\n"
        f"3. Correct Approach: Explain the correct way to solve this type of problem\n"
        f"4. Future Strategy: What specific strategy will you use to avoid this mistake?\n"
        f"5. Key Insight: Summarize the most important lesson learned\n\n"
        f"Write a comprehensive reflection (5-8 sentences) that demonstrates deep understanding:"
    )
    
    return base_intro + hint + reflection_questions


def build_answer_prompt(question: str, context: str = "") -> str:
    """
    Build answer prompt for Llama2 7B.
    
    Args:
        question: Question to answer
        context: Optional context from previous reflections
        
    Returns:
        Answer prompt string
    """
    if context:
        return f"""You have access to relevant feedback from previous attempts:

{context}

Carefully consider the above feedback and apply the lessons learned.

Now answer the following question accurately and completely:
{question}

Provide your answer:"""
    else:
        return f"""Question: {question}

Provide a clear, accurate, and complete answer:"""
