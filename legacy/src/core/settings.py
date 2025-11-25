"""
Settings and Configuration Loaders

Provides functions to load and validate various configuration files,
including main config, model specifications, and environment variables.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from .logger import get_logger

logger = get_logger("settings")

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent


def load_env() -> None:
    """
    Load environment variables from .env file.
    
    Example:
        >>> load_env()
        >>> api_key = os.getenv('GOOGLE_API_KEY')
    """
    env_path = PROJECT_ROOT / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded environment from {env_path}")
    else:
        logger.warning(f".env file not found at {env_path}")


def resolve_env_vars(value: Any) -> Any:
    """
    Recursively resolve environment variable references in config values.
    
    Supports syntax: ${VAR_NAME} or ${VAR_NAME:-default_value}
    
    Args:
        value: Config value (can be str, dict, list, or primitive)
    
    Returns:
        Resolved value with env vars substituted
    
    Example:
        >>> os.environ['RPM'] = '15'
        >>> resolve_env_vars('${RPM}')
        15
        >>> resolve_env_vars('${MISSING:-30}')
        30
        >>> resolve_env_vars({'rpm': '${RPM}', 'tpm': '${TPM:-1000}'})
        {'rpm': 15, 'tpm': 1000}
    """
    if isinstance(value, str):
        # Pattern: ${VAR_NAME} or ${VAR_NAME:-default}
        pattern = r'\$\{([^}:]+)(?::-(.*))?\}'
        
        def replacer(match):
            var_name = match.group(1)
            default_value = match.group(2)
            env_value = os.getenv(var_name)
            
            if env_value is not None:
                # Try to convert to int/float if possible
                try:
                    if '.' in env_value:
                        return str(float(env_value))
                    else:
                        return str(int(env_value))
                except ValueError:
                    return env_value
            elif default_value is not None:
                return default_value
            else:
                logger.warning(f"Environment variable {var_name} not found and no default provided")
                return match.group(0)  # Return original ${VAR} if not found
        
        resolved = re.sub(pattern, replacer, value)
        
        # Try to convert final result to int/float
        try:
            if '.' in resolved:
                return float(resolved)
            else:
                return int(resolved)
        except ValueError:
            return resolved
    
    elif isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}
    
    elif isinstance(value, list):
        return [resolve_env_vars(item) for item in value]
    
    else:
        return value


def load_models_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load and validate model configuration from models.yml.
    
    Resolves environment variables in rate limit fields (rpm, tpm, rpd).
    
    Args:
        config_path: Path to models.yml (defaults to config/models.yml)
    
    Returns:
        Dictionary with resolved model configurations
    
    Raises:
        FileNotFoundError: If models.yml doesn't exist
        ValueError: If required fields are missing
    
    Example:
        >>> config = load_models_config()
        >>> primary_model = config['primary']
        >>> teachers = config['teachers']
        >>> g25_config = teachers['g25_flash_lite']
        >>> print(f"RPM: {g25_config['rpm']}, TPM: {g25_config['tpm']}")
    """
    if config_path is None:
        config_path = PROJECT_ROOT / 'config' / 'models.yml'
    
    if not config_path.exists():
        raise FileNotFoundError(f"Model config not found: {config_path}")
    
    # Load YAML
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Resolve environment variables
    config = resolve_env_vars(config)
    
    # Validate structure
    if 'teachers' not in config:
        raise ValueError("Missing 'teachers' section in models.yml")
    
    if 'primary' not in config:
        raise ValueError("Missing 'primary' field in models.yml")
    
    # Validate each teacher model has required fields
    required_fields = ['provider', 'model', 'rpm', 'tpm', 'rpd', 'max_output_tokens']
    for teacher_name, teacher_config in config['teachers'].items():
        missing = [f for f in required_fields if f not in teacher_config]
        if missing:
            raise ValueError(f"Teacher '{teacher_name}' missing required fields: {missing}")
    
    # Validate primary teacher exists
    primary = config['primary']
    if primary not in config['teachers']:
        raise ValueError(f"Primary teacher '{primary}' not found in teachers section")
    
    logger.info(f"Loaded model config from {config_path}")
    logger.info(f"Primary teacher: {primary}")
    logger.info(f"Available teachers: {list(config['teachers'].keys())}")
    
    return config


