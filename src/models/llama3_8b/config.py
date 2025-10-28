"""
Meta Llama 3 8B default configuration
"""

# Model configuration
MODEL_NAME = "meta-llama/Meta-Llama-3-8B"
MODEL_SIZE = "8B"

# Generation parameters
DEFAULT_MAX_TOKENS = 256
DEFAULT_TEMPERATURE = 0.4
REFLECTION_MAX_TOKENS = 300
REFLECTION_TEMPERATURE = 0.7

# Evaluation parameters
DEFAULT_MAX_ITERS = 3
DEFAULT_RETRIEVAL_K = 3
DEFAULT_TFIDF_THRESHOLD = 0.1
