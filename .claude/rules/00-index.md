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
- **§0.5 Environment.** Run Python **only** through this project's `tlw` environment, named by its full path on the machine you are on — never a bare `python`, which resolves to the Windows Store stub or to whichever interpreter is first on PATH. Print the path once with `conda run -n tlw python -c "import sys; print(sys.executable)"` and use it verbatim; `README.md` §Install has the full procedure.
- **§0.6 Approved principles are frozen.** Do not change §0 or any accepted ADR yourself. If you believe one should change, raise a finding "needs user approval" — never edit it unilaterally.

---

## The rule files, and when each one reaches you

Four load at the start of every session. Four carry `paths:` frontmatter and load only when you open
a file they govern, which is why a session that never touches `data/` never pays for the data
contracts. Add `paths:` to anything new that is only relevant somewhere specific.

**Always loaded**

1. `00-index.md` — this file: the Constitution, and where everything is
2. `agents.md` — the specialist team and who owns what
3. `structure.md` — the canonical repository layout, regenerated from the executed tree
4. `decisions.md` — the ADR log: why each thing is the way it is

**Loaded on demand**

5. `schema.md` — data contracts and the six-slot experiment config — under `data/`, `scripts/`, `tools/`, `logs/`, `src/`
6. `rubric.md` — the dataset readiness rubric — under `data/`, `scripts/`, `tools/`
7. `providers.md` — model roster, free-tier limits, the §0.2 judge≠student rule — wherever a client is built
8. `todo.md` — the dated work log, every box ticked — under `.claude/` and `docs/plan/`

## Fast facts
- Testbeds = **MedQuAD** (NIH, CC BY 4.0) and **WixQA** (Wix help centre, MIT). "GHR" is Genetics
  Home Reference, *not* growth hormone receptor — a mislabelled source directory, left as published.
- Question = which interventions genuinely improve a small local model in one domain, and which only
  appear to. Answered: `docs/EXPERIMENT_RESULTS.md`.
- Status = research complete; the work now is maintenance, verification and presentation.
- Hardware = RTX 4060 Laptop, 8 GB VRAM, 64 GB RAM. Python environment = conda `tlw`.

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
| Published results | `README.md`, `docs/EXPERIMENT_RESULTS.md` |
| Committed evidence behind every number | `reports/` |
