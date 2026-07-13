"""
CLI for the dataset cleaner (Stage 1).

Examples (run from repo root, in the `tlw` conda env):

    python -m tools.dataset.cli --input data/medical_by_source/Diabetes_and_Digestive_and_Kidney_DiseasesQA.jsonl
    python -m tools.dataset.cli --all
    python -m tools.dataset.cli --all --output-dir data/clean --config tools/dataset/cleaning_config.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root on path

from tools.dataset.cleaner import Config, clean_records, load_records, write_jsonl  # noqa: E402
from tools.dataset.report import measure_clean, measure_raw  # noqa: E402

DEFAULT_CONFIG = Path(__file__).with_name("cleaning_config.yaml")
DEFAULT_SOURCE_DIR = Path("data/medical_by_source")
DEFAULT_OUT_DIR = Path("data/clean")


def _process_one(input_path: Path, out_dir: Path, cfg: Config) -> dict:
    records = load_records(input_path)
    before = measure_raw(records, cfg)
    cleaned, stats = clean_records(records, cfg)
    after = measure_clean(cleaned, cfg)

    stem = input_path.stem.replace("QA", "")
    out_jsonl = out_dir / f"{stem}_clean.jsonl"
    write_jsonl(cleaned, out_jsonl)

    report = {
        "input": str(input_path),
        "output": str(out_jsonl),
        "before": before,
        "after": after,
        "dropped": dict(stats.dropped),
        "dropped_exact_dup": stats.dropped_exact_dup,
        "template_marked": stats.template_marked,
        "top_flags": dict(stats.flag_counts.most_common(10)),
    }
    (out_dir / f"{stem}_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def _print_summary(rep: dict) -> None:
    b, a = rep["before"], rep["after"]
    name = Path(rep["input"]).stem
    print(f"\n=== {name} ===")
    print(f"  records:     {b['n']:>5}  ->  {a['n']:>5}  "
          f"(dropped {sum(rep['dropped'].values())} + exact-dup {rep['dropped_exact_dup']})")
    print(f"  noise rate:  {b['noise_rate']*100:>5.1f}% ->  {a['noise_rate']*100:>4.1f}%")
    print(f"  dup answers: {b['dup_answers']:>5}  ->  {a['dup_answers']:>5}   "
          f"(templates flagged: {rep['template_marked']})")
    print(f"  median words:{b['median_words']:>5}  ->  {a['median_words']:>5}   "
          f"(>250w: {b['pct_gt250w']}% -> {a['pct_gt250w']}%)")
    print(f"  double-?? Q: {b['double_qmark_questions']:>5}")
    if rep["dropped"]:
        print(f"  drop reasons: {rep['dropped']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic MedQuAD cleaner (Stage 1)")
    ap.add_argument("--input", type=Path, help="single .jsonl/.csv file to clean")
    ap.add_argument("--all", action="store_true", help=f"clean every *.jsonl in {DEFAULT_SOURCE_DIR}")
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = ap.parse_args(argv)

    if not args.input and not args.all:
        ap.error("provide --input <file> or --all")

    cfg = Config.load(args.config)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    inputs = sorted(DEFAULT_SOURCE_DIR.glob("*.jsonl")) if args.all else [args.input]
    grand_before = grand_after = 0
    for path in inputs:
        rep = _process_one(path, args.output_dir, cfg)
        _print_summary(rep)
        grand_before += rep["before"]["n"]
        grand_after += rep["after"]["n"]

    print(f"\n{'='*48}\nTOTAL: {grand_before} -> {grand_after} clean records  "
          f"(written to {args.output_dir}/)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
