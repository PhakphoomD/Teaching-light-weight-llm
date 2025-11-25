"""
Deterministic task classifier and structure extractor (structure-first memory).

This module is pure (no I/O). It provides:
- pre_normalize: Unicode-aware normalization preserving math symbols/punctuation
- extract_structure_signature: Canonical structure signatures per task
- extract_constraints: Regex-based constraints (n/style/cite, operands, separator)
- extract_task_type: End-to-end classification returning
  (task_type, structure_signature, constraints, confidence)

Rules:
- English-first, regex only, deterministic
- Clamp/normalize outputs to canonical forms
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Tuple


MATH_KEEP = "+-*/%()=^"  # math symbols to keep
PUNCT_KEEP = ".,;:!?-"    # punctuation to keep


def pre_normalize(text: str) -> str:
    """Normalize input text deterministically.

    - Unicode NFKC
    - Lowercase
    - Collapse whitespace to single spaces
    - Remove characters except: a-z, 0-9, whitespace, math symbols, selected punctuation
      (math: + - * / % ( ) = ^, punctuation: . , ; : ! ? -)

    Returns ASCII-safe string.
    """
    text = unicodedata.normalize("NFKC", text or "")
    text = text.lower()
    # Allow set
    allow = set("abcdefghijklmnopqrstuvwxyz0123456789 \t\n\r" + MATH_KEEP + PUNCT_KEEP)
    cleaned = "".join(ch if ch in allow else " " for ch in text)
    # collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_list_n(text: str) -> int | str:
    m = re.search(r"\b(\d{1,3})\b", text)
    if not m:
        return "?"
    try:
        n = int(m.group(1))
        return n
    except Exception:
        return "?"


def extract_constraints(question: str, task_type: str) -> Dict[str, Any]:
    """Extract constraints per task type.

    - list: n, style (numbered|bulleted|default), cite (bool)
    - split: separator ('comma'|'space') if present
    - math: operands (list of float)
    """
    q = pre_normalize(question)
    constraints: Dict[str, Any] = {}

    if task_type == "list_generation":
        n = _extract_list_n(q)
        style = "default"
        if re.search(r"\bnumbered\b", q):
            style = "numbered"
        elif re.search(r"\bbullet|bulleted\b", q):
            style = "bulleted"
        cite = bool(re.search(r"\b(citation|reference|source)\b", q))
        constraints = {"n": n, "style": style, "cite": cite}

    elif task_type == "text_splitting":
        sep = None
        if re.search(r"\bcomma\b", q):
            sep = "comma"
        elif re.search(r"\bspace\b", q):
            sep = "space"
        if sep:
            constraints["separator"] = sep

    elif task_type == "math_problem":
        nums = [float(x) for x in re.findall(r"(?<![a-zA-Z])(\d+(?:\.\d+)?)", q)]
        constraints["operands"] = nums

    return constraints


def extract_structure_signature(question: str, task_type: str) -> str:
    """Compute canonical structure signature per task type.

    Follows the canonical mapping in the project spec.
    """
    q = pre_normalize(question)

    if task_type == "list_generation":
        n = _extract_list_n(q)
        if re.search(r"\bnumbered\b", q):
            return f"numbered({n})"
        if re.search(r"\bbullet|bulleted\b", q):
            return f"bulleted({n})"
        return f"list({n})"

    if task_type == "text_splitting":
        if re.search(r"\bsentence|sentences\b", q):
            return "split_sentences"
        if re.search(r"\bword|words\b", q):
            return "split_words"
        return "split_generic"

    if task_type == "definition":
        # Simple heuristic by length
        # Short if <= 12 words
        words = len(q.split())
        return "definition_short" if words <= 12 else "definition_long"

    if task_type == "math_problem":
        if "%" in q or re.search(r"\bpercent|percentage\b", q):
            return "math_percentage"
        if re.search(r"\bsqrt|square root\b", q):
            return "math_sqrt"
        if re.search(r"[\d\)\]]\s*[+\-*/^]\s*[\(\[\d]", q):
            return "math_arithmetic"
        return "math_generic"

    if task_type == "translation":
        return "translate"
    if task_type == "classification":
        return "classify"
    if task_type == "comparison":
        return "compare"
    if task_type == "summarization":
        return "summarize"
    if task_type == "question_answering":
        return "qa"
    return "general"


def _detect_task_type(normalized: str) -> Tuple[str, str]:
    """Return (task_type, confidence)."""
    q = normalized
    # List
    if re.search(r"\b(name|list|give|provide|mention)\s+\d+", q) or re.search(r"\b(list|numbered|bulleted)\b", q):
        return "list_generation", "high"
    # Split
    if re.search(r"\b(split|break|separate|divide)\b", q):
        return "text_splitting", "high"
    # Definition
    if re.search(r"\b(define|definition|explain|what is|describe)\b", q):
        return "definition", "high"
    # Translation
    if re.search(r"\b(translate|convert)\b\s+", q):
        return "translation", "high"
    # Math
    if re.search(r"\b(calculate|compute|find|solve)\b", q) or re.search(r"[\d\)\]]\s*[+\-*/^%]\s*[\(\[\d]", q) or "%" in q:
        return "math_problem", "high"
    # Classification
    if re.search(r"\b(classify|categorize|sort|group)\b", q):
        return "classification", "high"
    # Comparison
    if re.search(r"\b(compare|contrast|difference|similar)\b", q):
        return "comparison", "med"
    # Summarization
    if re.search(r"\b(summarize|summarise|brief|overview)\b", q):
        return "summarization", "med"
    # QA (default for ending with ?)
    if q.strip().endswith("?"):
        return "question_answering", "low"
    return "general_instruction", "low"


def extract_task_type(question: str) -> Tuple[str, str, Dict[str, Any], str]:
    """Analyze a question to determine task type, structure, constraints, confidence.

    Returns (task_type, structure_signature, constraints, confidence)
    """
    norm = pre_normalize(question)
    task_type, confidence = _detect_task_type(norm)
    # Map general_instruction to general return signature
    if task_type == "general_instruction":
        signature = "general"
        constraints: Dict[str, Any] = {}
        return "general_instruction", signature, constraints, confidence

    constraints = extract_constraints(norm, task_type)
    signature = extract_structure_signature(norm, task_type)
    return task_type, signature, constraints, confidence


__all__ = [
    "pre_normalize",
    "extract_structure_signature",
    "extract_constraints",
    "extract_task_type",
]

