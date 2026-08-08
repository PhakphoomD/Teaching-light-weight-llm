# Canonical Repo Structure (v3 — ADR-034)

Source of truth for **housekeeping** and for every build task. Generated from the executed tree on
2026-08-07 and re-synced 2026-08-08 after P3-C (ADR-036 moved `RAG_LAW.md` to `archive/`, added
`EXPERIMENT_RESULTS.md`, emptied `notebooks/`), not from a plan — v2 had drifted into describing paths that no longer existed while
omitting ~14 that did, and every audit compared against that wrong map. **If this file and the repo
disagree, this file is the bug.**

---

## §A Design principles

1. **Source and artifacts never share a directory.** Anything a command regenerates lives under an
   artifact root (`runs/`, `indexes/`, `models/`) or the derived-evidence root (`reports/`). Nothing
   an experiment produces is written next to code.
2. **Group by the question answered, not by the order things ran.** `runs/rag-wixqa/` says what it
   is; `runs_wixqa/` said only when it happened.
3. **Names read as English.** The path carries a short human label; the exact experimental condition
   lives in a `manifest.json` beside the run. Words, not codes (`wider-context`, not `chunk2400`).
   Hyphens for directories, underscores for `.py` (PEP 8 — a rule the reader already knows).
   **Ordinals only where step N+1 genuinely contains step N** (a ladder), never for a factorial.
4. **The dependency arrow points one way:** `scripts/` → `src/`/`tools/`, never sideways.
5. **Change behaviour by editing configuration, not code.** Six slots, each resolved through a
   registry (`schema.md` Config Contract).
6. **Every move must earn its cost.** Where the cost exceeds the benefit, leave it alone and say so.

---

## §B The tree

