# experiments/ — one YAML per run condition

Each file is **slot overrides only** over `config/base.yml` — never a full config. The runner
(`src/tlw/runner.py`, invoked through root `run.py`) merges `base.yml` → this file →
any `EXPERIMENT_*` environment override, validates the result against the Config Contract
(V1–V8, `.claude/rules/schema.md`), and runs it. A reader should be able to see an
experiment's *intent* from its diff, not hunt through a wall of settings.

Files are grouped by the **question each study answers**, and named so the condition is
readable without opening anything (ADR-034). The exact settings live in the file; the
directory name says what it is for.

## Running one

```
$env:EXPERIMENT_PARAMS_SEED = "42"
& "C:\Users\ham25\.conda\envs\tlw\python.exe" run.py --config experiments/teaching-loop/3-teacher-feedback.yml `
  --teacher-fallback local:qwen2.5:7b-instruct --judge-fallback local:llama3.1:8b
```

**The seed is supplied by the environment, not the file.** `params.seed` is the run's
identity, so the same config drives all three pre-registered seeds `{13, 42, 123}` without
being edited (schema.md layering rule 4). Validation rule V4 rejects a run with no seed.

### Flags

| Flag | What it does |
|---|---|
| `--config PATH` | required — the override file |
| `--data PATH` | dataset JSONL. Default is the 125-question Diabetes held-out set. **Smoke runs must pass `*_train.jsonl` instead — never the held-out set (§0.2).** |
| `--limit N` | first N records only, in file order, no shuffling — so `(path, limit)` always yields the same records |
| `--runs-dir PATH` | output root. Used to keep the side studies out of the headline directory, e.g. `--runs-dir runs/rag-medquad-fair-tests` |
| `--teacher-fallback provider:model` | retry-with-backoff, then fall back for that one call. Off by default. Never point it at a 70B — it cannot run on an 8 GB card |
| `--judge-fallback provider:model` | same for the judge slot. The §0.2 family check (V2) runs against the config-declared **primary** judge; a runtime fallback is resilience, not experiment identity |
| `--no-faithfulness` | skips the inline RAG groundedness diagnostic so the correctness judge stays inside the daily token cap. It is computed offline afterwards, and it is a diagnostic — never the headline |

Every fallback that fires is counted into `summary.jsonl` (`teacher_fallback`, `judge_fallback`)
alongside the configured pair, so a run that leaned on fallback is visible rather than hidden (§0.1).

### What a run writes

`runs/<study>/<config-stem>__seed<N>__<UTC timestamp>/`, containing `config_used.json` (the
fully merged config), `rounds.jsonl` (one line per round per question), `summary.jsonl`
(one line, shape in `.claude/rules/schema.md`), and `memory/` only when `memory.type != none`.
Never `logs/experiments/` — that directory is immutable evidence from the pre-renovation
system and is guard-blocked for writes (ADR-012).

---

## The studies

### `teaching-loop/` — does an iterative teacher-student loop teach a small model?

The pre-registered four-arm ablation. All four differ from `base.yml` in the same three ways
— student `qwen2.5:3b` (the product floor), judge Groq `llama-3.1-8b-instant` (off the local
GPU so the student is not competing with it), and `pass_threshold: 1.0`, meaning judge score
≥ 4, "correct **and** complete". That bar came from the T2.7 pilot: at ≥ 3 every arm scored
about 100% and the ablation could not have shown anything.

| File | Arm | What it measures |
|---|---|---|
| `1-baseline.yml` | A | one attempt, no feedback |
| `2-self-refine.yml` | B | the model critiques and rewrites its own answer |
| `3-teacher-feedback.yml` | C | a larger model critiques it, **without** seeing the reference |
| `4-teacher-sees-answer.yml` | D | the teacher is shown the reference — a leakage ceiling, not a result |

Headline = `pass_rate(C) − pass_rate(B)` with a 95% paired cluster-bootstrap interval.
Memory is `none` for all four (ADR-022 (c)), so the comparison isolates teacher feedback.

### `pilots/` — the pre-registration pilots

The same four arms at 3B and 7B, run before the full measurement to check that the loop
engaged and the bar left headroom. They set `params.seed` inline because a pilot is a single
run, not a seeded protocol. They live one directory deeper on purpose: `discover_runs` scans
one level, so a headline command structurally cannot pool a pilot into a result (ADR-034).

### `rag-medquad/` — does retrieval help a model that already knows the domain?

Single-pass (`arm: A`, `max_rounds: 1`) so retrieval is the only variable, over a held-out-free
index built by `python -m tools.rag.cli`. Judge and bar are identical to the loop study, which
is what makes the two comparable.

| File | Student | Retrieval |
|---|---|---|
| `small-model-no-rag.yml` | `qwen2.5:3b` | none — this run is reused as the loop study's arm A |
| `small-model-with-rag.yml` | `qwen2.5:3b` | `indexes/medquad-diabetes-train`, top-3, floor 0.35 |
| `large-model-no-rag.yml` | `qwen2.5:7b-instruct` | none |
| `large-model-with-rag.yml` | `qwen2.5:7b-instruct` | same index |

A RAG run **must** target the held-out set. Pointing one at `*_train.jsonl` trips the RAG-L3
filter by design, because a training query retrieves its own answer.

### `rag-medquad-fair-tests/` — is that null an artifact of a weak retriever or a small library?

`matching-question-type-only.yml` reranks so only same-question-type passages survive;
`much-bigger-library.yml` swaps in the 24×-larger seven-domain index. Both single seed.

### `student-prompt/` — does the student prompt matter?

`detailed-prompt-style.yml` is the baseline with one change: the ORCA student preset instead
of MINIMAL. Note the preset registry is one flat namespace, so the student variant registers
as `orca_student` — plain `orca` is the *teacher* preset.

### `lora/` — superseded

`generate-training-data.yml` was written to use the loop as an offline data factory and then
abandoned: self-refine does not engage on the near-ceiling training split, so there was no
signal to distil. The adapter that was actually trained and evaluated used standard gold-SFT
built by `scripts/lora/build_data.py`, which calls no model at all. The file is kept because
the abandoned recipe is part of the record.

---

## Adding one

Name the directory after the question and the file after the condition, in words a reader who
has never seen this repository can decode — `much-bigger-library.yml`, not `bigcorpus2.yml`.
Use ordinals only where step N+1 genuinely contains step N. Put only the diff in the file, and
a header comment saying what it is testing and why.
