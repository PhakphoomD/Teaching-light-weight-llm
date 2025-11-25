"""
Simplified Teacher Module - Feedback Generation Only

Handles ONLY teaching and feedback generation.
All scoring/evaluation moved to metrics.py.

Key features:
1. Free-form feedback generation (no keyword constraints)
2. CoT-based feedback prompt for better reasoning
3. Special handling for difficult questions (round 4+)
4. Concise, actionable feedback

Teacher's role: Guide student learning through feedback
Metrics' role: Evaluate answer quality (separate concern)

Usage:
    from src.simplified.teacher import TeacherFeedback
    
    teacher = TeacherFeedback(config)
    feedback = teacher.generate_feedback(
        question="What is 2+2?",
        student_answer="5",
        ground_truth="4"
    )
"""

import re
from pathlib import Path
import sys
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.providers.factory import build_client
from src.utils.prompt_loader import get_prompt_loader


class TeacherFeedback:
    """
    Teacher feedback generator.
    
    Completely separate from scoring/evaluation logic.
    Focus: Help student improve through clear, actionable feedback.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize teacher feedback generator.
        
        Args:
            config: Teacher configuration dict with:
                - model: Teacher model name
                - provider: Provider name ('groq', 'gemini', etc.)
                - temperature: Sampling temperature (default: 0.2)
                - max_tokens: Max tokens for generation (default: 256)
                - feedback: Dict with feedback generation config
                - feedback_style: Feedback strategy ('cot', 'template', 'socratic')
        """
        self.config = config
        self.model = config['model']
        self.temperature = config.get('temperature', 0.2)
        self.max_tokens = config.get('max_tokens', 256)
        # Track total tokens used by the teacher model (for cost accounting)
        self.total_tokens: int = 0
        
        # Feedback config
        self.feedback_config = config.get('feedback', {
            'max_length': 200,
            'use_cot': True
        })
        
        # Feedback style (NEW: for Phase 1 experiments)
        self.feedback_style = config.get('feedback_style', 'cot')
        
        # Debug mode
        self.debug = config.get('debug', False)
        
        # Initialize teacher LLM client
        import src.providers  # Trigger provider registration
        
        provider = config.get('provider')
        if not provider:
            raise ValueError(
                "Teacher config must specify 'provider' field. "
                "Valid options: 'local', 'gemini', 'openai', 'groq'"
            )
        
        self.client = build_client(provider=provider, model=self.model)
    
    def generate_feedback(self,
                         question: str,
                         student_answer: str,
                         ground_truth: str,
                         previous_feedback: Optional[str] = None,
                         round_num: int = 1,
                         return_debug: bool = False):
        """
        Generate teaching feedback using CoT reasoning.
        
        Teacher has FULL FREEDOM - no keyword constraints!
        The teacher can use any approach that works best:
        - Give hints, examples, principles, or direct corrections
        - Analyze mistakes and suggest improvements
        - Provide context or background knowledge
        
        Args:
            question: The question
            student_answer: Student's incorrect answer
            ground_truth: Correct answer
            previous_feedback: Previous feedback (if refining)
            round_num: Current round number (for special handling)
            return_debug: If True, return dict with feedback/prompt/response
        
        Returns:
            If return_debug=False: Concise, actionable feedback (<200 chars)
            If return_debug=True: Dict with 'feedback', 'prompt', 'response'
        """
        # Select prompt based on feedback style
        if self.feedback_style == 'template':
            # Template-based feedback (concrete structure with placeholders)
            prompt = self._build_template_feedback_prompt(
                question, student_answer, ground_truth
            )
        elif self.feedback_style == 'socratic':
            # Socratic feedback (guiding questions)
            prompt = self._build_socratic_feedback_prompt(
                question, student_answer, ground_truth
            )
        else:  # 'cot' or 'analytical' (default)
            # Chain-of-thought feedback with reasoning
            if self.feedback_config.get('use_cot', True):
                # Round 4+: Use special CoT for difficult questions
                if round_num >= 4 and previous_feedback:
                    prompt = self._build_difficult_question_cot_prompt(
                        question, student_answer, ground_truth, previous_feedback
                    )
                else:
                    # Regular CoT
                    prompt = self._build_cot_feedback_prompt(
                        question, student_answer, ground_truth, previous_feedback
                    )
            else:
                # Direct feedback generation
                prompt = self._build_direct_feedback_prompt(
                    question, student_answer, ground_truth
                )
        
        try:
            response = self.client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout_s=60
            )
            # Accumulate token usage if available
            usage = getattr(response, "usage", None)
            if usage is not None:
                tokens = getattr(usage, "total_tokens", None)
                if isinstance(tokens, int):
                    self.total_tokens += tokens

            if getattr(response, 'error', None):
                if self.debug:
                    print(f"  Feedback generation error: {response.error}")
                fallback = self._fallback_feedback(student_answer, ground_truth)
                if return_debug:
                    return {'feedback': fallback, 'prompt': prompt, 'response': None}
                return fallback
            
            feedback = (response.text or "").strip()
            
            # Extract feedback from CoT response if needed
            feedback = self._extract_feedback(feedback)
            
            if self.debug:
                print(f"  DEBUG: Teacher raw feedback (before truncate): '{feedback}'")
            
            # Truncate if too long
            max_len = self.feedback_config.get('max_length', 200)
            if len(feedback) > max_len:
                if self.debug:
                    print(f"  DEBUG: Truncating from {len(feedback)} to {max_len} chars")
                feedback = feedback[:max_len] + "..."
            
            if return_debug:
                return {'feedback': feedback, 'prompt': prompt, 'response': response}
            return feedback
            
        except Exception as e:
            if self.debug:
                print(f"  Feedback generation exception: {e}")
            fallback = self._fallback_feedback(student_answer, ground_truth)
            if return_debug:
                return {'feedback': fallback, 'prompt': prompt, 'response': None}
            return fallback
    
    def _build_difficult_question_cot_prompt(self,
                                              question: str,
                                              student_answer: str,
                                              ground_truth: str,
                                              previous_feedback: str) -> str:
        """
        Build special CoT prompt for difficult questions (round 4+).
        
        Stronger CoT with deeper analysis + shows ground_truth as "Example".
        """
        loader = get_prompt_loader()
        return loader.get_teacher_prompt(
            'difficult_question',
            question=question,
            student_answer=student_answer,
            ground_truth=ground_truth,
            previous_feedback=previous_feedback
        )

    def _build_cot_feedback_prompt(self,
                                   question: str,
                                   student_answer: str,
                                   ground_truth: str,
                                   previous_feedback: Optional[str]) -> str:
        """
        Build Chain-of-Thought prompt with full reasoning but concise output.
        
        Teacher outputs: "Error: [what's wrong]. Fix: [specific guidance]. Format: [exact output format]"
        """
        loader = get_prompt_loader()
        if previous_feedback:
            # Refining previous feedback (round < 4)
            return loader.get_teacher_prompt(
                'cot_refinement',
                question=question,
                student_answer=student_answer,
                ground_truth=ground_truth,
                previous_feedback=previous_feedback
            )
        else:
            # First-time feedback
            return loader.get_teacher_prompt(
                'cot_first_time',
                question=question,
                student_answer=student_answer,
                ground_truth=ground_truth
            )
    
    def _build_direct_feedback_prompt(self,
                                     question: str,
                                     student_answer: str,
                                     ground_truth: str) -> str:
        """Build direct feedback prompt (no CoT)."""
        loader = get_prompt_loader()
        return loader.get_teacher_prompt(
            'direct',
            question=question,
            student_answer=student_answer,
            ground_truth=ground_truth
        )
    
    def _build_template_feedback_prompt(self,
                                        question: str,
                                        student_answer: str,
                                        ground_truth: str) -> str:
        """
        Build template-based feedback prompt.
        
        Provides concrete structure with placeholders for the student to fill in.
        """
        loader = get_prompt_loader()
        return loader.get_teacher_prompt(
            'template_feedback',
            question=question,
            student_answer=student_answer,
            ground_truth=ground_truth
        )
    
    def _build_socratic_feedback_prompt(self,
                                        question: str,
                                        student_answer: str,
                                        ground_truth: str) -> str:
        """
        Build Socratic feedback prompt.
        
        Asks guiding questions instead of providing direct corrections.
        """
        loader = get_prompt_loader()
        return loader.get_teacher_prompt(
            'socratic_feedback',
            question=question,
            student_answer=student_answer,
            ground_truth=ground_truth
        )
    
    def _extract_feedback(self, response: str) -> str:
        """
        Extract final feedback from CoT response.
        
        Args:
            response: Full response with potential CoT reasoning
        
        Returns:
            Extracted feedback
        """
        # Try to find feedback after "Feedback:" label
        if "Feedback:" in response:
            parts = response.split("Feedback:")
            if len(parts) > 1:
                feedback = parts[-1].strip()
                # Remove any trailing reasoning markers
                feedback = feedback.split("\n")[0].strip()
                return feedback
        
        # Otherwise, take last non-empty line
        lines = [line.strip() for line in response.split("\n") if line.strip()]
        if lines:
            return lines[-1]
        
        return response.strip()
    
    def _fallback_feedback(self, student_answer: str, ground_truth: str) -> str:
        """
        Generate simple fallback feedback when LLM fails.
        
        Args:
            student_answer: Student's answer
            ground_truth: Correct answer
        
        Returns:
            Basic feedback
        """
        return f"Your answer is incorrect. Think more carefully about the question."
