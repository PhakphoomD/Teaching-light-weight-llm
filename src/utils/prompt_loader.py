"""
Prompt Loader Utility

Centralized module for loading and formatting prompts from prompts_config.yml
Provides easy access to all prompts with variable substitution.

Usage:
    from src.utils.prompt_loader import PromptLoader
    
    loader = PromptLoader()
    
    # Get student prompt
    prompt = loader.get_student_prompt(
        'first_attempt',
        question="What is 2+2?"
    )
    
    # Get teacher feedback prompt
    feedback_prompt = loader.get_teacher_prompt(
        'cot_refinement',
        question="What is 2+2?",
        student_answer="5",
        ground_truth="4",
        previous_feedback="Check your addition"
    )
    
    # Get metrics prompt
    eval_prompt = loader.get_metrics_prompt(
        'blind_judge',
        question="What is 2+2?",
        student_answer="4"
    )
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class PromptLoader:
    """
    Load and format prompts from prompts_config.yml
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize prompt loader.
        
        Args:
            config_path: Path to prompts_config.yml (default: config/prompts_config.yml)
        """
        if config_path is None:
            # Default to config/prompts_config.yml relative to project root
            project_root = Path(__file__).parent.parent.parent
            self.config_path = project_root / "config" / "prompts_config.yml"
        else:
            self.config_path = Path(config_path)
        
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load prompts config from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Prompts config not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def reload(self):
        """Reload config from file (useful for hot-reloading in UI)."""
        self.config = self._load_config()
    
    def get_student_prompt(self, 
                          prompt_type: str,
                          **kwargs) -> str:
        """
        Get formatted student prompt.
        
        Args:
            prompt_type: Type of prompt (first_attempt, refinement, last_chance, simple)
            **kwargs: Variables for substitution (question, previous_answer, feedback, etc.)
        
        Returns:
            Formatted prompt string
        
        Example:
            >>> loader.get_student_prompt(
            ...     'first_attempt',
            ...     question="What is 2+2?"
            ... )
        """
        template = self.config['student'].get(prompt_type)
        if not template:
            raise ValueError(f"Unknown student prompt type: {prompt_type}")
        
        return template.format(**kwargs)
    
    def get_teacher_prompt(self,
                          prompt_type: str,
                          **kwargs) -> str:
        """
        Get formatted teacher feedback prompt.
        
        Args:
            prompt_type: Type of prompt (cot_first_time, cot_refinement, difficult_question, etc.)
            **kwargs: Variables for substitution (question, student_answer, ground_truth, etc.)
        
        Returns:
            Formatted prompt string
        
        Example:
            >>> loader.get_teacher_prompt(
            ...     'cot_refinement',
            ...     question="What is 2+2?",
            ...     student_answer="5",
            ...     ground_truth="4",
            ...     previous_feedback="Check your addition"
            ... )
        """
        template = self.config['teacher'].get(prompt_type)
        if not template:
            raise ValueError(f"Unknown teacher prompt type: {prompt_type}")
        
        return template.format(**kwargs)
    
    def get_metrics_prompt(self,
                          prompt_type: str,
                          **kwargs) -> str:
        """
        Get formatted metrics evaluation prompt.
        
        Args:
            prompt_type: Type of prompt (blind_judge, comparison_judge)
            **kwargs: Variables for substitution (question, student_answer, ground_truth)
        
        Returns:
            Formatted prompt string
        
        Example:
            >>> loader.get_metrics_prompt(
            ...     'blind_judge',
            ...     question="What is 2+2?",
            ...     student_answer="4"
            ... )
        """
        template = self.config['metrics'].get(prompt_type)
        if not template:
            raise ValueError(f"Unknown metrics prompt type: {prompt_type}")
        
        return template.format(**kwargs)
    
    def get_active_prompts(self) -> Dict[str, str]:
        """
        Get currently active prompt types.
        
        Returns:
            Dict mapping usage to active prompt type
        
        Example:
            >>> loader.get_active_prompts()
            {'student_first': 'first_attempt', 'teacher_feedback': 'cot_refinement', ...}
        """
        return self.config['settings']['active']
    
    def set_active_prompt(self, usage: str, prompt_type: str):
        """
        Set active prompt for a specific usage.
        
        Args:
            usage: Usage key (student_first, teacher_feedback, etc.)
            prompt_type: Prompt type to activate
        
        Note: This only changes in-memory config, not the file
        """
        if usage not in self.config['settings']['active']:
            raise ValueError(f"Unknown usage: {usage}")
        
        self.config['settings']['active'][usage] = prompt_type
    
    def list_available_prompts(self, category: str) -> list:
        """
        List all available prompts in a category.
        
        Args:
            category: Category name (student, teacher, metrics)
        
        Returns:
            List of prompt type names
        
        Example:
            >>> loader.list_available_prompts('student')
            ['first_attempt', 'refinement', 'last_chance', 'simple']
        """
        if category not in self.config:
            raise ValueError(f"Unknown category: {category}")
        
        return list(self.config[category].keys())
    
    def get_prompt_template(self, category: str, prompt_type: str) -> str:
        """
        Get raw prompt template without formatting.
        
        Args:
            category: Category name (student, teacher, metrics)
            prompt_type: Prompt type
        
        Returns:
            Raw template string with {variables}
        
        Example:
            >>> template = loader.get_prompt_template('student', 'first_attempt')
            >>> print(template)
        """
        if category not in self.config:
            raise ValueError(f"Unknown category: {category}")
        
        template = self.config[category].get(prompt_type)
        if not template:
            raise ValueError(f"Unknown prompt type: {prompt_type} in category: {category}")
        
        return template
    
    def get_settings(self) -> Dict[str, Any]:
        """Get prompt settings (max_lengths, variables, etc.)."""
        return self.config['settings']


# Convenience functions for backward compatibility
_default_loader = None

def get_prompt_loader() -> PromptLoader:
    """Get singleton prompt loader instance."""
    global _default_loader
    if _default_loader is None:
        _default_loader = PromptLoader()
    return _default_loader


def reload_prompts():
    """Reload prompts from config file (hot reload)."""
    get_prompt_loader().reload()
