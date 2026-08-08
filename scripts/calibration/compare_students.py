"""
Local student comparison: llama3.1:8b vs qwen2.5:7b-instruct (Ollama).

Bias-free method: each model answers the same domain questions zero-shot (no reference
shown — §0.2). We score each answer by semantic similarity to the reference answer using
all-MiniLM-L6-v2 (model-agnostic, favors neither family). Reported as a *reference-proximity*
proxy (per ADR-001, proximity != correctness — directional signal), plus length + speed.

Run (repo root, tlw env; Ollama up):
  & "C:\\Users\\ham25\\.conda\\envs\\tlw\\python.exe" scripts/calibration/compare_students.py --n 6
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.request
from pathlib import Path
from statistics import fmean

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.dataset.embeddings import embed, cosine  # noqa: E402

CLEAN = Path("data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_clean.jsonl")
STUDENTS = ["llama3.1:8b", "qwen2.5:7b-instruct"]
PROMPT = "Answer this medical question accurately and concisely.\n\nQuestion: {q}\n\nAnswer:"
HOST = "http://localhost:11434"


def ollama_generate(model: str, prompt: str) -> str:
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "stream": False, "options": {"temperature": 0.0, "num_predict": 256}}
    req = urllib.request.Request(f"{HOST}/api/chat", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read()).get("message", {}).get("content", "").strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    recs = [json.loads(l) for l in CLEAN.read_text(encoding="utf-8").splitlines() if l.strip()]
    sample = random.Random(args.seed).sample(recs, min(args.n, len(recs)))
    refs = [r["answer"] for r in sample]
    ref_vecs = embed(refs)
    print(f"Student probe: {len(sample)} Diabetes questions, zero-shot, scored vs reference (MiniLM)\n")

    for model in STUDENTS:
        t0 = time.time()
        answers = [ollama_generate(model, PROMPT.format(q=r["question"])) for r in sample]
        secs = time.time() - t0
        ans_vecs = embed(answers)
        sims = [cosine(ans_vecs[i], ref_vecs[i]) for i in range(len(sample))]
        words = [len(a.split()) for a in answers]
        print(f"=== {model} ===")
        print(f"  ref-proximity (cos): mean={fmean(sims):.3f}  min={min(sims):.3f}  max={max(sims):.3f}")
        print(f"  answer words: mean={fmean(words):.0f}   time: {secs:.1f}s ({secs/len(sample):.1f}s/q)\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
