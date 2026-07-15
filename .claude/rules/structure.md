# Canonical Repo Structure (v2 — ADR-017)

Source of truth for **housekeeping** and for every P2/P3 build task. Layout follows ML
project best practices (cookiecutter-data-science + Real Python `src` layout, ADR-009) and
adds the **target architecture** the renovation (ADR-015) builds into: a new config-driven
core (`src/tlw/`) that grows **beside** the frozen legacy (`src/simplified/`) until T2.9.

Legend: **(exists)** = present today · **(planned — create when first needed)** = agreed
target, do NOT flag as missing junk · **(frozen legacy)** = keep working, do not extend,
demolished in T2.9.

---

## §A Design principles (why the tree looks like this)

1. **Change-readiness = clean seams + config, not building everything now** (ADR-015). Every
   swappable thing (student / teacher / preset / memory / arm / judge — the six slots of the
   Config Contract, `schema.md` "Experiment Config Contract v1") sits behind an **interface**
   resolved through a **registry**. You change behaviour by editing YAML, never by surgery.
2. **One responsibility per module.** The new core splits the 843-line monolith
   (`simplified_teaching_loop.py`, MESSY per CODE_MAP.md:25, run() spans lines 214–742) into
   blocks that each own one concern and communicate only through the seam interfaces.
3. **Strangler migration** (ADR-015, ADR-017). New blocks are written under `src/tlw/`; the
   legacy loop keeps running unchanged until the new blocks are proven (T2.7), then the DEAD +
   legacy files are deleted in one demolition pass (T2.9). No big-bang moves mid-flight.
4. **Reuse the exemplars.** `src/providers/factory.py` (EXEMPLAR, CODE_MAP.md:65) is the
   registry pattern every new registry copies; `src/core/client.py` is the ModelClient seam,
   already implemented — the new core imports these in place, it does not rewrite them.

---

## §B Target tree

```
Teaching-light-weight-llm-based-project/
├── .claude/                        # Claude env: CLAUDE.md, rules/, agents/, skills/, hooks/, settings (exists)
├── config/
│   ├── simplified_config.yml       # (frozen legacy) — drives the old loop only; retired with it (exists)
│   ├── prompts_config.yml          # (exists) prompt catalog source; wrapped by PresetRegistry
│   └── base.yml                    # (planned — T2.1) ALL six-slot defaults; single source of truth (schema.md)
├── experiments/                    # (planned — T2.6) one YAML per run = slot overrides only; naming per schema.md
├── data/
│   ├── Medical_Q&A/                # raw MedQuAD CSVs — IMMUTABLE (exists)
│   ├── medical_by_source/          # per-domain JSONL (derived) — treat as raw (exists)
│   ├── clean/                      # cleaned + split outputs (tool-generated) (exists)
│   ├── interim/                    # (planned) intermediate transforms
│   └── processed/                  # (planned) final train/heldout ready for modeling
├── db/                             # (planned — ADR-010, deferred) unified SQLite store
├── docs/
│   ├── plan/                       # (exists) renovation task specs T*.md + README (ADR-015)
│   ├── audit/                      # (exists) P0 audit outputs (CODE_MAP, LEAKAGE_CENSUS, CLAUDE_ENV_AUDIT)
│   └── adr/                        # (planned — ADR-009) full ADR files; summaries stay in rules/decisions.md
├── logs/experiments/               # phase results (summary.jsonl, memory, faiss, debug) — evidence dir (exists)
├── models/                         # (planned — P3) LoRA adapters, encoders (git-ignored, large)
├── notebooks/                      # analysis notebooks (exists)
├── reports/                        # (planned) generated figures/reports; reports/figures/
├── schemas/                        # (exists) JSON schemas (log_record.schema.json)
├── scripts/                        # standalone stage scripts (import from src/) (exists)
├── src/
│   ├── core/                       # (exists, EXEMPLAR/ALIVE) ModelClient ABC, types, logger, tokens — shared base
│   ├── providers/                  # (exists, EXEMPLAR) factory + groq/local/gemini clients — the ProviderRegistry
│   ├── utils/                      # (exists) prompt_loader (reused by PresetRegistry)
│   ├── tlw/                        # (planned — the NEW config-driven core; grows here, block by block)
│   │   ├── config/                 #   (planned — T2.1) loader + validation (six-slot contract, fail-loud)
│   │   ├── registries.py           #   (planned — T2.2) MemoryRegistry, PresetRegistry, StrategyRegistry (factory pattern)
│   │   ├── memory/                 #   (planned — T2.5) MemoryBackend impls: none, faiss (port of simplified/memory.py), rag
│   │   ├── prompts/                #   (planned — T2.4/T1.5) PromptPreset registry over the prompt catalog
│   │   ├── evaluation/             #   (planned — T2.3) Judge + correctness/reference-match diagnostics; leakage tests
│   │   ├── loop/                   #   (planned — T2.4) ArmStrategy classes A/B/C/D; NO ground-truth hint paths
│   │   └── runner.py               #   (planned — T2.6) resolve config → build slots → run arm → write summary.jsonl
│   ├── simplified/                 # (FROZEN LEGACY) old loop core — keep running, do not extend; deleted T2.9
│   ├── prompts/                    # (exists) student.py ALIVE; teacher.py DEAD (CODE_MAP.md:58) → T2.9
│   └── eval/                       # (exists) metrics.py ALIVE; reports.py + retrieval.py DEAD (CODE_MAP.md:78-79) → T2.9
├── tests/                          # (planned — mirrors src/tlw/; created when first block lands, T2.1+)
├── tools/dataset/                  # (exists) Dataset Readiness Assessor + cleaner — track in git (CODE_MAP BLOCKER)
├── app/                            # (planned — P3+) product frontend/backend; NOT designed yet (ADR-015)
├── simplified_teaching_loop.py     # (FROZEN LEGACY) monolithic entrypoint (843 ln, MESSY) — retired T2.9
├── simplified_experiment_runner.py # (FROZEN LEGACY) old CLI entrypoint — retired T2.9
├── run.py                          # (planned — T2.6) new entrypoint: run.py --config experiments/<file>.yml
├── requirements.txt / environment.yml (exists)
└── README.md (exists)
```

