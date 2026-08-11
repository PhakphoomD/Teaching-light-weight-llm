"""WixQA: end-to-end dose-response run of the winning retriever.

Generates the 3B student's answers grounded on a *chosen retriever's* top-k
articles, at seeds {13,42,123}, so pass-rate can be plotted against retrieval
hit-rate (the dose-response proof). CONFOUND CONTROL: everything is byte-identical
to the MiniLM RAG run EXCEPT which articles the retriever selects —
  * same student (qwen2.5:3b, temp 0.3, seeded), same top-k (3),
  * same grounding format (article title + contents[:900], RAG_SYS),
  * same downstream judge (scripts/wixqa/judge.py, Groq ref-comparing, PASS>=3).
Only `--retriever` changes. Retrieval is seed-independent, so the ranking is
computed ONCE and reused across the 3 seeds. Scores left null (judge separately).

Grounding stays at the ARTICLE level (not the matched chunk) on purpose: the earlier
conditional P(pass|gold retrieved)=0.400 was measured with article grounding, so
holding it fixed is what makes the dose-response prediction testable — the retriever
changes HOW OFTEN gold is retrieved, not the grounding payoff.

  HF_HUB_OFFLINE=1 python scripts/wixqa/run_three_seeds_retriever.py --retriever bge_chunk
  HF_HUB_OFFLINE=1 python scripts/wixqa/run_three_seeds_retriever.py --retriever minilm_chunk --seeds 13 42 123
"""
import argparse, json, os, sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import src.tlw.providers  # noqa: F401
from src.providers.factory import build_client
from src.tlw.wixqa.retrieval import load_data, build_ranked, encode
from src.tlw.wixqa.grounding import GROUNDINGS, window, best_chunk_word_offset
from src.tlw.wixqa.prompts import RAG_SYS, TEMPERATURE, MAX_TOKENS
from src.tlw.wixqa.retrieval import retrieval_record, clear_models

