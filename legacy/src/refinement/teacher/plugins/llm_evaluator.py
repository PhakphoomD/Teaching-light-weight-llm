"""
LLM Reviewer

LLM-based critic that returns JSON-formatted feedback.
Replaces XML-based TeacherCritic with strict JSON schema.

Features:
- JSON-only output (no prose, no XML)
- Clean-parse: strips noise before/after JSON
- Safe fallback: handles timeout, malformed JSON, missing keys
- Reproducible: uses seed for deterministic evaluation

Usage:
    >>> reviewer = LLMReviewer(provider="gemini")
    >>> feedback = reviewer.evaluate(question, answer)
    >>> print(feedback.scores["overall"])  # 0.0-1.0
"""

from typing import Optional, Dict, Any, List
import json
import re
import logging
from datetime import datetime

# Import dependencies using absolute imports
from src.core.client import LLMClient
from src.providers.factory import build_client
from .schemas import CriticFeedback, validate_feedback, create_default_feedback
from ...settings import SETTINGS

logger = logging.getLogger("critic.llm_reviewer")


class LLMReviewer:
    """
    LLM-based reviewer that returns structured JSON feedback.
    
    This replaces the old XML-based TeacherCritic with:
    - Strict JSON schema output
    - Robust parsing with fallbacks
    - CriticFeedback standardized format
    
    Example:
        >>> reviewer = LLMReviewer(provider="gemini")
        >>> feedback = reviewer.evaluate(
        ...     question="What is the capital of France?",
        ...     answer="London"
        ... )
        >>> print(feedback.scores["overall"])  # Low score
        >>> print(feedback.issues)  # ["Wrong answer"]
    """
    
    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        seed: Optional[int] = None,
        timeout: float = 30.0
    ):
        """
        Initialize LLM reviewer.
        
        Rate limits (rpm/tpm/rpd) are now automatically loaded from 
        src/providers/constants.py based on the model name.
        No need to pass them manually.
        
        Args:
            provider: LLM provider (required, passed from HybridCritic)
            model_name: Specific model (required, passed from HybridCritic)
            temperature: Sampling temperature (defaults to SETTINGS.evaluator)
            max_tokens: Max tokens in response (defaults to SETTINGS.evaluator)
            seed: Random seed for reproducibility (if supported by provider)
            timeout: Timeout in seconds for LLM call
        """
        # Provider and model must be passed in (from HybridCritic)
        if not provider:
            raise ValueError("provider is required for LLMReviewer")
        if not model_name:
            raise ValueError("model_name is required for LLMReviewer")
        
        self.provider = provider
        self.model_name = model_name
        self.temperature = temperature if temperature is not None else SETTINGS.evaluator.temperature
        self.max_tokens = max_tokens if max_tokens is not None else SETTINGS.evaluator.max_tokens
        self.seed = seed
        self.timeout = timeout
        
        # Build client (rate limits auto-loaded from constants.py)
        try:
            self.client: LLMClient = build_client(
                self.provider, 
                model=self.model_name
                # rpm/tpm/rpd removed - automatically loaded from constants.py
            )
            logger.info(f"LLMReviewer initialized: {self.provider}/{self.model_name} (rate limits from constants.py)")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise
    
    def evaluate(
        self,
        question: str,
        answer: str,
        ground_truth: Optional[str] = None,
        use_cot: bool = False,
        error_keys: Optional[List[str]] = None
    ) -> CriticFeedback:
        """
        Evaluate answer using LLM and return structured feedback.
        
        This method:
        1. Builds JSON-strict prompt (with optional COT and error_keys hints)
        2. Calls LLM with timeout
        3. Cleans and parses JSON
        4. Validates with CriticFeedback schema
        5. Falls back gracefully on any error
        
        Args:
            question: The question text
            answer: Student's answer
            ground_truth: Correct answer (optional, for reference)
            use_cot: Whether to use chain-of-thought reasoning
            error_keys: Rule-based error categories to use as hints (optional)
        
        Returns:
            CriticFeedback: Always returns valid feedback (never None/crashes)
        
        Fallback Chain:
            LLM call -> JSON parse -> Validate schema -> Default feedback
        """
        try:
            # Build prompt (use enhanced version with hints if error_keys provided)
            if error_keys:
                prompt = self._build_evaluation_prompt_with_hints(
                    question, answer, ground_truth, error_keys, use_cot=use_cot
                )
            else:
                # Legacy prompt for backward compatibility
                prompt = self._build_json_prompt(question, answer, ground_truth, use_cot=use_cot)
            
            # Call LLM
            logger.debug(f"Calling LLM: {self.provider}/{self.model_name}")
            start_time = datetime.now()
            
            response = self.client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.debug(f"LLM response received in {elapsed:.2f}s")
            
            # Check for errors in response
            if hasattr(response, 'error') and response.error:
                error_msg = str(response.error).lower()
                if any(keyword in error_msg for keyword in ['rate_limit', 'rate limit', 'quota', '429', 'resource_exhausted']):
                    logger.error(f"LLM rate limit exceeded: {response.error}")
                    raise RuntimeError(f"Rate limit exceeded: {response.error}")
                else:
                    logger.error(f"LLM error: {response.error}")
                    raise RuntimeError(f"LLM error: {response.error}")
            
            # Extract text
            raw_text = response.text if hasattr(response, 'text') else str(response)
            
            # Clean and parse JSON
            feedback_dict = self._clean_and_parse_json(raw_text)
            
            # Add metadata
            feedback_dict["metadata"] = {
                "source": "LLMReviewer",
                "provider": self.provider,
                "model": self.model_name,
                "temperature": self.temperature,
                "elapsed_seconds": elapsed,
                "raw_text": raw_text[:500]  # Truncate for storage
            }
            
            # Validate and return
            feedback = validate_feedback(feedback_dict)
            
            # IMPORTANT: Add "llm" score = "overall" for HybridCritic to detect LLM availability
            if "llm" not in feedback.scores:
                feedback.scores["llm"] = feedback.scores.get("overall", 0.0)
            
            logger.debug(f"LLM feedback: overall={feedback.scores.get('overall', 0.0):.2f}, llm={feedback.scores.get('llm', 0.0):.2f}")
            
            return feedback
            
        except Exception as e:
            # Check error message for rate limit/quota issues
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['rate_limit', 'rate limit', 'quota', '429', 'resource_exhausted']):
                logger.error(f"LLM rate limit exceeded: {e}")
                raise RuntimeError(f"Rate limit exceeded") from e
            
            # For other errors, also raise to trigger HybridCritic fallback
            logger.warning(f"LLM evaluation failed: {e}")
            raise
    
    def _build_json_prompt(
        self,
        question: str,
        answer: str,
        ground_truth: Optional[str] = None,
        use_cot: bool = False
    ) -> str:
        """
        Build prompt that demands JSON output only.
        
        Key requirements:
        - NO prose before/after JSON
        - Strict schema adherence
        - Clear field descriptions
        - Optional Chain-of-Thought reasoning
        
        Args:
            question: Question text
            answer: Student's answer
            ground_truth: Correct answer (optional)
            use_cot: Whether to include chain-of-thought instruction
        
        Returns:
            str: Prompt string
        """
        gt_section = ""
        if ground_truth:
            gt_section = f"\nCorrect Answer (reference): {ground_truth}\n"
        
        cot_instruction = ""
        if use_cot:
            cot_instruction = """
Before generating the JSON, think step-by-step:
1. What does the question ask for?
2. What did the student provide?
3. What is missing or incorrect?
4. What would make the answer better?

"""
        
        prompt = f"""You are an expert teacher evaluating a student's answer.

Question: {question}
Student's Answer: {answer}{gt_section}
{cot_instruction}
CRITICAL: Respond with ONLY valid JSON (no prose, no explanation outside JSON).

Required JSON schema:
{{
  "issues": ["List of specific problems found (e.g., 'Answer too brief', 'Wrong capital city')"],
  "fixes": ["List of actionable suggestions (e.g., 'Add 2-3 sentences', 'Review European geography')"],
  "lesson": "Key learning point in 1-3 sentences (e.g., 'Paris is the capital of France, located on the Seine river')",
  "error_keys": ["Category tags (e.g., 'factual', 'incomplete', 'grammar')"],
  "scores": {{
    "overall": 0.75,
    "factual": 0.5,
    "grammar": 0.9
  }}
}}

Scoring guidelines:
- overall: 0.0 (completely wrong) to 1.0 (perfect)
- Use sub-scores (factual, grammar, completeness, etc.) as needed
- Be objective and precise

Output ONLY the JSON (no text before or after):"""
        
        return prompt
    
    def _build_evaluation_prompt_with_hints(
        self,
        question: str,
        answer: str,
        ground_truth: Optional[str] = None,
        error_keys: Optional[List[str]] = None,
        use_cot: bool = False
    ) -> str:
        """
        Build enhanced prompt using error_keys as contextual hints.
        
        This replaces generic templates with specific, context-aware feedback.
        The LLM uses error_keys (from rule checker) as hints about what to focus on,
        then generates natural, contextual feedback.
        
        CRITICAL SAFETY:
        - Must NOT reveal the actual answer
        - Must NOT give away direct solutions
        - Must guide thinking, not provide answers
        
        Args:
            question: Question text
            answer: Student's answer
            ground_truth: Correct answer (for reference, not to be leaked)
            error_keys: List of error categories detected by rule checker
            use_cot: Whether to use chain-of-thought reasoning
        
        Returns:
            str: Enhanced prompt with hints and safety instructions
        """
        gt_section = ""
        if ground_truth:
            gt_section = f"\nCorrect Answer (reference): {ground_truth}\n"
        
        hints_section = ""
        if error_keys:
            hints_list = "\n".join([f"  - {key}" for key in error_keys])
            hints_section = f"""
Detected Issues (use as hints for your evaluation):
{hints_list}

Your task:
- Focus on these detected issues
- Provide specific, actionable feedback
- Generate natural guidance (not templates)
- Help student improve without revealing answers
"""
        
        cot_instruction = ""
        if use_cot:
            cot_instruction = """
Before generating the JSON, think step-by-step:
1. What does the question ask for?
2. What did the student provide?
3. Based on detected issues, what specific problems exist?
4. What concrete steps would help the student improve?

"""
        
        safety_instructions = """
CRITICAL SAFETY RULES:
1. NEVER directly state the correct answer
2. NEVER give hints that reveal the answer (first letter, length, patterns)
3. Guide thinking process, not solutions
4. Use phrases like "Consider...", "Think about...", "Research..."
5. If tempted to reveal answer, provide a learning resource instead

"""
        
        prompt = f"""You are an expert teacher evaluating a student's answer.

Question: {question}
Student's Answer: {answer}{gt_section}
{hints_section}
{safety_instructions}
{cot_instruction}
CRITICAL: Respond with ONLY valid JSON (no prose, no explanation outside JSON).

Required JSON schema:
{{
  "issues": ["List of specific problems found (e.g., 'Answer too brief', 'Missing key concept: photosynthesis')"],
  "fixes": ["List of actionable suggestions (e.g., 'Research how plants produce energy', 'Explain the role of chlorophyll')"],
  "lesson": "Key learning point in 1-3 sentences (e.g., 'Plants create their own food through photosynthesis, using sunlight, water, and carbon dioxide')"],
  "error_keys": ["Category tags matching detected issues (e.g., 'incomplete', 'missing_concept')"],
  "scores": {{
    "overall": 0.75,
    "factual": 0.5,
    "completeness": 0.6
  }}
}}

Scoring guidelines:
- overall: 0.0 (completely wrong) to 1.0 (perfect)
- Use sub-scores based on error_keys (e.g., factual, grammar, completeness)
- Be objective and constructive

Output ONLY the JSON (no text before or after):"""
        
        return prompt
    
    def _clean_and_parse_json(self, raw_text: str) -> Dict[str, Any]:
        """
        Clean noise from LLM output and parse JSON.
        
        Common issues:
        - Prose before/after JSON block
        - Markdown code fences (```json ... ```)
        - Extra whitespace
        - Trailing commas
        
        Strategy:
        1. Find first { and last }
        2. Extract substring
        3. Try parsing
        4. If fails, try additional cleaning
        5. If still fails, return minimal valid dict
        
        Args:
            raw_text: Raw LLM output
        
        Returns:
            dict: Parsed JSON or minimal fallback
        """
        # Remove markdown code fences
        text = re.sub(r'```json\s*', '', raw_text)
        text = re.sub(r'```\s*', '', text)
        
        # Find JSON boundaries
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        
        if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
            logger.warning("No valid JSON boundaries found")
            return {"issues": ["JSON parsing failed"], "scores": {"overall": 0.0}}
        
        # Extract JSON substring
        json_str = text[first_brace:last_brace + 1]
        
        # Try parsing
        try:
            parsed = json.loads(json_str)
            logger.debug("JSON parsed successfully")
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}")
            
            # Try fixing common issues
            # 1. Remove trailing commas
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            try:
                parsed = json.loads(json_str)
                logger.debug("JSON parsed after cleanup")
                return parsed
            except json.JSONDecodeError:
                logger.error("JSON parsing failed after cleanup")
                return {
                    "issues": ["JSON parsing failed"],
                    "fixes": [],
                    "lesson": "Could not parse LLM response",
                    "error_keys": ["parse_error"],
                    "scores": {"overall": 0.0}
                }


def create_reviewer_from_config(config: Dict[str, Any]) -> LLMReviewer:
    """
    Create LLMReviewer from config dictionary.
    
    Expected config keys:
        provider: str (e.g., "gemini")
        model_name: str (optional)
        temperature: float (default 0.2)
        max_tokens: int (default 1024)
        seed: int (optional)
        timeout: float (default 30.0)
    
    Args:
        config: Configuration dictionary
    
    Returns:
        LLMReviewer: Configured reviewer instance
    
    Example:
        >>> config = {"provider": "gemini", "temperature": 0.1}
        >>> reviewer = create_reviewer_from_config(config)
    """
    return LLMReviewer(
        provider=config.get("provider", "gemini"),
        model_name=config.get("model_name"),
        temperature=config.get("temperature", 0.2),
        max_tokens=config.get("max_tokens", 1024),
        seed=config.get("seed"),
        timeout=config.get("timeout", 30.0)
    )
