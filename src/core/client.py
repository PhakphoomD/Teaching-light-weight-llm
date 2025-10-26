# Abstract interface for any LLM provider client.

from abc import ABC, abstractmethod
from typing import List
from .types import Message, ChatResult

class LLMClient(ABC):
    """Every provider must implement this interface."""

    @abstractmethod
    def name(self) -> str:
        """Human-readable provider+model identifier (e.g., 'groq:llama-3.1-8b-instant')."""
        raise NotImplementedError

    @abstractmethod
    def chat(
        self,
        messages: List[Message],
        temperature: float = 0.2,
        top_p: float = 1.0,
        max_tokens: int = 256,
        timeout_s: int = 30,
    ) -> ChatResult:
        """Single-shot text generation; return a ChatResult, never raise."""
        raise NotImplementedError
