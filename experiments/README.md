# experiments/ — Track-A run configs (T2.6)

One YAML per run = **slot overrides only** over `config/base.yml` (ADR-016
Layering rule 2). The runner (`src/tlw/runner.py`, invoked via root `run.py`)
merges `base.yml` → this file → any `EXPERIMENT_*` env override, validates the
result (V1–V8, `.claude/rules/schema.md`), and runs it.

## Usage

```
& "C:\Users\ham25\.conda\envs\tlw\python.exe" run.py --config experiments/trackA_p2_armC_diabetes.yml
```

Flags (CLI-only — dataset selection is deliberately **not** a config slot,
T2.6 build decision 3, no slot G):
- `--config PATH` (required) — an `experiments/*.yml` override file.
- `--data PATH` — dataset JSONL (default: `data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl`,
  the real Track-A measurement set). **Smoke/dry runs MUST pass the `_train.jsonl`
  split instead — never the held-out set (§0.2).**
- `--limit N` — only run the first N records (deterministic: file order, no
  shuffling — same `(path, limit)` always yields the same records).

Outputs land under `runs/<run_id>/` (repo-root `runs/`, never
`logs/experiments/` — that dir is immutable evidence, guard-blocked for
writes, ADR-012):
- `config_used.json` — the fully-merged, resolved config for this run.
- `rounds.jsonl` — one line per round per question.
- `summary.jsonl` — one line, `.claude/rules/schema.md` experiment-summary shape.
- `memory/` — only created when `memory.type != none`.

`run_id = <config-stem>__seed<seed>__<UTC timestamp>`.

## Naming convention (ADR-016)

`experiments/<track><phase>_<arm>_<slug>.yml`, e.g. `trackA_p2_armC_diabetes.yml`.
`<track>` = `trackA`/`trackB`; `<phase>` = `p2`, `p3`, …; `<arm>` = `armA`..`armD`
(ADR-002); `<slug>` = short domain/variant tag.

## The four headline configs (this task)

All four inherit `config/base.yml`'s P1-gate defaults (ADR-022) unchanged —
student `qwen2.5:7b-instruct` (local/Ollama), teacher Groq `qwen/qwen3-32b`,
preset `minimal`/`orca`, judge local `llama3.1:8b` (blind), `memory.type: none`
for ALL FOUR (headline is memory-off across the board, ADR-022 (c)). Each file
overrides only `params.arm` + `params.seed`:

| File | Arm | What differs from base.yml | Teacher calls? | Memory |
|---|---|---|---|---|
| `trackA_p2_armA_diabetes.yml` | A — baseline | `params.arm: A` | none (1 pass) | none |
| `trackA_p2_armB_diabetes.yml` | B — self-refine | `params.arm: B` | none (student self-critiques) | none |
| `trackA_p2_armC_diabetes.yml` | C — blind-teacher (the treatment) | `params.arm: C` | yes, blind (no GT) | none |
| `trackA_p2_armD_diabetes.yml` | D — sighted-teacher (leakage ceiling) | `params.arm: D` | yes, sees GT (its own prompt only, §0.2) | none |

**Headline claim = `pass_rate(C) − pass_rate(B)`** with a 95% CI (EVAL_SPEC.md
§4.3) — computed by T2.8 from the `summary.jsonl`/`rounds.jsonl` these produce,
run on the real 125-question held-out set across the 3 pre-registered seeds
(`{13, 42, 123}`, EVAL_SPEC.md §4.1). D is always the "leakage ceiling" —
context, never a claimed result.

## Fallback flags (robustness for the long Groq-primary full run, 2026-07-15)

`--teacher-fallback provider:model` and `--judge-fallback provider:model`
wrap that slot's primary client in a retry-with-backoff + fallback wrapper
(`src/tlw/runner.py::_FallbackClient`): a failing call is retried on the
primary a few times (honoring a parsed `Retry-After` hint when the error
text carries one, else exponential backoff), and only THEN switches to the
fallback client for that one call. Off by default (no flag = plain client,
no retry). Every fallback hit is counted into `summary.jsonl`'s
`teacher_fallback` / `judge_fallback` blocks, and the configured pair is
recorded verbatim (`teacher_fallback_configured` / `judge_fallback_configured`)
so a run where fallback fired a lot is visible, not hidden (§0.1). These are
CLI-only, deliberately outside the six-slot Config Contract (same precedent
as `--data`, T2.6 build decision 3) — fallback is a runtime resilience
concern, not experiment identity. Never point either flag at a 70B (hub
instruction — can't run on an 8GB card); when no fallback is configured, an
exhausted primary degrades to a null/error result instead of raising, so one
bad call never aborts a multi-hour run.

`--teacher-fallback-model <model>` (T2.6 original, local-only) still works as
a deprecated alias for `--teacher-fallback local:<model>`.

## The four FULL-RUN configs (fast-judge design, hub 2026-07-15)

`trackA_full_arm{A,B,C,D}_diabetes.yml` — the configs actually used for the
pre-registered 125×3-seed measurement. They diverge from the four `_p2_`
headline files above in three ways, all aimed at making the ~22h run fast
and non-degenerate (T2.7 pilot findings, `.claude/rules/todo.md`):

| Slot | `_p2_` headline files | `_full_` files | Why |
|---|---|---|---|
| student | local `qwen2.5:7b-instruct` | local `qwen2.5:3b` | product floor (ADR-015); Groq has no small Qwen so it MUST be local |
| judge | local `llama3.1:8b` | **Groq** `llama-3.1-8b-instant` | frees the 8GB GPU so the 3B student never judge-cohosts -> ~2-3x faster locally; still Llama family != Qwen student (§0.2/V2) |
| `eval.pass_threshold` | 0.75 (score>=3) | **1.0 (score>=4)** | the T2.7 headroom-pilot bar — "correct AND complete" restores headroom (baseline ~67-73% vs the old ceiling-effect ~100%) |

`params.seed` is deliberately NOT set in these files — supply it per
invocation via `EXPERIMENT_PARAMS_SEED` (schema.md Layering rule 4) so the
same file drives all 3 pre-registered seeds `{13, 42, 123}` without editing.
Teacher/memory stay at `config/base.yml`'s defaults (Groq `qwen/qwen3-32b`;
`memory.type: none` — headline is memory-off for all four arms, ADR-022 (c)).

```
$env:EXPERIMENT_PARAMS_SEED = "42"
& "C:\Users\ham25\.conda\envs\tlw\python.exe" run.py --config experiments/trackA_full_armC_diabetes.yml `
  --teacher-fallback local:qwen2.5:7b-instruct --judge-fallback local:llama3.1:8b
```

Smoke/dry runs of these files MUST still pass `--data
data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_train.jsonl --limit N`
(never the heldout set, §0.2) — see each file's header for the exact command.

## Not built here (future experiment files, not required by T2.6)

- `trackA_p2_armCprime_diabetes.yml` / `armDprime` — the **C′/D′ memory-on
  ablation** (`memory: { type: faiss }` override). Memory's marginal value =
  `C′ − C`, its own separate number (ADR-022 (c), schema.md Memory v2 §5).
- Seed sweeps (`{13, 123}`) — same files, override `params.seed` (or set
  `EXPERIMENT_PARAMS_SEED=13` and reuse the same file, schema.md Layering rule 4).
