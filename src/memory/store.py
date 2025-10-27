"""
Memory Store Abstractions

Provides a simple interface for storing and retrieving feedback that the
"student" model should remember across iterations. Default implementation
persists to a JSON file on disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Set
import json
import os
from threading import RLock
from src.memory.utils import compute_rule_key, hash_feedback


@dataclass
class Feedback:
    task_id: str
    message: str
    source: str = "critic"  # who wrote this


class MemoryStore:
    """Abstract memory interface."""

    def add_feedback(self, fb: Feedback) -> None:
        raise NotImplementedError

    def get_feedback(self, task_id: str, limit: Optional[int] = None) -> List[Feedback]:
        raise NotImplementedError

    def get_context(self, task_id: str, limit: int = 5) -> str:
        """Return a concise context string to prepend to the prompt."""
        fbs = self.get_feedback(task_id, limit=limit)
        if not fbs:
            return ""
        lines = [f"- {fb.message}" for fb in fbs[-limit:]]
        return "\n".join(lines)


class JsonMemoryStore(MemoryStore):
    """JSON file-backed memory store with rule_key indexing.

    Data shape:
    {
      "tasks": {
        "<task_id>": [
           {"task_id": "...", "message": "...", "source": "critic"},
           ...
        ],
        ...
      },
      "rules": {
        "<rule_key>": [
           {"task_id": "...", "message": "...", "source": "critic", "hash": "..."},
           ...
        ],
        ...
      }
    }
    
    The "rules" bucket enables fast retrieval by pattern (e.g., exact:ready, keyword:calculate).
    Deduplication via hash prevents storing identical feedback multiple times.
    Per-key cap ensures memory doesn't grow unbounded.
    """

    def __init__(
        self,
        path: str = "data/memory.json",
        cap_per_task: int = 5,
        cap_per_rule: int = 5
    ) -> None:
        self.path = path
        self.cap_per_task = cap_per_task
        self.cap_per_rule = cap_per_rule
        self._lock = RLock()
        self._data: Dict[str, Any] = {"tasks": {}, "rules": {}}
        self._ensure_file()
        self._load()

    def _ensure_file(self) -> None:
        folder = os.path.dirname(self.path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"tasks": {}, "rules": {}}, f)

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
                # Handle old format (flat dict) or new format (tasks/rules)
                if isinstance(raw, dict):
                    if "tasks" in raw or "rules" in raw:
                        self._data = raw
                        # Ensure both keys exist
                        self._data.setdefault("tasks", {})
                        self._data.setdefault("rules", {})
                    else:
                        # Old format: migrate to new
                        self._data = {"tasks": raw, "rules": {}}
        except Exception:
            # Corrupt file; reset to empty
            self._data = {"tasks": {}, "rules": {}}

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def add_feedback(self, fb: Feedback) -> None:
        """Add feedback to per-task bucket with cap enforcement."""
        with self._lock:
            bucket = self._data["tasks"].setdefault(fb.task_id, [])
            bucket.append({"task_id": fb.task_id, "message": fb.message, "source": fb.source})
            
            # Enforce cap: keep only last N
            if len(bucket) > self.cap_per_task:
                self._data["tasks"][fb.task_id] = bucket[-self.cap_per_task:]
            
            self._save()

    def get_feedback(self, task_id: str, limit: Optional[int] = None) -> List[Feedback]:
        """Get per-task feedback."""
        with self._lock:
            items = self._data["tasks"].get(task_id, [])
            if limit is not None:
                items = items[-limit:]
            return [Feedback(**it) for it in items]
    
    def add_global_feedback(self, question: str, fb: Feedback, similarity_threshold: float = 0.8) -> None:
        """
        Add feedback to global rule_key bucket with smart deduplication and cap.
        
        Uses both exact hash matching and similarity-based deduplication to prevent
        storing nearly identical feedback (>80% similar by default).
        
        Args:
            question: The question text (used to compute rule_key)
            fb: Feedback to store
            similarity_threshold: Minimum similarity (0-1) to consider as duplicate (default 0.8)
        """
        with self._lock:
            from src.memory.utils import is_similar_feedback
            
            rule_key = compute_rule_key(question)
            bucket = self._data["rules"].setdefault(rule_key, [])
            
            # Compute hash for exact deduplication
            fb_hash = hash_feedback(fb.message)
            
            # Check exact duplicates by hash
            existing_hashes: Set[str] = {
                item.get("hash", "") for item in bucket
            }
            
            if fb_hash in existing_hashes:
                # Exact duplicate; skip
                return
            
            # Smart deduplication: check similarity with existing feedbacks
            existing_messages = [item.get("message", "") for item in bucket]
            if is_similar_feedback(fb.message, existing_messages, threshold=similarity_threshold):
                # Too similar to existing feedback; skip
                return
            
            # Add new feedback with hash
            bucket.append({
                "task_id": fb.task_id,
                "message": fb.message,
                "source": fb.source,
                "hash": fb_hash
            })
            
            # Enforce cap: keep only last N
            if len(bucket) > self.cap_per_rule:
                self._data["rules"][rule_key] = bucket[-self.cap_per_rule:]
            
            self._save()
    
    def get_by_rule(self, question: str, limit: Optional[int] = None) -> List[Feedback]:
        """
        Retrieve feedback by rule_key pattern.
        
        Args:
            question: The question text (used to compute rule_key)
            limit: Max number of feedback items to return (None = all)
            
        Returns:
            List of Feedback matching the rule pattern
        """
        with self._lock:
            rule_key = compute_rule_key(question)
            items = self._data["rules"].get(rule_key, [])
            
            if limit is not None:
                items = items[-limit:]
            
            # Convert to Feedback objects (excluding hash field)
            return [
                Feedback(
                    task_id=it["task_id"],
                    message=it["message"],
                    source=it["source"]
                )
                for it in items
            ]
    
    def get_by_tfidf(self, question: str, limit: int = 3, threshold: float = 0.1) -> List[Feedback]:
        """
        Retrieve feedback using TF-IDF similarity by comparing with original questions.
        
        Flow:
        1. Collect all feedbacks from contexts bucket (which stores original questions)
        2. Compute n-gram enhanced TF-IDF similarity between current question and stored questions
        3. Return top-K most similar feedbacks above threshold (deduplicated)
        
        Args:
            question: The question text
            limit: Max number of feedback items to return
            threshold: Minimum similarity score (0-1, default 0.1)
            
        Returns:
            List of most similar Feedback items based on question similarity
        """
        with self._lock:
            from src.memory.utils import compute_tfidf_similarity, hash_feedback
            
            # Ensure contexts bucket exists
            if "contexts" not in self._data:
                self._data["contexts"] = {}
            
            # Collect all feedbacks from contexts bucket with their original questions
            feedback_pool = []
            seen_hashes = set()
            
            for context_key, items in self._data["contexts"].items():
                for item in items:
                    msg_hash = item.get("hash", hash_feedback(item["message"]))
                    if msg_hash not in seen_hashes:
                        seen_hashes.add(msg_hash)
                        
                        # Include original question for similarity comparison
                        fb_dict = {
                            "task_id": item["task_id"],
                            "message": item["message"],
                            "source": item["source"],
                            "question": item.get("question", "")  # Original question
                        }
                        feedback_pool.append(fb_dict)
            
            if not feedback_pool:
                return []
            
            # Compute n-gram enhanced similarity between current question and stored questions
            scored_feedbacks = compute_tfidf_similarity(
                question, 
                feedback_pool, 
                limit,
                threshold
            )
            
            # Convert to Feedback objects
            return [
                Feedback(
                    task_id=fb["task_id"],
                    message=fb["message"],
                    source=fb["source"]
                )
                for fb in scored_feedbacks
            ]
    
    def add_contextual_feedback(self, question: str, fb: Feedback, similarity_threshold: float = 0.8) -> None:
        """
        Add feedback with context clustering and smart deduplication.
        
        Instead of storing by task_id, store by semantic context.
        This allows cross-task learning. Uses similarity-based deduplication.
        
        Args:
            question: The question that generated this feedback
            fb: Feedback to store
            similarity_threshold: Minimum similarity (0-1) to consider as duplicate (default 0.8)
        """
        with self._lock:
            from src.memory.utils import extract_context_keywords, hash_feedback, is_similar_feedback
            
            # Extract context from question
            context_key = extract_context_keywords(question)
            
            # Store in context bucket (in addition to task bucket)
            if "contexts" not in self._data:
                self._data["contexts"] = {}
            
            bucket = self._data["contexts"].setdefault(context_key, [])
            
            # Exact deduplication by hash
            fb_hash = hash_feedback(fb.message)
            existing_hashes = {item.get("hash", "") for item in bucket}
            
            if fb_hash in existing_hashes:
                return  # Exact duplicate
            
            # Smart deduplication: check similarity
            existing_messages = [item.get("message", "") for item in bucket]
            if is_similar_feedback(fb.message, existing_messages, threshold=similarity_threshold):
                return  # Too similar
            
            # Add new feedback
            bucket.append({
                "task_id": fb.task_id,
                "message": fb.message,
                "source": fb.source,
                "hash": fb_hash,
                "question": question  # Store original question for better context
            })
            
            # Enforce cap
            if len(bucket) > self.cap_per_rule:
                self._data["contexts"][context_key] = bucket[-self.cap_per_rule:]
            
            self._save()
