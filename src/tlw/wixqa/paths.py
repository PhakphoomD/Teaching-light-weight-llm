"""Where the WixQA study's inputs live (ADR-034 layout).

Third-party data sits under `data/external/` with a fetch script beside it; the
search index it produces is a build artifact and lives under `indexes/`. Both are
gitignored, so a clone re-acquires them rather than downloading them from history.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

#: The 6,221 Wix help-centre articles — the legitimate knowledge source.
KB_PATH = PROJECT_ROOT / "data" / "external" / "wixqa" / "kb_corpus.jsonl"

#: The 200 expert-written question/answer pairs. Only the JUDGE ever sees these
#: answers; indexing them would make the whole study a leakage exercise.
QA_PATH = PROJECT_ROOT / "data" / "external" / "wixqa" / "expertwritten.jsonl"

#: The FAISS index built from the KB (never from the QA answers).
WIXQA_INDEX = PROJECT_ROOT / "indexes" / "wixqa-help-centre"

__all__ = ["PROJECT_ROOT", "KB_PATH", "QA_PATH", "WIXQA_INDEX"]
