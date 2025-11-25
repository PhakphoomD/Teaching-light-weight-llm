"""
Refinement Settings Module

Centralized parameter definitions for all refinement plugins.

Priority chain (highest to lowest):
1. CLI arguments (runtime override)
2. Config file (experiment-specific)
3. Settings.py (hardcoded defaults)

Usage:
    # In run_experiments.py
    from src.refinement.settings import SETTINGS
    SETTINGS.update_from_config(config)
    
    # In plugins
    from ...settings import SETTINGS
    tau = SETTINGS.early_stopping.tau
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


# ===== Metrics Settings =====

@dataclass
class MetricsSettings:
    """Evaluation metrics configuration"""
    use_f1: bool = True                    # Use F1 score instead of simple token overlap
    use_rouge_l_for_long: bool = True      # Use ROUGE-L for long answers
    rouge_l_word_threshold: int = 20       # Switch to ROUGE-L if answer > N words
    f1_weight: float = 0.5                 # Weight for F1 in faithfulness score
    rouge_l_weight: float = 0.5            # Weight for ROUGE-L in faithfulness score


# ===== LLM Reviewer Settings =====

@dataclass
class LLMReviewerSettings:
    """LLM Reviewer configuration"""
    enabled: bool = False                  # Enable/disable LLM reviewer
    model: str = "same_as_teacher"         # Model name or "same_as_teacher"
    use_for_borderline: bool = True        # Only use for borderline cases
    borderline_lower: float = 0.55         # Below this = definitely wrong
    borderline_upper: float = 0.75         # Above this = definitely correct
    temperature: float = 0.2               # Temperature for LLM reviewer
    max_tokens: int = 512                  # Max tokens for review


# ===== Teacher Settings =====

@dataclass
class EarlyStoppingSettings:
    """Early stopping parameters for teacher evaluation"""
    tau: float = 0.85              # Stop if stop_score >= tau (high confidence)
    patience: int = 1              # Stop after N rounds without improvement
    epsilon_gain: float = 0.01     # Minimum improvement delta (1%)


@dataclass
class EvaluatorSettings:
    """Teacher evaluator parameters"""
    temperature: float = 0.3       # Temperature for teacher LLM
    max_tokens: int = 512          # Max tokens for teacher response
    hint_max_length: int = 150     # Max hint length in characters


# ===== Student Settings =====

@dataclass
class MemoryRetrievalSettings:
    """Memory retrieval parameters for student"""
    k: int = 3                     # Top-k retrieval from memory
    distance_threshold: float = 0.7  # Similarity threshold for retrieval


@dataclass
class HardNegativeFilterSettings:
    """Hard-negative filter parameters"""
    threshold: int = 2             # Filter contexts with N+ quality drops


@dataclass
class StudentGenerationSettings:
    """Student generation parameters"""
    temperature: float = 0.7       # Temperature for student LLM
    max_tokens: int = 512          # Max tokens for student response


# ===== Memory Settings =====

@dataclass
class SemanticRuleSettings:
    """Semantic rule extraction parameters"""
    max_rules: int = 3             # Max rules to inject into prompt
    min_quality: float = 0.7       # Quality gate for rule creation
    min_support: int = 2           # Min episodes to support a rule
    distill_interval: int = 5      # Extract rules every N questions


# ===== Global Settings Container =====

class RefinementSettings:
    """
    Container for all refinement parameters.
    
    This class holds default values for all plugins.
    Values can be overridden from config files or CLI.
    """
    
    def __init__(self):
        # Metrics
        self.metrics = MetricsSettings()
        
        # LLM Reviewer
        self.llm_reviewer = LLMReviewerSettings()
        
        # Teacher
        self.early_stopping = EarlyStoppingSettings()
        self.evaluator = EvaluatorSettings()
        
        # Student
        self.memory_retrieval = MemoryRetrievalSettings()
        self.hard_negative_filter = HardNegativeFilterSettings()
        self.generation = StudentGenerationSettings()
        
        # Memory
        self.semantic_rule = SemanticRuleSettings()
    
    def update_from_config(self, config: Dict[str, Any]) -> None:
        """
        Override defaults from config file (Priority 2).
        
        Args:
            config: Experiment config dictionary
        
        Example config:
            tau: 0.9
            patience: 2
            k: 5
            student_temperature: 0.8
        """
        # Early stopping
        if "tau" in config:
            self.early_stopping.tau = float(config["tau"])
        if "patience" in config:
            self.early_stopping.patience = int(config["patience"])
        if "epsilon_gain" in config:
            self.early_stopping.epsilon_gain = float(config["epsilon_gain"])
        
        # Memory retrieval
        if "k" in config:
            self.memory_retrieval.k = int(config["k"])
        if "similarity_threshold" in config:
            self.memory_retrieval.distance_threshold = float(config["similarity_threshold"])
        
        # Hard-negative filter
        if "hard_negative_threshold" in config:
            self.hard_negative_filter.threshold = int(config["hard_negative_threshold"])
        
        # Semantic rules
        if "max_semantic_rules" in config:
            self.semantic_rule.max_rules = int(config["max_semantic_rules"])
        if "rule_min_quality" in config:
            self.semantic_rule.min_quality = float(config["rule_min_quality"])
        if "rule_min_support" in config:
            self.semantic_rule.min_support = int(config["rule_min_support"])
        if "rule_distill_interval" in config:
            self.semantic_rule.distill_interval = int(config["rule_distill_interval"])
        
        # Student generation
        if "student_temperature" in config:
            self.generation.temperature = float(config["student_temperature"])
        if "student_max_tokens" in config:
            self.generation.max_tokens = int(config["student_max_tokens"])
        
        # Teacher evaluation
        if "teacher_temperature" in config:
            self.evaluator.temperature = float(config["teacher_temperature"])
        if "teacher_max_tokens" in config:
            self.evaluator.max_tokens = int(config["teacher_max_tokens"])
        
        # Metrics
        if "metrics" in config:
            metrics_cfg = config["metrics"]
            if "use_f1" in metrics_cfg:
                self.metrics.use_f1 = bool(metrics_cfg["use_f1"])
            if "use_rouge_l_for_long" in metrics_cfg:
                self.metrics.use_rouge_l_for_long = bool(metrics_cfg["use_rouge_l_for_long"])
            if "rouge_l_word_threshold" in metrics_cfg:
                self.metrics.rouge_l_word_threshold = int(metrics_cfg["rouge_l_word_threshold"])
            if "f1_weight" in metrics_cfg:
                self.metrics.f1_weight = float(metrics_cfg["f1_weight"])
            if "rouge_l_weight" in metrics_cfg:
                self.metrics.rouge_l_weight = float(metrics_cfg["rouge_l_weight"])
        
        # LLM Reviewer
        if "llm_reviewer" in config:
            reviewer_cfg = config["llm_reviewer"]
            if "enabled" in reviewer_cfg:
                self.llm_reviewer.enabled = bool(reviewer_cfg["enabled"])
            if "model" in reviewer_cfg:
                self.llm_reviewer.model = str(reviewer_cfg["model"])
            if "use_for_borderline" in reviewer_cfg:
                self.llm_reviewer.use_for_borderline = bool(reviewer_cfg["use_for_borderline"])
            if "borderline_lower" in reviewer_cfg:
                self.llm_reviewer.borderline_lower = float(reviewer_cfg["borderline_lower"])
            if "borderline_upper" in reviewer_cfg:
                self.llm_reviewer.borderline_upper = float(reviewer_cfg["borderline_upper"])
            if "temperature" in reviewer_cfg:
                self.llm_reviewer.temperature = float(reviewer_cfg["temperature"])
            if "max_tokens" in reviewer_cfg:
                self.llm_reviewer.max_tokens = int(reviewer_cfg["max_tokens"])
    
    def update_from_cli(self, cli_args: Dict[str, Any]) -> None:
        """
        Override from CLI arguments (Priority 1 - highest).
        
        Args:
            cli_args: CLI arguments dictionary
        
        Note: Not implemented yet, prepared for future use.
        """
        # TODO: Implement CLI override
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary for logging/debugging"""
        return {
            "metrics": {
                "use_f1": self.metrics.use_f1,
                "use_rouge_l_for_long": self.metrics.use_rouge_l_for_long,
                "rouge_l_word_threshold": self.metrics.rouge_l_word_threshold,
                "f1_weight": self.metrics.f1_weight,
                "rouge_l_weight": self.metrics.rouge_l_weight,
            },
            "llm_reviewer": {
                "enabled": self.llm_reviewer.enabled,
                "model": self.llm_reviewer.model,
                "use_for_borderline": self.llm_reviewer.use_for_borderline,
                "borderline_lower": self.llm_reviewer.borderline_lower,
                "borderline_upper": self.llm_reviewer.borderline_upper,
                "temperature": self.llm_reviewer.temperature,
                "max_tokens": self.llm_reviewer.max_tokens,
            },
            "early_stopping": {
                "tau": self.early_stopping.tau,
                "patience": self.early_stopping.patience,
                "epsilon_gain": self.early_stopping.epsilon_gain,
            },
            "evaluator": {
                "temperature": self.evaluator.temperature,
                "max_tokens": self.evaluator.max_tokens,
                "hint_max_length": self.evaluator.hint_max_length,
            },
            "memory_retrieval": {
                "k": self.memory_retrieval.k,
                "distance_threshold": self.memory_retrieval.distance_threshold,
            },
            "hard_negative_filter": {
                "threshold": self.hard_negative_filter.threshold,
            },
            "generation": {
                "temperature": self.generation.temperature,
                "max_tokens": self.generation.max_tokens,
            },
            "semantic_rule": {
                "max_rules": self.semantic_rule.max_rules,
                "min_quality": self.semantic_rule.min_quality,
                "min_support": self.semantic_rule.min_support,
                "distill_interval": self.semantic_rule.distill_interval,
            },
        }


# Global instance (single source of truth)
SETTINGS = RefinementSettings()
