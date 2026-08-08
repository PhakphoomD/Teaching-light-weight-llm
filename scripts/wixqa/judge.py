"""WixQA T3.9 (P3-E): resumable, budget-aware scoring of generated runs.

Scores any record with score==null in the given run file(s) using the EXACT
ADR-030 reference-comparing judge (Groq llama-3.1-8b-instant, JUDGE_SYS reused
from wixqa_baseline.py, temperature 0, max_tokens 8). §0.2-legal for closed
domain: only the JUDGE sees the gold reference; the student stayed blind.

Why a separate resumable pass: Groq's 8b-instant TPD cap (500K) is org-wide and
too small to judge 6×200 answers in one go (todo lesson). This script:
  * self-paces via the GroqClient RateLimiter (RPM/TPM),
  * persists each score to disk immediately (crash/interrupt-safe),
  * STOPS GRACEFULLY on a daily-cap error (ChatResult.error) instead of writing
    nulls — rerun after the daily reset to resume exactly where it left off,
  * is idempotent: already-scored records are skipped.

  HF_HUB_OFFLINE=1 python scripts/wixqa/judge.py --glob 'runs/rag-wixqa/*__seed*.jsonl'
  HF_HUB_OFFLINE=1 python scripts/wixqa/judge.py --file runs/rag-wixqa/rag__seed13.jsonl
"""
import argparse, glob as globmod, json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import src.tlw.providers  # noqa: F401
from src.providers.factory import build_client
from src.tlw.wixqa.prompts import JUDGE_SYS


def judge_one(judge, q, ref, cand):
    """Returns (score:int|None, error:str|None). Mirrors wixqa_baseline.judge_score
    but surfaces the client error so a daily-cap 429 halts (not silently nulls)."""
    msg = [
        {"role": "system", "content": JUDGE_SYS},
        {"role": "user", "content": f"QUESTION:\n{q}\n\nREFERENCE:\n{ref}\n\nCANDIDATE:\n{cand}\n\nScore (0-4):"},
    ]
    r = judge.chat(msg, temperature=0.0, max_tokens=8, timeout_s=60)
    if r.error:
        return None, r.error
    m = re.search(r"[0-4]", r.text)
    return (int(m.group()) if m else None), None


def score_file(path: Path, judge) -> str:
    recs = [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]
    todo = [i for i, d in enumerate(recs) if d.get("score") is None]
    if not todo:
        return f"[{path.name}] already fully scored ({len(recs)} records)"
    print(f"[{path.name}] scoring {len(todo)}/{len(recs)} unscored records ...")

    def flush():
        with path.open("w", encoding="utf-8") as f:
            for d in recs:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")

    done = 0
    for i in todo:
        d = recs[i]
        # empty student answer -> score 0 (a non-answer), no judge call wasted
        if not (d.get("answer") or "").strip():
            d["score"] = 0
            done += 1
            continue
        s, err = judge_one(judge, d["question"], d["reference"], d["answer"])
        if err is not None:
            # one short retry for a transient blip, then stop gracefully
            time.sleep(5)
            s, err = judge_one(judge, d["question"], d["reference"], d["answer"])
        if err is not None:
            flush()
            return (f"[{path.name}] STOPPED at record {i} after {done} scored "
                    f"(judge error, likely TPD cap): {err[:160]}\n"
                    f"   -> {len(todo)-done} remain; rerun after the Groq daily reset to resume.")
        d["score"] = s
        done += 1
        if done % 20 == 0:
            flush()
            print(f"  scored {done}/{len(todo)}")
    flush()
    v = [d["score"] for d in recs if d.get("score") is not None]
    p3 = sum(x >= 3 for x in v) / len(v)
    return f"[{path.name}] DONE: {done} scored; pass@>=3 = {p3:.3f} (n={len(v)})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="single run file to score")
    ap.add_argument("--glob", help="glob of run files to score (in sorted order)")
    ap.add_argument("--judge", default="llama-3.1-8b-instant")
    a = ap.parse_args()

    if not a.file and not a.glob:
        ap.error("pass --file or --glob")
    paths = [Path(a.file)] if a.file else [Path(p) for p in sorted(globmod.glob(a.glob))]
    judge = build_client("groq", model=a.judge)

    for p in paths:
        if not p.is_file():
            print(f"[skip] {p} not found")
            continue
        msg = score_file(p, judge)
        print(msg)
        if "STOPPED" in msg:
            print("Halting remaining files until budget resets.")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
