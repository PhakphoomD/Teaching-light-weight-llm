"""
Dataset Readiness Assessor (Stage 2) — compute D1–D7 for a cleaned dataset + a target,
roll up per rubric weights, apply the volume gate, emit verdict + report (md + json).

Mirrors `.claude/rules/rubric.md` (thresholds/weights are here as the single code source).
Deterministic (seeded sampling for the D4 judge). Model-free dims run without any API.

Run (repo root, tlw env):
  & "C:\\Users\\ham25\\.conda\\envs\\tlw\\python.exe" -m tools.dataset.assessor \
      --input data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_clean.jsonl --target lora
  # add --judge none to skip D4 (no API); --quality-sample N to bound judge calls
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path
from statistics import fmean

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.dataset.embeddings import diversity_score, embed, cosine, near_dup_rate  # noqa: E402
from tools.dataset.report import noise_rate  # noqa: E402
from tools.dataset.cleaner import Config  # noqa: E402

RUBRIC = {
    "thresholds": {  # (green, yellow); below yellow = red
        "structural": (99, 95), "cleanliness": (98, 90), "uniqueness": (95, 85),
        "quality": (75, 60), "complexity": (85, 70), "diversity": (70, 50), "answerability": (80, 65),
    },
    "weights": {
        "rag":  {"answerability": .25, "cleanliness": .20, "quality": .15, "uniqueness": .10, "complexity": .05, "diversity": .10, "structural": .15},
        "lora": {"answerability": .05, "cleanliness": .15, "quality": .25, "uniqueness": .20, "complexity": .15, "diversity": .15, "structural": .05},
        "eval": {"answerability": .20, "cleanliness": .10, "quality": .15, "uniqueness": .25, "complexity": .20, "diversity": .05, "structural": .05},
    },
    "volume": {"rag": (200, 50), "lora": (1000, 300), "eval": (200, 100)},
}
_DEFER = re.compile(r"https?://|1-?800|for more information|visit the|see the website", re.IGNORECASE)


def _band(score: float, green: float, yellow: float) -> str:
    return "green" if score >= green else ("yellow" if score >= yellow else "red")


def _volume_band(n: int, target: str) -> str:
    g, y = RUBRIC["volume"][target]
    return "green" if n >= g else ("yellow" if n >= y else "red")


def assess(path: Path, target: str, judge_kind: str = "groq", quality_sample: int = 30, seed: int = 42) -> dict:
    cfg = Config.load(Path(__file__).with_name("cleaning_config.yaml"))
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    n = len(recs)
    answers = [r["answer"] for r in recs]
    questions = [r["question"] for r in recs]

    # --- model-free dims ---
    valid = sum(1 for r in recs if r.get("question") and r.get("answer"))
    d1 = 100.0 * valid / n
    d2 = 100.0 * (1 - noise_rate(answers, cfg))
    d3 = 100.0 * (1 - near_dup_rate(answers, threshold=0.90))
    non_template = sum(1 for r in recs if not r.get("is_template"))
    d5 = 100.0 * non_template / n
    d6 = diversity_score(questions)

    # D7 answerability: scaled Q-A relevance + self-contained
    qv, av = embed(questions), embed(answers)
    rel = fmean(cosine(qv[i], av[i]) for i in range(n))
    self_contained = 100.0 * sum(1 for a in answers if not _DEFER.search(a)) / n
    d7 = 0.6 * min(rel / 0.6, 1.0) * 100 + 0.4 * self_contained

    dims = {"structural": d1, "cleanliness": d2, "uniqueness": d3,
            "complexity": d5, "diversity": d6, "answerability": d7}

    # --- D4 quality (LLM judge, sampled) ---
    if judge_kind and judge_kind != "none":
        from tools.dataset.judge import build_judge
        judge = build_judge(judge_kind)
        rng = random.Random(seed)
        sample = rng.sample(recs, min(quality_sample, n))
        scores = [judge.score(r["question"], r["answer"]) for r in sample]
        scores = [s for s in scores if s is not None]
        dims["quality"] = 100.0 * fmean(scores) if scores else None
    else:
        dims["quality"] = None

    # --- bands + weighted overall (renormalize if quality skipped) ---
    th = RUBRIC["thresholds"]
    graded = {k: {"score": round(v, 1), "band": _band(v, *th[k])} for k, v in dims.items() if v is not None}
    w = dict(RUBRIC["weights"][target])
    if dims["quality"] is None:
        w.pop("quality", None)
        tot = sum(w.values())
        w = {k: v / tot for k, v in w.items()}
    overall = sum(w[k] * graded[k]["score"] for k in w)

    vol_band = _volume_band(n, target)
    reds = [k for k, g in graded.items() if g["band"] == "red"]
    if vol_band == "red" or graded["structural"]["band"] == "red" or overall < 50:
        verdict = "NOT READY"
    elif overall >= 75 and not reds and vol_band != "red":
        verdict = "READY"
    else:
        verdict = "NEEDS WORK"

    fixes = []
    for k, g in graded.items():
        if g["band"] != "green":
            fixes.append(f"{k} {g['band']} ({g['score']}) — {_fix_hint(k)}")
    if vol_band != "green":
        fixes.append(f"volume {vol_band} (n={n}) — need >= {RUBRIC['volume'][target][0]} for {target}")

    return {
        "dataset": path.stem, "n": n, "target": target,
        "dimensions": graded, "volume": {"n": n, "band": vol_band},
        "overall": round(overall, 1), "verdict": verdict,
        "quality_judge": judge_kind if dims["quality"] is not None else "skipped",
        "fixes": fixes,
    }


def _fix_hint(dim: str) -> str:
    return {
        "structural": "drop empty/invalid records",
        "cleanliness": "strip residual boilerplate/URLs",
        "uniqueness": "remove near-duplicate answers",
        "quality": "review low-scoring answers; the reference text may be weak",
        "complexity": "exclude template/canned answers or add richer content",
        "diversity": "add more question types (MedQuAD is template-heavy)",
        "answerability": "ensure answers directly address the question and are self-contained",
    }.get(dim, "review")


def _render_md(rep: dict) -> str:
    icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
    lines = [f"# Readiness: {rep['dataset']}  ·  target={rep['target']}",
             f"**Verdict: {rep['verdict']}**  ·  Overall {rep['overall']}  ·  n={rep['n']}  ·  D4 judge: {rep['quality_judge']}",
             "", "| Dimension | Score | Band |", "|---|---|---|"]
    for k, g in rep["dimensions"].items():
        lines.append(f"| {k} | {g['score']} | {icon[g['band']]} |")
    lines.append(f"| volume | {rep['volume']['n']} | {icon[rep['volume']['band']]} |")
    if rep["fixes"]:
        lines += ["", "## Fixes", *[f"- {f}" for f in rep["fixes"]]]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Dataset Readiness Assessor (Stage 2)")
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--target", choices=["rag", "lora", "eval"], default="lora")
    ap.add_argument("--judge", default="groq", help="groq | ollama | none")
    ap.add_argument("--quality-sample", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rep = assess(args.input, args.target, args.judge, args.quality_sample, args.seed)
    out_md = args.input.with_name(f"{args.input.stem}_readiness_{args.target}.md")
    out_json = args.input.with_name(f"{args.input.stem}_readiness_{args.target}.json")
    out_md.write_text(_render_md(rep), encoding="utf-8")
    out_json.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(_render_md(rep))
    print(f"[written] {out_md.name} + {out_json.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