```
Teaching-light-weight-llm-based-project/
├── README.md                  front door: findings, install, usage
├── run.py                     the entrypoint:  run.py --config experiments/<file>.yml
├── pytest.ini                 testpaths + pythonpath (replaced a sys.path hack in tests/conftest.py)
├── requirements.txt · environment.yml
│
├── .claude/                   SSOT — rules/, agents/, skills/, hooks/, settings.json
│
├── config/                    authored configuration only
│   ├── base.yml               ALL six-slot defaults — the single source (ADR-016)
│   ├── prompts/{student,teacher}.yml      preset templates (ADR-020)
│   └── archive/               superseded prompt catalogue
│
├── experiments/               one YAML per run condition; grouped by study (ADR-034)
│   ├── teaching-loop/         1-baseline · 2-self-refine · 3-teacher-feedback · 4-teacher-sees-answer
│   ├── rag-medquad/           {small,large}-model-{no,with}-rag
│   ├── rag-medquad-fair-tests/  matching-question-type-only · much-bigger-library
│   ├── student-prompt/        detailed-prompt-style
│   ├── lora/                  generate-training-data
│   └── pilots/                teaching-loop-*-{3b,7b} — the pre-registration pilots
│
├── data/                      INPUTS ONLY — nothing an experiment generates lives here
│   ├── Medical_Q&A/           raw MedQuAD CSVs — IMMUTABLE (guard-protected)
│   ├── medical_by_source/     per-domain JSONL — treated as raw
│   ├── clean/                 cleaner + split output (the pipeline product)
│   ├── processed/             model-ready derivatives (LoRA SFT pairs, hard-tail question lists)
│   ├── calibration/           judge boundary set
│   ├── external/wixqa/        third-party data (MIT) — gitignored; scripts/dataset/fetch_wixqa.py
│   └── legacy/                6 pre-renovation loose *.jsonl, kept for provenance
│
├── indexes/                   BUILT search indexes — gitignored, rebuildable  (was data/rag/)
│   ├── medquad-diabetes-train/ · medquad-all-topics/ · wixqa-help-centre/
│
├── src/                       library code — imported, tested, stable
│   ├── core/                  LLMClient ABC, types, logger, tokens        (EXEMPLAR seam)
│   ├── providers/             factory + groq/local/gemini clients          (EXEMPLAR registry)
│   └── tlw/                   "Teaching Lightweight LLMs" — the config-driven core
│       ├── config/            loader · schema · validation (V1–V8, fail-loud)
│       ├── registries.py      Memory / Preset / Judge / Strategy registries
│       ├── memory/            faiss_backend · rag_backend · tripwire (store-time GT gate)
│       ├── prompts/           loader · presets
│       ├── evaluation/        judge · diagnostics · faithfulness · calibration
│       ├── loop/              core (assert_gt_free) · strategies (arms A–D)
│       ├── analysis/          stats · loaders · report · rag_report · cli
│       ├── providers.py       Ollama client, registered as "local"
│       ├── wixqa/             the WixQA study library — paths · prompts · retrieval · grounding
│       └── runner.py          composition root: config → six slots → run → summary
│
├── scripts/                   thin drivers, one package per study (§A4)
│   ├── dataset/               prepare_medquad · split_by_source · assess_all · fetch_wixqa
│   ├── wixqa/                 run_* · build_* · analyze_* · judge · repair_empty
│   ├── lora/                  build_data · train · evaluate
│   ├── rag/                   faithfulness · selective_simulation · reliability · rejudge
│   ├── calibration/           build_probe · report · compare_judges · compare_students
│   └── make_figures.py        regenerates every figure and table from committed logs
│
├── tools/                     reusable, importable CLI utilities
│   ├── dataset/               cleaner · Readiness Assessor · split · judge · embeddings · app
│   └── rag/                   builder · cli — config-driven index construction
│
├── tests/                     mirrors src/ and tools/;  `tests/__init__.py` is load-bearing
│   ├── tlw/{config,memory,prompts,evaluation,loop,analysis,runner,wixqa}/
│   └── tools/rag/
│
├── runs/                      THE artifact root — gitignored except the evidence files below
│   ├── teaching-loop-medquad/   does the loop work? (ADR-024)        + pilots/
│   ├── rag-medquad/             does RAG help a model that knows? (ADR-027)
│   ├── rag-medquad-fair-tests/  is that null an artifact? (ADR-029)
│   ├── rag-medquad-reliability/ does RAG help reliability?  + hard-questions-only/
│   ├── student-prompt-medquad/  does the prompt matter? (ADR-029 gate-f)
│   ├── rag-wixqa/               does RAG help when there IS a gap? (ADR-030…033)
│   │                            1-no-rag → 2-rag-basic → 3-rag-better-retriever
│   │                            → 4-rag-wider-context   + pilots/
│   └── judge-calibration/       is the judge trustworthy? (T2.3)
│
├── reports/                   DERIVED EVIDENCE — git-tracked, small, human-readable
│   ├── README.md              study → question → report → reproduce command
│   ├── rag-wixqa/ · lora-medquad/ · …
│   └── figures/
│
├── docs/
│   ├── README.md              "start here" index
│   ├── EXPERIMENT_RESULTS.md  the full record — objectives, decisions, every measurement (ADR-036)
│   ├── TRACK_A_RESULTS.md · RAG_RESULTS.md · WIXQA_RESULTS.md · PRODUCT_RESULTS.md
│   ├── RAG_RELIABILITY_ANALYSIS.md
│   ├── plan/ · audit/         task specs, design docs, P0 audits
│   └── archive/               SUPERSEDED docs, each with a banner saying what was wrong
│                              (incl. RAG_LAW.md, superseded by EXPERIMENT_RESULTS.md — ADR-036,
│                               and v1-notebook-narrative.md recovered from the deleted notebook)
│
├── app/                       the demo the results point at — engine + showcase builder (T3.15)
├── logs/experiments/phase0..6/  pre-renovation evidence — IMMUTABLE, guard-protected
├── models/                    LoRA adapters + base weights — gitignored
├── notebooks/                 empty by design; README.md records why (ADR-036)
├── schemas/
```

---

## §C What goes where (the rule, when you are unsure)

