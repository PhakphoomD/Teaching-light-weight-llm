"""
Student Prompt Templates

This module provides prompt templates for the student model.
The prompts are designed to be clear, structured, and help the model understand
its role and the information available to it.
"""


def build_student_prompt(
    question: str,
    hints: str = "",
    context: str = "",
    use_cot: bool = False,
    previous_answer: str = ""
) -> str:
    """
    Build a structured prompt for the student model.
    
    This function creates a prompt that clearly defines the student's role
    and provides all necessary information in a structured format with
    XML-like delimiters for easy parsing.
    
    Args:
        question: The question the student needs to answer (REQUIRED)
        hints: Optional hints from the teacher to guide the student
        context: Optional relevant context from memory/RAG system
        use_cot: Enable chain-of-thought prompting (show reasoning)
        previous_answer: Student's previous attempt (for learning from mistakes)
    
    Returns:
        str: A formatted prompt string ready to be sent to the student model
    
    Template Structure:
        - ROLE: Defines the model's role as a student
        - QUESTION: The actual question (must be filled)
        - HINTS: Teacher's hints if available (can be empty)
        - CONTEXT: Retrieved relevant information (can be empty)
        - INSTRUCTION: What the model should do
    
    Important Notes:
        - All placeholders (<QUESTION>, <HINTS>, <CONTEXT>) MUST be filled
          with actual data before sending to the model
        - Empty hints/context should be explicitly stated (e.g., "No hints provided")
        - The delimiter tags help in prompt engineering and debugging
        - Do not include leading/trailing whitespace in the values
    
    Example:
        >>> prompt = build_student_prompt(
        ...     question="What is the capital of France?",
        ...     hints="Think about famous European cities",
        ...     context="France is a country in Western Europe"
        ... )
        >>> print(prompt)
        ROLE: STUDENT
        You are a student learning to answer questions...
    """
    
    # Validate required fields
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")
    
    # Normalize inputs (remove extra whitespace)
    question = question.strip()
    hints = hints.strip() if hints else ""
    context = context.strip() if context else ""
    previous_answer = previous_answer.strip() if previous_answer else ""
    
    # Build simple, direct prompt (no meta-instructions that confuse models)
    # Only show principles if there's feedback, otherwise keep it minimal
    prompt_parts = []
    
    # Simple instruction for first attempt
    if not previous_answer and not hints:
        prompt_parts.extend([
            "Answer the following question directly and completely.",
            "",
        ])
    else:
        # If refining, add minimal guidance
        prompt_parts.extend([
            "You are refining your answer. Provide a clear, complete response.",
            "",
        ])
    
    # Show previous attempt if refining (simple, direct)
    if previous_answer:
        prompt_parts.extend([
            f"Your previous answer was: {previous_answer}",
            "",
        ])
    
    # Show feedback if available (simple, direct)
    if hints:
        prompt_parts.extend([
            f"Feedback: {hints}",
            "",
        ])
    
    # Memory context injection disabled for current model architecture
    # Context from similar questions may cause interference with answer generation
    
    # Add the question (simple format)
    prompt_parts.extend([
        f"Question: {question}",
        "",
    ])
    
    # Simple answer prompt
    if use_cot:
        prompt_parts.append("Answer (think step-by-step):")
    else:
        prompt_parts.append("Answer:")
    
    return "\n".join(prompt_parts)


def build_ground_truth_hint_prompt(question: str, ground_truth: str, previous_answer: str = "") -> str:
    """
    Build an extremely simple prompt with ground truth (last resort).
    Forces the model to copy the answer exactly.
    
    Args:
        question: The question
        ground_truth: The correct answer
        previous_answer: Student's previous wrong answer (unused)
    
    Returns:
        str: Ultra-simple prompt forcing exact copy
    """
    from src.utils.prompt_loader import get_prompt_loader
    loader = get_prompt_loader()
    return loader.get_student_prompt('last_chance', ground_truth=ground_truth)


def build_student_prompt_simple(question: str) -> str:
    """
    Build a simple student prompt with only the question.
    
    This is a lightweight version for baseline testing without hints or context.
    
    Args:
        question: The question to answer
    
    Returns:
        str: A simple formatted prompt
    
    Example:
        >>> prompt = build_student_prompt_simple("What is 2+2?")
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")
    
    return f"""Answer this question directly:

QUESTION:
{question.strip()}

ANSWER:"""


def extract_student_answer(response: str) -> str:
    """
    Extract the student's answer from the model's response.
    
    This function cleans up the response by removing any prompt echoes
    or extra formatting.
    
    Args:
        response: Raw response from the student model
    
    Returns:
        str: Cleaned answer text
    
    Note:
        If the response contains "YOUR ANSWER:", extract text after it.
        Otherwise, return the full response trimmed.
    """
    if not response:
        return ""
    
    # Check if response contains the delimiter
    if "ANSWER:" in response:
        # Extract everything after "ANSWER:"
        parts = response.split("ANSWER:", 1)
        if len(parts) > 1:
            return parts[1].strip()
    
    # Otherwise return the full response cleaned
    return response.strip()
