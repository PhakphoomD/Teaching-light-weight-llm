"""Generate the test inventory table in docs/HOW_TO_RUN.md.

The table names every test file, how many tests it holds, what it checks and
the command that runs only that file. Counting by hand would go stale on the
next commit, so the counts come from `pytest --collect-only` and the summaries
come from each module's own docstring.

    python scripts/make_test_inventory.py           # rewrite the table
    python scripts/make_test_inventory.py --check   # fail if it is out of date

The `--check` form is what the test suite calls, so a new test file that nobody
documented makes the suite red rather than leaving the table quietly wrong.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "HOW_TO_RUN.md"
BEGIN = "<!-- test-inventory:begin -->"
END = "<!-- test-inventory:end -->"

#: What each test file is *for*, in the reader's terms rather than the module's.
#: A file with no entry falls back to the first line of its docstring, so the
#: table is never blank -- but an entry here reads better and is the intent.
PURPOSE: Dict[str, str] = {
    "tests/test_scripts_load.py":
        "Every experiment driver under `scripts/` imports cleanly and has no unbound name",
    "tests/tlw/analysis/test_stats.py":
        "The statistics themselves: bootstrap intervals, Wilson intervals, exact McNemar, "
        "checked against `scipy` where an independent implementation exists",
    "tests/tlw/analysis/test_loaders.py":
        "Run discovery and parsing, including the guard that stops a pilot being pooled "
        "into a headline",
    "tests/tlw/analysis/test_report.py":
        "Report assembly: the per-arm table, the headline comparison, the honesty banner",
    "tests/tlw/analysis/test_rag_report.py":
        "The retrieval ablation report, which groups runs by whether retrieval was attached",
    "tests/tlw/analysis/test_cli.py":
        "The analysis command documented in this file actually runs and prints its banner",
    "tests/tlw/config/test_validation.py":
        "The eight validation rules a config must pass, including judge-family independence",
    "tests/tlw/config/test_loader.py":
        "Config layering: defaults, then the experiment file, then environment overrides",
    "tests/tlw/config/test_experiment_configs.py":
        "Every experiment file shipped in `experiments/` still loads and validates",
    "tests/tlw/evaluation/test_judge.py":
        "The blind judge: score parsing, edge cases, and the contract it must satisfy",
    "tests/tlw/evaluation/test_diagnostics.py":
        "Reference-match diagnostics, computed separately from correctness and never merged",
    "tests/tlw/evaluation/test_faithfulness.py":
        "The groundedness diagnostic, which sees retrieved passages but never the reference",
    "tests/tlw/evaluation/test_leakage.py":
        "Leakage seals on the evaluation path, including the judge-family rule",
    "tests/tlw/loop/test_leakage_seals.py":
        "The loop's leakage seals: no prompt bound for the student may carry the reference",
    "tests/tlw/loop/test_strategies.py":
        "The four arm strategies: who is asked what, and in which order",
    "tests/tlw/memory/test_tripwire.py":
        "The store-time tripwire's three rules, each on its own and in combination",
    "tests/tlw/memory/test_faiss_backend.py":
        "The note store: persistence, ranking, per-run isolation, and the red-team fixture "
        "of answer-seeded records it must reject every time",
    "tests/tlw/memory/test_rag_backend.py":
        "The retrieval backend and the run-time filter that drops a leaky passage",
    "tests/tlw/prompts/test_presets.py":
        "Prompt presets resolve correctly, and the two quarantined leaking templates refuse "
        "to load",
    "tests/tlw/runner/test_runner.py":
        "The composition root: a config becomes six wired blocks, with no model called",
    "tests/tlw/test_registries.py":
        "Slot registries resolve real implementations and fail loudly on an unknown name",
    "tests/tlw/wixqa/test_grounding.py":
        "The grounding window: how much of an article reaches the prompt, and from where",
    "tests/tlw/wixqa/test_prompts_and_retrieval.py":
        "The controlled variables of the retrieval study, and the pure retrieval helpers",
    "tests/tlw/figures/test_published_numbers.py":
        "Every published figure and table still equals what the documents claim -- point "
        "estimates, confidence intervals and counts alike",
    "tests/tools/rag/test_builder.py":
        "The index builder, whose held-out exclusion seals are the point of the test",
}

#: Reading order: the groups a reader would want, not alphabetical.
GROUPS: List[Tuple[str, str]] = [
    ("Statistics and analysis", "tests/tlw/analysis/"),
    ("Configuration", "tests/tlw/config/"),
    ("Evaluation and judging", "tests/tlw/evaluation/"),
    ("Leakage control", "tests/tlw/loop/|tests/tlw/memory/test_tripwire"),
    ("The loop and its memory", "tests/tlw/memory/|tests/tlw/prompts/"),
    ("The retrieval study", "tests/tlw/wixqa/|tests/tools/rag/"),
    ("Composition and registries", "tests/tlw/runner/|tests/tlw/test_registries"),
    ("Published numbers and drivers", "tests/tlw/figures/|tests/test_scripts_load"),
]


def collect() -> Dict[str, int]:
    """{test file: number of tests}, from pytest itself."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--collect-only",
         "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
    )
    counts: Dict[str, int] = {}
    for line in proc.stdout.splitlines():
        m = re.match(r"^(tests[^\s:]+\.py):\s*(\d+)\s*$", line.strip())
        if m:
            counts[m.group(1).replace("\\", "/")] = int(m.group(2))
    if not counts:
        raise SystemExit("pytest reported no tests; is the environment installed?\n"
                         + proc.stdout[-800:])
    return counts


def summary_for(path: str) -> str:
    if path in PURPOSE:
        return PURPOSE[path]
    try:
        doc = ast.get_docstring(ast.parse((ROOT / path).read_text(encoding="utf-8")))
    except (SyntaxError, OSError):
        doc = None
    return (doc or "").split("\n")[0].rstrip(".") or "--"


def render(counts: Dict[str, int]) -> str:
    used: set = set()
    out: List[str] = []
    for title, pattern in GROUPS:
        rows = [p for p in sorted(counts) if re.search(pattern, p) and p not in used]
        if not rows:
            continue
        used.update(rows)
        out.append(f"#### {title}\n")
        out.append("| tests | what it checks | run only this |")
        out.append("|---|---|---|")
        for p in rows:
            out.append(f"| {counts[p]} | {summary_for(p)} | `pytest {p} -q` |")
        out.append("")
    leftover = [p for p in sorted(counts) if p not in used]
    if leftover:
        out.append("#### Other\n")
        out.append("| tests | what it checks | run only this |")
        out.append("|---|---|---|")
        for p in leftover:
            out.append(f"| {counts[p]} | {summary_for(p)} | `pytest {p} -q` |")
        out.append("")
    out.append(f"**{sum(counts.values())} tests in {len(counts)} files.** "
               f"Regenerate this table with `python scripts/make_test_inventory.py`.")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if the table is out of date")
    args = ap.parse_args()

    if not DOC.is_file():
        raise SystemExit(f"{DOC.relative_to(ROOT)} does not exist")
    text = DOC.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise SystemExit(f"{DOC.relative_to(ROOT)} has no {BEGIN} / {END} markers")

    table = render(collect())
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    updated = f"{head}{BEGIN}\n\n{table}\n\n{END}{tail}"

    if args.check:
        if updated != text:
            raise SystemExit(
                "docs/HOW_TO_RUN.md is out of date. Run:\n"
                "  python scripts/make_test_inventory.py"
            )
        print("test inventory is up to date")
        return

    DOC.write_text(updated, encoding="utf-8")
    print(f"wrote the inventory into {DOC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
