"""
Multi-Key Generator for Memory Indexing

Generates multiple index keys for memory storage to enable efficient retrieval:
- task:* - Task-specific keys
- keyword:* - Keyword-based keys (canonicalized)
- error:* - Error-type keys  
- format:* - Format-specific keys

Uses canonical mapping for semantic normalization.
"""

from typing import List, Set, Dict, Tuple, Optional
from dataclasses import dataclass

from src.memory.canonical_loader import get_canonical_mapper
from src.evaluation.critic import CriticResult


@dataclass
class MultiKeySet:
    """Set of multiple index keys for memory storage."""
    task_keys: List[str]  # task:taskid, task:domain
    keyword_keys: List[str]  # keyword:concept1_concept2
    error_keys: List[str]  # error:missing_concepts, error:format_mismatch
    format_keys: List[str]  # format:exact, format:keywords
    all_keys: Set[str]  # Combined set of all keys
    
    @property
    def primary_key(self) -> str:
        """Get primary key (first task key or first keyword key)."""
        if self.task_keys:
            return self.task_keys[0]
        elif self.keyword_keys:
            return self.keyword_keys[0]
        elif self.error_keys:
            return self.error_keys[0]
        else:
            return "general"


class MultiKeyGenerator:
    """
    Generates multiple index keys for memory storage.
    
    Features:
    - Canonical concept mapping
    - Multi-level key generation (task, keyword, error, format)
    - Smart key combination strategies
    """
    
    def __init__(self):
        """Initialize key generator with canonical mapper."""
        self.mapper = get_canonical_mapper()
    
    def generate_keys(
        self,
        question: str,
        task_id: Optional[str] = None,
        critic_result: Optional[CriticResult] = None,
        **kwargs
    ) -> MultiKeySet:
        """
        Generate multi-level index keys.
        
        Args:
            question: Question text
            task_id: Optional task identifier
            critic_result: Optional critic result with error details
            **kwargs: Additional metadata
            
        Returns:
            MultiKeySet with all generated keys
        """
        task_keys = self._generate_task_keys(task_id, kwargs.get("domain"))
        keyword_keys = self._generate_keyword_keys(question)
        error_keys = self._generate_error_keys(critic_result)
        format_keys = self._generate_format_keys(critic_result, kwargs)
        
        # Combine all keys
        all_keys = set(task_keys + keyword_keys + error_keys + format_keys)
        
        return MultiKeySet(
            task_keys=task_keys,
            keyword_keys=keyword_keys,
            error_keys=error_keys,
            format_keys=format_keys,
            all_keys=all_keys
        )
    
    def _generate_task_keys(self, task_id: Optional[str] = None, domain: Optional[str] = None) -> List[str]:
        """
        Generate task-specific keys.
        
        Examples:
            - task:alpaca-001
            - task:domain:math
        """
        keys = []
        
        if task_id:
            keys.append(f"task:{task_id}")
        
        if domain:
            keys.append(f"task:domain:{domain}")
        
        return keys
    
    def _generate_keyword_keys(self, question: str, max_combinations: int = 3) -> List[str]:
        """
        Generate keyword-based keys using canonical mapping.
        
        Strategy:
        1. Canonicalize question to concept IDs
        2. Generate single, pair, and triple combinations
        3. Sort for consistency
        
        Examples:
            - keyword:machine_learning
            - keyword:gradient_descent_learning_rate
            - keyword:explain_describe_algorithm
        """
        keys = []
        
        # Get canonical concepts
        concept_ids = self.mapper.canonicalize(question)
        
        if not concept_ids:
            # Fallback: extract raw keywords
            import re
            words = re.findall(r'\b\w{4,}\b', question.lower())  # Words >= 4 chars
            stopwords = {'what', 'this', 'that', 'have', 'with', 'from', 'they'}
            concept_ids = {w for w in words if w not in stopwords}
        
        concept_list = sorted(list(concept_ids))
        
        # Single concepts
        for concept in concept_list[:5]:  # Top 5
            keys.append(f"keyword:{concept}")
        
        # Pairs (for multi-concept questions)
        if len(concept_list) >= 2:
            for i in range(min(max_combinations, len(concept_list) - 1)):
                for j in range(i + 1, min(i + 3, len(concept_list))):  # Next 2 concepts
                    pair = "_".join(sorted([concept_list[i], concept_list[j]]))
                    keys.append(f"keyword:{pair}")
        
        # Triples (for complex questions)
        if len(concept_list) >= 3:
            triple = "_".join(sorted(concept_list[:3]))
            keys.append(f"keyword:{triple}")
        
        return keys
    
    def _generate_error_keys(self, critic_result: Optional[CriticResult] = None) -> List[str]:
        """
        Generate error-specific keys.
        
        Examples:
            - error:missing_concepts
            - error:missing:gradient_descent
            - error:format_mismatch
            - error:empty_response
        """
        keys = []
        
        if not critic_result or critic_result.satisfied:
            return keys
        
        # Add error type
        if critic_result.error_type:
            keys.append(f"error:{critic_result.error_type}")
        
        # Add from CriticResult.error_keys
        if critic_result.error_keys:
            for error_key in critic_result.error_keys:
                if not error_key.startswith("error:"):
                    keys.append(f"error:{error_key}")
                else:
                    keys.append(error_key)
        
        # Add missing concept keys
        if critic_result.missing_concepts:
            for concept in critic_result.missing_concepts[:5]:
                normalized = concept.lower().replace(" ", "_")
                keys.append(f"error:missing:{normalized}")
        
        return keys
    
    def _generate_format_keys(
        self,
        critic_result: Optional[CriticResult] = None,
        metadata: Optional[Dict] = None
    ) -> List[str]:
        """
        Generate format-specific keys.
        
        Examples:
            - format:exact_match
            - format:keywords
            - format:short_answer
            - format:explanation
        """
        keys = []
        
        # Detect format from critic result
        if critic_result:
            if critic_result.error_type == "exact_match_failed":
                keys.append("format:exact_match")
            elif critic_result.error_type == "missing_keywords":
                keys.append("format:keywords")
            elif critic_result.error_type == "empty_answer":
                keys.append("format:no_output")
        
        # Detect from metadata
        if metadata:
            if metadata.get("format_type"):
                keys.append(f"format:{metadata['format_type']}")
            
            # Length-based classification
            if "answer_length" in metadata:
                length = metadata["answer_length"]
                if length < 20:
                    keys.append("format:short_answer")
                elif length < 100:
                    keys.append("format:medium_answer")
                else:
                    keys.append("format:long_answer")
        
        return keys
    
    def generate_retrieval_query_keys(
        self,
        question: str,
        previous_error_types: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Generate keys for retrieval query with priority levels.
        
        Returns dict with priority levels:
        - priority_1: Task-specific exact matches
        - priority_2: Keyword + Error intersection
        - priority_3: Format-based matches
        - priority_4: Fallback to keyword-only
        
        Args:
            question: Query question
            previous_error_types: Error types from previous attempts
            
        Returns:
            Dict with priority-level key lists
        """
        # Get canonical concepts
        concept_ids = self.mapper.canonicalize(question)
        concept_list = sorted(list(concept_ids))
        
        query_keys = {
            "priority_1": [],  # Exact task matches (if task_id known)
            "priority_2": [],  # Keyword ∩ Error
            "priority_3": [],  # Format matches
            "priority_4": []   # Keyword fallback
        }
        
        # Priority 2: Keyword + Error intersection
        if concept_list and previous_error_types:
            for concept in concept_list[:3]:
                for error_type in previous_error_types:
                    query_keys["priority_2"].append(f"keyword:{concept}+error:{error_type}")
        
        # Priority 3: Format detection
        if len(question) < 50:
            query_keys["priority_3"].append("format:short_answer")
        
        # Priority 4: Keywords only (fallback)
        for concept in concept_list[:5]:
            query_keys["priority_4"].append(f"keyword:{concept}")
        
        # Pairs
        if len(concept_list) >= 2:
            pair = "_".join(sorted(concept_list[:2]))
            query_keys["priority_4"].append(f"keyword:{pair}")
        
        return query_keys


def generate_keys_for_question(question: str, **kwargs) -> MultiKeySet:
    """
    Convenience function to generate keys for a question.
    
    Args:
        question: Question text
        **kwargs: Additional parameters (task_id, domain, critic_result, etc.)
        
    Returns:
        MultiKeySet with generated keys
    """
    generator = MultiKeyGenerator()
    return generator.generate_keys(question, **kwargs)
