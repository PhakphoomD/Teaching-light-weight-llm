"""Shared mocks for loop-block tests — no API calls anywhere.

MockClient/MockJudge/MockMemory stand in for the LLMClient (src/core/client.py)
and Judge (registries.py) seams so arm-strategy tests exercise real call
patterns and real prompt text without touching a network.
"""

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest


class MockClient:
    """Stands in for an LLMClient. Returns queued responses in order;
    records every call (messages + decoding params) for assertions."""

    def __init__(self, responses: Optional[List[str]] = None):
        self._responses = list(responses or [])
        self.calls: List[Dict[str, Any]] = []

    def chat(self, messages, temperature=0.0, max_tokens=256, timeout_s=60):
        self.calls.append(
            {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        )
        text = self._responses.pop(0) if self._responses else ""
        return SimpleNamespace(text=text, error=None)

    @property
    def prompts(self) -> List[str]:
        """Convenience: the user-content string sent on each call, in order."""
        return [c["messages"][0]["content"] for c in self.calls]


class MockJudge:
    """Stands in for the Judge seam. Returns queued verdicts in order."""

    def __init__(self, verdicts: Optional[List[Dict[str, Any]]] = None):
        self._verdicts = list(verdicts or [])
        self.calls: List[Dict[str, Any]] = []

    def score(self, question, answer, mode):
        self.calls.append({"question": question, "answer": answer, "mode": mode})
        if self._verdicts:
            return self._verdicts.pop(0)
        return {"score": 0, "normalized_score": 0.0, "passed": False}


class MockMemory:
    """Stands in for a MemoryBackend. Records store()/retrieve() calls."""

    def __init__(self, retrieve_returns: Optional[List[Dict[str, Any]]] = None):
        self._retrieve_returns = retrieve_returns or []
        self.store_calls: List[Dict[str, Any]] = []
        self.retrieve_calls: List[Dict[str, Any]] = []

    def store(self, episode, reference_answer=None):
        self.store_calls.append({"episode": episode, "reference_answer": reference_answer})
        return "mock-id"

    def retrieve(self, query, top_k):
        self.retrieve_calls.append({"query": query, "top_k": top_k})
        return self._retrieve_returns

    def update_outcome(self, episode_id, scores):
        return None

    def stats(self):
        return {"total_episodes": 0, "total_attempts": 0, "overall_success_rate": 0.0, "index_size": 0, "rejects": 0}


PASS = {"score": 4, "normalized_score": 1.0, "passed": True}
FAIL = {"score": 1, "normalized_score": 0.25, "passed": False}


@pytest.fixture
def make_client():
    return MockClient


@pytest.fixture
def make_judge():
    return MockJudge


@pytest.fixture
def make_memory():
    return MockMemory
