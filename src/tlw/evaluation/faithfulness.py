"""FaithfulnessJudge (rag-medquad-protocol §4.2) — the RAG groundedness DIAGNOSTIC.

RAGAS-style groundedness (Es et al. 2023, arXiv 2309.15217): given an ANSWER and
the retrieved CONTEXT passages, what fraction of the answer's factual claims are
SUPPORTED by the context? `faithfulness = supported / total`.

§0.2-safe by construction: `score()` takes only (answer, passages) — the held-out
gold answer is NEVER a parameter, so it cannot reach this prompt (grep-proof: no
`ground_truth` identifier in this file). This is a NEW judge, NOT the deliberately
-unbuilt `gt_comparing` mode (registries.py) — it compares the answer to the
non-gold TRAIN passages, never to the reference.

DIAGNOSTIC ONLY (ADR-019 / rag-medquad-protocol §4): faithfulness is reported as its own
column beside blind correctness and reference_match, and NEVER enters the
pass/fail decision. A faithful-but-wrong answer must still FAIL on correctness.
"""

import json
import re
from typing import Any, Dict, List, Optional, Union

from src.providers.factory import build_client

FAITHFULNESS_PROMPT = """You are checking whether an ANSWER is grounded in the given CONTEXT passages.
Break the ANSWER into its distinct factual claims. For each claim decide whether it is
SUPPORTED by the CONTEXT (directly stated in, or clearly inferable from, the passages) or NOT.
Do NOT use outside knowledge, and do NOT judge whether the answer is correct — judge ONLY
whether the CONTEXT supports each claim.

CONTEXT:
{context}

ANSWER:
{answer}

Output STRICT JSON on one line: {{"supported": <int>, "total": <int>}}"""

_SUPPORTED_RE = re.compile(r'"supported"\s*:\s*(\d+)')
_TOTAL_RE = re.compile(r'"total"\s*:\s*(\d+)')


def parse_faithfulness(text: Optional[str]) -> Dict[str, Any]:
    """Parse a judge reply into {supported, total, faithfulness}. Unparseable or
    total<=0 -> faithfulness=None (null; excluded from the mean, null-rate reported)."""
    if not text or not text.strip():
        return {"supported": None, "total": None, "faithfulness": None}
    stripped = text.strip()

    supported = total = None
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            supported = obj.get("supported")
            total = obj.get("total")
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    if not isinstance(supported, int):
        m = _SUPPORTED_RE.search(stripped)
        supported = int(m.group(1)) if m else None
    if not isinstance(total, int):
        m = _TOTAL_RE.search(stripped)
        total = int(m.group(1)) if m else None

    if not isinstance(supported, int) or not isinstance(total, int) or total <= 0:
        return {"supported": supported, "total": total, "faithfulness": None}
    supported = max(0, min(supported, total))  # clamp to [0, total]
    return {"supported": supported, "total": total, "faithfulness": supported / total}


def _context_to_text(passages: Union[str, List[Any], None]) -> str:
    if not passages:
        return ""
    if isinstance(passages, str):
        return passages
    parts: List[str] = []
    for i, p in enumerate(passages, start=1):
        text = p if isinstance(p, str) else (p.get("passage") if isinstance(p, dict) else str(p))
        if text:
            parts.append(f"[{i}] {text}")
    return "\n".join(parts)


class FaithfulnessJudge:
    """Independent groundedness judge. Reuses a judge client (DI or built from
    provider/model). Same model family constraints do not apply (it never sees
    the student answer's gold, only passages) but reusing the the teaching-loop study judge
    keeps one consistent evaluator."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 256,
        timeout: int = 60,
        client: Optional[Any] = None,
    ):
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        if client is not None:
            self._client = client
        elif provider is not None and model is not None:
            self._client = build_client(provider, model=model)
        else:
            self._client = None

    def score(self, answer: str, passages: Union[str, List[Any], None]) -> Dict[str, Any]:
        """Groundedness of `answer` vs `passages`. No gold answer involved (§0.2)."""
        if self._client is None:
            raise RuntimeError("FaithfulnessJudge has no client — pass provider+model or client=")
        context = _context_to_text(passages)
        if not context.strip():
            # No passages -> groundedness is undefined (the answer was un-grounded).
            return {"supported": None, "total": None, "faithfulness": None, "null": True, "raw_response": ""}

        prompt = FAITHFULNESS_PROMPT.format(context=context, answer=answer or "")
        response = self._client.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout_s=self.timeout,
        )
        error = getattr(response, "error", None)
        raw = "" if error else (getattr(response, "text", "") or "")
        parsed = parse_faithfulness(raw)
        parsed["null"] = parsed["faithfulness"] is None
        parsed["raw_response"] = raw
        parsed["error"] = error
        return parsed
