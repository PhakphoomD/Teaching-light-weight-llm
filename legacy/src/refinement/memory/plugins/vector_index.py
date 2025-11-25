"""
Vector Index Module

This module provides vector-based retrieval using FAISS and SentenceTransformers.
Enables semantic search over teaching records.
"""

import numpy as np
import faiss
from pathlib import Path
from typing import List, Tuple, Optional
from sentence_transformers import SentenceTransformer

from src.core.logger import get_logger

logger = get_logger("memory.vector")


class VectorIndex:
    """
    Vector-based semantic search index using FAISS and SentenceTransformers.
    
    This class provides efficient similarity search over text embeddings.
    Uses FAISS (Facebook AI Similarity Search) for fast nearest neighbor lookup
    and SentenceTransformers for generating embeddings.
    
    Why normalized embeddings with IndexFlatIP?
    -------------------------------------------
    We use FAISS's IndexFlatIP (Inner Product) with L2-normalized embeddings.
    This is mathematically equivalent to cosine similarity:
    
        cosine_sim(A, B) = (A   B) / (||A|| x ||B||)
        
    When vectors are L2-normalized (||A|| = ||B|| = 1):
        cosine_sim(A, B) = A   B  (inner product)
    
    Benefits:
    - Inner product is faster than cosine distance computation
    - FAISS's IndexFlatIP is optimized for this
    - Results are identical to cosine similarity
    
    Architecture:
        [Text] -> [SentenceTransformer] -> [384-dim embedding]
               -> [L2 normalize] -> [FAISS IndexFlatIP]
               -> [Top-K search] -> [Record IDs]
    
    Example:
        >>> index = VectorIndex(
        ...     embedding_model="all-MiniLM-L6-v2",
        ...     index_path="logs/memory/faiss.index"
        ... )
        >>> index.add_record("q001", "What is the capital of France? Paris")
        >>> results = index.retrieve("French capital city", k=5)
        >>> print(results)  # ['q001', ...]
    """
    
    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        index_path: str = "logs/memory/faiss.index",
        dim: Optional[int] = None
    ):
        """
        Initialize the vector index.
        
        Args:
            embedding_model: HuggingFace model name for embeddings
            index_path: Path to save/load FAISS index
            dim: Embedding dimension (auto-detected if None)
        
        Notes:
            - all-MiniLM-L6-v2: 384 dimensions, fast, good quality
            - all-mpnet-base-v2: 768 dimensions, slower, better quality
            - See: https://www.sbert.net/docs/pretrained_models.html
        """
        self.index_path = Path(index_path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.encoder = SentenceTransformer(embedding_model)
        
        # Get embedding dimension
        if dim is None:
            # Auto-detect dimension from model
            test_embed = self.encoder.encode(["test"])
            self.dim = test_embed.shape[1]
        else:
            self.dim = dim
        
        logger.info(f"Embedding dimension: {self.dim}")
        
        # Initialize or load FAISS index
        self.ids: List[str] = []  # Mapping from FAISS index to record IDs
        
        if self.index_path.exists():
            self._load_index()
        else:
            self._create_index()
    
    def _create_index(self) -> None:
        """
        Create a new FAISS index.
        
        We use IndexFlatIP (Inner Product) which works well with
        normalized embeddings for cosine similarity search.
        """
        logger.info(f"Creating new FAISS index with dim={self.dim}")
        
        # IndexFlatIP: Flat index with inner product similarity
        # - "Flat" means brute-force search (exact, not approximate)
        # - "IP" means inner product (with normalized vectors = cosine sim)
        self.index = faiss.IndexFlatIP(self.dim)
        
        logger.info("FAISS index created")
    
    def _load_index(self) -> None:
        """
        Load existing FAISS index from disk.
        
        Also loads the ID mapping from a companion .ids file.
        """
        logger.info(f"Loading FAISS index from: {self.index_path}")
        
        try:
            # Load FAISS index
            self.index = faiss.read_index(str(self.index_path))
            
            # Load ID mapping
            ids_path = self.index_path.with_suffix(".ids")
            if ids_path.exists():
                with open(ids_path, "r", encoding="utf-8") as f:
                    self.ids = [line.strip() for line in f if line.strip()]
            else:
                logger.warning("IDs file not found, starting with empty mapping")
                self.ids = []
            
            logger.info(f"Loaded {self.index.ntotal} vectors with {len(self.ids)} IDs")
            
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            logger.info("Creating new index instead")
            self._create_index()
    
    def _save_index(self) -> None:
        """
        Save FAISS index and ID mapping to disk.
        """
        try:
            # Save FAISS index
            faiss.write_index(self.index, str(self.index_path))
            
            # Save ID mapping
            ids_path = self.index_path.with_suffix(".ids")
            with open(ids_path, "w", encoding="utf-8") as f:
                for record_id in self.ids:
                    f.write(f"{record_id}\n")
            
            logger.debug(f"Saved index with {self.index.ntotal} vectors")
            
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            raise
    
    def add_record(self, rec_id: str, text: str) -> None:
        """
        Add a record to the vector index.
        
        This method:
        1. Computes embedding for the text
        2. L2-normalizes the embedding (for cosine similarity)
        3. Adds to FAISS index
        4. Updates ID mapping
        5. Saves index to disk
        
        Args:
            rec_id: Unique identifier for the record
            text: Text to embed (e.g., question + answer + hints)
        
        Example:
            >>> # Combine multiple fields for better matching
            >>> text = f"{question} {refined_answer} {' '.join(feedbacks)}"
            >>> index.add_record(rec_id, text)
        
        Note:
            Text preprocessing:
            - Consider combining relevant fields (question, answer, hints)
            - Remove or normalize special characters if needed
            - Longer text = more context but may dilute specific terms
        """
        if not text or not text.strip():
            logger.warning(f"Empty text for record {rec_id}, skipping")
            return
        
        try:
            # Compute embedding
            # Returns shape: (1, dim)
            embedding = self.encoder.encode([text], convert_to_numpy=True)
            
            # L2 normalize for cosine similarity
            # After normalization: ||embedding|| = 1
            embedding = embedding / np.linalg.norm(embedding, axis=1, keepdims=True)
            
            # Ensure correct shape and type
            embedding = embedding.astype('float32')
            
            # Add to FAISS index
            # FAISS expects 2D array of shape (n_vectors, dim)
            self.index.add(embedding)  # type: ignore  # embedding is already (1, dim)
            
            # Update ID mapping
            self.ids.append(rec_id)
            
            # Save index
            self._save_index()
            
            logger.debug(f"Added record {rec_id} to index (total: {self.index.ntotal})")
            
        except Exception as e:
            logger.error(f"Failed to add record {rec_id}: {e}")
            raise
    
    def retrieve(self, query: str, k: int = 5) -> List[str]:
        """
        Retrieve top-k most similar records for a query.
        
        Args:
            query: Query text
            k: Number of results to return
        
        Returns:
            List of record IDs, ordered by similarity (most similar first)
        
        Example:
            >>> ids = index.retrieve("What is the capital of France?", k=3)
            >>> print(ids)  # ['q042', 'q015', 'q103']
        
        Note:
            - Returns fewer than k results if index has fewer records
            - Returns empty list if index is empty or query embedding fails
        """
        if self.index.ntotal == 0:
            logger.warning("Index is empty, cannot retrieve")
            return []
        
        if not query or not query.strip():
            logger.warning("Empty query, returning empty results")
            return []
        
        try:
            # Compute query embedding
            query_embedding = self.encoder.encode([query], convert_to_numpy=True)
            
            # L2 normalize (same as indexed embeddings)
            query_embedding = query_embedding / np.linalg.norm(
                query_embedding, axis=1, keepdims=True
            )
            query_embedding = query_embedding.astype('float32')
            
            # Limit k to available records
            k = min(k, self.index.ntotal)
            
            # Search FAISS index
            # Returns: (distances, indices)
            # - distances: Inner product scores (higher = more similar)
            # - indices: FAISS internal indices
            # query_embedding is (1, dim), k is the number of neighbors
            distances, indices = self.index.search(query_embedding, k)  # type: ignore
            
            # Map FAISS indices to record IDs
            result_ids = []
            for idx in indices[0]:  # indices[0] because we have 1 query
                if 0 <= idx < len(self.ids):
                    result_ids.append(self.ids[idx])
                else:
                    logger.warning(f"Invalid index {idx}, skipping")
            
            logger.debug(
                f"Retrieved {len(result_ids)} results for query: {query[:50]}..."
            )
            
            return result_ids
            
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return []
    
    def retrieve_with_scores(
        self,
        query: str,
        k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Retrieve top-k results with similarity scores.
        
        Args:
            query: Query text
            k: Number of results
        
        Returns:
            List of (record_id, score) tuples, ordered by score
        
        Example:
            >>> results = index.retrieve_with_scores("capital of France", k=3)
            >>> for rec_id, score in results:
            ...     print(f"{rec_id}: {score:.3f}")
            q042: 0.867
            q015: 0.742
            q103: 0.689
        """
        if self.index.ntotal == 0 or not query.strip():
            return []
        
        try:
            query_embedding = self.encoder.encode([query], convert_to_numpy=True)
            query_embedding = query_embedding / np.linalg.norm(
                query_embedding, axis=1, keepdims=True
            )
            query_embedding = query_embedding.astype('float32')
            
            k = min(k, self.index.ntotal)
            # query_embedding is (1, dim), k is the number of neighbors
            distances, indices = self.index.search(query_embedding, k)  # type: ignore
            
            results = []
            for idx, score in zip(indices[0], distances[0]):
                if 0 <= idx < len(self.ids):
                    results.append((self.ids[idx], float(score)))
            
            return results
            
        except Exception as e:
            logger.error(f"Retrieval with scores failed: {e}")
            return []
    
    def get_stats(self) -> dict:
        """
        Get statistics about the index.
        
        Returns:
            Dict with index statistics
        """
        return {
            "total_vectors": self.index.ntotal,
            "dimension": self.dim,
            "total_ids": len(self.ids),
            "index_type": type(self.index).__name__,
            "embedding_model": self.encoder.get_sentence_embedding_dimension(),
        }
