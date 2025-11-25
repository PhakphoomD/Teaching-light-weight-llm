"""
Shared CoT (Chain-of-Thought) Plugin

Provides CoT prompt building for both teacher and student.
"""

from ...core.logger import get_logger

logger = get_logger("refinement.shared.cot")


def build_cot_prompt(base_prompt: str, role: str = "student") -> str:
    """
    Build Chain-of-Thought prompt.
    
    Args:
        base_prompt: Base prompt text
        role: "teacher" or "student"
    
    Returns:
        CoT-enhanced prompt
    """
    if role == "teacher":
        template = """Let's evaluate this answer step by step:

1. First, identify what the question is asking
2. Check if the answer addresses the question
3. Verify factual accuracy
4. Assess completeness
5. Determine if the answer is correct

---

{base_prompt}

---

Now, let's think through this carefully:"""
    
    else:  # student
        template = """Let's think step by step:

1. First, understand what the question is asking
2. Recall relevant knowledge
3. Break down the problem if complex
4. Formulate a clear answer
5. Double-check the answer

---

{base_prompt}

---

Let's solve this carefully:"""
    
    return template.format(base_prompt=base_prompt)
