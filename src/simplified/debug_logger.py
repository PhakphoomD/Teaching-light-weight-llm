"""
Debug Logger - Full Logging for Debugging
==========================================
Logs everything (parameters, inputs, outputs, scores) to JSON files
for detailed debugging without cluttering terminal.

File format: logs/simplified/debug/YYYYMMDD_HHMMSS.json
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class DebugLogger:
    """Comprehensive debug logger for teaching loop"""
    
    def __init__(self, base_dir: str = "logs/simplified/debug"):
        """
        Initialize debug logger
        
        Args:
            base_dir: Base directory for debug logs
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.base_dir / f"{timestamp}.json"
        # Optional flat per-round JSONL file for easier inspection
        self.flat_log_file = self.base_dir / f"{timestamp}_flat.jsonl"
        
        # In-memory log structure
        self.log_data = {
            "timestamp": timestamp,
            "run_start": datetime.now().isoformat(),
            "parameters": {},
            "questions": []
        }
        
        self._current_question = None
    
    def log_parameters(self, config: Dict[str, Any]):
        """
        Log all configuration parameters at start
        
        Args:
            config: Full configuration dictionary
        """
        self.log_data["parameters"] = {
            "student_model": config.get("student", {}).get("model"),
            "student_provider": config.get("student", {}).get("provider"),
            "student_temperature": config.get("student", {}).get("temperature"),
            "student_max_tokens": config.get("student", {}).get("max_tokens"),
            "teacher_model": config.get("teacher", {}).get("model"),
            "teacher_provider": config.get("teacher", {}).get("provider"),
            "teacher_temperature": config.get("teacher", {}).get("temperature"),
            "teacher_max_tokens": config.get("teacher", {}).get("max_tokens"),
            "pass_threshold": config.get("teacher", {}).get("pass_threshold"),
            "metric_weights": config.get("teacher", {}).get("metrics", {}).get("weights", {}),
            "embedding_model": config.get("memory", {}).get("embedding_model"),
            "similarity_threshold": config.get("memory", {}).get("similarity_threshold"),
            "top_k": config.get("memory", {}).get("top_k"),
            "max_rounds": config.get("loop", {}).get("max_rounds"),
            "early_stopping": config.get("loop", {}).get("early_stopping", {}),
            "repetition_detection": config.get("loop", {}).get("repetition_detection", {}),
            "storage_path": config.get("memory", {}).get("storage_path"),
            "index_path": config.get("memory", {}).get("index_path"),
            "log_path": config.get("logging", {}).get("log_path")
        }
        self._save()
    
    def start_question(self, question_idx: int, question: str, ground_truth: str):
        """
        Start logging a new question
        
        Args:
            question_idx: Question index (1-based)
            question: Question text
            ground_truth: Ground truth answer
        """
        self._current_question = {
            "question_idx": question_idx,
            "question": question,
            "ground_truth": ground_truth,
            "rounds": [],
            "final_result": None,
            "warnings": [],
            "errors": []
        }
    
    def log_round(
        self,
        round_num: int,
        mode: str,
        student_input: str,
        student_output: str,
        student_raw_response: Optional[Dict[str, Any]],
        teacher_input: Optional[str],
        teacher_output: Optional[Dict[str, Any]],
        teacher_raw_response: Optional[Dict[str, Any]],
        scores: Dict[str, float],
        feedback: Optional[str],
        memory_hits: Optional[List[Dict[str, Any]]],
        flags: List[str]
    ):
        """
        Log a complete round with all details
        
        Args:
            round_num: Round number (1-based)
            mode: FIRST, REFINE, LAST_CHANCE
            student_input: Full prompt sent to student
            student_output: Student's answer
            student_raw_response: Raw API response from student
            teacher_input: Full prompt sent to metrics (None if error)
            teacher_output: Metrics evaluation dict (None if error)
            teacher_raw_response: Raw API response from metrics
            scores: All metric scores (blind_score, comparison_score, semantic_sim, rouge_l, exact_match, final)
            feedback: Feedback text used in this round (from memory or previous round)
            memory_hits: Retrieved memory entries
            flags: Status flags (RATE429, EARLY_STOP, REPETITION, etc.)
            
        Note: Feedback generation debug info is added separately via add_feedback_generation_to_last_round()
        """
        if self._current_question is None:
            return
        
        round_data = {
            "round": round_num,
            "mode": mode,
            "student": {
                "input": student_input,
                "output": student_output,
                "raw_response": student_raw_response
            },
            "teacher": {
                "input": teacher_input,
                "output": teacher_output,
                "raw_response": teacher_raw_response
            },
            "scores": scores,
            "feedback": feedback,
            "memory_hits": memory_hits,
            "flags": flags
        }
        
        self._current_question["rounds"].append(round_data)

        # Also append a flattened record for this round (for manual inspection)
        self._append_flat_round(round_data)
    
    def add_feedback_generation_to_last_round(
        self,
        prompt: str,
        response: Optional[Dict[str, Any]],
        feedback: str
    ):
        """
        Add feedback generation debug info to the last logged round.
        
        This is called after generate_feedback() completes, to update
        the round with feedback generation details.
        
        Args:
            prompt: Feedback generation prompt
            response: Raw API response from feedback generation
            feedback: Generated feedback text
        """
        if self._current_question is None or not self._current_question["rounds"]:
            return
        
        # Add feedback_generation to last round
        last_round = self._current_question["rounds"][-1]
        last_round["feedback_generation"] = {
            "prompt": prompt,
            "response": response,
            "feedback": feedback
        }
    
    def log_warning(self, warning: str):
        """Log a warning for current question"""
        if self._current_question is not None:
            self._current_question["warnings"].append({
                "timestamp": datetime.now().isoformat(),
                "message": warning
            })
    
    def log_error(self, error: str):
        """Log an error for current question"""
        if self._current_question is not None:
            self._current_question["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "message": error
            })
    
    def end_question(
        self,
        passed: bool,
        total_rounds: int,
        final_score: float,
        stop_reason: str
    ):
        """
        End current question and save final result
        
        Args:
            passed: Whether question passed threshold
            total_rounds: Total rounds taken
            final_score: Final combined score
            stop_reason: Reason for stopping (PASSED, MAX_ROUNDS, EARLY_STOP, etc.)
        """
        if self._current_question is None:
            return
        
        self._current_question["final_result"] = {
            "passed": passed,
            "total_rounds": total_rounds,
            "final_score": final_score,
            "stop_reason": stop_reason
        }
        
        self.log_data["questions"].append(self._current_question)
        self._current_question = None
        self._save()
    
    def finalize(self, summary: Dict[str, Any]):
        """
        Finalize log with summary statistics
        
        Args:
            summary: Summary dict with success_rate, avg_rounds, etc.
        """
        self.log_data["run_end"] = datetime.now().isoformat()
        self.log_data["summary"] = summary
        self._save()
    
    def _append_flat_round(self, round_data: Dict[str, Any]):
        """
        Append a single flattened round record to JSONL file.

        This is designed for quick manual analysis and contains:
        - question / ground_truth
        - student_input / student_output
        - teacher_input / teacher_output (metrics evaluator)
        - score (final combined score) + full scores dict
        - basic flags and feedback
        """
        try:
            if self._current_question is None:
                return

            scores = round_data.get("scores", {}) or {}
            final_score = None
            if isinstance(scores, dict):
                # Common keys: "final", "blind_score", "comparison_score", etc.
                final_score = scores.get("final")

            record = {
                "run_timestamp": self.log_data.get("timestamp"),
                "question_idx": self._current_question.get("question_idx"),
                "question": self._current_question.get("question"),
                "ground_truth": self._current_question.get("ground_truth"),
                "round": round_data.get("round"),
                "mode": round_data.get("mode"),
                "student_input": round_data.get("student", {}).get("input"),
                "student_output": round_data.get("student", {}).get("output"),
                "teacher_input": round_data.get("teacher", {}).get("input"),
                "teacher_output": round_data.get("teacher", {}).get("output"),
                "score": final_score,
                "scores": scores,
                "feedback": round_data.get("feedback"),
                "flags": round_data.get("flags", []),
            }

            with open(self.flat_log_file, "a", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False)
                f.write("\n")
        except Exception as e:
            print(f"[DEBUG_LOGGER] Failed to append flat log: {e}")
    
    def _save(self):
        """Save current log data to file"""
        try:
            # Custom JSON encoder to handle non-serializable objects
            def default_serializer(obj):
                # Handle ChatResult or similar objects
                if hasattr(obj, '__dict__'):
                    return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
                # Handle list of objects
                if isinstance(obj, list):
                    return [default_serializer(item) for item in obj]
                # Fallback: convert to string
                return str(obj)
            
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump(self.log_data, f, indent=2, ensure_ascii=False, default=default_serializer)
        except Exception as e:
            print(f"[DEBUG_LOGGER] Failed to save: {e}")
    
    def get_log_path(self) -> str:
        """Get the current log file path"""
        return str(self.log_file)
