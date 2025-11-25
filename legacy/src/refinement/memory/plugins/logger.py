"""
Logger Plugin

Logs rounds to JSONL for experiment tracking.
"""

from typing import Dict, Any
from datetime import datetime
from pathlib import Path
import json
from ....core.logger import get_logger

logger = get_logger("refinement.memory.logger")


class LoggerPlugin:
    """
    Logger plugin - logs rounds to JSONL.
    
    Logs are written to: logs/runs/{experiment_id}.jsonl
    """
    
    def __init__(self):
        """Initialize logger plugin"""
        self.log_dir = Path("logs/runs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("LoggerPlugin initialized")
    
    def log(
        self,
        experiment_id: str,
        question_id: str,
        round_num: int,
        question: str,
        student_answer: str,
        evaluation: Dict[str, Any]
    ):
        """
        Log round to JSONL.
        
        Args:
            experiment_id: Experiment ID
            question_id: Question ID
            round_num: Round number
            question: Question text
            student_answer: Student's answer
            evaluation: Teacher evaluation result
        """
        log_file = self.log_dir / f"{experiment_id}.jsonl"
        
        # Build log record
        round_log = {
            "experiment_id": experiment_id,
            "question_id": question_id,
            "round": round_num,
            "question": question,
            "student_answer": student_answer,
            "evaluation": evaluation["evaluation"],
            "reasoning": evaluation["reasoning"],
            "hint": evaluation["hint"],
            "stop_score": evaluation["stop_score"],
            "should_stop": evaluation.get("should_stop", False),
            "error_keys": evaluation.get("error_keys", []),
            "timestamp": datetime.now().isoformat()
        }
        
        # Write to file (append mode)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(round_log, ensure_ascii=False) + "\n")
        
        logger.debug(f"Logged round {round_num} to {log_file}")
