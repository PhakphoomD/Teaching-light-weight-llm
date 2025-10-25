from typing import Any, cast
from .base import LLMClient


class GeminiClient(LLMClient):
    def __init__(self, model: str, api_key: str):
        # Call through the Any-cast alias so static checkers don't complain about
        # missing exports in the package type stubs while preserving runtime
        # behavior.
        try:
            import google.generativeai as genai  # imported lazily to avoid import-time errors
        except Exception as e:
            raise ImportError("The 'google.generativeai' package is required for GeminiClient") from e

        genai_any = cast(Any, genai)
        genai_any.configure(api_key=api_key)
        self.model = genai_any.GenerativeModel(model)

    def chat(self, messages, temperature, max_tokens, top_p, timeout_s):
        prompt = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        # Cast generation_config to Any to satisfy static typing if the package's
        # GenerationConfig types are not exported in the installed stubs.
        resp = self.model.generate_content(
            prompt,
            generation_config=cast(Any, {"temperature": temperature, "top_p": top_p, "max_output_tokens": max_tokens}),
        )
        return {"text": resp.text or "", "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
    @property
    def name(self) -> str: return str(self.model)
