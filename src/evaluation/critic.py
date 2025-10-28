"""
Simple rule-based critic - Pure Checker with Structured Feedback

Supports two evaluation modes from dataset items:
- expected_exact: string that must match the student's answer after trimming
- expected_keywords: list of strings that all must be present (case-insensitive)

Returns structured validation results with actionable learning insights.
Does NOT leak exact answers - provides conceptual guidance instead.

Phase 2 integration: Uses canonical.py for text normalization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Set
import unicodedata
import re

from src.memory.canonical import normalize_for_comparison


@dataclass
class Critique:
    """Pure validation result from SimpleCritic (backward compatible)."""
    satisfied: bool
    error_type: Optional[str] = None  # "missing_keywords" | "exact_match_failed" | "empty_answer"
    missing_keywords: Optional[List[str]] = None
    expected_keywords: Optional[List[str]] = None
    expected_exact: Optional[str] = None
    student_answer: Optional[str] = None


@dataclass
class CriticResult:
    """
    Enhanced structured feedback from critic evaluation.
    
    Provides actionable learning insights without leaking exact answers.
    Designed for cross-task learning and self-improvement.
    """
    # Core validation
    satisfied: bool
    error_type: Optional[str] = None  # "missing_keywords" | "exact_match_failed" | "empty_answer"
    
    # Structured feedback (NO ANSWER LEAKAGE)
    error_analysis: str = ""  # What went wrong conceptually
    learning_point: str = ""  # Key insight to remember
    correction_hint: str = ""  # How to structure better answer
    
    # Detailed error information
    missing_concepts: Optional[List[str]] = None  # Missing concept IDs (not raw keywords)
    error_keys: Optional[List[str]] = None  # Error classification keys for indexing
    
    # Exact mode statistics (when error_type="exact_match_failed")
    exact_diff: Optional[Dict[str, Any]] = None  # {
        # "token_count_diff": int,  # student - expected token count
        # "case_errors": int,  # uppercase/lowercase mismatches
        # "space_errors": int,  # extra/missing spaces
        # "punct_errors": int,  # punctuation differences
        # "extra_words": List[str],  # words in student but not in expected
        # "missing_words": List[str]  # words in expected but not in student
    # }
    
    # Metadata
    student_answer: Optional[str] = None
    confidence: float = 1.0  # Critic's confidence in evaluation (0-1)
    
    def __post_init__(self):
        """Initialize default values."""
        if self.missing_concepts is None:
            self.missing_concepts = []
        if self.error_keys is None:
            self.error_keys = []


class SimpleCritic:
    """Pure checker - validates answers and provides structured feedback."""
    
    @staticmethod
    def _normalize(text: str) -> str:
        """Cheap, fast normalization: lowercase, NFKC, collapse spaces, strip.
        Avoids heavy NLP deps while reducing trivial mismatches.
        """
        if text is None:
            return ""
        t = unicodedata.normalize("NFKC", text).lower()
        t = re.sub(r"\s+", " ", t).strip()
        return t
    
    @staticmethod
    def _compute_exact_diff(student: str, expected: str, student_norm: str, expected_norm: str) -> Dict[str, Any]:
        """
        Compute detailed differences for exact match failures.
        
        Returns statistics about token count, case, space, punct differences.
        Does NOT return the expected answer itself.
        """
        # Token counts
        student_tokens = student_norm.split()
        expected_tokens = expected_norm.split()
        token_diff = len(student_tokens) - len(expected_tokens)
        
        # Case errors (compare before normalization)
        case_errors = sum(1 for s, e in zip(student, expected) if s.lower() == e.lower() and s != e)
        
        # Space errors (count space differences)
        student_spaces = student.count(' ')
        expected_spaces = expected.count(' ')
        space_errors = abs(student_spaces - expected_spaces)
        
        # Punctuation errors
        punct_pattern = r'[^\w\s]'
        student_punct = set(re.findall(punct_pattern, student))
        expected_punct = set(re.findall(punct_pattern, expected))
        punct_errors = len(student_punct.symmetric_difference(expected_punct))
        
        # Word-level diff (normalized)
        student_words = set(student_tokens)
        expected_words = set(expected_tokens)
        extra_words = list(student_words - expected_words)
        missing_words_count = len(expected_words - student_words)  # Don't reveal actual words
        
        return {
            "token_count_diff": token_diff,
            "case_errors": case_errors,
            "space_errors": space_errors,
            "punct_errors": punct_errors,
            "extra_words": extra_words,  # OK to show (student's own words)
            "missing_words_count": missing_words_count  # Count only, not actual words
        }

    def evaluate(self, item: Dict, answer: str) -> Critique:
        """
        Check if answer satisfies requirements (backward compatible).
        
        Returns Critique with structured error details (no feedback message).
        """
        answer_norm_raw = (answer or "").strip()
        answer_norm = self._normalize(answer_norm_raw)

        # Exact match mode
        if "expected_exact" in item and item["expected_exact"] is not None:
            expected = self._normalize(str(item["expected_exact"]).strip())
            if answer_norm == expected:
                return Critique(satisfied=True)
            
            return Critique(
                satisfied=False,
                error_type="exact_match_failed",
                expected_exact=None,  # Do not leak exact answer
                student_answer=answer_norm_raw
            )

        # Keyword mode: all keywords must appear (case-insensitive)
        if "expected_keywords" in item:
            kws: List[str] = [str(k) for k in item.get("expected_keywords", [])]
            miss = self._missing_keywords(answer_norm, kws)
            
            if not miss:
                return Critique(satisfied=True)
            
            return Critique(
                satisfied=False,
                error_type="missing_keywords",
                missing_keywords=miss,
                expected_keywords=kws,
                student_answer=answer_norm_raw
            )

        # Default: non-empty answer check
        if answer_norm:
            return Critique(satisfied=True)
        
        return Critique(
            satisfied=False,
            error_type="empty_answer",
            student_answer=answer_norm
        )
    
    def evaluate_structured(self, item: Dict, answer: str) -> CriticResult:
        """
        Enhanced evaluation with structured feedback.
        
        Returns CriticResult with actionable learning insights without answer leakage.
        
        Args:
            item: Task item with expected_keywords or expected_exact
            answer: Student's answer
            
        Returns:
            CriticResult with structured feedback
        """
        answer_norm_raw = (answer or "").strip()
        answer_norm = self._normalize(answer_norm_raw)
        
        # Empty answer check (highest priority)
        if not answer_norm:
            return CriticResult(
                satisfied=False,
                error_type="empty_answer",
                error_analysis="No answer provided",
                learning_point="Always provide a response, even if uncertain",
                correction_hint="Read the question carefully and attempt an answer",
                error_keys=["empty_response", "no_output"],
                student_answer=answer_norm_raw,
                confidence=1.0
            )
        
        # Exact match mode
        if "expected_exact" in item and item["expected_exact"] is not None:
            expected_raw = str(item["expected_exact"]).strip()
            expected = self._normalize(expected_raw)
            
            if answer_norm == expected:
                return CriticResult(
                    satisfied=True,
                    student_answer=answer_norm_raw,
                    confidence=1.0
                )
            
            # Compute detailed statistics
            exact_diff = self._compute_exact_diff(
                answer_norm_raw, expected_raw,
                answer_norm, expected
            )
            
            # Build error analysis based on statistics
            errors = []
            if exact_diff["token_count_diff"] != 0:
                if exact_diff["token_count_diff"] > 0:
                    errors.append(f"{exact_diff['token_count_diff']} extra words")
                else:
                    errors.append(f"{abs(exact_diff['token_count_diff'])} missing words")
            if exact_diff["case_errors"] > 0:
                errors.append(f"{exact_diff['case_errors']} case errors")
            if exact_diff["space_errors"] > 0:
                errors.append(f"{exact_diff['space_errors']} spacing errors")
            if exact_diff["punct_errors"] > 0:
                errors.append(f"{exact_diff['punct_errors']} punctuation errors")
            
            error_summary = ", ".join(errors) if errors else "format mismatch"
            
            # Provide guidance without leaking answer
            return CriticResult(
                satisfied=False,
                error_type="exact_match_failed",
                error_analysis=f"Answer format does not match required specification: {error_summary}",
                learning_point="Some tasks require exact wording, spacing, or format",
                correction_hint=(
                    "Follow the required format precisely:\n"
                    "- Match spacing and punctuation exactly\n"
                    "- Check for required capitalization\n"
                    "- Avoid extra words or explanations"
                ),
                error_keys=["format_mismatch", "exact_match_required"],
                exact_diff=exact_diff,
                student_answer=answer_norm_raw,
                confidence=0.95  # High confidence in format checking
            )
        
        # Keyword mode: check for missing concepts
        if "expected_keywords" in item:
            kws: List[str] = [str(k) for k in item.get("expected_keywords", [])]
            missing = self._missing_keywords(answer_norm, kws)
            present = [k for k in kws if k not in missing]
            
            if not missing:
                return CriticResult(
                    satisfied=True,
                    student_answer=answer_norm_raw,
                    confidence=1.0
                )
            
            # Build structured feedback
            error_analysis = self._build_error_analysis(missing, present, kws)
            learning_point = self._build_learning_point(missing, kws)
            correction_hint = self._build_correction_hint(missing, present, kws)
            error_keys = self._build_error_keys(missing)
            
            return CriticResult(
                satisfied=False,
                error_type="missing_keywords",
                error_analysis=error_analysis,
                learning_point=learning_point,
                correction_hint=correction_hint,
                missing_concepts=missing,  # Store for memory indexing
                error_keys=error_keys,
                student_answer=answer_norm_raw,
                confidence=0.9  # Good confidence in keyword detection
            )
        
        # Default: non-empty answer passes
        return CriticResult(
            satisfied=True,
            student_answer=answer_norm_raw,
            confidence=0.7  # Lower confidence without specific criteria
        )
    
    @staticmethod
    def validate_no_answer_leakage(feedback_data: Dict[str, Any], teacher_answer: Optional[str] = None) -> None:
        """
        Assert that feedback data does not contain teacher_answer or expected_exact.
        
        This safeguard prevents accidental answer leakage in logs or stored feedback.
        Call this before logging or storing any feedback.
        
        Args:
            feedback_data: Dictionary containing feedback to be logged/stored
            teacher_answer: Optional teacher answer to check against
            
        Raises:
            AssertionError: If answer leakage detected
        """
        # Convert to JSON string for comprehensive search
        feedback_str = str(feedback_data).lower()
        
        # Check for prohibited keys
        prohibited_keys = ["teacher_answer", "expected_exact", "correct_answer", "gold_answer"]
        for key in prohibited_keys:
            assert key not in feedback_data, \
                f"Prohibited key '{key}' found in feedback data - potential answer leakage!"
        
        # Check for teacher_answer content if provided
        if teacher_answer:
            teacher_norm = teacher_answer.lower().strip()
            if len(teacher_norm) > 10:  # Only check substantial answers
                # Check if more than 50% of teacher answer appears in feedback
                words = teacher_norm.split()
                matches = sum(1 for word in words if len(word) > 3 and word in feedback_str)
                if len(words) > 0 and matches / len(words) > 0.5:
                    assert False, \
                        f"Teacher answer content detected in feedback - potential leakage!"
        
        # Passed all checks
        pass
    
    def _build_error_analysis(
        self, 
        missing: List[str], 
        present: List[str],
        all_keywords: List[str]
    ) -> str:
        """Build error analysis without leaking answers."""
        analysis_parts = []
        
        if len(missing) == len(all_keywords):
            analysis_parts.append("Your answer does not address the required concepts")
        elif len(missing) == 1:
            analysis_parts.append(f"Your answer is missing 1 key concept: {missing[0]}")
        else:
            analysis_parts.append(
                f"Your answer is missing {len(missing)}/{len(all_keywords)} required concepts"
            )
        
        if present:
            analysis_parts.append(f"You correctly mentioned: {', '.join(present[:3])}")
        
        return ". ".join(analysis_parts) + "."
    
    def _build_learning_point(self, missing: List[str], all_keywords: List[str]) -> str:
        """Build key learning insight."""
        if len(missing) == len(all_keywords):
            return "Always address all aspects of the question systematically"
        elif len(missing) > len(all_keywords) // 2:
            return "Ensure your answer covers all major concepts requested"
        else:
            return f"Don't forget to include: {', '.join(missing)}"
    
    def _build_correction_hint(
        self,
        missing: List[str],
        present: List[str],
        all_keywords: List[str]
    ) -> str:
        """Build actionable correction hint."""
        hint_parts = []
        
        # Structure guidance
        if len(all_keywords) >= 3:
            hint_parts.append(
                f"Structure your answer to cover {len(all_keywords)} main points"
            )
        
        # Missing concepts (general guidance, not answers)
        if len(missing) == 1:
            hint_parts.append(f"Add information about: {missing[0]}")
        elif len(missing) <= 3:
            hint_parts.append(f"Include: {', '.join(missing)}")
        else:
            hint_parts.append(f"Cover these concepts: {', '.join(missing[:3])} (and {len(missing)-3} more)")
        
        # Format guidance
        if len(all_keywords) >= 2:
            hint_parts.append("Use clear sentences for each concept")
        
        return "\n- ".join([""] + hint_parts) if hint_parts else ""
    
    def _build_error_keys(self, missing: List[str]) -> List[str]:
        """Build error classification keys for memory indexing."""
        keys = ["missing_concepts"]
        
        # Add normalized concept keys
        for concept in missing[:5]:  # Limit to top 5
            normalized = self._normalize(concept)
            if normalized:
                keys.append(f"missing:{normalized.replace(' ', '_')}")
        
        return keys

    @staticmethod
    def _missing_keywords(answer: str, kws: List[str]) -> List[str]:
        """
        Find keywords that are missing from answer.
        
        Phase 2: Uses normalize_for_comparison for better matching.
        """
        # Use canonical normalization for better matching
        a = normalize_for_comparison(answer)
        result = []
        for k in kws:
            kn = normalize_for_comparison(k)
            if kn and kn not in a:
                result.append(k)
        return result
