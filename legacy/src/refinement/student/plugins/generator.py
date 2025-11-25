"""
Generator Plugin

Generates student answers using LLM client.
"""

import time
from typing import Dict, Any
from ...settings import SETTINGS
from ....core.logger import get_logger
from ....prompts.student import extract_student_answer

logger = get_logger("refinement.student.generator")


class GeneratorPlugin:
    """
    Generator plugin - generates student answers.
    
    Settings used:
    - SETTINGS.generation.temperature
    - SETTINGS.generation.max_tokens
    """
    
    def __init__(self, student_client):
        """
        Initialize generator.
        
        Args:
            student_client: Student LLM client
        """
        self.client = student_client
        self.temperature = SETTINGS.generation.temperature
        self.max_tokens = SETTINGS.generation.max_tokens
        
        logger.info(
            f"GeneratorPlugin initialized: "
            f"temperature={self.temperature}, max_tokens={self.max_tokens}"
        )
    
    def generate(self, prompt: str) -> Dict[str, Any]:
        """
        Generate answer from prompt.
        
        Args:
            prompt: Full prompt (question + hints + context)
        
        Returns:
            {
                'answer': str,
                'tokens_used': int,
                'latency_ms': float
            }
        """
        logger.debug(f"Generating answer (prompt length: {len(prompt)} chars)")
        
        start_time = time.time()
        
        # Call LLM
        chat_result = self.client.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Extract answer
        answer = extract_student_answer(chat_result.text)
        
        # Track tokens
        tokens_used = 0
        if hasattr(chat_result, 'usage') and chat_result.usage:
            tokens_used = (
                getattr(chat_result.usage, 'prompt_tokens', 0) +
                getattr(chat_result.usage, 'completion_tokens', 0)
            )
        
        logger.debug(f"Generated answer: {answer[:80]}...")
        logger.debug(f"Tokens: {tokens_used}, Latency: {latency_ms:.0f}ms")
        
        return {
            "answer": answer,
            "tokens_used": tokens_used,
            "latency_ms": latency_ms
        }
