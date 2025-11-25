"""
Text Generation Metrics Module

This module implements standard metrics for evaluating generated text quality
in retrieval-augmented generation (RAG) and teaching systems.

Metrics include:
- Exact Match: Binary correctness
- F1 Score: Token-level overlap
- BLEU: N-gram precision (machine translation metric)
- ROUGE: Recall-oriented n-gram overlap
- BERTScore: Semantic similarity using embeddings

References:
- RAG Evaluation: "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
  https://www.mdpi.com/2076-3417/13/19/11003
- BERTScore: "BERTScore: Evaluating Text Generation with BERT" (ICLR 2020)
- BLEU: Papineni et al. "BLEU: a Method for Automatic Evaluation of Machine Translation"
- ROUGE: Lin "ROUGE: A Package for Automatic Evaluation of Summaries"

Usage:
    >>> from src.eval.metrics import exact_match, f1, bleu, rouge_scores
    >>> pred = "The capital of France is Paris."
    >>> ref = "Paris is the capital of France."
    >>> print(f"Exact Match: {exact_match(pred, ref)}")
    >>> print(f"F1 Score: {f1(pred, ref)}")
    >>> print(f"BLEU: {bleu(pred, ref)}")
    >>> print(f"ROUGE: {rouge_scores(pred, ref)}")
"""

