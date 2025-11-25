"""
Rule-Based Checkers

Deterministic (non-LLM) quality checks for student answers.
Fast, reproducible, and interpretable.

Checkers:
- format_checker: Length, structure, formatting
- faithfulness_checker: Match with ground truth (if available)
- completeness_checker: Coverage of question requirements

Metrics:
- compute_f1_score: F1 score for token-level matching
- compute_rouge_l: ROUGE-L for sequence-level matching

Each returns (score, error_keys) where score in [0, 1].
"""

from typing import List, Tuple, Dict, Optional
import re
import logging

logger = logging.getLogger("critic.rule_checkers")


# ============================================================================
# ADVANCED METRICS
# ============================================================================

def compute_f1_score(answer: str, ground_truth: str) -> float:
    """
    Compute F1 score between answer and ground truth.
    Better than simple token overlap as it balances precision and recall.
    
    Args:
        answer: Student's answer text
        ground_truth: Reference answer text
    
    Returns:
        F1 score in [0.0, 1.0]
    
    Examples:
        >>> compute_f1_score("Paris is the capital", "Paris")
        0.67  # Precision=0.5, Recall=1.0 -> F1=0.67
        
        >>> compute_f1_score("Paris", "Paris is the capital")
        0.67  # Precision=1.0, Recall=0.5 -> F1=0.67
    """
    answer_tokens = set(_tokenize(_normalize_text(answer)))
    gt_tokens = set(_tokenize(_normalize_text(ground_truth)))
    
    if not gt_tokens or not answer_tokens:
        return 0.0
    
    common = answer_tokens & gt_tokens
    
    if not common:
        return 0.0
    
    precision = len(common) / len(answer_tokens)
    recall = len(common) / len(gt_tokens)
    
    if precision + recall == 0:
        return 0.0
    
    f1 = 2 * (precision * recall) / (precision + recall)
    return f1


def compute_rouge_l(answer: str, ground_truth: str) -> float:
    """
    Compute ROUGE-L (Longest Common Subsequence).
    Better for long answers as it considers word order.
    
    Args:
        answer: Student's answer text
        ground_truth: Reference answer text
    
    Returns:
        ROUGE-L score in [0.0, 1.0]
    
    Examples:
        >>> compute_rouge_l("Paris is the capital of France", "Paris is capital of France")
        0.83  # 5/6 LCS length
    """
    def lcs_length(s1: List[str], s2: List[str]) -> int:
        """Compute longest common subsequence length using DP."""
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        
        return dp[m][n]
    
    answer_tokens = _tokenize(_normalize_text(answer))
    gt_tokens = _tokenize(_normalize_text(ground_truth))
    
    if not gt_tokens:
        return 0.0
    
    lcs_len = lcs_length(answer_tokens, gt_tokens)
    
    # ROUGE-L recall = LCS / len(reference)
    rouge_l_recall = lcs_len / len(gt_tokens)
    
    # Can also compute precision for F-measure, but typically use recall
    if not answer_tokens:
        rouge_l_precision = 0.0
    else:
        rouge_l_precision = lcs_len / len(answer_tokens)
    
    # ROUGE-L F-measure (balanced)
    if rouge_l_precision + rouge_l_recall == 0:
        return 0.0
    
    rouge_l_f = 2 * (rouge_l_precision * rouge_l_recall) / (rouge_l_precision + rouge_l_recall)
    
    return rouge_l_f


# ============================================================================
# FORMAT CHECKER
# ============================================================================

def format_checker(answer: str) -> Tuple[float, List[str]]:
    """
    Check formatting quality of answer.
    
    Checks:
    - Length (too short < 10 chars -> penalty)
    - Capitalization (starts with lowercase -> minor penalty)
    - Punctuation (missing period at end -> minor penalty)
    - Empty/whitespace only -> score 0.0
    
    Args:
        answer: Student's answer text
    
    Returns:
        (score, error_keys):
            score: 0.0-1.0 (higher = better formatting)
            error_keys: e.g., ["too_short", "no_punctuation"]
    
    Examples:
        >>> format_checker("Paris")
        (0.7, ["too_short", "no_punctuation"])
        
        >>> format_checker("Paris is the capital of France.")
        (1.0, [])
        
        >>> format_checker("")
        (0.0, ["empty"])
    """
    error_keys = []
    score = 1.0
    
    # Strip whitespace
    answer = answer.strip()
    
    # Empty check
    if not answer:
        return (0.0, ["empty"])
    
    # Length check
    if len(answer) < 10:
        error_keys.append("too_short")
        score -= 0.3
    
    # Capitalization check (first character)
    if answer and answer[0].islower():
        error_keys.append("no_capitalization")
        score -= 0.1
    
    # Punctuation check (ends with . ! ?)
    if not re.search(r'[.!?]$', answer):
        error_keys.append("no_punctuation")
        score -= 0.1
    
    # Clamp to [0, 1]
    score = max(0.0, min(1.0, score))
    
    return (score, error_keys)


