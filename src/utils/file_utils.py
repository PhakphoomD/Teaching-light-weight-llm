"""
File Utilities

Common file operations for experiments.
"""

import os
import json
from typing import Dict, List, Any
from datetime import datetime


def create_run_directory(base_dir: str, prefix: str = "run") -> str:
    """
    Create timestamped run directory.
    
    Args:
        base_dir: Base directory path
        prefix: Prefix for run directory (default: "run")
        
    Returns:
        Full path to created directory
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(base_dir, f"{prefix}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """
    Load JSONL file.
    
    Args:
        file_path: Path to JSONL file
        
    Returns:
        List of dictionaries
    """
    data = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            data.append(json.loads(line))
    return data


def save_jsonl(data: List[Dict[str, Any]], file_path: str) -> None:
    """
    Save data as JSONL file.
    
    Args:
        data: List of dictionaries
        file_path: Output file path
    """
    with open(file_path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def load_json(file_path: str) -> Dict[str, Any]:
    """
    Load JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Dictionary
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Dict[str, Any], file_path: str, indent: int = 2) -> None:
    """
    Save data as JSON file.
    
    Args:
        data: Dictionary to save
        file_path: Output file path
        indent: JSON indentation
    """
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def ensure_dir(dir_path: str) -> None:
    """
    Ensure directory exists.
    
    Args:
        dir_path: Directory path
    """
    os.makedirs(dir_path, exist_ok=True)
