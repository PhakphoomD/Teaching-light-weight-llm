"""
Simplified Teacher Module

Handles evaluation and feedback generation with multiple metrics to prevent bias.

Key features:
1. Multi-metric evaluation: F1, BLEU, Similarity, Teacher-LLM score
2. Configurable weights for final score computation
3. Free-form feedback generation (no keyword constraints)
4. CoT-based feedback prompt for better reasoning
5. Separate evaluation and feedback generation

Metrics breakdown:
- Exact Match: Binary match (0 or 1)
- F1 Score: Token overlap with precision/recall
- BLEU Score: N-gram overlap (machine translation metric)
- Similarity: Cosine similarity of embeddings
- Teacher Score: LLM-based semantic evaluation (0-1)

Final Score = weighted average of all metrics
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional
import re

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.eval import metrics as det_metrics
from src.providers.factory import build_client


class TeacherEvaluator:
    """
    Teacher evaluator with multi-metric scoring and feedback generation.
    
    Evaluation is separate from feedback generation to allow flexibility
    and prevent bias from leaked answers.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize teacher evaluator with configuration.
        
        Args:
            config: Teacher configuration dict with:
                - model: Teacher model name (e.g., "gemini-2.0-flash-lite")
                - temperature: Sampling temperature (default: 0.1)
                - max_tokens: Max tokens for generation (default: 256)
                - metrics: Dict with metric weights
                - pass_threshold: Score threshold to pass (default: 0.8)
                - feedback: Dict with feedback generation config
                - hybrid_scoring: Dict with blind/comparison judge config (optional)
        """
        self.config = config
        self.model = config['model']
        self.temperature = config.get('temperature', 0.1)
        self.max_tokens = config.get('max_tokens', 256)
        self.pass_threshold = config.get('pass_threshold', 0.8)
        
        # Hybrid Scoring (optional)
        self.hybrid_enabled = config.get('hybrid_scoring', {}).get('enabled', False)
        
        # Metric weights (should sum to 1.0)
        if self.hybrid_enabled:
            # Hybrid mode: blind + comparison + deterministic metrics
            DEFAULT_WEIGHTS = {
                'blind_score': 0.2,      # Blind judge (unbiased)
                'comparison_score': 0.4, # Comparison judge (accurate)
                'semantic_sim': 0.2,     # Embedding similarity
                'rouge_l': 0.1,          # Format check
                'exact_match': 0.1       # Perfect match bonus
            }
        else:
            # Legacy mode: single teacher score + deterministic metrics
            DEFAULT_WEIGHTS = {
                'teacher_score': 0.6,    # LLM grader
                'semantic_sim': 0.2,     # Embedding similarity
                'rouge_l': 0.1,          # Format check
                'exact_match': 0.1       # Perfect match bonus
            }
        self.weights = config.get('metrics', {}).get('weights', DEFAULT_WEIGHTS)
        
        # Feedback config
        self.feedback_config = config.get('feedback', {
            'max_length': 100,
            'use_cot': True,
            'avoid_examples': False  # Teacher is free to use examples if needed
        })
        
        # Debug mode (from config, default False for clean UI)
        self.debug = config.get('debug', False)
        
        # Initialize teacher LLM client (for feedback generation)
        import src.providers  # Trigger provider registration
        
        # Get provider from config (required)
        provider = config.get('provider')
        if not provider:
            raise ValueError(
                "Teacher config must specify 'provider' field. "
                "Valid options: 'local', 'gemini', 'openai', 'groq'"
            )
        
        self.client = build_client(provider=provider, model=self.model)
        
        # Initialize hybrid scoring judges (if enabled)
        if self.hybrid_enabled:
            hybrid_config = config.get('hybrid_scoring', {})
            
            # Blind judge (no ground truth)
            blind_cfg = hybrid_config.get('blind_judge', {})
            self.blind_judge = build_client(
                provider=blind_cfg.get('provider', 'gemini'),
                model=blind_cfg.get('model', 'gemini-2.0-flash-exp')
            )
            self.blind_weight = blind_cfg.get('weight', 0.2)
            
            # Comparison judge (with ground truth)
            comp_cfg = hybrid_config.get('comparison_judge', {})
            self.comparison_judge = build_client(
                provider=comp_cfg.get('provider', 'groq'),
                model=comp_cfg.get('model', 'llama-3.3-70b-versatile')
            )
            self.comparison_weight = comp_cfg.get('weight', 0.4)
        else:
            self.blind_judge = None
            self.comparison_judge = None
        
        # Initialize sentence encoder for semantic similarity
        try:
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            print("sentence-transformers not installed, semantic_similarity will be disabled")
            self.encoder = None
    
    def evaluate(self,
                 question: str,
                 student_answer: str,
                 ground_truth: str) -> Dict[str, Any]:
        """
        Evaluate student answer using multiple metrics.
        
        Args:
            question: The question asked
            student_answer: Student's answer
            ground_truth: Correct answer
        
        Returns:
            Dict with:
            - scores: Dict of individual metric scores
            - final_score: Weighted average
            - passed: Boolean (>= threshold)
            - debug_info: Dict with prompts/responses for logging
        """
        scores = {}
        debug_info = {
            'prompts': [],
            'responses': []
        }
        
        # 1. Exact Match (perfect match bonus)
        scores['exact_match'] = float(det_metrics.exact_match(
            student_answer, ground_truth
        ))
        
        # 2. ROUGE-L Recall (longest common subsequence)
        rouge = det_metrics.rouge_scores(student_answer, ground_truth)
        scores['rouge_l'] = rouge['rouge-l']
        
        # 3. Semantic Similarity (sentence embeddings)
        if self.encoder:
            scores['semantic_sim'] = det_metrics.semantic_similarity(
                student_answer, ground_truth, encoder=self.encoder
            )
        else:
            scores['semantic_sim'] = 0.0
        
        # 4. LLM Scoring (hybrid or legacy)
        if self.hybrid_enabled:
            # Hybrid: Blind judge + Comparison judge
            blind_result = self._get_blind_score(question, student_answer, return_debug=True)
            comparison_result = self._get_comparison_score(question, student_answer, ground_truth, return_debug=True)
            
            scores['blind_score'] = blind_result['score'] if blind_result['score'] is not None else 0.0
            scores['comparison_score'] = comparison_result['score'] if comparison_result['score'] is not None else 0.0
            
            # Collect debug info
            if blind_result.get('prompt'):
                debug_info['prompts'].append(('blind_judge', blind_result['prompt']))
            if blind_result.get('response'):
                debug_info['responses'].append(('blind_judge', blind_result['response']))
            if comparison_result.get('prompt'):
                debug_info['prompts'].append(('comparison_judge', comparison_result['prompt']))
            if comparison_result.get('response'):
                debug_info['responses'].append(('comparison_judge', comparison_result['response']))
        else:
            # Legacy: Single teacher score (with ground truth)
            teacher_result = self._get_teacher_score(question, student_answer, ground_truth, return_debug=True)
            scores['teacher_score'] = teacher_result['score'] if teacher_result['score'] is not None else 0.0
            
            if teacher_result.get('prompt'):
                debug_info['prompts'].append(('teacher', teacher_result['prompt']))
            if teacher_result.get('response'):
                debug_info['responses'].append(('teacher', teacher_result['response']))
        
        # Compute final weighted score
        final_score = self._compute_final_score(scores)
        scores['final'] = final_score  # Add to scores dict for logging
        
        # Check if passed
        passed = final_score >= self.pass_threshold
        
        return {
            'scores': scores,
            'final_score': final_score,
            'passed': passed,
            'debug_info': debug_info
        }
    
    def _compute_final_score(self, scores: Dict[str, float]) -> float:
        """
        Compute weighted final score from individual metrics.
        
        Args:
            scores: Dict of metric scores
        
        Returns:
            Weighted average score (0.0 to 1.0)
        """
        weighted_sum = 0.0
        total_weight = 0.0
        
        for metric, weight in self.weights.items():
            if metric in scores:
                weighted_sum += scores[metric] * weight
                total_weight += weight
        
        # Normalize by total weight (in case some metrics are missing)
        if total_weight > 0:
            return weighted_sum / total_weight
        else:
            return 0.0
    
    def _get_blind_score(self,
                        question: str,
                        student_answer: str,
                        return_debug: bool = False):
        """
        Get blind score (without seeing ground truth) - unbiased evaluation.
        
        Judge evaluates based on:
        - Does the answer make sense for the question?
        - Is it relevant and coherent?
        - Does it show understanding of the topic?
        
        Args:
            question: The question
            student_answer: Student's answer
            return_debug: If True, return dict with prompt/response, else just score
        
        Returns:
            If return_debug=False: Score between 0.0 and 1.0, or None if failed
            If return_debug=True: Dict with 'score', 'prompt', 'response'
        """
        prompt = f"""You are an evaluator. Rate the quality of this answer WITHOUT seeing the correct answer.

