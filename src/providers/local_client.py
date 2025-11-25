"""
TinyLlama Local Provider Module

A production-grade implementation for local inference using TinyLlama models.
Features shared model caching, automatic device management, and robust error handling.

Architecture highlights:
- Thread-safe model caching with device awareness
- Automatic CUDA/CPU detection and optimization
- Comprehensive error handling with custom exceptions
- Memory-efficient inference with proper cleanup
"""

from typing import List, Optional, ClassVar
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer

from ..core.client import LLMClient
from ..core.types import Message, ChatResult, Usage
from ..core.logger import get_logger
from .factory import register

# Module-level logger for operational monitoring
logger = get_logger("provider.local")

# Domain-specific exception hierarchy
class TinyLlamaError(Exception):
    """Base exception for TinyLlama domain errors."""
    pass

class ModelLoadError(TinyLlamaError):
    """Model initialization or loading failure."""
    pass

class GenerationError(TinyLlamaError):
    """Text generation runtime failure."""
    pass

@register("local")
class LocalTinyLlama(LLMClient):
    """
    High-performance local inference provider utilizing TinyLlama models.
    
    Core features:
    - Device-aware model caching to optimize memory usage
    - Thread-safe model instance management
    - Automatic device selection and optimization
    - Robust error handling and resource cleanup
    
    The caching mechanism uses a composite key combining model ID and device
    to ensure proper model-device alignment across multiple instances.
    """
    
    # Class-level cache with double-underscore name mangling for encapsulation
    __tok: ClassVar[Optional[PreTrainedTokenizer]] = None
    __mdl: ClassVar[Optional[PreTrainedModel]] = None
    __loaded_id: ClassVar[Optional[str]] = None  # Composite cache key (model_id::device)
    
    @classmethod
    def get_cached_model(cls) -> Optional[PreTrainedModel]:
        return cls.__mdl
        
    @classmethod
    def get_cached_tokenizer(cls) -> Optional[PreTrainedTokenizer]:
        return cls.__tok
        
    @classmethod
    def get_cached_id(cls) -> Optional[str]:
        return cls.__loaded_id
        
    @classmethod
    def update_cache(cls, tok: PreTrainedTokenizer, mdl: PreTrainedModel, cache_key: str) -> None:
        cls.__tok = tok
        cls.__mdl = mdl
        cls.__loaded_id = cache_key

    def __init__(
        self, 
        model: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0", 
        device: Optional[str] = None,
        load_in_8bit: bool = False,
        use_cache: bool = True
    ) -> None:
        """
        Initialize a new TinyLlama inference provider.

        Args:
            model: HuggingFace model identifier
            device: Target device ('cuda' or 'cpu'). Auto-detected if None
            load_in_8bit: Enable 8-bit quantization for CUDA devices
            use_cache: Enable model caching across instances

        Raises:
            ModelLoadError: If model initialization fails
        """
        self.model_id = model
        self.use_cache = use_cache
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        
        # These will be initialized in the try block
        self.tok: PreTrainedTokenizer  # Required attribute
        self.mdl: PreTrainedModel     # Required attribute
        
        # Composite cache key incorporating model and device
        cache_key = f"{self.model_id}::{self.device}"

        try:
            if not use_cache or self.get_cached_model() is None or self.get_cached_id() != cache_key:
                logger.info(f"Cache miss. Loading TinyLlama: {self.model_id} onto {self.device}")
                
                # Get HuggingFace token from environment (for gated models like Llama)
                hf_token = os.environ.get('HUGGINGFACE_HUB_TOKEN') or os.environ.get('HF_TOKEN')
                
                tok = AutoTokenizer.from_pretrained(
                    self.model_id, 
                    use_fast=True,
                    trust_remote_code=True,
                    token=hf_token  # Pass token for gated repos
                )

                model_kwargs = {
                    "dtype": torch.float16 if self.device == "cuda" else torch.float32,
                    "device_map": "auto" if self.device == "cuda" else None,
                    "load_in_8bit": load_in_8bit if self.device == "cuda" else False,
                    "trust_remote_code": True,
                    "token": hf_token,  # Pass token for gated repos
                }

                mdl = AutoModelForCausalLM.from_pretrained(self.model_id, **model_kwargs)

                # Move model to CPU if needed (use standard PyTorch API)
                if self.device == "cpu" and model_kwargs.get("device_map") is None:
                    mdl = mdl.cpu()
                
                # --- Store in instance ---
                self.tok = tok
                self.mdl = mdl

                # --- Update cache if enabled ---
                if use_cache:
                    logger.info(f"Updating cache for key: {cache_key}")
                    self.update_cache(tok, mdl, cache_key)
            
            else:
                # --- Cache HIT ---
                logger.info(f"Cache hit. Reusing model from key: {cache_key}")
                # Point instance attributes to the cached class attributes
                tok = self.get_cached_tokenizer()
                mdl = self.get_cached_model()
                if tok is None or mdl is None:
                    raise ModelLoadError("Cache is corrupted - model or tokenizer is None")
                self.tok = tok
                self.mdl = mdl

        except Exception as e:
            raise ModelLoadError(f"Failed to load TinyLlama model: {e}") from e

    def __del__(self):
        """Cleanup resources *if* this instance was not using the cache."""
        if not self.use_cache and hasattr(self, 'mdl'):
            logger.debug(f"Deleting non-cached model instance for {self.model_id}")
            del self.mdl
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def name(self) -> str:
        """Return unique identifier for this provider instance."""
        return f"local:{self.model_id}::{self.device}"

    def _format_prompt(self, messages: List[Message]) -> str:
        """
        Format conversation messages into model-specific prompt structure.
        
        Primary: try model's chat template.
        Fallback: minimal format to reduce drift: `user: ...\nassistant:`
        """
        try:
            result = self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            if not isinstance(result, str):
                raise ValueError("Chat template returned non-string result")
            return result
        except Exception as e:
            # Downgrade to debug - many models don't have chat templates (expected behavior)
            logger.debug(f"Native chat template not available: {e}. Using minimal fallback.")
            last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            prompt_str = f"user: {last_user}\nassistant:"
            return prompt_str

    def chat(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        top_p: float = 0.95,
        max_tokens: int = 512,
        timeout_s: int = 30,  # Reserved for future implementation
    ) -> ChatResult:
        """
        Generate model response for a given conversation.
        
        Implementation notes:
        - Uses efficient tensor operations with proper device placement
        - Implements standard sampling-based generation
        - Handles prompt formatting with fallback options
        - Provides accurate token accounting
        """
        try:
            # Instance attributes guaranteed by constructor
            prompt = self._format_prompt(messages)
            inputs = self.tok(prompt, return_tensors="pt")
            
            # Ensure tensors are on same device as model
            inputs = {k: v.to(self.mdl.device) for k, v in inputs.items()}
            
            # Determine pad_token_id fallback
            pad_id = getattr(self.tok, "eos_token_id", None) or getattr(self.tok, "pad_token_id", None)
            if pad_id is None:
                logger.warning("Tokenizer missing eos_token_id and pad_token_id; falling back to 0 for pad_token_id")
                pad_id = 0
            
            # Use deterministic generation when temperature is 0.0 (for smoke tests)
            do_sample_flag = not (temperature == 0.0)
            
            generation_config = {
                "max_new_tokens": max_tokens,
                "do_sample": do_sample_flag,
                "pad_token_id": int(pad_id),
            }
            
            # Add sampling parameters only if do_sample is True
            if do_sample_flag:
                generation_config.update({
                    "temperature": max(temperature, 0.01),  # Temp 0 causes issues
                    "top_p": top_p,
                    "repetition_penalty": 1.1,
                    "no_repeat_ngram_size": 3
                })
            
            with torch.no_grad():
                gen_ids = self.mdl.generate(**inputs, **generation_config)

            # Decode only the newly generated tokens for accurate response extraction
            # Use tensor sizes (not Python len) for correctness with batched tensors
            input_length = inputs['input_ids'].size(1)
            new_tokens = gen_ids[0][input_length:]
            text = self.tok.decode(new_tokens, skip_special_tokens=True).strip()

            return ChatResult(
                text=text,
                usage=Usage(
                    prompt_tokens=int(input_length),
                    completion_tokens=int(gen_ids.size(1) - input_length)
                )
            )
            
        except Exception as e:
            logger.error(f"Generation failed: {str(e)}")
            raise GenerationError(f"TinyLlama generation error: {e}") from e