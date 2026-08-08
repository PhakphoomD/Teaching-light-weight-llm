"""WixQA baseline de-risk (step 2): does the 3B answer Wix-specific questions
WITHOUT retrieval? If baseline is high -> no knowledge gap -> WixQA is another
saturated testbed (abort). If low -> real gap -> RAG has headroom -> build index.

Student = qwen2.5:3b (Ollama, no context). Judge = Groq llama-3.1-8b-instant
in REFERENCE-COMPARING mode (sees question+gold+candidate). This is a gt_comparing
judge, legitimate for closed-domain: the STUDENT stays blind (never sees gold),
only the JUDGE sees gold to score. Not the Track-A blind judge (which can't verify
proprietary product facts). Standalone — does NOT touch the framework.

  python scripts/wixqa/run_baseline.py --limit 200
"""
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import src.tlw.providers  # noqa: registers Ollama under "local"
from src.providers.factory import build_client

QA = ROOT / "data/external/wixqa/expertwritten.jsonl"

JUDGE_SYS = (
    "You are a strict QA grader for a website-builder (Wix) customer-support assistant. "
    "You are given a QUESTION, the REFERENCE answer (ground truth), and a CANDIDATE answer. "
    "Rate how well the CANDIDATE matches the factual content of the REFERENCE on a 0-4 scale:\n"
    "4 = fully correct AND complete (all key facts from the reference present, none wrong)\n"
    "3 = correct but missing a minor detail\n"
    "2 = partially correct but missing a key fact or slightly wrong\n"
    "1 = mostly wrong or generic non-answer\n"
    "0 = wrong or refuses\n"
    "Judge ONLY against the reference (it is the truth for this product). "
    "Reply with ONLY the single digit."
)

def judge_score(judge, q, ref, cand):
    msg = [
        {"role": "system", "content": JUDGE_SYS},
        {"role": "user", "content": f"QUESTION:\n{q}\n\nREFERENCE:\n{ref}\n\nCANDIDATE:\n{cand}\n\nScore (0-4):"},
    ]
    r = judge.chat(msg, temperature=0.0, max_tokens=8, timeout_s=60)
    m = re.search(r"[0-4]", r.text)
    return int(m.group()) if m else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    a = ap.parse_args()

    recs = [json.loads(l) for l in QA.open(encoding="utf-8")][: a.limit]
    student = build_client("local", model="qwen2.5:3b")
    judge = build_client("groq", model="llama-3.1-8b-instant")

    scores, fails = [], 0
    out = ROOT / "runs/rag-wixqa"; out.mkdir(exist_ok=True)
    log = (out / "baseline_norag.jsonl").open("w", encoding="utf-8")
    for i, r in enumerate(recs):
        q, ref = r["question"], r["answer"]
        try:
            ans = student.chat(
                [{"role": "system", "content": "You are a helpful Wix customer-support assistant. Answer the user's question concisely and accurately."},
                 {"role": "user", "content": q}],
                temperature=0.3, max_tokens=256, timeout_s=60,
            ).text
        except Exception as e:
            ans = ""; fails += 1; print(f"[{i}] student err: {e}")
        s = judge_score(judge, q, ref, ans)
        scores.append(s)
        log.write(json.dumps({"idx": i, "question": q, "answer": ans, "reference": ref, "score": s}, ensure_ascii=False) + "\n")
        if (i + 1) % 20 == 0:
            valid = [x for x in scores if x is not None]
            print(f"  {i+1}/{len(recs)}  pass@>=4={sum(x>=4 for x in valid)/len(valid):.3f}  pass@>=3={sum(x>=3 for x in valid)/len(valid):.3f}")
    log.close()

    valid = [x for x in scores if x is not None]
    n = len(valid)
    print("\n=== WixQA baseline (3B, NO RAG) ===")
    print(f"n={n}  student_fails={fails}  judge_nulls={len(scores)-n}")
    print(f"pass@>=4 (correct+complete): {sum(x>=4 for x in valid)}/{n} = {sum(x>=4 for x in valid)/n:.3f}")
    print(f"pass@>=3 (correct):          {sum(x>=3 for x in valid)}/{n} = {sum(x>=3 for x in valid)/n:.3f}")
    print(f"mean score: {sum(valid)/n:.2f}")
    from collections import Counter
    print("score dist:", dict(sorted(Counter(valid).items())))

if __name__ == "__main__":
    main()
