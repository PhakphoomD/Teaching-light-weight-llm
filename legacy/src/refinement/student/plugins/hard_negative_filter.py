"""
Hard-Negative Filter Module

This module tracks and filters contexts that cause quality degradation.
When a context leads to worse performance, it's marked as a "hard negative"
and filtered out in future retrievals.

Example:
    >>> filter = HardNegativeFilter()
    >>> # If context caused quality drop
    >>> filter.add_negative("Lesson: Use logistic regression...")
    >>> # Later, check before using
    >>> if not filter.should_filter(context_text, threshold=2):
    ...     # Use this context
"""

import json
from pathlib import Path
from typing import Dict, List
import hashlib

from src.core.logger import get_logger

logger = get_logger("memory.hard_negatives")


class HardNegativeFilter:
    """
    Filter for tracking and blocking contexts that degrade performance.
    
    Hard negatives are contexts that, when provided to the student,
    lead to worse answers (lower stop_score). This typically happens when:
    - The context is misleading or incorrect
    - The context is from a different domain/task
    - The context confuses rather than helps
    
    Architecture:
        - Hash context text to create stable IDs
        - Track count of times each context caused degradation
        - Filter contexts with count >= threshold
    
    Storage format (hard_negatives.json):
        {
            "a1b2c3d4": 3,  # context_hash: negative_count
            "e5f6g7h8": 2,
            ...
        }
    """
    
    def __init__(self, file_path: str = "logs/memory/hard_negatives.json"):
        """
        Initialize hard-negative filter.
        
        Args:
            file_path: Path to JSON file storing negative counts
        """
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.negatives: Dict[str, int] = {}
        self._load()
        
        logger.info(f"HardNegativeFilter initialized with {len(self.negatives)} tracked contexts")
    
    def _load(self) -> None:
        """Load negative counts from JSON file."""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.negatives = json.load(f)
                logger.debug(f"Loaded {len(self.negatives)} hard-negative contexts")
            except Exception as e:
                logger.error(f"Failed to load hard-negatives: {e}")
                self.negatives = {}
        else:
            logger.debug("No existing hard-negatives file")
    
    def _save(self) -> None:
        """Save negative counts to JSON file."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.negatives, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(self.negatives)} hard-negative contexts")
        except Exception as e:
            logger.error(f"Failed to save hard-negatives: {e}")
    
    def _hash_context(self, context_text: str) -> str:
        """
        Create stable hash for context text.
        
        Args:
            context_text: The context string
        
        Returns:
            8-character hex hash
        """
        # Normalize text (lowercase, strip) for consistent hashing
        normalized = context_text.strip().lower()
        hash_obj = hashlib.md5(normalized.encode('utf-8'))
        return hash_obj.hexdigest()[:8]
    
    def add_negative(self, context_text: str) -> None:
        """
        Mark a context as causing quality degradation.
        
        Args:
            context_text: The context that led to worse performance
        
        Example:
            >>> filter.add_negative("Lesson: Always use method X")
            >>> # Now tracked with count=1
        """
        if not context_text or not context_text.strip():
            return
        
        ctx_hash = self._hash_context(context_text)
        self.negatives[ctx_hash] = self.negatives.get(ctx_hash, 0) + 1
        
        count = self.negatives[ctx_hash]
        logger.debug(
            f"Added hard-negative: {ctx_hash} "
            f"(count={count}, text={context_text[:50]}...)"
        )
        
        self._save()
    
    def should_filter(self, context_text: str, threshold: int = 2) -> bool:
        """
        Check if a context should be filtered out.
        
        Args:
            context_text: The context to check
            threshold: Minimum negative count to filter (default: 2)
        
        Returns:
            True if context should be filtered (count >= threshold)
        
        Example:
            >>> if filter.should_filter(context, threshold=2):
            ...     # Skip this context
            ...     continue
        """
        if not context_text or not context_text.strip():
            return False
        
        ctx_hash = self._hash_context(context_text)
        count = self.negatives.get(ctx_hash, 0)
        
        should_block = count >= threshold
        
        if should_block:
            logger.debug(
                f"Filtering hard-negative: {ctx_hash} "
                f"(count={count} >= threshold={threshold})"
            )
        
        return should_block
    
    def filter_contexts(
        self,
        contexts: List[str],
        threshold: int = 2
    ) -> List[str]:
        """
        Filter a list of contexts, removing hard negatives.
        
        Args:
            contexts: List of context strings
            threshold: Minimum negative count to filter
        
        Returns:
            Filtered list with hard negatives removed
        
        Example:
            >>> contexts = ["Lesson: A", "Lesson: B", "Lesson: C"]
            >>> filtered = filter.filter_contexts(contexts, threshold=2)
            >>> # Returns only contexts with count < 2
        """
        if not contexts:
            return []
        
        original_count = len(contexts)
        filtered = [
            ctx for ctx in contexts
            if not self.should_filter(ctx, threshold)
        ]
        
        removed_count = original_count - len(filtered)
        if removed_count > 0:
            logger.info(
                f"Filtered {removed_count}/{original_count} hard-negative contexts "
                f"(threshold={threshold})"
            )
        
        return filtered
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about hard negatives.
        
        Returns:
            Dict with stats:
            - total_tracked: Total unique contexts tracked
            - high_negative: Contexts with count >= 5
            - medium_negative: Contexts with count 2-4
            - low_negative: Contexts with count 1
        """
        stats = {
            "total_tracked": len(self.negatives),
            "high_negative": sum(1 for c in self.negatives.values() if c >= 5),
            "medium_negative": sum(1 for c in self.negatives.values() if 2 <= c < 5),
            "low_negative": sum(1 for c in self.negatives.values() if c == 1)
        }
        return stats
    
    def clear(self) -> None:
        """
        Clear all hard-negative tracking.
        
        Warning: This is irreversible!
        """
        self.negatives = {}
        self._save()
        logger.warning("Cleared all hard-negative tracking")
