"""
Token usage tracker for student and teacher models

Tracks token usage separately for student and teacher models,
saves to results/tokens/ directory for analysis.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


@dataclass
class ModelTokenUsage:
    """Token usage for a single model"""
    model_name: str
    model_type: str  # "student" or "teacher"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    num_calls: int = 0
    
    def add_usage(self, prompt: int, completion: int):
        """Add token usage from a single call"""
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += (prompt + completion)
        self.num_calls += 1
    
    def avg_prompt_tokens(self) -> float:
        """Average prompt tokens per call"""
        return self.prompt_tokens / max(self.num_calls, 1)
    
    def avg_completion_tokens(self) -> float:
        """Average completion tokens per call"""
        return self.completion_tokens / max(self.num_calls, 1)
    
    def avg_total_tokens(self) -> float:
        """Average total tokens per call"""
        return self.total_tokens / max(self.num_calls, 1)


@dataclass
class ExperimentTokenUsage:
    """Token usage for an entire experiment (student + teacher)"""
    experiment_id: str
    strategy_name: str
    student_model: str
    teacher_model: str
    timestamp: str
    
    student_usage: ModelTokenUsage
    teacher_usage: Optional[ModelTokenUsage] = None
    
    def total_tokens(self) -> int:
        """Total tokens across all models"""
        total = self.student_usage.total_tokens
        if self.teacher_usage:
            total += self.teacher_usage.total_tokens
        return total
    
    def total_prompt_tokens(self) -> int:
        """Total prompt tokens across all models"""
        total = self.student_usage.prompt_tokens
        if self.teacher_usage:
            total += self.teacher_usage.prompt_tokens
        return total
    
    def total_completion_tokens(self) -> int:
        """Total completion tokens across all models"""
        total = self.student_usage.completion_tokens
        if self.teacher_usage:
            total += self.teacher_usage.completion_tokens
        return total
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        result = {
            "experiment_id": self.experiment_id,
            "strategy_name": self.strategy_name,
            "student_model": self.student_model,
            "teacher_model": self.teacher_model,
            "timestamp": self.timestamp,
            "student_usage": asdict(self.student_usage),
            "total_tokens": self.total_tokens(),
            "total_prompt_tokens": self.total_prompt_tokens(),
            "total_completion_tokens": self.total_completion_tokens(),
        }
        
        if self.teacher_usage:
            result["teacher_usage"] = asdict(self.teacher_usage)
        
        return result
    
    def save(self, output_dir: str):
        """Save token usage to JSON file"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        filepath = output_path / "token_usage.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        return str(filepath)


