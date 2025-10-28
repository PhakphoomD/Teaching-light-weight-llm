"""
TinyLlama 1.1B Client Wrapper

Convenience wrapper for TinyLlama model with default configurations.
"""

from typing import Dict, Any, List
from src.providers.factory import build_client
from src.models.tinyllama_1_1b.config import (
    DEFAULT_MAX_ITERS,
    DEFAULT_TEMPERATURE,
    REFLECTION_TEMPERATURE,
    DEFAULT_RETRIEVAL_K
)
from src.core.types import ChatResult


class TinyLlamaClient:
    """
    Wrapper class for TinyLlama 1.1B model.
    
    Provides convenient interface with model-specific defaults.
    """
    
    def __init__(self, provider: str = "local"):
        """
        Initialize TinyLlama client.
        
        Args:
            provider: Provider name ('local', 'groq', 'gemini')
        """
        self.provider = provider
        self.client = build_client(provider)
        self.model_name = "TinyLlama-1.1B-Chat-v1.0"
    
    def generate_answer(
        self,
        question: str,
        context: str = "",
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = 200
    ) -> ChatResult:
        """
        Generate answer to a question.
        
        Args:
            question: Question text
            context: Optional context from memory
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated answer text
        """
        from src.models.tinyllama_1_1b.prompts import build_answer_prompt
        
        prompt = build_answer_prompt(question, context)
        
        resp = self.client.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return resp
    
    def generate_reflection(
        self,
        question: str,
        answer: str,
        critique: Any,
        temperature: float = REFLECTION_TEMPERATURE,
        max_tokens: int = 200
    ) -> ChatResult:
        """
        Generate self-reflection from error details.
        
        Args:
            question: Original question
            answer: Student's answer
            critique: Critique object from SimpleCritic
            temperature: Sampling temperature (higher for reflection)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated reflection text
        """
        from src.models.tinyllama_1_1b.prompts import build_reflection_prompt
        
        prompt = build_reflection_prompt(question, answer, critique)
        
        resp = self.client.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return resp
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = 200
    ) -> Any:
        """
        Direct chat interface for custom use cases.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Response object from provider
        """
        return self.client.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    @property
    def name(self) -> str:
        """Return model name."""
        return self.model_name
