"""
Simple rule-based critic - Pure Checker (No Reflection Generation)

Supports two evaluation modes from dataset items:
- expected_exact: string that must match the student's answer after trimming
- expected_keywords: list of strings that all must be present (case-insensitive)

Returns only validation results with structured error details.
Does NOT generate feedback messages - that's the Reflector's job.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class Critique:
    """Pure validation result from SimpleCritic."""
    satisfied: bool
    error_type: Optional[str] = None  # "missing_keywords" | "exact_match_failed" | "empty_answer"
    missing_keywords: Optional[List[str]] = None
    expected_keywords: Optional[List[str]] = None
    expected_exact: Optional[str] = None
    student_answer: Optional[str] = None


class SimpleCritic:
    """Pure checker - validates answers without generating feedback."""
    
    def evaluate(self, item: Dict, answer: str) -> Critique:
        """
        Check if answer satisfies requirements.
        
        Returns Critique with structured error details (no feedback message).
        """
        answer_norm = (answer or "").strip()

        # Exact match mode
        if "expected_exact" in item and item["expected_exact"] is not None:
            expected = str(item["expected_exact"]).strip()
            if answer_norm == expected:
                return Critique(satisfied=True)
            
            return Critique(
                satisfied=False,
                error_type="exact_match_failed",
                expected_exact=expected,
                student_answer=answer_norm
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
                student_answer=answer_norm
            )

        # Default: non-empty answer check
        if answer_norm:
            return Critique(satisfied=True)
        
        return Critique(
            satisfied=False,
            error_type="empty_answer",
            student_answer=answer_norm
        )

    @staticmethod
    def _missing_keywords(answer: str, kws: List[str]) -> List[str]:
        """Find keywords that are missing from answer."""
        a = answer.lower()
        return [k for k in kws if k.lower() not in a]
