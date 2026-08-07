"""Repair records whose student answer came back EMPTY (generation failure).

Why this exists: on 2026-08-06 the Ollama backend crashed mid-run (a native
python.exe fault) and 5 consecutive records in the Stage-1 seed-42 run were
written with `answer: ""`. `wixqa_judge.py` scores an empty answer 0 (a non-
answer), so leaving them in would silently bias that arm DOWNWARD by ~2.5pt.
This regenerates exactly those records, in place, with the identical prompt the
run used (same retriever/grounding/seed), then leaves them for the judge.

Idempotent: records that already have a non-empty answer are untouched.

  HF_HUB_OFFLINE=1 python scripts/wixqa_repair_empty.py \
      --glob 'runs/rag-wixqa/rag_bge_chunk_chunk2400__seed*.jsonl' --grounding chunk2400
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
from scripts.wixqa_run3seed import RAG_SYS, TEMPERATURE, MAX_TOKENS
from scripts.wixqa_run3seed_retriever import GROUNDINGS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", required=True)
    ap.add_argument("--grounding", choices=list(GROUNDINGS), required=True)
    ap.add_argument("--top-k", type=int, default=3)
    a = ap.parse_args()

    files = sorted(glob.glob(a.glob))
    todo = []  # (path, record_index, record)
    for p in files:
        recs = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        for j, r in enumerate(recs):
            if not (r.get("answer") or "").strip():
                todo.append((p, j))
    if not todo:
        print("no empty answers found — nothing to repair")
        return 0
    print(f"found {len(todo)} empty answers across {len(files)} file(s): "
          + ", ".join(f"{Path(p).name}#{j}" for p, j in todo[:10]))

    arts, qa, _, _ = load_data()
    id2art = {x["id"]: x for x in arts}
    budget, centred = GROUNDINGS[a.grounding]
    student = build_client("local", model="qwen2.5:3b")

    by_file = {}
    for p, j in todo:
        by_file.setdefault(p, []).append(j)

    for p, idxs in by_file.items():
        recs = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        # chunk offsets only for the affected questions
        need = [recs[j] for j in idxs]
        qvecs = encode("bge", [r["question"] for r in need], is_query=True) if centred else None
        fixed = 0
        for n, j in enumerate(idxs):
            r = recs[j]
            hits = [id2art[aid] for aid in r["retrieved_ids"]]
            block = "\n\n".join(
                f"[{k+1}] {h.get('title','')}\n"
                f"{window(h, budget, best_chunk_word_offset(h, qvecs[n]) if centred else None)}"
                for k, h in enumerate(hits))
            res = student.chat(
                [{"role": "system", "content": RAG_SYS},
                 {"role": "user", "content": f"REFERENCE CONTEXT:\n{block}\n\nQUESTION: {r['question']}"}],
                temperature=TEMPERATURE, max_tokens=MAX_TOKENS, timeout_s=120, seed=r["seed"])
            if res.text and res.text.strip():
                r["answer"] = res.text
                r["prompt_chars"] = len(block)
                r["repaired"] = True   # provenance: this record was regenerated (§0.1)
                r["score"] = None      # force re-judge
                fixed += 1
                print(f"  repaired {Path(p).name}#{r['idx']} ({len(res.text.split())} words)")
            else:
                print(f"  STILL EMPTY {Path(p).name}#{r['idx']}: {res.error}")
        with open(p, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[{Path(p).name}] repaired {fixed}/{len(idxs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
