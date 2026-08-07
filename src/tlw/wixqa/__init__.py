"""WixQA study library — the shared pieces of the P3-E experiments.

These four modules used to live inside `scripts/wixqa_*.py` and were imported
script-to-script (15 edges). That made the experiment drivers load-bearing
library code: renaming or reorganising a driver could silently change what a
different experiment measured. ADR-034 §A4 says the dependency arrow points one
way — `scripts/` → `src/`, never sideways — so the shared logic lives here and
the scripts are thin drivers again.

| module | what it owns |
|---|---|
| `paths`     | where the WixQA data and its index live |
| `prompts`   | the exact student/judge prompts and decoding settings of ADR-030 |
| `retrieval` | encoders, chunking, and the seven retriever variants of the T3.10 ladder |
| `grounding` | how much of a retrieved article reaches the prompt (T3.14 Stage 1) |

**Nothing here may change behaviour.** The prompts, the chunk size, the encoder
prefixes and the decoding parameters are the controlled variables of published
results (ADR-030…033); a change to any of them invalidates a comparison. If a
new experiment needs different values, add them alongside — do not edit these.
"""

from .paths import KB_PATH, QA_PATH, WIXQA_INDEX
from .prompts import (
    BASELINE_SYS,
    JUDGE_SYS,
    MAX_PASSAGE_CHARS,
    MAX_TOKENS,
    RAG_SYS,
    TEMPERATURE,
    judge_score,
)

__all__ = [
    "KB_PATH", "QA_PATH", "WIXQA_INDEX",
    "BASELINE_SYS", "RAG_SYS", "JUDGE_SYS",
    "TEMPERATURE", "MAX_TOKENS", "MAX_PASSAGE_CHARS",
    "judge_score",
]
