"""
Semantic Rule Memory Module

This module distills high-quality "rules" from episodic teaching records.
Rules are short, reusable lessons that can guide future refinements.

Key Concepts:
- Episodic Memory: Individual teaching episodes (question -> hint -> outcome)
- Semantic Rules: Distilled, reusable lessons from multiple episodes
- Quality Gating: Only create rules from high-quality episodes (stop_score >= threshold)
- Deduplication: Merge similar hints into single rules
- Support Tracking: Count how many episodes support each rule

Example Flow:
    1. Episodes: "Split sentence: X" -> hint: "Use words not chars" (quality=0.9)
       Episodes: "Split sentence: Y" -> hint: "Separate by words" (quality=0.85)
    2. Distill: Both hints -> Rule: "For 'Split' tasks: separate by WORDS, not chars"
    3. Reuse: New "Split sentence: Z" -> inject rule as guidance

Architecture inspired by:
- Self-Refine (Madaan et al., 2023): Iterative refinement with feedback
- Reflexion (Shinn et al., 2023): Episodic + semantic memory for agents
- Memory-Augmented LLMs: RAG + distilled rules for efficiency

References:
- Self-Refine: https://arxiv.org/abs/2303.17651
- Reflexion: https://arxiv.org/abs/2303.11366
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import Counter
from datetime import datetime
import hashlib

from src.core.logger import get_logger

logger = get_logger("memory.semantic_rules")


class SemanticRuleStore:
    """
    Store for semantic rules distilled from teaching episodes.
    
    Rules are high-quality lessons that:
    - Are reusable across similar tasks
    - Come from episodes with high stop_score (>= quality gate)
    - Are deduplicated (similar hints merged)
    - Track support count (how many episodes confirm this rule)
    
    Storage Format (semantic_rules.json):
        {
            "rule_0001": {
                "rule_id": "rule_0001",
                "domain": "general",
                "text": "For 'Split sentence' tasks: separate by WORDS, not characters",
                "source_evidence": ["20251111_120001_a1b2", "20251111_120102_c3d4"],
                "quality_score": 0.875,
                "support_count": 2,
                "last_seen_ts": 1731304325
            },
            ...
        }
    
    Quality Score Calculation:
        - Weighted average of all supporting episodes' stop_scores
        - Higher support_count -> more confident in rule quality
        - Example: episode1 (0.9) + episode2 (0.85) -> avg = 0.875
    
    Usage:
        >>> store = SemanticRuleStore()
        >>> # Distill rules from recent episodes
        >>> store.distill_from_episodes(episodes, min_quality=0.7)
        >>> # Retrieve top rules for guidance
        >>> top_rules = store.get_top_rules(k=3, min_quality=0.7)
        >>> # Inject into prompt
        >>> rules_text = "\\n".join([f"  {r['text']}" for r in top_rules])
    """
    
    def __init__(self, file_path: str = "logs/memory/semantic_rules.json"):
        """
        Initialize semantic rule store.
        
        Args:
            file_path: Path to JSON file storing rules
        """
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.rules: Dict[str, Dict[str, Any]] = {}
        self._load_rules()
        
        logger.info(
            f"SemanticRuleStore initialized: {len(self.rules)} rules loaded"
        )
    
    def _load_rules(self) -> None:
        """Load rules from JSON file."""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.rules = json.load(f)
                logger.debug(f"Loaded {len(self.rules)} semantic rules from disk")
            except Exception as e:
                logger.error(f"Failed to load semantic rules: {e}")
                self.rules = {}
        else:
            logger.debug("No existing semantic rules file")
    
    def _save_rules(self) -> None:
        """Save rules to JSON file."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.rules, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved {len(self.rules)} semantic rules to disk")
        except Exception as e:
            logger.error(f"Failed to save semantic rules: {e}")
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for deduplication matching.
        
        Args:
            text: Input text
        
        Returns:
            Normalized text (lowercase, stripped, single spaces)
        """
        # Lowercase and strip
        normalized = text.strip().lower()
        # Normalize whitespace
        normalized = " ".join(normalized.split())
        return normalized
    
    def _compute_rule_hash(self, text: str) -> str:
        """
        Compute stable hash for rule text.
        
        Args:
            text: Rule text
        
        Returns:
            8-character hex hash
        """
        normalized = self._normalize_text(text)
        hash_obj = hashlib.md5(normalized.encode('utf-8'))
        return hash_obj.hexdigest()[:8]
    
    def add_or_update_rule(
        self,
        rule_text: str,
        source_episode_id: str,
        quality_score: float,
        domain: str = "general",
        error_keys: Optional[List[str]] = None
    ) -> str:
        """
        Add a new rule or update existing one.
        
        If a similar rule exists (normalized text match), update it:
        - Add source_episode_id to evidence
        - Increment support_count
        - Update quality_score (weighted average)
        
        Args:
            rule_text: The rule text (1-3 sentences recommended)
            source_episode_id: Episode ID that generated this rule
            quality_score: Quality score from episode (0.0-1.0)
            domain: Domain/category (e.g., "general", "math", "coding")
            error_keys: Optional error keys from episode
        
        Returns:
            rule_id: The rule ID (new or existing)
        
        Example:
            >>> store.add_or_update_rule(
            ...     rule_text="For 'Split' tasks: use words not chars",
            ...     source_episode_id="20251111_120001_a1b2",
            ...     quality_score=0.9,
            ...     error_keys=["format"]
            ... )
            'rule_0001'
        """
        if not rule_text or not rule_text.strip():
            logger.warning("Empty rule_text, skipping")
            return ""
        
        # Clamp quality_score
        quality_score = max(0.0, min(1.0, quality_score))
        
        # Check if similar rule exists (exact normalized match)
        rule_hash = self._compute_rule_hash(rule_text)
        rule_id = None
        
        for rid, rule in self.rules.items():
            if self._compute_rule_hash(rule["text"]) == rule_hash:
                rule_id = rid
                break
        
        # Create new rule if not exists
        if not rule_id:
            rule_id = f"rule_{len(self.rules) + 1:04d}"
            self.rules[rule_id] = {
                "rule_id": rule_id,
                "domain": domain,
                "text": rule_text.strip(),
                "source_evidence": [],
                "quality_score": 0.0,
                "support_count": 0,
                "last_seen_ts": 0,
                "error_keys": error_keys or []
            }
            logger.debug(f"Created new rule: {rule_id}")
        
        # Update rule
        rule = self.rules[rule_id]
        
        # Add source evidence (avoid duplicates)
        if source_episode_id not in rule["source_evidence"]:
            rule["source_evidence"].append(source_episode_id)
        
        # Update support count
        rule["support_count"] += 1
        
        # Update timestamp
        rule["last_seen_ts"] = int(datetime.now().timestamp())
        
        # Update quality score (weighted average)
        old_score = rule["quality_score"]
        old_count = rule["support_count"] - 1
        
        if old_count == 0:
            # First support
            new_score = quality_score
        else:
            # Weighted average
            new_score = (old_score * old_count + quality_score) / rule["support_count"]
        
        rule["quality_score"] = new_score
        
        # Merge error_keys (deduplicate)
        if error_keys:
            for key in error_keys:
                if key not in rule["error_keys"]:
                    rule["error_keys"].append(key)
        
        self._save_rules()
        
        logger.debug(
            f"Updated rule {rule_id}: support={rule['support_count']}, "
            f"quality={new_score:.3f}, text='{rule_text[:50]}...'"
        )
        
        return rule_id
    
    def get_top_rules(
        self,
        k: int = 3,
        min_quality: float = 0.7,
        min_support: int = 2,
        domain: Optional[str] = None,
        error_keys: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get top-k rules by quality score.
        
        Args:
            k: Number of rules to return
            min_quality: Minimum quality score threshold
            min_support: Minimum support count (number of episodes)
            domain: Optional domain filter
            error_keys: Optional error keys filter (return rules matching ANY key)
        
        Returns:
            List of rule dicts, sorted by quality score (descending)
        
        Example:
            >>> # Get top 3 general rules with quality >= 0.7
            >>> rules = store.get_top_rules(k=3, min_quality=0.7)
            >>> for rule in rules:
            ...     print(f"{rule['text']} (quality={rule['quality_score']:.2f})")
            
            >>> # Get rules for specific error types
            >>> rules = store.get_top_rules(k=3, error_keys=["format", "incomplete"])
        """
        if k <= 0:
            return []
        
        # Filter rules
        filtered = []
        for rule in self.rules.values():
            # Quality check
            if rule["quality_score"] < min_quality:
                continue
            
            # Support check
            if rule["support_count"] < min_support:
                continue
            
            # Domain check
            if domain and rule["domain"] != domain:
                continue
            
            # Error keys check (match ANY key)
            if error_keys:
                rule_keys = set(rule.get("error_keys", []))
                query_keys = set(error_keys)
                if not rule_keys.intersection(query_keys):
                    continue
            
            filtered.append(rule)
        
        # Sort by quality score (descending)
        sorted_rules = sorted(
            filtered,
            key=lambda r: r["quality_score"],
            reverse=True
        )
        
        result = sorted_rules[:k]
        
        if result:
            logger.debug(
                f"Retrieved {len(result)} rules (filtered from {len(self.rules)} total)"
            )
        
        return result
    
    def distill_from_episodes(
        self,
        episodes: List[Dict[str, Any]],
        min_quality: float = 0.7,
        min_hint_length: int = 10
    ) -> int:
        """
        Distill rules from a list of episodes.
        
        Process:
        1. Filter episodes by quality (stop_score >= min_quality)
        2. Extract hints from episodes
        3. Group similar hints (normalized text matching)
        4. Create rules for hints that appear 2+ times
        5. Add/update rules in store
        
        Args:
            episodes: List of episode records with 'hint' and 'stop_score'
            min_quality: Minimum stop_score threshold for rule creation
            min_hint_length: Minimum hint length (characters)
        
        Returns:
            Number of rules created/updated
        
        Example:
            >>> episodes = list(store.load_records())
            >>> rules_count = rule_store.distill_from_episodes(
            ...     episodes,
            ...     min_quality=0.7
            ... )
            >>> print(f"Distilled {rules_count} rules")
        """
        if not episodes:
            logger.debug("No episodes to distill")
            return 0
        
        rules_updated = 0
        
        # Group hints by normalized text
        hint_groups: Dict[str, List[Dict]] = {}
        
        for ep in episodes:
            # Extract hint
            hint = ep.get("hint", "").strip()
            if not hint or len(hint) < min_hint_length:
                continue
            
            # Get quality score
            quality = ep.get("stop_score", 0.0)
            
            # Filter by quality
            if quality < min_quality:
                continue
            
            # Get error keys
            error_keys = ep.get("error_keys", [])
            
            # Normalize hint for grouping
            normalized = self._normalize_text(hint)
            
            if normalized not in hint_groups:
                hint_groups[normalized] = []
            
            hint_groups[normalized].append({
                "id": ep.get("id", ""),
                "hint": hint,  # Original text (not normalized)
                "quality": quality,
                "error_keys": error_keys
            })
        
        # Create rules for hints that appear multiple times (support >= 2)
        for normalized, group in hint_groups.items():
            # Need at least 1 occurrence to create rule (changed from 2)
            # This allows single high-quality hints to become rules
            if len(group) < 1:
                continue
            
            # Use the first hint as canonical text
            canonical_hint = group[0]["hint"]
            
            # Collect all error keys from group
            all_error_keys = []
            for item in group:
                all_error_keys.extend(item.get("error_keys", []))
            unique_error_keys = list(set(all_error_keys))
            
            # Add/update rule for each episode in group
            for item in group:
                self.add_or_update_rule(
                    rule_text=canonical_hint,
                    source_episode_id=item["id"],
                    quality_score=item["quality"],
                    error_keys=unique_error_keys
                )
            
            rules_updated += 1
        
        if rules_updated > 0:
            logger.info(
                f"Distilled {rules_updated} rules from {len(episodes)} episodes "
                f"(min_quality={min_quality})"
            )
        else:
            logger.debug(
                f"No rules distilled from {len(episodes)} episodes "
                f"(min_quality={min_quality} may be too high)"
            )
        
        return rules_updated
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about semantic rules.
        
        Returns:
            Dict with stats:
            - total_rules: Total number of rules
            - avg_quality: Average quality score
            - avg_support: Average support count
            - high_quality: Rules with quality >= 0.8
            - domains: Count by domain
        """
        if not self.rules:
            return {
                "total_rules": 0,
                "avg_quality": 0.0,
                "avg_support": 0.0,
                "high_quality": 0,
                "domains": {}
            }
        
        qualities = [r["quality_score"] for r in self.rules.values()]
        supports = [r["support_count"] for r in self.rules.values()]
        high_quality = sum(1 for q in qualities if q >= 0.8)
        
        domains: Dict[str, int] = {}
        for rule in self.rules.values():
            domain = rule.get("domain", "unknown")
            domains[domain] = domains.get(domain, 0) + 1
        
        return {
            "total_rules": len(self.rules),
            "avg_quality": sum(qualities) / len(qualities) if qualities else 0.0,
            "avg_support": sum(supports) / len(supports) if supports else 0.0,
            "high_quality": high_quality,
            "domains": domains
        }
    
    def clear(self) -> None:
        """
        Clear all semantic rules.
        
        Warning: This is irreversible!
        """
        self.rules = {}
        self._save_rules()
        logger.warning("Cleared all semantic rules")
