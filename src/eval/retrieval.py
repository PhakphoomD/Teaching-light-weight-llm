"""
Retrieval Evaluation Metrics

This module provides comprehensive evaluation metrics for information retrieval systems.
Used to measure the quality of vector-based memory retrieval in the teaching loop.

Metrics included:
- Hit Rate (Recall@K): Percentage of queries where at least one relevant item is retrieved
- Precision@K: Proportion of relevant items in top-K results
- Recall@K: Proportion of all relevant items that are retrieved in top-K
- Mean Reciprocal Rank (MRR): Average of reciprocal ranks of first relevant item
- Normalized Discounted Cumulative Gain (NDCG@K): Quality of ranking considering position

References:
- Manning et al., "Introduction to Information Retrieval" (2008)
- J rvelin & Kek l inen, "Cumulated gain-based evaluation of IR techniques" (2002)
"""

from typing import List, Set, Dict, Union, Optional
import numpy as np
from collections import defaultdict

from ..core.logger import get_logger

logger = get_logger("eval.retrieval")


def hit_rate(
    retrieved_lists: List[List[str]],
    relevant_sets: List[Set[str]],
    k: Optional[int] = None
) -> float:
    """
    Calculate Hit Rate (also known as Recall@K or Success@K).
    
    Hit rate measures the percentage of queries where at least one relevant
    item appears in the top-K retrieved results.
    
    Formula:
        hit_rate@K = (# queries with  1 relevant item in top-K) / (# total queries)
    
    Args:
        retrieved_lists: List of retrieved item IDs for each query
                        Format: [[query1_results], [query2_results], ...]
        relevant_sets: List of relevant item IDs for each query
                      Format: [{query1_relevant}, {query2_relevant}, ...]
        k: Consider only top-K results (None = use all results)
    
    Returns:
        Hit rate as a float between 0.0 and 1.0
    
    Example:
        >>> retrieved = [
        ...     ['doc1', 'doc2', 'doc3'],  # Query 1: doc1 is relevant
        ...     ['doc4', 'doc5', 'doc6'],  # Query 2: none relevant
        ...     ['doc7', 'doc8', 'doc9']   # Query 3: doc8 is relevant
        ... ]
        >>> relevant = [
        ...     {'doc1'},
        ...     {'doc2', 'doc3'},  # Neither in top results for query 2
        ...     {'doc8', 'doc10'}
        ... ]
        >>> hit_rate(retrieved, relevant, k=3)
        0.6666666666666666  # 2 out of 3 queries have hits
    
    Raises:
        ValueError: If retrieved_lists and relevant_sets have different lengths
        ValueError: If lists are empty
        ValueError: If k is negative
    """
    # Validation
    if len(retrieved_lists) != len(relevant_sets):
        raise ValueError(
            f"Mismatch: {len(retrieved_lists)} retrieved lists vs "
            f"{len(relevant_sets)} relevant sets"
        )
    
    if len(retrieved_lists) == 0:
        raise ValueError("Cannot calculate hit rate on empty lists")
    
    if k is not None and k < 0:
        raise ValueError(f"k must be non-negative, got {k}")
    
    hits = 0
    total_queries = len(retrieved_lists)
    
    for retrieved, relevant in zip(retrieved_lists, relevant_sets):
        if not isinstance(relevant, set):
            relevant = set(relevant)
        
        # Take top-K results
        top_k_retrieved = retrieved[:k] if k is not None else retrieved
        
        # Check if any retrieved item is relevant
        if any(item in relevant for item in top_k_retrieved):
            hits += 1
    
    hit_rate_value = hits / total_queries
    logger.debug(f"Hit Rate@{k}: {hit_rate_value:.4f} ({hits}/{total_queries})")
    
    return hit_rate_value


