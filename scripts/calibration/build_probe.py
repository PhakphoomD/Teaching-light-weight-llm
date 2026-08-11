"""Build a boundary-targeted judge-calibration set.

The RAG/the teaching-loop study pass/fail decision lives entirely at the uncalibrated score
3-vs-4 line (99.6% of real answers score 3 or 4). This samples REAL student
answers stratified around that line, attaches the gold reference (legal for
CALIBRATION — a score-path activity, teaching-loop-protocol §2 / L10-L12), and records each
candidate judge's BLIND score, so a strong-reference anchor label (added next)
can be compared against them (accuracy / Cohen's kappa).

Sources both judges' views of the SAME (question, answer) pairs:
  - local score: already in runs_reliability/ rounds (local llama3.1:8b)
  - groq score: computed here (Groq llama-3.1-8b-instant, blind)

  HF_HUB_OFFLINE=1 python scripts/calibration/build_probe.py --n 60 --out data/calibration/boundary_set.jsonl
"""

from __future__ import annotations

import argparse
import glob
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import src.tlw.providers  # noqa: E402,F401
from src.providers.factory import build_client  # noqa: E402
from src.tlw.evaluation.judge import BlindJudge  # noqa: E402

HELDOUT = "data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--out", default="data/calibration/boundary_set.jsonl")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)

    gold = {json.loads(l)["id"]: json.loads(l)["answer"]
            for l in open(HELDOUT, encoding="utf-8")}

    # collect real answers with their local score, tagged by arm
    pool = []
    for f in glob.glob("runs_reliability/*/rounds.jsonl"):
        arm = "3B+RAG" if "3bRAG" in f else "3B"
        for l in open(f, encoding="utf-8"):
            r = json.loads(l)
            if r.get("answer") and r.get("score") is not None and r["question_id"] in gold:
                pool.append({"question_id": r["question_id"], "question": r["question"],
                             "answer": r["answer"], "arm": arm, "local_score": r["score"]})
    rng = random.Random(args.seed)
    rng.shuffle(pool)

    # stratify around the boundary: aim for a spread of local scores 3 and 4,
    # both arms; take a few clearly-low if any exist.
    buckets = {("3B", 3): [], ("3B", 4): [], ("3B+RAG", 3): [], ("3B+RAG", 4): [], "low": []}
    for p in pool:
        if p["local_score"] <= 2:
            buckets["low"].append(p)
        else:
            buckets[(p["arm"], p["local_score"])].append(p)
    per = max(1, (args.n - 6) // 4)
    picked, seen = [], set()
    for key in [("3B", 4), ("3B", 3), ("3B+RAG", 4), ("3B+RAG", 3)]:
        for p in buckets[key][:per]:
            k = (p["question_id"], p["arm"], p["answer"][:40])
            if k not in seen:
                seen.add(k); picked.append(p)
    for p in buckets["low"][:6]:
        picked.append(p)
    picked = picked[:args.n]

    # blind Groq judge on the SAME answers
    judge = BlindJudge(client=build_client("groq", model="llama-3.1-8b-instant"),
                       pass_threshold=1.0, temperature=0.0, max_tokens=256)
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for i, p in enumerate(picked, 1):
            v = judge.score(p["question"], p["answer"], mode="blind")
            rec = {
                "idx": i,
                "question_id": p["question_id"],
                "question": p["question"],
                "gold_answer": gold[p["question_id"]],
                "student_answer": p["answer"],
                "arm": p["arm"],
                "local_score": p["local_score"],
                "groq_score": v["score"],
                "anchor_pass": None,  # to be filled by the strong-reference anchor
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if i % 20 == 0:
                print(f"  judged {i}/{len(picked)}", flush=True)
    print(f"wrote {len(picked)} calibration items -> {out_path}")
    # quick summary of judge (dis)agreement on pass(>=4)/fail
    items = [json.loads(l) for l in open(out_path, encoding="utf-8")]
    agree = sum(1 for r in items if (r["local_score"] >= 4) == (r["groq_score"] >= 4))
    print(f"local vs groq PASS agreement (pre-anchor): {agree}/{len(items)} = {agree/len(items):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
