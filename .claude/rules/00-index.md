# SSOT Index — Teaching-Lightweight-LLM

Navigation + Constitution for the project. **Read this first every session.** All durable
truth lives under `.claude/rules/`. Agents cite authority by anchor, e.g. `00-index §0.2`
or `decisions.md ADR-003` or `rubric.md D3`.

---

## §0 Constitution (non-negotiable — cite these)
- **§0.1 Honesty over optics.** Every reported number must match its source log/data file. No inflated, outdated, or hand-tuned metrics. Weak results are reported plainly.
- **§0.2 No ground-truth leakage in evaluation.** The student/eval path must never see the reference answer. Teacher-sees-GT is allowed only for feedback / training-data generation — never for *measuring* learning.
- **§0.3 Reproducible.** Deterministic, seeded, single-command, documented — so others can follow.
- **§0.4 Evidence-backed.** Every claim/finding cites something actually read (file:line) or run (command + output). No reporting what you did not open.
- **§0.5 Environment.** Run Python **only** via the full path `C:\Users\ham25\.conda\envs\tlw\python.exe`. The bare `python` alias is the Windows Store stub.
- **§0.6 Approved principles are frozen.** Do not change §0 or any accepted ADR yourself. If you believe one should change, raise a finding "needs user approval" — never edit it unilaterally.

---

## Read order
1. `structure.md` — canonical repo layout (what goes where; what counts as junk)
2. `agents.md` — the specialist team, archetypes, and who owns what
3. `todo.md` — current roadmap and the active workstream
4. `decisions.md` — the ADR log (why things are the way they are)
5. `schema.md` — data contracts *(auto-loads under `data/`, `scripts/`, `tools/`)*
6. `rubric.md` — dataset readiness rubric *(auto-loads under `data/`, `scripts/`, `tools/`)*
7. `providers.md` — Groq + Ollama models, free-tier limits, and the §0.2 judge≠student rule

## Fast facts
- Dataset = **MedQuAD** (NIH, CC BY 4.0). "GHR" = Genetics Home Reference, *not* growth hormone receptor.
- Goal = small local open-source LLM, deep in ONE domain, for small businesses.
- Path = (A) honest research ablation proving the loop, then (B) RAG + LoRA product.
- Hardware = RTX 4060 Laptop 8GB VRAM + 64GB RAM. Python env = conda `tlw`.

## Where things live
| What | Where |
|---|---|
| Project instructions | `.claude/CLAUDE.md` |
| Rules / SSOT | `.claude/rules/` |
| Agent team | `.claude/agents/` |
| Permissions + hook registration | `.claude/settings.json` (ADR-012) |
| Constitution guard hook | `.claude/hooks/guard.py` — enforces §0.5 + immutable dirs |
| Project skills | `.claude/skills/` — `run-pipeline`, `reconcile-numbers`, `new-adr` |
| Existing code | `src/`, `scripts/`, root `*.py` |
| Dataset tooling | `tools/dataset/` |
| Data (raw = immutable) | `data/Medical_Q&A/`, `data/medical_by_source/`; cleaned → `data/clean/` |
| Experiment logs | `logs/experiments/` |
| Long-form analysis | `docs/` |
