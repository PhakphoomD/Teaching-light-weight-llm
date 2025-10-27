"""
Visualization Utilities

Generate charts and reports for experiment results.
"""

from typing import List, Dict, Any
import json


def generate_ascii_chart(
    labels: List[str],
    values: List[float],
    title: str = "Chart",
    max_width: int = 50
) -> str:
    """
    Generate ASCII bar chart.
    
    Args:
        labels: Category labels
        values: Values for each label
        title: Chart title
        max_width: Maximum bar width
        
    Returns:
        ASCII chart string
    """
    if not labels or not values:
        return "No data to display"
    
    max_value = max(values)
    chart = [f"\n{title}\n" + "=" * (max_width + 20)]
    
    for label, value in zip(labels, values):
        bar_length = int((value / max_value) * max_width) if max_value > 0 else 0
        bar = "█" * bar_length
        chart.append(f"{label:<15} {bar} {value:.2f}")
    
    chart.append("=" * (max_width + 20))
    return "\n".join(chart)


def generate_success_rate_chart(
    experiments: List[str],
    success_rates: List[float]
) -> str:
    """
    Generate success rate comparison chart.
    
    Args:
        experiments: Experiment names
        success_rates: Success rates (0-1)
        
    Returns:
        ASCII chart
    """
    percentages = [rate * 100 for rate in success_rates]
    return generate_ascii_chart(
        labels=experiments,
        values=percentages,
        title="Success Rate Comparison (%)",
        max_width=50
    )


def generate_time_chart(
    experiments: List[str],
    times_ms: List[float]
) -> str:
    """
    Generate execution time comparison chart.
    
    Args:
        experiments: Experiment names
        times_ms: Average times in milliseconds
        
    Returns:
        ASCII chart
    """
    return generate_ascii_chart(
        labels=experiments,
        values=times_ms,
        title="Average Time per Task (ms)",
        max_width=50
    )


def generate_report(
    model_name: str,
    experiments: List[str],
    summaries: List[Dict[str, Any]]
) -> str:
    """
    Generate comprehensive text report.
    
    Args:
        model_name: Model name
        experiments: Experiment names
        summaries: Summary dictionaries for each experiment
        
    Returns:
        Formatted report string
    """
    report = []
    report.append("=" * 80)
    report.append(f"EXPERIMENT REPORT - {model_name.upper()}")
    report.append("=" * 80)
    report.append("")
    
    # Success rates
    success_rates = [s.get("success_rate", 0.0) for s in summaries]
    report.append(generate_success_rate_chart(experiments, success_rates))
    report.append("")
    
    # Detailed table
    report.append("Detailed Metrics:")
    report.append("-" * 80)
    report.append(f"{'Experiment':<20} {'Success':<10} {'Attempts':<10} {'Time(ms)':<12} {'Runtime(s)':<12}")
    report.append("-" * 80)
    
    for exp, summary in zip(experiments, summaries):
        report.append(
            f"{exp:<20} "
            f"{summary.get('success_rate', 0)*100:>8.1f}% "
            f"{summary.get('avg_attempts', 0):>8.1f} "
            f"{summary.get('avg_total_ms', 0):>10.0f} "
            f"{summary.get('total_runtime_s', 0):>10.1f}"
        )
    
    report.append("=" * 80)
    
    return "\n".join(report)


def save_report(report: str, output_path: str) -> None:
    """
    Save report to file.
    
    Args:
        report: Report string
        output_path: Output file path
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)


if __name__ == "__main__":
    # Example usage
    experiments = ["baseline", "memory_tfidf", "memory_rulekey"]
    success_rates = [0.45, 0.65, 0.70]
    
    chart = generate_success_rate_chart(experiments, success_rates)
    print(chart)
