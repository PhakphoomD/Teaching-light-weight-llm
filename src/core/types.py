# Basic shared types used across providers and pipeline.

from dataclasses import dataclass
from typing import Dict, Optional

# Chat messages exchanged with providers (simple, text-only).
Message = Dict[str, str]  # {"role": "system|user|assistant", "content": "..."}

@dataclass
class Usage:
    """Token usage accounting; some providers may leave these as zeros."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

@dataclass
class ChatResult:
    """Normalized response wrapper returned by every provider."""
    text: str
    usage: Usage
    raw: Optional[object] = None
    error: Optional[str] = None
