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
        self.principles_text = self.feedback_config.get(
            'principles_text',
            'truthfulness, harmlessness, fairness, conciseness'
        )
        
        # Feedback style (NEW: for Phase 1 experiments)
        self.feedback_style = (config.get('feedback_style') or 'cot').lower()
        
        # NEW: Configurable prompt names (allows overriding from notebook config)
        # Default prompts per feedback_style
        default_prompts = {
            'orca': {'first': 'orca_critique', 'refine': 'orca_critique'},
            'principle': {'first': 'principle_critique', 'refine': 'principle_critique'},
            'cot': {'first': 'cot_first_time', 'refine': 'cot_refinement'},
        }
        style_defaults = default_prompts.get(self.feedback_style, default_prompts['cot'])
        
        # Allow config to override prompt names
        self.first_prompt = config.get('first_prompt') or style_defaults['first']
        self.refine_prompt = config.get('refine_prompt') or style_defaults['refine']
        
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
        # NEW: Use configurable prompt names from self.first_prompt / self.refine_prompt
        structured_parser = None
        
        # Determine which prompt to use (first round vs refinement)
        is_first_round = (round_num == 1 or not previous_feedback)
        prompt_name = self.first_prompt if is_first_round else self.refine_prompt
        
        # Build prompt using prompt_loader with the configured prompt name
        prompt = self._build_generic_prompt(
            prompt_name=prompt_name,
            question=question,
            student_answer=student_answer,
            ground_truth=ground_truth,
            previous_feedback=previous_feedback,
        )
        
        # Select parser based on feedback style
        if self.feedback_style == 'orca':
            structured_parser = self._parse_orca_feedback
        elif self.feedback_style == 'principle':
            structured_parser = self._parse_principle_feedback
        elif self.feedback_style == 'stop_decision':
            prompt = self._build_stop_decision_prompt(question, student_answer)
            structured_parser = self._parse_stop_decision_feedback
        elif self.feedback_style == 'template':
            prompt = self._build_template_feedback_prompt(
                question, student_answer, ground_truth
            )
        elif self.feedback_style == 'socratic':
            prompt = self._build_socratic_feedback_prompt(
                question, student_answer, ground_truth
            )
        elif self.feedback_style == 'cot':
            if self.feedback_config.get('use_cot', True):
                if round_num >= 4 and previous_feedback:
                    prompt = self._build_difficult_question_cot_prompt(
                        question, student_answer, ground_truth, previous_feedback
                    )
                else:
                    prompt = self._build_cot_feedback_prompt(
                        question, student_answer, ground_truth, previous_feedback
                    )
            else:
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
            
            raw_text = (response.text or "").strip()
            if structured_parser:
                parsed = structured_parser(raw_text)
            else:
                parsed = {
                    'feedback': self._extract_feedback(raw_text),
                    'critique': None,
                    'improvements': None,
                    'score': None,
                    'stop_flag': None,
                }
            feedback = parsed.get('feedback') or self._extract_feedback(raw_text)
            
            if self.debug:
                print(f"  DEBUG: Teacher raw feedback (before truncate): '{feedback}'")
            
            # Truncate if too long
            max_len = self.feedback_config.get('max_length', 200)
            if len(feedback) > max_len:
                if self.debug:
                    print(f"  DEBUG: Truncating from {len(feedback)} to {max_len} chars")
                feedback = feedback[:max_len] + "..."
            
            result_payload = {
                'feedback': feedback,
                'critique': parsed.get('critique'),
                'improvements': parsed.get('improvements'),
                'score': parsed.get('score'),
                'stop_flag': parsed.get('stop_flag'),
                'principle_critique': parsed.get('principle_critique'),
                'principle_improvements': parsed.get('principle_improvements'),
                'prompt': prompt,
                'response': response,
                'raw': raw_text,
            }
            if return_debug:
                return result_payload
            return result_payload['feedback']
            
        except Exception as e:
            if self.debug:
                print(f"  Feedback generation exception: {e}")
            fallback = self._fallback_feedback(student_answer, ground_truth)
            result_payload = {
                'feedback': fallback,
                'critique': None,
                'improvements': None,
                'score': None,
                'stop_flag': None,
                'principle_critique': None,
                'principle_improvements': None,
                'prompt': prompt,
                'response': None,
                'raw': None,
            }
            if return_debug:
                return result_payload
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
    
    def _build_generic_prompt(self,
                              prompt_name: str,
                              question: str,
                              student_answer: str,
                              ground_truth: str,
                              previous_feedback: Optional[str] = None) -> str:
        """
        Build prompt using any prompt template from prompts_config.yml.
        
        This allows config to specify which prompt to use instead of hardcoding.
        All available variables are passed; the template uses what it needs.
        
        Args:
            prompt_name: Name of the prompt in prompts_config.yml (e.g., 'orca_critique')
            question: The question
            student_answer: Student's answer
            ground_truth: Correct answer
            previous_feedback: Previous feedback (if refining)
            
        Returns:
            Formatted prompt string
        """
        loader = get_prompt_loader()
        return loader.get_teacher_prompt(
            prompt_name,
            question=question,
            student_answer=student_answer,
            ground_truth=ground_truth,
            previous_feedback=previous_feedback or "",
            principles_text=self.principles_text,
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

    def _build_orca_feedback_prompt(self, question: str, student_answer: str) -> str:
        """LEGACY: Orca feedback without ground_truth (kept for backward compatibility)."""
        loader = get_prompt_loader()
        return loader.get_teacher_prompt(
            'orca_critique',
            question=question,
            student_answer=student_answer,
        )

    def _build_orca_first_time_prompt(self, question: str, student_answer: str, ground_truth: str) -> str:
        """NEW: Orca feedback for first round WITH ground_truth."""
        loader = get_prompt_loader()
        return loader.get_teacher_prompt(
            'orca_first_time',
            question=question,
            student_answer=student_answer,
            ground_truth=ground_truth,
        )

    def _build_orca_refinement_prompt(self, question: str, student_answer: str, 
                                      ground_truth: str, previous_feedback: str) -> str:
        """NEW: Orca feedback for refinement rounds WITH ground_truth and previous_feedback."""
        loader = get_prompt_loader()
        return loader.get_teacher_prompt(
            'orca_refinement',
            question=question,
            student_answer=student_answer,
            ground_truth=ground_truth,
            previous_feedback=previous_feedback or "",
        )

    def _build_principle_feedback_prompt(self, question: str, student_answer: str) -> str:
        """LEGACY: Principle feedback without ground_truth (kept for backward compatibility)."""
        loader = get_prompt_loader()
        return loader.get_teacher_prompt(
            'principle_critique',
            question=question,
            student_answer=student_answer,
            principles_text=self.principles_text,
        )

    def _build_principle_first_time_prompt(self, question: str, student_answer: str, ground_truth: str) -> str:
        """NEW: Principle feedback for first round WITH ground_truth."""
        loader = get_prompt_loader()
        return loader.get_teacher_prompt(
            'principle_first_time',
            question=question,
            student_answer=student_answer,
            ground_truth=ground_truth,
            principles_text=self.principles_text,
        )

    def _build_principle_refinement_prompt(self, question: str, student_answer: str,
                                           ground_truth: str, previous_feedback: str) -> str:
        """NEW: Principle feedback for refinement rounds WITH ground_truth and previous_feedback."""
        loader = get_prompt_loader()
        return loader.get_teacher_prompt(
            'principle_refinement',
            question=question,
            student_answer=student_answer,
            ground_truth=ground_truth,
            previous_feedback=previous_feedback or "",
            principles_text=self.principles_text,
        )

    def _build_stop_decision_prompt(self, question: str, student_answer: str) -> str:
        loader = get_prompt_loader()
        return loader.get_teacher_prompt(
            'stop_decision',
            question=question,
            student_answer=student_answer,
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

    # -------- Parsing helpers for structured prompts --------

    def _extract_block(self, text: str, start_marker: str, end_marker: Optional[str] = None) -> str:
        if not text or start_marker not in text:
            return ""
        start = text.find(start_marker)
        if start == -1:
            return ""
        start += len(start_marker)
        remainder = text[start:]
        if end_marker:
            end = remainder.find(end_marker)
            if end != -1:
                remainder = remainder[:end]
        return remainder.strip()

    def _safe_float(self, value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None

    def _parse_orca_feedback(self, text: str) -> Dict[str, Any]:
        critique = self._extract_block(text, "Critique:", "Score:")
        score_raw = self._extract_block(text, "Score:", "Improvements:")
        improvements = self._extract_block(text, "Improvements:", None)
        score = self._safe_float(score_raw)
        summary = improvements or critique or text
        return {
            'critique': critique,
            'improvements': improvements,
            'score': score,
            'feedback': summary.strip() if isinstance(summary, str) else summary,
            'stop_flag': None,
            'principle_critique': None,
            'principle_improvements': None,
        }

    def _parse_principle_feedback(self, text: str) -> Dict[str, Any]:
        critique = self._extract_block(text, "Principle_Critique:", "Principle_Improvements:")
        improvements = self._extract_block(text, "Principle_Improvements:", None)
        summary = improvements or critique or text
        return {
            'critique': None,
            'improvements': None,
            'score': None,
            'feedback': summary.strip() if isinstance(summary, str) else summary,
            'stop_flag': None,
            'principle_critique': critique,
            'principle_improvements': improvements,
        }

    def _parse_stop_decision_feedback(self, text: str) -> Dict[str, Any]:
        critique = self._extract_block(text, "Brief_Critique:", "Score:")
        score_raw = self._extract_block(text, "Score:", "StopFlag:")
        stop_flag = self._extract_block(text, "StopFlag:", None).upper()
        score = self._safe_float(score_raw)
        if stop_flag not in {"STOP", "CONTINUE"}:
            stop_flag = None
        summary = critique or text
        return {
            'critique': critique,
            'improvements': None,
            'score': score,
            'feedback': summary.strip() if isinstance(summary, str) else summary,
            'stop_flag': stop_flag,
            'principle_critique': None,
            'principle_improvements': None,
        }