Question: {question}
Student's answer: {student_answer}

Evaluation criteria:
1. RELEVANCE: Does the answer address the question? (most important)
2. COHERENCE: Is it clear and well-structured?
3. COMPLETENESS: Does it provide sufficient information?
4. CORRECTNESS: Based on your knowledge, is it factually accurate?

Rating scale (0.0 to 1.0):
- 1.0 = Excellent answer (relevant, coherent, complete, accurate)
- 0.8-0.9 = Good answer (minor issues but generally correct)
- 0.6-0.7 = Acceptable (relevant but incomplete or unclear)
- 0.4-0.5 = Poor (partially relevant or has errors)
- 0.0-0.3 = Very poor (irrelevant, incoherent, or wrong)

Output ONLY a number between 0.0 and 1.0. No explanation.

Score:"""
        
        try:
            response = self.blind_judge.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=50,
                timeout_s=30
            )
            
            if getattr(response, 'error', None):
                if self.debug:
                    print(f" Blind judge error: {response.error}")
                if return_debug:
                    return {'score': None, 'prompt': prompt, 'response': None}
                return None
            
            text = (response.text or "").strip()
            if self.debug:
                print(f"  DEBUG: Blind judge response = '{text}'")
            score = self._parse_score(text)
            if self.debug:
                print(f"  DEBUG: Blind score = {score}")
            
            if return_debug:
                return {'score': score, 'prompt': prompt, 'response': response}
            return score
            
        except Exception as e:
            if self.debug:
                print(f" Blind judge exception: {e}")
            if return_debug:
                return {'score': None, 'prompt': prompt, 'response': None}
            return None
    
    def _get_comparison_score(self,
                             question: str,
                             student_answer: str,
                             ground_truth: str,
                             return_debug: bool = False):
        """
        Get comparison score (with ground truth) - accurate semantic evaluation.
        
        Args:
            question: The question
            student_answer: Student's answer
            ground_truth: Correct answer
            return_debug: If True, return dict with prompt/response, else just score
        
        Returns:
            If return_debug=False: Score between 0.0 and 1.0, or None if failed
            If return_debug=True: Dict with 'score', 'prompt', 'response'
        """
        prompt = f"""You are an evaluator. Compare student's answer with the reference answer.