class TokenTracker:
    """
    Tracks token usage during experiment execution
    
    Separates student and teacher model usage for accurate cost calculation.
    """
    
    def __init__(
        self,
        student_model_name: str,
        teacher_model_name: str,
        strategy_name: str,
        experiment_id: str,
    ):
        self.student_model_name = student_model_name
        self.teacher_model_name = teacher_model_name
        self.strategy_name = strategy_name
        self.experiment_id = experiment_id
        self.timestamp = datetime.now().isoformat()
        
        # Initialize usage trackers
        self.student_usage = ModelTokenUsage(
            model_name=student_model_name,
            model_type="student"
        )
        
        # Only create teacher tracker if different from student
        if teacher_model_name != student_model_name:
            self.teacher_usage = ModelTokenUsage(
                model_name=teacher_model_name,
                model_type="teacher"
            )
        else:
            self.teacher_usage = None
    
    def track_student(self, prompt_tokens: int, completion_tokens: int):
        """Track student model usage"""
        self.student_usage.add_usage(prompt_tokens, completion_tokens)
    
    def track_teacher(self, prompt_tokens: int, completion_tokens: int):
        """Track teacher model usage"""
        if self.teacher_usage:
            self.teacher_usage.add_usage(prompt_tokens, completion_tokens)
        else:
            # Same model - add to student usage
            self.student_usage.add_usage(prompt_tokens, completion_tokens)
    
    def get_summary(self) -> ExperimentTokenUsage:
        """Get experiment token usage summary"""
        return ExperimentTokenUsage(
            experiment_id=self.experiment_id,
            strategy_name=self.strategy_name,
            student_model=self.student_model_name,
            teacher_model=self.teacher_model_name,
            timestamp=self.timestamp,
            student_usage=self.student_usage,
            teacher_usage=self.teacher_usage,
        )
    
    def save(self, output_dir: str) -> str:
        """Save token usage to file"""
        summary = self.get_summary()
        return summary.save(output_dir)
    
    def print_summary(self):
        """Print token usage summary to console"""
        # Check if models are local (no API pricing)
        is_local_student = self.student_model_name.startswith(('tinyllama', 'llama2', 'llama3_8b'))
        is_local_teacher = self.teacher_model_name.startswith(('tinyllama', 'llama2', 'llama3_8b')) if self.teacher_usage else False
        
        print("\n" + "=" * 80)
        print(" TOKEN USAGE SUMMARY")
        print("=" * 80)
        
        # Student usage
        print(f"\n‍ Student Model: {self.student_model_name}")
        if is_local_student:
            print(f"  Type: Local Model (estimated/average tokens)")
        print(f"  Calls:            {self.student_usage.num_calls:,}")
        print(f"  Prompt Tokens (avg):    {self.student_usage.prompt_tokens:,}")
        print(f"  Completion Tokens (avg): {self.student_usage.completion_tokens:,}")
        print(f"  Total Tokens (avg):     {self.student_usage.total_tokens:,}")
        print(f"  Avg per call:     {self.student_usage.avg_total_tokens():.1f} tokens")
        if is_local_student:
            print(f"  Note: Estimated from local tokenizer for baseline comparison with API models")
        
        # Teacher usage (if different)
        if self.teacher_usage:
            print(f"\n‍ Teacher Model: {self.teacher_model_name}")
            if is_local_teacher:
                print(f"  Type: Local Model (estimated/average tokens)")
            print(f"  Calls:            {self.teacher_usage.num_calls:,}")
            print(f"  Prompt Tokens (avg):    {self.teacher_usage.prompt_tokens:,}")
            print(f"  Completion Tokens (avg): {self.teacher_usage.completion_tokens:,}")
            print(f"  Total Tokens (avg):     {self.teacher_usage.total_tokens:,}")
            print(f"  Avg per call:     {self.teacher_usage.avg_total_tokens():.1f} tokens")
            if is_local_teacher:
                print(f"  Note: Estimated from local tokenizer for baseline comparison with API models")
        
        # Grand total
        summary = self.get_summary()
        print("\n" + "-" * 80)
        print(f" GRAND TOTAL (avg):     {summary.total_tokens():,} tokens")
        if is_local_student or is_local_teacher:
            print(f"   Note: Token counts are averaged estimates for baseline comparison")
        print("=" * 80 + "\n")


def load_token_usage(filepath: str) -> dict:
    """Load token usage from JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def calculate_cost(token_usage: dict, pricing: Dict[str, Dict[str, float]]) -> dict:
    """
    Calculate cost from token usage
    
    Args:
        token_usage: Token usage dictionary from load_token_usage()
        pricing: Model pricing dict, e.g., {"model_name": {"input": 0.5, "output": 1.5}}
    
    Returns:
        Dictionary with cost breakdown
    """
    result = {
        "student_cost": 0.0,
        "teacher_cost": 0.0,
        "total_cost": 0.0,
    }
    
    # Student cost
    student_model = token_usage["student_model"]
    if student_model in pricing:
        student_usage = token_usage["student_usage"]
        input_cost = (student_usage["prompt_tokens"] / 1_000_000) * pricing[student_model]["input"]
        output_cost = (student_usage["completion_tokens"] / 1_000_000) * pricing[student_model]["output"]
        result["student_cost"] = input_cost + output_cost
    
    # Teacher cost
    if "teacher_usage" in token_usage:
        teacher_model = token_usage["teacher_model"]
        if teacher_model in pricing:
            teacher_usage = token_usage["teacher_usage"]
            input_cost = (teacher_usage["prompt_tokens"] / 1_000_000) * pricing[teacher_model]["input"]
            output_cost = (teacher_usage["completion_tokens"] / 1_000_000) * pricing[teacher_model]["output"]
            result["teacher_cost"] = input_cost + output_cost
    
    result["total_cost"] = result["student_cost"] + result["teacher_cost"]
    return result
