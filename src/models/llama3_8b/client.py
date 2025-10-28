"""
Meta Llama 3 8B Client Wrapper

Convenience wrapper for Meta Llama 3 8B model with default configurations.
"""

from typing import Dict, Any, List
from src.providers.factory import build_client
from src.models.llama3_8b.config import (
    MODEL_NAME,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    REFLECTION_TEMPERATURE,
    DEFAULT_MAX_ITERS,
    DEFAULT_RETRIEVAL_K
)
from src.core.types import ChatResult


class Llama3Client:
    """
    Wrapper class for Meta Llama 3 8B model.
    
    Provides convenient interface with model-specific defaults.
    """
    
    def __init__(self, provider: str = "local"):
        """
        Initialize Llama 3 8B client.
        
        Args:
            provider: Provider name ('local', 'groq', 'gemini')
        """
        self.provider = provider
        if provider == "local":
            # For local provider, pass the model name
            self.client = build_client(provider, model=MODEL_NAME)
        else:
            self.client = build_client(provider)
        self.model_name = "Meta-Llama-3-8B"
    
    def generate_answer(
        self,
        question: str,
        context: str = "",
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS
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
        from src.models.llama3_8b.prompts import build_answer_prompt
        
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
        max_tokens: int = DEFAULT_MAX_TOKENS
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
        from src.models.llama3_8b.prompts import build_reflection_prompt
        
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
        max_tokens: int = DEFAULT_MAX_TOKENS
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
