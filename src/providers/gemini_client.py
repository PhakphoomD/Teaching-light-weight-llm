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
from .factory import register

logger = get_logger("provider.gemini")

@register("gemini")
class GeminiClient(LLMClient):
    def __init__(self, model: str, api_key: Optional[str] = None, system_hint: Optional[str] = None):
        self.model_name = model
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY is required")
        
        # Initialize Gemini client (typed API)
        self.client = genai.Client(api_key=self.api_key)

        # Store system prompt text (passed via GenerateContentConfig)
        self._system = system_hint or "You are concise. Follow instructions exactly."

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
        """Generate once; return safety block as error."""
        try:
            # Build typed contents (single user content; supports multi-part)
            user_text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_text)]
                )
            ]

            # Typed generation config with system instruction
            cfg = types.GenerateContentConfig(
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=max_tokens,
                system_instruction=self._system,
            )

            # Call typed API (cast to Any to satisfy static typing across SDKs)
            contents_payload: Any = cast(Any, contents)
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

            # Safety check
            pf = getattr(resp, "prompt_feedback", None)
            if pf and getattr(pf, "block_reason", None):
                return ChatResult(text="", usage=Usage(), raw=resp,
                                  error=f"safety_block:{pf.block_reason}")

            return ChatResult(text=text or "", usage=Usage(), raw=resp)
        
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return ChatResult(text="", usage=Usage(), error=str(e))