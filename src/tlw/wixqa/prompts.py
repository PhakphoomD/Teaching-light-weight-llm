"""The exact prompts and decoding settings of the WixQA study.

**These are controlled variables, not defaults.** Every WixQA number published in
`docs/EXPERIMENT_RESULTS.md §7.4-7.6` and `docs/RAG_LAW.md` was produced with these strings and
these values; the only variable that ever changed across those runs was the one
the experiment was testing (the seed, the retriever, or the grounding window).
Editing anything here retroactively invalidates the comparison between runs.

Originally duplicated across `scripts/wixqa_{baseline,rag,run3seed}.py`, which is
how drift becomes possible in the first place.
"""

from __future__ import annotations

import re
from typing import Optional

# --- student prompts ---------------------------------------------------------

#: No retrieval: the model answers from parametric knowledge alone (ADR-030 baseline).
BASELINE_SYS = (
    "You are a helpful Wix customer-support assistant. "
    "Answer the user's question concisely and accurately."
)

#: With retrieval. Note "if the context is relevant" — the model is invited to
#: ignore unhelpful passages, which matters because ~45% of retrievals miss the
#: gold article and a hard "use the context" instruction backfired on MedQuAD
#: (ADR-027: a hardened grounding prompt dropped the pass rate 0.80 -> 0.56).
RAG_SYS = (
    "You are a helpful Wix customer-support assistant. Use the REFERENCE CONTEXT below "
    "(help-center articles) to answer the question accurately and concisely. "
    "If the context is relevant, ground your answer in it."
)

# --- decoding ----------------------------------------------------------------

TEMPERATURE = 0.3          #: student sampling temperature, fixed across every WixQA run
MAX_TOKENS = 256           #: student answer cap
MAX_PASSAGE_CHARS = 900    #: the ORIGINAL per-article grounding budget (ADR-030 / T3.11).
#: Kept because it defines the `head900` control arm. T3.14 Stage 1 showed it
#: truncates 92.5% of gold articles; the winning `chunk2400` variant lives in
#: `grounding.py`. Do not "fix" this constant — it is a measured baseline.

# --- judge -------------------------------------------------------------------

#: Reference-comparing judge (§0.2-legal for a closed domain: only the JUDGE sees
#: the gold answer; the student is always blind). A blind judge cannot verify
#: proprietary product facts, which is why WixQA uses this mode and MedQuAD does not.
JUDGE_SYS = (
    "You are a strict QA grader for a website-builder (Wix) customer-support assistant. "
    "You are given a QUESTION, the REFERENCE answer (ground truth), and a CANDIDATE answer. "
    "Rate how well the CANDIDATE matches the factual content of the REFERENCE on a 0-4 scale:\n"
    "4 = fully correct AND complete (all key facts from the reference present, none wrong)\n"
    "3 = correct but missing a minor detail\n"
    "2 = partially correct but missing a key fact or slightly wrong\n"
    "1 = mostly wrong or generic non-answer\n"
    "0 = wrong or refuses\n"
    "Judge ONLY against the reference (it is the truth for this product). "
    "Reply with ONLY the single digit."
)

_DIGIT = re.compile(r"[0-4]")


def judge_score(judge, question: str, reference: str, candidate: str) -> Optional[int]:
    """Score one answer 0-4. Returns None when the judge produced no digit.

    Temperature 0 and an 8-token cap: this is a classification call, not a
    generation, and the caller pools thousands of them under a shared daily quota.
    """
    messages = [
        {"role": "system", "content": JUDGE_SYS},
        {
            "role": "user",
            "content": (
                f"QUESTION:\n{question}\n\nREFERENCE:\n{reference}\n\n"
                f"CANDIDATE:\n{candidate}\n\nScore (0-4):"
            ),
        },
    ]
    result = judge.chat(messages, temperature=0.0, max_tokens=8, timeout_s=60)
    match = _DIGIT.search(result.text or "")
    return int(match.group()) if match else None


__all__ = [
    "BASELINE_SYS", "RAG_SYS", "JUDGE_SYS",
    "TEMPERATURE", "MAX_TOKENS", "MAX_PASSAGE_CHARS",
    "judge_score",
]
