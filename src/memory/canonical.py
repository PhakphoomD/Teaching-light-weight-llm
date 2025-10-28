"""
Canonical Text Processing (Phase 2)

Provides text normalization and concept extraction functions:
- canonicalize(text): NFKC + lowercase + collapse-space + punct-lite
- concept_keys(question, expected_keywords): Extract canonical concept keys
- Hot-reload support via CanonicalMapper

Usage:
    from src.memory.canonical import canonicalize, concept_keys
    
    # Normalize text
    normalized = canonicalize("Hello,  World!")  # "hello, world!"
    
    # Extract concept keys
    keys = concept_keys("What is gradient descent?", ["gradient descent", "optimization"])
    # Returns: {"kw:gradient_descent", "kw:optimization"}
"""

import re
import unicodedata
from typing import Set, List, Optional

from src.memory.canonical_loader import get_canonical_mapper


def canonicalize(text: str) -> str:
    """
    Normalize text for consistent comparison.
    
    Phase 2 normalization steps:
    1. NFKC Unicode normalization (compatibility decomposition + composition)
    2. Lowercase conversion
    3. Collapse whitespace (multiple spaces -> single space)
    4. Punct-lite: preserve essential punctuation, remove decorative
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized text string
        
    Examples:
        >>> canonicalize("Hello,  World!")
        'hello, world!'
        
        >>> canonicalize("Café")  # é -> e (NFKC)
        'café'
        
        >>> canonicalize("gradient   descent")
        'gradient descent'
    """
    if not text:
        return ""
    
    # Step 1: NFKC normalization (handles accents, ligatures, etc.)
    text = unicodedata.normalize('NFKC', text)
    
    # Step 2: Lowercase
    text = text.lower()
    
    # Step 3: Collapse whitespace (tabs, newlines, multiple spaces -> single space)
    text = re.sub(r'\s+', ' ', text)
    
    # Step 4: Punct-lite - remove excessive punctuation but keep essential
    # Keep: periods, commas, hyphens, apostrophes, question marks, exclamation marks
    # Remove: brackets, quotes, etc.
    # This is a balance between "clean" and "preserve meaning"
    text = re.sub(r'["""''`]', '', text)  # Remove decorative quotes
    text = re.sub(r'[\[\]{}()<>]', '', text)  # Remove brackets
    text = re.sub(r'[_*~^]', '', text)  # Remove formatting chars
    
    # Final trim
    text = text.strip()
    
    return text


def concept_keys(
    question: str,
    expected_keywords: Optional[List[str]] = None
) -> Set[str]:
    """
    Extract canonical concept keys from question and expected keywords.
    
    Phase 2: Maps text to canonical concept IDs, then creates "kw:*" keys.
    Uses CanonicalMapper for synonym/pattern matching.
    
    Args:
        question: Question text to analyze
        expected_keywords: Optional list of expected keywords/concepts
        
    Returns:
        Set of canonical keys in format "kw:concept_id"
        
    Examples:
        >>> concept_keys("What is GD?", ["gradient descent"])
        {'kw:gradient_descent'}
        
        >>> concept_keys("Explain machine learning", ["ml", "ai"])
        {'kw:machine_learning', 'kw:artificial_intelligence'}
    """
    mapper = get_canonical_mapper()
    
    concept_ids = set()
    
    # Extract concepts from question
    question_concepts = mapper.canonicalize(question)
    concept_ids.update(question_concepts)
    
    # Extract concepts from expected keywords
    if expected_keywords:
        for keyword in expected_keywords:
            if keyword:
                keyword_concepts = mapper.canonicalize(keyword)
                concept_ids.update(keyword_concepts)
    
    # Convert to key format: "kw:concept_id"
    keys = {f"kw:{cid}" for cid in concept_ids}
    
    return keys


def normalize_for_comparison(text: str) -> str:
    """
    Normalize text for keyword comparison.
    
    More aggressive than canonicalize() - strips all punctuation.
    Used for keyword presence checking in critic evaluation.
    
    Args:
        text: Text to normalize
        
    Returns:
        Heavily normalized text (alphanumeric + spaces only)
        
    Examples:
        >>> normalize_for_comparison("gradient-descent!")
        'gradient descent'
        
        >>> normalize_for_comparison("ML/AI")
        'ml ai'
    """
    if not text:
        return ""
    
    # NFKC + lowercase (same as canonicalize)
    text = unicodedata.normalize('NFKC', text)
    text = text.lower()
    
    # Remove ALL punctuation (replace with space)
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def extract_key_terms(text: str, min_length: int = 2) -> Set[str]:
    """
    Extract significant terms from text for indexing.
    
    Filters out stop words and very short terms.
    Used for creating searchable keys.
    
    Args:
        text: Input text
        min_length: Minimum term length to include
        
    Returns:
        Set of normalized key terms
        
    Examples:
        >>> extract_key_terms("gradient descent optimization")
        {'gradient', 'descent', 'optimization'}
        
        >>> extract_key_terms("What is AI?")
        {'ai'}  # "what", "is" filtered as stop words
    """
    # Common English stop words (minimal set)
    STOP_WORDS = {
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
        'can', 'could', 'may', 'might', 'must', 'shall',
        'i', 'you', 'he', 'she', 'it', 'we', 'they',
        'this', 'that', 'these', 'those',
        'of', 'to', 'in', 'on', 'at', 'by', 'for', 'with', 'about',
        'what', 'which', 'who', 'when', 'where', 'why', 'how'
    }
    
    # Normalize
    normalized = normalize_for_comparison(text)
    
    # Split into words
    words = normalized.split()
    
    # Filter: not stop word, meets min length
    key_terms = {
        word for word in words 
        if word not in STOP_WORDS and len(word) >= min_length
    }
    
    return key_terms


# Hot-reload wrapper
def reload_canonical_concepts(force: bool = False) -> bool:
    """
    Trigger reload of canonical concepts from JSON files.
    
    Args:
        force: Force reload even if files haven't changed
        
    Returns:
        True if reload occurred, False otherwise
    """
    mapper = get_canonical_mapper()
    
    if force:
        # Force reload by recreating mapper
        get_canonical_mapper(force_reload=True)
        return True
    else:
        # Let mapper check file mtimes
        return mapper.reload_if_needed()