Question: {question}
Reference answer: {ground_truth}
Student's answer: {student_answer}

CRITICAL RULES - Focus on MEANING, not FORMAT:
1. If student's answer has the SAME MEANING → 0.9-1.0
   - Different wording is OK (e.g., "dog" = "canine")
   - Different format is OK (e.g., "Paris" = "The capital is Paris")
   - Different order is OK (e.g., "A and B" = "B and A")
2. Extra information is OK if core meaning is correct
3. Only penalize if FACTS/MEANING are wrong or missing

Rating scale (0.0 to 1.0):
- 1.0 = Same meaning, may have different words/format/order
- 0.9 = Same meaning with minor extra/missing details
- 0.7-0.8 = Mostly correct but missing important parts
- 0.5-0.6 = Partially correct (some right, some wrong)
- 0.0-0.4 = Wrong meaning or irrelevant

Output ONLY a number between 0.0 and 1.0. No explanation.

Score:"""
        
        try:
            response = self.comparison_judge.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=50,
                timeout_s=30
            )
            
            if getattr(response, 'error', None):
                if self.debug:
                    print(f" Comparison judge error: {response.error}")
                if return_debug:
                    return {'score': None, 'prompt': prompt, 'response': None}
                return None
            
            text = (response.text or "").strip()
            if self.debug:
                print(f"  DEBUG: Comparison judge response = '{text}'")
            score = self._parse_score(text)
            if self.debug:
                print(f"  DEBUG: Comparison score = {score}")
            
            if return_debug:
                return {'score': score, 'prompt': prompt, 'response': response}
            return score
            
        except Exception as e:
            if self.debug:
                print(f" Comparison judge exception: {e}")
            if return_debug:
                return {'score': None, 'prompt': prompt, 'response': None}
            return None
    
    def _get_teacher_score(self,
                           question: str,
                           student_answer: str,
                           ground_truth: str,
                           return_debug: bool = False):
        """
        Get semantic correctness score from teacher LLM (LEGACY - for backward compatibility).
        
        This method is only used when hybrid_scoring is disabled.
        
        Args:
            question: The question
            student_answer: Student's answer
            ground_truth: Correct answer
            return_debug: If True, return dict with prompt/response, else just score
        
        Returns:
            If return_debug=False: Score between 0.0 and 1.0, or None if failed
            If return_debug=True: Dict with 'score', 'prompt', 'response'
        """
        prompt = f"""You are an evaluator. Rate ONLY the semantic correctness (meaning), NOT the format or length.

