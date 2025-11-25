"""
Memory Retrieval Plugin (structure-first)

Routes by task/structure and returns compact, structured context.
"""

from typing import Tuple, List, Dict, Any
from ...settings import SETTINGS
from ....core.logger import get_logger
try:
    from src.memory.plugins.task_classifier import extract_task_type
except Exception:  # pragma: no cover
    extract_task_type = None  # type: ignore
from ...memory.plugins.storage import _build_structure_tokens  # sibling package under refinement
from .hard_negative_filter import HardNegativeFilter

logger = get_logger("refinement.student.memory_retrieval")


class MemoryRetrievalPlugin:
    """
    Memory retrieval plugin.
    
    Retrieves similar examples from vector index and builds context.
    
    Settings used:
    - SETTINGS.memory_retrieval.k
    - SETTINGS.memory_retrieval.distance_threshold
    """
    
    def __init__(self, memory_store, vector_index):
        """
        Initialize retrieval plugin.
        
        Args:
            memory_store: MemoryStore instance
            vector_index: VectorIndex instance
        """
        self.store = memory_store
        self.index = vector_index
        self.k = SETTINGS.memory_retrieval.k
        self.distance_threshold = SETTINGS.memory_retrieval.distance_threshold
        
        logger.info(
            f"MemoryRetrievalPlugin initialized: "
            f"k={self.k}, distance_threshold={self.distance_threshold}"
        )
    
    def retrieve(self, question: str) -> Tuple[str, List[str]]:
        """Compatibility: returns (context, ids)."""
        context, ids, _ = self.retrieve_with_stats(question)
        return context, ids

    def retrieve_with_stats(self, question: str) -> Tuple[str, List[str], Dict[str, Any]]:
        """Full structure-first retrieval with stats."""
        logger.debug(f"Retrieving context for question: {question[:80]}...")
        stats: Dict[str, Any] = {}

        # Analyze
        try:
            if extract_task_type:
                task_type, structure_sig, constraints, _conf = extract_task_type(question)
            else:
                task_type, structure_sig, constraints = "general_instruction", "general", {}
        except Exception:
            task_type, structure_sig, constraints = "general_instruction", "general", {}
        stats["task_type"] = task_type
        stats["structure_signature"] = structure_sig
        logger.info(f"Retrieval routing -> task={task_type}, structure={structure_sig}")

        # Load records
        records = list(self.store.load_records())
        stats["total"] = len(records)
        if not records:
            return "", [], stats

        # Filter by task
        by_task = [r for r in records if r.get("task_type") == task_type]
        stats["after_task"] = len(by_task)
        if not by_task:
            return "", [], stats

        # Filter by structure (relax if empty)
        by_struct = [r for r in by_task if r.get("structure_signature") == structure_sig]
        if not by_struct:
            logger.warning("Structure filter empty; relaxing to task_type only")
            by_struct = by_task
        stats["after_structure"] = len(by_struct)

        # Rank by similarity using structure-only tokens
        query_tokens = _build_structure_tokens(task_type, structure_sig, constraints)
        try:
            retrieved = self.index.retrieve(query_tokens, k=min(self.k, len(by_struct)))
        except Exception:
            retrieved = []

        # Intersect with candidates
        cand_ids = {r.get("id") for r in by_struct if r.get("id")}
        ranked = [rid for rid in retrieved if rid in cand_ids]
        if not ranked:
            # simple lexical fallback
            qtoks = set(query_tokens.split())
            scored = []
            for r in by_struct:
                rid = r.get("id")
                if not rid:
                    continue
                rtoks = set(_build_structure_tokens(r.get("task_type", ""), r.get("structure_signature", ""), r.get("constraints", {})).split())
                score = len(qtoks & rtoks)
                scored.append((score, rid))
            scored.sort(reverse=True)
            ranked = [rid for _s, rid in scored[: self.k]]

        # Hard-negative filtering by id string (simple heuristic)
        hnf = HardNegativeFilter()
        before_neg = len(ranked)
        ranked = [rid for rid in ranked if not hnf.should_filter(rid, threshold=SETTINGS.hard_negative_filter.threshold)]
        stats["filtered_by_negative"] = before_neg - len(ranked)

        selected_ids = ranked[: self.k]
        stats["used"] = len(selected_ids)
        logger.info(
            "Retrieval stats | total=%s, after_task=%s, after_structure=%s, filtered_by_negative=%s, used=%s",
            stats.get("total"), stats.get("after_task"), stats.get("after_structure"),
            stats.get("filtered_by_negative"), stats.get("used")
        )

        # Build compact context from error_keys (convert to actionable warnings)
        id_to_record = {r.get("id"): r for r in by_struct}
        warnings: List[str] = []
        seen_keys = set()  # Avoid duplicates
        
        for rid in selected_ids:
            rec = id_to_record.get(rid, {})
            error_keys = (rec or {}).get("error_keys", [])
            
            # Convert each error_key to warning
            for key in error_keys:
                if key not in seen_keys:
                    warning = _translate_error_key_to_warning(key)
                    warnings.append(warning)
                    seen_keys.add(key)
        
        # Limit number of warnings (use semantic_rule.max_rules setting)
        max_warnings = getattr(SETTINGS.semantic_rule, "max_rules", 6)
        warnings = warnings[: max_warnings]

        context = build_context(task_type, structure_sig, constraints, warnings)
        return context, selected_ids, stats


def _translate_error_key_to_warning(error_key: str) -> str:
    """
    Translate error_key to actionable warning in English.
    This provides experience-based guidance without revealing the answer.
    """
    warnings = {
        "too_short": "Questions like this often need more detail - aim for 2-3 complete sentences explaining your answer thoroughly",
        "too_brief": "Answers that are too brief tend to miss important details - expand your explanation to be more comprehensive",
        "incomplete": "Make sure to address every part of the question - partial answers are often marked wrong",
        "no_punctuation": "Always end your answer with proper punctuation (period, question mark, etc.)",
        "no_capitalization": "Start your answer with a capital letter",
        "wrong_answer": "Review the question requirements very carefully - what exactly is being asked for?",
        "low_overlap": "Include specific keywords and concepts directly related to the question",
        "partial_match": "Your answer might be on the right track but needs more specific details or examples",
        "missing_keywords": "Important terms from the question should appear in your answer",
        "empty_answer": "A valid response is required - don't leave it blank"
    }
    return warnings.get(error_key, f"Be careful with: {error_key.replace('_', ' ')}")


def build_context(task_type: str, structure_sig: str, constraints: Dict[str, Any], rules: List[str]) -> str:
    """
    Build context from memory patterns - provides guidance based on past mistakes.
    Now integrated into unified prompt structure with error_keys as warnings.
    """
    cons_str = constraints if constraints else {}
    out: List[str] = [
        f"- Question type: '{task_type}' | Expected format: '{structure_sig}'",
    ]
    
    # Add constraint-based guidance
    if cons_str:
        out.append(f"- Specific requirements: {cons_str}")
    
    # Add common mistakes as actionable warnings
    if rules:
        out.append("- Past students struggled with:")
        for rule in rules:
            out.append(f"    • {rule}")
    
    return "\n".join(out)