from typing import Tuple, Dict, List
import re
from collections import Counter
import numpy as np


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison.
    
    Args:
        text: Input text
    
    Returns:
        Normalized text (lowercase, no punctuation, single spaces)
    
    Example:
        >>> normalize_text("Hello,  World!")
        'hello world'
    """
    if text is None:
        return ''
    
    text = str(text)  # Convert to string if not already
    
    # Lowercase
    text = text.lower()
    # Remove punctuation
    text = re.sub(r'[^\w\s]', '', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    return text


def tokenize(text: str) -> List[str]:
    """
    Simple whitespace tokenizer.
    
    Args:
        text: Input text
    
    Returns:
        List of tokens
    """
    return normalize_text(text).split()


def exact_match(pred: str, ref: str, normalize: bool = True) -> float:
    """
    Calculate exact match score (0 or 1).
    
    Exact match is a binary metric: 1 if prediction exactly matches reference
    after normalization, 0 otherwise. Commonly used in QA evaluation.
    
    Args:
        pred: Predicted text
        ref: Reference (ground truth) text
        normalize: Whether to normalize text before comparison (default: True)
    
    Returns:
        1.0 if exact match, 0.0 otherwise
    
    Example:
        >>> exact_match("Paris", "Paris")
        1.0
        >>> exact_match("Paris", "paris")
        1.0  # normalized
        >>> exact_match("Paris", "London")
        0.0
    
    Reference:
        Standard metric in SQuAD, Natural Questions, and other QA benchmarks.
    """
    if normalize:
        pred = normalize_text(pred)
        ref = normalize_text(ref)
    
    return 1.0 if pred == ref else 0.0


def keyword_coverage(pred: str, keywords: List[str], normalize: bool = True) -> float:
    """
    Calculate percentage of expected keywords present in prediction.
    
    Args:
        pred: Predicted text
        keywords: List of expected keywords
        normalize: Whether to normalize text before comparison (default: True)
    
    Returns:
        Float between 0.0 and 1.0 (percentage of keywords found)
    
    Example:
        >>> keyword_coverage("Logistic regression algorithm", ["regression", "algorithm", "appropriate"])
        0.667  # 2 out of 3 keywords found
    """
    if not keywords:
        return 1.0  # No keywords required = always pass
    
    if normalize:
        pred = normalize_text(pred)
        keywords = [normalize_text(kw) for kw in keywords]
    
    found = sum(1 for kw in keywords if kw in pred)
    return found / len(keywords)


def semantic_similarity(pred: str, ref: str, encoder=None) -> float:
    """
    Calculate semantic similarity using sentence embeddings.
    
    Uses sentence-transformers to compute cosine similarity between
    prediction and reference embeddings. This captures semantic meaning
    rather than exact word overlap.
    
    Args:
        pred: Predicted text
        ref: Reference text
        encoder: SentenceTransformer encoder (if None, creates one)
    
    Returns:
        Cosine similarity between 0.0 and 1.0
    
    Example:
        >>> semantic_similarity("Logistic Regression", "logistic regression algorithm")
        0.87  # high semantic similarity despite different words
        >>> semantic_similarity("Random Forest", "Logistic Regression")
        0.65  # medium (both ML algorithms)
        >>> semantic_similarity("cat", "machine learning")
        0.15  # low (unrelated)
    
    Note:
        Requires sentence-transformers package.
        Uses 'all-MiniLM-L6-v2' model (384-dim, fast).
    """
    try:
        from sentence_transformers import SentenceTransformer
        
        # Use provided encoder or create one
        if encoder is None:
            encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Compute embeddings
        pred_emb = encoder.encode([pred], convert_to_numpy=True)[0]
        ref_emb = encoder.encode([ref], convert_to_numpy=True)[0]
        
        # Cosine similarity
        cos_sim = np.dot(pred_emb, ref_emb) / (
            np.linalg.norm(pred_emb) * np.linalg.norm(ref_emb)
        )
        
        # Clamp to [0, 1] (should already be in range but safe)
        return float(max(0.0, min(1.0, cos_sim)))
        
    except ImportError:
        print("sentence-transformers not installed, returning 0.0")
        return 0.0
    except Exception as e:
        print(f"Error computing semantic similarity: {e}")
        return 0.0


def f1(pred: str, ref: str) -> float:
    """
    Calculate token-level F1 score.
    
    F1 score is the harmonic mean of precision and recall at the token level.
    This is more lenient than exact match and gives partial credit for
    overlapping tokens.
    
    Formula:
        Precision = |common_tokens| / |pred_tokens|
        Recall = |common_tokens| / |ref_tokens|
        F1 = 2 * (Precision * Recall) / (Precision + Recall)
    
    Args:
        pred: Predicted text
        ref: Reference text
    
    Returns:
        F1 score between 0.0 and 1.0
    
    Example:
        >>> f1("The capital is Paris", "Paris is the capital")
        0.8  # 4/5 tokens match
        >>> f1("London", "Paris")
        0.0  # no overlap
        >>> f1("Paris France", "Paris")
        0.67  # partial overlap
    
    Reference:
        Widely used in SQuAD and other QA datasets for partial credit.
    """
    pred_tokens = tokenize(pred)
    ref_tokens = tokenize(ref)
    
    if len(pred_tokens) == 0 or len(ref_tokens) == 0:
        return 0.0
    
    # Count token overlaps
    pred_counter = Counter(pred_tokens)
    ref_counter = Counter(ref_tokens)
    
    common = pred_counter & ref_counter  # Intersection
    num_common = sum(common.values())
    
    if num_common == 0:
        return 0.0
    
    precision = num_common / len(pred_tokens)
    recall = num_common / len(ref_tokens)
    
    f1_score = 2 * (precision * recall) / (precision + recall)
    
    return f1_score


def bleu(pred: str, ref: str, max_n: int = 4) -> float:
    """
    Calculate BLEU score (BiLingual Evaluation Understudy).
    
    BLEU measures n-gram precision between predicted and reference text.
    Originally designed for machine translation evaluation.
    
    This is a simplified implementation using geometric mean of n-gram
    precisions with brevity penalty.
    
    Formula:
        BLEU = BP * exp(sum(w_n * log(p_n)))
        where p_n is n-gram precision, BP is brevity penalty
    
    Args:
        pred: Predicted text
        ref: Reference text
        max_n: Maximum n-gram size (default: 4)
    
    Returns:
        BLEU score between 0.0 and 1.0
    
    Example:
        >>> bleu("The cat sat on the mat", "The cat sat on the mat")
        1.0  # perfect match
        >>> bleu("The dog sat", "The cat sat on the mat")
        0.45  # partial match
    
    Reference:
        Papineni et al. (2002) "BLEU: a Method for Automatic Evaluation
        of Machine Translation"
    
    Note:
        For production use, consider using nltk.translate.bleu_score
        or sacrebleu for more robust implementation.
    """
    try:
        from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
        
        pred_tokens = tokenize(pred)
        ref_tokens = tokenize(ref)
        
        # NLTK expects reference as list of token lists
        references = [ref_tokens]
        
        # Use smoothing to avoid zero scores for missing n-grams
        smoothing = SmoothingFunction().method1
        
        score = sentence_bleu(
            references,
            pred_tokens,
            weights=[1/max_n] * max_n,
            smoothing_function=smoothing
        )
        
        return score
        
    except ImportError:
        # Fallback: simple unigram precision if NLTK not available
        pred_tokens = set(tokenize(pred))
        ref_tokens = set(tokenize(ref))
        
        if len(pred_tokens) == 0:
            return 0.0
        
        overlap = len(pred_tokens & ref_tokens)
        return overlap / len(pred_tokens)


def rouge_scores(pred: str, ref: str) -> Dict[str, float]:
    """
    Calculate ROUGE scores (Recall-Oriented Understudy for Gisting Evaluation).
    
    ROUGE measures recall-based n-gram overlap, commonly used for
    summarization evaluation. Returns ROUGE-1, ROUGE-2, and ROUGE-L scores.
    
    Metrics:
    - ROUGE-1: Unigram overlap
    - ROUGE-2: Bigram overlap
    - ROUGE-L: Longest common subsequence
    
    Args:
        pred: Predicted text
        ref: Reference text
    
    Returns:
        Dictionary with 'rouge-1', 'rouge-2', 'rouge-l' scores
    
    Example:
        >>> scores = rouge_scores("The cat sat", "The cat sat on the mat")
        >>> print(scores)
        {'rouge-1': 1.0, 'rouge-2': 1.0, 'rouge-l': 0.5}
    
    Reference:
        Lin (2004) "ROUGE: A Package for Automatic Evaluation of Summaries"
    
    Note:
        Uses simplified implementation. For production, use py-rouge
        or rouge-score library for official ROUGE metrics.
    """
    pred_tokens = tokenize(pred)
    ref_tokens = tokenize(ref)
    
    if len(pred_tokens) == 0 or len(ref_tokens) == 0:
        return {'rouge-1': 0.0, 'rouge-2': 0.0, 'rouge-l': 0.0}
    
    # ROUGE-1 (unigram recall)
    pred_unigrams = set(pred_tokens)
    ref_unigrams = set(ref_tokens)
    rouge_1 = len(pred_unigrams & ref_unigrams) / len(ref_unigrams)
    
    # ROUGE-2 (bigram recall)
    pred_bigrams = set(zip(pred_tokens[:-1], pred_tokens[1:]))
    ref_bigrams = set(zip(ref_tokens[:-1], ref_tokens[1:]))
    
    if len(ref_bigrams) > 0:
        rouge_2 = len(pred_bigrams & ref_bigrams) / len(ref_bigrams)
    else:
        rouge_2 = 0.0
    
    # ROUGE-L (longest common subsequence)
    def lcs_length(s1: List[str], s2: List[str]) -> int:
        """Calculate longest common subsequence length."""
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        
        return dp[m][n]
    
    lcs_len = lcs_length(pred_tokens, ref_tokens)
    rouge_l = lcs_len / len(ref_tokens) if len(ref_tokens) > 0 else 0.0
    
    return {
        'rouge-1': rouge_1,
        'rouge-2': rouge_2,
        'rouge-l': rouge_l
    }


def bert_precision_recall_f1(
    pred: str,
    ref: str,
    model_name: str = "all-MiniLM-L6-v2"
) -> Tuple[float, float, float]:
    """
    Calculate BERTScore using semantic embeddings.
    
    BERTScore computes similarity between predicted and reference text
    using contextualized embeddings from pre-trained models. It correlates
    better with human judgment than n-gram based metrics.
    
    Returns precision, recall, and F1 based on token-level cosine similarity.
    
    Formula:
        Precision = avg(max_similarity per pred token)
        Recall = avg(max_similarity per ref token)
        F1 = 2 * (P * R) / (P + R)
    
    Args:
        pred: Predicted text
        ref: Reference text
        model_name: SentenceTransformer model name (default: all-MiniLM-L6-v2)
    
    Returns:
        Tuple of (precision, recall, f1) scores between 0.0 and 1.0
    
    Example:
        >>> p, r, f1 = bert_precision_recall_f1(
        ...     "Paris is the capital",
        ...     "The capital is Paris"
        ... )
        >>> print(f"BERTScore F1: {f1:.3f}")
        BERTScore F1: 0.987  # high semantic similarity
    
    Reference:
        Zhang et al. (2020) "BERTScore: Evaluating Text Generation with BERT"
        https://arxiv.org/abs/1904.09675
    
    Note:
        This is a simplified sentence-level implementation.
        For official BERTScore with token-level matching, use bert-score library.
    """
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Load model (cached after first use)
        model = SentenceTransformer(model_name)
        
        # Get embeddings
        pred_emb = model.encode([pred], convert_to_numpy=True)
        ref_emb = model.encode([ref], convert_to_numpy=True)
        
        # Calculate cosine similarity
        similarity = cosine_similarity(pred_emb, ref_emb)[0][0]
        
        # For sentence-level, precision = recall = f1 = similarity
        # (In token-level BERTScore, these would differ)
        precision = float(similarity)
        recall = float(similarity)
        f1_score = float(similarity)
        
        return precision, recall, f1_score
        
    except ImportError:
        # Fallback: use simple token overlap if sentence-transformers not available
        tokens_pred = set(tokenize(pred))
        tokens_ref = set(tokenize(ref))
        
        if len(tokens_pred) == 0 or len(tokens_ref) == 0:
            return 0.0, 0.0, 0.0
        
        overlap = len(tokens_pred & tokens_ref)
        precision = overlap / len(tokens_pred)
        recall = overlap / len(tokens_ref)
        
        if precision + recall == 0:
            f1_score = 0.0
        else:
            f1_score = 2 * (precision * recall) / (precision + recall)
        
        return precision, recall, f1_score


def compute_all_metrics(pred: str, ref: str) -> Dict[str, float]:
    """
    Compute all available metrics for a prediction-reference pair.
    
    Args:
        pred: Predicted text
        ref: Reference text
    
    Returns:
        Dictionary with all metric scores
    
    Example:
        >>> metrics = compute_all_metrics(
        ...     "The capital of France is Paris",
        ...     "Paris is the capital of France"
        ... )
        >>> for metric, score in metrics.items():
        ...     print(f"{metric}: {score:.3f}")
    """
    metrics = {}
    
    # Exact match
    metrics['exact_match'] = exact_match(pred, ref)
    
    # F1 score
    metrics['f1'] = f1(pred, ref)
    
    # BLEU
    metrics['bleu'] = bleu(pred, ref)
    
    # ROUGE scores
    rouge = rouge_scores(pred, ref)
    metrics['rouge-1'] = rouge['rouge-1']
    metrics['rouge-2'] = rouge['rouge-2']
    metrics['rouge-l'] = rouge['rouge-l']
    
    # BERTScore
    bert_p, bert_r, bert_f1 = bert_precision_recall_f1(pred, ref)
    metrics['bert_precision'] = bert_p
    metrics['bert_recall'] = bert_r
    metrics['bert_f1'] = bert_f1
    
    return metrics
