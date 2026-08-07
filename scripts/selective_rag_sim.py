"""Offline selective-RAG simulation (P3-B, SELECTIVE_RAG.md §4).

Tests the "verify-then-ground" gate WITHOUT re-running the student. We already
have, per (question, seed): the baseline draft + its pass/fail (trackA_full_armA)
and the always-on-RAG answer + its pass/fail (trackB_p3_3bRAG). This script runs
ONLY the gate call per (question, seed) and simulates the selective outcome:

    selective pass = RAG answer's pass/fail   if gate says "passages add knowledge"
                     baseline draft's pass/fail otherwise

then compares selective vs baseline / always-on / oracle. §0.2-safe: the gate
sees (draft, passages) only — never the gold answer.

Run (tlw python, after the GPU is free / on Groq):
  HF_HUB_OFFLINE=1 python scripts/selective_rag_sim.py --runs-dir runs_rag \
      --corpus indexes/medquad-diabetes-train --gate groq:llama-3.1-8b-instant
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parents[1] / ".env")  # GROQ_API_KEY (gate on Groq)

from src.providers.factory import build_client  # noqa: E402
import src.tlw.providers  # noqa: E402,F401  registers local->Ollama
import src.tlw.memory  # noqa: E402,F401  registers rag
from src.tlw.registries import build_memory_backend  # noqa: E402

GATE_PROMPT = """A DRAFT ANSWER to a medical question is shown below, with some REFERENCE PASSAGES.
Decide whether the draft NEEDS the passages.

Answer YES only if the passages contain a specific, important fact that DIRECTLY answers the
QUESTION and is CLEARLY ABSENT from, or CONTRADICTED by, the draft. If the draft already answers
the question adequately on its own, answer NO — even if the passages are topically related. When
unsure, answer NO.

QUESTION: {question}

DRAFT ANSWER:
{draft}

REFERENCE PASSAGES:
{passages}

Answer with a single word: YES or NO."""

_YES = re.compile(r"\byes\b", re.I)
_NO = re.compile(r"\bno\b", re.I)


def gate_says_ground(client, question: str, draft: str, passages: str) -> bool:
    if not passages.strip():
        return False  # nothing retrieved -> keep the draft
    prompt = GATE_PROMPT.format(question=question or "", draft=draft or "", passages=passages)
    resp = client.chat(messages=[{"role": "user", "content": prompt}], temperature=0.0, max_tokens=8, timeout_s=60)
    text = "" if getattr(resp, "error", None) else (getattr(resp, "text", "") or "")
    # first explicit YES/NO wins; default NO (conservative — don't ground on ambiguity)
    y, n = _YES.search(text), _NO.search(text)
    if y and (not n or y.start() < n.start()):
        return True
    return False


def _load(pat: str):
    out = {}
    for f in Path(".").glob(pat):
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            out[(r["question_id"], r["seed"])] = r
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Offline selective-RAG (verify-then-ground) simulation.")
    ap.add_argument("--runs-dir", default="runs_rag")
    ap.add_argument("--corpus", default="indexes/medquad-diabetes-train")
    ap.add_argument("--gate", default="groq:llama-3.1-8b-instant", help="gate model provider:model")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--floor", type=float, default=0.35)
    ap.add_argument("--seed", type=int, default=None, help="restrict to one seed (e.g. 42) — for a small-budget strong-gate test")
    args = ap.parse_args(argv)

    rd = args.runs_dir
    # Label-driven with a fallback to the pre-ADR-034 config-stem names, so this
    # works before and after the restructure; fails loud instead of silently
    # simulating on zero questions.
    def _load_any(patterns, label):
        for pat in patterns:
            got = _load(f"{rd}/{pat}/rounds.jsonl")
            if got:
                return got
        raise SystemExit(f"no {label} runs under {rd!r}; tried: {', '.join(patterns)}")

    base = _load_any(["small-model-no-rag__seed*", "trackA_full_armA_diabetes__seed*"], "baseline")
    rag = _load_any(["small-model-with-rag__seed*", "trackB_p3_3bRAG*"], "RAG")
    keys = [k for k in base if k in rag]
    if args.seed is not None:
        keys = [k for k in keys if k[1] == args.seed]
    if not keys:
        print("no matching (question,seed) pairs found", file=sys.stderr)
        return 1

    provider, model = args.gate.split(":", 1)
    gate_client = build_client(provider, model=model)
    memory = build_memory_backend("rag", corpus_path=args.corpus, top_k=args.top_k, similarity_threshold=args.floor)

    n = len(keys)
    base_pass = sum(base[k]["passed"] for k in keys)
    rag_pass = sum(rag[k]["passed"] for k in keys)
    oracle = sum(base[k]["passed"] or rag[k]["passed"] for k in keys)

    sel_pass = 0
    gate_fires = 0
    # gate per (question, seed) using that run's baseline draft
    for i, k in enumerate(keys, 1):
        draft = base[k]["answer"]
        hits = memory.retrieve(base[k]["question"], args.top_k)
        passages = "\n".join(f"[{j+1}] {h['passage']}" for j, h in enumerate(hits))
        ground = gate_says_ground(gate_client, base[k]["question"], draft, passages)
        gate_fires += int(ground)
        chosen = rag[k] if ground else base[k]
        sel_pass += int(chosen["passed"])
        if i % 50 == 0:
            print(f"  ...{i}/{n} (gate fired {gate_fires})", flush=True)

    print("\n" + "=" * 60)
    print(f"n (question,seed) pairs        : {n}")
    print(f"3B baseline                    : {base_pass/n:.3f}  ({base_pass}/{n})")
    print(f"3B+RAG always-on               : {rag_pass/n:.3f}  ({rag_pass}/{n})")
    print(f"3B+SELECTIVE (verify-then-ground): {sel_pass/n:.3f}  ({sel_pass}/{n})  gate fired {gate_fires}/{n} ({gate_fires/n:.0%})")
    print(f"3B+ORACLE-selective (ceiling)  : {oracle/n:.3f}  ({oracle}/{n})")
    print("-" * 60)
    print(f"selective − baseline           : {(sel_pass-base_pass)/n:+.3f}")
    print(f"selective − always-on          : {(sel_pass-rag_pass)/n:+.3f}")
    print(f"oracle    − baseline (headroom): {(oracle-base_pass)/n:+.3f}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
