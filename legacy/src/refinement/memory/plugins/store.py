"""
Memory Store Module

This module provides persistent storage for teaching loop records.
Uses JSONL (JSON Lines) format for efficient append-only operations.
"""

import json
from pathlib import Path
from typing import Dict, Iterable, Optional, Callable, Any
from datetime import datetime

from src.core.logger import get_logger

logger = get_logger("memory.store")


class MemoryStore:
    """
    Persistent storage for teaching loop records using JSONL format.
    
    JSONL (JSON Lines) format benefits:
    - Append-only: Can add records without loading entire file
    - Streaming: Can process records one at a time (memory-efficient)
    - Simple: Each line is a valid JSON object
    - Robust: Corrupted lines don't affect other records
    
    Record Structure:
        {
            "id": str,                    # Unique record identifier
            "question": str,              # Original question
            "initial_answer": str,        # Student's first attempt
            "feedbacks": List[str],       # List of teacher hints/feedbacks
            "refined_answer": str,        # Student's final answer after hints
            "error_type": str,            # Type of error (if any)
            "timestamp": str,             # ISO format timestamp
            "meta": {                     # Additional metadata
                "round": int,             # Which teaching round
                "tokens_used": int,       # Total tokens consumed
                "latency_ms": float,      # Processing time
                "evaluation": str,        # correct/incorrect
                ...                       # Any other metadata
            }
        }
    
    Example:
        >>> store = MemoryStore("logs/memory/store.jsonl")
        >>> record = {
        ...     "id": "q001",
        ...     "question": "What is 2+2?",
        ...     "initial_answer": "5",
        ...     "feedbacks": ["Think about basic addition"],
        ...     "refined_answer": "4",
        ...     "error_type": "calculation",
        ...     "timestamp": "2025-01-01T00:00:00",
        ...     "meta": {"round": 1, "tokens_used": 100}
        ... }
        >>> store.save_record(record)
        >>> for rec in store.load_records():
        ...     print(rec["id"])
    """
    
    def __init__(self, file_path: str = "logs/memory/store.jsonl"):
        """
        Initialize the memory store.
        
        Args:
            file_path: Path to the JSONL file (will be created if doesn't exist)
        """
        self.file_path = Path(file_path)
        
        # Create directory if it doesn't exist
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create file if it doesn't exist
        if not self.file_path.exists():
            self.file_path.touch()
            logger.info(f"Created memory store at: {self.file_path}")
        else:
            logger.info(f"Using existing memory store at: {self.file_path}")
    
    def save_record(self, record: Dict[str, Any]) -> None:
        """
        Save a record to the store (append-only).
        
        This method appends a new JSON record to the file without loading
        the entire file into memory. Each record is written as a single line.
        
        Args:
            record: Dictionary containing the record data
        
        Raises:
            ValueError: If required fields are missing
            IOError: If file cannot be written
        
        Required Fields:
            - id: Unique identifier
            - For legacy schema: question (required)
            - For mem.v1 schema: task_type, structure_signature (required)
            - timestamp: ISO format timestamp (auto-added if missing)
        
        Note:
            - Records are NOT validated for duplicates (append-only)
            - Timestamp is auto-added if not present
            - ID is auto-generated if not present (using timestamp + random suffix)
            - Use UTF-8 encoding for international characters
            - Supports both legacy and compact (mem.v1) schemas
        """
        # Validate required fields (support both legacy and mem.v1)
        schema_version = record.get("schema_version", "legacy")
        
        if schema_version == "mem.v1":
            # Compact schema validation
            if "task_type" not in record or "structure_signature" not in record:
                raise ValueError("Missing required fields for mem.v1: task_type, structure_signature")
        else:
            # Legacy schema validation
            if "question" not in record:
                raise ValueError("Missing required field: question")
        
        # Auto-generate ID if not present
        if "id" not in record:
            import random
            import string
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            record["id"] = f"{timestamp}_{suffix}"
        
        # Add timestamp if not present
        if "timestamp" not in record:
            record["timestamp"] = datetime.now().isoformat()
        
        try:
            # Append record as a single JSON line
            with open(self.file_path, "a", encoding="utf-8") as f:
                json_line = json.dumps(record, ensure_ascii=False)
                f.write(json_line + "\n")
            
            logger.debug(f"Saved record: {record['id']}")
            
        except Exception as e:
            logger.error(f"Failed to save record {record.get('id', 'unknown')}: {e}")
            raise IOError(f"Could not write to {self.file_path}") from e
    
    def load_records(
        self,
        filter_fn: Optional[Callable[[Dict], bool]] = None
    ) -> Iterable[Dict[str, Any]]:
        """
        Load records from the store with optional filtering.
        
        This method yields records one at a time (streaming), so it doesn't
        load the entire file into memory. This is crucial for large datasets.
        
        Args:
            filter_fn: Optional function to filter records.
                       Should return True to include the record.
        
        Yields:
            Dict: Record dictionaries that pass the filter
        
        Example:
            >>> # Load all records
            >>> for record in store.load_records():
            ...     print(record["id"])
            
            >>> # Load only correct answers
            >>> def only_correct(rec):
            ...     return rec.get("meta", {}).get("evaluation") == "correct"
            >>> for record in store.load_records(filter_fn=only_correct):
            ...     print(record["question"])
            
            >>> # Load recent records (last 7 days)
            >>> from datetime import datetime, timedelta
            >>> week_ago = datetime.now() - timedelta(days=7)
            >>> def recent(rec):
            ...     ts = datetime.fromisoformat(rec["timestamp"])
            ...     return ts > week_ago
            >>> recent_records = list(store.load_records(filter_fn=recent))
        
        Note:
            - Handles corrupted lines gracefully (logs warning, skips line)
            - Empty lines are silently skipped
            - Memory-efficient: processes one record at a time
        """
        if not self.file_path.exists():
            logger.warning(f"Store file does not exist: {self.file_path}")
            return
        
        line_num = 0
        records_yielded = 0
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line_num += 1
                    
                    # Skip empty lines
                    if not line.strip():
                        continue
                    
                    try:
                        # Parse JSON line
                        record = json.loads(line)
                        
                        # Apply filter if provided
                        if filter_fn is None or filter_fn(record):
                            records_yielded += 1
                            yield record
                    
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Corrupted line {line_num} in {self.file_path}: {e}"
                        )
                        continue
        
        except Exception as e:
            logger.error(f"Error reading store file: {e}")
            raise
        
        logger.debug(
            f"Loaded {records_yielded} records from {line_num} lines"
        )
    
    def count_records(self, filter_fn: Optional[Callable[[Dict], bool]] = None) -> int:
        """
        Count records in the store (optionally with filter).
        
        Args:
            filter_fn: Optional filter function
        
        Returns:
            int: Number of records matching the filter
        """
        return sum(1 for _ in self.load_records(filter_fn=filter_fn))
    
    def get_record_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific record by ID.
        
        Args:
            record_id: The record ID to search for
        
        Returns:
            Dict or None: The record if found, None otherwise
        
        Note:
            This method scans the entire file, so it's O(n).
            For frequent lookups, consider building an in-memory index.
        """
        for record in self.load_records():
            if record.get("id") == record_id:
                return record
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the store.
        
        Returns:
            Dict with statistics:
            - total_records: Total number of records
            - file_size_mb: Size of the file in MB
            - oldest_timestamp: Timestamp of oldest record
            - newest_timestamp: Timestamp of newest record
        """
        stats = {
            "total_records": 0,
            "file_size_mb": 0.0,
            "oldest_timestamp": None,
            "newest_timestamp": None,
        }
        
        if not self.file_path.exists():
            return stats
        
        # File size
        stats["file_size_mb"] = self.file_path.stat().st_size / (1024 * 1024)
        
        # Scan records for timestamps
        for record in self.load_records():
            stats["total_records"] += 1
            
            ts = record.get("timestamp")
            if ts:
                if stats["oldest_timestamp"] is None:
                    stats["oldest_timestamp"] = ts
                stats["newest_timestamp"] = ts
        
        return stats
    
    def clear(self) -> None:
        """
        Clear all records from the store.
        
        Warning: This operation is irreversible!
        """
        if self.file_path.exists():
            self.file_path.unlink()
            self.file_path.touch()
            logger.warning(f"Cleared all records from {self.file_path}")
