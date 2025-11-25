"""
Hybrid Critic Aggregator

[STAR] PRIMARY CRITIC - Use this for all new code!

Combines rule-based and LLM-based evaluation into single score.

Architecture:
- Rule checkers: Fast, deterministic, interpretable (format, faithfulness, completeness)
- LLM reviewer: Deep understanding, context-aware evaluation
- Weighted aggregation: overall = w_rule x rule_score + w_llm x llm_score
- Sigmoid calibration: stop_score = sigmoid(a x overall + b)
- Disagreement logging: Logs to JSONL when |rule - llm| > threshold

Why HybridCritic?
[OK] Robust: Combines fast rules with deep LLM understanding
[OK] Observable: Disagreement detection reveals edge cases
[OK] Calibrated: Sigmoid maps scores to stopping criterion
[OK] Configurable: All weights from config.yaml (no hardcoding)
[OK] Tested: Full unit test coverage with mocks

This is the MAIN critic for production use.
[WARNING] Old TeacherCritic (XML-based) is kept for backward compatibility only.

Usage:
    >>> from src.critic import HybridCritic
    >>> 
    >>> # Automatic config loading
    >>> critic = HybridCritic()
    >>> 
    >>> # Or explicit parameters
    >>> critic = HybridCritic(
    ...     provider="gemini",
    ...     rule_weight=0.5,
    ...     llm_weight=0.5,
    ...     calibration_params={"a": 1.0, "b": 0.0},
    ...     disagreement_threshold=0.3,
    ...     disagreements_log="outputs/disagreements.jsonl"
    ... )
    >>> 
    >>> feedback = critic.evaluate(
    ...     question="What is 2+2?",
    ...     answer="4",
    ...     ground_truth="4"
    ... )
    >>> 
    >>> # Access results
    >>> print(feedback.stop_score)      # 0.0-1.0 (calibrated)
    >>> print(feedback.scores['overall'])  # Combined score
    >>> print(feedback.scores['rule'])     # Rule-based component
    >>> print(feedback.scores['llm'])      # LLM component
    >>> print(feedback.issues)             # List of problems found
    >>> print(feedback.lesson)             # Teaching lesson

See also:
- schemas.py: CriticFeedback dataclass definition
- rule_checkers.py: Rule-based scoring logic
- llm_reviewer.py: LLM evaluation with JSON output
"""

from typing import Optional, Dict, Any
import logging
import math
import json
from pathlib import Path
from datetime import datetime

from .rule_checkers import compute_rule_score
from .llm_evaluator import LLMReviewer
from .schemas import CriticFeedback, validate_feedback
from .hint_generator import filter_answer_leakage

logger = logging.getLogger("critic.aggregator")


def sigmoid(x: float) -> float:
    """
    Sigmoid function for score calibration.
    
    Maps (-infinity, infinity) -> (0, 1) with smooth curve.
    
    Args:
        x: Input value
    
    Returns:
        Sigmoid output in (0, 1)
    """
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        # Handle extreme values
        return 0.0 if x < 0 else 1.0


