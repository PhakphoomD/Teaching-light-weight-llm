# Token estimation utilities
from typing import Optional


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using a simple heuristic.
    
    Heuristic: ~4 characters per token for English text.
    This is a rough approximation suitable for rate limiting and logging.
    
    For more accurate counts, consider using a tokenizer like tiktoken or GPT-2.
    
    Args:
        text: Input text string
        
    Returns:
        Estimated token count (minimum 1 if text is non-empty)
    """
    if not text:
        return 0
    
    # Basic heuristic: 4 chars   1 token
    char_count = len(text)
    estimated = max(1, int(char_count / 4))
    
    return estimated


def estimate_prompt_tokens(messages: list, system_prompt: Optional[str] = None) -> int:
    """
    Estimate total tokens for a chat prompt.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        system_prompt: Optional system prompt text
        
    Returns:
        Estimated token count for entire prompt
    """
    total = 0
    
    # System prompt
    if system_prompt:
        total += estimate_tokens(system_prompt)
    
    # Messages
    for msg in messages:
        content = msg.get('content', '')
        total += estimate_tokens(content)
        total += 4  # Overhead per message (role markers, formatting)
    
    return total
