"""
Embedding utilities for Stage 2 readiness dimensions (D3 near-dup, D6 diversity,
D7 answerability) + general reuse. Uses all-MiniLM-L6-v2 (already a project dep).
Loaded once (lazy singleton).
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

_MODEL = None


def get_model(name: str = "all-MiniLM-L6-v2"):
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(name)
    return _MODEL


def embed(texts: Sequence[str]) -> np.ndarray:
    """L2-normalized embeddings, shape (n, d)."""
    vecs = get_model().encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vecs, dtype=np.float32)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # inputs already normalized


def relevance(question: str, answer: str) -> float:
    v = embed([question, answer])
    return cosine(v[0], v[1])


def near_dup_rate(answers: List[str], threshold: float = 0.90) -> float:
    """Fraction of answers that are a near-duplicate (cos>=threshold) of an earlier one."""
    if len(answers) < 2:
        return 0.0
    V = embed(answers)
    dup = 0
    kept: List[int] = []
    for i in range(len(V)):
        if any(cosine(V[i], V[j]) >= threshold for j in kept):
            dup += 1
        else:
            kept.append(i)
    return round(dup / len(answers), 4)


def diversity_score(texts: List[str], sample: int = 400) -> float:
    """0–100. Mean pairwise cosine distance over a sample (higher = more diverse)."""
    if len(texts) < 2:
        return 0.0
    idx = np.linspace(0, len(texts) - 1, min(sample, len(texts))).astype(int)
    V = embed([texts[i] for i in idx])
    sims = V @ V.T
    n = len(V)
    off = (sims.sum() - np.trace(sims)) / (n * (n - 1))
    return round(float((1 - off) * 100), 1)
