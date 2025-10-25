from typing import Any, cast, List, Dict
from .base import LLMClient


class OpenAILike(LLMClient):
    def __init__(self, model: str, api_key: str, base_url: str | None = None):
        self.model = model
        # Import the OpenAI client lazily so importing this module doesn't
        # require the `openai` package to be installed. If the package is
        # missing, attempting to instantiate this class will raise with a
        # clear message.
        try:
            from openai import OpenAI
        except Exception as e:
            raise ImportError("The 'openai' package is required for OpenAILike") from e

        # The OpenAI client accepts api_key and base_url in recent SDKs.
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, messages, temperature, max_tokens, top_p, timeout_s):
        # Convert our Message dicts ({{'role':..., 'content': ...}}) into the
        # SDK-native message representation. The OpenAI SDK expects messages
        # shaped like ChatCompletionMessageParam; constructing dicts with the
        # proper keys is sufficient at runtime. We cast to Any at the callsite
        # to satisfy type-checkers that don't know our Message shape maps to
        # the SDK type.
        sdk_messages: List[Dict[str, str]] = [
            {"role": m["role"], "content": m["content"]} for m in messages
        ]

        r = self.client.chat.completions.create(
            model=self.model,
            messages=cast(Any, sdk_messages),
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            timeout=timeout_s,
        )
        msg = r.choices[0].message.content or ""
        usage = r.usage or None
        return {
            "text": msg,
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
            },
        }

    @property
    def name(self) -> str:
        return self.model

