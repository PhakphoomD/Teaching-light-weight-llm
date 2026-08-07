"""WixQA T3.14 Stage-2 (P3-E): self-refine ON TOP OF RAG — the Loop+RAG system.

The configuration the project is named after, never previously evaluated: every
RAG run so far was single-pass (arm A), and the loop (self-refine) was only ever
run WITHOUT RAG (Track A). This runs them together (ADR-032).

Design (from the Stage-1 findings and the pre-registered plan):

* **Grounding persists in EVERY round.** The framework's arm-B `refine` prompt
  (`src/tlw/loop/strategies.py:154`) drops the passages after round 1, which would
  make the model refine from memory and re-open the knowledge gap RAG just closed.
  Here the SAME chunk2400 grounding block is supplied to the critique AND the
  refine step of every round — this is Reflexion-style grounded refinement
  (Shinn 2303.11366), not the intrinsic self-correction Huang (2310.01798) showed
  to be unreliable.
* **Rewrite, don't append (finding F1).** The student already writes longer than
  the reference (152 vs 125 words) and ~40% of answers sit near the token ceiling,
  so the critique asks for MISSING CONCRETE FACTS FROM THE CONTEXT and the refine
  step rewrites within the same length instead of padding.
* **No gold anywhere in the loop (§0.2).** WixQA's only usable judge is
  reference-comparing, so it must NOT gate iteration. Rounds are FIXED (1 initial
  + N refinements) and judged once, offline, at the end. A BLIND self-assessment
  is logged each round so an early-stop policy can be evaluated offline from the
  same generation run (both policies, one run, no extra cost).
* **Round 1 is reused** from the Stage-1 chunk2400 run (identical prompt+seed →
  identical output), so the comparison is exactly paired and 1/3 of the compute
  is saved.

  HF_HUB_OFFLINE=1 python scripts/wixqa_selfrefine.py --seeds 42 --only-gold-retrieved --tag pilot
"""
import argparse, glob, json, os, sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import src.tlw.providers  # noqa: F401
from src.providers.factory import build_client
from scripts.wixqa_retriever_ladder import load_data, encode
from scripts.wixqa_grounding_ladder import window, best_chunk_word_offset
from scripts.wixqa_run3seed_retriever import GROUNDINGS
from scripts.wixqa_run3seed import RAG_SYS, TEMPERATURE, MAX_TOKENS

OUT = ROOT / "runs/rag-wixqa"