# ============================================================================
# FAITHFULNESS CHECKER
# ============================================================================

def faithfulness_checker(
    question: str,
    answer: str,
    ground_truth: Optional[str] = None,
    use_f1: bool = True,
    use_rouge_l_for_long: bool = True,
    rouge_l_word_threshold: int = 20
) -> Tuple[float, List[str]]:
    """
    Check faithfulness/correctness of answer using F1 or ROUGE-L.
    
    Strategies:
    1. If ground_truth provided:
       - Exact match -> 1.0
       - Contains GT -> 1.0
       - F1 score (short answers) -> 0.0-1.0
       - ROUGE-L (long answers) -> 0.0-1.0
    
    2. If no ground_truth:
       - Check if answer contains key terms from question
       - Score based on coverage
    
    Args:
        question: The question text
        answer: Student's answer
        ground_truth: Correct answer (optional)
        use_f1: Use F1 score for evaluation
        use_rouge_l_for_long: Use ROUGE-L for long answers
        rouge_l_word_threshold: Switch to ROUGE-L if answer > N words
    
    Returns:
        (score, error_keys):
            score: 0.0-1.0
            error_keys: e.g., ["wrong_answer", "partial_match"]
    
    Examples:
        >>> faithfulness_checker("Capital?", "Paris", "Paris")
        (1.0, [])
        
        >>> faithfulness_checker("Capital?", "Paris is capital", "Paris", use_f1=True)
        (0.67, [])  # F1 score
    """
    error_keys = []
    
    # Normalize
    answer_norm = _normalize_text(answer)
    
    # Strategy 1: Ground truth available
    if ground_truth:
        gt_norm = _normalize_text(ground_truth)
        
        # Exact match (normalized)
        if answer_norm == gt_norm:
            return (1.0, [])
        
        # Fuzzy match (lowercase + strip)
        if answer_norm.lower() == gt_norm.lower():
            return (1.0, [])
        
        # Check if ground truth is CONTAINED in answer
        if gt_norm.lower() in answer_norm.lower():
            return (1.0, [])
        
        # Decide which metric to use based on answer length
        answer_word_count = len(answer.split())
        
        if use_rouge_l_for_long and answer_word_count > rouge_l_word_threshold:
            # Use ROUGE-L for long answers
            score = compute_rouge_l(answer, ground_truth)
            metric_type = "rouge_l"
        elif use_f1:
            # Use F1 for short answers
            score = compute_f1_score(answer, ground_truth)
            metric_type = "f1"
        else:
            # Fallback to token overlap
            answer_tokens = set(_tokenize(answer_norm))
            gt_tokens = set(_tokenize(gt_norm))
            
            if gt_tokens:
                overlap = len(answer_tokens & gt_tokens) / len(gt_tokens)
                score = min(0.9, overlap)
                metric_type = "overlap"
            else:
                return (0.5, ["no_ground_truth"])
        
        # Map score to error keys
        if score >= 0.8:
            return (score, [])
        elif score >= 0.6:
            error_keys.append("partial_match")
        elif score >= 0.3:
            error_keys.append("low_overlap")
        else:
            error_keys.append("wrong_answer")
        
        return (score, error_keys)
    
    # Strategy 2: No ground truth -> check key terms from question
    question_norm = _normalize_text(question)
    question_tokens = set(_tokenize(question_norm))
    answer_tokens = set(_tokenize(answer_norm))
    
    # Remove stop words (very basic)
    question_tokens = _remove_stopwords(question_tokens)
    
    if question_tokens:
        coverage = len(question_tokens & answer_tokens) / len(question_tokens)
        
        if coverage < 0.3:
            error_keys.append("missing_key_terms")
        
        # Score based on coverage
        score = min(1.0, coverage * 1.5)  # Boost to reach 1.0 at 67% coverage
        return (score, error_keys)
    else:
        # No key terms to check
        return (0.5, ["no_key_terms"])


# ============================================================================
# COMPLETENESS CHECKER
# ============================================================================

