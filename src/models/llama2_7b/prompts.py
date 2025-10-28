"""
Llama2 7B specific prompts

Prompts optimized for Llama2 7B model.
"""

from typing import Optional
from src.evaluation.critic import Critique, CriticResult


def format_previous_failure(critic_result: Optional[CriticResult]) -> str:
    """
    Format CriticResult as learning context (no answer leakage).
    
    Args:
        critic_result: CriticResult from previous attempt
        
    Returns:
        Formatted context string
    """
    if not critic_result or critic_result.satisfied:
        return ""
    
    context = "[Context from your previous attempt]\n"
    context += f"Error Analysis: {critic_result.error_analysis}\n"
    context += f"Key Learning: {critic_result.learning_point}\n"
    context += f"How to Improve: {critic_result.correction_hint}\n"
    
    if critic_result.missing_concepts:
        context += f"Missing Concepts: {', '.join(critic_result.missing_concepts)}\n"
    
    context += "\n"
    return context


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
        # Do NOT reveal the expected exact answer. Give rule-based guidance only.
        hint = (
            "Error Analysis:\n"
            "- Your answer must match the required string exactly\n"
            "- Use the precise wording (no extra or missing tokens)\n"
            "- Match spacing, punctuation, and casing as required\n\n"
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


def build_answer_prompt(
    question: str, 
    context: str = "",
    previous_answer: Optional[str] = None,
    previous_critique: Optional[Critique] = None,
    previous_critic_result: Optional[CriticResult] = None
) -> str:
    """
    Build answer prompt for Llama2 7B with optional previous failure context.
    
    Args:
        question: Question to answer
        context: Optional context from memory retrieval
        previous_answer: Previous incorrect answer (if retry) - DEPRECATED, use previous_critic_result
        previous_critique: Previous critique object (if retry) - DEPRECATED, use previous_critic_result
        previous_critic_result: Previous CriticResult (NEW - structured feedback)
        
    Returns:
        Answer prompt string
    """
    prompt = ""
    
    # Use new structured feedback if available
    if previous_critic_result:
        prompt += format_previous_failure(previous_critic_result)
    
    # Backward compatible: show previous attempt failure (old format)
    elif previous_answer and previous_critique:
        prompt += "[Your Previous Attempt]\n"
        prompt += f"You answered: {previous_answer}\n"
        
        if previous_critique.error_type == "missing_keywords":
            missing = previous_critique.missing_keywords or []
            expected = previous_critique.expected_keywords or []
            prompt += f"Error: Missing required keywords: {missing}\n"
            prompt += f"Required: {expected}\n"
        elif previous_critique.error_type == "exact_match_failed":
            prompt += "Error: Answer format does not match requirements\n"
            prompt += "Use precise wording as required\n"
        elif previous_critique.error_type == "empty_answer":
            prompt += "Error: You provided an empty answer\n"
        
        prompt += "\n"
    
    # Add context from memory retrieval if available
    if context:
        prompt += f"""You have access to relevant feedback from previous attempts:

{context}

Carefully consider the above feedback and apply the lessons learned.

"""
    
    # Add question
    prompt += f"""Now answer the following question accurately and completely:
{question}

Provide your answer:"""
    
    return prompt
