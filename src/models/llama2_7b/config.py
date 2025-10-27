"""
Llama2 7B Configuration

Hyperparameters and settings for Llama2 7B model.
"""

# Model settings
MODEL_NAME = "llama2-7b"
MODEL_SIZE = "7B"

# Training/inference parameters
DEFAULT_MAX_ITERS = 3
DEFAULT_TEMPERATURE = 0.3
REFLECTION_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 300  # Larger context than TinyLlama

# Retrieval settings
DEFAULT_RETRIEVAL_K = 5  # More context than TinyLlama
DEFAULT_TFIDF_THRESHOLD = 0.15