| If it is… | it goes in | because |
|---|---|---|
| imported by other code, or tested | `src/` (or `tools/` if it is a CLI utility) | §A4 — only `src`/`tools` may be imported |
| a script that drives one experiment | `scripts/<study or purpose>/` | thin driver; imports from `src/` |
| produced by a run | `runs/<study>/<condition>/` | §A1 — artifacts never sit beside source |
| a number a reader must be able to check | `reports/<study>/` | tracked; this is what makes "computed from a committed log" true |
| a built index / adapter / weight | `indexes/` or `models/` | rebuildable, gitignored |
| input data we produced | `data/{clean,processed}/` | derived forward from raw, never edited in place |
| input data someone else produced | `data/external/` + a fetch script | licence provenance, and a clone must be able to re-acquire it |
| prose for a human | `docs/` | narrative, authored |
| superseded but historically meaningful | `*/archive/` with a banner | the correction is part of the honest record |

**Run outputs.** `runs/<study>/<condition>__seed<N>__<UTC ts>/` for framework runs (a run is a dated
event); `runs/<study>/<step>/seed<N>.jsonl` for the standalone WixQA scripts. Either way the
**directory names the condition and a `manifest.json` beside it carries the exact settings** — never
encode the condition in a filename. Pilots and subsets go one level deeper (`pilots/`,
`hard-questions-only/`) so that `discover_runs`, which scans one level, cannot mix them into a
headline. That is a structural guarantee, not a convention to remember.

---

## §D Seams (interfaces + registries)

| Seam | Interface | Registry (slot) | Where |
|---|---|---|---|
| **ModelClient** | `chat(messages, temperature, max_tokens, timeout_s, seed=None)` | ProviderRegistry (A student, B teacher, F judge) | `src/core/client.py` + `src/providers/factory.py` |
| **MemoryBackend** | `store` · `retrieve` · `update_outcome` · `stats` | MemoryRegistry (D) — `none` / `faiss` / `rag` | `src/tlw/memory/` |
| **PromptPreset** | `get(name)` · `render(name, **vars)` | PresetRegistry (C) | `src/tlw/prompts/` |
| **Judge** | `score(question, answer, mode)` | slot F + eval block | `src/tlw/evaluation/judge.py` |
| **ArmStrategy** | `run(question, student, teacher, memory, judge, params)` | StrategyRegistry (E `params.arm`) | `src/tlw/loop/strategies.py` |

Every registry copies `src/providers/factory.py`: a `_REGISTRY` dict + `@register` decorator + a
`build_*()` resolver.

---

## §E Junk / smell checklist (what housekeeping flags)

- **A run artifact outside `runs/<study>/`** — a new `runs_*` root at top level is the exact drift
  ADR-034 removed.
- **Analysis output written inside `runs/`** — derived evidence belongs in `reports/`.
- **A hardcoded absolute path** (`ROOT = Path("C:/Users/…")`). 13 scripts had this; it made the
  headline results unreproducible from a clone (§0.3). Use `Path(__file__).resolve().parents[N]`.
- **A run-discovery glob keyed on a config stem** (`trackB_p3_3bRAG*`) — it breaks silently on
  rename. Key on the label, and fail loud when nothing matches.
- **A script importing another script.** Shared logic belongs in `src/`; a driver that other
  drivers import is library code wearing a script's name, and renaming it changes what a different
  experiment measures. The arrow points one way (§A4).
- **A name only an insider can read** — if understanding it needs project vocabulary, rename it.
- **A test that skips when its fixture is missing** without distinguishing "absent in a fresh
  clone" (skip is right) from "the layout moved" (must fail).
- **A `tests/<name>/` that shadows a top-level package** — `tests/__init__.py` prevents this; do not
  delete it.
- Numbers in `docs/`/`README` that disagree with the source log (§0.1).
- Debug dumps, `*.tmp`, editor backups, stray `__pycache__/` not gitignored.

---

## §F Tracking policy

**Track what a reader must check; ignore what a command rebuilds.**

| Tracked | Ignored |
|---|---|
| `runs/**/summary.jsonl`, `config_used.json`, `manifest.json`, `README.md` | `runs/**` everything else (raw generations, `rounds.jsonl`) |
| everything under `reports/` | `indexes/`, `models/`, `data/external/` |

The `.gitignore` block uses `runs/**` plus `!runs/**/` and per-file negations. **The `!runs/**/` line
is load-bearing** — without it git never descends into `runs/<study>/<condition>/` and every negation
below it is dead. Keep comments on their own lines: gitignore has no trailing-comment syntax, and a
trailing comment silently disables the whole rule.
