"""CLI for the RAG index builder (T3.2).

Reproducible single command (§0.3), tlw python only (§0.5):

  python -m tools.rag.cli \
    --source  data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_train.jsonl \
    --exclude data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl \
    --out     indexes/medquad-diabetes-train

`--exclude` is the held-out split whose records must NOT enter the index
(RAG-L1) and whose near-duplicates are scrubbed (RAG-L2). Omit it only for a
generality smoke on a split-less domain file.
"""

from __future__ import annotations

import argparse
import sys

from tools.rag.builder import RagIndexBuilder


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build a RAG retrieval index from a cleaned jsonl.")
    ap.add_argument("--source", required=True, help="cleaned jsonl to index (e.g. a *_train.jsonl)")
    ap.add_argument("--out", required=True, help="output dir for the index trio + report")
    ap.add_argument("--exclude", default=None, help="held-out jsonl to EXCLUDE + scrub near-dups against")
    ap.add_argument("--name", default=None, help="index name (default: source stem)")
    ap.add_argument("--dedup-threshold", type=float, default=0.90, help="RAG-L2a cosine cutoff (default 0.90)")
    ap.add_argument(
        "--block-shingle-min",
        type=int,
        default=8,
        help="RAG-L2b: drop a record sharing >= this many 12-token shingles with any "
        "held-out answer (verbatim-block/template leak; default 8)",
    )
    args = ap.parse_args(argv)

    builder = RagIndexBuilder(
        source=args.source,
        out_dir=args.out,
        exclude=args.exclude,
        name=args.name,
        dedup_threshold=args.dedup_threshold,
        block_shingle_min=args.block_shingle_min,
    )
    report = builder.build()

    print(f"[rag-build] name={report.name}")
    print(f"[rag-build] source records: {report.n_source}")
    print(f"[rag-build] dropped held-out id (RAG-L1): {report.n_dropped_heldout_id}")
    print(f"[rag-build] dropped cosine near-dup (RAG-L2a): {report.n_dropped_near_dup}")
    print(f"[rag-build] dropped verbatim-block (RAG-L2b): {report.n_dropped_block}")
    print(f"[rag-build] indexed passages: {report.n_indexed} (dim {report.dim})")
    print(f"[rag-build] held-out id exclusion: {report.heldout_id_exclusion}")
    print(f"[rag-build] held-out text exclusion: {report.heldout_text_exclusion}")
    print(f"[rag-build] artifacts -> {args.out}")

    ok = report.heldout_id_exclusion == "PASS" and not report.heldout_text_exclusion.startswith("FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
