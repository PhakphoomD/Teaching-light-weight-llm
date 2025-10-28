"""
Retrieval Strategies for Memory System

Concrete implementations of retrieval strategies:
- BaselineRetrieval: No retrieval (empty context)
- RuleKeyRetrieval: Fast O(1) pattern-based lookup using rule keys
- TFIDFRetrieval: Similarity-based retrieval using TF-IDF with n-gram enhancement

Phase 4 additions:
- get_task_recent(): Retrieve most recent n feedbacks for a specific task
"""

import time
from typing import List, Protocol, Optional
from abc import ABC, abstractmethod

from src.memory.store import JsonMemoryStore, Feedback, FeedbackLite


def get_task_recent(
    memory: JsonMemoryStore,
    task_id: str,
    n: int = 2
) -> List[FeedbackLite]:
    """
    Retrieve the n most recent feedbacks for a specific task.
    
    Phase 4: Used for reflection to show "Previous attempt" context.
    Retrieves from by_task index for O(1) lookup.
    
    Args:
        memory: Memory store instance
        task_id: Task identifier
        n: Number of recent feedbacks to retrieve (default: 2)
        
    Returns:
        List of FeedbackLite objects, most recent first
        
    Example:
        >>> recent = get_task_recent(memory, "alpaca-001", n=2)
        >>> for fb in recent:
        ...     print(f"Lesson: {fb.lesson}")
        ...     print(f"Errors: {fb.error_keys}")
    """
    with memory._lock:
        # Get entry IDs from by_task index
        task_key = f"task:{task_id}"
        entry_ids = memory._data.get("index", {}).get(task_key, [])
        
        if not entry_ids:
            # Fallback: check legacy tasks bucket
            legacy_items = memory._data.get("tasks", {}).get(task_id, [])
            if legacy_items:
                # Convert legacy format on-the-fly (best effort)
                result = []
                for item in legacy_items[-n:]:
                    if isinstance(item, dict):
                        fb_lite = FeedbackLite(
                            lesson=item.get("message", "")[:300],
                            error_keys=["error:legacy"],
                            student_answer_short="",
                            ts=item.get("timestamp", ""),
                            task_id=task_id
                        )
                        result.append(fb_lite)
                return result[::-1]  # Most recent first
            return []
        
        # Get most recent n entries
        recent_ids = entry_ids[-n:]
        
        # Fetch actual entries
        feedbacks = []
        for entry_id in reversed(recent_ids):  # Most recent first
            entry = memory._data.get("entries", {}).get(entry_id)
            if entry:
                fb_lite = FeedbackLite(
                    lesson=entry.get("lesson", ""),
                    error_keys=entry.get("error_keys", []),
                    student_answer_short=entry.get("student_answer_short", ""),
                    ts=entry.get("ts", ""),
                    task_id=entry.get("task_id")
                )
                feedbacks.append(fb_lite)
        
        return feedbacks


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


