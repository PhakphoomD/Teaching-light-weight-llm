"""
TinyLlama 1.1B default configuration
"""

# Model configuration
MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
MODEL_SIZE = "1.1B"

# Generation parameters
DEFAULT_MAX_TOKENS = 150
DEFAULT_TEMPERATURE = 0.3
REFLECTION_MAX_TOKENS = 200
REFLECTION_TEMPERATURE = 0.7

# Evaluation parameters
DEFAULT_MAX_ITERS = 3
DEFAULT_RETRIEVAL_K = 3
DEFAULT_TFIDF_THRESHOLD = 0.1
