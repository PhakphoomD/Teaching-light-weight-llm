"""
CoT Student Plugin

Provides Chain-of-Thought prompting for student answer generation.
"""

from ....core.logger import get_logger

logger = get_logger("refinement.student.cot")


def build_cot_answer_prompt(base_prompt: str) -> str:
    """
    Build CoT answer prompt for student.
    
    Wraps base answer prompt with CoT template.
    
    Args:
        base_prompt: Base answer prompt
    
    Returns:
        CoT-enhanced prompt
    """
    cot_template = """Let's think step by step:

1. First, understand what the question is asking
2. Recall relevant knowledge
3. Break down the problem if complex
4. Formulate a clear answer
5. Double-check the answer

---

{base_prompt}

---

Let's solve this carefully:"""
    
    return cot_template.format(base_prompt=base_prompt)