---

## §C Module boundaries (the new core, `src/tlw/`)

Each block owns exactly one concern and talks to the rest only through a seam interface
(§D). Blocks never import each other's internals; the **runner** wires them via the registries.

| Block | Package | Single responsibility | Reuses / replaces |
|---|---|---|---|
| **config** | `src/tlw/config/` | Load `base.yml` + experiment override, deep-merge, validate (V1–V7, `schema.md`), resolve paths. Fail-loud. | Generalizes `src/utils/prompt_loader.py` YAML loading (CODE_MAP.md:283) |
| **providers** | `src/providers/` *(exists)* | Build a ModelClient for any slot (student/teacher/judge). | Keep as-is — EXEMPLAR (CODE_MAP.md:65) |
| **memory** | `src/tlw/memory/` | Store/retrieve teaching notes; `none`/`faiss`/`rag` backends behind one interface. Store-time GT tripwire (T1.3, §0.2). | Ports `src/simplified/memory.py` (CODE_MAP.md:298) |
| **prompts** | `src/tlw/prompts/` | Resolve a preset **name** → rendered prompt for student/teacher. | Wraps `config/prompts_config.yml` via prompt_loader; catalog from T1.5 |
| **evaluation** | `src/tlw/evaluation/` | Score an answer via a Judge; keep correctness ≠ reference-match separate; leakage guards. | Reworks `src/simplified/metrics.py` + `src/eval/metrics.py` (deterministic) |
| **loop** | `src/tlw/loop/` | Arm strategies A/B/C/D as swappable classes; orchestrate rounds; **no GT hint paths**. | Refactors monolithic run() (CODE_MAP.md:338) |
| **runner** | `src/tlw/runner.py` + `run.py` | Resolve config → build the six slots from registries → run the arm → record resolved config + results to `summary.jsonl`. | Replaces `simplified_experiment_runner.py` |

---

## §D Seams table (interfaces + registries)

Every seam is an interface (method names only — signatures finalized by the owning P2 task)
resolved through a registry. Registry names match the Config Contract slots (`schema.md`).

| Seam | Interface (methods) | Registry (slot) | Status / source |
|---|---|---|---|
| **ModelClient** | `chat_completion(messages, model, temperature, max_tokens)` · `stream(...)` | **ProviderRegistry** (A student, B teacher, F judge) — `build_client(provider, **kwargs)` | **exists**: `src/core/client.py` (LLMClient ABC, CODE_MAP.md:86) + `src/providers/factory.py` (CODE_MAP.md:65) |
| **MemoryBackend** | `store(episode)` · `retrieve(query, top_k)` · `update_outcome(id, scores)` · `stats()` | **MemoryRegistry** (D memory) — `type ∈ {none, faiss, rag}` | planned (T2.5); port of `src/simplified/memory.py`. Methods align with T1.3 memory spec |
| **PromptPreset** | `get(name)` · `render(name, **vars)` | **PresetRegistry** (C preset) — preset name → template | planned (T2.4); wraps `src/utils/prompt_loader.py`; names from T1.5 |
| **Judge** | `score(question, answer, mode)` → `{score, ...}` · `mode ∈ {blind, gt_comparing}` | (ProviderRegistry judge client, slot F) + eval block | planned (T2.3); from `src/simplified/metrics.py`. §0.2: judge family ≠ student family (V2) |
| **ArmStrategy** | `run(question, student, teacher, memory, judge, params)` → rounds | **StrategyRegistry** (E params.arm) — `arm ∈ {A,B,C,D}` | planned (T2.4); A baseline / B self-refine / C blind-teacher / D sighted-teacher (ADR-002) |

