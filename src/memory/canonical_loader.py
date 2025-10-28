"""
Canonical Concept Mapping Loader

Loads and manages canonical concept mappings from JSON configuration.
Supports:
- Schema validation
- Layered overrides (base + organization-specific)
- Hot-reload capability
- Provenance tracking
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from threading import RLock

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Concept:
    """Canonical concept definition."""
    id: str
    variants: List[str]
    patterns: List[str]
    domain: str
    confidence: float
    sources: List[str]
    last_seen: str
    
    def __post_init__(self):
        """Compile regex patterns for efficient matching."""
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.patterns
        ]
    
    def matches(self, text: str) -> bool:
        """Check if text matches any pattern for this concept."""
        text_lower = text.lower()
        
        # Check variants (exact match)
        for variant in self.variants:
            if variant.lower() in text_lower:
                return True
        
        # Check regex patterns
        for pattern in self._compiled_patterns:
            if pattern.search(text):
                return True
        
        return False


class CanonicalMapper:
    """
    Manages canonical concept mappings with hot-reload support.
    
    Features:
    - Load from JSON with schema validation
    - Layered overrides (base + organization configs)
    - Hot-reload with file monitoring
    - Thread-safe operations
    - Metrics tracking (coverage, hits, misses)
    """
    
    def __init__(
        self,
        base_path: str = "config/canonical_concepts.json",
        override_path: Optional[str] = None,
        auto_reload_interval: int = 300  # 5 minutes
    ):
        """
        Initialize canonical mapper.
        
        Args:
            base_path: Path to base concepts JSON
            override_path: Optional path to organization-specific overrides
            auto_reload_interval: Seconds between auto-reload checks (0 = disabled)
        """
        self.base_path = Path(base_path)
        self.override_path = Path(override_path) if override_path else None
        self.auto_reload_interval = auto_reload_interval
        
        self._lock = RLock()
        self._concepts: Dict[str, Concept] = {}
        self._variant_to_id: Dict[str, str] = {}  # Fast lookup: variant -> concept_id
        self._last_load_time: float = 0
        self._last_base_mtime: float = 0
        self._last_override_mtime: float = 0
        
        # Metrics
        self._metrics = {
            "total_queries": 0,
            "hits": 0,
            "misses": 0,
            "coverage": 0.0
        }
        
        # Initial load
        self._load()
    
    def _load(self) -> None:
        """Load concepts from JSON files with validation."""
        with self._lock:
            try:
                # Load base concepts
                if not self.base_path.exists():
                    logger.warning(f"Base concepts file not found: {self.base_path}")
                    self._concepts = {}
                    return
                
                with open(self.base_path, 'r', encoding='utf-8') as f:
                    base_data = json.load(f)
                
                self._validate_schema(base_data)
                
                # Parse concepts
                concepts = {}
                for concept_dict in base_data.get("concepts", []):
                    concept = Concept(
                        id=concept_dict["id"],
                        variants=concept_dict["variants"],
                        patterns=concept_dict["patterns"],
                        domain=concept_dict["domain"],
                        confidence=concept_dict["confidence"],
                        sources=concept_dict["sources"],
                        last_seen=concept_dict["last_seen"]
                    )
                    concepts[concept.id] = concept
                
                # Load overrides if present
                if self.override_path and self.override_path.exists():
                    with open(self.override_path, 'r', encoding='utf-8') as f:
                        override_data = json.load(f)
                    
                    self._validate_schema(override_data)
                    
                    for concept_dict in override_data.get("concepts", []):
                        concept = Concept(
                            id=concept_dict["id"],
                            variants=concept_dict["variants"],
                            patterns=concept_dict["patterns"],
                            domain=concept_dict["domain"],
                            confidence=concept_dict["confidence"],
                            sources=concept_dict["sources"],
                            last_seen=concept_dict["last_seen"]
                        )
                        # Override or add new concept
                        concepts[concept.id] = concept
                        logger.info(f"Override applied for concept: {concept.id}")
                
                # Build fast lookup index
                variant_to_id = {}
                for concept_id, concept in concepts.items():
                    for variant in concept.variants:
                        variant_to_id[variant.lower()] = concept_id
                
                # Update state
                self._concepts = concepts
                self._variant_to_id = variant_to_id
                self._last_load_time = time.time()
                self._last_base_mtime = self.base_path.stat().st_mtime
                if self.override_path and self.override_path.exists():
                    self._last_override_mtime = self.override_path.stat().st_mtime
                
                logger.info(
                    f"Loaded {len(concepts)} canonical concepts "
                    f"({len(variant_to_id)} variants)"
                )
                
            except Exception as e:
                logger.error(f"Failed to load canonical concepts: {e}", exc_info=True)
                # Keep existing concepts on error
    
    def _validate_schema(self, data: dict) -> None:
        """Validate JSON schema."""
        required_fields = ["version", "concepts"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        concept_required = ["id", "variants", "patterns", "domain", "confidence", "sources", "last_seen"]
        for concept in data["concepts"]:
            for field in concept_required:
                if field not in concept:
                    raise ValueError(f"Concept missing required field: {field}")
            
            # Validate types
            if not isinstance(concept["variants"], list):
                raise ValueError(f"Concept {concept['id']}: variants must be a list")
            if not isinstance(concept["patterns"], list):
                raise ValueError(f"Concept {concept['id']}: patterns must be a list")
            if not 0 <= concept["confidence"] <= 1:
                raise ValueError(f"Concept {concept['id']}: confidence must be 0-1")
    
    def reload_if_needed(self) -> bool:
        """
        Check if files have changed and reload if needed.
        
        Returns:
            True if reload occurred, False otherwise
        """
        if self.auto_reload_interval == 0:
            return False
        
        current_time = time.time()
        if current_time - self._last_load_time < self.auto_reload_interval:
            return False
        
        # Check if files have been modified
        try:
            base_mtime = self.base_path.stat().st_mtime if self.base_path.exists() else 0
            override_mtime = 0
            if self.override_path and self.override_path.exists():
                override_mtime = self.override_path.stat().st_mtime
            
            if (base_mtime > self._last_base_mtime or 
                override_mtime > self._last_override_mtime):
                logger.info("Canonical concepts file changed, reloading...")
                self._load()
                return True
        
        except Exception as e:
            logger.warning(f"Failed to check file modification time: {e}")
        
        return False
    
    def canonicalize(self, text: str) -> Set[str]:
        """
        Convert text to canonical concept IDs.
        
        Args:
            text: Input text to canonicalize
            
        Returns:
            Set of canonical concept IDs that match the text
        """
        with self._lock:
            self.reload_if_needed()
            
            self._metrics["total_queries"] += 1
            
            matched_ids = set()
            text_lower = text.lower()
            
            # Fast lookup by variant
            words = re.findall(r'\b\w+\b', text_lower)
            for word in words:
                if word in self._variant_to_id:
                    matched_ids.add(self._variant_to_id[word])
            
            # Pattern matching (slower, but catches multi-word patterns)
            for concept_id, concept in self._concepts.items():
                if concept.matches(text):
                    matched_ids.add(concept_id)
            
            # Update metrics
            if matched_ids:
                self._metrics["hits"] += 1
            else:
                self._metrics["misses"] += 1
            
            self._metrics["coverage"] = (
                self._metrics["hits"] / self._metrics["total_queries"]
                if self._metrics["total_queries"] > 0 else 0.0
            )
            
            return matched_ids
    
    def get_variants(self, concept_id: str) -> List[str]:
        """Get all variants for a concept ID."""
        with self._lock:
            concept = self._concepts.get(concept_id)
            return concept.variants if concept else []
    
    def get_concept(self, concept_id: str) -> Optional[Concept]:
        """Get concept by ID."""
        with self._lock:
            return self._concepts.get(concept_id)
    
    def get_all_concepts(self) -> Dict[str, Concept]:
        """Get all concepts (read-only copy)."""
        with self._lock:
            return dict(self._concepts)
    
    def get_metrics(self) -> Dict:
        """Get usage metrics."""
        with self._lock:
            return dict(self._metrics)
    
    def reset_metrics(self) -> None:
        """Reset usage metrics."""
        with self._lock:
            self._metrics = {
                "total_queries": 0,
                "hits": 0,
                "misses": 0,
                "coverage": 0.0
            }


# Global singleton instance
_global_mapper: Optional[CanonicalMapper] = None
_mapper_lock = RLock()


def get_canonical_mapper(
    base_path: str = "config/canonical_concepts.json",
    override_path: Optional[str] = None,
    force_reload: bool = False
) -> CanonicalMapper:
    """
    Get or create global canonical mapper instance (singleton).
    
    Args:
        base_path: Path to base concepts JSON
        override_path: Optional path to organization-specific overrides
        force_reload: Force recreation of mapper
        
    Returns:
        CanonicalMapper instance
    """
    global _global_mapper
    
    with _mapper_lock:
        if _global_mapper is None or force_reload:
            _global_mapper = CanonicalMapper(base_path, override_path)
        
        return _global_mapper
