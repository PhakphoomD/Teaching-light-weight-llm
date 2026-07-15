"""reference_match diagnostics (T2.3) — EVAL_SPEC.md §2.

`reference_match` is a DIAGNOSTIC column, never the pass/fail decision
(that is `correctness`, judge.py's BlindJudge). It exists only to expose
the old confound named in EVAL_SPEC §2: if an arm raises reference_match
without raising correctness, it learned to mimic the reference's wording,
not to be more correct. No weight, no threshold, never merged (ADR-019).

Computed AFTER the judge verdict, from separate call sites, into separate
fields — callers must not fold this into `correctness`/`passed`.

Primitives (normalize/tokenize/ROUGE-L LCS/MiniLM cosine) are reworked here
from src/eval/metrics.py (read-only salvage per T2.3 spec) so this package
has zero import dependency on legacy/other src/ evaluation code.
"""

import re
from typing import Any, Dict, List, Optional

_PUNCT_RE = re.compile(r"[^\w\s]")

_DEFAULT_ENCODER_NAME = "all-MiniLM-L6-v2"
_encoder_cache: Dict[str, Any] = {}


def normalize_text(text: Optional[str]) -> str:
    if text is None:
        return ""
    text = str(text).lower()
    text = _PUNCT_RE.sub("", text)
    return " ".join(text.split())


def tokenize(text: Optional[str]) -> List[str]:
    return normalize_text(text).split()


def rouge_l(answer: str, reference_answer: str) -> float:
    """ROUGE-L recall (LCS-based), reworked from src/eval/metrics.py:368-390."""
    pred_tokens = tokenize(answer)
    ref_tokens = tokenize(reference_answer)
    if not pred_tokens or not ref_tokens:
        return 0.0

    m, n = len(pred_tokens), len(ref_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if pred_tokens[i - 1] == ref_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs_len = dp[m][n]
    return lcs_len / n if n > 0 else 0.0


def get_default_encoder():
    """Lazy-load + cache a SentenceTransformer encoder (module-level cache so
    repeated diagnostic calls in one process don't reload the model)."""
    if _DEFAULT_ENCODER_NAME not in _encoder_cache:
        from sentence_transformers import SentenceTransformer

        _encoder_cache[_DEFAULT_ENCODER_NAME] = SentenceTransformer(_DEFAULT_ENCODER_NAME)
    return _encoder_cache[_DEFAULT_ENCODER_NAME]


def semantic_similarity(answer: str, reference_answer: str, encoder: Optional[Any] = None) -> float:
    """Cosine similarity between MiniLM embeddings, reworked from
    src/eval/metrics.py:138-190. Returns 0.0 if sentence-transformers is
    unavailable rather than raising (diagnostics must not crash a run)."""
    try:
        import numpy as np

        enc = encoder if encoder is not None else get_default_encoder()
        pred_emb = enc.encode([answer], convert_to_numpy=True)[0]
        ref_emb = enc.encode([reference_answer], convert_to_numpy=True)[0]
        denom = float(np.linalg.norm(pred_emb) * np.linalg.norm(ref_emb))
        if denom == 0.0:
            return 0.0
        cos_sim = float(np.dot(pred_emb, ref_emb) / denom)
        return max(0.0, min(1.0, cos_sim))
    except ImportError:
        return 0.0
    except Exception:
        return 0.0


def reference_match(answer: str, reference_answer: str, encoder: Optional[Any] = None) -> Dict[str, float]:
    """The two-field diagnostic (EVAL_SPEC §2 table): semantic_sim + rouge_l
    vs the reference answer. NOT a pass/fail signal, NOT weighted into
    correctness. Callers log these as separate columns on the per-round
    record, alongside (never combined with) the judge's `correctness`."""
    return {
        "semantic_sim": semantic_similarity(answer, reference_answer, encoder=encoder),
        "rouge_l": rouge_l(answer, reference_answer),
    }
