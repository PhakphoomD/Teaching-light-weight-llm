"""
Evaluation metrics
"""
from typing import List, Dict, Any


def calculate_success_rate(results: List[Dict[str, Any]]) -> float:
    """Calculate success rate from results."""
    if not results:
        return 0.0
    passed = sum(1 for r in results if r.get("passed", False))
    return passed / len(results)


def calculate_avg_attempts(results: List[Dict[str, Any]]) -> float:
    """Calculate average attempts from results."""
    if not results:
        return 0.0
    total_attempts = sum(r.get("attempts", 0) for r in results)
    return total_attempts / len(results)


def calculate_avg_time(results: List[Dict[str, Any]]) -> float:
    """Calculate average time (ms) from results."""
    if not results:
        return 0.0
    total_time = sum(r.get("total_time_ms", 0) for r in results)
    return total_time / len(results)
