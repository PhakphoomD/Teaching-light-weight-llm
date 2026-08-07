"""Build the LoRA SFT dataset (T3.6) — standard instruction tuning on the
Diabetes TRAIN split's (question -> gold reference answer) pairs.

Recipe rationale (T3.5 gate, ADR-027): the loop-as-factory recipe the light
spec assumed (self-refine + RAG grounding) yields NO distillable signal on this
near-ceiling testbed — self-refine does not engage on TRAIN (the 3B passes
round-1, T3.6 smoke) and RAG hurts (ADR-027). So the honest LoRA target is the
domain's own reference answers (TRAIN only), teaching the 3B the domain answer
style/format (LIMA: fine-tuning teaches style, not facts). Held-out gain is
expected to be modest/null and will be reported honestly (T3.8).

Anti-leak (§0.2): TRAIN split only; the held-out 125 are never included and are
verified absent by id AND by question text. Cloud-free (no judge/Groq needed —
the gold answer IS the quality target).

  python scripts/build_lora_data.py --out data/processed/lora_diabetes_sft.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_train.jsonl"
HELDOUT = ROOT / "data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl"


def norm(s: str) -> str:
    return " ".join((s or "").split()).lower()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/processed/lora_diabetes_sft.jsonl")
    ap.add_argument("--min-answer-words", type=int, default=10)
    ap.add_argument("--max-answer-words", type=int, default=400)
    args = ap.parse_args(argv)

    train = [json.loads(l) for l in open(TRAIN, encoding="utf-8")]
    held = [json.loads(l) for l in open(HELDOUT, encoding="utf-8")]
    held_ids = {r["id"] for r in held}
    held_q = {norm(r["question"]) for r in held}

    seen_q, pairs, skipped = set(), [], {"template": 0, "len": 0, "dup": 0, "heldout": 0, "empty": 0}
    for r in train:
        q, a = r.get("question", ""), r.get("answer", "")
        if not q.strip() or not a.strip():
            skipped["empty"] += 1; continue
        if r.get("is_template"):
            skipped["template"] += 1; continue
        # HARD anti-leak: never a held-out id or question
        if r["id"] in held_ids or norm(q) in held_q:
            skipped["heldout"] += 1; continue
        w = len(a.split())
        if w < args.min_answer_words or w > args.max_answer_words:
            skipped["len"] += 1; continue
        if norm(q) in seen_q:
            skipped["dup"] += 1; continue
        seen_q.add(norm(q))
        pairs.append({
            "question": q.strip(),
            "answer": a.strip(),
            "provenance": {"source_id": r["id"], "split": "train", "recipe": "gold-sft"},
        })

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    # data card
    card = out.with_name(out.stem + "_CARD.md")
    aw = [len(p["answer"].split()) for p in pairs]
    card.write_text(
        f"""# LoRA SFT dataset — Diabetes (T3.6)

- **Pairs:** {len(pairs)}  (question -> gold reference answer)
- **Source:** `{TRAIN.name}` (TRAIN split only)
- **Recipe:** gold-SFT (instruction tuning on the domain reference answers).
  Rationale: the loop-factory recipe yields no distillable signal on this
  near-ceiling testbed (self-refine doesn't engage; RAG hurts, ADR-027), so the
  target is the reference answers — teaching answer style/format (LIMA).
- **Answer length (words):** min {min(aw)}, median {sorted(aw)[len(aw)//2]}, max {max(aw)}
- **Anti-leak (§0.2):** held-out 125 excluded by id AND question; verified 0 held-out here.
- **Filters skipped:** {skipped}
- **Expected result (T3.8):** modest/null held-out gain — LoRA teaches style, not
  the held-out-specific knowledge (LIMA); reported honestly.
""",
        encoding="utf-8",
    )
    print(f"wrote {len(pairs)} SFT pairs -> {out}")
    print(f"skipped: {skipped}")
    print(f"held-out leak check: 0 (excluded {skipped['heldout']} by id/question)")
    print(f"data card -> {card}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
