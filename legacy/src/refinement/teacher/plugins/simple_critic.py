"""
Simple Teacher Critic (Default Prompt-based Evaluation)

This module provides a simple prompt-based critic that uses teacher prompts
from src/prompts/teacher.py for evaluation.

Purpose:
- Provides DEFAULT evaluation when COT is disabled
- Uses structured prompts (XML-based) for clear output parsing
- Simpler than HybridCritic (no rule-based component, no score calibration)

When to use:
- When use_cot_teacher=False (default evaluation)
- For backward compatibility with existing prompts
- When HybridCritic's complexity is not needed

Architecture:
- Uses teacher prompts from src/prompts/teacher.py
- LLM generates XML-formatted feedback
- Parses XML to extract evaluation, reasoning, hint
- Returns CriticResult with binary correct/incorrect judgment
"""

from dataclasses import dataclass
from typing import Optional
import re

from src.core.client import LLMClient
from src.core.logger import get_logger
from src.providers.factory import build_client
from src.prompts.teacher import build_teacher_prompt
from ...settings import SETTINGS

logger = get_logger("critic.model")


@dataclass
class CriticResult:
    """
    Result from teacher's evaluation of student answer.
    
    Attributes:
        evaluation: Binary judgment - "correct" or "incorrect"
        reasoning: Teacher's reasoning (chain-of-thought)
        hint: Helpful hint for the student (should not reveal answer)
        raw_text: Full raw response from the teacher model
        error: Error message if parsing failed
    """
    evaluation: str  # "correct" or "incorrect"
    reasoning: str
    hint: str
    raw_text: str
    error: Optional[str] = None
    
    def is_correct(self) -> bool:
        """Check if evaluation is 'correct'."""
        return self.evaluation.lower() == "correct"
    
    def is_incorrect(self) -> bool:
        """Check if evaluation is 'incorrect'."""
        return self.evaluation.lower() == "incorrect"


