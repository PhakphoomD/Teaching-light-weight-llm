"""
Memory retrieval utilities for rule-based pattern matching.

This module provides fast, pattern-based retrieval using rule_key hashing.
The approach is designed for O(1) lookup without heavyweight ML dependencies.
"""

import re
from typing import List, Set


def normalize(text: str) -> str:
    """
    Normalize text for consistent comparison.
    
    Args:
        text: Raw input text
        
    Returns:
        Normalized text: lowercase, collapsed whitespace, stripped
    """
    if not text:
        return ""
    
    # Lowercase
    text = text.lower()
    
    # Collapse multiple whitespace to single space
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def tokenize(text: str) -> List[str]:
    """
    Simple word tokenization for rule_key extraction.
    
    Args:
        text: Input text
        
    Returns:
        List of word tokens (alphanumeric sequences)
    """
    if not text:
        return []
    
    # Extract alphanumeric word sequences
    tokens = re.findall(r'\b\w+\b', text.lower())
    
    return tokens


def compute_rule_key(question: str) -> str:
    """
    Compute a rule_key for fast retrieval based on question pattern.
    
    Rule patterns (ordered by priority):
    1. exact:WORD - Contains "exactly", "exact", "precise" → extract target word
    2. keyword:W1,W2 - Multiple important nouns/verbs
    3. one_word - Very short questions (≤3 tokens)
    4. generic - Fallback for all others
    
    Args:
        question: The question/task text
        
    Returns:
        Rule key string (e.g., "exact:ready", "keyword:calculate,result", "one_word")
        
    Examples:
        >>> compute_rule_key("Output exactly: READY")
        'exact:ready'
        >>> compute_rule_key("What color is the sky?")
        'keyword:color,sky'
        >>> compute_rule_key("Calculate 5+3")
        'keyword:calculate'
        >>> compute_rule_key("Hi")
        'one_word'
    """
    if not question:
        return "generic"
    
    norm = normalize(question)
    tokens = tokenize(norm)
    
    if not tokens:
        return "generic"
    
    # Rule 1: exact:WORD pattern
    # Look for "exactly", "exact", "precise", "output exactly"
    exact_patterns = [
        r'exactly?\s*:?\s*(\w+)',
        r'precise(?:ly)?\s*:?\s*(\w+)',
        r'output\s+exactly?\s*:?\s*(\w+)',
    ]
    
    for pattern in exact_patterns:
        match = re.search(pattern, norm)
        if match:
            target_word = match.group(1)
            return f"exact:{target_word}"
    
    # Rule 2: one_word (very short)
    if len(tokens) <= 3:
        return "one_word"
    
    # Rule 3: keyword extraction (important content words)
    # Filter out common stopwords
    stopwords: Set[str] = {
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'can', 'could', 'will',
        'would', 'should', 'may', 'might', 'must', 'shall',
        'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
        'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their',
        'this', 'that', 'these', 'those', 'what', 'which', 'who', 'when',
        'where', 'why', 'how', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'by', 'from', 'as', 'and', 'or', 'but', 'not', 'if', 'then',
    }
    
    # Extract content words (not stopwords, length > 2)
    keywords = [
        token for token in tokens
        if token not in stopwords and len(token) > 2
    ]
    
    # Take up to 3 keywords
    if keywords:
        selected = keywords[:3]
        return f"keyword:{','.join(selected)}"
    
    # Rule 4: Fallback
    return "generic"


def hash_feedback(feedback: str) -> str:
    """
    Compute a simple hash of feedback for deduplication.
    
    Uses normalized text as hash (simple but effective for small datasets).
    
    Args:
        feedback: Feedback text
        
    Returns:
        Hash string (normalized feedback)
    """
    return normalize(feedback)


