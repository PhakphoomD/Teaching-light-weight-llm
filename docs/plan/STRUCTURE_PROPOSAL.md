# Repo Structure Audit + Redesign Proposal

**Version 2** (2026-08-07) — revised after the user rejected v1's naming convention.
**Status:** PROPOSAL — nothing has been moved, renamed or deleted. Requires user approval.
**Author:** housekeeping (audit, read-only). **Output contract:** ADR-008 Archetype R.

**Scope note (§0.6):** two Accepted ADRs are touched and I do **not** propose editing them.
`ADR-017` fixed the `structure.md` v2 tree; `ADR-023` fixed `runs/<run_id>/` as the run-output
location. Each needs a **new superseding ADR**, decided by the user. Both flagged in §D phase 0.

---

## What changed in v2 (the diff in reasoning)

The user's verdict on v1's naming: the names are still hard for a real person to read.
The example that failed —
`runs/wixqa-rag/rag-bge_chunk-chunk2400-selfrefine-goldonly-pilot/seed42.jsonl` —
fails for four reasons I now accept as correct:

1. **"chunk" appears twice meaning two different things** (retriever chunking vs grounding-window
   size). Unparseable from outside the project.
2. **Mixed separators carrying meaning** (hyphen between dimensions, underscore inside a value) is
   a rule the reader must be *taught*. A rule that must be taught is not readable.
3. **The path tried to encode the whole experimental condition.** That was the root error.
4. **`goldonly`, `pilot`, `bge_chunk`, `chunk2400`** are internal vocabulary with no explanation at
   the point of use.

### The governing rule now

> **A name must read like English to someone who has never seen this repo.**
> If understanding a name requires knowing what `bge_chunk` or `chunk2400` means, the name failed.

### What v2 does differently

| v1 | v2 |
|---|---|
| Path encodes the full condition | **Path is a short English label; the full condition lives in a `manifest.json` inside the directory.** |
| Hyphen between dimensions, underscore inside values | **One rule, stated once: hyphens for folders and artifacts, underscores for `.py` files (PEP 8 — the language's own rule, not ours).** |
| "no stage ordinals" | **Ordinals where the runs form a real progression** (the WixQA ladder tells a story); **no ordinals where the design is factorial** (the 2×2 RAG arms) — §C.3 explains why the distinction is principled, not aesthetic. |
| `bge_chunk`, `chunk2400`, `goldonly` | `better-retriever`, `wider-context`, and "gold-retrieved subset" moved into the manifest |
| Arms named `armA`…`armD` (left alone) | `baseline`, `self-refine`, `teacher-feedback`, `teacher-sees-answer` |
| Before→after for WixQA only | **Before→after for every run directory in all nine roots** (§C.4) |
| `tlw` not examined | **Examined with real numbers; recommendation = keep it and document it in one line** (§C.7) |
| `tests/` one MINOR line | **Full audit — §C.8, finding 18** |
| "root-level clutter" implied | **Corrected: the repo root is clean** (4 files). The clutter is in `scripts/`, `runs*/`, `data/` root. |

Section A (inventory) and findings 1–15 are unchanged from v1 except where noted.
§B, §C and §D are revised; findings 17 and 18 are new.

---

## VERDICT: **FAIL**

Not because the codebase is bad — `src/tlw/` is clean and well tested, and (a v2 correction) the
**repo root is genuinely tidy**: only `README.md`, `run.py`, `requirements.txt`, `environment.yml`
plus dotfiles. It fails because **the canonical structure document no longer describes the
repository**, and because the experiment layer that grew during P3 — 9 output roots, 31 flat
scripts — is named in a private vocabulary nobody outside the project can read.

---

## FINDINGS (heaviest first)

### [BLOCKER] 1 — `structure.md` (the canonical layout SSOT) is materially false

- **evidence:** `.claude/rules/structure.md:38,71,72,73,77,78` list as present:
  `config/simplified_config.yml`, `src/simplified/`, `src/prompts/`, `src/eval/`,
  `simplified_teaching_loop.py`, `simplified_experiment_runner.py`. On disk: all five sources
  **GONE**; `src/simplified/` and `src/prompts/` survive only as `__pycache__`-only shells
  (finding 10). §B omits, though all exist: the 9 root run directories, `data/rag/`,
  `data/wixqa/`, `data/processed/`, `data/calibration/`, `tools/rag/`, `src/tlw/analysis/`,
  `src/tlw/providers.py`, `config/prompts/`, `config/archive/`, `docs/archive/`. §B lists 5
  "(planned)" dirs never created and no longer needed: `reports/`, `db/`, `data/interim/`,
  `docs/adr/`, `app/`.
- **why:** `00-index.md` read-order #1; `structure.md:3` calls itself the source of truth for
  housekeeping *and every P2/P3 build task*. A false map silently authorises misplacement — which
  is exactly what happened. `docs/audit/CODE_MAP.md:3-11` predicted it: *"A full re-audit against
  structure.md v2 is a P3 housekeeping follow-up."*
- **fix:** rewrite to v3 per §B, under a new ADR superseding ADR-017's tree (§0.6 — do not edit
  ADR-017). — owner: **program-architect** + **project-coordinator**.

### [BLOCKER] 2 — 13 result-producing scripts hardcode an absolute machine path

- **evidence:** identical literal
  `ROOT = Path("C:/Users/ham25/Desktop/Torrens_Assessment/ITA602/Teaching-light-weight-llm-based-project")`
  at `scripts/wixqa_analyze.py:21`, `wixqa_baseline.py:16`, `wixqa_build_index.py:17`,
  `wixqa_dose_analyze.py:23`, `wixqa_grounding_compare.py:24`, `wixqa_grounding_ladder.py:34`,
  `wixqa_judge.py:22`, `wixqa_rag.py:17`, `wixqa_repair_empty.py:20`,
  `wixqa_retriever_ladder.py:32`, `wixqa_run3seed.py:32`, `wixqa_run3seed_retriever.py:26`,
  `wixqa_selfrefine.py:36`. Five siblings use the correct pattern —
  `build_calibration.py:25`, `build_lora_data.py:25`, `eval_lora.py:18`,
  `finish_when_groq_ready.py:21`, `train_lora.py:17` (`Path(__file__).resolve().parents[1]`).
- **why:** §0.3; `structure.md` §F lists hardcoded absolute paths as a junk smell. These produced
  ADR-030…033 — the headline portfolio result cannot be reproduced from a clone.
- **fix:** one-line replacement per file. — owner: **ops-engineer**.

### [MAJOR] 3 — 9 experiment-output roots, no tracking policy, and a README claim that is not true

- **evidence:** `runs/ runs_hardtail/ runs_lora/ runs_orca/ runs_rag/ runs_rag_aspect/
  runs_rag_big/ runs_reliability/ runs_wixqa/` (23.4 MB). `git check-ignore`: `runs/` **IGNORED**
  (`.gitignore:236`), the other eight **NOT** — so `git status` permanently shows 8 `?? runs_*/`.
  `README.md:90`: *"Every number below is computed from a **committed** run log."* `git ls-files`
  = 274 tracked files, none under any `runs*`.
- **why:** §0.1 + §0.4. The pattern `runs/` matches only the directory literally named `runs`,
  which is how the eight siblings leaked out.
- **fix:** one artifact root `runs/<study>/` (§B) + the tracked/ignored split (§C.6) + correct
  `README.md:90`. — owner: **ops-engineer**, **qa-engineer**.

### [MAJOR] 4 — byte-identical duplicate run data between `runs/` and `runs_rag/`

- **evidence:** `md5sum` on all three files of
  `trackA_full_armA_diabetes__seed13__20260715T051042Z` in both roots:
  `config_used.json` `e12d676ab20d…` = `e12d676ab20d…`; `summary.jsonl` `9997bb1e0323…` =
  `9997bb1e0323…`; `rounds.jsonl` `d8415dc48891…` = `d8415dc48891…`. Three run dirs duplicated
  (seeds 13/42/123). Deliberate at the time — ADR-027: *"3B baseline REUSED … copied into
  `runs_rag/` to avoid conflation with the mixed `runs/` dir."*
- **why:** `structure.md` §F duplicated-data rule. The reason for the copy disappears once each
  study owns a directory.
- **fix:** keep one copy; record the reuse in the study README. Do not delete before the RAG
  analysis command is re-verified. — owner: **qa-engineer**.

### [MAJOR] 5 — `scripts/` holds library code imported cross-file from a non-package directory

- **evidence:** 15 cross-imports `from scripts.X import …` at `wixqa_grounding_ladder.py:36`,
  `wixqa_judge.py:28`, `wixqa_rag.py:24`, `wixqa_repair_empty.py:26,27,28,29`,
  `wixqa_run3seed_retriever.py:32,33,34` (+ runtime import at `:117`),
  `wixqa_selfrefine.py:42,43,44,45`. **No `scripts/__init__.py`** — works only by PEP-420
  namespace packaging plus `sys.path.insert`. De-facto libraries: `wixqa_retriever_ladder.py`
  (`chunks_of`, `encode`, `load_data`, `build_ranked` → 4 importers),
  `wixqa_grounding_ladder.py` (`window`, `best_chunk_word_offset` → 3),
  `wixqa_run3seed.py` (`RAG_SYS`, `TEMPERATURE`, `MAX_TOKENS`, `MAX_PASSAGE_CHARS`,
  `retrieval_record` → 4), `wixqa_baseline.py` (`JUDGE_SYS`, `judge_score` → 3).
- **why:** `structure.md` §E — *"Reusable tools → `tools/`; one-off stage scripts → `scripts/`
  (import shared logic from `src/`)"*. The arrow here runs script→script. None of this shared
  logic is covered by `tests/`.
- **fix:** extract to `src/tlw/wixqa/` + a test mirror; leave thin drivers in `scripts/wixqa/`.
  Sequenced last. — owner: **codebase-steward** + **qa-engineer**.

### [MAJOR] 6 — a 553-line doc describing deleted code sits beside the live result reports

- **evidence:** `docs/APPENDIX_PROMPTS_MEMORY_CODE.md:172,263,277` document the memory field
  `teaching_feedback`, retired by ADR-018 and deleted by T2.9. Tracked, at `docs/` top level,
  alphabetically first, next to `RAG_LAW.md`.
- **why:** §0.1 + the 30-second discoverability rule. Precedent exists: T3.13 archived
  `PROJECT_OVERVIEW_AND_RESULTS.md` with a SUPERSEDED banner.
- **fix:** → `docs/archive/` + banner naming ADR-018 and T2.9. — owner: **qa-engineer**.

