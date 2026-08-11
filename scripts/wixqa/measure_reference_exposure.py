"""Separate the grounding-window effect from reference exposure.

On the support-documentation testbed the judge scores by comparison against an
expert answer, and the knowledge-base articles those answers were written from
are indexed deliberately and never scrubbed. Widening the grounding window
therefore does two things at once: it shows the model more of the material it
needs, and it shows the model more of the text it is graded against. The
published effect cannot be attributed to the first until the second is measured.

This script separates them. For every question it rebuilds both grounding
blocks — the narrow window of the earlier rung and the wide window of the
winner — measures how much of the expert answer appears verbatim in each using
the twelve-token criterion the leakage guard uses elsewhere, and splits the
questions by whether the wide window revealed any *new* reference text. The
effect measured on the questions where it revealed none is the part of the
result that exposure cannot explain.

Deterministic and offline. Retrieval is read from the committed run logs rather
than re-run, so the blocks are the ones the model actually saw, and the only
model loaded is the sentence encoder that locates the matched chunk.

    python scripts/wixqa/measure_reference_exposure.py

Writes reports/rag-wixqa/reference-exposure-strata.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.tlw.analysis.stats import (  # noqa: E402
    exact_mcnemar,
    paired_cluster_bootstrap,
    wilson_interval,
)
from src.tlw.evaluation.diagnostics import normalize_text  # noqa: E402
from src.tlw.loop.core import _MIN_SHINGLE_TOKENS  # noqa: E402
from src.tlw.wixqa.grounding import GROUNDINGS, best_chunk_word_offset, window  # noqa: E402
from src.tlw.wixqa.retrieval import encode, load_data  # noqa: E402

NARROW, WIDE = "head900", "chunk2400"
STEP_NARROW = "3-rag-better-retriever"
STEP_WIDE = "4-rag-wider-context"
BAR = 3
OUT = ROOT / "reports" / "rag-wixqa" / "reference-exposure-strata.json"


def tokens(text: str) -> List[str]:
    return normalize_text(text).split()


def verbatim_run_tokens(answer: str, block: str) -> int:
    """Longest contiguous run of answer tokens appearing in `block`.

    The unit is the project's own leak criterion: `assert_gt_free` aborts a run
    when a prompt shares this many contiguous tokens with the reference.
    """
    a, b = tokens(answer), tokens(block)
    if not a or not b:
        return 0
    index: Dict[str, List[int]] = {}
    for i, tok in enumerate(b):
        index.setdefault(tok, []).append(i)
    best, prev = 0, {}
    for tok in a:
        cur: Dict[int, int] = {}
        for j in index.get(tok, ()):
            run = prev.get(j - 1, 0) + 1
            cur[j] = run
            best = max(best, run)
        prev = cur
    return best


def verbatim_share(answer: str, block: str, size: int = _MIN_SHINGLE_TOKENS) -> float:
    """Share of the answer's n-token shingles that appear verbatim in `block`.

    A continuous companion to the binary criterion: "how much of the graded text
    is sitting in front of the model", not merely "is any of it".
    """
    a, b = tokens(answer), tokens(block)
    if len(a) < size:
        return 0.0
    haystack = " ".join(b)
    shingles = [" ".join(a[i : i + size]) for i in range(len(a) - size + 1)]
    return sum(1 for s in shingles if s in haystack) / len(shingles)


def load_records(step: str) -> List[dict]:
    rows: List[dict] = []
    for path in sorted((ROOT / "runs" / "rag-wixqa" / step).glob("seed*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    if not rows:
        raise SystemExit(f"no records under runs/rag-wixqa/{step}/")
    return rows


def build_block(
    articles_by_id: Dict[str, dict],
    retrieved_ids: Sequence[str],
    qvec,
    grounding: str,
) -> str:
    """Rebuild what the model was shown, from the ids the run recorded.

    `qvec` is the question's embedding, because the wide window is centred on
    whichever chunk best matches it — the same call the run made.
    """
    budget, centred = GROUNDINGS[grounding]
    parts = []
    for art_id in retrieved_ids:
        art = articles_by_id.get(str(art_id))
        if art is None:
            continue
        centre = best_chunk_word_offset(art, qvec) if centred else None
        parts.append(window(art, budget, centre))
    return "\n\n".join(parts)


def main() -> None:
    articles, qa, _kb_ids, _gold = load_data()
    by_id = {str(a["id"]): a for a in articles}

    narrow_rows = load_records(STEP_NARROW)
    wide_rows = load_records(STEP_WIDE)

    # retrieval is identical between the two rungs by construction; take the ids
    # from the wide rung and assert the narrow one agrees rather than assuming it
    ids_by_idx: Dict[int, List[str]] = {}
    for r in wide_rows:
        ids_by_idx.setdefault(int(r["idx"]), [str(i) for i in r["retrieved_ids"]])
    mismatched = sum(
        1 for r in narrow_rows
        if ids_by_idx.get(int(r["idx"])) != [str(i) for i in r["retrieved_ids"]]
    )
    print(f"retrieval identical across the two rungs: {len(narrow_rows) - mismatched}"
          f"/{len(narrow_rows)} cells")

    print(f"rebuilding {len(ids_by_idx)} grounding blocks per rung "
          f"(loads the sentence encoder once)...")
    ordered = sorted(ids_by_idx.items())
    qvecs = encode("bge", [qa[idx]["question"] for idx, _ in ordered], is_query=True)

    exposure: Dict[int, Dict[str, float]] = {}
    for n, ((idx, ids), qvec) in enumerate(zip(ordered, qvecs), 1):
        answer = qa[idx]["answer"]
        narrow_block = build_block(by_id, ids, qvec, NARROW)
        wide_block = build_block(by_id, ids, qvec, WIDE)
        exposure[idx] = {
            "narrow_run": verbatim_run_tokens(answer, narrow_block),
            "wide_run": verbatim_run_tokens(answer, wide_block),
            "narrow_share": verbatim_share(answer, narrow_block),
            "wide_share": verbatim_share(answer, wide_block),
        }
        if n % 50 == 0:
            print(f"  {n}/{len(ids_by_idx)}")

    for e in exposure.values():
        e["delta_share"] = e["wide_share"] - e["narrow_share"]

    # --- the split: did the wider window reveal any NEW reference text? --------
    NEW = 1e-9
    strata = {
        "no new reference text revealed": [i for i, e in exposure.items()
                                           if e["delta_share"] <= NEW],
        "new reference text revealed": [i for i, e in exposure.items()
                                        if e["delta_share"] > NEW],
    }

    scores = {STEP_NARROW: {}, STEP_WIDE: {}}
    for step, rows in ((STEP_NARROW, narrow_rows), (STEP_WIDE, wide_rows)):
        for r in rows:
            if r.get("score") is None:
                continue
            scores[step].setdefault(int(r["idx"]), {})[int(r["seed"])] = int(r["score"])

    out: Dict[str, object] = {
        "criterion": {
            "shingle_tokens": _MIN_SHINGLE_TOKENS,
            "source": "src/tlw/loop/core.py — the guard that aborts a run elsewhere",
        },
        "overall": {
            "questions": len(exposure),
            "share_with_a_verbatim_run": sum(
                1 for e in exposure.values() if e["wide_run"] >= _MIN_SHINGLE_TOKENS
            ) / len(exposure),
            "median_longest_run_tokens": sorted(
                e["wide_run"] for e in exposure.values()
            )[len(exposure) // 2],
            "max_longest_run_tokens": max(e["wide_run"] for e in exposure.values()),
        },
        "strata": {},
    }

    print()
    for label, idxs in strata.items():
        keep = set(idxs)
        table: Dict[str, Dict[str, List[bool]]] = {}
        pairs: List[Tuple[bool, bool]] = []
        for idx in sorted(keep):
            seeds = set(scores[STEP_NARROW].get(idx, {})) & set(scores[STEP_WIDE].get(idx, {}))
            for seed in sorted(seeds):
                pa = scores[STEP_WIDE][idx][seed] >= BAR
                pb = scores[STEP_NARROW][idx][seed] >= BAR
                table.setdefault(str(idx), {}).setdefault("wide", []).append(pa)
                table[str(idx)].setdefault("narrow", []).append(pb)
                pairs.append((pa, pb))
        if not pairs:
            print(f"  {label}: no paired cells")
            continue
        boot = paired_cluster_bootstrap(table, arm_a="wide", arm_b="narrow", seed=0)
        mc = exact_mcnemar(pairs)
        w_wide = wilson_interval(sum(p for p, _ in pairs), len(pairs))
        w_narrow = wilson_interval(sum(q for _, q in pairs), len(pairs))
        out["strata"][label] = {
            "questions": len(table),
            "paired_cells": len(pairs),
            "narrow_pass_rate": w_narrow.point,
            "wide_pass_rate": w_wide.point,
            "delta": boot.point_estimate,
            "ci": [boot.ci_low, boot.ci_high],
            "mcnemar_p": mc.p_value,
            "b": mc.b,
            "c": mc.c,
        }
        print(f"  {label}:")
        print(f"      n={len(table)} questions, {len(pairs)} paired cells")
        print(f"      narrow {w_narrow.point:.3f} -> wide {w_wide.point:.3f}   "
              f"delta {boot.point_estimate:+.3f} [{boot.ci_low:+.3f}, {boot.ci_high:+.3f}]  "
              f"McNemar p={mc.p_value:.4g}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