CRITIQUE_SYS = (
    "You review a DRAFT answer to a Wix customer-support question. Compare the draft ONLY against the "
    "REFERENCE CONTEXT below. List up to 5 concrete, specific facts, steps, settings or conditions that "
    "appear in the REFERENCE CONTEXT, are relevant to the QUESTION, and are MISSING from the draft or "
    "stated vaguely/incorrectly in it. Be terse: short bullet points, no preamble, no praise. "
    "If the draft already covers everything relevant, reply with exactly: COMPLETE"
)
REFINE_SYS = (
    "You rewrite a draft answer for a Wix customer-support assistant. Using the REFERENCE CONTEXT and the "
    "REVIEW notes, produce an improved answer that incorporates the missing facts named in the review. "
    "IMPORTANT: keep the answer roughly the SAME LENGTH as the draft — do not pad; cut redundant or generic "
    "sentences to make room for the specific facts. Stay grounded in the context; never invent details. "
    "Output ONLY the rewritten answer."
)
SELFASSESS_SYS = (
    "Answer with exactly one word, YES or NO. Given the QUESTION and the REFERENCE CONTEXT, does the "
    "ANSWER below completely and correctly answer the question with all the relevant specifics from the "
    "context? Reply YES or NO only."
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[13, 42, 123])
    ap.add_argument("--grounding", choices=list(GROUNDINGS), default="chunk2400")
    ap.add_argument("--refine-rounds", type=int, default=2, help="refinement rounds AFTER the initial answer")
    ap.add_argument("--only-gold-retrieved", action="store_true",
                    help="PILOT ONLY: labelled diagnostic subset, never a headline aggregate")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()

    arts, qa, _, _ = load_data()
    id2art = {x["id"]: x for x in arts}
    budget, centred = GROUNDINGS[a.grounding]
    student = build_client("local", model="qwen2.5:3b")

    def gen(sys_msg, user_msg, seed, max_tokens=MAX_TOKENS):
        r = student.chat([{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
                         temperature=TEMPERATURE, max_tokens=max_tokens, timeout_s=180, seed=seed)
        return (r.text or "").strip(), r.error

    for seed in a.seeds:
        base_path = OUT / f"rag_bge_chunk_{a.grounding}__seed{seed}.jsonl"
        if not base_path.is_file():
            print(f"[skip] missing Stage-1 base run {base_path.name}")
            continue
        base = [json.loads(l) for l in base_path.open(encoding="utf-8") if l.strip()]
        if a.only_gold_retrieved:
            base = [r for r in base if r.get("gold_retrieved")]
        print(f"[seed {seed}] {len(base)} questions x ({a.refine_rounds} refine rounds) "
              f"= {len(base)*a.refine_rounds*3} student calls")

        # grounding blocks (identical to Stage 1) — needed in EVERY round
        qv = encode("bge", [r["question"] for r in base], is_query=True) if centred else None
        suffix = (f"_{a.tag}" if a.tag else "")
        out_path = OUT / f"rag_bge_chunk_{a.grounding}_selfrefine{suffix}__seed{seed}.jsonl"
        f = out_path.open("w", encoding="utf-8")
        fails = 0
        for n, r in enumerate(base):
            hits = [id2art[aid] for aid in r["retrieved_ids"]]
            block = "\n\n".join(
                f"[{k+1}] {h.get('title','')}\n"
                f"{window(h, budget, best_chunk_word_offset(h, qv[n]) if centred else None)}"
                for k, h in enumerate(hits))

            answer = r["answer"]                       # round 1 = Stage-1 answer (reused)
            rounds = [{"round": 1, "answer": answer}]
            # blind self-assessment of round 1
            sa, _ = gen(SELFASSESS_SYS,
                        f"REFERENCE CONTEXT:\n{block}\n\nQUESTION: {r['question']}\n\nANSWER:\n{answer}",
                        seed, max_tokens=4)
            rounds[0]["self_complete"] = sa.upper().startswith("YES")

            for rd in range(2, 2 + a.refine_rounds):
                crit, e1 = gen(CRITIQUE_SYS,
                               f"REFERENCE CONTEXT:\n{block}\n\nQUESTION: {r['question']}\n\nDRAFT:\n{answer}",
                               seed, max_tokens=220)
                if e1 or not crit:
                    fails += 1
                    rounds.append({"round": rd, "answer": answer, "critique": "", "error": e1})
                    continue
                if crit.strip().upper().startswith("COMPLETE"):
                    rounds.append({"round": rd, "answer": answer, "critique": crit,
                                   "no_change": True, "self_complete": True})
                    continue
                new, e2 = gen(REFINE_SYS,
                              f"REFERENCE CONTEXT:\n{block}\n\nQUESTION: {r['question']}\n\n"
                              f"DRAFT:\n{answer}\n\nREVIEW (facts missing from the draft):\n{crit}",
                              seed)
                if e2 or not new:
                    fails += 1
                    rounds.append({"round": rd, "answer": answer, "critique": crit, "error": e2})
                    continue
                answer = new
                sa, _ = gen(SELFASSESS_SYS,
                            f"REFERENCE CONTEXT:\n{block}\n\nQUESTION: {r['question']}\n\nANSWER:\n{answer}",
                            seed, max_tokens=4)
                rounds.append({"round": rd, "answer": answer, "critique": crit,
                               "self_complete": sa.upper().startswith("YES")})

            rec = {**{k: r[k] for k in ("idx", "seed", "question", "reference",
                                        "gold_article_ids", "retrieved_ids", "gold_rank", "gold_retrieved")},
                   "arm": "rag+selfrefine", "retriever": "bge_chunk", "grounding": a.grounding,
                   "prompt_chars": len(block), "rounds": rounds,
                   "answer": answer,          # FINAL answer (fixed-round policy) -> judged
                   "round1_answer": r["answer"],
                   "score": None}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if (n + 1) % 25 == 0:
                print(f"  seed{seed} {n+1}/{len(base)} (fails={fails})")
        f.close()
        print(f"wrote {out_path.name} ({len(base)} records, student_fails={fails})")
    print("next: HF_HUB_OFFLINE=1 python scripts/wixqa_judge.py --glob "
          f"'runs/rag-wixqa/rag_bge_chunk_{a.grounding}_selfrefine*__seed*.jsonl'")


if __name__ == "__main__":
    main()