def precision_at_k(
    retrieved_lists: List[List[str]],
    relevant_sets: List[Set[str]],
    k: int
) -> float:
    """
    Calculate Precision@K averaged across all queries.
    
    Precision@K measures what proportion of the top-K retrieved items
    are actually relevant.
    
    Formula:
        precision@K = (# relevant items in top-K) / K
        Average across all queries
    
    Args:
        retrieved_lists: List of retrieved item IDs for each query
        relevant_sets: List of relevant item IDs for each query
        k: Number of top results to consider
    
    Returns:
        Average precision@K as a float between 0.0 and 1.0
    
    Example:
        >>> retrieved = [
        ...     ['doc1', 'doc2', 'doc3'],  # doc1, doc2 relevant
        ...     ['doc4', 'doc5', 'doc6']   # doc4 relevant
        ... ]
        >>> relevant = [
        ...     {'doc1', 'doc2'},
        ...     {'doc4', 'doc7'}
        ... ]
        >>> precision_at_k(retrieved, relevant, k=3)
        0.5  # (2/3 + 1/3) / 2 = 0.5
    
    Raises:
        ValueError: If retrieved_lists and relevant_sets have different lengths
        ValueError: If k is not positive
    """
    # Validation
    if len(retrieved_lists) != len(relevant_sets):
        raise ValueError(
            f"Mismatch: {len(retrieved_lists)} retrieved lists vs "
            f"{len(relevant_sets)} relevant sets"
        )
    
    if len(retrieved_lists) == 0:
        raise ValueError("Cannot calculate precision on empty lists")
    
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    
    precisions = []
    
    for retrieved, relevant in zip(retrieved_lists, relevant_sets):
        if not isinstance(relevant, set):
            relevant = set(relevant)
        
        # Take top-K results
        top_k_retrieved = retrieved[:k]
        
        if len(top_k_retrieved) == 0:
            precision = 0.0
        else:
            # Count how many retrieved items are relevant
            relevant_count = sum(1 for item in top_k_retrieved if item in relevant)
            precision = relevant_count / k
        
        precisions.append(precision)
    
    avg_precision = float(np.mean(precisions))
    logger.debug(f"Precision@{k}: {avg_precision:.4f}")
    
    return avg_precision


def recall_at_k(
    retrieved_lists: List[List[str]],
    relevant_sets: List[Set[str]],
    k: int
) -> float:
    """
    Calculate Recall@K averaged across all queries.
    
    Recall@K measures what proportion of all relevant items were retrieved
    in the top-K results.
    
    Formula:
        recall@K = (# relevant items in top-K) / (# total relevant items)
        Average across all queries
    
    Args:
        retrieved_lists: List of retrieved item IDs for each query
        relevant_sets: List of relevant item IDs for each query
        k: Number of top results to consider
    
    Returns:
        Average recall@K as a float between 0.0 and 1.0
    
    Example:
        >>> retrieved = [
        ...     ['doc1', 'doc2', 'doc3'],  # Got 2 out of 4 relevant
        ...     ['doc5', 'doc6', 'doc7']   # Got 1 out of 2 relevant
        ... ]
        >>> relevant = [
        ...     {'doc1', 'doc2', 'doc8', 'doc9'},  # 4 total
        ...     {'doc5', 'doc10'}                   # 2 total
        ... ]
        >>> recall_at_k(retrieved, relevant, k=3)
        0.5  # (2/4 + 1/2) / 2 = 0.5
    
    Note:
        Queries with no relevant items are excluded from the average
        to avoid division by zero and inflating the metric.
    
    Raises:
        ValueError: If retrieved_lists and relevant_sets have different lengths
        ValueError: If k is not positive
    """
    # Validation
    if len(retrieved_lists) != len(relevant_sets):
        raise ValueError(
            f"Mismatch: {len(retrieved_lists)} retrieved lists vs "
            f"{len(relevant_sets)} relevant sets"
        )
    
    if len(retrieved_lists) == 0:
        raise ValueError("Cannot calculate recall on empty lists")
    
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    
    recalls = []
    
    for retrieved, relevant in zip(retrieved_lists, relevant_sets):
        if not isinstance(relevant, set):
            relevant = set(relevant)
        
        # Skip queries with no relevant items
        if len(relevant) == 0:
            logger.warning("Query has no relevant items, skipping for recall calculation")
            continue
        
        # Take top-K results
        top_k_retrieved = retrieved[:k]
        
        # Count how many relevant items were retrieved
        relevant_count = sum(1 for item in top_k_retrieved if item in relevant)
        recall = relevant_count / len(relevant)
        
        recalls.append(recall)
    
    if len(recalls) == 0:
        logger.warning("No valid queries for recall calculation, returning 0.0")
        return 0.0
    
    avg_recall = float(np.mean(recalls))
    logger.debug(f"Recall@{k}: {avg_recall:.4f}")
    
    return avg_recall


