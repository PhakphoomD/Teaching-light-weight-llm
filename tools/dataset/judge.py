"""
LLM quality judges for D4 (answer quality) — pluggable backends so we can compare.

Two backends:
- GroqJudge:  cloud API (fast). Default model llama-3.3-70b-versatile.
- OllamaJudge: local, private, free (runs on the RTX 4060). Default qwen2.5:7b-instruct.

Both score answer quality WITHOUT a reference (blind) on 0.0–1.0, so the judge is
independent of the reference text (§0.2 spirit). Deterministic (temperature 0).
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

QUALITY_PROMPT = (
    "You are a strict evaluator. Rate the quality of the ANSWER to the QUESTION "
    "WITHOUT any reference answer.\n\n"
    "QUESTION: {q}\n"
    "ANSWER: {a}\n\n"
    "Judge: (1) does it actually address THIS question, (2) coherence, "
    "(3) completeness, (4) factual correctness.\n"
    "Output ONLY a number from 0.0 to 1.0 — 1.0=excellent, 0.5=partial, "
    "0.0=irrelevant/wrong. No words, just the number."
)

_NUM = re.compile(r"\d*\.?\d+")


def _parse_score(text: str) -> Optional[float]:
    if not text:
        return None
    m = _NUM.search(text.strip())
    if not m:
        return None
    try:
        return max(0.0, min(1.0, float(m.group(0))))
    except ValueError:
        return None


class GroqJudge:
    name = "groq"

    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        from groq import Groq

        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set")
        self.client = Groq(api_key=key)
        self.model = model
        self.label = f"groq:{model}"

    def score(self, question: str, answer: str) -> Optional[float]:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": QUALITY_PROMPT.format(q=question, a=answer)}],
            temperature=0.0,
            max_tokens=8,
        )
        return _parse_score(resp.choices[0].message.content or "")


class OllamaJudge:
    name = "ollama"

    def __init__(self, model: str = "qwen2.5:7b-instruct", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host.rstrip("/")
        self.label = f"ollama:{model}"

    def score(self, question: str, answer: str) -> Optional[float]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": QUALITY_PROMPT.format(q=question, a=answer)}],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 8},
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read())
        return _parse_score(resp.get("message", {}).get("content", ""))


def build_judge(kind: str, model: Optional[str] = None):
    if kind == "groq":
        return GroqJudge(model or "llama-3.3-70b-versatile")
    if kind == "ollama":
        return OllamaJudge(model or "qwen2.5:7b-instruct")
    raise ValueError(f"unknown judge kind: {kind}")
