"""
Memory Store Abstractions

Provides a simple interface for storing and retrieving feedback that the
"student" model should remember across iterations. Default implementation
persists to a JSON file on disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
import json
import os
from datetime import datetime
from threading import RLock
from src.memory.utils import compute_rule_key, hash_feedback


@dataclass
class Feedback:
    task_id: str
    message: str
    source: str = "critic"  # who wrote this
    

@dataclass
class FeedbackLite:
    """Lightweight feedback structure for multi-key memory (Phase 3).
    
    Replaces verbose 'message' field with structured, actionable components:
    - lesson: Concise actionable guidance (2-3 sentences)
    - error_keys: List of canonical error types/missing concepts
    - student_answer_short: Truncated student response for context
    - ts: ISO timestamp for recency-based retrieval
    - task_id: Task identifier for per-task recent retrieval
    
    This prevents memory bloat from storing full reflections/letters.
    """
    lesson: str
    error_keys: List[str]
    student_answer_short: str
    ts: str = field(default_factory=lambda: datetime.now().isoformat())
    task_id: Optional[str] = None
    
    
@dataclass
class FeedbackMetadata:
    """Metadata for multi-key indexed feedback."""
    score: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    concept_ids: List[str] = field(default_factory=list)
    source: str = "self_reflection"
    error_types: List[str] = field(default_factory=list)


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
    """JSON file-backed memory store with multi-key indexing.

    Data shape:
      "index": {
        "task:alpaca-001": ["entry_id_1", "entry_id_2"],
        "keyword:gradient_descent": ["entry_id_1"],
        "error:missing_concepts": ["entry_id_3"],
        "format:keywords": ["entry_id_1", "entry_id_3"]
      },
      "entries": {
        "entry_id_1": {
          "task_id": "alpaca-001",
          "message": "...",
          "source": "self_reflection",
          "hash": "...",
          "metadata": {
            "score": 0.3,
            "timestamp": "2025-10-28T14:00:00",
            "concept_ids": ["gradient_descent"],
            "source": "self_reflection",
            "error_types": ["missing_concepts"]
          }
        }
      }
    }
    
    The "index" bucket enables multi-key lookup (task:*, keyword:*, error:*, format:*).
    Deduplication via hash prevents storing identical feedback multiple times.
    Per-key cap ensures memory doesn't grow unbounded.
    """

    def __init__(
        self,
        path: str = "data/memory.json",
        cap_per_task: int = 3,  # Phase 3: Reduced from 5 to 3 - store only the 3 most recent attempts per task
                                # This prevents memory bloat while retaining immediate context for reflection
        cap_per_rule: int = 5,
        cap_per_key: int = 10
    ) -> None:
        self.path = path
        self.cap_per_task = cap_per_task
        self.cap_per_rule = cap_per_rule
        self.cap_per_key = cap_per_key
        self._lock = RLock()
        self._data: Dict[str, Any] = {
            "tasks": {},  # by_task index: Maps task_id -> [entry_ids] for quick per-task retrieval
                         # Used by get_task_recent() to fetch recent attempts for reflection
            "rules": {},  # Legacy support
            "index": {},  # Multi-key index: {key: [entry_ids]}
            "entries": {}  # Actual feedback entries
        }
        self._entry_counter = 0
        self._ensure_file()
        self._load()

    def _ensure_file(self) -> None:
        folder = os.path.dirname(self.path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({
                    "tasks": {}, 
                    "rules": {},
                    "index": {},
                    "entries": {}
                }, f)

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
                # Handle old format (flat dict) or new format (tasks/rules/index/entries)
                if isinstance(raw, dict):
                    if "tasks" in raw or "rules" in raw:
                        self._data = raw
                        # Ensure all keys exist
                        self._data.setdefault("tasks", {})
                        self._data.setdefault("rules", {})
                        self._data.setdefault("index", {})
                        self._data.setdefault("entries", {})
                    else:
                        # Old format: migrate to new
                        self._data = {
                            "tasks": raw, 
                            "rules": {},
                            "index": {},
                            "entries": {}
                        }
                
                # Initialize entry counter from existing entries
                if self._data.get("entries"):
                    entry_ids = [int(eid.split("_")[1]) for eid in self._data["entries"].keys() if eid.startswith("entry_")]
                    self._entry_counter = max(entry_ids) if entry_ids else 0
                    
        except Exception:
            # Corrupt file; reset to empty
            self._data = {
                "tasks": {}, 
                "rules": {},
                "index": {},
                "entries": {}
            }
            self._entry_counter = 0

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
    
    def add_feedback_multi_key(
        self, 
        keys: Set[str], 
        fb: Feedback, 
        metadata: Optional[FeedbackMetadata] = None
    ) -> None:
        """
        Add feedback with multi-key indexing.
        
        Args:
            keys: Set of keys (e.g., {"task:alpaca-001", "keyword:gradient_descent", "error:missing_concepts"})
            fb: Feedback to store
            metadata: Optional metadata (score, timestamp, concept_ids, etc.)
        """
        with self._lock:
            # Generate unique entry ID
            self._entry_counter += 1
            entry_id = f"entry_{self._entry_counter}"
            
            # Compute hash for deduplication
            fb_hash = hash_feedback(fb.message)
            
            # Check if this hash already exists
            for existing_entry in self._data["entries"].values():
                if existing_entry.get("hash") == fb_hash:
                    # Exact duplicate; skip
                    return
            
            # Create entry
            entry = {
                "task_id": fb.task_id,
                "message": fb.message,
                "source": fb.source,
                "hash": fb_hash,
                "metadata": {
                    "score": metadata.score if metadata else 0.0,
                    "timestamp": metadata.timestamp if metadata else datetime.now().isoformat(),
                    "concept_ids": metadata.concept_ids if metadata else [],
                    "source": metadata.source if metadata else fb.source,
                    "error_types": metadata.error_types if metadata else []
                }
            }
            
            # Store entry
            self._data["entries"][entry_id] = entry
            
            # Add to multi-key index
            for key in keys:
                if key not in self._data["index"]:
                    self._data["index"][key] = []
                
                self._data["index"][key].append(entry_id)
                
                # Enforce cap per key
                if len(self._data["index"][key]) > self.cap_per_key:
                    # Remove oldest entry (first in list)
                    old_entry_id = self._data["index"][key][0]
                    self._data["index"][key] = self._data["index"][key][-self.cap_per_key:]
                    
                    # Check if old_entry_id is still referenced by other keys
                    still_referenced = any(
                        old_entry_id in entry_ids 
                        for k, entry_ids in self._data["index"].items() 
                        if k != key
                    )
                    
                    # Delete entry if no longer referenced
                    if not still_referenced and old_entry_id in self._data["entries"]:
                        del self._data["entries"][old_entry_id]
            
            self._save()
    
    def get_by_multi_key(self, key: str, limit: Optional[int] = None) -> List[Feedback]:
        """
        Retrieve feedback by a single key from multi-key index.
        
        Args:
            key: A key like "task:alpaca-001", "keyword:gradient_descent", etc.
            limit: Max number of feedback items to return (None = all)
            
        Returns:
            List of Feedback matching the key
        """
        with self._lock:
            entry_ids = self._data["index"].get(key, [])
            
            if limit is not None:
                entry_ids = entry_ids[-limit:]
            
            # Convert to Feedback objects
            results = []
            for entry_id in entry_ids:
                if entry_id in self._data["entries"]:
                    entry = self._data["entries"][entry_id]
                    results.append(Feedback(
                        task_id=entry["task_id"],
                        message=entry["message"],
                        source=entry["source"]
                    ))
            
            return results
    
    def cleanup(
        self, 
        max_per_key: int = 10, 
        quality_threshold: float = 0.7,
        max_age_days: int = 30
    ) -> None:
        """
        Cleanup memory:
        1. Cap each key to max_per_key entries
        2. Keep only high-quality entries (score >= threshold)
        3. Remove entries older than max_age_days
        
        Args:
            max_per_key: Maximum entries per key
            quality_threshold: Minimum score to keep (0-1)
            max_age_days: Maximum age in days
        """
        with self._lock:
            from datetime import timedelta
            
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            
            # Collect all entry_ids to keep
            entries_to_keep = set()
            
            for key, entry_ids in list(self._data["index"].items()):
                # Filter by quality and age
                valid_entries = []
                
                for entry_id in entry_ids:
                    if entry_id not in self._data["entries"]:
                        continue
                    
                    entry = self._data["entries"][entry_id]
                    metadata = entry.get("metadata", {})
                    
                    # Check quality
                    score = metadata.get("score", 0.0)
                    if score < quality_threshold:
                        continue
                    
                    # Check age
                    timestamp_str = metadata.get("timestamp", "")
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        if timestamp < cutoff_date:
                            continue
                    except Exception:
                        pass  # Keep if timestamp invalid
                    
                    valid_entries.append(entry_id)
                
                # Cap to max_per_key (keep most recent)
                valid_entries = valid_entries[-max_per_key:]
                
                # Update index
                if valid_entries:
                    self._data["index"][key] = valid_entries
                    entries_to_keep.update(valid_entries)
                else:
                    # Remove empty key
                    del self._data["index"][key]
            
            # Remove entries not referenced by any key
            for entry_id in list(self._data["entries"].keys()):
                if entry_id not in entries_to_keep:
                    del self._data["entries"][entry_id]
            
            self._save()
    
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
    
    def get_by_tfidf(self, question: str, limit: int = 3, threshold: Optional[float] = None) -> List[Feedback]:
        """
        Retrieve feedback using TF-IDF similarity by comparing with original questions.
        
        Phase 4: Uses config parameters for threshold (defaults to config.yaml value).
        
        Flow:
        1. Collect all feedbacks from contexts bucket (which stores original questions)
        2. Compute n-gram enhanced TF-IDF similarity between current question and stored questions
        3. Return top-K most similar feedbacks above threshold (deduplicated)
        
        Args:
            question: The question text
            limit: Max number of feedback items to return
            threshold: Minimum similarity score (0-1). If None, uses config.yaml value (default 0.30)
            
        Returns:
            List of most similar Feedback items based on question similarity
        """
        with self._lock:
            from src.memory.utils import compute_tfidf_similarity, hash_feedback
            from config.ai_config import load_config
            
            # Get threshold from config if not provided
            if threshold is None:
                try:
                    from config.ai_config import load_config
                    cfg, _ = load_config()
                    threshold = cfg.memory.retrieval.get("tfidf", {}).get("min_cosine", 0.30)
                except:
                    threshold = 0.30  # Fallback default
            
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
            
            # Ensure threshold is float
            final_threshold: float = threshold if threshold is not None else 0.30
            
            # Compute n-gram enhanced similarity between current question and stored questions
            scored_feedbacks = compute_tfidf_similarity(
                question, 
                feedback_pool, 
                limit,
                final_threshold
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
