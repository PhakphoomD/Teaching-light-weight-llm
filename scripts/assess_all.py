"""
Stage 4 — verify: run the readiness assessor across every cleaned domain and compare.

Uses model-free dims (D1-D3, D5-D7 + volume) by default (--judge none) so the sweep is
fast, reproducible, and needs no API. D4 quality can be run per-domain separately.

Run (repo root, tlw env):
  & "C:\\Users\\ham25\\.conda\\envs\\tlw\\python.exe" scripts/assess_all.py --target lora
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.dataset.assessor import assess  # noqa: E402

CLEAN_DIR = Path("data/clean")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["rag", "lora", "eval"], default="lora")
    ap.add_argument("--judge", default="none")
    args = ap.parse_args()

    files = sorted(CLEAN_DIR.glob("*_clean.jsonl"))
    print(f"Stage 4 verify — target={args.target}, judge={args.judge}, {len(files)} domains\n")
    print(f"{'domain':<26}{'n':>6}{'overall':>9}  {'verdict':<11} weakest dims")
    print("=" * 78)
    for f in files:
        rep = assess(f, args.target, judge_kind=args.judge)
        weak = [f"{k}({g['score']:.0f}{'🔴' if g['band']=='red' else '🟡'})"
                for k, g in rep["dimensions"].items() if g["band"] != "green"]
        if rep["volume"]["band"] != "green":
            weak.append(f"volume({rep['volume']['n']}{'🔴' if rep['volume']['band']=='red' else '🟡'})")
        print(f"{rep['dataset'].replace('_clean',''):<26}{rep['n']:>6}{rep['overall']:>9}  "
              f"{rep['verdict']:<11} {', '.join(weak) if weak else 'all green'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
