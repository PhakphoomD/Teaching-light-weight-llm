"""
Simplified Logger Module

Fixed-width formatting for easy debugging and analysis.

Key features:
1. Fixed-width columns for aligned output
2. Both console and JSONL logging
3. Color-coded output (optional)
4. Easy to read during debugging

Output format:
┌──────┬─────────────────┬──────────────┬───────────┬─────────┬──────┐
│Round │ Answer          │ Scores       │ Final     │ Passed  │ Time │
├──────┼─────────────────┼──────────────┼───────────┼─────────┼──────┤
│  1   │ Paris           │ F1:0.85 B... │ 0.825     │   1     │ 234ms│
│  2   │ London          │ F1:0.42 B... │ 0.401     │   0     │ 198ms│
└──────┴─────────────────┴──────────────┴───────────┴─────────┴──────┘
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class RoundLogger:
    """
    Logger with fixed-width formatting for debugging.
    
    Features:
    - Fixed-width columns (aligned output)
    - Console + JSONL dual logging
    - Easy to scan visually
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize round logger.
        
        Args:
            config: Logging configuration dict with:
                - debug: Enable debug output (default: True)
                - save_rounds: Save to JSONL (default: True)
                - log_path: Base path for logs (default: "logs/simplified")
        """
        self.config = config
        self.debug = config.get('debug', True)
        self.save_rounds = config.get('save_rounds', True)
        
        # Log paths
        log_dir = Path(config.get('log_path', 'logs/simplified'))
        log_dir.mkdir(parents=True, exist_ok=True)
        
        self.rounds_path = log_dir / 'debug_rounds.jsonl'
        self.metrics_path = log_dir / 'metrics_per_question.json'
        
        # Accumulate metrics for final export
        self._metrics_data = {}
        
        # Column widths for fixed-width output (compact for readability)
        self.col_widths = {
            'round': 5,
            'answer': 25,
            'scores': 30,
            'final': 8,
            'passed': 6,
            'feedback_id': 10,
            'time': 7
        }
        
        # Print header on first use
        self._header_printed = False
    
    def log_round(self,
                  round_num: int,
                  question: str,
                  answer: str,
                  scores: Dict[str, float],
                  passed: bool,
                  feedback_id: Optional[str] = None,
                  time_ms: int = 0):
        """
        Log a single round with fixed-width formatting.
        
        Args:
            round_num: Round number
            question: The question (for JSONL only)
            answer: Student's answer
            scores: Dict of metric scores
            passed: Whether answer passed
            feedback_id: Memory feedback ID used (if any)
            time_ms: Time taken in milliseconds
        """
        # Print header if first time
        if self.debug and not self._header_printed:
            self._print_header()
            self._header_printed = True
        
        # Prepare data
        final_score = scores.get('final', 0.0)
        
        # Format scores string (compact)
        scores_str = self._format_scores(scores)
        
        # Truncate answer if too long
        answer_display = self._truncate(answer, self.col_widths['answer'])
        
        # Truncate feedback_id
        feedback_display = self._truncate(
            feedback_id or '-',
            self.col_widths['feedback_id']
        )
        
        # Format console output (fixed-width)
        if self.debug:
            line = (
                f"│ {round_num:^{self.col_widths['round']-2}} "
                f"│ {answer_display:<{self.col_widths['answer']}} "
                f"│ {scores_str:<{self.col_widths['scores']}} "
                f"│ {final_score:>{self.col_widths['final']-2}.3f} "
                f"│ {'[OK]' if passed else '[FAIL]':^{self.col_widths['passed']-2}} "
                f"│ {feedback_display:>{self.col_widths['feedback_id']}} "
                f"│ {time_ms:>{self.col_widths['time']-3}}ms │"
            )
            # Removed: print(line) - now using terminal_ui instead
        
        # Save to JSONL
        if self.save_rounds:
            record = {
                'round': round_num,
                'timestamp': datetime.now().isoformat(),
                'question': question,
                'answer': answer,
                'scores': scores,
                'final_score': final_score,
                'passed': passed,
                'feedback_id': feedback_id,
                'time_ms': time_ms
            }
            self._save_jsonl(record)
    
    def _print_header(self):
        """Print table header (DISABLED - now using terminal_ui)."""
        pass
    
    def print_footer(self):
        """Print table footer (DISABLED - now using terminal_ui)."""
        self._header_printed = False
    
    def _format_scores(self, scores: Dict[str, float]) -> str:
        """
        Format scores into compact string.
        
        Args:
            scores: Dict of scores
        
        Returns:
            Compact string like "EM:1.0 F1:0.85 B:0.72 T:0.90"
        """
        parts = []
        
        # Short names for metrics (new: T, SemSim, ROUGE-L, EM)
        abbrev = {
            'teacher_score': 'T',
            'semantic_sim': 'Sem',
            'rouge_l': 'R-L',
            'exact_match': 'EM'
        }
        
        for key in ['teacher_score', 'semantic_sim', 'rouge_l', 'exact_match']:
            if key in scores:
                short_name = abbrev.get(key, key[:2].upper())
                parts.append(f"{short_name}:{scores[key]:.2f}")
        
        return " ".join(parts)
    
    def _truncate(self, text: str, max_len: int) -> str:
        """
        Truncate text to max length with ellipsis.
        
        Args:
            text: Input text
            max_len: Maximum length
        
        Returns:
            Truncated text
        """
        if len(text) <= max_len:
            return text
        return text[:max_len-3] + "..."
    
    def _save_jsonl(self, record: Dict[str, Any]):
        """Append record to JSONL file."""
        try:
            with open(self.rounds_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[WARNING] Error saving log: {e}")
    
    def accumulate_metrics(self, 
                           question_id: str,
                           round_num: int,
                           scores: Dict[str, float],
                           answer: str,
                           passed: bool,
                           teacher_feedback: Optional[str] = None):
        """
        Accumulate metrics for later export.
        
        Args:
            question_id: Question identifier (e.g., "alpaca-0")
            round_num: Round/attempt number
            scores: Dict of metric scores
            answer: Student's answer
            passed: Whether answer passed
            teacher_feedback: Feedback given by teacher (if any)
        """
        if question_id not in self._metrics_data:
            self._metrics_data[question_id] = {
                'question_id': question_id,
                'attempts': []
            }
        
        # Add this attempt
        self._metrics_data[question_id]['attempts'].append({
            'round': round_num,
            'teacher_score': scores.get('teacher_score', 0.0),
            'semantic_sim': scores.get('semantic_sim', 0.0),
            'rouge_l': scores.get('rouge_l', 0.0),
            'exact_match': scores.get('exact_match', 0.0),
            'final_score': scores.get('final', 0.0),
            'passed': passed,
            'teacher_feedback': teacher_feedback or '(No feedback yet)'
        })
    
    def save_metrics_json(self):
        """
        Save accumulated metrics to JSON file for visualization.
        
        Output format:
        {
            "alpaca-0": {
                "question_id": "alpaca-0",
                "attempts": [
                    {
                        "round": 1,
                        "teacher_score": 0.5,
                        "semantic_sim": 0.55,
                        "rouge_l": 0.64,
                        "exact_match": 0.0,
                        "final_score": 0.487,
                        "passed": false,
                        "teacher_feedback": "Error: Random Forest is overkill. Fix: Use Logistic Regression."
                    },
                    {...}
                ]
            },
            ...
        }
        
        Use this file to:
        - Visualize learning progress across attempts
        - Analyze which feedback types are most effective
        - Identify common mistakes and correction patterns
        """
        try:
            with open(self.metrics_path, 'w', encoding='utf-8') as f:
                json.dump(self._metrics_data, f, indent=2, ensure_ascii=False)
            print(f"[Docs] Metrics saved to: {self.metrics_path}")
        except Exception as e:
            print(f"[WARNING] Error saving metrics: {e}")
    
    def log_summary(self, summary: Dict[str, Any]):
        """
        Log experiment summary.
        
        Args:
            summary: Summary dict with metrics
        """
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Success Rate: {summary.get('success_rate', 0)*100:.1f}%")
        print(f"Avg Rounds: {summary.get('avg_rounds', 0):.2f}")
        print(f"Total Questions: {summary.get('total_questions', 0)}")
        print(f"Memory Hit Rate: {summary.get('memory_hit_rate', 0)*100:.1f}%")
        print("="*80 + "\n")


# Example usage and testing
if __name__ == "__main__":
    # Mock config
    config = {
        'debug': True,
        'save_rounds': True,
        'log_path': 'logs/simplified/test'
    }
    
    print("="*80)
    print("Testing Round Logger")
    print("="*80)
    print()
    
    logger = RoundLogger(config)
    
    # Simulate a teaching loop
    test_data = [
        {
            'round': 1,
            'question': 'What is the capital of France?',
            'answer': 'Paris',
            'scores': {
                'exact_match': 1.0,
                'f1': 1.0,
                'bleu': 1.0,
                'teacher_score': 1.0,
                'final': 1.0
            },
            'passed': True,
            'feedback_id': None,
            'time_ms': 234
        },
        {
            'round': 1,
            'question': 'Separate: helloworld',
            'answer': 'hello world',
            'scores': {
                'exact_match': 0.0,
                'f1': 0.67,
                'bleu': 0.58,
                'teacher_score': 0.70,
                'final': 0.601
            },
            'passed': False,
            'feedback_id': None,
            'time_ms': 198
        },
        {
            'round': 2,
            'question': 'Separate: helloworld',
            'answer': 'hello + world',
            'scores': {
                'exact_match': 1.0,
                'f1': 0.85,
                'bleu': 0.79,
                'teacher_score': 0.95,
                'final': 0.882
            },
            'passed': True,
            'feedback_id': 'abc123def456',
            'time_ms': 215
        }
    ]
    
    for data in test_data:
        logger.log_round(
            round_num=data['round'],
            question=data['question'],
            answer=data['answer'],
            scores=data['scores'],
            passed=data['passed'],
            feedback_id=data['feedback_id'],
            time_ms=data['time_ms']
        )
    
    logger.print_footer()
    
    # Log summary
    logger.log_summary({
        'success_rate': 0.67,
        'avg_rounds': 1.33,
        'total_questions': 3,
        'memory_hit_rate': 0.33
    })
    
    print(f"\n Logs saved to: {logger.rounds_path}")
