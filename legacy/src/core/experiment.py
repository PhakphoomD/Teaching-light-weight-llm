"""
Experiment Management Module

Provides utilities for organizing and tracking experiments with
professional directory structure and metadata tracking.

Directory Structure:
    logs/
        experiments/          # Production experiments
            YYYYMMDD_HHMMSS_<name>/
                config.yaml   # Experiment configuration
                memory/       # Memory store + vector index
                runs.jsonl    # Per-round detailed logs
                summary.json  # Final results summary
        tests/                # Test runs
        dev/                  # Development/debug runs
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import json
import yaml

from .logger import get_logger

logger = get_logger("core.experiment")


class ExperimentManager:
    """
    Manages experiment directories and metadata with professional organization.
    
    Features:
    - Timestamped directories (YYYYMMDD_HHMMSS_name)
    - Automatic config saving
    - Structured logging (memory, runs, summary)
    - Easy cleanup and archival
    
    Example:
        >>> exp = ExperimentManager.create(
        ...     name="alpaca_20_adaptive",
        ...     category="experiments",
        ...     config={
        ...         "student_model": "TinyLlama-1.1B",
        ...         "teacher_model": "gemini-2.0-flash-lite",
        ...         "strategy": "adaptive",
        ...         "max_rounds": 5
        ...     }
        ... )
        >>> print(exp.run_id)
        '20251108_223000_alpaca_20_adaptive'
        >>> print(exp.memory_dir)
        'logs/experiments/20251108_223000_alpaca_20_adaptive/memory'
    """
    
    def __init__(self, run_dir: Path):
        """
        Initialize experiment manager.
        
        Args:
            run_dir: Path to experiment directory
        """
        self.run_dir = run_dir
        self.run_id = run_dir.name
        
        # Standard subdirectories
        self.memory_dir = run_dir / "memory"
        self.config_file = run_dir / "config.yaml"
        self.runs_log = run_dir / "runs.jsonl"
        self.summary_file = run_dir / "summary.json"
        
        logger.info(f"Experiment initialized: {self.run_id}")
    
    @classmethod
    def create(
        cls,
        name: str,
        category: str = "experiments",
        config: Optional[Dict[str, Any]] = None,
        base_dir: str = "logs"
    ) -> "ExperimentManager":
        """
        Create a new experiment with timestamped directory.
        
        Args:
            name: Experiment name (e.g., "alpaca_20_adaptive")
            category: Category folder ("experiments", "tests", "dev")
            config: Configuration dictionary to save
            base_dir: Base logs directory (default: "logs")
        
        Returns:
            ExperimentManager instance
        
        Example:
            >>> exp = ExperimentManager.create(
            ...     name="baseline_test",
            ...     category="tests",
            ...     config={"max_rounds": 3}
            ... )
        """
        # Generate run_id: YYYYMMDD_HHMMSS_name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{timestamp}_{name}"
        
        # Create directory structure
        run_dir = Path(base_dir) / category / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (run_dir / "memory").mkdir(exist_ok=True)
        
        logger.info(f"Created experiment: {run_id}")
        logger.info(f"Directory: {run_dir}")
        
        # Initialize manager
        manager = cls(run_dir)
        
        # Save config if provided
        if config:
            manager.save_config(config)
        
        return manager
    
    @classmethod
    def from_run_id(
        cls,
        run_id: str,
        category: str = "experiments",
        base_dir: str = "logs"
    ) -> "ExperimentManager":
        """
        Load existing experiment by run_id.
        
        Args:
            run_id: Experiment run ID (e.g., "20251108_223000_alpaca_20")
            category: Category folder
            base_dir: Base logs directory
        
        Returns:
            ExperimentManager instance
        
        Raises:
            FileNotFoundError: If experiment directory doesn't exist
        """
        run_dir = Path(base_dir) / category / run_id
        
        if not run_dir.exists():
            raise FileNotFoundError(f"Experiment not found: {run_dir}")
        
        logger.info(f"Loaded experiment: {run_id}")
        return cls(run_dir)
    
    def save_config(self, config: Dict[str, Any]) -> None:
        """
        Save experiment configuration to YAML.
        
        Args:
            config: Configuration dictionary
        """
        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"Config saved: {self.config_file}")
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load experiment configuration from YAML.
        
        Returns:
            Configuration dictionary
        """
        if not self.config_file.exists():
            logger.warning("Config file not found")
            return {}
        
        with open(self.config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        return config or {}
    
    def log_run(self, run_data: Dict[str, Any]) -> None:
        """
        Append a run record to runs.jsonl.
        
        Args:
            run_data: Run data (question, round, answer, evaluation, etc.)
        """
        with open(self.runs_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(run_data, ensure_ascii=False) + "\n")
    
    def save_summary(self, summary: Dict[str, Any]) -> None:
        """
        Save experiment summary (final results).
        
        Args:
            summary: Summary data (success_rate, avg_rounds, etc.)
        """
        with open(self.summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Summary saved: {self.summary_file}")
    
    def get_memory_store_path(self) -> str:
        """Get path to memory store JSONL file."""
        return str(self.memory_dir / "store.jsonl")
    
    def get_vector_index_path(self) -> str:
        """Get path to FAISS vector index file."""
        return str(self.memory_dir / "faiss.index")
    
    def get_runs_log_path(self) -> str:
        """Get path to runs log JSONL file."""
        return str(self.runs_log)
    
    def list_runs(self) -> list:
        """
        Load all run records from runs.jsonl.
        
        Returns:
            List of run dictionaries
        """
        if not self.runs_log.exists():
            return []
        
        runs = []
        with open(self.runs_log, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    runs.append(json.loads(line))
        
        return runs
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get experiment information summary.
        
        Returns:
            Dictionary with experiment info
        """
        info = {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "memory_dir": str(self.memory_dir),
            "config_file": str(self.config_file),
            "runs_log": str(self.runs_log),
            "summary_file": str(self.summary_file),
            "exists": {
                "config": self.config_file.exists(),
                "runs_log": self.runs_log.exists(),
                "summary": self.summary_file.exists(),
                "memory_store": (self.memory_dir / "store.jsonl").exists(),
                "vector_index": (self.memory_dir / "faiss.index").exists()
            }
        }
        
        if self.runs_log.exists():
            info["num_runs"] = len(self.list_runs())
        
        return info
    
    def __str__(self) -> str:
        """String representation."""
        return f"Experiment({self.run_id})"
    
    def __repr__(self) -> str:
        """Detailed representation."""
        return f"ExperimentManager(run_id='{self.run_id}', dir='{self.run_dir}')"


def list_experiments(
    category: str = "experiments",
    base_dir: str = "logs"
) -> list:
    """
    List all experiments in a category.
    
    Args:
        category: Category folder ("experiments", "tests", "dev")
        base_dir: Base logs directory
    
    Returns:
        List of run_ids
    
    Example:
        >>> experiments = list_experiments("experiments")
        >>> print(experiments)
        ['20251108_223000_alpaca_20_adaptive', '20251108_224500_alpaca_100_memory']
    """
    category_dir = Path(base_dir) / category
    
    if not category_dir.exists():
        return []
    
    experiments = []
    for exp_dir in sorted(category_dir.iterdir(), reverse=True):
        if exp_dir.is_dir():
            experiments.append(exp_dir.name)
    
    return experiments


def cleanup_old_experiments(
    category: str = "dev",
    keep_latest: int = 5,
    base_dir: str = "logs"
) -> int:
    """
    Clean up old experiment directories, keeping only the latest N.
    
    Args:
        category: Category to clean ("dev", "tests")
        keep_latest: Number of latest experiments to keep
        base_dir: Base logs directory
    
    Returns:
        Number of directories deleted
    
    Example:
        >>> deleted = cleanup_old_experiments("dev", keep_latest=3)
        >>> print(f"Deleted {deleted} old experiments")
    """
    experiments = list_experiments(category, base_dir)
    
    if len(experiments) <= keep_latest:
        logger.info(f"No cleanup needed (found {len(experiments)}, keeping {keep_latest})")
        return 0
    
    to_delete = experiments[keep_latest:]
    deleted_count = 0
    
    category_dir = Path(base_dir) / category
    
    for exp_name in to_delete:
        exp_dir = category_dir / exp_name
        if exp_dir.exists():
            import shutil
            shutil.rmtree(exp_dir)
            logger.info(f"Deleted: {exp_name}")
            deleted_count += 1
    
    logger.info(f"Cleanup complete: deleted {deleted_count} experiments")
    return deleted_count
