# Teaching Lightweight LLMs — project instructions

A measurement study: which interventions actually make a 3-billion-parameter local model better at
one specialised domain, and which only appear to. Nine were tried across two testbeds; the finished
result is in `README.md` and `docs/EXPERIMENT_RESULTS.md`. The research is complete — work now is
maintenance, verification, and presentation.

## Start here

Durable truth lives in `.claude/rules/`. **Read `.claude/rules/00-index.md` first**, then the rule it
points to. When a decision is made, log it in `decisions.md`; when work moves, update `todo.md`.

Two of the rule files load only when you touch the code they govern (`paths:` frontmatter), so if a
data contract or a model choice looks undocumented, open the file rather than assuming it is absent.

## Constitution — the six rules everything else answers to

Canonical text and full wording: `.claude/rules/00-index.md` §0. Summarised here so that no session
starts without them.

- **§0.1 Honesty over optics** — every number must match its source log. Weak results are reported plainly.
- **§0.2 No ground-truth leakage in evaluation** — the student and the scorer never see the reference;
  a teacher may see it only to generate feedback or training data, never to measure.
- **§0.3 Reproducible** — deterministic, seeded, one documented command.
- **§0.4 Evidence-backed** — cite a file and line you opened, or a command and its output.
- **§0.5 Environment** — run Python **only** through this project's `tlw` environment, named by its full path on this machine (`conda run -n tlw python -c "import sys; print(sys.executable)"` prints it). A bare `python` is the Windows Store stub.
- **§0.6 Approved principles are frozen** — do not edit §0 or an accepted ADR. Raise
  "needs user approval" instead.

## The specialist agents

Eight subagents in `.claude/agents/`; roster and ownership in `.claude/rules/agents.md`. Route by
subject: data → `data-engineer` · prompts → `prompt-engineer` · environment and GPU → `ops-engineer` ·
tests, verification and statistics → `qa-engineer` · refactoring → `codebase-steward` · design and
technology choices → `program-architect` · planning and the rule files → `project-coordinator` ·
layout audits → `housekeeping`. Questions for the user stay in the main thread; subagents cannot ask.

## Environment

- **Python** — the `tlw` conda environment (`environment.yml` + `requirements.txt`). Per §0.5, invoke it
  by full path inside this repository, because a bare `python` on Windows is the Store stub.
  Published documentation uses `python` because it addresses a reader who has already activated
  the environment; both mean the same interpreter.
- **Shell** — Windows PowerShell, with the Bash tool also available. They take different syntax.
- **Hardware** — RTX 4060 Laptop, 8 GB VRAM, 64 GB RAM. Comfortable for 1–3B; 4-bit QLoRA reaches 7–8B.
- **Data** — MedQuAD (NIH, CC BY 4.0) and WixQA (MIT). Raw files under `data/Medical_Q&A/` are
  immutable and the guard hook enforces it. Licence terms and what was changed: `NOTICE.md`.

## The commands that matter

`PY` below is this machine's `tlw` interpreter, printed by
`conda run -n tlw python -c "import sys; print(sys.executable)"` (§0.5).

| To do this | Run |
|---|---|
| One experiment | `$env:EXPERIMENT_PARAMS_SEED="42"; & PY run.py --config experiments/teaching-loop/1-baseline.yml` |
| Reproduce the teaching-loop headline | `& PY -m src.tlw.analysis --runs-dir runs/teaching-loop-medquad --comparison C-B --comparison B-A` |
| Reproduce the retrieval headlines | `& PY scripts/wixqa/analyze_three_seeds.py` · `& PY scripts/wixqa/analyze_dose_response.py` |
| Regenerate every figure and table | `& PY scripts/make_figures.py` |
| The test suite | `& PY -m pytest tests/ -q` |
| Rebuild the cleaned dataset | `& PY -m tools.dataset.cli --all` (or the `run-pipeline` skill) |
| Rebuild what a clone lacks | `& PY scripts/dataset/fetch_wixqa.py` · `& PY -m tools.rag.cli` |

The seed is the run's identity and comes from the environment, so one config file drives all of its
pre-registered seeds. Set `HF_HUB_OFFLINE=1` for anything that embeds text.

## Enforcement

Rules that matter are machinery, not reminders (ADR-012).

- **`.claude/settings.json`** — denies edits to raw data, `logs/experiments/` and `.env`; registers
  the guard hook. Machine-specific values belong in `settings.local.json`, which is gitignored.
- **`.claude/hooks/guard.py`** — a `PreToolUse` hook. Blocks a bare `python`/`pip` (§0.5) and any write
  into an immutable or evidence directory, exiting 2 with the rule it enforced. If it blocks you,
  follow its message; never work around it.
- **`.claude/skills/`** — `run-pipeline` (a reproducible cleaner run), `reconcile-numbers` (the §0.1
  audit of published numbers against their logs), `new-adr` (record a decision per §0.6).

<!-- Keep this file short; Claude Code's guidance is under ~200 lines. Detail belongs in
     .claude/rules/, where schema.md, rubric.md, providers.md and todo.md are path-scoped and load
     only for the work they govern. -->
