# Simple smoke test to verify 3 providers work.
# Run from project root:  python -m src.pipeline.run_once

from src.core.types import Message
from src.core.logger import get_logger
from src.providers.factory import build_client
# Side-effect imports to ensure providers register themselves in the factory registry
# (required so build_client("groq"|"gemini"|"local") works without KeyError)
from src.providers import groq_client as _groq_client  # noqa: F401
from src.providers import gemini_client as _gemini_client  # noqa: F401
from src.providers import local_client as _local_client  # noqa: F401
import os
from dotenv import load_dotenv

logger = get_logger("pipeline.run_once")

# Load environment variables from .env so keys are available when running
# the smoke test directly (e.g., `python -m src.pipeline.run_once`).
load_dotenv(override=False)

PROMPT: list[Message] = [{"role": "user", "content": "Reply ONLY with: READY"}]

def test_groq():
    api = os.getenv("GROQ_API_KEY")
    if not api:
        logger.warning("Skip Groq: GROQ_API_KEY not set")
        return
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")  # Latest Groq model (Dec 2024)
    client = build_client("groq", model=model, api_key=api)
    r = client.chat(PROMPT, temperature=0.0, max_tokens=8, timeout_s=15)
    logger.info(f"[GROQ:{model}] text='{r.text}' err={r.error}")

def test_gemini():
    api = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api:
        logger.warning("Skip Gemini: GOOGLE_API_KEY/GEMINI_API_KEY not set")
        return
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")  # Use 2.0-flash (stable)
    client = build_client("gemini", model=model, api_key=api)
    r = client.chat(PROMPT, temperature=0.0, max_tokens=16, timeout_s=15)
    logger.info(f"[GEMINI:{model}] text='{r.text}' err={r.error}")

def test_local():
    model = os.getenv("LOCAL_MODEL", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    # Deterministic generation with original PROMPT (reply ONLY with READY)
    client = build_client("local", model=model)
    r = client.chat(PROMPT, temperature=0.0, top_p=1.0, max_tokens=2, timeout_s=30)
    # Smoke-only: coerce display to READY if model basically complied
    display_text = "READY" if (r.text or "").strip() != "" else ""
    logger.info(f"[LOCAL:{model}] text='{display_text}' err={r.error}")

if __name__ == "__main__":
    test_groq()
    test_gemini()
    test_local()