class TeacherCritic:
    """
    Teacher model that evaluates student answers and provides feedback.
    
    The teacher uses an LLM (configured via provider) to:
    1. Evaluate whether a student's answer is correct or incorrect
    2. Provide reasoning using chain-of-thought
    3. Generate helpful hints that guide without revealing answers
    
    Example:
        >>> teacher = TeacherCritic(provider="gemini", model_name="gemini-2.0-flash-lite")
        >>> result = teacher.evaluate(
        ...     question="What is the capital of France?",
        ...     student_answer="London"
        ... )
        >>> print(result.evaluation)  # "incorrect"
        >>> print(result.hint)  # "Think about the capital city on the Seine river"
    """
    
    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        rpm: Optional[int] = None,
        tpm: Optional[int] = None,
        rpd: Optional[int] = None
    ):
        """
        Initialize the teacher critic.
        
        Args:
            provider: LLM provider name (required)
            model_name: Specific model to use for evaluation (required)
            temperature: Sampling temperature (defaults to SETTINGS.evaluator)
            max_tokens: Maximum tokens in teacher's response (defaults to SETTINGS.evaluator)
            rpm: DEPRECATED - rate limits auto-loaded from constants.py
            tpm: DEPRECATED - rate limits auto-loaded from constants.py
            rpd: DEPRECATED - rate limits auto-loaded from constants.py
        """
        # Provider and model must be passed in (no defaults from old config files)
        if not provider:
            raise ValueError("provider is required for TeacherCritic")
        if not model_name:
            raise ValueError("model_name is required for TeacherCritic")
        
        self.provider = provider
        self.model_name = model_name
        self.temperature = temperature if temperature is not None else SETTINGS.evaluator.temperature
        self.max_tokens = max_tokens if max_tokens is not None else SETTINGS.evaluator.max_tokens
        
        # Create the LLM client (rate limits auto-loaded from constants.py)
        try:
            self.client: LLMClient = build_client(self.provider, model=self.model_name)
            logger.info(f"TeacherCritic initialized with {provider}/{self.model_name} (rate limits from constants.py)")
        except Exception as e:
            logger.error(f"Failed to initialize teacher client: {e}")
            raise
    
    def evaluate(
        self,
        question: str,
        student_answer: str,
        correct_answer: str = ""
    ) -> CriticResult:
        """
        Evaluate a student's answer and provide feedback.
        
        This method:
        1. Builds a prompt for the teacher using build_teacher_prompt()
        2. Calls the LLM client to get evaluation
        3. Parses the response using regex to extract structured output
        4. Returns a CriticResult with evaluation, reasoning, and hint
        
        Args:
            question: The original question
            student_answer: The student's answer to evaluate
            correct_answer: Optional correct answer for reference
        
        Returns:
            CriticResult: Structured evaluation result
        
        Parsing Strategy:
            We use regex to extract content between XML-like tags:
            - <EVALUATION>...</EVALUATION> for the judgment
            - <REASONING>...</REASONING> for the explanation
            - <HINT>...</HINT> for the guidance
            
            If any tag is missing, we provide default values and log a warning.
            The raw_text is always preserved for debugging.
        
        Error Handling:
            - If LLM call fails: Returns CriticResult with error message
            - If parsing fails: Returns partial result with what was extracted
            - Missing tags: Uses sensible defaults and logs warning
        """
        try:
            # Build the teacher prompt
            prompt = build_teacher_prompt(
                question=question,
                student_answer=student_answer,
                correct_answer=correct_answer
            )
            
            # Call the teacher model
            logger.debug(f"Evaluating student answer for question: {question[:50]}...")
            
            response = self.client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Check for errors in response
            if response.error:
                logger.error(f"Teacher model error: {response.error}")
                
                # Propagate rate limit errors clearly for upper layer handling
                if response.error == "rate_limit":
                    return CriticResult(
                        evaluation="unknown",
                        reasoning="",
                        hint="",
                        raw_text="",
                        error="RATE_LIMIT"
                    )
                
                return CriticResult(
                    evaluation="unknown",
                    reasoning="",
                    hint="",
                    raw_text=response.text or "",
                    error=f"LLM error: {response.error}"
                )
            
            # Parse the response
            raw_text = response.text or ""
            
            if not raw_text.strip():
                logger.warning("Teacher returned empty response")
                return CriticResult(
                    evaluation="unknown",
                    reasoning="",
                    hint="",
                    raw_text="",
                    error="Empty response from teacher"
                )
            
            # Extract structured fields using regex
            evaluation = self._extract_tag(raw_text, "EVALUATION")
            reasoning = self._extract_tag(raw_text, "REASONING")
            hint = self._extract_tag(raw_text, "HINT")
            
            # Validate and normalize evaluation
            evaluation = evaluation.lower().strip()
            if evaluation not in ["correct", "incorrect"]:
                logger.warning(f"Invalid evaluation value: {evaluation}")
                # Try to infer from content
                if "correct" in evaluation or "yes" in evaluation:
                    evaluation = "correct"
                elif "incorrect" in evaluation or "no" in evaluation or "wrong" in evaluation:
                    evaluation = "incorrect"
                else:
                    evaluation = "unknown"
            
            # Check if any required field is missing
            error_msg = None
            if not reasoning:
                logger.warning("Missing <REASONING> tag in teacher response")
                error_msg = "Missing reasoning"
            if not hint:
                logger.warning("Missing <HINT> tag in teacher response")
                error_msg = error_msg + ", missing hint" if error_msg else "Missing hint"
            
            logger.info(f"Evaluation complete: {evaluation}")
            
            return CriticResult(
                evaluation=evaluation,
                reasoning=reasoning or "No reasoning provided",
                hint=hint or "No hint available",
                raw_text=raw_text,
                error=error_msg
            )
            
        except Exception as e:
            logger.error(f"Evaluation failed: {e}", exc_info=True)
            return CriticResult(
                evaluation="error",
                reasoning="",
                hint="",
                raw_text="",
                error=str(e)
            )
    
    def _extract_tag(self, text: str, tag_name: str) -> str:
        """
        Extract content between XML-like tags using regex.
        
        This method uses regex to find content between opening and closing tags.
        It handles multi-line content and is case-insensitive.
        
        Args:
            text: The text to search in
            tag_name: The tag name (without angle brackets)
        
        Returns:
            str: The content between tags, or empty string if not found
        
        Regex Pattern Explanation:
            - <TAG_NAME>      : Opening tag (case-insensitive)
            - (.*?)           : Non-greedy capture group (content)
            - </TAG_NAME>     : Closing tag (case-insensitive)
            - re.DOTALL       : Make . match newlines too
            - re.IGNORECASE   : Case-insensitive matching
        
        Handling Missing Tags:
            If the tag is not found, we return an empty string and let the
            caller decide how to handle it. This allows graceful degradation
            when the LLM doesn't follow the exact format.
        
        Future Improvements:
            - Support for nested tags
            - Handle malformed XML (e.g., unclosed tags)
            - Extract multiple occurrences if needed
        """
        # Build the regex pattern
        # Pattern: <TAG>(.*?)</TAG> with DOTALL and IGNORECASE flags
        pattern = rf"<{tag_name}>(.*?)</{tag_name}>"
        
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if match:
            # Return the captured group (content between tags)
            content = match.group(1).strip()
            return content
        
        # Tag not found
        return ""
    
    def batch_evaluate(
        self,
        questions: list[str],
        student_answers: list[str],
        correct_answers: Optional[list[str]] = None
    ) -> list[CriticResult]:
        """
        Evaluate multiple student answers in sequence.
        
        Note: This is a simple sequential implementation. For production,
        consider implementing parallel processing or batching.
        
        Args:
            questions: List of questions
            student_answers: List of student answers
            correct_answers: Optional list of correct answers
        
        Returns:
            list[CriticResult]: List of evaluation results
        """
        if len(questions) != len(student_answers):
            raise ValueError("Number of questions and answers must match")
        
        if correct_answers and len(correct_answers) != len(questions):
            raise ValueError("Number of correct answers must match questions")
        
        results = []
        for i, (q, sa) in enumerate(zip(questions, student_answers)):
            ca = correct_answers[i] if correct_answers else ""
            result = self.evaluate(q, sa, ca)
            results.append(result)
        
        return results
