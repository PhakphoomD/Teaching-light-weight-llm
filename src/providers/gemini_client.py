# Gemini provider using google-genai library (version 1.46+)
# ENV: GOOGLE_API_KEY
# Models: gemini-pro, gemini-pro-vision

from typing import List, Optional, Any, cast
import os
from google import genai
from google.genai import types

from ..core.client import LLMClient
from ..core.types import Message, ChatResult, Usage
from ..core.logger import get_logger
from ..core.tokens import estimate_tokens, estimate_prompt_tokens
from .factory import register
from .constants import get_model_limits, ModelLimits
from .ratelimit import RateLimiter

logger = get_logger("provider.gemini")

@register("gemini")
class GeminiClient(LLMClient):
    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        system_hint: Optional[str] = None,
        rpm: Optional[int] = None,
        tpm: Optional[int] = None,
        rpd: Optional[int] = None
    ):
        """
        Initialize Gemini client.
        
        Rate limits are automatically loaded from constants.py (single source of truth).
        Manual overrides (rpm/tpm/rpd parameters) should ONLY be used for testing.
        
        Args:
            model: Model name (e.g., "gemini-2.5-flash-lite")
            api_key: API key (defaults to GOOGLE_API_KEY env var)
            system_hint: System instruction
            rpm: Manual override for requests per minute (testing only)
            tpm: Manual override for tokens per minute (testing only)
            rpd: Manual override for requests per day (testing only)
        """
        self.model_name = model
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY is required")
        
        # Initialize Gemini client (typed API)
        self.client = genai.Client(api_key=self.api_key)

        # Store system prompt text (passed via GenerateContentConfig)
        self._system = system_hint or "You are concise. Follow instructions exactly."
        
        # Load rate limits from constants.py (SINGLE SOURCE OF TRUTH)
        default_limits = get_model_limits(model)
        
        # Use provided overrides ONLY if explicitly passed (for testing)
        # Otherwise, use constants.py values
        self.limits: ModelLimits = {
            'RPM': rpm if rpm is not None else default_limits['RPM'],
            'TPM': tpm if tpm is not None else default_limits['TPM'],
            'RPD': rpd if rpd is not None else default_limits['RPD']
        }
        
        # Warn if manual overrides are used in production
        if any([rpm is not None, tpm is not None, rpd is not None]):
            logger.warning(f"Manual rate limit override detected for {model}. "
                         f"Production code should use constants.py defaults!")
        
        # Initialize rate limiter with RPM, TPM, and RPD
        self._rate_limiter = RateLimiter(
            rpm=int(self.limits['RPM']),
            tpm=int(self.limits['TPM']) if self.limits['TPM'] else None,
            rpd=int(self.limits['RPD']) if self.limits['RPD'] else None
        )
        
        logger.info(f"Initialized {model} with limits: RPM={self.limits['RPM']}, TPM={self.limits['TPM']}, RPD={self.limits['RPD']}")

    def name(self) -> str:
        return f"gemini:{self.model_name}"

    def chat(
        self,
        messages: List[Message],
        temperature: float = 0.2,
        top_p: float = 1.0,
        max_tokens: int = 256,
        timeout_s: int = 30,
    ) -> ChatResult:
        """Generate once; return safety block as error. Retry with last user message if empty."""
        
        def _pack(msgs: List[Message]) -> List[types.Content]:
            """Pack all messages into typed content."""
            text = "\n".join(f"{m['role']}: {m['content']}" for m in msgs)
            return [types.Content(role="user", parts=[types.Part.from_text(text=text)])]
        
        def _pack_last_user(msgs: List[Message]) -> List[types.Content]:
            """Pack only last user message for retry."""
            last_user = next((m["content"] for m in reversed(msgs) if m["role"] == "user"), "")
            return [types.Content(role="user", parts=[types.Part.from_text(text=last_user or "Say READY")])]
        
        # Estimate tokens for rate limiting and usage tracking
        est_prompt_tokens = estimate_prompt_tokens(messages, self._system)
        est_total_tokens = est_prompt_tokens + max_tokens
        
        try:
            # Apply rate limiting BEFORE API call
            self._rate_limiter.acquire()  # RPM control
            self._rate_limiter.acquire_tokens(est_total_tokens)  # TPM control
        except Exception as rate_err:
            logger.error(f"Rate limiter error: {rate_err}")
        
        try:
            # Typed generation config with system instruction and response format
            cfg = types.GenerateContentConfig(
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=max_tokens,
                system_instruction=self._system,
                response_mime_type="text/plain",  # Nudge SDK to return plain text
            )

            # Call typed API
            contents_payload: Any = cast(Any, _pack(messages))
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=contents_payload,
                config=cfg,
            )

            # Primary extraction
            text = (getattr(resp, "text", "") or "").strip()

            # Fallback: join candidate parts if primary text empty
            if not text:
                chunks: List[str] = []
                for c in getattr(resp, "candidates", []) or []:
                    content = getattr(c, "content", None)
                    parts = getattr(content, "parts", None) if content else None
                    if parts:
                        for p in parts:
                            t = getattr(p, "text", None)
                            if t:
                                chunks.append(t)
                text = "".join(chunks).strip()

            # Retry once with last user message only if still empty
            if not text:
                logger.warning("Empty response from Gemini, retrying with last user message only")
                resp2 = self.client.models.generate_content(
                    model=self.model_name,
                    contents=cast(Any, _pack_last_user(messages)),
                    config=cfg,
                )
                text = (getattr(resp2, "text", "") or "").strip()

            # Safety check
            pf = getattr(resp, "prompt_feedback", None)
            if pf and getattr(pf, "block_reason", None):
                return ChatResult(text="", usage=Usage(), raw=resp,
                                  error=f"safety_block:{pf.block_reason}")

            # Return empty_response error if still no text
            if not text:
                return ChatResult(text="", usage=Usage(), raw=resp, error="empty_response")

            # Estimate actual token usage since Gemini doesn't return it
            actual_tokens = estimate_tokens(text) if text else 0
            usage = Usage(
                prompt_tokens=est_prompt_tokens,
                completion_tokens=actual_tokens,
                total_tokens=est_prompt_tokens + actual_tokens
            )
            
            return ChatResult(text=text, usage=usage, raw=resp)
        
        except Exception as e:
            error_str = str(e)
            logger.error(f"Gemini error: {error_str}")
            
            # Detect rate limit errors
            if any(x in error_str.lower() for x in ["rate limit", "quota", "429", "resource_exhausted"]):
                return ChatResult(text="", usage=Usage(), error="rate_limit")
            
            return ChatResult(text="", usage=Usage(), error=error_str)