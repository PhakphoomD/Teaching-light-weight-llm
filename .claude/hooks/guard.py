"""PreToolUse guard — enforces the parts of the Constitution that can be automated.

Registered in .claude/settings.json. Reads the hook JSON from stdin.
Exit 0 = allow (normal permission flow), exit 2 + stderr = block and tell Claude why.

Enforces:
  - 00-index §0.5: Python runs through this project's environment, never a bare
    `python`/`pip` (on Windows that resolves to the Store stub, or to whichever
    interpreter happens to be first on PATH).
  - structure.md:   raw data dirs are immutable; experiment logs are evidence (§0.1) and
    must never be edited by hand.
"""
import json
import os
import re
import shutil
import sys


def project_interpreter() -> str:
    """The interpreter this project's commands should name, on this machine.

    Resolved rather than written down, so the guard is correct in any checkout.
    `TLW_PYTHON` wins when set; otherwise the interpreter running this hook is
    the right answer, because Claude Code launches the hook with the project's
    own Python.
    """
    return (
        os.environ.get("TLW_PYTHON")
        or sys.executable
        or shutil.which("python")
        or "python"
    )

# Paths (relative, forward- or back-slash) that no file tool may modify.
PROTECTED = [
    r"data[/\\]Medical_Q&A[/\\]",       # raw MedQuAD CSVs — immutable
    r"data[/\\]medical_by_source[/\\]", # derived per-domain JSONL — treat as raw
    r"logs[/\\]experiments[/\\]",       # experiment evidence — §0.1, write via runs only
]

# `python`/`python3`/`pip` in COMMAND POSITION only: start of command or right after a
# separator (; && || |) — so full paths (C:\...\python.exe) and the word "python" inside
# strings/arguments still pass. Deliberately narrow: better a rare miss than constant
# false blocks.
BARE_PY = re.compile(r"(?:^\s*|[;&|]\s+|&&\s*|\|\|\s*)(python3?|pip)(?:\.exe)?(?=\s|$)", re.IGNORECASE)


def block(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # malformed input — never block on our own bug

    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}

    if tool in ("Bash", "PowerShell"):
        cmd = tool_input.get("command") or ""
        m = BARE_PY.search(cmd)
        if m:
            py = project_interpreter()
            block(
                f"BLOCKED by .claude/hooks/guard.py (00-index §0.5): a bare "
                f"`{m.group(1)}` does not reliably resolve to this project's "
                f"environment. Name this machine's interpreter in full:\n"
                f'  & "{py}" <args>\n'
                f'  & "{py}" -m pip <args>\n'
                f"Print it with: conda run -n tlw python -c "
                f"\"import sys; print(sys.executable)\"  (or set TLW_PYTHON)."
            )
        # Bash writing into protected dirs (>, >>, cp/mv/rm/sed -i targeting them).
        # `>>?(?!&)` matches real file redirects but NOT fd-duplication like `2>&1`
        # (the `>` there is immediately followed by `&`) — keeps read-only commands that
        # merely redirect stderr from being false-blocked. Deliberately narrow.
        if re.search(r"(>>?(?!&)|\b(rm|mv|cp|sed|tee)\b)[^\n]*" + "(" + "|".join(PROTECTED) + ")", cmd, re.IGNORECASE):
            block(
                "BLOCKED by .claude/hooks/guard.py (structure.md): this command appears to "
                "modify an immutable/evidence directory (raw data or logs/experiments). "
                "Derive forward into data/clean/ instead; logs are written by experiment runs only."
            )

    elif tool in ("Edit", "Write", "NotebookEdit"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        for pat in PROTECTED:
            if re.search(pat, path, re.IGNORECASE):
                block(
                    f"BLOCKED by .claude/hooks/guard.py (structure.md / §0.1): `{path}` is in an "
                    "immutable or evidence directory. Raw data is never edited — derive into "
                    "data/clean/. Experiment logs are only written by actual runs."
                )

    sys.exit(0)


if __name__ == "__main__":
    main()
