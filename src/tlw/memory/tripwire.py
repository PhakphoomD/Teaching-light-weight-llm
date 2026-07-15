"""Store-time GT leakage tripwire (schema.md "Memory v2 contract" §2, ADR-018).

Pure functions, no I/O, no model loading — kept separate from `faiss_backend.py`
so the T-1/T-3 rules are unit-testable without a sentence-transformers encoder,
and T-2 takes a pre-computed similarity (the backend owns embedding).

Three independent checks, ANY of which rejects the write:
  T-1 substring / >=12-token shingle overlap (normalized text)
  T-2 cosine(embed(note), embed(reference)) >= gt_similarity_max
  T-3 length + token-overlap "smell" (catches reworded full answers that
      dodge T-1 but are still basically the reference)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

_WORD_RE = re.compile(r"[a-z0-9]+")


def normalize(text: str) -> str:
    """Lowercase, collapse whitespace/punctuation to single spaces."""
    if not text:
        return ""
    tokens = _WORD_RE.findall(text.lower())
    return " ".join(tokens)


def tokenize(text: str) -> Tuple[str, ...]:
    return tuple(_WORD_RE.findall((text or "").lower()))


def _shingles(tokens: Tuple[str, ...], n: int) -> set:
    if len(tokens) < n:
        return set()
    return {tokens[i : i + n] for i in range(len(tokens) - n + 1)}


def check_t1_substring(note: str, reference: str, shingle_n: int = 12) -> bool:
    """True = REJECT. Normalized reference is a substring of the note, OR any
    contiguous >=shingle_n-token run of the reference appears in the note."""
    if not reference:
        return False
    norm_note = normalize(note)
    norm_ref = normalize(reference)
    if not norm_ref:
        return False
    if norm_ref in norm_note:
        return True
    note_tokens = tuple(norm_note.split())
    ref_tokens = tuple(norm_ref.split())
    if len(ref_tokens) < shingle_n:
        return False
    note_shingles = _shingles(note_tokens, shingle_n)
    ref_shingles = _shingles(ref_tokens, shingle_n)
    return bool(note_shingles & ref_shingles)


def check_t2_similarity(cosine_sim: float, gt_similarity_max: float = 0.80) -> bool:
    """True = REJECT. Caller computes cosine(embed(note), embed(reference))."""
    return cosine_sim >= gt_similarity_max


def check_t3_length_overlap(note: str, reference: str) -> bool:
    """True = REJECT. note is >=0.60*len(reference) tokens AND >=0.90 token
    overlap with reference — catches lightly-reworded full answers."""
    if not reference:
        return False
    note_tokens = tokenize(note)
    ref_tokens = tokenize(reference)
    if not ref_tokens or not note_tokens:
        return False
    if len(note_tokens) < 0.60 * len(ref_tokens):
        return False
    ref_set = set(ref_tokens)
    overlap = len(set(note_tokens) & ref_set) / len(ref_set)
    return overlap >= 0.90


@dataclass(frozen=True)
class TripwireResult:
    rejected: bool
    reason: Optional[str] = None  # "T-1" | "T-2" | "T-3" | None


def run_tripwire(
    note: str,
    reference: Optional[str],
    cosine_sim: Optional[float],
    *,
    gt_substring_shingle: int = 12,
    gt_similarity_max: float = 0.80,
) -> TripwireResult:
    """Run T-1/T-2/T-3 in order; short-circuits on first hit.

    `reference` may be None (no GT available at this call site) — then the
    tripwire is a no-op pass (nothing to check against), matching the
    contract's "GT never enters store()" preferred design for the headline
    no-memory arms and any caller that legitimately has no reference.
    """
    if not reference:
        return TripwireResult(rejected=False)
    if check_t1_substring(note, reference, shingle_n=gt_substring_shingle):
        return TripwireResult(rejected=True, reason="T-1")
    if cosine_sim is not None and check_t2_similarity(cosine_sim, gt_similarity_max):
        return TripwireResult(rejected=True, reason="T-2")
    if check_t3_length_overlap(note, reference):
        return TripwireResult(rejected=True, reason="T-3")
    return TripwireResult(rejected=False)
