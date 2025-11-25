"""
Teacher/Critic Prompt Templates

This module provides prompt templates for the teacher model that acts as
a critic to evaluate student answers and provide constructive feedback.

The teacher model should:
1. Evaluate student answers objectively (correct/incorrect)
2. Provide reasoning using chain-of-thought (internal)
3. Generate helpful hints that guide without revealing the answer
"""


def build_teacher_prompt(
    question: str,
    student_answer: str,
    correct_answer: str = ""
) -> str:
    """
    Build a structured prompt for the teacher/critic model.
    
    This function creates a prompt that instructs the teacher to:
    - Evaluate whether the student's answer is correct or incorrect
    - Explain the reasoning behind the evaluation (chain-of-thought)
    - Provide a helpful hint that guides the student without revealing the answer
    
    The teacher must be unbiased and objective in evaluation. The reasoning
    section allows the model to use internal chain-of-thought processing,
    which can be used for hint distillation later.
    
    Args:
        question: The original question asked to the student (REQUIRED)
        student_answer: The answer provided by the student (REQUIRED)
        correct_answer: Optional correct answer for reference (if available)
    
    Returns:
        str: A formatted prompt string ready to be sent to the teacher model
    
    Output Format:
        The teacher's response MUST contain these XML-like tags:
        
        <EVALUATION>correct</EVALUATION> or <EVALUATION>incorrect</EVALUATION>
        - Simple binary judgment of the student's answer
        
        <REASONING>
        Step-by-step explanation of why the answer is correct/incorrect.
        This can include chain-of-thought reasoning, comparisons, and analysis.
        This section is internal and may be filtered before showing to student.
        </REASONING>
        
        <HINT>
        A helpful hint that guides the student toward the correct answer
        WITHOUT directly revealing it. Should be educational and constructive.
        Examples: "Think about the largest city in the country"
                  "Consider the formula for area of a circle"
        </HINT>
    
    Important Guidelines for the Teacher:
        1. Be objective and unbiased in evaluation
        2. Use clear reasoning based on facts
        3. Provide hints that teach, not tell
        4. Avoid revealing the exact answer in hints
        5. Be encouraging and constructive
        6. Use chain-of-thought in <REASONING> if helpful
    
    Example:
        >>> prompt = build_teacher_prompt(
        ...     question="What is the capital of France?",
        ...     student_answer="London"
        ... )
    
    Note:
        The correct_answer parameter is optional. If not provided, the teacher
        should use its own knowledge to evaluate. This allows flexibility for
        both supervised and unsupervised evaluation scenarios.
    """
    
    # Validate required fields
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")
    if not student_answer or not student_answer.strip():
        raise ValueError("Student answer cannot be empty")
    
    # Normalize inputs
    question = question.strip()
    student_answer = student_answer.strip()
    correct_answer = correct_answer.strip() if correct_answer else ""
    
    # Build the prompt
    prompt_parts = [
        "ROLE: TEACHER/CRITIC",
        "You are an expert teacher evaluating a student's answer.",
        "Your goal is to assess accuracy and provide constructive guidance.",
        "",
        "EVALUATION GUIDELINES:",
        "1. Determine if the student's answer is CORRECT or INCORRECT",
        "2. Provide clear reasoning for your evaluation (use chain-of-thought if needed)",
        "3. Generate a helpful hint that guides without revealing the exact answer",
        "4. Be objective, unbiased, and educational",
        "",
        "<QUESTION>",
        question,
        "</QUESTION>",
        "",
        "<STUDENT_ANSWER>",
        student_answer,
        "</STUDENT_ANSWER>",
        "",
    ]
    
    # Add correct answer if provided (optional reference)
    if correct_answer:
        prompt_parts.extend([
            "<CORRECT_ANSWER>",
            "(Reference for evaluation purposes)",
            correct_answer,
            "</CORRECT_ANSWER>",
            "",
        ])
    
    # Add output format instructions
    prompt_parts.extend([
        "YOUR EVALUATION:",
        "",
        "Provide your evaluation in the following format:",
        "",
        "<EVALUATION>",
        "State either 'correct' or 'incorrect'",
        "</EVALUATION>",
        "",
        "<REASONING>",
        "Explain your evaluation step-by-step.",
        "Use chain-of-thought reasoning if helpful.",
        "Compare the student's answer with the correct answer.",
        "This section is for your internal processing.",
        "</REASONING>",
        "",
        "<HINT>",
        "Provide a helpful hint that guides the student.",
        "DO NOT reveal the exact answer.",
        "Be constructive and educational.",
        "Example: 'Think about the capital city located on the Seine river'",
        "</HINT>",
        "",
        "Begin your evaluation:",
    ])
    
    return "\n".join(prompt_parts)


def build_teacher_prompt_simple(question: str, student_answer: str) -> str:
    """
    Build a simplified teacher prompt for quick evaluation.
    
    This version has minimal instructions and is faster to process.
    
    Args:
        question: The question
        student_answer: The student's answer
    
    Returns:
        str: A simple formatted prompt
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")
    if not student_answer or not student_answer.strip():
        raise ValueError("Student answer cannot be empty")
    
    return f"""ROLE: TEACHER/CRITIC
Evaluate if the student's answer is correct or incorrect, then provide a helpful hint.

<QUESTION>
{question.strip()}
</QUESTION>

<STUDENT_ANSWER>
{student_answer.strip()}
</STUDENT_ANSWER>

Respond using these tags:
<EVALUATION>correct or incorrect</EVALUATION>
<REASONING>Your reasoning here</REASONING>
<HINT>Your hint here (do not reveal the answer)</HINT>

Begin:"""


def build_grading_prompt(
    question: str,
    student_answer: str,
    correct_answer: str,
    rubric: str = ""
) -> str:
    """
    Build a prompt for detailed grading with a rubric.
    
    This is for more formal evaluation scenarios where you have
    a grading rubric or specific criteria.
    
    Args:
        question: The question
        student_answer: The student's answer
        correct_answer: The correct answer
        rubric: Optional grading rubric or criteria
    
    Returns:
        str: A formatted grading prompt
    """
    if not question or not student_answer or not correct_answer:
        raise ValueError("Question, student answer, and correct answer are required")
    
    prompt_parts = [
        "ROLE: GRADING TEACHER",
        "Evaluate the student's answer against the correct answer.",
        "",
        f"<QUESTION>{question.strip()}</QUESTION>",
        "",
        f"<STUDENT_ANSWER>{student_answer.strip()}</STUDENT_ANSWER>",
        "",
        f"<CORRECT_ANSWER>{correct_answer.strip()}</CORRECT_ANSWER>",
        "",
    ]
    
    if rubric:
        prompt_parts.extend([
            "<RUBRIC>",
            rubric.strip(),
            "</RUBRIC>",
            "",
        ])
    
    prompt_parts.extend([
        "Provide:",
        "<EVALUATION>correct or incorrect</EVALUATION>",
        "<REASONING>Detailed comparison and reasoning</REASONING>",
        "<HINT>Constructive hint for improvement</HINT>",
    ])
    
    return "\n".join(prompt_parts)