### [MAJOR] 7 — `README.md` "Project Structure" and "Usage" describe the pre-T2.9 tree

- **evidence:** `README.md:547-581` lists `simplified_teaching_loop.py`,
  `simplified_experiment_runner.py`, `config/simplified_config.yml`, `config/prompts_config.yml`
  and 11 `src/simplified/*.py` modules — all deleted. `:591-592` names
  `notebooks/experiment_redesigned.ipynb`; the file is `notebooks/experiment.ipynb`.
  `:583-586` presents `data/medical_mixed_100.jsonl` / `alpaca_100.jsonl` as the main datasets
  (0 live code references). `:428` shows `simplified_experiment_runner.py` usage. Known and
  deferred — `.claude/rules/todo.md` T3.13 closing note.
- **fix:** regenerate from the approved v3 tree, so it is written once. — owner:
  **project-coordinator**.

### [MAJOR] 8 — a 52 MB external dataset with no documented acquisition step

- **evidence:** `data/external`-shaped content living at `data/wixqa/`:
  `kb_corpus.jsonl` (52,293,710 bytes) + `expertwritten.jsonl` (255,116 bytes), untracked and
  **not** ignored. No fetch script anywhere (`grep load_dataset|Wix/WixQA` across `*.py`); the
  only provenance is prose in ADR-030. Six scripts depend on it (`wixqa_baseline.py:23`,
  `wixqa_build_index.py:21`, `wixqa_rag.py:26`, `wixqa_retriever_ladder.py:35,36`,
  `wixqa_run3seed.py:40`).
- **why:** §0.3 — the WixQA half of the project cannot be reproduced from a clone.
- **fix:** `scripts/dataset/fetch_wixqa.py` recording the HF revision; relocate to
  `data/external/wixqa/`; gitignore. — owner: **data-engineer**.

### [MAJOR] 17 *(new in v2)* — the experiment vocabulary is private, and one word means two things

- **evidence:** the example the user rejected —
  `runs_wixqa/rag_bge_chunk_chunk2400_selfrefine_pilot__seed42.jsonl`. Decoding it required
  reading source: `bge_chunk` = "bge-base-en-v1.5 encoder over 180-word article chunks"
  (`scripts/wixqa_retriever_ladder.py:13,40,194`); `chunk2400` = "2400-character grounding window
  centred on the matched chunk" (`scripts/wixqa_run3seed_retriever.py:43-44`:
  `GROUNDINGS = {"head900": (900, False), … "chunk2400": (2400, True)}`). **The token `chunk`
  therefore carries two unrelated meanings inside one filename.** Same class of problem:
  `armA`…`armD` (`src/tlw/loop/strategies.py:99,120,274,284` — the docstrings say what they
  actually are: *baseline*; *the student critiques its own previous answer*; *an independent
  teacher without seeing GT*; *teacher with GT visible*), `runs_rag_big` (= a 9,798-passage corpus
  vs 414), `runs_hardtail`, `goldonly`, `_s1`/`_s2`.
- **why:** the 30-second discoverability requirement and the user's governing rule. It is also a
  *correctness* risk, not merely cosmetic: a reader who mis-decodes `chunk` mis-attributes the
  project's largest finding (delivery +0.130 vs retriever +0.025 — ADR-033).
- **fix:** §C in full. — owner: **housekeeping** (naming), **ops-engineer** (execution).

### [MAJOR] 18 *(new in v2)* — `tests/` does not fully mirror `src/`, and the mirror it has is uneven

- **evidence:** `tests/rag/test_builder.py:11` imports `from tools.rag.builder import
  RagIndexBuilder` — it tests `tools/rag/` but sits at `tests/rag/`, mirroring nothing.
  `__init__.py` exists in 4 of 10 test directories (`tests/tlw/{analysis,evaluation,loop,prompts}`)
  and is absent in 6 (`tests/`, `tests/rag/`, `tests/tlw/`, `tests/tlw/{config,memory,runner}`).
  `src/tlw/providers.py` has no test module of its own — its tests live inside
  `tests/tlw/runner/test_runner.py:316,329` (`test_local_provider_is_ollama_not_tinyllama`,
  `test_local_provider_reregistration_is_silent_no_raise`), which is also the largest test file
  (30 tests). `tests/conftest.py` exists only to do `sys.path.insert`; pytest 8.4.2 is installed
  (verified with `--version`), so the `pythonpath` ini option can replace it outright.
- **why:** `structure.md` §E — *"Tests mirror `src/tlw/` under `tests/`"*.
- **explicitly NOT a finding — two things are already good and must not be churned:**
  (a) **test names describe behaviour, not modules** — sampled 55 across two files, e.g.
  `test_v2_same_family_rejected`, `test_load_dataset_limit_is_deterministic_prefix`,
  `test_fallback_honors_retry_after_hint_in_error_text`,
  `test_diagnose_round_computed_even_without_params_ground_truth`;
  (b) the four `conftest.py` files are **not** duplicated scaffolding — each has a distinct,
  documented job (root = import path; `tests/tlw/` = registry-registration side effects, with the
  pytest-randomly bug that motivated it written into the comment; `analysis/` = a 163-line
  synthetic run-dir factory; `loop/` = network-free mocks).
- **fix:** §C.8. — owner: **qa-engineer**.

### [MINOR] 9 — analysis outputs stored inside the raw-generation directory, underscore-prefixed

