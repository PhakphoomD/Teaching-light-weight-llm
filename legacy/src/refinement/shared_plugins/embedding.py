"""
Shared Embedding Plugin

Provides embedding functionality for vector operations.
"""

from sentence_transformers import SentenceTransformer
from ...core.logger import get_logger

logger = get_logger("refinement.shared.embedding")


class EmbeddingWrapper:
    """
    Embedding wrapper for SentenceTransformer.
    
    Used by:
    - VectorIndex (memory retrieval)
    - SemanticRuleStore (rule clustering)
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding model.
        
        Args:
            model_name: SentenceTransformer model name
        """
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        
        logger.info(f"EmbeddingWrapper initialized with model: {model_name}")
    
    def encode(self, text: str):
        """
        Encode text to embedding vector.
        
        Args:
            text: Text to encode
        
        Returns:
            Embedding vector (numpy array)
        """
        return self.model.encode([text])[0]
    
    def encode_batch(self, texts: list):
        """
        Encode multiple texts.
        
        Args:
            texts: List of texts
        
        Returns:
            List of embedding vectors
        """
        return self.model.encode(texts)