Question: {question}
Correct answer: {ground_truth}
Student's answer: {student_answer}

IMPORTANT:
- If the student's answer contains the correct information, give high score (0.9-1.0)
- Extra explanation or different wording is OK if the core meaning is correct
- Length difference is acceptable as long as content is accurate
- Only penalize if the answer is factually wrong or missing key information

Rating scale (0.0 to 1.0):
- 1.0 = Correct information (may be longer/shorter but semantically right)
- 0.9 = Correct with minor verbosity or missing minor details
- 0.7-0.8 = Mostly correct but missing some important parts
- 0.5-0.6 = Partially correct (has some right info but incomplete)
- 0.0-0.4 = Incorrect or irrelevant

Output ONLY a number between 0.0 and 1.0. No explanation.

Score:"""
        
        try:
            response = self.client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=50,  # Short response
                timeout_s=30
            )
            
            if getattr(response, 'error', None):
                if self.debug:
                    print(f" Teacher scoring error: {response.error}")
                if return_debug:
                    return {'score': None, 'prompt': prompt, 'response': None}
                return None
            
            # Parse score from response
            text = (response.text or "").strip()
            if self.debug:
                print(f"  DEBUG: Teacher score LLM response = '{text}'")
            score = self._parse_score(text)
            if self.debug:
                print(f"  DEBUG: Parsed score = {score}")
            
            if return_debug:
                return {'score': score, 'prompt': prompt, 'response': response}
            return score
            
        except Exception as e:
            if self.debug:
                print(f" Teacher scoring exception: {e}")
            if return_debug:
                return {'score': None, 'prompt': prompt, 'response': None}
            return None
    
    def _parse_score(self, text: str) -> Optional[float]:
        """
        Parse score from teacher response.
        
        Args:
            text: Response text
        
        Returns:
            Score or None if parsing failed
        """
        # Try to extract first number
        match = re.search(r'(\d+\.?\d*)', text)
        if match:
            try:
                score = float(match.group(1))
                # Clamp to [0.0, 1.0]
                return max(0.0, min(1.0, score))
            except ValueError:
                pass
        return None
    
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
            If return_debug=False: Concise, actionable feedback (<100 chars recommended)
            If return_debug=True: Dict with 'feedback', 'prompt', 'response'
        """
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
            
            if getattr(response, 'error', None):
                if self.debug:
                    print(f" Feedback generation error: {response.error}")
                fallback = self._fallback_feedback(student_answer, ground_truth)
                if return_debug:
                    return {'feedback': fallback, 'prompt': prompt, 'response': None}
                return fallback
            
            feedback = (response.text or "").strip()
            
            # Extract feedback from CoT response if needed
            feedback = self._extract_feedback(feedback)
            
            if self.debug:
                print(f"  DEBUG: Teacher raw feedback (before truncate): '{feedback}'")
            
            # Truncate if too long (increased to 200 to accommodate Error + Fix + Format)
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
                print(f" Feedback generation exception: {e}")
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
        This gives student a concrete reference without explicitly saying "copy this".
        """
        return f"""CRITICAL: The student keeps giving the SAME answer. Analyze why and fix it.

