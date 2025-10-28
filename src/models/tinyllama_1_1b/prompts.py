"""
TinyLlama 1.1B specific prompts
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
        # Do NOT reveal the expected exact answer to avoid leakage.
        # Provide format/rule guidance only.
        hint = (
            "Analysis: Your answer must match the required string exactly.\n"
            "- Follow the required wording precisely (no extra words).\n"
            "- Match spacing, punctuation, and casing as required.\n"
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


def build_answer_prompt(
    question: str, 
    context: str = "",
    previous_answer: Optional[str] = None,
    previous_critique: Optional[Critique] = None,
    previous_critic_result: Optional[CriticResult] = None
) -> str:
    """
    Build answer prompt for TinyLlama with optional previous failure context.
    
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
            prompt += f"Error: Missing required keywords: {missing}\n"
        elif previous_critique.error_type == "exact_match_failed":
            prompt += "Error: Answer format does not match requirements\n"
        elif previous_critique.error_type == "empty_answer":
            prompt += "Error: You provided an empty answer\n"
        
        prompt += "\n"
    
    # Add context from memory retrieval if available
    if context:
        prompt += f"""Past feedback to consider:
{context}

"""
    
    # Add question
    prompt += f"""Now answer the following question concisely:
{question}

Answer:"""
    
    return prompt