def mean_reciprocal_rank(
    retrieved_lists: List[List[str]],
    relevant_sets: List[Set[str]]
) -> float:
    """
    Calculate Mean Reciprocal Rank (MRR).
    
    MRR measures how high the first relevant item appears in the ranking.
    It's the average of the reciprocal ranks of the first relevant item.
    
    Formula:
        RR = 1 / rank_of_first_relevant_item
        MRR = average(RR) across all queries
    
    Args:
        retrieved_lists: List of retrieved item IDs for each query
        relevant_sets: List of relevant item IDs for each query
    
    Returns:
        MRR as a float between 0.0 and 1.0
    
    Example:
        >>> retrieved = [
        ...     ['doc1', 'doc2', 'doc3'],  # First relevant at position 1 (RR=1.0)
        ...     ['doc4', 'doc5', 'doc6'],  # First relevant at position 2 (RR=0.5)
        ...     ['doc7', 'doc8', 'doc9']   # No relevant items (RR=0.0)
        ... ]
        >>> relevant = [
        ...     {'doc1'},
        ...     {'doc5'},
        ...     {'doc10'}
        ... ]
        >>> mean_reciprocal_rank(retrieved, relevant)
        0.5  # (1.0 + 0.5 + 0.0) / 3 = 0.5
    
    Note:
        - Ranks start at 1 (not 0)
        - If no relevant item is found, RR = 0
    
    Raises:
        ValueError: If retrieved_lists and relevant_sets have different lengths
        ValueError: If lists are empty
    """
    # Validation
    if len(retrieved_lists) != len(relevant_sets):
        raise ValueError(
            f"Mismatch: {len(retrieved_lists)} retrieved lists vs "
            f"{len(relevant_sets)} relevant sets"
        )
    
    if len(retrieved_lists) == 0:
        raise ValueError("Cannot calculate MRR on empty lists")
    
    reciprocal_ranks = []
    
    for retrieved, relevant in zip(retrieved_lists, relevant_sets):
        if not isinstance(relevant, set):
            relevant = set(relevant)
        
        # Find rank of first relevant item
        reciprocal_rank = 0.0
        for rank, item in enumerate(retrieved, start=1):
            if item in relevant:
                reciprocal_rank = 1.0 / rank
                break
        
        reciprocal_ranks.append(reciprocal_rank)
    
    mrr = float(np.mean(reciprocal_ranks))
    logger.debug(f"MRR: {mrr:.4f}")
    
    return mrr