class EnhancedRuleKeyRetrieval(RetrievalStrategy):
    """
    Enhanced rule-key retrieval with multi-level priority and TF-IDF fallback.
    
    Retrieval Order Strategy:
    1. Priority 1: task:* exact match (O(1) lookup)
    2. Priority 2: keyword ∩ error (intersection of keyword and error keys)
    3. Priority 3: format:* matches
    4. Priority 4: TF-IDF fallback (semantic similarity)
    
    This provides robust retrieval with graceful degradation when exact matches fail.
    """
    
    def __init__(self, k: Optional[int] = None, tfidf_threshold: Optional[float] = None):
        """
        Initialize enhanced rule-key retrieval.
        
        Phase 4: Reads defaults from config.yaml if not provided.
        
        Args:
            k: Number of past feedbacks to retrieve (default from config: k_similar=2)
            tfidf_threshold: Minimum similarity score for TF-IDF fallback (default from config: 0.30)
        """
        # Load defaults from config if not provided
        if k is None or tfidf_threshold is None:
            try:
                from config.ai_config import load_config
                cfg, _ = load_config()
                if k is None:
                    k = cfg.memory.retrieval.get("k_similar", 2)
                if tfidf_threshold is None:
                    tfidf_threshold = cfg.memory.retrieval.get("tfidf", {}).get("min_cosine", 0.30)
            except:
                k = k or 3
                tfidf_threshold = tfidf_threshold or 0.30
        
        # Ensure values are set (for type checking)
        self.k: int = k if k is not None else 3
        self.tfidf_threshold: float = tfidf_threshold if tfidf_threshold is not None else 0.30
    
    def retrieve(
        self, 
        memory: JsonMemoryStore, 
        question: str,
        **kwargs
    ) -> tuple[List[Feedback], int]:
        """
        Retrieve feedbacks using multi-level priority strategy.
        
        Args:
            memory: Memory store instance
            question: Current question text
            **kwargs: Optional parameters:
                - task_id: Task identifier for Priority 1 lookup
                - previous_error_types: List of error types from previous attempts
            
        Returns:
            Tuple of (list of feedbacks, retrieval time in ms)
        """
        from src.memory.key_generator import MultiKeyGenerator
        
        start = time.time()
        generator = MultiKeyGenerator()
        
        # Generate query keys
        query_keys = generator.generate_retrieval_query_keys(
            question, 
            kwargs.get("previous_error_types")
        )
        
        results = []
        seen_hashes = set()
        
        # Priority 1: Task exact match (if task_id provided)
        task_id = kwargs.get("task_id")
        if task_id:
            task_key = f"task:{task_id}"
            task_feedbacks = memory.get_by_multi_key(task_key, limit=self.k)
            
            for fb in task_feedbacks:
                fb_hash = self._hash_feedback(fb)
                if fb_hash not in seen_hashes:
                    seen_hashes.add(fb_hash)
                    results.append(fb)
        
        # Priority 2: Keyword ∩ Error (intersection)
        if len(results) < self.k and query_keys["priority_2"]:
            for combined_key in query_keys["priority_2"]:
                # Parse "keyword:X+error:Y" format
                if "+" in combined_key:
                    parts = combined_key.split("+")
                    if len(parts) == 2:
                        # Get both keyword and error results
                        kw_results = memory.get_by_multi_key(parts[0].strip())
                        err_results = memory.get_by_multi_key(parts[1].strip())
                        
                        # Find intersection by task_id
                        kw_task_ids = {fb.task_id for fb in kw_results}
                        
                        for fb in err_results:
                            if fb.task_id in kw_task_ids:
                                fb_hash = self._hash_feedback(fb)
                                if fb_hash not in seen_hashes:
                                    seen_hashes.add(fb_hash)
                                    results.append(fb)
                                    
                                    if len(results) >= self.k:
                                        break
                    
                if len(results) >= self.k:
                    break
        
        # Priority 3: Format matches
        if len(results) < self.k and query_keys["priority_3"]:
            for key in query_keys["priority_3"]:
                format_feedbacks = memory.get_by_multi_key(key)
                
                for fb in format_feedbacks:
                    fb_hash = self._hash_feedback(fb)
                    if fb_hash not in seen_hashes:
                        seen_hashes.add(fb_hash)
                        results.append(fb)
                        
                        if len(results) >= self.k:
                            break
                
                if len(results) >= self.k:
                    break
        
        # Priority 4: Keyword fallback
        if len(results) < self.k and query_keys["priority_4"]:
            for key in query_keys["priority_4"]:
                kw_feedbacks = memory.get_by_multi_key(key)
                
                for fb in kw_feedbacks:
                    fb_hash = self._hash_feedback(fb)
                    if fb_hash not in seen_hashes:
                        seen_hashes.add(fb_hash)
                        results.append(fb)
                        
                        if len(results) >= self.k:
                            break
                
                if len(results) >= self.k:
                    break
        
        # Priority 5: TF-IDF fallback
        if len(results) < self.k:
            tfidf_feedbacks = memory.get_by_tfidf(
                question, 
                limit=self.k - len(results), 
                threshold=self.tfidf_threshold
            )
            
            for fb in tfidf_feedbacks:
                fb_hash = self._hash_feedback(fb)
                if fb_hash not in seen_hashes:
                    seen_hashes.add(fb_hash)
                    results.append(fb)
        
        # Limit to k results
        final_results = results[:self.k]
        
        retrieval_ms = int((time.time() - start) * 1000)
        return final_results, retrieval_ms
    
    def store_feedback(
        self,
        memory: JsonMemoryStore,
        question: str,
        feedback: Feedback
    ) -> None:
        """
        Store feedback using multi-key indexing (deprecated - use add_feedback_multi_key directly).
        
        Args:
            memory: Memory store instance
            question: Question text (unused in new system)
            feedback: Feedback to store (unused in new system)
        """
        # Note: In the new system, use memory.add_feedback_multi_key() directly
        # This method is kept for backward compatibility but should not be used
        pass
    
    @property
    def name(self) -> str:
        return f"enhanced_rulekey_k{self.k}_tfidf_fallback"
    
    @staticmethod
    def _hash_feedback(fb: Feedback) -> str:
        """Hash feedback for deduplication."""
        from src.memory.utils import hash_feedback
        return hash_feedback(fb.message)
