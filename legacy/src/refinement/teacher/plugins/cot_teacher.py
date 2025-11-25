"""
CoT Teacher Plugin

Provides Chain-of-Thought prompting for teacher evaluation.
"""

from ....core.logger import get_logger

logger = get_logger("refinement.teacher.cot")


def build_cot_evaluation_prompt(base_prompt: str) -> str:
    """
    Build CoT evaluation prompt for teacher.
    
    Wraps base evaluation prompt with CoT template.
    
    Args:
        base_prompt: Base evaluation prompt
    
    Returns:
        CoT-enhanced prompt
    """
    cot_template = """Let's evaluate this answer step by step:

1. First, identify what the question is asking
2. Check if the answer addresses the question
3. Verify factual accuracy
4. Assess completeness
5. Determine if the answer is correct

---

{base_prompt}

---

Now, let's think through this carefully:"""
    
    return cot_template.format(base_prompt=base_prompt)
