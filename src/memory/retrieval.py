"""
Retrieval Strategies for Memory System

Concrete implementations of retrieval strategies:
- BaselineRetrieval: No retrieval (empty context)
- RuleKeyRetrieval: Fast O(1) pattern-based lookup using rule keys
- TFIDFRetrieval: Similarity-based retrieval using TF-IDF with n-gram enhancement
"""

import time
from typing import List, Protocol
from abc import ABC, abstractmethod

from src.memory.store import JsonMemoryStore, Feedback


class RetrievalStrategy(ABC):
    """
    Abstract base class for retrieval strategies.
    
    Implementations define how to retrieve relevant past feedbacks from memory.
    """
    
    @abstractmethod
    def retrieve(
        self, 
        memory: JsonMemoryStore, 
        question: str,
        **kwargs
    ) -> tuple[List[Feedback], int]:
        """
        Retrieve relevant past feedbacks for a question.
        
        Args:
            memory: Memory store instance
            question: Current question text
            **kwargs: Strategy-specific parameters
            
        Returns:
            Tuple of (list of feedbacks, retrieval time in ms)
        """
        pass
    
    @abstractmethod
    def store_feedback(
        self,
        memory: JsonMemoryStore,
        question: str,
        feedback: Feedback
    ) -> None:
        """
        Store feedback in memory using strategy-specific approach.
        
        Args:
            memory: Memory store instance
            question: Question text (may be used for indexing)
            feedback: Feedback to store
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return strategy name for logging/reporting."""
        pass


class BaselineRetrieval(RetrievalStrategy):
    """
    Baseline retrieval strategy - no retrieval.
    
    Always returns empty feedback list. Used for baseline experiments
    without memory retrieval.
    """
    
    def retrieve(
        self, 
        memory: JsonMemoryStore, 
        question: str,
        **kwargs
    ) -> tuple[List[Feedback], int]:
        """
        Return empty feedback list (no retrieval).
        
        Args:
            memory: Memory store instance (unused)
            question: Current question text (unused)
            **kwargs: Ignored
            
        Returns:
            Tuple of (empty list, 0ms retrieval time)
        """
        return [], 0
    
    def store_feedback(
        self,
        memory: JsonMemoryStore,
        question: str,
        feedback: Feedback
    ) -> None:
        """
        No-op for baseline (don't store).
        
        Args:
            memory: Memory store instance (unused)
            question: Question text (unused)
            feedback: Feedback (unused)
        """
        pass
    
    @property
    def name(self) -> str:
        return "baseline_no_retrieval"


class RuleKeyRetrieval(RetrievalStrategy):
    """
    Rule-key based retrieval strategy.
    
    Uses pattern-based keys (exact:X, keyword:Y,Z) for O(1) lookup.
    Fast and deterministic, ideal for exact pattern matching.
    """
    
    def __init__(self, k: int = 3):
        """
        Initialize rule-key retrieval.
        
        Args:
            k: Number of past feedbacks to retrieve
        """
        self.k = k
    
    def retrieve(
        self, 
        memory: JsonMemoryStore, 
        question: str,
        **kwargs
    ) -> tuple[List[Feedback], int]:
        """
        Retrieve feedbacks using rule-key lookup.
        
        Args:
            memory: Memory store instance
            question: Current question text
            **kwargs: Ignored for this strategy
            
        Returns:
            Tuple of (list of feedbacks, retrieval time in ms)
        """
        start = time.time()
        feedbacks = memory.get_by_rule(question, limit=self.k)
        retrieval_ms = int((time.time() - start) * 1000)
        return feedbacks, retrieval_ms
    
    def store_feedback(
        self,
        memory: JsonMemoryStore,
        question: str,
        feedback: Feedback
    ) -> None:
        """
        Store feedback in global rule-key bucket.
        
        Args:
            memory: Memory store instance
            question: Question text (used for rule key generation)
            feedback: Feedback to store
        """
        # Store in global rule-key bucket to avoid per-attempt/task bloat
        memory.add_global_feedback(question, feedback)
    
    @property
    def name(self) -> str:
        return f"rule_key_k{self.k}"


class TFIDFRetrieval(RetrievalStrategy):
    """
    TF-IDF similarity-based retrieval strategy.
    
    Uses word overlap (Jaccard similarity with n-gram enhancement) to find 
    semantically related past feedbacks. More flexible than rule-key but slower.
    """
    
    def __init__(self, k: int = 3, threshold: float = 0.1):
        """
        Initialize TF-IDF retrieval.
        
        Args:
            k: Number of past feedbacks to retrieve
            threshold: Minimum similarity score (0-1)
        """
        self.k = k
        self.threshold = threshold
    
    def retrieve(
        self, 
        memory: JsonMemoryStore, 
        question: str,
        **kwargs
    ) -> tuple[List[Feedback], int]:
        """
        Retrieve feedbacks using TF-IDF similarity.
        
        Args:
            memory: Memory store instance
            question: Current question text
            **kwargs: Ignored for this strategy
            
        Returns:
            Tuple of (list of feedbacks, retrieval time in ms)
        """
        start = time.time()
        feedbacks = memory.get_by_tfidf(question, limit=self.k, threshold=self.threshold)
        retrieval_ms = int((time.time() - start) * 1000)
        return feedbacks, retrieval_ms
    
    def store_feedback(
        self,
        memory: JsonMemoryStore,
        question: str,
        feedback: Feedback
    ) -> None:
        """
        Store feedback in contextual bucket for TF-IDF indexing.
        
        Args:
            memory: Memory store instance
            question: Question text (used for TF-IDF indexing)
            feedback: Feedback to store
        """
        # Store in contextual bucket (not per-task) for efficient TF-IDF retrieval
        memory.add_contextual_feedback(question, feedback)
    
    @property
    def name(self) -> str:
        return f"tfidf_k{self.k}_t{self.threshold}"
