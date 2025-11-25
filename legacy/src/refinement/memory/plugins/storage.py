"""
Storage Plugin (structure-first compact memory)

Writes compact records (no full question/answer text) and indexes
structure-only tokens for retrieval.
"""

from typing import Dict, Any
import re
from datetime import datetime
import uuid
from ....core.logger import get_logger
# Prefer new classifier (structure-first); fallback to legacy local if missing
try:
    from src.memory.plugins.task_classifier import (
        extract_task_type,  # returns (task_type, structure_signature, constraints, confidence)
    )
except Exception:  # pragma: no cover - fallback
    from .task_classifier import extract_task_type as _legacy_extract_task_type  # type: ignore
    def extract_task_type(q: str):  # type: ignore
        t, c = _legacy_extract_task_type(q)
        return t, "general", {}, c

logger = get_logger("refinement.memory.storage")


class StoragePlugin:
    """
    Storage plugin - saves incorrect examples to memory.
    
    Handles:
    1. Save record to MemoryStore (JSONL)
    2. Add to VectorIndex (FAISS)
    """
    
    def __init__(self, memory_store, vector_index):
        """
        Initialize storage plugin.
        
        Args:
            memory_store: MemoryStore instance
            vector_index: VectorIndex instance
        """
        self.store = memory_store
        self.index = vector_index
        
        logger.info("StoragePlugin initialized")
    
    def save(
        self,
        question: str,
        answer: str,
        evaluation: Dict[str, Any]
    ):
        """
        Save record to memory.
        
        Args:
            question: Question text
            answer: Student's answer (incorrect)
            evaluation: Teacher evaluation result
        """
        # Generate record ID
        record_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        
        # Extract structure-first features
        try:
            task_type, structure_sig, constraints, confidence = extract_task_type(question)
        except Exception:
            task_type, structure_sig, constraints, confidence = (
                "general_instruction", "general", {}, "low"
            )

        # Evaluation fields
        stop_score = float(evaluation.get("stop_score", 0.0))
        stop_score = max(0.0, min(1.0, stop_score))  # clamp
        error_keys = list(evaluation.get("error_keys", []))
        hint = evaluation.get("hint", "")

        # Build compact record (no question/answer content)
        record = {
            "schema_version": "mem.v1",
            "id": record_id,
            "task_type": task_type,
            "structure_signature": structure_sig,
            "constraints": constraints,
            "confidence": confidence,
            "error_keys": error_keys,
            "stop_score": stop_score,
            "semantic_rule": _extract_semantic_rule(hint),
            "timestamp": datetime.now().isoformat(),
        }

        # Save compact
        self.store.save_record(record)
        logger.info(f"Saved compact record to store: {record_id}")

        # Index structure-only tokens
        tokens = _build_structure_tokens(task_type, structure_sig, constraints)
        self.index.add_record(record_id, tokens)
        logger.info(f"Indexed structure tokens: {record_id} | {tokens}")

        logger.debug(f"Record: [{task_type}] {structure_sig}")


def _build_structure_tokens(task_type: str, structure_sig: str, constraints: Dict[str, Any]) -> str:
    parts = [task_type, structure_sig]
    if constraints:
        items = []
        for k in sorted(constraints.keys()):
            items.append(f"{k}={constraints[k]}")
        parts.append(",".join(items))
    return " | ".join(parts)


def _extract_semantic_rule(hint: str) -> str:
    # First sentence
    text = (hint or "").strip()
    first = re.split(r"[.!?]", text)[0] if text else ""
    rule = first or ""
    # digits -> n
    rule = re.sub(r"\d+", "n", rule)
    # collapse ws and trim length
    rule = re.sub(r"\s+", " ", rule).strip()
    return (rule[:150] + ("..." if len(rule) > 150 else "")) if rule else ""