Pattern for all registries: copy `src/providers/factory.py` — a `_REGISTRY` dict + `@register`
decorator + `build_*()` resolver (CODE_MAP.md:243-263 recommends exactly this for the slots).

---

## §E Placement + migration policy (strangler)

- **`data/Medical_Q&A/` and `data/medical_by_source/` are immutable** — never edit; derive
  forward into `data/clean/` → (planned) `data/processed/`.
- **New core code goes under `src/tlw/`**, one block per P2 task, beside the legacy. Reusable
  tools → `tools/`; one-off stage scripts → `scripts/` (import shared logic from `src/`).
- **`src/providers/` and `src/core/` stay where they are** (EXEMPLAR/ALIVE) and are imported
  in place by `src/tlw/`. Relocating them under `src/tlw/` is optional cleanup, not required —
  do not churn.
- **Frozen legacy = do-not-extend, delete-in-T2.9:** `src/simplified/*`, `src/prompts/teacher.py`,
  `src/eval/reports.py`, `src/eval/retrieval.py`, root `simplified_teaching_loop.py`,
  `simplified_experiment_runner.py`, `config/simplified_config.yml`. They keep working so the
  ADR-001 baseline stays reproducible until the new arms are proven.
- **Each P2 task states exactly what it may touch** (scope discipline, ADR-015):
  - T2.1 config loader → creates `src/tlw/config/` + `config/base.yml`; touches nothing legacy.
  - T2.2 registries → creates `src/tlw/registries.py`.
  - T2.3 eval / T2.5 memory / T2.4 loop → create their `src/tlw/` sub-packages + `tests/` mirror.
  - T2.6 runner → creates `src/tlw/runner.py`, `run.py`, `experiments/*.yml`.
  - **T2.9 demolition only** deletes DEAD + frozen-legacy files and finalizes this tree.
- **No file is moved or refactored before its P2 task.** P1 (this task included) writes paper
  only; zero code/file moves.
- **Tests mirror `src/tlw/` under `tests/`** — created when the first block lands, not before.

---

## §F Junk / smell checklist (housekeeping flags these) — v2

- **DEAD files (0 importers, T2.9 demolition targets — CODE_MAP.md:227-237):**
  `src/eval/reports.py`, `src/eval/retrieval.py`, `src/prompts/teacher.py`,
  `src/simplified/console_logger.py` (empty), `src/simplified/logger_manager.py` (empty).
  These are *known and scheduled* — flag only if they gain new importers (that would be a
  regression) or if they still exist after T2.9.
- **Untracked-but-exemplary code** (CODE_MAP BLOCKER; CLAUDE_ENV_AUDIT BLOCKER): `tools/`,
  `.claude/`, `docs/plan/`, `docs/audit/`, `scripts/{assess_all,compare_judges,compare_students}.py`
  are `?? ` in git — flag as needs-commit, not as delete-junk.
- **Files claiming to be "clean" that still contain raw boilerplate** — e.g.
  `data/medical_all_clean.jsonl` (misnamed; still has HPO boilerplate hits, under D3/D4 audit,
  CODE_MAP.md:354).
- **Hardcoded absolute paths in committed configs** — e.g. `C:\Users\...\Desktop\...` in
  `logs/experiments/*/configs/*.yml` (`logs/experiments/phase6/configs/P6A-NoMemory-Baseline.yml:42-43`,
  schema.md §config-contract). Killed structurally by the T2.1 loader's path resolution.
- **Config comment-drift** — a comment disagreeing with the live value
  (`config/simplified_config.yml:45-53`, schema.md V1). New configs use `base.yml` single-source.
- **New reusable code placed at repo root or `src/simplified/`** instead of `src/tlw/`, `src/`,
  or `tools/` (strangler violation — new code must not grow inside frozen legacy).
- **Numbers in `docs/`/`README` that disagree with `logs/experiments/*/summary.jsonl`** (§0.1).
- Debug dumps, `*.tmp`, editor backups, stray `__pycache__/` not git-ignored.
- Duplicated data files with no clear owner.