def dcg_at_k(
    retrieved_list: List[str],
    relevant_set: Set[str],
    k: int
) -> float:
    """
    Calculate Discounted Cumulative Gain at K for a single query.
    
    DCG measures the quality of ranking by giving higher weight to relevant
    items that appear earlier in the results.
    
    Formula:
        DCG@K =  (i=1 to K) rel_i / log2(i + 1)
        where rel_i = 1 if item at position i is relevant, 0 otherwise
    
    Args:
        retrieved_list: Retrieved item IDs for the query
        relevant_set: Set of relevant item IDs for the query
        k: Number of top results to consider
    
    Returns:
        DCG@K as a float
    
    Example:
        >>> retrieved = ['doc1', 'doc4', 'doc2', 'doc5']  # doc1, doc2 relevant
        >>> relevant = {'doc1', 'doc2', 'doc3'}
        >>> dcg = dcg_at_k(retrieved, relevant, k=4)
        >>> # DCG = 1/log2(2) + 0/log2(3) + 1/log2(4) + 0/log2(5)
        >>> # DCG = 1.0 + 0.0 + 0.5 + 0.0 = 1.5
    
    Note:
        Uses log2(position + 1) as the discount factor
    
    Raises:
        ValueError: If k is not positive
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    
    if not isinstance(relevant_set, set):
        relevant_set = set(relevant_set)
    
    dcg = 0.0
    top_k = retrieved_list[:k]
    
    for position, item in enumerate(top_k, start=1):
        relevance = 1.0 if item in relevant_set else 0.0
        discount = np.log2(position + 1)
        dcg += relevance / discount
    
    return float(dcg)


def idcg_at_k(
    relevant_set: Set[str],
    k: int
) -> float:
    """
    Calculate Ideal Discounted Cumulative Gain at K.
    
    IDCG is the maximum possible DCG@K, achieved when all relevant items
    are ranked at the top positions.
    
    Args:
        relevant_set: Set of relevant item IDs
        k: Number of top results to consider
    
    Returns:
        IDCG@K as a float
    
    Example:
        >>> relevant = {'doc1', 'doc2', 'doc3'}
        >>> idcg = idcg_at_k(relevant, k=5)
        >>> # IDCG = 1/log2(2) + 1/log2(3) + 1/log2(4) + 0/log2(5) + 0/log2(6)
        >>> # IDCG = 1.0 + 0.631 + 0.5 = 2.131
    
    Raises:
        ValueError: If k is not positive
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    
    if not isinstance(relevant_set, set):
        relevant_set = set(relevant_set)
    
    # Number of relevant items that can appear in top-K
    num_relevant = min(len(relevant_set), k)
    
    idcg = 0.0
    for position in range(1, num_relevant + 1):
        relevance = 1.0
        discount = np.log2(position + 1)
        idcg += relevance / discount
    
    return float(idcg)


def ndcg_at_k(
    retrieved_lists: List[List[str]],
    relevant_sets: List[Set[str]],
    k: int
) -> float:
    """
    Calculate Normalized Discounted Cumulative Gain at K.
    
    NDCG normalizes DCG by the ideal DCG (IDCG), producing a score between
    0 and 1 that measures ranking quality while accounting for position.
    
    Formula:
        NDCG@K = DCG@K / IDCG@K
        Average across all queries
    
    Args:
        retrieved_lists: List of retrieved item IDs for each query
        relevant_sets: List of relevant item IDs for each query
        k: Number of top results to consider
    
    Returns:
        Average NDCG@K as a float between 0.0 and 1.0
    
    Example:
        >>> retrieved = [
        ...     ['doc1', 'doc4', 'doc2'],  # doc1, doc2 relevant (positions 1, 3)
        ...     ['doc5', 'doc6', 'doc7']   # doc6 relevant (position 2)
        ... ]
        >>> relevant = [
        ...     {'doc1', 'doc2', 'doc3'},
        ...     {'doc6'}
        ... ]
        >>> ndcg_at_k(retrieved, relevant, k=3)
        # Query 1: DCG = 1/log2(2) + 1/log2(4), IDCG = 1/log2(2) + 1/log2(3) + 1/log2(4)
        # Query 2: DCG = 1/log2(3), IDCG = 1/log2(2)
        # Average NDCG
    
    Note:
        - Queries with no relevant items are excluded to avoid division by zero
        - Perfect ranking (all relevant items at top) gives NDCG = 1.0
    
    Raises:
        ValueError: If retrieved_lists and relevant_sets have different lengths
        ValueError: If k is not positive
    """
    # Validation
    if len(retrieved_lists) != len(relevant_sets):
        raise ValueError(
            f"Mismatch: {len(retrieved_lists)} retrieved lists vs "
            f"{len(relevant_sets)} relevant sets"
        )
    
    if len(retrieved_lists) == 0:
        raise ValueError("Cannot calculate NDCG on empty lists")
    
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    
    ndcg_scores = []
    
    for retrieved, relevant in zip(retrieved_lists, relevant_sets):
        if not isinstance(relevant, set):
            relevant = set(relevant)
        
        # Skip queries with no relevant items
        if len(relevant) == 0:
            logger.warning("Query has no relevant items, skipping for NDCG calculation")
            continue
        
        # Calculate DCG and IDCG
        dcg = dcg_at_k(retrieved, relevant, k)
        idcg = idcg_at_k(relevant, k)
        
        # Normalize
        if idcg > 0:
            ndcg = dcg / idcg
        else:
            ndcg = 0.0
        
        ndcg_scores.append(ndcg)
    
    if len(ndcg_scores) == 0:
        logger.warning("No valid queries for NDCG calculation, returning 0.0")
        return 0.0
    
    avg_ndcg = float(np.mean(ndcg_scores))
    logger.debug(f"NDCG@{k}: {avg_ndcg:.4f}")
    
    return avg_ndcg


