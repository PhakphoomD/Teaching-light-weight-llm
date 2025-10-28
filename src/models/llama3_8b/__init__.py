"""
Meta Llama 3 8B model package.
"""

from src.models.llama3_8b.client import Llama3Client
from src.models.llama3_8b.config import (
    MODEL_NAME,
    MODEL_SIZE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    REFLECTION_TEMPERATURE,
    DEFAULT_MAX_ITERS,
    DEFAULT_RETRIEVAL_K,
    DEFAULT_TFIDF_THRESHOLD
)

__all__ = [
    "Llama3Client",
    "MODEL_NAME",
    "MODEL_SIZE",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TEMPERATURE",
    "REFLECTION_TEMPERATURE",
    "DEFAULT_MAX_ITERS",
    "DEFAULT_RETRIEVAL_K",
    "DEFAULT_TFIDF_THRESHOLD"
]
