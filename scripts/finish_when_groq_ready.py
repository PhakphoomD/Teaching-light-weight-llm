"""Wait for Groq's daily cap to reset, then finish the two Groq-blocked tasks
(user decisions 2026-07-17): (1) re-judge the corrupted 7B runs on a single
consistent Groq judge, (2) test the strong-reasoner (70B) selective-RAG gate.

Polls a tiny Groq call until it succeeds (cap reset), then runs, in order:
  1. scripts/rag/rejudge.py --only-nulls   -> re-judge the null-corrupted 7B runs
     (8b-instant pool; --only-nulls is idempotent/resumable if it partially fails)
  2. scripts/rag/selective_simulation.py --gate groq:llama-3.3-70b-versatile --seed 42
     (separate 70B pool; 125 calls fit its 100K TPD)
  3. python -m src.tlw.analysis --runs-dir runs_rag --rag  -> the clean 4-arm table

Runs unattended in the background across the reset. Idempotent enough to re-launch.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import src.tlw.providers  # noqa: E402,F401
from src.providers.factory import build_client  # noqa: E402
from src.tlw.evaluation.judge import BlindJudge  # noqa: E402

PY = sys.executable
ENV = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
POLL_SECONDS = 1200
MAX_WAIT_HOURS = 16


def groq_ready() -> bool:
    try:
        j = BlindJudge(client=build_client("groq", model="llama-3.1-8b-instant"), pass_threshold=1.0)
        r = j.score("What is diabetes?", "Diabetes is a disease of high blood sugar.", mode="blind")
        return r.get("error") is None and r.get("score") is not None
    except Exception as e:  # noqa: BLE001
        print(f"[finish] probe error: {e}", flush=True)
        return False


def run(cmd) -> int:
    print(f"[finish] $ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=ROOT, env=ENV).returncode


def main() -> int:
    deadline = time.time() + MAX_WAIT_HOURS * 3600
    while time.time() < deadline:
        if groq_ready():
            print("[finish] Groq is ready — proceeding.", flush=True)
            break
        print(f"[finish] Groq still capped; sleeping {POLL_SECONDS//60} min.", flush=True)
        time.sleep(POLL_SECONDS)
    else:
        print("[finish] timed out waiting for Groq reset.", flush=True)
        return 1

    # 1. re-judge the null-corrupted 7B runs on one consistent Groq judge
    run([PY, "scripts/rag/rejudge.py", "--runs-dir", "runs_rag", "--pattern", "trackB_p3_7b*",
         "--judge", "groq:llama-3.1-8b-instant", "--pass-threshold", "1.0", "--only-nulls"])
    # 2. strong-gate (70B) selective-RAG test on one seed (fits the 70B 100K TPD)
    run([PY, "scripts/rag/selective_simulation.py", "--runs-dir", "runs_rag",
         "--corpus", "indexes/medquad-diabetes-train", "--gate", "groq:llama-3.3-70b-versatile", "--seed", "42"])
    # 3. the clean 4-arm RAG table
    run([PY, "-m", "src.tlw.analysis", "--runs-dir", "runs_rag", "--rag"])
    print("[finish] DONE — inspect the 4-arm table + selective result above.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