def completeness_checker(
    question: str,
    answer: str
) -> Tuple[float, List[str]]:
    """
    Check if answer addresses all parts of the question.
    
    Heuristics:
    - Multi-part questions (contains "and", "or", numbered list)
    - Answer should have multiple sentences/clauses
    - Length proportional to question complexity
    
    Args:
        question: The question text
        answer: Student's answer
    
    Returns:
        (score, error_keys):
            score: 0.0-1.0
            error_keys: e.g., ["incomplete", "too_brief"]
    
    Examples:
        >>> completeness_checker("What is X and why?", "X is Y.")
        (0.5, ["incomplete"])
        
        >>> completeness_checker("What is X and why?", "X is Y because Z.")
        (1.0, [])
    """
    error_keys = []
    score = 1.0
    
    # Detect multi-part question
    is_multipart = any(marker in question.lower() for marker in [
        " and ", " or ", "why", "how", "explain", "describe",
        "1.", "2.", "a)", "b)"
    ])
    
    # Count sentences in answer
    answer_sentences = _count_sentences(answer)
    
    if is_multipart:
        # Expect multiple sentences for multi-part questions
        if answer_sentences < 2:
            error_keys.append("incomplete")
            score -= 0.5
        
        # Check length
        if len(answer.strip()) < 30:
            error_keys.append("too_brief")
            score -= 0.3
    else:
        # Single-part question
        if len(answer.strip()) < 5:
            error_keys.append("too_brief")
            score -= 0.5
    
    # Clamp
    score = max(0.0, min(1.0, score))
    
    return (score, error_keys)


# ============================================================================
# AGGREGATE RULE SCORES
# ============================================================================

def compute_rule_score(
    question: str,
    answer: str,
    ground_truth: Optional[str] = None,
    weights: Optional[Dict[str, float]] = None
) -> Tuple[float, List[str]]:
    """
    Run all rule checkers and aggregate scores.
    
    Combines:
    - format_checker
    - faithfulness_checker (with F1/ROUGE-L from settings)
    - completeness_checker
    
    Args:
        question: The question text
        answer: Student's answer
        ground_truth: Correct answer (optional)
        weights: Custom weights for each checker (optional)
                 Default: {"format": 0.2, "faithfulness": 0.6, "completeness": 0.2}
    
    Returns:
        (overall_score, all_error_keys):
            overall_score: Weighted average in [0, 1]
            all_error_keys: Combined list of all error keys
    
    Example:
        >>> score, keys = compute_rule_score(
        ...     "What is the capital of France?",
        ...     "paris",
        ...     ground_truth="Paris"
        ... )
        >>> print(f"Score: {score:.2f}, Errors: {keys}")
        Score: 0.76, Errors: ['no_punctuation', 'no_capitalization']
    """
    # Load metrics settings
    from ...settings import SETTINGS
    
    # Default weights
    if weights is None:
        weights = {
            "format": 0.2,
            "faithfulness": 0.6,
            "completeness": 0.2
        }
    
    # Run checkers
    format_score, format_keys = format_checker(answer)
    
    # Faithfulness checker with F1/ROUGE-L from settings
    faith_score, faith_keys = faithfulness_checker(
        question=question,
        answer=answer,
        ground_truth=ground_truth,
        use_f1=SETTINGS.metrics.use_f1,
        use_rouge_l_for_long=SETTINGS.metrics.use_rouge_l_for_long,
        rouge_l_word_threshold=SETTINGS.metrics.rouge_l_word_threshold
    )
    
    complete_score, complete_keys = completeness_checker(question, answer)
    
    # Aggregate scores
    overall_score = (
        weights["format"] * format_score +
        weights["faithfulness"] * faith_score +
        weights["completeness"] * complete_score
    )
    
    # Combine error keys (deduplicate)
    all_error_keys = list(set(format_keys + faith_keys + complete_keys))
    
    logger.debug(
        f"Rule scores: format={format_score:.2f}, faith={faith_score:.2f}, "
        f"complete={complete_score:.2f}, overall={overall_score:.2f}"
    )
    
    return (overall_score, all_error_keys)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _normalize_text(text: str) -> str:
    """Normalize text: strip, collapse whitespace."""
    return " ".join(text.strip().split())


def _tokenize(text: str) -> List[str]:
    """Simple tokenization: split on whitespace and punctuation."""
    # Remove punctuation, split on whitespace
    text = re.sub(r'[^\w\s]', ' ', text)
    return [t.lower() for t in text.split() if t]


def _remove_stopwords(tokens: set) -> set:
    """Remove common English stop words (very basic list)."""
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "of", "to", "in", "on", "at", "for", "with", "by",
        "what", "why", "how", "when", "where", "who"
    }
    return tokens - stopwords


def _count_sentences(text: str) -> int:
    """Count sentences (split on . ! ?)."""
    return len(re.split(r'[.!?]+', text.strip())) - 1  # -1 for trailing split
