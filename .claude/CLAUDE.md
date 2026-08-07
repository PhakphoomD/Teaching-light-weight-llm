# Teaching-Lightweight-LLM — Project Instructions

Built with Llama. An iterative teacher–student system for small LLMs, being rebuilt into an **honest research result + a RAG/LoRA product** (small local model, deep in one domain, for small businesses).

## Start here
The Single Source of Truth is `.claude/rules/` (auto-loaded). **Read `.claude/rules/00-index.md` first**, then the rule it points you to for the task at hand. Keep the SSOT current — when a decision is made, log it in `decisions.md`; when work moves, update `todo.md`.

## Golden rules — Constitution (canonical: `.claude/rules/00-index.md` §0)
- **§0.1 Honesty over optics** — numbers must match their source log; no inflation.
- **§0.2 No ground-truth leakage in evaluation** — student/eval never sees the reference; teacher-sees-GT only for feedback/data-gen.
- **§0.3 Reproducible** — deterministic, seeded, single command, documented.
- **§0.4 Evidence-backed** — cite what you actually read (file:line) or ran (command+output).
- **§0.5 Environment** — run Python **only** via `C:\Users\ham25\.conda\envs\tlw\python.exe`.
- **§0.6 Approved principles are frozen** — don't edit §0 or an Accepted ADR; flag "needs user approval".

## Agent team
Specialists live in `.claude/agents/` (roster + ownership in `.claude/rules/agents.md`). Route work: data → `data-engineer`, prompts → `prompt-engineer`, env/GPU → `ops-engineer`, tests/verify → `qa-engineer`, refactor → `codebase-steward`, design → `program-architect`, planning/SSOT → `project-coordinator`, structure audit → `housekeeping`. User-facing questions/approvals stay with the main thread.

## Environment
- Python: **always** `C:\Users\ham25\.conda\envs\tlw\python.exe` (§0.5). The bare `python` alias is the Windows Store stub.
- Shell: Windows + PowerShell (Bash tool also available).
- GPU: RTX 4060 Laptop 8GB VRAM + 64GB RAM (QLoRA 4-bit ok for 7–8B; 1–3B comfortable).
- Dataset: MedQuAD (NIH, CC BY). Raw CSVs in `data/Medical_Q&A/` are immutable.

## Key commands (always the full-path python — §0.5)
Shorthand below: `PY` = `C:\Users\ham25\.conda\envs\tlw\python.exe`.
- Run an experiment: `$env:EXPERIMENT_PARAMS_SEED="42"; & PY run.py --config experiments/teaching-loop/1-baseline.yml`
  (the seed is the run's identity and comes from the environment, so one config drives all its seeds)
- Reproduce a headline: `& PY -m src.tlw.analysis --runs-dir runs/teaching-loop-medquad --comparison C-B --comparison B-A`
- WixQA analyses: `& PY scripts/wixqa_analyze.py` · `& PY scripts/wixqa_dose_analyze.py`
- Tests: `& PY -m pytest tests/ -q`
- Clean dataset: `& PY -m tools.dataset.cli --all` (or invoke the `run-pipeline` skill)
- Rebuild what a clone lacks: `& PY scripts/dataset/fetch_wixqa.py` · `& PY -m tools.rag.cli`

## Enforcement & skills (ADR-012)
- `.claude/settings.json` — permission rules (deny edits to raw data, `logs/experiments/`, `.env`) + registers the guard hook.
- `.claude/hooks/guard.py` — PreToolUse guard: blocks bare `python`/`pip` (§0.5) and writes into immutable/evidence dirs. If it blocks you, follow its message — never work around it.
- `.claude/skills/` — project skills: `run-pipeline` (reproducible cleaner run), `reconcile-numbers` (§0.1 docs-vs-logs audit), `new-adr` (log decisions per §0.6).

<!-- Keep this file under ~200 lines. Detailed specs live in .claude/rules/ (schema.md, rubric.md are path-scoped to data work). -->
