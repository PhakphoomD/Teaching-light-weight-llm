"""
Model Client Factory

Central factory for creating model clients based on model type.
Supports TinyLlama, Llama2, and Llama3.
"""

from typing import Any
from src.core.logger import get_logger

# Import providers to trigger registration
import src.providers.local_client  # noqa: F401
import src.providers.groq_client  # noqa: F401
import src.providers.gemini_client  # noqa: F401

logger = get_logger(__name__)


def get_model_client(model_type: str, provider: str = "local") -> Any:
    """
    Get appropriate model client based on model type.
    
    Args:
        model_type: Model type ('tinyllama_1_1b', 'llama2_7b', 'llama3_8b')
        provider: Provider name ('local', 'groq', 'gemini')
        
    Returns:
        Model client instance
        
    Raises:
        ValueError: If model type is not supported
    """
    model_type = model_type.lower().replace('.', '_')
    
    if model_type == "tinyllama_1_1b" or model_type == "tinyllama":
        from src.models.tinyllama_1_1b.client import TinyLlamaClient
        logger.info(f"Using TinyLlama 1.1B with provider: {provider}")
        return TinyLlamaClient(provider=provider)
    
    elif model_type == "llama2_7b" or model_type == "llama2":
        from src.models.llama2_7b.client import Llama2Client
        logger.info(f"Using Llama2 7B with provider: {provider}")
        return Llama2Client(provider=provider)
    
    elif model_type == "llama3_8b" or model_type == "llama3":
        from src.models.llama3_8b.client import Llama3Client
        logger.info(f"Using Llama3 8B with provider: {provider}")
        return Llama3Client(provider=provider)
    
    else:
        supported = ["tinyllama_1_1b", "llama2_7b", "llama3_8b"]
        raise ValueError(
            f"Unsupported model type: '{model_type}'. "
            f"Supported models: {supported}"
        )


def get_prompt_builder(model_type: str):
    """
    Get appropriate prompt building functions for model type.
    
    Args:
        model_type: Model type ('tinyllama_1_1b', 'llama2_7b', 'llama3_8b')
        
    Returns:
        Module with build_reflection_prompt and build_answer_prompt functions
    """
    model_type = model_type.lower().replace('.', '_')
    
    if model_type == "tinyllama_1_1b" or model_type == "tinyllama":
        from src.models.tinyllama_1_1b import prompts
        return prompts
    
    elif model_type == "llama2_7b" or model_type == "llama2":
        from src.models.llama2_7b import prompts
        return prompts
    
    elif model_type == "llama3_8b" or model_type == "llama3":
        from src.models.llama3_8b import prompts
        return prompts
    
    else:
        supported = ["tinyllama_1_1b", "llama2_7b", "llama3_8b"]
        raise ValueError(
            f"Unsupported model type: '{model_type}'. "
            f"Supported models: {supported}"
        )
