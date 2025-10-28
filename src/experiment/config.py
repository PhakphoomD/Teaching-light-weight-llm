"""
Configuration loader for experiments

Loads and validates model and strategy configurations from YAML files.
"""

import os
import yaml
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class ModelConfig:
    """Model configuration."""
    key: str
    type: str  # 'local' or 'api'
    model_id: str
    display_name: str
    description: str
    params: Dict[str, Any]


@dataclass
class StrategyConfig:
    """Strategy configuration."""
    key: str
    name: str
    short_name: str
    description: str
    display_name: str
    features: Dict[str, Any]
    params: Dict[str, Any]
    notes: str


@dataclass
class DatasetConfig:
    """Dataset configuration."""
    name: str
    path: str
    size: int
    description: str


@dataclass
class ExperimentConfig:
    """Complete experiment configuration."""
    models: Dict[str, ModelConfig]
    strategies: Dict[str, StrategyConfig]
    datasets: List[DatasetConfig]
    strategy_groups: Dict[str, List[str]]


def load_models_config(config_path: str = "config/models.yaml") -> Dict[str, ModelConfig]:
    """
    Load model configurations from YAML file.
    
    Args:
        config_path: Path to models.yaml
        
    Returns:
        Dictionary of model_key -> ModelConfig
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    models = {}
    for key, config in data['models'].items():
        models[key] = ModelConfig(
            key=key,
            type=config['type'],
            model_id=config['model_id'],
            display_name=config['display_name'],
            description=config['description'],
            params={k: v for k, v in config.items() 
                   if k not in ['type', 'model_id', 'display_name', 'description']}
        )
    
    return models


def load_strategies_config(config_path: str = "config/strategies.yaml") -> tuple[Dict[str, StrategyConfig], Dict[str, List[str]]]:
    """
    Load strategy configurations from YAML file.
    
    Args:
        config_path: Path to strategies.yaml
        
    Returns:
        Tuple of (strategies_dict, strategy_groups_dict)
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    strategies = {}
    for key, config in data['strategies'].items():
        strategies[key] = StrategyConfig(
            key=key,
            name=config['name'],
            short_name=config['short_name'],
            description=config['description'],
            display_name=config['display_name'],
            features=config['features'],
            params=config['params'],
            notes=config.get('notes', '')
        )
    
    strategy_groups = data.get('strategy_groups', {})
    
    return strategies, strategy_groups


def discover_datasets(data_dir: str = "data") -> List[DatasetConfig]:
    """
    Discover available datasets in data directory.
    
    Args:
        data_dir: Path to data directory
        
    Returns:
        List of DatasetConfig
    """
    datasets = []
    
    # Check for standard datasets
    dataset_files = {
        'alpaca_20.jsonl': ('Quick Test', 20, 'Small dataset for quick testing'),
        'alpaca_100.jsonl': ('Medium Test', 100, 'Medium dataset for validation'),
        'alpaca_full.jsonl': ('Full Dataset', 52000, 'Complete Alpaca dataset'),
        'alpaca_questions.jsonl': ('Full Dataset', 52000, 'Complete Alpaca dataset (alias)')
    }
    
    for filename, (name, size, desc) in dataset_files.items():
        path = os.path.join(data_dir, filename)
        if os.path.exists(path):
            datasets.append(DatasetConfig(
                name=name,
                path=path,
                size=size,
                description=desc
            ))
    
    return datasets


def load_experiment_config() -> ExperimentConfig:
    """
    Load complete experiment configuration.
    
    Returns:
        ExperimentConfig with all models, strategies, and datasets
    """
    models = load_models_config()
    strategies, strategy_groups = load_strategies_config()
    datasets = discover_datasets()
    
    return ExperimentConfig(
        models=models,
        strategies=strategies,
        datasets=datasets,
        strategy_groups=strategy_groups
    )


def get_model_by_key(config: ExperimentConfig, key: str) -> Optional[ModelConfig]:
    """Get model configuration by key."""
    return config.models.get(key)


def get_strategy_by_key(config: ExperimentConfig, key: str) -> Optional[StrategyConfig]:
    """Get strategy configuration by key."""
    return config.strategies.get(key)


def get_strategies_by_group(config: ExperimentConfig, group: str) -> List[StrategyConfig]:
    """Get list of strategies in a group."""
    keys = config.strategy_groups.get(group, [])
    return [config.strategies[k] for k in keys if k in config.strategies]