[Question]
{question}

[Target Answer]
{ground_truth}

[Student's Repeated Answer]
{student_answer}

[Failed Feedback]
{previous_feedback}

<Root Cause Analysis>
1. Is the CONTENT/MEANING of student's answer correct?
   - Compare with [Target Answer] above
   - If YES → Problem is ONLY format/structure
   - If NO → Problem is content (wrong facts/concept)
2. Why is previous feedback failing?
   - Too vague? (e.g., "be more specific" doesn't help)
   - Wrong diagnosis? (saying "wrong" when it's correct but wrong format)
3. What is the EXACT difference between student's answer and target?
4. What ULTRA-SPECIFIC instruction will fix it?
</Root Cause Analysis>

SOLUTION RULES:
- If content is correct → Say "Your answer is correct! Just fix the format:"
- Give COMPLETE template with ALL static words written out
- Use [brackets] ONLY for variable parts
- Show a concrete example to make it crystal clear

Return ONLY:
"Error: [diagnosis]. Fix: [ultra-specific instruction]. Format: '[COMPLETE template]'. Example: {ground_truth}"

IMPORTANT: Keep under 250 chars total. Be EXTREMELY SPECIFIC.

Feedback:"""

    def _build_cot_feedback_prompt(self,
                                   question: str,
                                   student_answer: str,
                                   ground_truth: str,
                                   previous_feedback: Optional[str]) -> str:
        """
        Build Chain-of-Thought prompt with full reasoning but concise output.
        
        Teacher outputs: "Error: [what's wrong]. Fix: [specific guidance]. Format: [exact output format]"
        """
        if previous_feedback:
            # Refining previous feedback (round < 4)
            return f"""You are a teacher helping a small LLM improve its answer.

[Question]
{question}

[Target Answer]
{ground_truth}

[Student's Answer]
{student_answer}

[Previous Feedback]
{previous_feedback}

<Analysis>
1. Is the core meaning/content correct? (If yes, the problem is FORMAT/STRUCTURE, not content!)
2. What's specifically different: Length? Sentence structure? Missing words? Word order?
3. Why did previous feedback not work? Was it unclear or wrong?
4. What EXACT change will make student_answer match the target format?
</Analysis>

IMPORTANT:
- If content is correct but format differs → Focus on FORMAT (e.g., "Need full sentence starting with...")
- If content is wrong → Focus on CONTENT (e.g., "Wrong algorithm, should be X")
- Be SPECIFIC about what to add/remove/change

Return ONLY:
"Error: [what's wrong]. Fix: [specific action]. Format: [exact template with [placeholders]]"

Example formats:
- "Error: Missing sentence structure. Fix: Wrap in full sentence. Format: 'The appropriate [X] algorithm for this problem is [Y].'"
- "Error: Wrong algorithm. Fix: Use classification not regression. Format: 'Logistic Regression'"

Feedback:"""
        else:
            # First-time feedback
            return f"""You are a teacher helping a small LLM answer a question correctly.

[Question]
{question}

[Target Answer]
{ground_truth}

[Student's Answer]
{student_answer}

<Analysis>
1. Is the core meaning/content correct?
   - If YES → Problem is FORMAT/STRUCTURE only (length, sentence form, word order)
   - If NO → Problem is CONTENT (wrong facts, wrong concept)
2. What EXACTLY differs between student's answer and target?
   - Missing words? Different structure? Too short/long? Wrong order?
3. What ONE specific change will fix it?
3. What knowledge/format is required?
4. What ONE specific change will fix it?
</Analysis>

IMPORTANT:
- If content is correct but format differs → Guide FORMAT (e.g., "Expand to full sentence: 'The [X] is [Y]'")
- If content is wrong → Guide CONTENT (e.g., "Use [X] instead of [Y]")
- Be SPECIFIC with exact templates

Return ONLY:
"Error: [what's wrong]. Fix: [specific action]. Format: [exact template with [placeholders]]"

Examples:
- "Error: Too short. Fix: Add prefix. Format: 'The appropriate [type] algorithm for this problem is [name].'"
- "Error: Wrong algorithm. Fix: Use classification. Format: 'Logistic Regression'"

Keep under 200 chars.

Feedback:"""
    
    def _build_direct_feedback_prompt(self,
                                     question: str,
                                     student_answer: str,
                                     ground_truth: str) -> str:
        """Build direct feedback prompt (no CoT)."""
        return f"""Generate concise feedback to help the student improve.

Question: {question}
Correct answer: {ground_truth}
Student's answer: {student_answer}

Provide brief, actionable guidance (<100 characters):"""
    
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


# Example usage and testing
if __name__ == "__main__":
    import json
    
    # Mock config
    config = {
        'model': 'gemini-2.0-flash-lite',
        'temperature': 0.1,
        'max_tokens': 256,
        'pass_threshold': 0.8,
        'metrics': {
            'weights': {
                'exact_match': 0.3,
                'f1': 0.3,
                'bleu': 0.2,
                'teacher_score': 0.2
            }
        },
        'feedback': {
            'max_length': 100,
            'use_cot': True,
            'avoid_examples': False
        }
    }
    
    print("="*80)
    print("Testing Teacher Evaluator")
    print("="*80)
    
    teacher = TeacherEvaluator(config)
    
    # Test case 1: Correct answer
    print("\n--- Test 1: Correct Answer ---")
    result = teacher.evaluate(
        question="What is the capital of France?",
        student_answer="Paris",
        ground_truth="Paris"
    )
    print(f"Scores: {json.dumps(result['scores'], indent=2)}")
    print(f"Final Score: {result['final_score']:.3f}")
    print(f"Passed: {result['passed']}")
    
    # Test case 2: Incorrect answer
    print("\n--- Test 2: Incorrect Answer ---")
    result = teacher.evaluate(
        question="What is the capital of France?",
        student_answer="London",
        ground_truth="Paris"
    )
    print(f"Scores: {json.dumps(result['scores'], indent=2)}")
    print(f"Final Score: {result['final_score']:.3f}")
    print(f"Passed: {result['passed']}")
    
    # Test case 3: Generate feedback
    print("\n--- Test 3: Generate Feedback ---")
    feedback = teacher.generate_feedback(
        question="Separate words: helloworld",
        student_answer="hello world",
        ground_truth="hello + world",
        previous_feedback=None
    )
    print(f"Feedback: {feedback}")