class HybridCritic:
    """
    Hybrid critic combining rule-based and LLM evaluation.
    
    This is the recommended critic for production use:
    - Fast rule checks catch obvious errors
    - LLM provides nuanced assessment
    - Weighted combination balances both
    - Calibrated stop_score for loop termination
    - Disagreement detection for debugging
    
    Parameters:
        provider: LLM provider for reviewer ("gemini", "groq", "local")
        model_name: Specific model (default from config)
        rule_weight: Weight for rule score (0.0-1.0)
        llm_weight: Weight for LLM score (0.0-1.0)
        calibration_params: Dict with "a" and "b" for sigmoid(a*x + b)
        disagreement_threshold: Log warning when |rule - llm| > this
        rule_only_fallback: If True, use rules only when LLM fails
        
    Note:
        rule_weight + llm_weight should equal 1.0 for interpretability,
        but not enforced (allows experimentation).
    
    Example:
        >>> critic = HybridCritic(
        ...     provider="gemini",
        ...     rule_weight=0.4,
        ...     llm_weight=0.6,
        ...     calibration_params={"a": 2.0, "b": -1.0},
        ...     disagreement_threshold=0.3
        ... )
        >>> feedback = critic.evaluate(
        ...     question="What is the capital of France?",
        ...     answer="Paris is the capital.",
        ...     ground_truth="Paris"
        ... )
        >>> print(f"Overall: {feedback.scores['overall']:.2f}")
        >>> print(f"Stop score: {feedback.stop_score:.2f}")
    """
    
    def __init__(
        self,
        provider: str = "gemini",
        model_name: Optional[str] = None,
        rule_weight: float = 0.5,
        llm_weight: float = 0.5,
        calibration_params: Optional[Dict[str, float]] = None,
        disagreement_threshold: float = 0.3,
        rule_only_fallback: bool = True,
        disagreements_log: Optional[str] = None,  # Path to disagreements.jsonl
        llm_reviewer_config: Optional[Dict[str, Any]] = None  # NEW: LLM reviewer config
    ):
        """
        Initialize hybrid critic with rule and LLM components.
        
        Rate limits (rpm/tpm/rpd) are now automatically loaded from 
        src/providers/constants.py based on the model name.
        
        Args:
            llm_reviewer_config: Configuration for LLM reviewer:
                - enabled: bool (enable/disable reviewer)
                - model: str (model name or "same_as_teacher")
                - use_for_borderline: bool (only use for borderline cases)
                - borderline_lower/upper: float (score thresholds)
                - temperature: float
                - max_tokens: int
        """
        self.provider = provider
        self.teacher_model = model_name
        self.rule_weight = rule_weight
        self.llm_weight = llm_weight
        self.disagreement_threshold = disagreement_threshold
        self.rule_only_fallback = rule_only_fallback
        self.disagreements_log = disagreements_log
        
        # Calibration parameters for sigmoid
        if calibration_params is None:
            calibration_params = {"a": 1.0, "b": 0.0}
        self.calib_a = calibration_params.get("a", 1.0)
        self.calib_b = calibration_params.get("b", 0.0)
        
        # LLM Reviewer Configuration
        if llm_reviewer_config is None:
            llm_reviewer_config = {"enabled": False}
        
        self.llm_enabled = llm_reviewer_config.get("enabled", False)
        self.use_borderline = llm_reviewer_config.get("use_for_borderline", True)
        self.borderline_lower = llm_reviewer_config.get("borderline_lower", 0.55)
        self.borderline_upper = llm_reviewer_config.get("borderline_upper", 0.75)
        
        # Initialize LLM Reviewer if enabled
        if self.llm_enabled:
            reviewer_model = llm_reviewer_config.get("model", "same_as_teacher")
            if reviewer_model == "same_as_teacher":
                reviewer_model = model_name
            
            reviewer_temp = llm_reviewer_config.get("temperature", 0.2)
            reviewer_max_tokens = llm_reviewer_config.get("max_tokens", 512)
            
            try:
                self.llm_reviewer = LLMReviewer(
                    provider=provider,
                    model_name=reviewer_model,
                    temperature=reviewer_temp,
                    max_tokens=reviewer_max_tokens
                )
                self.llm_available = True
                logger.info(f"✓ LLM Reviewer ENABLED: {reviewer_model}")
                if self.use_borderline:
                    logger.info(f"  Borderline mode: scores [{self.borderline_lower}, {self.borderline_upper}]")
                else:
                    logger.info(f"  Full mode: All answers reviewed by LLM")
            except Exception as e:
                logger.warning(f"✗ LLM Reviewer initialization failed: {e}")
                self.llm_reviewer = None
                self.llm_available = False
                logger.info("  Falling back to RULE-ONLY mode")
        else:
            self.llm_reviewer = None
            self.llm_available = False
            logger.info("✓ HybridCritic in RULE-ONLY mode (LLM reviewer disabled)")
        
        # Log configuration
        logger.info(f"Weights: rule={rule_weight}, llm={llm_weight}")
        logger.info(f"Calibration: stop_score = sigmoid({self.calib_a}*x + {self.calib_b})")
        logger.info(f"Disagreement threshold: {disagreement_threshold}")
    
    def evaluate(
        self,
        question: str,
        answer: str,
        ground_truth: Optional[str] = None,
        use_cot: bool = False
    ) -> CriticFeedback:
        """
        Evaluate answer using both rule-based and LLM critics.
        
        Process:
        1. Run rule checkers (always fast and deterministic)
        2. Run LLM reviewer (if available, with optional COT)
        3. Combine scores: overall = w_rule * rule + w_llm * llm
        4. Calibrate: stop_score = sigmoid(a * overall + b)
        5. Detect disagreement: log if |rule - llm| > threshold
        6. Merge feedback: combine issues/fixes/lesson
        
        Args:
            question: The question text
            answer: Student's answer
            ground_truth: Correct answer (optional, improves rule checks)
            use_cot: Whether to use chain-of-thought in LLM evaluation
        
        Returns:
            CriticFeedback with:
                - scores["rule"]: Rule-based score
                - scores["llm"]: LLM score (if available)
                - scores["overall"]: Weighted combination
                - stop_score: Calibrated score for stopping
                - issues: Combined issues from both
                - fixes: Combined fixes from both
                - lesson: LLM lesson (or rule-based summary)
        
        Fallback behavior:
            - If LLM fails: use rule score only (if rule_only_fallback=True)
            - If rule fails: use default scores (0.0)
        """
        # Step 1: Run rule checkers
        try:
            rule_score, rule_error_keys = compute_rule_score(
                question=question,
                answer=answer,
                ground_truth=ground_truth
            )
            logger.debug(f"Rule score: {rule_score:.3f}, errors: {rule_error_keys}")
        except Exception as e:
            logger.error(f"Rule checker failed: {e}", exc_info=True)
            rule_score = 0.0
            rule_error_keys = ["rule_checker_error"]
        
        # Step 2: Run LLM reviewer (if available, with borderline logic)
        llm_feedback = None
        llm_score = None
        should_use_llm = False
        
        if self.llm_available and self.llm_reviewer is not None:
            # Borderline mode: only use LLM for scores in [lower, upper]
            if self.use_borderline:
                if self.borderline_lower <= rule_score <= self.borderline_upper:
                    should_use_llm = True
                    logger.debug(f"Borderline score {rule_score:.3f} → Using LLM reviewer")
                else:
                    should_use_llm = False
                    logger.debug(f"Clear score {rule_score:.3f} → Skip LLM (rule-only)")
            else:
                # Full mode: always use LLM
                should_use_llm = True
                logger.debug(f"Full mode → Using LLM reviewer")
            
            if should_use_llm:
                try:
                    llm_feedback = self.llm_reviewer.evaluate(
                        question=question,
                        answer=answer,
                        ground_truth=ground_truth,
                        use_cot=use_cot,  # Pass COT flag
                        error_keys=rule_error_keys  # Pass error_keys as hints
                    )
                    llm_score = llm_feedback.scores.get("overall", 0.0)
                    logger.debug(f"LLM score: {llm_score:.3f} (COT={use_cot}, hints={len(rule_error_keys)})")
                except Exception as e:
                    logger.warning(f"LLM reviewer failed: {e}")
                    llm_score = None
        
        # Step 3: Combine scores
        if llm_score is not None:
            # Both available: weighted combination
            overall_score = (self.rule_weight * rule_score + 
                           self.llm_weight * llm_score)
            
            # Detect disagreement
            disagreement = abs(rule_score - llm_score)
            if disagreement > self.disagreement_threshold:
                logger.warning(
                    f"Disagreement detected! rule={rule_score:.3f}, "
                    f"llm={llm_score:.3f}, diff={disagreement:.3f}"
                )
                
                # Log disagreement to file if configured
                if self.disagreements_log:
                    self._log_disagreement(
                        question=question,
                        answer=answer,
                        rule_score=rule_score,
                        llm_score=llm_score,
                        disagreement=disagreement
                    )
        else:
            # LLM unavailable
            if self.rule_only_fallback:
                overall_score = rule_score
                logger.debug("Using rule-only score (LLM unavailable)")
            else:
                overall_score = 0.0
                logger.warning("LLM unavailable and fallback disabled, using 0.0")
        
        # Clamp to [0, 1]
        overall_score = max(0.0, min(1.0, overall_score))
        
        # Step 4: Calibrate stop_score with sigmoid
        stop_score_raw = self.calib_a * overall_score + self.calib_b
        stop_score = sigmoid(stop_score_raw)
        
        logger.debug(
            f"Scores: rule={rule_score:.3f}, llm={llm_score}, "
            f"overall={overall_score:.3f}, stop={stop_score:.3f}"
        )
        
        # Step 5: Merge feedback
        feedback = self._merge_feedback(
            rule_score=rule_score,
            rule_error_keys=rule_error_keys,
            llm_feedback=llm_feedback,
            overall_score=overall_score,
            stop_score=stop_score,
            ground_truth=ground_truth
        )
        
        # Step 6: Log evaluation metrics
        self._log_evaluation_metrics(
            question=question,
            answer=answer,
            rule_score=rule_score,
            rule_error_keys=rule_error_keys,
            llm_score=llm_score,
            overall_score=overall_score,
            stop_score=stop_score,
            used_llm=(llm_score is not None)
        )
        
        return feedback
    
    def _merge_feedback(
        self,
        rule_score: float,
        rule_error_keys: list,
        llm_feedback: Optional[CriticFeedback],
        overall_score: float,
        stop_score: float,
        ground_truth: Optional[str] = None
    ) -> CriticFeedback:
        """
        Merge rule-based and LLM feedback into single CriticFeedback.
        
        Strategy:
        - issues: Combine rule error_keys + LLM issues (deduplicate)
        - fixes: Take from LLM if available, else generate from rules (with leakage filtering)
        - lesson: Take from LLM if available, else generic (with leakage filtering)
        - scores: Include rule, llm (if available), overall
        - stop_score: From calibration
        
        Args:
            rule_score: Score from rule checkers
            rule_error_keys: Error keys from rule checkers
            llm_feedback: Feedback from LLM (None if unavailable)
            overall_score: Combined score
            stop_score: Calibrated stopping score
            ground_truth: Correct answer (used for leakage detection)
        
        Returns:
            Merged CriticFeedback
        """
        # Start with rule error keys as issues
        issues = [self._humanize_error_key(key) for key in rule_error_keys]
        fixes = []
        lesson = ""
        error_keys = list(rule_error_keys)  # Copy
        
        # Merge LLM feedback if available
        if llm_feedback is not None:
            # Add LLM issues (avoid duplicates)
            for issue in llm_feedback.issues:
                if issue not in issues:
                    issues.append(issue)
            
            # Use LLM fixes (with leakage filtering if ground_truth available)
            if ground_truth:
                filtered_fixes = []
                for fix in llm_feedback.fixes:
                    safe_fix, was_filtered = filter_answer_leakage(
                        hint=fix,
                        known_answer=ground_truth,
                        sensitive_words=[]  # Use default sensitive words
                    )
                    if was_filtered:
                        logger.warning(f"Filtered potential leakage in fix: {fix[:50]}...")
                    filtered_fixes.append(safe_fix)
                fixes = filtered_fixes
            else:
                fixes = llm_feedback.fixes
            
            # Use LLM lesson (with leakage filtering if ground_truth available)
            if ground_truth:
                lesson, was_filtered = filter_answer_leakage(
                    hint=llm_feedback.lesson,
                    known_answer=ground_truth,
                    sensitive_words=[]
                )
                if was_filtered:
                    logger.warning(f"Filtered potential leakage in lesson: {llm_feedback.lesson[:50]}...")
            else:
                lesson = llm_feedback.lesson
            
            # Merge error keys
            for key in llm_feedback.error_keys:
                if key not in error_keys:
                    error_keys.append(key)
        else:
            # No LLM available: convert error_keys to readable hints
            if rule_error_keys:
                # Convert technical error_keys to friendly messages
                readable_hints = []
                for key in rule_error_keys:
                    if key == "wrong_answer":
                        readable_hints.append("Your answer is incorrect. Please reconsider the question.")
                    elif key == "no_punctuation":
                        readable_hints.append("Add proper punctuation at the end of your answer.")
                    elif key == "too_brief":
                        readable_hints.append("Your answer is too short. Provide more detail.")
                    elif key == "incomplete":
                        readable_hints.append("Your answer is incomplete. Make sure you fully address the question.")
                    elif key == "empty":
                        readable_hints.append("You didn't provide an answer. Please answer the question.")
                    elif key == "partial_match":
                        readable_hints.append("Your answer is partially correct. Review what's missing or incorrect.")
                    elif key == "low_overlap":
                        readable_hints.append("Your answer doesn't match the expected content well. Review the key concepts.")
                    else:
                        # For unknown keys, use a generic message
                        readable_hints.append(f"Review your answer regarding: {key.replace('_', ' ')}")
                
                fixes = readable_hints
                lesson = "Your answer needs improvement. Please address the feedback above."
            else:
                fixes = ["Review and improve your answer"]
                lesson = "Your answer needs revision"
            logger.warning(f"LLM unavailable, using error_keys as readable hints: {rule_error_keys}")
        
        # Build scores dict
        scores = {
            "rule": rule_score,
            "overall": overall_score
        }
        if llm_feedback is not None:
            scores["llm"] = llm_feedback.scores.get("overall", 0.0)
        
        # Create feedback
        feedback = CriticFeedback(
            issues=issues,
            fixes=fixes,
            lesson=lesson,
            error_keys=error_keys,
            scores=scores,
            stop_score=stop_score,
            metadata={
                "hybrid_mode": llm_feedback is not None,
                "rule_weight": self.rule_weight,
                "llm_weight": self.llm_weight,
                "calibration": {"a": self.calib_a, "b": self.calib_b}
            }
        )
        
        return feedback
    
    def _humanize_error_key(self, key: str) -> str:
        """
        Convert error key to human-readable issue.
        
        Args:
            key: Error key like "too_short", "no_punctuation"
        
        Returns:
            Human-readable issue string
        """
        humanized = {
            "too_short": "Answer is too brief",
            "no_punctuation": "Missing punctuation",
            "no_capitalization": "Missing capitalization",
            "empty_answer": "Empty answer",
            "mismatch_ground_truth": "Does not match expected answer",
            "partial_match": "Partially correct answer",
            "incomplete_coverage": "Does not address all parts of question",
            "missing_keywords": "Missing important keywords"
        }
        return humanized.get(key, key.replace("_", " ").capitalize())
    
    def _generate_rule_fixes(self, error_keys: list) -> list:
        """
        Generate actionable fixes from rule error keys.
        These give guidance on HOW to improve without revealing the answer.
        
        Args:
            error_keys: List of error keys from rule checkers
        
        Returns:
            List of actionable fix suggestions
        """
        fixes = []
        
        if "too_short" or "too_brief" in error_keys:
            fixes.append("Expand your answer with more detail (write 2-3 complete sentences)")
        
        if "no_punctuation" in error_keys:
            fixes.append("End your answer with proper punctuation (period, question mark, etc.)")
        
        if "no_capitalization" in error_keys:
            fixes.append("Start your answer with a capital letter")
        
        if "incomplete" in error_keys:
            fixes.append("Make sure your answer addresses the full question, not just part of it")
        
        if "wrong_answer" in error_keys:
            fixes.append("Reconsider your answer - it doesn't match what's expected. Review the question carefully")
        
        if "low_overlap" in error_keys:
            fixes.append("Include more relevant keywords and concepts from the question in your answer")
        
        if "partial_match" in error_keys:
            fixes.append("Your answer is partially correct - add more specific details or examples")
        
        if "missing_keywords" in error_keys:
            fixes.append("Include important terms and concepts that are missing from your answer")
        
        return fixes
    
    def _log_disagreement(
        self,
        question: str,
        answer: str,
        rule_score: float,
        llm_score: float,
        disagreement: float
    ) -> None:
        """
        Log disagreement between rule and LLM scores to JSONL file.
        
        Args:
            question: The question being evaluated
            answer: Student's answer
            rule_score: Rule-based score
            llm_score: LLM score
            disagreement: Absolute difference |rule - llm|
        """
        if not self.disagreements_log:
            return
        
        try:
            log_path = Path(self.disagreements_log)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            record = {
                "timestamp": datetime.now().isoformat(),
                "question": question,
                "answer": answer,
                "rule_score": rule_score,
                "llm_score": llm_score,
                "disagreement": disagreement,
                "threshold": self.disagreement_threshold
            }
            
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
            
            logger.debug(f"Logged disagreement to {log_path}")
        except Exception as e:
            logger.error(f"Failed to log disagreement: {e}")
    
    def _log_evaluation_metrics(
        self,
        question: str,
        answer: str,
        rule_score: float,
        rule_error_keys: list,
        llm_score: Optional[float],
        overall_score: float,
        stop_score: float,
        used_llm: bool
    ) -> None:
        """
        Log comprehensive evaluation metrics for monitoring and analysis.
        
        This helps track:
        - How often LLM is used vs skipped (borderline mode)
        - Score distributions (rule vs LLM vs overall)
        - Error patterns (which error_keys appear most)
        - Calibration effectiveness (stop_score distribution)
        
        Args:
            question: The question being evaluated
            answer: Student's answer
            rule_score: Rule-based score
            rule_error_keys: Error keys detected by rules
            llm_score: LLM score (None if not used)
            overall_score: Combined weighted score
            stop_score: Calibrated stopping score
            used_llm: Whether LLM reviewer was invoked
        """
        try:
            log_path = Path("logs/evaluation_metrics.jsonl")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            record = {
                "timestamp": datetime.now().isoformat(),
                "question": question[:100],  # Truncate for storage
                "answer": answer[:200],
                "rule_score": rule_score,
                "rule_error_keys": rule_error_keys,
                "llm_score": llm_score,
                "overall_score": overall_score,
                "stop_score": stop_score,
                "used_llm": used_llm,
                "borderline_mode": self.use_borderline,
                "weights": {
                    "rule": self.rule_weight,
                    "llm": self.llm_weight
                }
            }
            
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
            
            logger.debug(f"Logged evaluation metrics to {log_path}")
        except Exception as e:
            logger.error(f"Failed to log evaluation metrics: {e}")
