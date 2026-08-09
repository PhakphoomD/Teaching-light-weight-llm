"""Write the committable half of every run's per-round log.

`rounds.jsonl` carries the generated text — the question, the answer, the
teacher's feedback, the grounding block. That is 15 MB across the project and it
is not what any published number is computed from. What the analysis actually
reads is the scoring: which question, which round, what the judge scored, whether
it passed, and the diagnostic columns beside it.

This script writes that half to `rounds-analysis.jsonl` beside each
`rounds.jsonl`, which is the file `.gitignore` tracks. The result is 2.2 MB —
small enough to commit, complete enough that every interval, every McNemar and
every figure recomputes from a fresh clone.

Why this exists: without it, `runs/**` was gitignored except three metadata
files, so a clone carried per-arm pass rates and nothing else. Every paired
statistic silently reported "cannot pair", `scripts/make_figures.py` crashed on
its first figure, and 35 tests failed — while the README promised that every
number recomputes from a committed log. That promise is what this file makes
true.

Run after any experiment, or to rebuild the whole set:

    python scripts/export_analysis_rows.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]

#: Fields carrying generated or source text. Dropped — large, and no published
#: number reads them. Everything else is kept, so a new diagnostic column
#: survives this script without anyone remembering to add it.
#:
#: `reference` is the expert answer on the WixQA side. It is dropped for size,
#: not for secrecy — it is published in the WixQA dataset — but dropping it also
#: means the committed evidence cannot be mistaken for an answer key.
TEXT_FIELDS = frozenset(
    {"question", "answer", "feedback", "grounding_context", "reference"}
)

ANALYSIS_NAME = "rounds-analysis.jsonl"

#: The two run shapes in this repository. The framework runner writes one
#: `rounds.jsonl` per run directory; the WixQA scripts write one file per seed.
#: Both are per-question scoring records and both are exported the same way.
SOURCE_PATTERNS = ("rounds.jsonl", "seed*.jsonl")


def analysis_row(row: Dict) -> Dict:
    """One round, with the generated text removed and nothing else touched."""
    return {k: v for k, v in row.items() if k not in TEXT_FIELDS}


def export_file(source: Path) -> tuple[int, int]:
    """Write the analysis-only twin of one per-round log. Returns (rows, bytes).

    `rounds.jsonl` -> `rounds-analysis.jsonl`;  `seed13.jsonl` ->
    `seed13-analysis.jsonl`. The name is derived so the pairing is visible in a
    directory listing.
    """
    if source.name == "rounds.jsonl":
        target = source.with_name(ANALYSIS_NAME)
    else:
        target = source.with_name(f"{source.stem}-analysis.jsonl")

    rows: List[str] = []
    with open(source, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rows.append(json.dumps(analysis_row(json.loads(line)), separators=(",", ":")))
    payload = "\n".join(rows) + ("\n" if rows else "")
    target.write_text(payload, encoding="utf-8")
    return len(rows), len(payload.encode("utf-8"))


def discover(runs_root: Path) -> Iterable[Path]:
    """Every per-round log, excluding the analysis twins this script writes."""
    found: List[Path] = []
    for pattern in SOURCE_PATTERNS:
        found.extend(p for p in runs_root.rglob(pattern) if "-analysis" not in p.name)
    return sorted(set(found))


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--runs-dir", default=str(ROOT / "runs"))
    args = parser.parse_args(argv)

    runs_root = Path(args.runs_dir)
    if not runs_root.is_dir():
        print(f"no such directory: {runs_root}", file=sys.stderr)
        return 1

    sources = list(discover(runs_root))
    if not sources:
        print(f"no per-round log found under {runs_root} — nothing to export", file=sys.stderr)
        return 1

    total_rows = total_bytes = 0
    for source in sources:
        rows, size = export_file(source)
        total_rows += rows
        total_bytes += size

    print(f"{len(sources)} logs · {total_rows:,} rows · {total_bytes / 1048576:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
