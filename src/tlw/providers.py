"""Ollama-backed 'local' provider for the new core (T2.6 build decision 2).

`.claude/rules/providers.md` defines **local = Ollama** (`qwen2.5:7b-instruct`,
`llama3.1:8b`, RTX 4060 8GB). But the ProviderRegistry's existing "local"
entry (`src/providers/local_client.py::LocalTinyLlama`) is a
HuggingFace-transformers TinyLlama loader — a different provider entirely.
This gap was already flagged, not fixed, in T2.3
(`src/tlw/evaluation/calibration.py` module docstring: "'local' as used by
config/base.yml ... has no matching ProviderRegistry entry yet ... owned by
T2.1/ops-engineer, the ProviderRegistry seam").

**Fix (strangler-style, structure.md §E):** this module registers a real
Ollama HTTP client under the SAME name "local", so any process that imports
it gets Ollama for slot A/B/F `provider: local`. It does **not** edit
`src/providers/local_client.py` or `src/providers/__init__.py` (frozen /
untouched — those keep TinyLlama for the legacy loop, which never imports
`src.tlw`).

**Verified duplicate-registration behavior** (read `src/providers/factory.py:6-13`):
`register()`'s `_wrap` does `_REGISTRY[name] = cls` unconditionally — no
existing-key guard, no exception. So importing this module AFTER
`src.providers` (which registers `LocalTinyLlama` under "local" as an import
side effect, `src/providers/__init__.py:11`) silently overwrites the
binding to `OllamaClient`. Import order decides which "local" a given
process gets:
  - legacy (`simplified_teaching_loop.py` et al.) never imports `src.tlw.*`
    -> keeps `LocalTinyLlama`.
  - the new core (`src/tlw/runner.py`, `run.py`) imports this module before
    any `build_client("local", ...)` call -> gets `OllamaClient`.
Both cores can therefore coexist during the strangler period without either
being edited (structure.md §E migration policy).

Do not import this module from any frozen-legacy file or from
`src/providers/__init__.py` itself — only the new core imports it.
"""

from __future__ import annotations

import json
import urllib.request
from typing import List

from src.core.client import LLMClient
from src.core.types import ChatResult, Message, Usage
from src.providers.factory import register

DEFAULT_HOST = "http://localhost:11434"


@register("local")
class OllamaClient(LLMClient):
    """Local provider = the Ollama HTTP daemon (providers.md), model-name
    driven (e.g. 'qwen2.5:7b-instruct', 'llama3.1:8b'). Adapted from the
    proven `_OllamaAdapter` in `src/tlw/evaluation/calibration.py:63-89`
    (same request shape, now promoted from a test-only bypass to the real
    registered "local" client the whole new core resolves through)."""

    def __init__(self, model: str, host: str = DEFAULT_HOST, **_ignored):
        self.model = model
        self.host = host.rstrip("/")

    def name(self) -> str:
        return f"local:{self.model}"

    def chat(
        self,
        messages: List[Message],
        temperature: float = 0.2,
        top_p: float = 1.0,
        max_tokens: int = 256,
        timeout_s: int = 30,
        seed: int | None = None,
    ) -> ChatResult:
        options = {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": max_tokens,
        }
        if seed is not None:
            # Ollama `options.seed` makes sampling reproducible for a given
            # (model, prompt, options) — used by the WixQA 3-seed re-run (T3.9)
            # so seeds {13,42,123} are distinct-but-reproducible draws (§0.3).
            options["seed"] = seed
        payload = {
            "model": self.model,
            "messages": list(messages),
            "stream": False,
            "options": options,
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp_raw:
                resp = json.loads(resp_raw.read())
            text = (resp.get("message", {}) or {}).get("content", "") or ""
            prompt_tokens = int(resp.get("prompt_eval_count") or 0)
            completion_tokens = int(resp.get("eval_count") or 0)
            usage = Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            )
            return ChatResult(text=text, usage=usage, raw=resp)
        except Exception as e:  # noqa: BLE001 - LLMClient.chat contract: never raise
            return ChatResult(text="", usage=Usage(), error=str(e))
