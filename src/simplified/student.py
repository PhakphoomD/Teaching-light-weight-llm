"""
Simplified Student Module

Provides minimal, crisp prompts optimized for small, budget-friendly language models
(e.g., Llama 3.1 8B, Gemini Flash).

Design Principles:
1. Prompts limited to 3-4 lines to avoid context overload
2. Two prompt types: initial attempt and refinement with feedback
3. No meta-instructions or complex reasoning chains
4. Direct, actionable instructions focused on the core task

Prompt Templates:
- First attempt: "Answer this question precisely:\n{question}\n\nAnswer:"
- Refinement: "Answer: {question}\nGuidance: {feedback}\n\nAnswer:"
"""

from typing import Dict, Any, Optional
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.providers.factory import build_client
from src.utils.prompt_loader import get_prompt_loader

# Initialize prompt loader
_prompt_loader = None

def get_loader():
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = get_prompt_loader()
    return _prompt_loader


def build_first_attempt_prompt(question: str, prompt_type: str = "first_attempt") -> str:
    """
    Build minimal prompt for first attempt (no memory/feedback).
    
    Args:
        question: The question to answer
    
    Returns:
        Simple 2-line prompt
    
    Example:
        >>> prompt = build_first_attempt_prompt("What is 2+2?")
        >>> print(prompt)
        Answer this question precisely:
        What is 2+2?
        
        Answer:
    """
    loader = get_loader()
    return loader.get_student_prompt(prompt_type, question=question)


def build_refinement_prompt(
    question: str,
    previous_answer: str,
    feedback: Optional[str] = None,
    prompt_type: str = "refinement",
    no_feedback_prompt_type: str = "refinement_no_feedback",
) -> str:
    """
    Build prompt for refinement with optional feedback.
    
    Args:
        question: The question to answer
        previous_answer: Student's previous attempt
        feedback: Optional guidance from teacher
    
    Returns:
        3-4 line prompt with feedback
    
    Example with feedback:
        >>> prompt = build_refinement_prompt(
        ...     "Separate: helloworld",
        ...     "hello world",
        ...     "Split into meaningful complete words"
        ... )
        >>> print(prompt)
        Answer: Separate: helloworld
        Your previous answer: hello world
        Guidance: Split into meaningful complete words
        
        Answer:
    
    Example without feedback:
        >>> prompt = build_refinement_prompt(
        ...     "What is the capital?",
        ...     "London",
        ...     None
        ... )
        >>> print(prompt)
        Answer this question more carefully:
        What is the capital?
        Your previous answer was: London
        
        Answer:
    """
    loader = get_loader()
    if feedback and feedback.strip():
        return loader.get_student_prompt(
            prompt_type,
            question=question,
            previous_answer=previous_answer,
            feedback=feedback,
        )
    else:
        # No feedback available, use fallback
        return loader.get_student_prompt(
            no_feedback_prompt_type,
            question=question,
            previous_answer=previous_answer,
        )


class StudentClient:
    """
    Client wrapper for small language model inference.
    
    Manages communication with the student model, handling prompt delivery,
    response collection, and basic error handling.
    
    Capabilities:
    - Prompt construction with memory feedback integration
    - Request timeout management
    - Token usage tracking
    - Response extraction and cleanup
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize student client with configuration.
        
        Args:
            config: Student configuration dictionary containing:
                - model: Model identifier (e.g., "llama-3.1-8b-instant")
                - provider: LLM provider name (e.g., "groq", "gemini")
                - temperature: Sampling temperature for generation (default: 0.0)
                - max_tokens: Maximum tokens to generate (default: 128)
                - timeout: Request timeout in seconds (default: 30)
        """
        self.config = config
        self.model = config['model']
        self.temperature = config.get('temperature', 0.0)
        self.max_tokens = config.get('max_tokens', 128)
        self.timeout = config.get('timeout', 30)
        # Track total tokens used by the student model (for cost accounting)
        self.total_tokens: int = 0
        
        # Get provider from config (required)
        self.provider = config.get('provider')
        if not self.provider:
            raise ValueError(
                "Student config must specify 'provider' field. "
                "Valid options: 'local', 'gemini', 'openai', 'groq'"
            )
        
        # Initialize provider
        # Import here to avoid circular imports
        import src.providers  # Trigger provider registration
        
        self.client = build_client(
            provider=self.provider,
            model=self.model
        )
    
    def answer(self, prompt: str) -> str:
        """
        Generate answer from student model.
        
        Args:
            prompt: The prompt to send to model
        
        Returns:
            Student's answer (cleaned)
        
        Raises:
            RuntimeError: If model returns error
        """
        try:
            response = self.client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout_s=self.timeout
            )
            # Accumulate token usage if available
            usage = getattr(response, "usage", None)
            if usage is not None:
                tokens = getattr(usage, "total_tokens", None)
                if isinstance(tokens, int):
                    self.total_tokens += tokens

            if getattr(response, 'error', None):
                raise RuntimeError(f"Student model error: {response.error}")
            
            answer = (response.text or "").strip()
            
            # Clean up common artifacts
            answer = self._clean_answer(answer)
            
            return answer
            
        except Exception as e:
            print(f"[WARNING] Student error: {e}")
            return ""
    
    def _clean_answer(self, answer: str) -> str:
        """
        Clean up common artifacts in student answers.
        
        Args:
            answer: Raw answer from model
        
        Returns:
            Cleaned answer
        """
        # Remove leading "Answer:" if present
        if answer.lower().startswith("answer:"):
            answer = answer[7:].strip()
        
        # Remove trailing incomplete sentences
        # Small models sometimes generate partial or truncated output
        if answer and not answer[-1] in '.!?':
            # Try to find last complete sentence
            for end_char in ['.', '!', '?']:
                if end_char in answer:
                    last_idx = answer.rfind(end_char)
                    answer = answer[:last_idx + 1]
                    break
        
        return answer.strip()


# Example usage
if __name__ == "__main__":
    # Test prompts
    print("=" * 80)
    print("FIRST ATTEMPT PROMPT")
    print("=" * 80)
    prompt1 = build_first_attempt_prompt("What is the capital of France?")
    print(prompt1)
    print(f"\nLength: {len(prompt1)} chars")
    
    print("\n" + "=" * 80)
    print("REFINEMENT PROMPT (with feedback)")
    print("=" * 80)
    prompt2 = build_refinement_prompt(
        "Separate: helloworld",
        "hello world",
        "Split into meaningful complete words"
    )
    print(prompt2)
    print(f"\nLength: {len(prompt2)} chars")
    
    print("\n" + "=" * 80)
    print("REFINEMENT PROMPT (without feedback)")
    print("=" * 80)
    prompt3 = build_refinement_prompt(
        "What is 2+2?",
        "5",
        None
    )
    print(prompt3)
    print(f"\nLength: {len(prompt3)} chars")