def get_teacher_config(teacher_name: str, models_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get configuration for a specific teacher model.
    
    Args:
        teacher_name: Name of the teacher (e.g., 'g25_flash_lite')
        models_config: Pre-loaded models config (will load if None)
    
    Returns:
        Teacher configuration dictionary
    
    Raises:
        ValueError: If teacher name not found
    
    Example:
        >>> config = get_teacher_config('g25_flash_lite')
        >>> print(f"Model: {config['model']}, RPM: {config['rpm']}")
    """
    if models_config is None:
        models_config = load_models_config()
    
    if teacher_name not in models_config['teachers']:
        available = list(models_config['teachers'].keys())
        raise ValueError(f"Teacher '{teacher_name}' not found. Available: {available}")
    
    return models_config['teachers'][teacher_name]


def get_primary_teacher(models_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get configuration for the primary teacher model.
    
    Args:
        models_config: Pre-loaded models config (will load if None)
    
    Returns:
        Primary teacher configuration dictionary
    
    Example:
        >>> primary = get_primary_teacher()
        >>> print(f"Using primary teacher: {primary['model']}")
    """
    if models_config is None:
        models_config = load_models_config()
    
    primary_name = models_config['primary']
    return get_teacher_config(primary_name, models_config)


def get_fallback_chain(models_config: Optional[Dict[str, Any]] = None) -> list[str]:
    """
    Get the fallback chain for teacher models.
    
    Args:
        models_config: Pre-loaded models config (will load if None)
    
    Returns:
        List of teacher names in fallback order
    
    Example:
        >>> chain = get_fallback_chain()
        >>> print(f"Fallback chain: {chain}")
    """
    if models_config is None:
        models_config = load_models_config()
    
    if 'fallback' in models_config and 'chain' in models_config['fallback']:
        return models_config['fallback']['chain']
    
    # Default fallback: just return all teachers
    return list(models_config['teachers'].keys())


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load main configuration from config.yaml.
    
    Args:
        config_path: Path to config.yaml (defaults to config/config.yaml)
    
    Returns:
        Dictionary with configuration
    
    Example:
        >>> config = load_config()
        >>> student_model = config['student']['model']
        >>> k_retrieval = config['memory']['k']
    """
    if config_path is None:
        config_path = PROJECT_ROOT / 'config' / 'config.yaml'
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    logger.info(f"Loaded config from {config_path}")
    return config


# Load configurations on import
_CONFIG = None
_MODELS_CONFIG = None

def get_config() -> Dict[str, Any]:
    """Get cached main configuration."""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = load_config()
    return _CONFIG

def get_models() -> Dict[str, Any]:
    """Get cached models configuration."""
    global _MODELS_CONFIG
    if _MODELS_CONFIG is None:
        _MODELS_CONFIG = load_models_config()
    return _MODELS_CONFIG


# Constants derived from config (lazy-loaded)
def _get_student_config() -> Dict[str, Any]:
    """Get student configuration."""
    return get_config()['student']

def _get_teacher_provider() -> str:
    """Get primary teacher provider."""
    primary = get_models()['primary']
    return get_models()['teachers'][primary]['provider']

def _get_teacher_model() -> str:
    """Get primary teacher model."""
    primary = get_models()['primary']
    return get_models()['teachers'][primary]['model']


# Public constants (computed on first access)
def get_student_model() -> str:
    """Student model name (e.g., 'TinyLlama/TinyLlama-1.1B-Chat-v1.0')"""
    return _get_student_config()['model']

def get_student_mode() -> str:
    """Student mode: 'local' or 'api'"""
    return _get_student_config()['mode']

def get_teacher_provider() -> str:
    """Primary teacher provider (e.g., 'gemini')"""
    return _get_teacher_provider()

def get_teacher_model_name() -> str:
    """Primary teacher model (e.g., 'gemini-2.5-flash-lite')"""
    return _get_teacher_model()

def get_k_retrieval() -> int:
    """Top-K for memory retrieval"""
    return get_config()['memory']['k']

def get_tau_threshold() -> float:
    """Quality threshold for stopping refinement"""
    return get_config()['refinement']['tau']

def get_max_rounds() -> int:
    """Maximum refinement iterations"""
    return get_config()['refinement']['max_rounds']

def get_logs_dir() -> Path:
    """Logs directory path"""
    return Path(get_config()['paths']['logs_dir'])

def get_experiments_dir() -> Path:
    """Experiments directory path"""
    return Path(get_config()['paths']['experiments_dir'])

def get_memory_dir() -> Path:
    """Memory directory path"""
    return Path(get_config()['paths']['memory_dir'])

def get_embedding_model() -> str:
    """Embedding model name"""
    return get_config()['memory']['encoder']

def get_embedding_dim() -> int:
    """Embedding dimension"""
    return get_config()['memory']['dim']

def get_teacher_temperature() -> float:
    """Teacher temperature for LLM calls (from config.yaml)"""
    return get_config().get('teacher', {}).get('temperature', 0.2)

def get_teacher_max_tokens() -> int:
    """Teacher max_tokens for LLM calls (from config.yaml)"""
    return get_config().get('teacher', {}).get('max_tokens', 512)

def get_critic_type() -> str:
    """Critic type: hybrid | rule | llm (from config.yaml)"""
    return get_config().get('critic', {}).get('type', 'hybrid')

def get_critic_rule_weight() -> float:
    """Critic rule-based score weight (from config.yaml)"""
    return get_config().get('critic', {}).get('rule_weight', 0.5)

def get_critic_llm_weight() -> float:
    """Critic LLM score weight (from config.yaml)"""
    return get_config().get('critic', {}).get('llm_weight', 0.5)

def get_critic_stop_calibration() -> Dict[str, float]:
    """Critic stop_score calibration params {a, b} (from config.yaml)"""
    return get_config().get('critic', {}).get('stop_calibration', {'a': 1.0, 'b': 0.0})

def get_critic_disagreement_delta() -> float:
    """Critic disagreement threshold (from config.yaml)"""
    return get_config().get('critic', {}).get('disagreement_delta', 0.3)

def get_critic_disagreements_file() -> str:
    """Critic disagreements output file name (from config.yaml)"""
    return get_config().get('critic', {}).get('disagreements_file', 'disagreements.jsonl')

def get_critic_evaluation_thresholds() -> Dict[str, float]:
    """Critic evaluation thresholds for stop_score mapping (from config.yaml)"""
    return get_config().get('critic', {}).get('evaluation_thresholds', {
        'correct': 0.8,
        'partially_correct': 0.4
    })


# Initialize environment on import
load_env()


__all__ = [
    'load_env',
    'resolve_env_vars',
    'load_config',
    'load_models_config',
    'get_config',
    'get_models',
    'get_teacher_config',
    'get_primary_teacher',
    'get_fallback_chain',
    'PROJECT_ROOT',
    # Config getters
    'get_student_model',
    'get_student_mode',
    'get_teacher_provider',
    'get_teacher_model_name',
    'get_teacher_temperature',
    'get_teacher_max_tokens',
    'get_k_retrieval',
    'get_tau_threshold',
    'get_max_rounds',
    'get_logs_dir',
    'get_experiments_dir',
    'get_memory_dir',
    'get_embedding_model',
    'get_embedding_dim',
    # Critic config getters
    'get_critic_type',
    'get_critic_rule_weight',
    'get_critic_llm_weight',
    'get_critic_stop_calibration',
    'get_critic_disagreement_delta',
    'get_critic_disagreements_file',
    'get_critic_evaluation_thresholds'
]