OUT = ROOT / "runs/rag-wixqa"



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--retriever", required=True,
                    help="ladder variant name: minilm_chunk | bge_chunk | bge_whole | ...")
    ap.add_argument("--seeds", type=int, nargs="+", default=[13, 42, 123])
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--grounding", choices=list(GROUNDINGS), default="head900",
                    help="how much/which part of each retrieved article reaches the prompt "
                         "(head900 = T3.11 behaviour)")
    ap.add_argument("--only-gold-retrieved", action="store_true",
                    help="PILOT ONLY: restrict to questions whose gold article was retrieved "
                         "(a labelled diagnostic subset — biases the aggregate, never a headline)")
    ap.add_argument("--tag", default="", help="extra run-file tag")
    ap.add_argument("--no-reuse-retrieval", dest="reuse_retrieval", action="store_false",
                    help="recompute the ranking instead of reusing runs/rag-wixqa/retrieval_log_<retriever>.jsonl")
    a = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    arts, qa, kb_ids, gold = load_data()
    qa = qa[: a.limit]
    id2art = {x["id"]: x for x in arts}

    # --- retrieval: computed ONCE (seed-independent) --------------------------
    cached = OUT / f"retrieval_log_{a.retriever}.jsonl"
    if a.reuse_retrieval and cached.is_file():
        # Reuse the EXACT retrieved article ids from the better-retriever run. This is both
        # faster (skips re-encoding the 6,221-article KB) and stricter confound
        # control: retrieval is then provably identical and the grounding window
        # is the only thing that changed.
        log = {d["idx"]: d for d in (json.loads(l) for l in cached.open(encoding="utf-8"))}
        if len(log) >= len(qa):
            per_q = [(log[i]["retrieved_ids"][: a.top_k], log[i]) for i in range(len(qa))]
            print(f"[{a.retriever}] reusing cached retrieval from {cached.name} ({len(log)} questions)")
        else:
            a.reuse_retrieval = False
    if not a.reuse_retrieval or not cached.is_file():
        out = build_ranked(a.retriever, arts, qa)
        ranked = out[0] if isinstance(out, tuple) else out  # hybrid returns (ranked, dense_name)
        per_q = []
        for i, q in enumerate(qa):
            top_ids = ranked[i][: a.top_k]
            per_q.append((top_ids, retrieval_record(i, q["question"], q.get("article_ids", []), top_ids, [])))

    # matched-chunk offsets — only needed for the chunk-centred groundings
    budget, centred = GROUNDINGS[a.grounding]
    offsets = {}
    if centred:
        print(f"[{a.grounding}] locating the matched chunk inside each retrieved article ...")
        qvecs = encode("bge", [q["question"] for q in qa], is_query=True)
        for i, (top_ids, _) in enumerate(per_q):
            for aid in top_ids:
                offsets[(i, aid)] = best_chunk_word_offset(id2art[aid], qvecs[i])
    # Seed-independent retrieval log. Written ONLY for a full, untagged run —
    # a partial (--limit) or tagged pilot must never clobber the canonical log
    # the analysis depends on (learned the hard way 2026-07-25: a --limit 4 smoke
    # truncated this file to 4 records; it was restorable from the run files).
    hit = sum(1 for _, rr in per_q if rr["gold_retrieved"])
    rl = OUT / f"retrieval_log_{a.retriever}.jsonl"
    if a.limit >= len(qa) and not a.tag:
        with rl.open("w", encoding="utf-8") as f:
            for _, rr in per_q:
                f.write(json.dumps(rr, ensure_ascii=False) + "\n")
        dest = rl.name
    else:
        dest = "(not written — partial/tagged run)"
    print(f"[{a.retriever}] retrieval hit-rate@{a.top_k} = {hit}/{len(qa)} = {hit/len(qa):.3f}  -> {dest}")

    # free the encoder's GPU memory before Ollama generation runs — the encoder
    # and qwen2.5:3b must not both sit in the 8GB VRAM (contention).
    clear_models()

    # --- generation: seeded student, grounded on top-k ARTICLES ---------------
    student = build_client("local", model="qwen2.5:3b")
    idxs = [i for i in range(len(qa)) if (not a.only_gold_retrieved) or per_q[i][1]["gold_retrieved"]]
    suffix = ("" if a.grounding == "head900" else f"_{a.grounding}") + (f"_{a.tag}" if a.tag else "")
    print(f"[{a.grounding}] generating {len(idxs)} questions/seed"
          + (" (GOLD-RETRIEVED PILOT SUBSET)" if a.only_gold_retrieved else ""))
    for seed in a.seeds:
        out_path = OUT / f"rag_{a.retriever}{suffix}__seed{seed}.jsonl"
        f = out_path.open("w", encoding="utf-8")
        fails = 0
        for i in idxs:
            q = qa[i]
            top_ids, rr = per_q[i]
            hits = [id2art[aid] for aid in top_ids]
            block = "\n\n".join(
                f"[{k+1}] {h.get('title','')}\n"
                f"{window(h, budget, offsets.get((i, h['id'])) if centred else None)}"
                for k, h in enumerate(hits))
            messages = [{"role": "system", "content": RAG_SYS},
                        {"role": "user", "content": f"REFERENCE CONTEXT:\n{block}\n\nQUESTION: {q['question']}"}]
            res = student.chat(messages, temperature=TEMPERATURE, max_tokens=MAX_TOKENS,
                               timeout_s=90, seed=seed)
            ans = res.text
            if res.error or not ans:
                fails += 1
            rec = {"idx": i, "seed": seed, "arm": "rag", "retriever": a.retriever,
                   "grounding": a.grounding, "prompt_chars": len(block),
                   "question": q["question"], "reference": q["answer"], "answer": ans, "score": None,
                   "gold_article_ids": rr["gold_article_ids"], "retrieved_ids": rr["retrieved_ids"],
                   "gold_rank": rr["gold_rank"], "gold_retrieved": rr["gold_retrieved"]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if (idxs.index(i) + 1) % 50 == 0:
                print(f"  seed{seed} gen {idxs.index(i)+1}/{len(idxs)} (fails={fails})")
        f.close()
        print(f"wrote {out_path.name} ({len(idxs)} records, score=null, student_fails={fails})")
    print(f"next: score with  scripts/wixqa/judge.py --glob 'runs/rag-wixqa/rag_{a.retriever}{suffix}__seed*.jsonl'")


if __name__ == "__main__":
    main()
