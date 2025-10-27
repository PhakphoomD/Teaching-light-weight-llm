"""
A/B Testing Analysis

Analyze and compare A/B test results.
"""

from typing import Dict, List, Any
from dataclasses import dataclass
import json


@dataclass
class ABTestResult:
    """A/B test result summary."""
    variant_a: str
    variant_b: str
    a_success_rate: float
    b_success_rate: float
    improvement: float
    a_avg_attempts: float
    b_avg_attempts: float
    a_avg_time_ms: float
    b_avg_time_ms: float
    statistical_significant: bool = False


def analyze_ab_test(
    results_a: List[Dict[str, Any]],
    results_b: List[Dict[str, Any]],
    variant_a_name: str = "A",
    variant_b_name: str = "B"
) -> ABTestResult:
    """
    Analyze A/B test results.
    
    Args:
        results_a: Task results for variant A
        results_b: Task results for variant B
        variant_a_name: Name of variant A
        variant_b_name: Name of variant B
        
    Returns:
        ABTestResult object
    """
    # Variant A metrics
    a_passed = sum(1 for r in results_a if r.get("passed", False))
    a_success_rate = a_passed / len(results_a) if results_a else 0.0
    a_avg_attempts = sum(r.get("attempts", 0) for r in results_a) / len(results_a) if results_a else 0.0
    a_avg_time = sum(r.get("total_time_ms", 0) for r in results_a) / len(results_a) if results_a else 0.0
    
    # Variant B metrics
    b_passed = sum(1 for r in results_b if r.get("passed", False))
    b_success_rate = b_passed / len(results_b) if results_b else 0.0
    b_avg_attempts = sum(r.get("attempts", 0) for r in results_b) / len(results_b) if results_b else 0.0
    b_avg_time = sum(r.get("total_time_ms", 0) for r in results_b) / len(results_b) if results_b else 0.0
    
    # Improvement
    improvement = ((b_success_rate - a_success_rate) / a_success_rate * 100) if a_success_rate > 0 else 0.0
    
    # TODO: Add statistical significance test (chi-square, t-test)
    statistical_significant = abs(improvement) > 10.0  # Placeholder
    
    return ABTestResult(
        variant_a=variant_a_name,
        variant_b=variant_b_name,
        a_success_rate=a_success_rate,
        b_success_rate=b_success_rate,
        improvement=improvement,
        a_avg_attempts=a_avg_attempts,
        b_avg_attempts=b_avg_attempts,
        a_avg_time_ms=a_avg_time,
        b_avg_time_ms=b_avg_time,
        statistical_significant=statistical_significant
    )


def print_ab_result(result: ABTestResult) -> None:
    """
    Print A/B test result.
    
    Args:
        result: ABTestResult object
    """
    print("\n" + "=" * 80)
    print("A/B TEST RESULTS")
    print("=" * 80)
    
    print(f"\nVariant A ({result.variant_a}):")
    print(f"  Success Rate: {result.a_success_rate*100:.1f}%")
    print(f"  Avg Attempts: {result.a_avg_attempts:.1f}")
    print(f"  Avg Time: {result.a_avg_time_ms:.0f}ms")
    
    print(f"\nVariant B ({result.variant_b}):")
    print(f"  Success Rate: {result.b_success_rate*100:.1f}%")
    print(f"  Avg Attempts: {result.b_avg_attempts:.1f}")
    print(f"  Avg Time: {result.b_avg_time_ms:.0f}ms")
    
    print(f"\nImprovement: {result.improvement:+.1f}%")
    
    if result.statistical_significant:
        print("Statistical Significance: YES ✓")
    else:
        print("Statistical Significance: NO")
    
    print("=" * 80)


def save_ab_analysis(result: ABTestResult, output_path: str) -> None:
    """
    Save A/B analysis to JSON.
    
    Args:
        result: ABTestResult object
        output_path: Output file path
    """
    data = {
        "variant_a": result.variant_a,
        "variant_b": result.variant_b,
        "a_success_rate": result.a_success_rate,
        "b_success_rate": result.b_success_rate,
        "improvement_percent": result.improvement,
        "a_avg_attempts": result.a_avg_attempts,
        "b_avg_attempts": result.b_avg_attempts,
        "a_avg_time_ms": result.a_avg_time_ms,
        "b_avg_time_ms": result.b_avg_time_ms,
        "statistical_significant": result.statistical_significant
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
