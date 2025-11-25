# Groq provider (OpenAI-compatible Chat Completions) - ENABLED
# Fast Llama inference with rate limiting
# ENV: GROQ_API_KEY
# Models: 'llama-3.1-8b-instant', 'llama-3.3-70b-versatile', etc.

from typing import List, Optional, Dict, Any, cast
import os
from groq import Groq
from groq.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionAssistantMessageParam
)

from ..core.client import LLMClient
from ..core.types import Message, ChatResult, Usage
from ..core.logger import get_logger
from .factory import register
from .ratelimit import RateLimiter

logger = get_logger("provider.groq")

# Groq Rate Limits (as of 2025-11-14)
# Source: https://console.groq.com/docs/rate-limits
GROQ_RATE_LIMITS = {
    "llama-3.1-8b-instant": {"rpm": 30, "rpd": 14400, "tpm": 6000, "tpd": 500000},
    "llama-3.3-70b-versatile": {"rpm": 30, "rpd": 1000, "tpm": 12000, "tpd": 100000},
    "llama-guard-3-8b": {"rpm": 30, "rpd": 14400, "tpm": 15000, "tpd": 500000},
    "qwen/qwen3-32b": {"rpm": 60, "rpd": 1000, "tpm": 6000, "tpd": 500000},
    "groq/compound": {"rpm": 30, "rpd": 250, "tpm": 70000, "tpd": None},
    "groq/compound-mini": {"rpm": 30, "rpd": 250, "tpm": 70000, "tpd": None},
}

def _convert_to_groq_message(msg: Message) -> dict:
    """Convert our Message type to an OpenAI-compatible dict for Groq.

    Using plain dicts is the most stable approach across Groq SDK versions.
    """
    role = msg.get("role", "user")
    content = msg.get("content", "")
    return {"role": role, "content": content}

def _usage(u) -> Usage:
    """Normalize Groq usage to our Usage dataclass."""
    if not u:
        return Usage()
    return Usage(
        prompt_tokens=getattr(u, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(u, "completion_tokens", 0) or 0,
        total_tokens=getattr(u, "total_tokens", 0) or 0,
    )

@register("groq")
class GroqClient(LLMClient):
    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is required")
        
        # Initialize Groq client
        self._client = Groq(api_key=self.api_key)
        
        # Initialize rate limiter
        limits = GROQ_RATE_LIMITS.get(model, GROQ_RATE_LIMITS["llama-3.1-8b-instant"])
        self._rate_limiter = RateLimiter(
            rpm=limits["rpm"],
            tpm=limits["tpm"],
            rpd=limits["rpd"]
        )
        
        logger.info(f"Initialized {model} with limits: RPM={limits['rpm']}, TPM={limits['tpm']}, RPD={limits['rpd']}")

    def name(self) -> str:
        return f"groq:{self.model}"

    def chat(
        self,
        messages: List[Message],
        temperature: float = 0.2,
        top_p: float = 1.0,
        max_tokens: int = 256,
        timeout_s: int = 30,
    ) -> ChatResult:
        """Single-call chat completion with rate limiting."""
        try:
            # Rate limit (RPM control)
            self._rate_limiter.acquire()
            
            # Convert messages to Groq's expected format
            groq_messages = [_convert_to_groq_message(msg) for msg in messages]
            
            groq_payload: Any = cast(Any, groq_messages)
            r = cast(Any, self._client).chat.completions.create(
                model=self.model,
                messages=groq_payload,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                timeout=timeout_s,
            )
            choice = r.choices[0] if getattr(r, "choices", None) else None
            text = (choice.message.content if choice else "") or ""
            
            # Track tokens (TPM control)
            usage = _usage(getattr(r, "usage", None))
            if usage.total_tokens > 0:
                self._rate_limiter.acquire_tokens(usage.total_tokens)
            
            return ChatResult(text=text, usage=usage, raw=r)
        except Exception as e:
            logger.error(f"Groq error: {e}")
            return ChatResult(text="", usage=Usage(), error=str(e))
