"""
Terminal UI - Clean and Readable Output
========================================
Beautiful terminal output with:
- Parameter summary header (with 3-sec delay)
- Progress bar per question (TQDM)
- Clean table format for rounds
- Error/warning aggregation
- Enhanced summary with metrics
"""

import time
from typing import Dict, Any, List, Optional
from collections import defaultdict
from tqdm import tqdm


class TerminalUI:
    """Clean terminal UI for teaching loop"""
    
    def __init__(self):
        """Initialize terminal UI"""
        self.error_counts = defaultdict(int)
        self.warning_counts = defaultdict(int)
        self.current_progress = None
    
    def print_header(self, config: Dict[str, Any], experiment_name: str = "Simplified Teaching Loop"):
        """
        Print beautiful header with parameters (3-sec delay before start)
        
        Args:
            config: Configuration dictionary
            experiment_name: Name of experiment
        """
        print("\n" + "=" * 80)
        print(f"{experiment_name.center(80)}")
        print("=" * 80)
        
        # Dataset info
        dataset_path = config.get("dataset", {}).get("path", "N/A")
        num_questions = config.get("dataset", {}).get("num_questions", "all")
        print(f"Dataset: {dataset_path} ({num_questions} questions)")
        print()
        
        # Model info
        student = config.get("student", {})
        teacher = config.get("teacher", {})
        print(f"Teacher Model:  {teacher.get('provider', 'N/A')}/{teacher.get('model', 'N/A')} "
              f"(temp={teacher.get('temperature', 'N/A')}, max_tokens={teacher.get('max_tokens', 'N/A')})")
        print(f"Student Model:  {student.get('provider', 'N/A')}/{student.get('model', 'N/A')} "
              f"(temp={student.get('temperature', 'N/A')}, max_tokens={student.get('max_tokens', 'N/A')})")
        print()
        
        # Metrics (hybrid or legacy)
        weights = config.get("teacher", {}).get("metrics", {}).get("weights", {})
        hybrid_config = config.get("teacher", {}).get("hybrid_scoring", {})
        
        if hybrid_config.get("enabled", False):
            # Hybrid mode
            print(f"Metric Weights: Blind={weights.get('blind_score', 0):.1f} | "
                  f"Comparison={weights.get('comparison_score', 0):.1f} | "
                  f"Semantic={weights.get('semantic_sim', 0):.1f} | "
                  f"Rouge_L={weights.get('rouge_l', 0):.1f} | "
                  f"Exact={weights.get('exact_match', 0):.1f}")
        else:
            # Legacy mode
            print(f"Metric Weights: T_score={weights.get('teacher_score', 0):.1f} | "
                  f"Semantic={weights.get('semantic_sim', 0):.1f} | "
                  f"Rouge_L={weights.get('rouge_l', 0):.1f} | "
                  f"Exact={weights.get('exact_match', 0):.1f}")
        print(f"Pass Threshold: {teacher.get('pass_threshold', 'N/A')}")
        print()
        
        # Embedding
        memory = config.get("memory", {})
        print(f"Embedding Model: {memory.get('embedding_model', 'N/A')} "
              f"(sim_threshold={memory.get('similarity_threshold', 'N/A')}, top_k={memory.get('top_k', 'N/A')})")
        print()
        
        # Early stopping config
        early_stop = config.get("loop", {}).get("early_stopping", {})
        repetition = config.get("loop", {}).get("repetition_detection", {})
        print(f"Early Stopping: patience={early_stop.get('patience', 'N/A')}, "
              f"start_round={early_stop.get('start_from_round', 'N/A')}, "
              f"plateau={early_stop.get('plateau_threshold', 'N/A')}")
        print(f"Repetition Detection: enabled={repetition.get('enabled', False)}, "
              f"threshold={repetition.get('similarity_threshold', 'N/A')}")
        print()
        
        # Storage paths
        log_path = config.get("logging", {}).get("log_path", "N/A")
        storage_path = memory.get("storage_path", "N/A")
        index_path = memory.get("index_path", "N/A")
        print(f"Storage Paths:")
        print(f"  - Log:    {log_path}")
        print(f"  - Memory: {storage_path}")
        print(f"  - FAISS:  {index_path}")
        
        print("=" * 80)
        print("\n⏳ Starting in 3 seconds... (check parameters above)\n")
        time.sleep(3)
    
    def create_progress_bar(self, total: int, desc: str = "Processing") -> tqdm:
        """
        Create progress bar for questions
        
        Args:
            total: Total number of questions
            desc: Description prefix
        
        Returns:
            tqdm progress bar object
        """
        self.current_progress = tqdm(
            total=total,
            desc=desc,
            ncols=100,
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]'
        )
        return self.current_progress
    
    def update_progress(self, question_num: int, question_text: str):
        """
        Update progress bar with current question
        
        Args:
            question_num: Current question number
            question_text: Question text (will be truncated)
        """
        if self.current_progress:
            # Truncate question to 40 chars
            q_short = question_text[:40] + "..." if len(question_text) > 40 else question_text
            self.current_progress.set_description(f"Q{question_num}: {q_short}")
            self.current_progress.update(1)
    
    def close_progress(self):
        """Close progress bar"""
        if self.current_progress:
            self.current_progress.close()
            self.current_progress = None
    
    def print_question_result(
        self,
        question_idx: int,
        total_questions: int,
        question: str,
        ground_truth: str,
        rounds: List[Dict[str, Any]],
        passed: bool,
        final_score: float
    ):
        """
        Print beautiful table for a question's results
        
        Args:
            question_idx: Question index (1-based)
            total_questions: Total questions
            question: Question text
            ground_truth: Ground truth answer
            rounds: List of round data dicts
            passed: Whether passed threshold
            final_score: Final combined score
        """
        print("\n" + "=" * 80)
        status = "[OK] PASSED" if passed else "[FAIL] FAILED"
        print(f"Question: {question_idx}/{total_questions} | Result: {status} | "
              f"Rounds: {len(rounds)} | Final Score: {final_score:.3f}")
        print("-" * 80)
        
        # Question and ground truth
        q_display = question[:60] + "..." if len(question) > 60 else question
        gt_display = ground_truth[:60] + "..." if len(ground_truth) > 60 else ground_truth
        print(f"Question:      {q_display}")
        print(f"Ground Truth:  {gt_display}")
        print()
        
        # Table header
        print(f"{'Round':<6} | {'Mode':<12} | {'Student Answer':<35} | {'Feedback':<30} | {'Scores':<25} | {'Flags':<15}")
        print("-" * 80)
        
        # Table rows
        for round_data in rounds:
            round_num = round_data.get("round", "?")
            mode = round_data.get("mode", "?")
            student_ans = round_data.get("student_answer", "")
            feedback = round_data.get("feedback", "")
            scores = round_data.get("scores", {})
            flags = round_data.get("flags", [])
            
            # Truncate long strings
            ans_display = (student_ans[:32] + "...") if len(student_ans) > 35 else student_ans
            feedback_display = (feedback[:27] + "...") if len(feedback) > 30 else feedback
            
            # Format scores (hybrid or legacy)
            final = scores.get("final", 0)
            rouge = scores.get("rouge_l", 0)
            sem = scores.get("semantic_sim", 0)
            
            # Check if hybrid mode (has blind_score + comparison_score)
            if "blind_score" in scores and "comparison_score" in scores:
                blind = scores.get("blind_score", 0)
                comp = scores.get("comparison_score", 0)
                score_str = f"B={blind:.2f} C={comp:.2f} F={final:.2f} S={sem:.2f}"
            else:
                # Legacy mode (single teacher_score)
                t_score = scores.get("teacher_score", 0)
                score_str = f"T={t_score:.2f} F={final:.2f} S={sem:.2f} R={rouge:.2f}"
            
            # Format flags
            flags_str = ", ".join(flags[:2])  # Max 2 flags
            if len(flags) > 2:
                flags_str += "..."
            
            print(f"{round_num:<6} | {mode:<12} | {ans_display:<35} | {feedback_display:<30} | {score_str:<25} | {flags_str:<15}")
        
        print("=" * 80)
    
    def log_error(self, error_type: str, error_msg: str):
        """
        Log an error (will be aggregated and shown at end)
        
        Args:
            error_type: Type of error (e.g., "Groq 429", "Timeout")
            error_msg: Full error message
        """
        self.error_counts[error_type] += 1
    
    def log_warning(self, warning_type: str, warning_msg: str):
        """
        Log a warning (will be aggregated and shown at end)
        
        Args:
            warning_type: Type of warning
            warning_msg: Full warning message
        """
        self.warning_counts[warning_type] += 1
    
    def print_warnings_errors(self):
        """Print aggregated warnings and errors"""
        if not self.error_counts and not self.warning_counts:
            return
        
        print("\n" + "=" * 80)
        print("WARNINGS & ERRORS DETECTED")
        print("=" * 80)
        
        if self.error_counts:
            print("\n[WARNING]  ERRORS:")
            for error_type, count in sorted(self.error_counts.items(), key=lambda x: -x[1]):
                print(f"  - {error_type}: {count} occurrence(s)")
        
        if self.warning_counts:
            print("\n[WARNING]  WARNINGS:")
            for warning_type, count in sorted(self.warning_counts.items(), key=lambda x: -x[1]):
                print(f"  - {warning_type}: {count} occurrence(s)")
        
        print("=" * 80)
    
    def print_summary(
        self,
        success_rate: float,
        total_passed: int,
        total_questions: int,
        avg_rounds: float,
        memory_hit_rate: float,
        total_time: float,
        avg_time_per_question: float,
        avg_metrics: Dict[str, float]
    ):
        """
        Print beautiful final summary with all metrics
        
        Args:
            success_rate: Success percentage (0-100)
            total_passed: Number of passed questions
            total_questions: Total questions
            avg_rounds: Average rounds per question
            memory_hit_rate: Percentage of memory hits
            total_time: Total elapsed time (seconds)
            avg_time_per_question: Average time per question (ms)
            avg_metrics: Average metric scores (teacher_score, semantic_sim, etc.)
        """
        print("\n" + "=" * 80)
        print("FINAL RESULTS".center(80))
        print("=" * 80)
        
        print(f"Success Rate:     {success_rate:.1f}% ({total_passed}/{total_questions})")
        print(f"Average Rounds:   {avg_rounds:.2f}")
        print(f"Memory Hit Rate:  {memory_hit_rate:.1f}%")
        print(f"Total Time:       {total_time:.2f}s")
        print(f"Avg Time/Q:       {avg_time_per_question:.0f}ms")
        print()
        
        # Average metrics (hybrid or legacy)
        print("Average Metrics:")
        
        # Check if hybrid mode (has blind_score + comparison_score)
        if "blind_score" in avg_metrics and "comparison_score" in avg_metrics:
            print(f"  - Blind Score:    {avg_metrics.get('blind_score', 0):.3f}")
            print(f"  - Comparison:     {avg_metrics.get('comparison_score', 0):.3f}")
        elif "teacher_score" in avg_metrics:
            print(f"  - Teacher Score:  {avg_metrics.get('teacher_score', 0):.3f}")
        
        print(f"  - Semantic Sim:   {avg_metrics.get('semantic_sim', 0):.3f}")
        print(f"  - Rouge-L:        {avg_metrics.get('rouge_l', 0):.3f}")
        print(f"  - Exact Match:    {avg_metrics.get('exact_match', 0):.3f}")
        print(f"  - Final Score:    {avg_metrics.get('final', 0):.3f}")
        
        print("=" * 80 + "\n")


def format_error_summary(error: Exception, model_name: str = "") -> str:
    """
    Format error into short summary for terminal
    
    Args:
        error: Exception object
        model_name: Model name (if known)
    
    Returns:
        Short error summary string
    """
    error_str = str(error)
    
    # Groq 429 Rate Limit
    if "429" in error_str and "Rate limit" in error_str:
        if "llama-3.3-70b" in error_str or "70b" in model_name.lower():
            return "Groq 429: Rate limit (llama-3.3-70b-versatile)"
        elif "llama-3.1-8b" in error_str or "8b" in model_name.lower():
            return "Groq 429: Rate limit (llama-3.1-8b-instant)"
        else:
            return "Groq 429: Rate limit exceeded"
    
    # Timeout
    if "timeout" in error_str.lower() or "timed out" in error_str.lower():
        return f"Timeout: {model_name}" if model_name else "Timeout error"
    
    # Connection error
    if "connection" in error_str.lower() or "network" in error_str.lower():
        return "Connection error"
    
    # 404 Not Found
    if "404" in error_str:
        return "404: Model not found"
    
    # Generic
    error_type = type(error).__name__
    return f"{error_type}: {error_str[:50]}"