def compute_similarity(text1: str, text2: str) -> float:
    """
    Compute text similarity using Jaccard similarity on words.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not text1 or not text2:
        return 0.0
    
    # Tokenize both texts
    tokens1 = set(tokenize(normalize(text1)))
    tokens2 = set(tokenize(normalize(text2)))
    
    if not tokens1 or not tokens2:
        return 0.0
    
    # Jaccard similarity: intersection / union
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    
    return intersection / union if union > 0 else 0.0


def is_similar_feedback(feedback: str, existing_feedbacks: List[str], threshold: float = 0.8) -> bool:
    """
    Check if feedback is too similar to any existing feedback.
    
    Args:
        feedback: New feedback text
        existing_feedbacks: List of existing feedback texts
        threshold: Similarity threshold (0.0 to 1.0, default 0.8)
        
    Returns:
        True if similar feedback exists (>= threshold), False otherwise
    """
    if not existing_feedbacks:
        return False
    
    for existing in existing_feedbacks:
        similarity = compute_similarity(feedback, existing)
        if similarity >= threshold:
            return True
    
    return False


def is_duplicate(feedback: str, existing_hashes: Set[str]) -> bool:
    """
    Check if feedback is duplicate based on hash.
    
    Args:
        feedback: New feedback text
        existing_hashes: Set of existing feedback hashes
        
    Returns:
        True if duplicate, False otherwise
    """
    fb_hash = hash_feedback(feedback)
    return fb_hash in existing_hashes


def extract_ngrams(tokens: List[str], n: int = 2) -> List[str]:
    """
    Extract n-grams from token list.
    
    Args:
        tokens: List of tokens
        n: N-gram size (2=bigram, 3=trigram)
        
    Returns:
        List of n-gram strings
    """
    if len(tokens) < n:
        return []
    return ["_".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def compute_tfidf_similarity(query: str, feedbacks: List[dict], limit: int = 3, threshold: float = 0.1) -> List[dict]:
    """
    Compute TF-IDF similarity between query and feedbacks with n-gram support.
    
    Improvements:
    - Uses original 'question' field for similarity (fallback to 'message')
    - Adds bigram and trigram support for better phrase matching
    - Uses TF-IDF weighted cosine similarity instead of Jaccard
    - Filters results below threshold
    
    Args:
        query: The query text
        feedbacks: List of feedback dicts with 'question' and 'message' fields
        limit: Number of most similar feedbacks to return
        threshold: Minimum similarity score (0-1, default 0.1)
        
    Returns:
        List of feedback dicts sorted by similarity (highest first)
    """
    if not feedbacks:
        return []
    
    # Normalize query
    query_norm = normalize(query)
    query_tokens = tokenize(query_norm)
    
    if not query_tokens:
        return feedbacks[:limit]
    
    # Build query feature set (unigrams + bigrams + trigrams)
    query_unigrams = set(query_tokens)
    query_bigrams = set(extract_ngrams(query_tokens, n=2))
    query_trigrams = set(extract_ngrams(query_tokens, n=3))
    query_features = query_unigrams | query_bigrams | query_trigrams
    
    if not query_features:
        return feedbacks[:limit]
    
    # Compute similarity scores (cosine with TF weighting)
    scored = []
    for fb in feedbacks:
        # Use original question for similarity (fallback to message)
        fb_text = fb.get("question", "") or fb.get("message", "")
        fb_norm = normalize(fb_text)
        fb_tokens = tokenize(fb_norm)
        
        if not fb_tokens:
            score = 0.0
        else:
            # Build feedback feature set
            fb_unigrams = set(fb_tokens)
            fb_bigrams = set(extract_ngrams(fb_tokens, n=2))
            fb_trigrams = set(extract_ngrams(fb_tokens, n=3))
            fb_features = fb_unigrams | fb_bigrams | fb_trigrams
            
            # Compute cosine similarity (binary TF-IDF approximation)
            intersection = len(query_features & fb_features)
            query_magnitude = len(query_features) ** 0.5
            fb_magnitude = len(fb_features) ** 0.5
            
            if query_magnitude > 0 and fb_magnitude > 0:
                score = intersection / (query_magnitude * fb_magnitude)
            else:
                score = 0.0
        
        # Only include if above threshold
        if score >= threshold:
            scored.append((score, fb))
    
    # Sort by score (descending) and return top K
    scored.sort(key=lambda x: x[0], reverse=True)
    return [fb for score, fb in scored[:limit]]


def extract_context_keywords(text: str, max_keywords: int = 3) -> str:
    """
    Extract key context words from text for clustering similar questions.
    
    Args:
        text: Input text (usually a question)
        max_keywords: Maximum number of keywords to extract
        
    Returns:
        Comma-separated context keywords (e.g., "algorithm,prediction,regression")
    """
    if not text:
        return "general"
    
    tokens = tokenize(text)
    
    # Filter stopwords
    stopwords: Set[str] = {
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'can', 'could', 'will',
        'would', 'should', 'may', 'might', 'must', 'shall',
        'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
        'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their',
        'this', 'that', 'these', 'those', 'what', 'which', 'who', 'when',
        'where', 'why', 'how', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'by', 'from', 'as', 'and', 'or', 'but', 'not', 'if', 'then',
    }
    
    # Extract content words
    keywords = [
        token for token in tokens
        if token not in stopwords and len(token) > 2
    ]
    
    # Return top keywords as context key
    if not keywords:
        return "general"
    
    return ",".join(keywords[:max_keywords])


def clean_feedback_message(message: str, strip_reflection: bool = True) -> str:
    """
    Clean feedback message for more focused context.
    
    Improvements:
    - Strip "REFLECTION:" prefix
    - Extract actionable advice (How to Fix, General Advice sections)
    - Remove verbose explanations
    
    Args:
        message: Raw feedback message
        strip_reflection: Whether to strip "REFLECTION:" prefix
        
    Returns:
        Cleaned, actionable feedback text
    """
    if not message:
        return ""
    
    # Strip "REFLECTION:" prefix if present
    if strip_reflection and message.strip().upper().startswith("REFLECTION"):
        # Find the first newline after REFLECTION
        lines = message.split('\n')
        # Skip first line if it's just "REFLECTION:" or "REFLECTION:\n"
        if lines and lines[0].strip().upper() in ("REFLECTION:", "REFLECTION"):
            message = '\n'.join(lines[1:])
    
    # Extract actionable sections (How to Fix, General Advice)
    sections = []
    current_section = []
    in_actionable_section = False
    
    for line in message.split('\n'):
        line_stripped = line.strip()
        
        # Check if starting actionable section
        if any(keyword in line_stripped for keyword in [
            "How to Fix", "General Advice", "What to do", "Next time"
        ]):
            if current_section:
                sections.append('\n'.join(current_section))
            current_section = [line]
            in_actionable_section = True
        # Check if ending section (empty line or new section)
        elif in_actionable_section and (not line_stripped or line_stripped.startswith("---")):
            if current_section:
                sections.append('\n'.join(current_section))
                current_section = []
            in_actionable_section = False
        # Continue current section
        elif in_actionable_section:
            current_section.append(line)
    
    # Add last section if exists
    if current_section:
        sections.append('\n'.join(current_section))
    
    # If we extracted actionable sections, return those
    if sections:
        return '\n\n'.join(sections)
    
    # Otherwise return original (cleaned) message
    return message.strip()
