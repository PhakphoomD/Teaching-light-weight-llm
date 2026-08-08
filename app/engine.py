"""Demo engine — the retrieval + grounding + answer core of the WixQA RAG demo (T3.15).

Pure Python (no UI): it can be smoke-tested, and it is what `app/build_showcase.py`
reuses to capture the before/after comparison examples that become a portfolio TABLE.
(A Streamlit UI was prototyped and removed — it read as generic and the portfolio's
value is the honest results, not a chat box; the engine's captured comparison DATA is
what the narrative uses.)

Everything here REUSES the study library (`src/tlw/wixqa`) so the demo answers with
the exact prompts, decoding and grounding of the published results — a demo that
drifted from the paper would be dishonest (§0.1). What the demo adds is the ability
to run one question three ways side by side, which is how it re-demonstrates the
findings live:

  * no-RAG   vs  RAG               -> the +0.152 knowledge lift (ADR-030)
  * narrow (head900) vs wide (chunk2400) grounding -> the +0.130 delivery lever (ADR-033)
  * RAG      vs  RAG + self-refine -> self-refine does not compound (ADR-032; directional)

Retriever note: the demo uses the committed MiniLM index (`indexes/wixqa-help-centre/`,
the ADR-030 retriever, hit-rate 0.55) for instant startup. The published *winner* is
`bge_chunk` (0.665), but the delivery lever shown here is retriever-independent — it is
about how much of a retrieved article reaches the prompt, not which retriever found it.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# MiniLM is cached locally; without this the first encode stalls ~60s trying to
# reach huggingface.co (see memory: hf-offline-embedding-stall).
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import json

import faiss
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

from src.tlw.wixqa.grounding import window  # chunk-centred window renderer
from src.tlw.wixqa.prompts import BASELINE_SYS, MAX_TOKENS, RAG_SYS, TEMPERATURE
from src.tlw.wixqa.retrieval import chunks_of
from tools.dataset.embeddings import embed  # MiniLM encoder used to build the index

INDEX_DIR = ROOT / "indexes" / "wixqa-help-centre"
STRIDE = 180 - 40  # CHUNK_WORDS - OVERLAP, matching retrieval.chunks_of

#: Grounding modes the demo exposes. head900 = the ADR-030 baseline (truncates
#: 92.5% of gold articles); chunk2400 = the ADR-033 delivery fix (the winner).
GROUNDING_MODES = {
    "none": None,
    "narrow": (900, False),      # head900
    "wide": (2400, True),        # chunk2400 (chunk-centred)
}

REFINE_CRITIQUE_SYS = (
    "You are reviewing your own draft answer to a Wix support question. "
    "Using ONLY the reference context, list in one or two sentences what key facts "
    "from the context are missing or wrong in the draft. Do not rewrite the answer."
)


@dataclass
class Hit:
    id: str
    title: str
    text: str
    sim: float


@dataclass
class Answer:
    text: str
    latency_s: float
    tokens: Optional[int]
    grounding: str
    sources: List[Hit] = field(default_factory=list)
    refined: bool = False


class DemoEngine:
    """Loads the committed index once; answers arbitrary questions three ways."""

    def __init__(self, model: str = "qwen2.5:3b"):
        import src.tlw.providers  # noqa: F401 — registers the Ollama client under "local"
        from src.providers.factory import build_client

        self.index = faiss.read_index(str(INDEX_DIR / "faiss.index"))
        self.passages = [
            json.loads(l) for l in (INDEX_DIR / "passages.jsonl").open(encoding="utf-8")
        ]
        self.student = build_client("local", model=model)
        self.model = model

    # -- retrieval -----------------------------------------------------------
    def retrieve(self, question: str, top_k: int = 3) -> List[Hit]:
        qv = np.asarray(embed([question]), dtype="float32")
        faiss.normalize_L2(qv)
        sims, idxs = self.index.search(qv, top_k)
        hits: List[Hit] = []
        for j, s in zip(idxs[0], sims[0]):
            if j < 0:
                continue
            p = self.passages[j]
            hits.append(Hit(id=p["id"], title=p.get("title", ""),
                            text=p.get("passage", ""), sim=round(float(s), 3)))
        return hits

    def hit_gold(self, hits: List[Hit], gold_ids: List[str]) -> bool:
        return bool(set(h.id for h in hits) & set(gold_ids))

    # -- grounding -----------------------------------------------------------
    def _chunk_centre_offset(self, hit: Hit, qv: np.ndarray) -> int:
        """Word offset of the article chunk that best matches the question.

        Uses the demo's own encoder (MiniLM) so no second encoder is loaded; this
        is what makes the `wide` window *chunk-centred* rather than article-head.
        """
        art = {"title": hit.title, "contents": hit.text}
        chs = chunks_of(art)
        if len(chs) <= 1:
            return 0
        cv = np.asarray(embed(chs), dtype="float32")
        cv /= (np.linalg.norm(cv, axis=1, keepdims=True) + 1e-9)
        return int(np.argmax(cv @ qv[0])) * STRIDE

    def ground(self, question: str, hits: List[Hit], mode: str) -> str:
        """Build the REFERENCE CONTEXT block for a grounding mode ('narrow'|'wide')."""
        budget, centred = GROUNDING_MODES[mode]
        qv = None
        if centred:
            qv = np.asarray(embed([question]), dtype="float32")
            faiss.normalize_L2(qv)
        parts = []
        for k, h in enumerate(hits, start=1):
            art = {"title": h.title, "contents": h.text}
            centre = self._chunk_centre_offset(h, qv) if centred else None
            parts.append(f"[{k}] {h.title}\n{window(art, budget, centre)}")
        return "\n\n".join(parts)

    # -- generation ----------------------------------------------------------
    def _chat(self, system: str, user: str) -> Answer:
        t0 = time.time()
        resp = self.student.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=TEMPERATURE, max_tokens=MAX_TOKENS, timeout_s=60,
        )
        dt = time.time() - t0
        usage = getattr(resp, "usage", None)
        tokens = getattr(usage, "total_tokens", None) if usage else None
        return Answer(text=(resp.text or "").strip(), latency_s=round(dt, 2),
                      tokens=tokens, grounding="")

    def answer(self, question: str, hits: Optional[List[Hit]], grounding: str,
               refine: bool = False) -> Answer:
        """Answer one question in one configuration.

        grounding='none' -> no RAG (parametric only). Otherwise ground on `hits`
        with the given mode. `refine` runs one blind self-critique + rewrite round,
        keeping the grounding in context (ADR-032: honest, rarely helps).
        """
        if grounding == "none" or not hits:
            ans = self._chat(BASELINE_SYS, f"QUESTION: {question}")
            ans.grounding = "none"
            return ans

        block = self.ground(question, hits, grounding)
        user = f"REFERENCE CONTEXT:\n{block}\n\nQUESTION: {question}"
        ans = self._chat(RAG_SYS, user)
        ans.grounding, ans.sources = grounding, hits

        if refine:
            crit = self._chat(REFINE_CRITIQUE_SYS,
                              f"REFERENCE CONTEXT:\n{block}\n\nQUESTION: {question}\n\nDRAFT: {ans.text}")
            rewrite = self._chat(
                RAG_SYS,
                f"REFERENCE CONTEXT:\n{block}\n\nQUESTION: {question}\n\n"
                f"Your draft: {ans.text}\nMissing/wrong: {crit.text}\n\nWrite the improved answer:")
            rewrite.grounding, rewrite.sources, rewrite.refined = grounding, hits, True
            rewrite.latency_s = round(ans.latency_s + crit.latency_s + rewrite.latency_s, 2)
            return rewrite
        return ans

    # -- the compare view (what the UI and showcase both use) ----------------
    def compare(self, question: str, top_k: int = 3, refine: bool = False,
                gold_ids: Optional[List[str]] = None) -> Dict:
        """Run one question the ways the narrative needs, side by side."""
        hits = self.retrieve(question, top_k)
        lanes = {
            "no_rag": self.answer(question, None, "none"),
            "rag_narrow": self.answer(question, hits, "narrow"),
            "rag_wide": self.answer(question, hits, "wide"),
        }
        if refine:
            lanes["rag_wide_refine"] = self.answer(question, hits, "wide", refine=True)
        return {
            "question": question,
            "gold_retrieved": self.hit_gold(hits, gold_ids) if gold_ids is not None else None,
            "sources": [h.__dict__ for h in hits],
            "lanes": {k: v.text for k, v in lanes.items()},
            "latency_s": {k: v.latency_s for k, v in lanes.items()},
        }