- **evidence:** `runs_wixqa/_s1_full_aggregate.txt` (opened — it is the rendered Stage-1 table:
  `pass@>=3: head900=0.340 … chunk2400=0.470 … McNemar p=3.52e-08`, i.e. the primary evidence for
  ADR-033's `+0.130`), plus `_s1_full_gold.txt`, `_s1_pilot_result.txt`, `_s2_pilot_result.txt`.
  946 bytes, generated, untracked.
- **why:** generated artifacts must not sit next to their inputs; `_s1`/`_s2` are stage ordinals
  and the leading underscore exists only to sort them above the clutter.
- **fix:** `reports/rag-wixqa/…` per §C.4, git-tracked. — owner: **qa-engineer**.

### [MINOR] 10 — ghost package directories containing only stale bytecode

- **evidence:** `find src/simplified` → only `__pycache__/*.pyc` for `memory`, `metrics`,
  `student`, `teacher_feedback`, `early_stopping`, `logger`, `debug_logger`, `monitor`,
  `terminal_ui`, `__init__`; same for `src/prompts/`. Root `__pycache__/` still holds
  `simplified_teaching_loop.cpython-311.pyc` and `simplified_experiment_runner.cpython-311.pyc`.
  Not importable (`__pycache__/x.pyc` without `x.py` cannot be imported) — cosmetic, not a leak.
- **fix:** delete the two empty directories, with user confirmation. — owner: **codebase-steward**.

### [MINOR] 11 — an undocumented sub-experiment: judge boundary calibration

- **evidence:** `scripts/build_calibration.py` + `scripts/calibration_report.py` +
  `data/calibration/boundary_set.jsonl` (119 KB). Zero hits across `docs/`, `README.md`,
  `.claude/rules/`. `build_calibration.py:50` reads `runs_reliability/*/rounds.jsonl`.
- **fix:** a one-paragraph note + a todo line, or archive. Needs a user decision. — owner:
  **project-coordinator** (to ask).

### [MINOR] 12 — a published analysis reports a run as "still running" that has since completed

- **evidence:** `docs/RAG_RELIABILITY_ANALYSIS.md:4` — *"a full-125 × 8-seed sweep
  (`runs_reliability/`) **is running** to firm them up"*; repeated at `:126`. `runs_reliability/`
  holds 16 completed run dirs (8 seeds × 2 arms, 20260721T124338Z–20260721T213449Z). Linked from
  `docs/RAG_LAW.md:343` and `docs/PRODUCT_RESULTS.md:79`.
- **fix:** re-run `reliability_analysis.py` and update, or state plainly that it completed and was
  not analysed. — owner: **qa-engineer**.

### [MINOR] 13 — six legacy loose data files at `data/` root, five with zero live references

- **evidence:** `alpaca_questions.jsonl` (25.0 MB), `medical_all_clean.jsonl` (12.7 MB),
  `medical_mixed_100.jsonl`, `medical_100.jsonl`, `alpaca_100.jsonl`, `alpaca_20.jsonl` — tracked.
  Live-reference grep across `src/ tools/ scripts/ config/ experiments/ tests/ run.py`: 0 hits for
  five, 1 for `medical_all_clean` (already flagged by `structure.md` §F as misnamed).
  `data/__init__.py` (0 bytes) makes the data directory a Python package.
- **fix:** `data/legacy/` + a README line; drop `data/__init__.py` unless something imports it.
  Not deletion — `logs/experiments/phase*` reproducibility may reference them. — owner:
  **data-engineer**.

### [MINOR] 14 — `src/utils/prompt_loader.py` is dead

- **evidence:** only docstring mentions at `src/tlw/prompts/loader.py:3,29` and the file's own
  `:8`. Zero real importers. Already scheduled: `todo.md` T2.9 — *"Left
  `src/utils/prompt_loader.py` + `notebooks/experiment.ipynb` (exploratory, now dead — retire in
  P3 housekeeping)"*.
- **fix:** delete `src/utils/` and `notebooks/experiment.ipynb` (68 cells, 2.2 MB, Phase-0-6 era),
  with user confirmation. — owner: **codebase-steward**.

### [MINOR] 15 — the `src/` layout is emulated, not installed

- **evidence:** no `pyproject.toml`, `setup.py`, `setup.cfg`, `pytest.ini` or `tox.ini` at root.
  Importability comes from `sys.path.insert(0, ROOT)` repeated across ~20 files plus
  `tests/conftest.py:6-8`; packages import as `src.tlw.*`, not `tlw.*`.
- **fix:** **not** a package migration (see §C.7). But a **7-line `pytest.ini`** is worth it — it
  deletes `tests/conftest.py`'s path hack and fixes rootdir ambiguity. — owner: **ops-engineer**.

### [MINOR] 16 — inconsistent `__init__.py` under `tests/` — *folded into finding 18*

---

## NOT VERIFIED

1. **Completeness of all ~70 run directories.** I opened one Track-A run dir, sampled one WixQA
   record, and opened all 8 calibration probes. I did not verify every run. *Needed:*
   `python -m src.tlw.analysis --runs-dir <each>` plus a null-score count per WixQA file.
2. **Whether `docs/` numbers still match their logs.** Out of scope; `todo.md` T3.12 records a
   recent §0.1 reconcile that caught a real drift. *Needed:* the `reconcile-numbers` skill.
3. **Runtime behaviour of the scripts.** Nothing requiring Ollama or Groq was executed. The only
   commands run were `tools.dataset.cli --help` (passed), `pytest --version`, and JSON reads.
4. **Whether `runs_hardtail/` and the two duplicate `runs_orca/` dirs are still wanted.**
   `runs_hardtail/` has **zero** SSOT hits by name. `runs_orca/` holds two directories for the
   same config *and* seed (`…__seed42__20260723T155406Z` and `…__seed42__20260723T155536Z`,
   90 seconds apart) — one is probably a false start, but I did not open both summaries to confirm
   which was reported. *Needed:* a user decision + a `summary.jsonl` diff.
5. **Contents of all 45 files in `docs/plan/`.**
6. **External dependencies on current paths** (shell history, a Streamlit launch command for
   `tools/dataset/app.py`). Only the user knows.
7. **v2-specific:** I did **not** verify by *execution* that renaming run directories leaves
   `src/tlw/analysis` unaffected; I verified it by reading — `discover_runs`
   (`loaders.py:136-151`) is directory-shaped and `group_runs` (`:154-161`) keys off the `arm`
   field inside `summary.jsonl`, not the path. *Needed:* the §D phase-3 verification run before
   trusting it.

---

## EVIDENCE LOG

**Files opened:** `.claude/rules/{00-index,structure,decisions,todo,schema,agents}.md`,
`.claude/settings.json`, `.claude/hooks/guard.py` (grep), `.gitignore`, `README.md:88-149`,
`README.md:537-611`, `docs/audit/CODE_MAP.md:1-12`, `docs/RAG_RELIABILITY_ANALYSIS.md:1-30`,
`docs/plan/README.md:1-40`, `scripts/wixqa_analyze.py:1-60`, `scripts/wixqa_selfrefine.py:1-70`,
`scripts/wixqa_run3seed_retriever.py:43-63`, `scripts/wixqa_retriever_ladder.py:10-40,188-215`,
`tools/rag/cli.py:1-30`, `tests/conftest.py`, `tests/tlw/conftest.py`,
`tests/tlw/analysis/conftest.py:1-12`, `tests/tlw/loop/conftest.py:1-12`,
`tests/rag/test_builder.py:1-12`, `src/tlw/analysis/loaders.py:136-161`,
`src/tlw/loop/strategies.py` (registrations + docstrings), `src/tlw/__init__.py`,
`experiments/trackB_p3_3bRAG_diabetes.yml`, `experiments/trackA_p2_armA_diabetes_orca.yml`,
`environment.yml:6-8`, `.vscode/settings.json`, `runs_wixqa/_s1_full_aggregate.txt`,
`runs_wixqa/_s2_pilot_result.txt`, first record of
`runs_wixqa/rag_bge_chunk_chunk2400__seed42.jsonl`, **all 8 files in `runs/calibration/`**.

**Commands run** (read-only; Python via the §0.5 full path):
```
ls -la ; git status --porcelain ; git ls-files            # 274 tracked, 8 untracked runs_* roots
du -sh runs runs_* data models logs docs                  # runs* 23.4 MB, data 210 MB, models 333 MB, logs 298 MB
md5sum runs/trackA_full_armA_.../{3 files} vs runs_rag/   # identical
git check-ignore -q <10 artifact dirs>                    # runs/ data/rag/ models/ IGNORED; 8 runs_* NOT
grep -rn 'ROOT\s*=\s*Path('  scripts/ tools/ src/ run.py
grep -rn 'C:[\\/]Users[\\/]ham25' --glob *.py             # 13 wixqa scripts + guard.py (legitimate)
grep -rn 'from scripts\.' scripts/*.py                    # 15 cross-imports; no __init__.py
grep -rn 'src\.tlw|src/tlw' --include=*.py | wc -l        # 158 import sites (src 56, tests 69, scripts 28, tools 3, run.py 1)
grep -rl 'tlw' --include=*.py | wc -l                     # 73 files
grep -rc 'tlw' .claude/ config/ docs/ experiments/ README.md   # ~25 non-code files
grep -rno 'docs/(RAG_LAW|TRACK_A_RESULTS|...)\.md' --include=*.md .   # 62 inbound links
grep -rc '^def test_' tests --include=*.py                # 20 test modules, 246 test functions
find tests -type d ; per-dir __init__.py check            # 4 of 10 have it
ls pyproject.toml setup.py setup.cfg pytest.ini tox.ini   # none exist
python -m pytest --version                                # pytest 8.4.2 (pythonpath ini available)
python -c '<read judge_model from each calibration probe>' # 8/8 identified
python -m tools.dataset.cli --help                        # PASSED
ls -p | grep -v /                                         # root = README.md environment.yml requirements.txt run.py
```

---
---

# A. Current-state inventory

*(unchanged from v1 except the two corrections noted in bold)*

## A.1 Top level

| Path | What it is | Written by | Read by | Git | Nature |
|---|---|---|---|---|---|
| `.claude/` | SSOT: CLAUDE.md, rules/, agents/, skills/, hooks/, settings | user + agents | every session | tracked | authored |
| `config/` | `base.yml`, `prompts/{student,teacher}.yml`, `archive/` | ops/prompt-eng | `src/tlw/config` | tracked | authored |
| `data/` | raw MedQuAD + derived + external + indices (210 MB) | see A.3 | pipeline, scripts | mixed | mixed |
| `docs/` | 7 loose reports + `plan/` (45) + `audit/` (3) + `archive/` (1) | agents | user | tracked | authored |
| `experiments/` | 21 run-config YAMLs + README (ADR-016 naming) | ops | `run.py` | 14 tracked, 7 untracked | authored |
| `logs/experiments/phase0..6` | pre-renovation evidence (298 MB) | legacy loop (deleted) | historical | tracked | generated, immutable |
| `models/` | `Llama-3.1-8B-Instruct/` + `lora_diabetes/` (333 MB) | HF, `train_lora.py` | `eval_lora.py` | ignored | generated |
| `notebooks/experiment.ipynb` | 68 cells, 2.2 MB, Phase-0-6 era, dead | user | — | tracked | authored, stale |
| `schemas/log_record.schema.json` | schema for the legacy log record | user | — (no live validator) | tracked | authored |
| `scripts/` | 31 `.py` — see A.2 | agents | user | 7 tracked, 24 untracked | authored |
| `src/` | `core/`, `providers/`, `tlw/` live; `simplified/`, `prompts/`, `utils/` dead | agents | everything | tracked | authored |
| `tests/` | 20 modules, 246 test functions | agents | pytest | mostly tracked | authored |
| `tools/` | `dataset/`, `rag/` | data-eng | CLI + scripts | `dataset/` tracked, `rag/` untracked | authored |
| `runs*/` ×9 | experiment outputs, 23.4 MB — see A.4 | runner + scripts | analysis | 1 ignored, 8 untracked | generated |
| **root files** | **v2 correction — the root is clean: `README.md`, `run.py`, `requirements.txt`, `environment.yml`** | user | — | tracked | authored |
| `__pycache__/`, `.pytest_cache/`, `.vscode/` | tooling residue | tools | — | ignored / `.vscode` tracked | generated |

## A.2 `scripts/` — 31 files, classified

**Reusable libraries wrongly living in `scripts/`** (finding 5): `wixqa_retriever_ladder.py`,
`wixqa_grounding_ladder.py`, `wixqa_run3seed.py`, `wixqa_baseline.py`.

**Load-bearing drivers** (cited by a report or ADR): `wixqa_build_index.py`, `wixqa_rag.py`,
`wixqa_judge.py`, `wixqa_run3seed_retriever.py`, `wixqa_selfrefine.py`, `wixqa_repair_empty.py`,
`wixqa_analyze.py`, `wixqa_dose_analyze.py`, `wixqa_grounding_compare.py`, `build_lora_data.py`,
`train_lora.py`, `eval_lora.py`, `rag_faithfulness.py`, `selective_rag_sim.py`, `rejudge.py`,
`reliability_analysis.py`, `assess_all.py`, `prepare_medical_dataset.py`,
`split_medical_by_source.py`, `compare_judges.py`, `compare_students.py`.
(`wixqa_repair_empty.py` and `wixqa_baseline.py` show 0 literal doc hits only because ADRs cite
them in brace form — `scripts/wixqa_{baseline,build_index,rag}.py` in ADR-030 and
`wixqa_{…,repair_empty}.py` in ADR-033.)

**One-off / superseded / undocumented:** `finish_when_groq_ready.py` (a 2026-07-17 Groq-cap-reset
scheduler with a finished task list hardcoded at `:64-70`), `build_calibration.py` +
`calibration_report.py` (finding 11), `analyze_lhs_strategy.py` + `estimate_cost.py`
(pre-renovation; only `docs/audit/CODE_MAP.md:122-123` cites them), `compare_judges.py` +
`compare_students.py` (produced ADR-011/ADR-014, both since superseded).
**Outright dead: none** — every file has at least a historical citation.

## A.3 `data/` subtrees

| Path | Size | Content | Git | Verdict |
|---|---|---|---|---|
| `data/Medical_Q&A/` | — | 10 raw MedQuAD CSVs | tracked | **immutable**, correct (guard-protected) |
| `data/medical_by_source/` | — | 7 per-domain JSONL + README | tracked | derived-as-raw, correct |
| `data/clean/` | — | 7 `*_clean.jsonl` + reports + Diabetes splits | tracked | correct |
| `data/processed/` | 520 KB | `lora_diabetes_sft.jsonl` + `_CARD.md` | untracked | right place, just uncommitted |
| `data/rag/` | 49 MB | `diabetes_train`, `all_medquad`, `wixqa_kb`, `retriever_ladder` | ignored | generated artifact under `data/` — see §B |
| `data/wixqa/` | 52 MB | external HF dataset | untracked, not ignored | finding 8 |
| `data/calibration/` | 119 KB | `boundary_set.jsonl` | untracked | finding 11 |
| `data/*.jsonl` ×6 | 38 MB | pre-renovation loose data | tracked | finding 13 |
| `data/__init__.py` | 0 B | makes `data/` a package | tracked | vestigial |

`data/rag/retriever_ladder/{hitrate,grounding}_table.json` are **analysis results** cited by
ADR-033, not indexes — they sit inside an ignored directory, so evidence for a headline claim is
uncommitted.

## A.4 The nine run roots

| dir | entries | size | the question it answers | SSOT reference |
|---|---|---|---|---|
| `runs/` | 26 run dirs + `calibration/` | 3.7 MB | does the teaching loop work? (12 `trackA_full_*` = ADR-024) + 14 pilots + 8 judge probes | ADR-023, ADR-024 |
| `runs_rag/` | 12 | 4.3 MB | does RAG help a model that already knows the domain? | ADR-027 |
| `runs_rag_aspect/` | 1 | 520 KB | is the null a *retriever* artifact? | ADR-029 |
| `runs_rag_big/` | 1 | 532 KB | is the null a *corpus-size* artifact? | ADR-029 |
| `runs_orca/` | 2 | 196 KB | is the student prompt a lever? | ADR-029 gate-(f) |
| `runs_hardtail/` | 10 | 1.2 MB | 5-seed hard-question probe | **no SSOT hit by name** |
| `runs_reliability/` | 16 | 5.9 MB | does RAG improve *reliability*, not just the mean? | `RAG_RELIABILITY_ANALYSIS.md:4,126` |
| `runs_lora/` | 1 file | 1 KB | does gold-SFT help? | `PRODUCT_RESULTS.md:111` |
| `runs_wixqa/` | 20 files | 6.8 MB | does RAG help when there IS a knowledge gap? | `WIXQA_RESULTS.md`, `RAG_LAW.md:329-330` |

Two output shapes coexist: **directory-per-run** (`<config-stem>__seed<N>__<UTC>/` with
`config_used.json` + `rounds.jsonl` + `summary.jsonl`, written by `src/tlw/runner.py:76`) and
**file-per-run** (`runs_wixqa/*.jsonl`, written by the standalone scripts). Both are kept; only
placement and naming change.

## A.5 `docs/`

Root: `RAG_LAW.md` (the portfolio artifact), `TRACK_A_RESULTS.md`, `RAG_RESULTS.md`,
`WIXQA_RESULTS.md`, `PRODUCT_RESULTS.md`, `RAG_RELIABILITY_ANALYSIS.md`,
`APPENDIX_PROMPTS_MEMORY_CODE.md` (stale — finding 6).
`docs/plan/` (45) mixes task specs (`T*.md`, 31), design specs (`EVAL_SPEC`, `RAG_SPEC`,
`SELECTIVE_RAG`, `PROMPT_CATALOG`, `P3-E-*`, `P3E-CAPSTONE-PLAN`, `P3-track-b-placeholder`) and
reports (`P1_GATE_REVIEW`, `T2.7_PILOT_REPORT`). `docs/audit/` and `docs/archive/` are correct.
**There is no `docs/README.md`** — nothing tells a newcomer that `RAG_LAW.md` is the entry point.

---

# B. Proposed target structure  *(revised in v2)*

**Principles** (each placement cites the one it serves):

- **P1 — Do not redesign what works.** `src/tlw/`, `src/core/`, `src/providers/`,
  `tools/dataset/`, `config/base.yml` + `experiments/`, `data/` immutability and the `tests/`
  mirror are prescribed by `structure.md` §B/§C/§E and ADR-016/017, and they work. Unchanged.
- **P2 — Source and artifacts never share a directory.** Anything a command regenerates lives
  under an artifact root (`runs/`, `indexes/`, `models/`) or a derived-evidence root (`reports/`).
- **P3 — Group by the question answered, not by the order things were run.**
- **P4 — Names read as English.** *(new in v2 — the governing rule.)*
- **P5 — The dependency arrow points one way:** `scripts/` → `src/`/`tools/`, never sideways.
- **P6 — Every move must earn its cost.** Where cost (broken links, frozen ADRs) exceeds benefit,
  I say so and leave it alone.

```
Teaching-light-weight-llm-based-project/
├── .claude/                          (exists) SSOT — unchanged
├── README.md                         (exists) front door; §Project-Structure + §Usage regenerated (finding 7)
├── run.py                            (exists) entrypoint
├── requirements.txt / environment.yml (exists)
├── pytest.ini                        (new) 7 lines: testpaths + pythonpath; deletes tests/conftest.py's path hack
│
├── config/                           (exists) authored configuration only — unchanged
│   ├── base.yml                      (exists) single source of six-slot defaults (ADR-016)
│   ├── prompts/{student,teacher}.yml (exists) preset templates (ADR-020)
│   └── archive/                      (exists) superseded prompt catalog
│
├── experiments/                      (exists, regrouped) one YAML per run condition
│   ├── teaching-loop/                (new) 1-baseline.yml, 2-self-refine.yml,
│   │                                       3-teacher-feedback.yml, 4-teacher-sees-answer.yml
│   │                                       (was trackA_full_arm{A,B,C,D}_diabetes.yml)
│   ├── rag-medquad/                  (new) small-model-no-rag.yml, small-model-with-rag.yml,
│   │                                       large-model-no-rag.yml, large-model-with-rag.yml
│   ├── rag-medquad-fair-tests/       (new) matching-question-type-only.yml, much-bigger-library.yml
│   ├── student-prompt/               (new) detailed-prompt-style.yml
│   └── pilots/                       (new) the 10 trackA_p2_* pilot configs
│
├── data/                             — inputs only; nothing an experiment generates lives here
│   ├── Medical_Q&A/                  (exists) raw MedQuAD CSVs — IMMUTABLE (guard-protected)
│   ├── medical_by_source/            (exists) per-domain JSONL — treated as raw
│   ├── external/                     (new) third-party datasets, gitignored + fetch script
│   │   └── wixqa/                    (moved from data/wixqa/) 52 MB HF Wix/WixQA (finding 8)
│   ├── clean/                        (exists) cleaner + split output
│   ├── processed/                    (exists) model-ready derivatives
│   ├── legacy/                       (new) the 6 pre-renovation loose *.jsonl (from data/*.jsonl)
│   └── calibration/                  (exists) judge boundary set — keep or archive per finding 11
│
├── indexes/                          (new — moved from data/rag/) built search indexes, gitignored
│   ├── medquad-diabetes-train/       (moved from data/rag/diabetes_train/)
│   ├── medquad-all-topics/           (moved from data/rag/all_medquad/)
│   └── wixqa-help-centre/            (moved from data/rag/wixqa_kb/)
│        # P2: an index is a build product of (data x encoder), not data. Living under data/ is why
│        # data/ needed its own ignore line (.gitignore:241). As a sibling of runs/ and models/ the
│        # rule becomes uniform: three artifact roots, all gitignored, all rebuilt by one command.
│        # data/rag/retriever_ladder/*.json are ANALYSIS results -> reports/rag-wixqa/ instead.
│
├── src/                              (exists) library code — UNCHANGED except:
│   ├── core/  providers/             (exists) EXEMPLAR seams — do not churn (structure.md:127-129)
│   ├── tlw/                          (exists) the core library. NAME KEPT — see §C.7
│   │   ├── __init__.py               (exists) docstring gains one line: what "tlw" stands for
│   │   ├── config/ registries.py memory/ prompts/ evaluation/ loop/ runner.py   (exists)
│   │   ├── analysis/                 (exists — MISSING from structure.md §B; add it)
│   │   ├── providers.py              (exists — MISSING from structure.md §B; add it)
│   │   └── wixqa/                    (new, phase 6 only) the 4 de-facto libraries (finding 5)
│   ├── simplified/  prompts/         (DELETE — empty ghost dirs, finding 10)
│   └── utils/                        (DELETE — dead, finding 14)
│
├── scripts/                          — thin drivers only; each imports from src/ or tools/ (P5)
│   ├── __init__.py                   (new) makes the existing cross-imports explicit
│   ├── dataset/                      (new) prepare_medquad.py, split_by_source.py,
│   │                                       assess_all.py, fetch_wixqa.py
│   ├── wixqa/                        (new) English names — see §C.9
│   ├── rag_medquad/                  (new) score_faithfulness.py, simulate_selective_rag.py,
│   │                                       rescore_answers.py, analyze_reliability.py
│   ├── lora/                         (new) build_training_data.py, train.py, evaluate.py
│   ├── judge_calibration/            (new) build_boundary_set.py, report.py
│   └── archive/                      (new) wait_for_groq_quota.py, analyze_lhs_strategy.py,
│                                           estimate_cost.py, compare_judges.py, compare_students.py
│
├── tools/                            (exists) reusable, importable CLI utilities — unchanged
│   ├── dataset/                      (exists) cleaner + Readiness Assessor + Streamlit app
│   └── rag/                          (exists — MISSING from structure.md §B; add it)
│
├── tests/                            (exists, tidied — §C.8) mirrors src/ and tools/ exactly
│   ├── tlw/…                         (exists) one dir per src/tlw/ package, uniform __init__.py
│   ├── tlw/test_providers.py         (new) the 2 provider tests now inside test_runner.py
│   └── tools/rag/test_builder.py     (moved from tests/rag/) mirrors tools/rag/
│
├── runs/                             (exists, restructured) THE artifact root — §C
│   ├── teaching-loop-medquad/        (from runs/trackA_full_*)   + pilots/
│   ├── rag-medquad/                  (from runs_rag/)
│   ├── rag-medquad-fair-tests/       (from runs_rag_aspect/ + runs_rag_big/)
│   ├── rag-medquad-reliability/      (from runs_reliability/ + runs_hardtail/)
│   ├── student-prompt-medquad/       (from runs_orca/)
│   ├── rag-wixqa/                    (from runs_wixqa/)  the 5-step ladder
│   └── judge-calibration/            (from runs/calibration/)
│
├── reports/                          (new — already "planned" at structure.md:56) DERIVED EVIDENCE, tracked
│   ├── README.md                     (new) study -> question -> report -> reproduce command
│   ├── teaching-loop-medquad/ rag-medquad/ rag-wixqa/ lora-medquad/ …
│   └── figures/                      (new) cookiecutter's reports/figures
│
├── docs/                             (exists) narrative, authored
│   ├── README.md                     (new) "start here" index — RAG_LAW.md first
│   ├── RAG_LAW.md TRACK_A_RESULTS.md RAG_RESULTS.md WIXQA_RESULTS.md PRODUCT_RESULTS.md
│   │                                 (exists) STAY PUT — 62 inbound links make moving uneconomic (P6)
│   ├── RAG_RELIABILITY_ANALYSIS.md   (exists) status line corrected (finding 12)
│   ├── plan/ audit/                  (exists) unchanged
│   └── archive/                      (exists) + APPENDIX_PROMPTS_MEMORY_CODE.md (finding 6)
│
├── logs/experiments/phase0..6/       (exists) pre-renovation evidence — IMMUTABLE, do not touch
├── models/                           (exists) adapters + base weights, gitignored
├── notebooks/                        (exists) empty after retiring experiment.ipynb (finding 14)
└── schemas/                          (exists) JSON schemas
```

### Deliberately NOT proposed (cost > benefit — P6)

| Tempting move | Why not |
|---|---|
| `docs/*.md` → `docs/results/` | 62 path-qualified inbound links across 15 files, 6 inside frozen ADRs (§0.6), 13 in `todo.md`. `docs/README.md` buys the same discoverability for one new file. |
| `docs/plan/` split | 45 files, heavily cross-linked; `T*.md` vs `*_SPEC.md` already signals the kinds. |
| Renaming `tlw` | **§C.7 — full cost analysis; recommendation is keep + document.** |
| `src/` → installed package (`pyproject.toml`, `tlw.*` imports) | 158 import sites. A 7-line `pytest.ini` gets the practical benefit at ~0 risk. |
| Moving `src/core/`, `src/providers/` under `src/tlw/` | `structure.md:127-129` already says do not churn. Agreed. |
| Deleting any run data | Irreplaceable §0.4 evidence for published ADRs. Consolidate, never delete. |
| Renaming test *functions* | They are already good — finding 18. |

---

# C. Results / artifacts organisation + naming convention  *(rewritten in v2)*

## C.1 The naming rule, in full

> **A name must read like English to someone who has never seen this repo.**

Four sub-rules — deliberately few, because a convention you must memorise has already failed:

1. **Words, not codes.** `wider-context`, not `chunk2400`. `better-retriever`, not `bge_chunk`.
   `self-refine`, not `selfrefine`. Industry-standard acronyms are fine (`RAG`, `LoRA`);
   project-internal ones are not (`armA`, `goldonly`, `hardtail`, `s1`).
2. **One separator per kind of thing, and both kinds are ones the reader already knows:**
   **hyphens** in folders and data artifacts; **underscores** in `.py` filenames because that is
   PEP 8 — Python's own rule, not one this project invented. Nothing else, and never mixed inside
   one name.
3. **The path is a label; the manifest is the record.** A directory name says *which experiment*;
   a `manifest.json` inside it (or, for framework runs, the existing `config_used.json`) says
   *exactly what was configured*. **Never encode the whole condition in the path.**
4. **Ordinal prefixes only where the runs form a genuine progression** (§C.3).

## C.2 One home, grouped by the question answered

```
runs/<study>/…            raw generations       gitignored (regenerable)
reports/<study>/…         computed evidence     git-tracked (small, citable)
docs/<REPORT>.md          the narrative         git-tracked (authored)
```

| study folder | the question, in plain English | ADR | today |
|---|---|---|---|
| `teaching-loop-medquad` | Does a teacher help more than the model checking its own work? | ADR-024 | `runs/trackA_*` |
| `judge-calibration` | Can we trust the automatic marker? | T2.3 / ADR-022(d) | `runs/calibration/` |
| `rag-medquad` | Does giving the model documents help when it already knows the subject? | ADR-027 | `runs_rag/` |
| `rag-medquad-fair-tests` | Was that "no" caused by weak search or a small library? | ADR-029 | `runs_rag_aspect/`, `runs_rag_big/` |
| `rag-medquad-reliability` | Does it at least make right answers more *repeatable*? | RAG_RELIABILITY_ANALYSIS | `runs_reliability/`, `runs_hardtail/` |
| `student-prompt-medquad` | Does the wording of the instruction matter? | ADR-029 gate-(f) | `runs_orca/` |
| `lora-medquad` | Does fine-tuning on the reference answers help? | ADR-028 | `runs_lora/` |
| `rag-wixqa` | Does giving the model documents help when it *doesn't* know the subject? | ADR-030…033 | `runs_wixqa/` |

This table becomes `reports/README.md`. A newcomer reading only the folder names gets the whole
research programme.

## C.3 On ordinals — where they belong, and where they do not

v1 banned stage ordinals. **v2 reverses that where a progression genuinely exists**, and the
distinction is principled rather than aesthetic:

- **The WixQA study IS a ladder.** Each step adds one thing to the step before, and that story —
  no RAG → RAG → better retriever → better context → plus self-refinement — *is* the finding
  (ADR-033's "three-stage pipeline"). Numbering makes it readable from `ls` alone. Cookiecutter's
  own notebook convention (`1.0-explore`, `2.0-clean`) numbers for exactly this reason. The
  numbers encode a *scientific* order, not a chronological one, so they satisfy the user's
  "no dates-in-name" standard.
- **The MedQuAD RAG study is NOT a ladder — it is a 2×2** (small/large model × with/without RAG,
  ADR-027). Numbering would invent a progression that does not exist and would imply
  `4-large-model-with-rag` is "latest and best" when it is in fact the worst arm
  (7B+RAG = −0.069). It stays unnumbered.
- **Track A IS ordered** — baseline → self-refine → teacher → teacher-sees-answer is increasing
  intervention, and arm D is explicitly a labelled ceiling rather than a result. Numbered.

Rule of thumb, stated once in `reports/README.md`: *number a set only if step N+1 contains step N.*

## C.4 Before → after, every run directory in all nine roots

### Study 1 — `runs/trackA_full_*` (12 dirs) → `runs/teaching-loop-medquad/`

Arm letters replaced by what `src/tlw/loop/strategies.py:99,120,274,284` says the arms *are*. The
run-id shape (`__seed<N>__<UTC>`) is unchanged — ADR-023 requires it for collision-safety, and a
timestamp is legitimately "what it is" for a dated run.

| before | after |
|---|---|
| `runs/trackA_full_armA_diabetes__seed{13,42,123}__<ts>/` | `runs/teaching-loop-medquad/1-baseline__seed{13,42,123}__<ts>/` |
| `runs/trackA_full_armB_diabetes__seed{13,42,123}__<ts>/` | `runs/teaching-loop-medquad/2-self-refine__seed{…}__<ts>/` |
| `runs/trackA_full_armC_diabetes__seed{13,42,123}__<ts>/` | `runs/teaching-loop-medquad/3-teacher-feedback__seed{…}__<ts>/` |
| `runs/trackA_full_armD_diabetes__seed{13,42}__<ts>/` | `runs/teaching-loop-medquad/4-teacher-sees-answer__seed{13,42}__<ts>/` |
| the 14 `runs/trackA_p2_*` pilot/dry runs | `runs/teaching-loop-medquad/pilots/<same names>` |

**This also removes a real correctness hazard.** `todo.md` T2.7 warns: *"T2.8 analysis MUST filter
to run_id prefix `trackA_full_*` + heldout data_path — the pilot 3b runs share (arm,seed,mem,3b)
keys so pool by run_id/data_path."* Because `discover_runs` (`loaders.py:136-151`) is one level
deep, putting pilots in a subdirectory makes that filter **structural instead of a manual
precaution** — `--runs-dir runs/teaching-loop-medquad` can no longer accidentally pool them.

### Study 2 — `runs_rag/` (12 dirs) → `runs/rag-medquad/`  *(2×2, unnumbered)*

| before | after |
|---|---|
| `runs_rag/trackA_full_armA_diabetes__seed{13,42,123}__<ts>/` *(the duplicated baseline)* | `runs/rag-medquad/small-model-no-rag__seed{…}__<ts>/` — or drop per finding 4 |
| `runs_rag/trackB_p3_3bRAG_diabetes__seed{13,42,123}__<ts>/` | `runs/rag-medquad/small-model-with-rag__seed{…}__<ts>/` |
| `runs_rag/trackB_p3_7b_diabetes__seed{13,42,123}__<ts>/` | `runs/rag-medquad/large-model-no-rag__seed{…}__<ts>/` |
| `runs_rag/trackB_p3_7bRAG_diabetes__seed{13,42,123}__<ts>/` | `runs/rag-medquad/large-model-with-rag__seed{…}__<ts>/` |

Exact model ids (`qwen2.5:3b`, `qwen2.5:7b-instruct`) already live in each run's
`config_used.json`, so nothing is lost by saying "small"/"large" in the path.

### Study 3 — `runs_rag_aspect/` + `runs_rag_big/` → `runs/rag-medquad-fair-tests/`

| before | after | what it actually was |
|---|---|---|
| `runs_rag_aspect/trackB_p3_3bRAGaspect_diabetes__seed42__<ts>/` | `runs/rag-medquad-fair-tests/matching-question-type-only__seed42__<ts>/` | keep only passages answering the same *kind* of question (`rag_backend.py::_aspect`) |
| `runs_rag_big/trackB_p3_3bRAGbig_diabetes__seed42__<ts>/` | `runs/rag-medquad-fair-tests/much-bigger-library__seed42__<ts>/` | 9,798 passages instead of 414 |

### Study 4 — `runs_reliability/` (16) + `runs_hardtail/` (10) → `runs/rag-medquad-reliability/`

| before | after |
|---|---|
| `runs_reliability/trackB_p3_3b_diabetes__seed{1..8}__<ts>/` | `runs/rag-medquad-reliability/no-rag__seed{1..8}__<ts>/` |
| `runs_reliability/trackB_p3_3bRAG_diabetes__seed{1..8}__<ts>/` | `runs/rag-medquad-reliability/with-rag__seed{1..8}__<ts>/` |
| `runs_hardtail/trackB_p3_3b_diabetes__seed{1..5}__<ts>/` | `runs/rag-medquad-reliability/hard-questions-only/no-rag__seed{1..5}__<ts>/` |
| `runs_hardtail/trackB_p3_3bRAG_diabetes__seed{1..5}__<ts>/` | `runs/rag-medquad-reliability/hard-questions-only/with-rag__seed{1..5}__<ts>/` |

`hardtail` → `hard-questions-only`. **Flagged:** `runs_hardtail/` has zero SSOT references by name
— confirm it should be kept before moving it (NOT VERIFIED #4).

### Study 5 — `runs_orca/` (2) → `runs/student-prompt-medquad/`

| before | after |
|---|---|
| `runs_orca/trackA_p2_armA_diabetes_orca__seed42__20260723T155406Z/` | `runs/student-prompt-medquad/detailed-prompt-style__seed42__20260723T155406Z/` |
| `runs_orca/trackA_p2_armA_diabetes_orca__seed42__20260723T155536Z/` | `runs/student-prompt-medquad/detailed-prompt-style__seed42__20260723T155536Z/` |

`orca` is a prompt-*style* name (ADR-020); its comparison partner is Track A's `1-baseline`
(minimal style). **Flagged:** two directories for the same config *and* seed, 90 seconds apart —
one is probably a false start. Confirm which was reported before moving (NOT VERIFIED #4).

### Study 6 — `runs_lora/` → `reports/lora-medquad/`

| before | after |
|---|---|
| `runs_lora/lora_eval_result.json` | `reports/lora-medquad/fine-tuned-vs-original.json` |

It is a *result*, not a generation — so it belongs in `reports/` and becomes git-tracked (1 KB),
which makes ADR-028's `−0.292` checkable from a clone.

### Study 7 — `runs_wixqa/` → `runs/rag-wixqa/`  *(the ladder — numbered)*

```
runs/rag-wixqa/
├── README.md                          <- the story in six lines, one per step
├── 1-no-rag/                          seed13.jsonl  seed42.jsonl  seed123.jsonl  manifest.json
├── 2-rag-basic/                       + retrieval-log.jsonl
├── 3-rag-better-retriever/            + retrieval-log.jsonl
├── 4-rag-wider-context/               <- the winner (+0.130, the project's largest lever)
├── 5-rag-plus-self-refine/
└── pilots/
    ├── 4-rag-wider-context/
    └── 5-rag-plus-self-refine/
```

| before | after |
|---|---|
| `runs_wixqa/baseline_norag.jsonl` | `runs/rag-wixqa/1-no-rag/seed42.jsonl` |
| `runs_wixqa/baseline__seed13.jsonl` | `runs/rag-wixqa/1-no-rag/seed13.jsonl` |
| `runs_wixqa/baseline__seed123.jsonl` | `runs/rag-wixqa/1-no-rag/seed123.jsonl` |
| `runs_wixqa/rag_top3.jsonl` | `runs/rag-wixqa/2-rag-basic/seed42.jsonl` |
| `runs_wixqa/rag__seed13.jsonl` | `runs/rag-wixqa/2-rag-basic/seed13.jsonl` |
| `runs_wixqa/rag__seed123.jsonl` | `runs/rag-wixqa/2-rag-basic/seed123.jsonl` |
| `runs_wixqa/retrieval_log.jsonl` | `runs/rag-wixqa/2-rag-basic/retrieval-log.jsonl` |
| `runs_wixqa/rag_bge_chunk__seed{13,42,123}.jsonl` | `runs/rag-wixqa/3-rag-better-retriever/seed{13,42,123}.jsonl` |
| `runs_wixqa/retrieval_log_bge_chunk.jsonl` | `runs/rag-wixqa/3-rag-better-retriever/retrieval-log.jsonl` |
| `runs_wixqa/rag_bge_chunk_chunk2400__seed{13,42,123}.jsonl` | `runs/rag-wixqa/4-rag-wider-context/seed{13,42,123}.jsonl` |
| `runs_wixqa/rag_bge_chunk_chunk2400_pilot__seed42.jsonl` | `runs/rag-wixqa/pilots/4-rag-wider-context/seed42.jsonl` |
| `runs_wixqa/rag_bge_chunk_chunk2400_selfrefine_pilot__seed42.jsonl` | `runs/rag-wixqa/pilots/5-rag-plus-self-refine/seed42.jsonl` |
| `runs_wixqa/_s1_full_aggregate.txt` | `reports/rag-wixqa/wider-context-vs-narrow.txt` |
| `runs_wixqa/_s1_full_gold.txt` | `reports/rag-wixqa/wider-context-vs-narrow-when-answer-found.txt` |
| `runs_wixqa/_s1_pilot_result.txt` | `reports/rag-wixqa/wider-context-pilot.txt` |
| `runs_wixqa/_s2_pilot_result.txt` | `reports/rag-wixqa/self-refine-pilot.txt` |
| `data/rag/retriever_ladder/hitrate_table.json` | `reports/rag-wixqa/retriever-comparison.json` |
| `data/rag/retriever_ladder/grounding_table.json` | `reports/rag-wixqa/context-window-comparison.json` |

**Where the jargon went.** `bge_chunk`, `chunk2400`, `top3` and `goldonly` are not lost — they move
into `manifest.json`, which is the right place for exactness:

```jsonc
// runs/rag-wixqa/4-rag-wider-context/manifest.json
{
  "step": 4,
  "label": "RAG with a wider, better-targeted slice of each article",
  "question": "Does showing more of the RIGHT part of the retrieved article help?",
  "changed_from_previous_step": "the grounding window only — retrieval is byte-identical to step 3",
  "student":   { "provider": "local", "model": "qwen2.5:3b", "temperature": 0.3, "max_tokens": 256 },
  "retriever": { "encoder": "bge-base-en-v1.5", "unit": "180-word chunks", "top_k": 3 },
  "grounding": { "chars_per_article": 2400, "centred_on": "the matched chunk",
                 "previous": "first 900 chars of the article" },
  "judge":     { "provider": "groq", "model": "llama-3.1-8b-instant",
                 "mode": "reference-comparing", "pass_at": 3 },
  "seeds": [13, 42, 123], "questions": 200,
  "subset": "all questions",
  "produced_by": "scripts/wixqa/run_three_seeds_with_retriever.py --retriever bge_chunk --grounding chunk2400",
  "reported_in": "docs/WIXQA_RESULTS.md#grounding-delivery, ADR-033"
}
```

For the self-refine pilot: `"subset": "only the 133 questions whose answer-bearing article was
retrieved (a labelled diagnostic subset — never a headline)"` — the sentence `goldonly` was trying
to be.

**Correctness check (required by "two conditions must never map to the same name"):** 5 ladder
steps × {seed13, seed42, seed123} plus 2 pilots = 17 destination paths for 17 source files. No
collisions. The seed-42 files that currently break the pattern (`baseline_norag.jsonl`,
`rag_top3.jsonl` — the ADR-030 published draw) land on `1-no-rag/seed42.jsonl` and
`2-rag-basic/seed42.jsonl`, which is what they always were. **Bonus:** this deletes the hardcoded
per-seed filename map at `scripts/wixqa_analyze.py:32-35`, replacing it with `f"{step}/seed{s}.jsonl"`.

### Study 8 — `runs/calibration/` (8 files) → `runs/judge-calibration/`

I opened all eight and read `judge_model` / `local_judge_model` from each, so this grouping is
evidence-based, not guessed:

| before | after | judge under test (read from the file) |
|---|---|---|
| `probe_seed42_n3_1783951752.json` | `judge-calibration/local-llama-8b/seed42-3-questions-smoke.json` | `ollama/llama3.1:8b` |
| `probe_seed42_n40_1783952270.json` | `judge-calibration/local-llama-8b/seed42-40-questions-rubric-v1.json` | `ollama/llama3.1:8b`, κ=0.346 |
| `probe_seed42_n40_1784002100.json` | `judge-calibration/local-llama-8b/seed42-40-questions-rubric-v2.json` | `ollama/llama3.1:8b`, κ=0.120 |
| `probe_seed123_n40_1784002100.json` | `judge-calibration/local-llama-8b/seed123-40-questions-rubric-v2.json` | `ollama/llama3.1:8b`, κ=0.213 |
| `probe_fallback_8binstant_seed42_n40_1783953647.json` | `judge-calibration/groq-llama-8b/seed42-40-questions.json` | `groq/llama-3.1-8b-instant`, κ=0.411 |
| `probe_seed42_n2_1784030417.json` | `judge-calibration/groq-llama-70b/seed42-2-questions-smoke.json` | `groq/llama-3.3-70b-versatile` |
| `probe_seed42_n20_1784030559.json` | `judge-calibration/groq-llama-70b/seed42-20-questions.json` | `groq/llama-3.3-70b-versatile` |
| `probe_seed42_n15_1784030978.json` | `judge-calibration/groq-llama-70b/seed42-15-questions.json` | `groq/llama-3.3-70b-versatile` |

The unix-epoch suffixes disappear. **They were doing real work** — two files are both
`probe_seed42_n40_*` — so I checked before dropping them: they differ by *rubric version*
(κ=0.346 vs κ=0.120, matching `todo.md` T2.3b's "κ 0.35→0.21" note), and `rubric-v1`/`rubric-v2`
disambiguates them. No two conditions map to the same name.

### The `experiments/*.yml` configs follow the same names

Because `src/tlw/runner.py` derives the run id from the config stem, renaming the config is what
makes the run id readable: `trackA_full_armA_diabetes.yml` → `teaching-loop/1-baseline.yml`.
The `params.arm: A` key **inside** stays `A` — that is a registry key (`strategies.py:99`), not a
label, and must not change.

## C.5 One tiny naming rule for `reports/`

Report filenames answer *"what is being compared?"* in English:
`wider-context-vs-narrow.txt`, `fine-tuned-vs-original.json`, `retriever-comparison.json`,
`teacher-vs-self-refine.txt`. No stage ordinals, no leading underscores, no dates — the run
directories carry the dates.

## C.6 What is tracked vs ignored

**The rule:** *track what a reader must be able to check; ignore what a command can rebuild.*

| Artifact | Size | Decision | Reason |
|---|---|---|---|
| `runs/**/summary.jsonl` | ~2 KB × ~70 | **TRACK** | the §0.4 evidence for ADR-024/027/028 (~150 KB); makes `README.md:90` true |
| `runs/**/config_used.json` | ~1 KB × ~70 | **TRACK** | the §0.3 reproduction key (resolved config + seed + git commit) |
| `runs/**/manifest.json` | ~1 KB each | **TRACK** | the plain-English record behind every short folder name |
| `runs/**/rounds.jsonl` | 100–200 KB × ~70 | **IGNORE** | raw generations, rebuildable from config + seed |
| `runs/rag-wixqa/**/seed*.jsonl` | ~500 KB × 14 | **IGNORE** | 6.8 MB of raw generations — but see the next row |
| `reports/<study>/scores.csv` | ~20 KB | **TRACK (new artifact)** | `question, seed, step, score` — enough to recompute every WixQA headline number at 0.3% of the size. The honest substitute for committing 6.8 MB. |
| `reports/<study>/*.txt \| *.json` | < 20 KB each | **TRACK** | the computed tables ADR-033 cites (e.g. the `+0.130 … p=3.52e-08` block) |
| `reports/figures/*.png` | small | **TRACK** | cookiecutter standard |
| `indexes/**` | 49 MB | **IGNORE** | rebuilt by `python -m tools.rag.cli …` (`tools/rag/cli.py:5-11`) and `scripts/wixqa/build_index.py` |
| `models/**` | 333 MB | **IGNORE** | already ignored (`.gitignore:220`); rebuilt by `scripts/lora/train.py` |
| `data/external/**` | 52 MB | **IGNORE** + fetch script | third-party, licensed, re-downloadable |
| `data/{clean,processed,legacy,calibration}/**` | small | **TRACK** | pipeline products that gate every experiment |
| `logs/experiments/**` | 298 MB | **TRACK (as today)** | immutable historical evidence, guard-protected (`settings.json:27`, `guard.py:22`) — do not touch |

Required `.gitignore` change (replaces the single `runs/` line at `.gitignore:236`):

```gitignore
# Experiment artifacts: raw generations ignored, evidence tracked.
runs/**
!runs/**/                      # let git descend into study/run directories
!runs/**/summary.jsonl         # the §0.4 evidence (~2 KB per run)
!runs/**/config_used.json      # the §0.3 reproduction key (~1 KB per run)
!runs/**/manifest.json         # the plain-English record of the condition
!runs/**/README.md             # the study story

indexes/                       # rebuildable: python -m tools.rag.cli      (was: data/rag/)
data/external/                 # third-party downloads; see scripts/dataset/fetch_wixqa.py
```
`reports/` is deliberately absent — everything in it is meant to be committed.

## C.7 `tlw` — the honest assessment  *(new in v2)*

**What a rename costs.** Measured, not estimated:

| Where | Count | Note |
|---|---|---|
| `src.tlw` / `src/tlw` references in `.py` | **158** | `src/` 56, `tests/` 69, `scripts/` 28, `tools/` 3, `run.py` 1 |
| `.py` files containing the string `tlw` | **73** | |
| Non-code files referencing it | **~25** | incl. all 8 `.claude/agents/*.md`, `.claude/CLAUDE.md`, `00-index.md`, `structure.md`, `decisions.md` (13 hits), `todo.md` (18), `schema.md`, `settings.json`, both skills, `config/base.yml`, `config/prompts/*.yml`, 4 `experiments/*.yml`, `docs/{TRACK_A,WIXQA,RAG}_RESULTS.md` |
| Directory paths | `src/tlw/` (8 packages) + `tests/tlw/` (7 dirs) | |

**The decisive fact.** The conda environment is *also* named `tlw` (`environment.yml:8`:
`name: tlw # tlp = teaching light weight LLM`), and §0.5 of the Constitution hardcodes
`C:\Users\ham25\.conda\envs\tlw\python.exe` — a **frozen** line (§0.6). It also appears in
`.claude/settings.json:13,37` (the permission allowlist and the guard-hook command). So renaming
the package alone produces a *worse* inconsistency than today (package `foo`, env `tlw`), and
renaming both requires editing the Constitution, which no agent may do.

**Recommendation: KEEP `tlw`, and document it in one line.** Reasons, in order:

1. ~160 import sites + ~25 documents + 8 agent definitions + `settings.json`, for zero functional
   gain — the largest change in this whole proposal and the only one with no correctness benefit.
2. The env-name coupling above makes a *clean* rename impossible without §0.6 approval.
3. A short package name is normal in Python (`numpy`, `sklearn`, `django.db`). The problem is not
   the length — it is that **nothing anywhere expands the acronym.** `src/tlw/__init__.py`
   currently reads: *"tlw — the new config-driven core (ADR-017). Grows beside the frozen legacy
   (src/simplified/) until T2.9 demolition."* It never says what the letters mean, and it is
   itself stale (T2.9 happened).
4. The 30-second test is passed by one sentence, not by a rename.

**The one-line fix**, in three places (all cheap, all additive):

- `src/tlw/__init__.py` → `"""tlw — Teaching Lightweight LLM. The project's core library: config,
  registries, prompts, memory, evaluation, the loop and the runner."""` (also drops the stale
  legacy sentence)
- `README.md` §Project Structure → `src/tlw/   # "Teaching Lightweight LLM" — the core library`
- `.claude/rules/structure.md` §C → the same gloss in the block table.

**If the user still wants a rename**, two candidates: **`teachlite`** (keeps both ideas,
pronounceable, unambiguous as an import — `from teachlite.loop import …`) or **`teaching_loop`**
(maximally literal, but names only one of the seven blocks and undersells `config`/`evaluation`/
`analysis`). My recommendation stands at **keep + document**; if forced, `teachlite`. Either way
it must be a single commit that also renames the conda env, and the §0.5 Constitution edit needs
the user's own hand.

## C.8 `tests/` — audit and tidy-up  *(new in v2)*

**Already good — do not touch:**

- **Test names describe behaviour, not modules.** Sampled 55 across two files:
  `test_v2_same_family_rejected`, `test_v8_baseline_arm_with_rag_allowed`,
  `test_load_dataset_limit_is_deterministic_prefix`,
  `test_fallback_honors_retry_after_hint_in_error_text`,
  `test_diagnose_round_computed_even_without_params_ground_truth`. Better than most production
  codebases. **No renaming proposed.**
- **The four `conftest.py` files are not duplicated scaffolding.** Root = import path;
  `tests/tlw/` = registry-registration side effects (with the pytest-randomly bug that motivated
  it written into the comment); `analysis/` = a 163-line synthetic run-dir factory; `loop/` =
  network-free mocks.
- **Coverage is even:** 20 modules, 246 test functions, roughly proportional to package size.

**To tidy (finding 18):**

| # | Issue | Fix |
|---|---|---|
| 1 | `tests/rag/test_builder.py` tests `tools/rag/builder.py` but mirrors nothing | → `tests/tools/rag/test_builder.py` |
| 2 | `__init__.py` in 4 of 10 dirs | add the 6 missing (`tests/`, `tests/tools/rag/`, `tests/tlw/`, `tests/tlw/{config,memory,runner}`) so a duplicate basename can never shadow |
| 3 | `src/tlw/providers.py` has no test module; its 2 tests hide in `test_runner.py:316,329` (30 tests, the largest file) | extract → `tests/tlw/test_providers.py` |
| 4 | `tests/conftest.py` exists only for `sys.path.insert` | replace with a 7-line `pytest.ini` (pytest 8.4.2 verified, so `pythonpath` is available) and delete the file |
| 5 | after phase 6, `src/tlw/wixqa/` would have no mirror | add `tests/tlw/wixqa/` alongside the extraction |

Proposed `pytest.ini`:
```ini
[pytest]
testpaths = tests
pythonpath = .
addopts = -q
```
That one file also fixes finding 15's practical symptom (rootdir ambiguity, repeated path
incantations) without the 158-site package migration.

## C.9 `scripts/` names after regrouping  *(new in v2)*

Underscores because PEP 8 (rule 2); English words because rule 1:

| before | after |
|---|---|
| `scripts/wixqa_baseline.py` | `scripts/wixqa/run_without_rag.py` |
| `scripts/wixqa_rag.py` | `scripts/wixqa/run_with_rag.py` |
| `scripts/wixqa_build_index.py` | `scripts/wixqa/build_index.py` |
| `scripts/wixqa_judge.py` | `scripts/wixqa/score_answers.py` |
| `scripts/wixqa_run3seed.py` | `scripts/wixqa/run_three_seeds.py` |
| `scripts/wixqa_run3seed_retriever.py` | `scripts/wixqa/run_three_seeds_with_retriever.py` |
| `scripts/wixqa_retriever_ladder.py` | `scripts/wixqa/compare_retrievers.py` |
| `scripts/wixqa_grounding_ladder.py` | `scripts/wixqa/compare_context_windows.py` |
| `scripts/wixqa_grounding_compare.py` | `scripts/wixqa/compare_two_runs.py` |
| `scripts/wixqa_selfrefine.py` | `scripts/wixqa/run_with_self_refine.py` |
| `scripts/wixqa_repair_empty.py` | `scripts/wixqa/regenerate_empty_answers.py` |
| `scripts/wixqa_analyze.py` | `scripts/wixqa/analyze_three_seeds.py` |
| `scripts/wixqa_dose_analyze.py` | `scripts/wixqa/analyze_dose_response.py` |
| `scripts/build_lora_data.py` | `scripts/lora/build_training_data.py` |
| `scripts/train_lora.py` | `scripts/lora/train.py` |
| `scripts/eval_lora.py` | `scripts/lora/evaluate.py` |
| `scripts/rag_faithfulness.py` | `scripts/rag_medquad/score_faithfulness.py` |
| `scripts/selective_rag_sim.py` | `scripts/rag_medquad/simulate_selective_rag.py` |
| `scripts/rejudge.py` | `scripts/rag_medquad/rescore_answers.py` |
| `scripts/reliability_analysis.py` | `scripts/rag_medquad/analyze_reliability.py` |
| `scripts/build_calibration.py` | `scripts/judge_calibration/build_boundary_set.py` |
| `scripts/calibration_report.py` | `scripts/judge_calibration/report.py` |
| `scripts/prepare_medical_dataset.py` | `scripts/dataset/prepare_medquad.py` |
| `scripts/split_medical_by_source.py` | `scripts/dataset/split_by_source.py` |
| `scripts/assess_all.py` | `scripts/dataset/assess_all.py` |
| `scripts/finish_when_groq_ready.py` | `scripts/archive/wait_for_groq_quota.py` |
| `scripts/{analyze_lhs_strategy,estimate_cost,compare_judges,compare_students}.py` | `scripts/archive/<same name>` |

## C.10 Where the "start here" pointer lives

Three pointers, each one hop from the last:

1. **`README.md` §Key Results** — already correct (`:88-146`). Add one line: *"Raw evidence and
   how to reproduce it: `reports/README.md`."*
2. **`docs/README.md` (new)** — "Start with `RAG_LAW.md`", then one line per report, then `plan/`,
   `audit/`, `archive/`.
3. **`reports/README.md` (new)** — the §C.2 table: question → ADR → report → tracked evidence file
   → the exact command that regenerates it.

Root README → results table → report → tracked evidence → reproduce command. Nothing needs
decoding at any step.

---

# D. Risk & sequencing  *(revised in v2)*

Ordered so the repo is never broken. Each phase is one commit, independently revertible.
**Phases 1–2 are near-zero risk; risk grows monotonically; phase 6 is optional.**

### Phase 0 — approvals (no file changes)

Two Accepted ADRs are touched; per §0.6 neither may be edited, both need a **new superseding ADR**
written from the user's decision:
- **ADR-017** fixed the `structure.md` v2 tree → "canonical structure v3".
- **ADR-023** fixed run outputs at `runs/<run_id>/` → "run outputs at `runs/<study>/<run_id>/`,
  with English step names".
A third, smaller item: **ADR-016** defines `experiments/<track><phase>_<arm>_<slug>.yml`, and §C.4
renames those configs — the same superseding ADR should cover it.
**Owner:** user decision at the hub; **project-coordinator** logs via the `new-adr` skill.

### Phase 1 — pure additions (risk: **none**)

| Step | Action | Breaks |
|---|---|---|
| 1.1 | Create `docs/README.md`, `reports/README.md`, `reports/figures/.gitkeep` | nothing |
| 1.2 | Add `scripts/__init__.py` | nothing — makes the 15 existing `from scripts.X import` lines explicit rather than PEP-420-implicit |
| 1.3 | Add `pytest.ini` (§C.8); delete `tests/conftest.py` in the *same* commit | verify with `pytest tests/ -q` — 270 tests must still pass |
| 1.4 | One-line `tlw` gloss in `src/tlw/__init__.py`, README, `structure.md` (§C.7) | nothing |
| 1.5 | Commit the untracked authored files: `tools/rag/`, 24 `scripts/*.py`, 7 `experiments/*.yml`, 12 `docs/plan/*.md`, 5 `docs/*.md`, `src/tlw/{analysis/rag_report,evaluation/faithfulness,memory/rag_backend}.py`, `tests/rag/`, `data/processed/` | nothing — `structure.md` §F says untracked-but-exemplary code is *"needs-commit, not delete-junk"* |

### Phase 2 — fix the absolute paths (risk: **very low**, independently verifiable)

| Step | Action | Verification |
|---|---|---|
| 2.1 | Replace the hardcoded `ROOT` with `Path(__file__).resolve().parents[1]` in the 13 files from finding 2 | run `wixqa_analyze.py` and `wixqa_dose_analyze.py` — both pure-offline (they read judged `.jsonl` + `src/tlw/analysis/stats.py`, zero LLM calls) and print the published ADR-030/033 numbers. If those match, the change is proven. |

Do this **before** any move: it is what makes every later move testable.

### Phase 3 — consolidate and rename the run roots (risk: **low**, all mechanical)

| Step | Action | What breaks, exactly |
|---|---|---|
| 3.1 | Create the 7 study directories under `runs/` | nothing |
| 3.2 | `git mv` the 8 sibling roots + `runs/trackA_*` + `runs/calibration/` in, applying §C.4's names | see 3.4–3.6 |
| 3.3 | Write one `manifest.json` per condition directory + one `README.md` per study | nothing (additive) — **this is what lets the folder names be short** |
| 3.4 | Update path literals: `scripts/build_calibration.py:50`, `eval_lora.py:107`, `finish_when_groq_ready.py:64,67,70`, `rejudge.py:91`, `reliability_analysis.py:53`, `selective_rag_sim.py:83`, `wixqa_analyze.py:27` **and the filename map at `:32-35`**, `wixqa_baseline.py:57`, `wixqa_dose_analyze.py:27`, `wixqa_grounding_ladder.py:38`, `wixqa_rag.py:52`, `wixqa_run3seed.py:42`, `wixqa_run3seed_retriever.py:36`, `wixqa_selfrefine.py:47` | 15 literals + 1 map |
| 3.5 | Update docstring usage examples: `rejudge.py:15`, `selective_rag_sim.py:15`, `wixqa_judge.py:16-17`, `wixqa_grounding_compare.py:16-17`, `wixqa_repair_empty.py:13`, `wixqa_run3seed_retriever.py:161`, `wixqa_selfrefine.py:163`, `reliability_analysis.py:12`, `finish_when_groq_ready.py:10`, `build_calibration.py:11` | 10 docstrings |
| 3.6 | Update doc reproduce commands: `docs/RAG_LAW.md:320,323,326-330`, `RAG_RESULTS.md:201-209`, `WIXQA_RESULTS.md:35,98,103,104,340-342`, `TRACK_A_RESULTS.md:159`, `PRODUCT_RESULTS.md:111`, `RAG_RELIABILITY_ANALYSIS.md:4,126` | ~22 lines |
| 3.7 | Rename + regroup `experiments/*.yml` per §C.4. **Leave every `params.arm` value alone** (`A`/`B`/`C`/`D` are registry keys — `strategies.py:99,120,274,284`) | `experiments/README.md` + any doc quoting a config path |
| 3.8 | Apply the `.gitignore` block from §C.6 | replaces `.gitignore:236,241` |
| 3.9 | **Verify** | `python -m src.tlw.analysis --runs-dir runs/teaching-loop-medquad --comparison C-B` → **+0.003 [−0.021,+0.029] p=1.00**; `--runs-dir runs/rag-medquad --rag` → the 4-arm table; `python scripts/wixqa/analyze_three_seeds.py` → **+0.152 [+0.090,+0.213]**; `analyze_dose_response.py` → **0.163 / 0.315 / 0.340** |

**What does NOT break, and why I am confident:** `discover_runs`
(`src/tlw/analysis/loaders.py:136-151`) is one level deep and **directory-shaped, not
filename-shaped** — its own docstring says so — and `group_runs` (`:154-161`) keys off the `arm`
field inside `summary.jsonl`, not the path. So renaming run directories is invisible to the
analysis, **provided the conditions stay siblings inside one study directory.** That is exactly why
§C.4 does *not* nest Track A's arms in per-arm subfolders: the C−B comparison needs all four arms
discoverable in a single `--runs-dir`. `src/tlw/runner.py:683` already honours `--runs-dir`.
`.claude/settings.json` and `.claude/hooks/guard.py:19-22` protect only `data/Medical_Q&A/`,
`data/medical_by_source/` and `logs/experiments/` — **no `runs*` path is guard-protected**, so
there is no hook conflict.

**Do NOT touch in this phase:** the ~20 `runs_*` mentions inside `.claude/rules/decisions.md`
(ADR-027/029/030/033 evidence lines). Editing an Accepted ADR is §0.6-sensitive; the superseding
ADR should state the old→new mapping once, and the historical ADRs stay as written.
**Flagged for user approval.**

### Phase 4 — reports, indexes, external data (risk: **low–medium**)

| Step | Action | Breaks |
|---|---|---|
| 4.1 | Create `reports/<study>/`; move the 4 `runs_wixqa/_s*.txt`, the 2 `data/rag/retriever_ladder/*.json` and `runs_lora/lora_eval_result.json` in, renamed per §C.4 | output paths in `wixqa_grounding_ladder.py`, `wixqa_retriever_ladder.py`, `eval_lora.py:107` (3 files) |
| 4.2 | Add a `--scores-csv` flag to the two analysers; generate + commit `reports/<study>/scores.csv` | nothing (additive) |
| 4.3 | `data/rag/` → `indexes/` | **8 literals**: `wixqa_build_index.py:22`, `wixqa_rag.py:27`, `wixqa_run3seed.py:41`, `corpus_path:` in `experiments/trackB_p3_3bRAG{,aspect,big}_diabetes.yml` + `trackB_p3_7bRAG_diabetes.yml`, and the example at `tools/rag/cli.py:5-11`. **Verify with a 4-question RAG smoke run.** `corpus_path` is validated at config-load, so a wrong path fails loud — a safe failure mode. |
| 4.4 | `data/wixqa/` → `data/external/wixqa/`; write `scripts/dataset/fetch_wixqa.py` | **6 literals**: `wixqa_baseline.py:23`, `wixqa_build_index.py:21`, `wixqa_rag.py:26`, `wixqa_retriever_ladder.py:35,36`, `wixqa_run3seed.py:40` |
| 4.5 | `docs/APPENDIX_PROMPTS_MEMORY_CODE.md` → `docs/archive/` + SUPERSEDED banner | 0 inbound links found — safe |
| 4.6 | `data/*.jsonl` (6) → `data/legacy/` + README | 1 reference to `medical_all_clean`; verify first |
| 4.7 | Correct `README.md:90` and `RAG_RELIABILITY_ANALYSIS.md:4,126` | nothing |

### Phase 5 — `tests/` tidy + regenerate the two maps (risk: **none**; last, so each is written once)

| Step | Action |
|---|---|
| 5.1 | `tests/rag/` → `tests/tools/rag/`; add the 6 missing `__init__.py`; extract `tests/tlw/test_providers.py` from `test_runner.py:316,329`. Verify: `pytest tests/ -q` green, same count |
| 5.2 | Rewrite `.claude/rules/structure.md` to v3 = §B's tree; update §F's junk checklist (drop the T2.9 DEAD list — those files are gone; add "run artifacts outside `runs/<study>/`", "analysis output inside `runs/`", "hardcoded absolute `ROOT`", "a name only an insider can read") |
| 5.3 | Rewrite `README.md` §Project-Structure + §Usage + §Configuration from the v3 tree (finding 7 — the deferred T3.13 item) |
| 5.4 | Add the `todo.md` line + tick, per the spoke protocol (`docs/plan/README.md:15-18`) |

### Phase 6 — the `scripts/` refactor (risk: **medium**; OPTIONAL)

| Step | Action | Breaks |
|---|---|---|
| 6.1 | Extract the shared library (`load_data`, `encode`, `chunks_of`, `build_ranked`, `window`, `best_chunk_word_offset`, `RAG_SYS`, `JUDGE_SYS`, `judge_score`, `TEMPERATURE`, `MAX_TOKENS`, `MAX_PASSAGE_CHARS`, `retrieval_record`, `GROUNDINGS`) into `src/tlw/wixqa/` + `tests/tlw/wixqa/` | the **15 cross-import lines** from finding 5 |
| 6.2 | Move + rename the 31 scripts per §C.9 | every doc command containing `scripts/wixqa_*` (~25 occurrences across `docs/`, `README.md`, `todo.md`) + `ROOT` becomes `parents[2]` in every moved file (already touched in phase 2 — do phase 6 *after*, never instead) |
| 6.3 | Verify: full `pytest tests/ -q` **and** re-run both offline analysers | — |

**Honest assessment, unchanged from v1:** phase 6 delivers the cleanest structure but is the only
phase that can silently break a published reproduction path. If the user's next move is the P3-C
product surface, **do 6.1 and skip 6.2** — the library extraction has lasting value; the directory
grouping is cosmetic once §C.9's names are settled.

### Not worth moving at all

| Item | Verdict |
|---|---|
| `docs/*.md` result reports | 62 inbound links, 6 inside frozen ADRs. `docs/README.md` instead. |
| `docs/plan/` reorganisation | 45 files, heavily cross-linked; naming already distinguishes the kinds. |
| Renaming `tlw` | §C.7 — keep and document. |
| `src/` → installed package | 158 import sites; `pytest.ini` gets the practical benefit. |
| `src/core/`, `src/providers/` relocation | `structure.md:127-129` — do not churn. |
| Test function names | Already excellent (finding 18). |
| `logs/experiments/phase0..6` | Immutable, guard-protected, historical. Never touch. |
| Any deletion of run data | Irreplaceable §0.4 evidence. Consolidate, never delete. |

### Rollback

Every phase is one commit. Phases 3–4 are `git mv` + literal edits, so `git revert <sha>` restores
the previous layout exactly. Phase 2 is behaviour-preserving by construction (same absolute path,
computed instead of typed). Phase 1 is additive. The only phase needing a real rollback plan is 6,
which is why it is last and optional.
