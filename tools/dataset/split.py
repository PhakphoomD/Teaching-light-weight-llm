"""
Stage 3 — split a cleaned dataset into train / held-out.

Held-out rules (§0.2 integrity):
- excludes `is_template` records (trivial/leakage-prone canned answers),
- stratified by question type so held-out covers the same variety as train,
- deterministic (seeded).

Run (repo root, tlw env):
  python -m tools.dataset.split \
      --input data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_clean.jsonl --heldout-frac 0.2
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import defaultdict
from pathlib import Path

_QTYPE = re.compile(
    r"^(what is \(are\)|what is|what are the symptoms|who is at risk|how to diagnose|"
    r"what causes|what are the treatments|how many people|is )",
    re.IGNORECASE,
)


def qtype(q: str) -> str:
    m = _QTYPE.match(q.strip())
    return m.group(1).lower() if m else "other"


def split_dataset(path: Path, out_dir: Path, heldout_frac: float = 0.2, seed: int = 42) -> dict:
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    rng = random.Random(seed)

    eligible = [r for r in recs if not r.get("is_template")]  # held-out candidates
    by_type: dict[str, list] = defaultdict(list)
    for r in eligible:
        by_type[qtype(r["question"])].append(r)

    heldout_ids: set[str] = set()
    for group in by_type.values():
        rng.shuffle(group)
        k = round(len(group) * heldout_frac) if len(group) >= 5 else 0
        for r in group[:k]:
            heldout_ids.add(r["id"])

    train, heldout = [], []
    for r in recs:
        r["split"] = "heldout" if r["id"] in heldout_ids else "train"
        (heldout if r["split"] == "heldout" else train).append(r)

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem.replace("_clean", "")
    for name, rows in (("train", train), ("heldout", heldout)):
        with open(out_dir / f"{stem}_{name}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    templates = sum(1 for r in recs if r.get("is_template"))
    return {
        "input": str(path), "n": len(recs),
        "train": len(train), "heldout": len(heldout),
        "templates_in_train_only": templates,
        "heldout_types": {k: sum(1 for r in heldout if qtype(r["question"]) == k)
                          for k in sorted({qtype(r["question"]) for r in heldout})},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 3 — train/held-out split")
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, default=Path("data/clean"))
    ap.add_argument("--heldout-frac", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    st = split_dataset(args.input, args.output_dir, args.heldout_frac, args.seed)
    print(json.dumps(st, ensure_ascii=False, indent=2))
    print(f"\n[written] {st['input']} -> train {st['train']} + heldout {st['heldout']} "
          f"(templates excluded from held-out)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
