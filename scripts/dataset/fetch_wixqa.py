"""Fetch the WixQA dataset into data/external/wixqa/ (ADR-034, §0.3).

The 52 MB corpus is third-party data (Wix/WixQA on HuggingFace, MIT licence). It is
gitignored, so a clone has to be able to re-acquire it — otherwise every WixQA number
in docs/EXPERIMENT_RESULTS.md §7.4-7.6 is unreproducible from a fresh checkout. That is what this
script exists for.

  python scripts/dataset/fetch_wixqa.py

Idempotent: files already present are left alone.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "external" / "wixqa"
REPO = "Wix/WixQA"  # HuggingFace dataset id, MIT licence, arXiv:2505.08643
CONFIGS = {"expertwritten.jsonl": "expertwritten", "kb_corpus.jsonl": "kb_corpus"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    missing = [f for f in CONFIGS if not (OUT / f).is_file()]
    if not missing:
        print(f"already present in {OUT} — nothing to do")
        return 0
    try:
        from datasets import load_dataset
    except ImportError:
        print("this needs the `datasets` package:  pip install datasets", file=sys.stderr)
        return 1

    for fname in missing:
        config = CONFIGS[fname]
        print(f"downloading {REPO}:{config} -> {OUT / fname}")
        ds = load_dataset(REPO, config, split="train")
        with (OUT / fname).open("w", encoding="utf-8") as f:
            for row in ds:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"  wrote {len(ds)} records")

    print("\nnext: rebuild the search index —")
    print("  HF_HUB_OFFLINE=1 python scripts/wixqa/build_index.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
