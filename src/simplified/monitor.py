"""
Simplified Performance Monitor

Tracks and reports key metrics across all questions.

Key metrics:
1. Success rate (% of questions answered correctly)
2. Average rounds per question
3. Average tokens per question
4. Memory hit rate (% of times memory was used)
5. Performance by question type (if available)
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


class PerformanceMonitor:
    """
    Monitor and track performance metrics.
    
    Tracks:
    - Success rate
    - Average rounds
    - Token usage
    - Memory effectiveness
    - Time spent
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize performance monitor.
        
        Args:
            config: Logging configuration dict with:
                - log_path: Base path for logs (default: "logs/simplified")
        """
        self.config = config
        
        # Results storage
        self.results: List[Dict[str, Any]] = []
        
        # Aggregated stats
        self.stats = {
            'total_questions': 0,
            'success_count': 0,
            'total_rounds': 0,
            'total_tokens': 0,
            'total_time_ms': 0,
            'memory_used_count': 0
        }
        
        # Output path
        log_dir = Path(config.get('log_path', 'logs/simplified'))
        log_dir.mkdir(parents=True, exist_ok=True)
        self.performance_path = log_dir / 'performance.json'
    
    def record_result(self, result: Dict[str, Any]):
        """
        Record result from a single question.
        
        Args:
            result: Result dict with keys:
                - success: bool
                - num_rounds: int
                - final_score: float
                - history: List[Dict] (round details)
        """
        self.results.append(result)
        
        # Update aggregated stats
        self.stats['total_questions'] += 1
        
        if result.get('success', False):
            self.stats['success_count'] += 1
        
        self.stats['total_rounds'] += result.get('num_rounds', 0)
        
        # Count memory usage from history
        history = result.get('history', [])
        for round_data in history:
            if round_data.get('feedback_used'):
                self.stats['memory_used_count'] += 1
            
            # Accumulate time
            self.stats['total_time_ms'] += round_data.get('time_ms', 0)
            
            # Token counting requires access to model responses
            # Current implementation tracks time-based metrics only
    
    def get_report(self) -> Dict[str, Any]:
        """
        Generate performance report.
        
        Returns:
            Dict with:
            - success_rate: float (0-1)
            - avg_rounds: float
            - avg_tokens: float (if tracked)
            - memory_hit_rate: float (0-1)
            - total_questions: int
            - total_time_seconds: float
        """
        total = self.stats['total_questions']
        
        if total == 0:
            return {
                'success_rate': 0.0,
                'avg_rounds': 0.0,
                'avg_tokens': 0.0,
                'memory_hit_rate': 0.0,
                'total_questions': 0,
                'total_time_seconds': 0.0
            }
        
        # Calculate rates
        success_rate = self.stats['success_count'] / total
        avg_rounds = self.stats['total_rounds'] / total
        
        # Memory hit rate (per question, not per round)
        # Count questions where memory was used at least once
        questions_with_memory = len([
            r for r in self.results 
            if any(round_data.get('feedback_used') for round_data in r.get('history', []))
        ])
        memory_hit_rate = questions_with_memory / total if total > 0 else 0.0
        
        # Token usage (placeholder - requires instrumentation)
        avg_tokens = self.stats['total_tokens'] / total if total > 0 else 0.0
        
        # Time
        total_time_seconds = self.stats['total_time_ms'] / 1000.0
        
        return {
            'success_rate': success_rate,
            'avg_rounds': avg_rounds,
            'avg_tokens': avg_tokens,
            'memory_hit_rate': memory_hit_rate,
            'total_questions': total,
            'success_count': self.stats['success_count'],
            'total_rounds': self.stats['total_rounds'],
            'total_time_seconds': total_time_seconds,
            'avg_time_per_question_ms': self.stats['total_time_ms'] / total if total > 0 else 0.0
        }
    
    def save_report(self, output_path: str = None):
        """
        Save performance report to JSON file.
        
        Args:
            output_path: Override default output path
        """
        if output_path is None:
            output_path = self.performance_path
        
        report = self.get_report()
        
        # Add detailed results
        full_report = {
            'summary': report,
            'timestamp': datetime.now().isoformat(),
            'detailed_results': self.results
        }
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(full_report, f, indent=2, ensure_ascii=False)
            print(f"[OK] Performance report saved to: {output_path}")
        except Exception as e:
            print(f"[WARNING] Error saving report: {e}")
    
    def print_report(self):
        """Print performance report to console."""
        report = self.get_report()
        
        print("\n" + "="*80)
        print("PERFORMANCE REPORT")
        print("="*80)
        print(f"Total Questions:      {report['total_questions']}")
        print(f"Successful:           {report['success_count']}")
        print(f"Success Rate:         {report['success_rate']*100:.1f}%")
        print(f"Average Rounds:       {report['avg_rounds']:.2f}")
        print(f"Memory Hit Rate:      {report['memory_hit_rate']*100:.1f}%")
        print(f"Total Time:           {report['total_time_seconds']:.2f}s")
        print(f"Avg Time/Question:    {report['avg_time_per_question_ms']:.0f}ms")
        print("="*80 + "\n")
    
    def get_failure_analysis(self) -> Dict[str, Any]:
        """
        Analyze failed questions for patterns.
        
        Returns:
            Dict with failure analysis
        """
        failed_results = [r for r in self.results if not r.get('success', False)]
        
        if not failed_results:
            return {
                'total_failures': 0,
                'common_patterns': []
            }
        
        # Analyze patterns
        avg_final_score = sum(
            r.get('final_score', 0) for r in failed_results
        ) / len(failed_results)
        
        avg_rounds_for_failures = sum(
            r.get('num_rounds', 0) for r in failed_results
        ) / len(failed_results)
        
        return {
            'total_failures': len(failed_results),
            'failure_rate': len(failed_results) / len(self.results),
            'avg_final_score_on_failures': avg_final_score,
            'avg_rounds_for_failures': avg_rounds_for_failures
        }


# Example usage and testing
if __name__ == "__main__":
    # Mock config
    config = {
        'log_path': 'logs/simplified/test'
    }
    
    print("="*80)
    print("Testing Performance Monitor")
    print("="*80)
    
    monitor = PerformanceMonitor(config)
    
    # Simulate results from 5 questions
    test_results = [
        {
            'success': True,
            'num_rounds': 1,
            'final_score': 1.0,
            'history': [
                {'feedback_used': None, 'time_ms': 234}
            ]
        },
        {
            'success': False,
            'num_rounds': 3,
            'final_score': 0.65,
            'history': [
                {'feedback_used': None, 'time_ms': 198},
                {'feedback_used': 'abc123', 'time_ms': 215},
                {'feedback_used': 'abc123', 'time_ms': 203}
            ]
        },
        {
            'success': True,
            'num_rounds': 2,
            'final_score': 0.92,
            'history': [
                {'feedback_used': None, 'time_ms': 187},
                {'feedback_used': 'def456', 'time_ms': 201}
            ]
        },
        {
            'success': True,
            'num_rounds': 1,
            'final_score': 0.98,
            'history': [
                {'feedback_used': None, 'time_ms': 224}
            ]
        },
        {
            'success': False,
            'num_rounds': 3,
            'final_score': 0.71,
            'history': [
                {'feedback_used': None, 'time_ms': 195},
                {'feedback_used': 'ghi789', 'time_ms': 208},
                {'feedback_used': 'ghi789', 'time_ms': 199}
            ]
        }
    ]
    
    print("\nRecording results...")
    for i, result in enumerate(test_results, 1):
        monitor.record_result(result)
        print(f"  Question {i}: {'[OK]' if result['success'] else '[FAIL]'} "
              f"({result['num_rounds']} rounds, score={result['final_score']:.3f})")
    
    # Print report
    monitor.print_report()
    
    # Failure analysis
    print("\n" + "="*80)
    print("FAILURE ANALYSIS")
    print("="*80)
    failure_analysis = monitor.get_failure_analysis()
    print(json.dumps(failure_analysis, indent=2))
    print()
    
    # Save report
    monitor.save_report()
    
    print(f"\n[OK] Full report saved to: {monitor.performance_path}")
