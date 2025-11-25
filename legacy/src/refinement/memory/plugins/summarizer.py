"""
Memory Summarizer Module

This module provides functions to:
1. Summarize multiple teaching records into concise summaries
2. Forget/prune old records to prevent unbounded memory growth
3. Merge similar records to reduce redundancy

Used for memory management in the teaching loop.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta

from src.core.logger import get_logger

logger = get_logger("memory.summarizer")


def summarize_records(
    records: List[Dict],
    max_length: int = 500,
    method: str = "concat"
) -> str:
    """
    Summarize multiple teaching records into a concise text.
    
    This is useful for:
    - Creating context for the student from multiple past examples
    - Reducing token count when passing memory to LLM
    - Providing overview of learning history
    
    Args:
        records: List of memory records (from MemoryStore)
        max_length: Maximum length of summary in characters
        method: Summarization method
            - "concat": Simple concatenation of refined answers
            - "bullets": Bullet-point format
            - "llm": Use LLM to generate summary (TODO: not yet implemented)
    
    Returns:
        Summary string
    
    Example:
        >>> records = [
        ...     {"question": "Capital of France?", "refined_answer": "Paris"},
        ...     {"question": "Capital of UK?", "refined_answer": "London"}
        ... ]
        >>> summary = summarize_records(records, method="bullets")
        >>> print(summary)
          Capital of France? -> Paris
          Capital of UK? -> London
    
    Note:
        For production use, consider using an LLM to generate more
        coherent summaries instead of simple concatenation.
    """
    if not records:
        return ""
    
    try:
        if method == "concat":
            return _summarize_concat(records, max_length)
        elif method == "bullets":
            return _summarize_bullets(records, max_length)
        elif method == "llm":
            # TODO: Implement LLM-based summarization
            logger.warning("LLM summarization not yet implemented, using concat")
            return _summarize_concat(records, max_length)
        else:
            logger.warning(f"Unknown method '{method}', using concat")
            return _summarize_concat(records, max_length)
    
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        return ""


def _summarize_concat(records: List[Dict], max_length: int) -> str:
    """
    Simple concatenation of refined answers.
    
    Format: "Q1? A1. Q2? A2. ..."
    """
    parts = []
    total_length = 0
    
    for rec in records:
        question = rec.get("question", "").strip()
        answer = rec.get("refined_answer", rec.get("initial_answer", "")).strip()
        
        if not question or not answer:
            continue
        
        # Format: "Q? A."
        part = f"{question} {answer}"
        part_length = len(part)
        
        if total_length + part_length > max_length:
            # Truncate and stop
            remaining = max_length - total_length
            if remaining > 20:  # Only add if meaningful space left
                parts.append(part[:remaining] + "...")
            break
        
        parts.append(part)
        total_length += part_length + 1  # +1 for space
    
    return " ".join(parts)


def _summarize_bullets(records: List[Dict], max_length: int) -> str:
    """
    Bullet-point format summary.
    
    Format:
          Q1? -> A1
          Q2? -> A2
    """
    lines = []
    total_length = 0
    
    for rec in records:
        question = rec.get("question", "").strip()
        answer = rec.get("refined_answer", rec.get("initial_answer", "")).strip()
        
        if not question or not answer:
            continue
        
        # Format: "  Q? -> A"
        line = f"  {question} -> {answer}"
        line_length = len(line)
        
        if total_length + line_length > max_length:
            remaining = max_length - total_length
            if remaining > 20:
                lines.append(line[:remaining] + "...")
            break
        
        lines.append(line)
        total_length += line_length + 1  # +1 for newline
    
    return "\n".join(lines)


def forget_old_records(
    records: List[Dict],
    days: int = 7,
    keep_important: bool = True
) -> List[Dict]:
    """
    Remove or filter out old records to prevent unbounded memory growth.
    
    This implements a simple time-based forgetting mechanism inspired by
    human memory decay. Records older than the threshold are removed.
    
    Args:
        records: List of memory records
        days: Age threshold in days (records older than this are forgotten)
        keep_important: If True, keep records marked as important regardless of age
    
    Returns:
        List of records that should be kept
    
    Example:
        >>> from datetime import datetime, timedelta
        >>> old_date = (datetime.now() - timedelta(days=10)).isoformat()
        >>> new_date = datetime.now().isoformat()
        >>> records = [
        ...     {"id": "r1", "timestamp": old_date, "question": "Old Q"},
        ...     {"id": "r2", "timestamp": new_date, "question": "New Q"}
        ... ]
        >>> kept = forget_old_records(records, days=7)
        >>> len(kept)
        1
        >>> kept[0]["id"]
        'r2'
    
    Note:
        Consider more sophisticated forgetting strategies:
        - Importance-weighted (keep frequently accessed records)
        - Cluster-based (keep representative examples from each cluster)
        - Reinforcement-based (keep records that led to improvement)
    """
    if not records:
        return []
    
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    
    kept_records = []
    forgotten_count = 0
    
    for rec in records:
        # Check if record should be kept
        should_keep = False
        
        # 1. Check importance flag
        if keep_important and rec.get("meta", {}).get("important", False):
            should_keep = True
            logger.debug(f"Keeping important record: {rec.get('id')}")
        
        # 2. Check timestamp
        timestamp_str = rec.get("timestamp")
        if timestamp_str:
            try:
                record_time = datetime.fromisoformat(timestamp_str)
                if record_time >= cutoff:
                    should_keep = True
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid timestamp in record {rec.get('id')}: {e}")
                # Keep records with invalid timestamps (safer default)
                should_keep = True
        else:
            # No timestamp, keep it (safer default)
            should_keep = True
        
        if should_keep:
            kept_records.append(rec)
        else:
            forgotten_count += 1
    
    if forgotten_count > 0:
        logger.info(
            f"Forgot {forgotten_count} old records (older than {days} days), "
            f"kept {len(kept_records)} records"
        )
    
    return kept_records


def merge_similar_records(
    records: List[Dict],
    similarity_threshold: float = 0.95
) -> List[Dict]:
    """
    Merge nearly identical records to reduce redundancy.
    
    This is useful when the same question has been asked multiple times
    with only minor variations in answers. Keeps the most recent version.
    
    Args:
        records: List of memory records
        similarity_threshold: Threshold for considering records as duplicates
            (0.0 = completely different, 1.0 = identical)
    
    Returns:
        List of merged records (duplicates removed)
    
    Note:
        This is a placeholder. Full implementation would require:
        1. Computing embeddings for each record
        2. Finding pairs with similarity > threshold
        3. Merging records (keep most recent, combine feedbacks)
        
        For now, we use simple exact string matching on questions.
    
    Example:
        >>> records = [
        ...     {"id": "r1", "question": "Capital of France?", "timestamp": "2024-01-01T10:00:00"},
        ...     {"id": "r2", "question": "Capital of France?", "timestamp": "2024-01-02T10:00:00"}
        ... ]
        >>> merged = merge_similar_records(records)
        >>> len(merged)
        1
        >>> merged[0]["id"]
        'r2'
    """
    if not records:
        return []
    
    # Group by question (exact match)
    question_groups: Dict[str, List[Dict]] = {}
    
    for rec in records:
        question = rec.get("question", "").strip().lower()
        if not question:
            continue
        
        if question not in question_groups:
            question_groups[question] = []
        question_groups[question].append(rec)
    
    # For each group, keep the most recent record
    merged_records = []
    merge_count = 0
    
    for question, group in question_groups.items():
        if len(group) == 1:
            merged_records.append(group[0])
        else:
            # Sort by timestamp (most recent first)
            sorted_group = sorted(
                group,
                key=lambda r: r.get("timestamp", ""),
                reverse=True
            )
            
            # Keep the most recent
            most_recent = sorted_group[0]
            merged_records.append(most_recent)
            
            merge_count += len(group) - 1
            logger.debug(
                f"Merged {len(group)} records for question: {question[:50]}... "
                f"(kept: {most_recent.get('id')})"
            )
    
    if merge_count > 0:
        logger.info(
            f"Merged {merge_count} duplicate records, "
            f"result: {len(merged_records)} unique records"
        )
    
    return merged_records


def get_memory_stats(records: List[Dict]) -> Dict:
    """
    Get statistics about memory records.
    
    Useful for monitoring and debugging memory system.
    
    Args:
        records: List of memory records
    
    Returns:
        Dict with statistics:
        - total_records: Total number of records
        - date_range: (oldest, newest) timestamps
        - avg_feedbacks: Average number of feedbacks per record
        - error_types: Count of each error type
    
    Example:
        >>> records = [...]
        >>> stats = get_memory_stats(records)
        >>> print(stats)
        {
            'total_records': 100,
            'date_range': ('2024-01-01T10:00:00', '2024-01-10T10:00:00'),
            'avg_feedbacks': 2.5,
            'error_types': {'incorrect': 45, 'incomplete': 30, 'unclear': 25}
        }
    """
    if not records:
        return {
            "total_records": 0,
            "date_range": (None, None),
            "avg_feedbacks": 0.0,
            "error_types": {}
        }
    
    total_records = len(records)
    
    # Date range
    timestamps = [r.get("timestamp") for r in records if r.get("timestamp")]
    if timestamps:
        # Filter out None values before sorting
        valid_timestamps = [ts for ts in timestamps if ts is not None]
        if valid_timestamps:
            timestamps_sorted = sorted(valid_timestamps)
            date_range = (timestamps_sorted[0], timestamps_sorted[-1])
        else:
            date_range = (None, None)
    else:
        date_range = (None, None)
    
    # Average feedbacks
    feedback_counts = [
        len(r.get("feedbacks", [])) for r in records
    ]
    avg_feedbacks = sum(feedback_counts) / len(feedback_counts) if feedback_counts else 0.0
    
    # Error types
    error_types: Dict[str, int] = {}
    for rec in records:
        error_type = rec.get("error_type")
        if error_type:
            error_types[error_type] = error_types.get(error_type, 0) + 1
    
    return {
        "total_records": total_records,
        "date_range": date_range,
        "avg_feedbacks": round(avg_feedbacks, 2),
        "error_types": error_types
    }
