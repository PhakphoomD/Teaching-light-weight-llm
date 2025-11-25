"""
Simple Task Type Extractor

Uses regex patterns to classify questions into task types.
Fast, lightweight, no LLM calls needed.
"""

import re
from typing import Tuple


def extract_task_type(question: str) -> Tuple[str, str]:
    """
    Extract task type from question using regex patterns.
    
    Args:
        question: Question text
    
    Returns:
        (task_type, confidence)
        - task_type: Category name
        - confidence: "high" | "medium" | "low"
    
    Example:
        >>> extract_task_type("Name 5 adventure sports")
        ("list_generation", "high")
        
        >>> extract_task_type("Split sentence: hello")
        ("text_splitting", "high")
    """
    q_lower = question.lower().strip()
    
    # Pattern 1: List generation (Name N items, List N things)
    if re.search(r'\b(name|list|give|provide|mention)\s+\d+', q_lower):
        return "list_generation", "high"
    
    # Pattern 2: Split/Break text (including "Split: text" format)
    if re.search(r'\b(split|break|separate|divide)\b', q_lower):
        return "text_splitting", "high"
    
    # Pattern 3: Definition/Explanation (expanded patterns)
    if re.search(r'\b(define|definition|explain|what\s+is|describe|write.*definition)\b', q_lower):
        return "definition", "high"
    
    # Pattern 4: Translation
    if re.search(r'\b(translate|convert)\b.*\b(to|into|from)\b', q_lower):
        return "translation", "high"
    
    # Pattern 5: Math/Calculation (expanded to catch more math operations)
    if re.search(r'\b(calculate|compute|find|solve)\b', q_lower) or \
       re.search(r'(\d+\s*[+\-*/×÷]\s*\d+|percentage|%|square root|sqrt)', q_lower):
        return "math_problem", "high"
    
    # Pattern 6: Classification/Categorization
    if re.search(r'\b(classify|categorize|sort|group)\b', q_lower):
        return "classification", "high"
    
    # Pattern 7: Comparison
    if re.search(r'\b(compare|contrast|difference|similar)\b', q_lower):
        return "comparison", "medium"
    
    # Pattern 8: Summarization
    if re.search(r'\b(summarize|summarise|brief|overview)\b', q_lower):
        return "summarization", "medium"
    
    # Pattern 9: Question Answering (default for questions)
    if question.strip().endswith('?'):
        return "question_answering", "low"
    
    # Default: General instruction
    return "general_instruction", "low"


def get_task_description(task_type: str) -> str:
    """Get human-readable description of task type."""
    descriptions = {
        "list_generation": "Generate a list of items",
        "text_splitting": "Split text into components",
        "definition": "Define or explain a concept",
        "translation": "Translate between languages",
        "math_problem": "Solve mathematical problems",
        "classification": "Classify or categorize items",
        "comparison": "Compare multiple items",
        "summarization": "Summarize text",
        "question_answering": "Answer a question",
        "general_instruction": "General task"
    }
    return descriptions.get(task_type, "Unknown task type")


# Test the extractor
if __name__ == "__main__":
    test_questions = [
        "Name 5 adventure sports",
        "Name 3 subjects that people hate",
        "Split the sentence into words: Iamadoglover",
        "Define the term photosynthesis",
        "Translate this to French: Hello world",
        "Calculate 15% of 200",
        "What is the capital of France?",
        "Summarize the following article:",
        "Compare Python and Java",
    ]
    
    print("Task Type Extraction Test")
    print("=" * 80)
    
    for question in test_questions:
        task_type, confidence = extract_task_type(question)
        desc = get_task_description(task_type)
        print(f"\nQuestion: {question}")
        print(f"  Type: {task_type}")
        print(f"  Confidence: {confidence}")
        print(f"  Description: {desc}")
