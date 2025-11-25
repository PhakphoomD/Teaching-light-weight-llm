"""
Evaluation Module

Metrics and tools for evaluating the teaching system.
"""

from .retrieval import (
    hit_rate,
    precision_at_k,
    recall_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    evaluate_retrieval,
    print_metrics
)

__all__ = [
    'hit_rate',
    'precision_at_k',
    'recall_at_k',
    'mean_reciprocal_rank',
    'ndcg_at_k',
    'evaluate_retrieval',
    'print_metrics'
]
