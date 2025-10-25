from __future__ import annotations
import os, time
from dataclasses import dataclass
from typing import List, Dict, Optional
from .router import build_llm

@dataclass
class ProviderSpec:
    provider: str
    model: str
    timeout_s: int = 20

class AutoRouter:
    def __init__(self, specs: List[ProviderSpec], temperature=0.2, top_p=0.9, max_tokens=64):
        self.specs = specs
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.backoff: Dict[str, float] = {}

    def _env(self, provider: str):
        p = provider.lower()
        if p == "groq":   return os.getenv("GROQ_API_KEY"), (os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1")
        if p == "openai": return os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_BASE_URL") or None
        if p == "gemini": return os.getenv("GOOGLE_API_KEY"), None
        return None, None

    def _gate(self, key: str) -> bool:
        return time.time() >= self.backoff.get(key, 0.0)

    def _ban(self, key: str, seconds=30):
        self.backoff[key] = time.time() + seconds

    def _probe(self, client, spec: ProviderSpec) -> bool:
        try:
            out = client.chat([{"role": "user", "content": "ok?"}],
                              0.0, 1, 1.0, min(10, spec.timeout_s))
            return isinstance(out.get("text", ""), str)
        except Exception:
            return False

    def pick(self):
        for spec in self.specs:
            key = f"{spec.provider}:{spec.model}"
            if not self._gate(key):
                continue
            api_key, base_url = self._env(spec.provider)
            if not api_key:
                self._ban(key, 10)
                continue
            client = build_llm(spec.provider, spec.model, api_key, base_url)
            if self._probe(client, spec):
                return client, spec
            self._ban(key, 60)
        raise RuntimeError("No healthy LLM provider available.")