def evaluate_retrieval(
    retrieved_lists: List[List[str]],
    relevant_sets: List[Set[str]],
    k_values: List[int] = [1, 3, 5, 10]
) -> Dict[str, float]:
    """
    Calculate all retrieval metrics for multiple k values.
    
    This is a convenience function that computes all metrics at once.
    
    Args:
        retrieved_lists: List of retrieved item IDs for each query
        relevant_sets: List of relevant item IDs for each query
        k_values: List of k values to evaluate at
    
    Returns:
        Dictionary with all metrics:
        {
            'hit_rate@1': ...,
            'hit_rate@3': ...,
            'precision@1': ...,
            'recall@1': ...,
            'ndcg@1': ...,
            'mrr': ...
        }
    
    Example:
        >>> retrieved = [['doc1', 'doc2'], ['doc3', 'doc4']]
        >>> relevant = [{'doc1'}, {'doc4'}]
        >>> metrics = evaluate_retrieval(retrieved, relevant, k_values=[1, 2])
        >>> print(metrics)
        {
            'hit_rate@1': 0.5,
            'hit_rate@2': 1.0,
            'precision@1': 0.5,
            'precision@2': 0.5,
            'recall@1': 0.5,
            'recall@2': 1.0,
            'ndcg@1': 0.5,
            'ndcg@2': 0.863,
            'mrr': 0.75
        }
    
    Raises:
        ValueError: If validation fails for any metric
    """
    logger.info(f"Evaluating retrieval metrics for {len(retrieved_lists)} queries")
    
    metrics = {}
    
    # Calculate metrics for each k
    for k in k_values:
        try:
            metrics[f'hit_rate@{k}'] = hit_rate(retrieved_lists, relevant_sets, k)
            metrics[f'precision@{k}'] = precision_at_k(retrieved_lists, relevant_sets, k)
            metrics[f'recall@{k}'] = recall_at_k(retrieved_lists, relevant_sets, k)
            metrics[f'ndcg@{k}'] = ndcg_at_k(retrieved_lists, relevant_sets, k)
        except Exception as e:
            logger.error(f"Error calculating metrics at k={k}: {e}")
            raise
    
    # MRR (not k-dependent)
    try:
        metrics['mrr'] = mean_reciprocal_rank(retrieved_lists, relevant_sets)
    except Exception as e:
        logger.error(f"Error calculating MRR: {e}")
        raise
    
    logger.info(f"Evaluation complete: {len(metrics)} metrics calculated")
    
    return metrics


def print_metrics(metrics: Dict[str, float], title: str = "Retrieval Metrics") -> None:
    """
    Pretty-print retrieval metrics.
    
    Args:
        metrics: Dictionary of metric names and values
        title: Title for the metrics report
    
    Example:
        >>> metrics = {
        ...     'hit_rate@5': 0.8,
        ...     'precision@5': 0.6,
        ...     'recall@5': 0.75,
        ...     'ndcg@5': 0.82,
        ...     'mrr': 0.71
        ... }
        >>> print_metrics(metrics)
        
        ============================================================
        Retrieval Metrics
        ============================================================
        hit_rate@5     : 0.8000
        precision@5    : 0.6000
        recall@5       : 0.7500
        ndcg@5         : 0.8200
        mrr            : 0.7100
        ============================================================
    """
    print("\n" + "="*60)
    print(title)
    print("="*60)
    
    for metric_name, value in sorted(metrics.items()):
        print(f"{metric_name:15s}: {value:.4f}")
    
    print("="*60 + "\n")
