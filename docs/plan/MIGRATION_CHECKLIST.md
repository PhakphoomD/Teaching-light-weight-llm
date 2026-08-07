# Migration Safety Check — ADR-034 restructure (phases 1–5)

**Status:** COMPLETE. **Author:** codebase-steward.
**Output contract:** ADR-008 Archetype R + an executable checklist.
**Scope:** verify that executing `docs/plan/STRUCTURE_PROPOSAL.md` v2 (as approved by ADR-034,
phases 1–5) cannot silently break anything. **Nothing was moved, renamed or deleted by this task.**

> Reading order: `VERDICT` → `FINDINGS` → the phase checklist (§P1–§P5). Every claim cites a
> `file:line` that was opened or a command that was run (§0.4).

---

## VERDICT

# **NOT safe to execute as written — safe WITH CHANGES.**

The *design* is sound and I verified its central claim by execution rather than by reading: the
proposed `runs/<study>/<condition>/` layout reproduces ADR-024's headline **exactly**
(C−B `+0.003 [−0.021,+0.029]` p=1.0000, B−A `+0.091 [+0.051,+0.133]`, arms
0.821/0.912/0.915/0.940) and **repairs a live §0.1 defect** — today the documented command
`--runs-dir runs` silently pools 14 pilot runs and returns `+0.001`, not the published `+0.003`.
The migration is worth doing.

But three things must change before anyone runs a `git mv`:

| # | Must change | Consequence if executed as written |
|---|---|---|
| **BLOCKER-1** | **Do not delete `runs_hardtail/`** (ADR-034 decision 5) | It is the sole source of the published table at `docs/RAG_RELIABILITY_ANALYSIS.md:16-17` — I recomputed `0.606 / 0.640 / +0.034` and pass@5 `0.89 / 0.74` from it exactly. Deleting it is an irreversible §0.1/§0.4 regression. **§0.6 — needs the user's decision; I cannot edit ADR-034.** |
| **BLOCKER-2** | **Do not paste the `.gitignore` block from `STRUCTURE_PROPOSAL.md:836-847`** | Its trailing `#` comments are parsed as part of the pattern (gitignore has no trailing-comment syntax). Verified with real git: `git add -A -n` offers **nothing**. Zero evidence files become tracked and `README.md:90` stays false — silently. Corrected literal block in §V1.7. |
| **MAJOR-1** | **Keep the duplicated `runs_rag/trackA_full_armA_*`** | `discover_runs` is one level deep and cannot see across studies. Dropping them removes the `3B` label, so §D step 3.9's own verification (`--runs-dir runs/rag-medquad --rag` → the 4-arm table) cannot pass. |

Plus four MAJORs the proposal missed (config-stem globs in 4 scripts; no writer for the new layout;
`calibration.py`'s output path; 10 runs hidden by the `hard-questions-only/` nesting) and 5 MINORs.
With §P0's four decisions taken and the corrected steps in §P1–§P5, execution is safe.

**Highest-risk step: §P3.7 (WixQA).** The `git mv` and the rewrites of `wixqa_analyze.py:32-35`
and `wixqa_dose_analyze.py:31-39` are mutually dependent, and `wixqa_dose_analyze.py` degrades
**silently** — `load_variant` skips a missing seed file with `continue`, so a half-renamed ladder
yields a plausible table computed on fewer replicates. De-risked by: (1) capturing the exact
pre-move oracle in §P2.2 *before* any move; (2) making 3.7 one atomic commit; (3) verifying on the
printed **`seeds 3 (600)`** column, not just on the delta.

---

## V1 — Path literals a move would break

### V1.1 The 13 hardcoded absolute `ROOT` literals — **CONFIRMED, count exact**

Command (run 2026-08-07):
```
grep -rn "^ROOT\s*=\|ROOT\s*=\s*Path(" scripts/ tools/ src/ run.py tests/
grep -rn "C:[\\/]Users[\\/]ham25" --include=*.py .
```

All 13 carry the identical literal
`ROOT = Path("C:/Users/ham25/Desktop/Torrens_Assessment/ITA602/Teaching-light-weight-llm-based-project")`:

| file:line |
|---|
| `scripts/wixqa_analyze.py:21` |
| `scripts/wixqa_baseline.py:16` |
| `scripts/wixqa_build_index.py:17` |
| `scripts/wixqa_dose_analyze.py:23` |
| `scripts/wixqa_grounding_compare.py:24` |
| `scripts/wixqa_grounding_ladder.py:34` |
| `scripts/wixqa_judge.py:22` |
| `scripts/wixqa_rag.py:17` |
| `scripts/wixqa_repair_empty.py:20` |
| `scripts/wixqa_retriever_ladder.py:32` |
| `scripts/wixqa_run3seed.py:32` |
| `scripts/wixqa_run3seed_retriever.py:26` |
| `scripts/wixqa_selfrefine.py:36` |

Correct siblings (the replacement pattern, `Path(__file__).resolve().parents[1]`):
`scripts/build_calibration.py:25`, `build_lora_data.py:25`, `eval_lora.py:18`,
`finish_when_groq_ready.py:21`, `train_lora.py:17`.
The other "correct" hits ADR-034 counts are in library code and use a different depth:
`src/tlw/config/loader.py:30` / `src/tlw/evaluation/calibration.py:44` /
`src/tlw/prompts/loader.py:18` = `parents[3]`; `src/tlw/runner.py:72` = `parents[2]`;
`tests/conftest.py:6` = `parents[1]`; `tests/tlw/memory/test_faiss_backend.py:18` = `parents[3]`.
**`.claude/hooks/guard.py:16` (`TLW = r"C:\Users\ham25\.conda\envs\tlw\python.exe"`) is a
legitimate §0.5 literal — do NOT touch it.**

**Replacement is depth-sensitive.** For a file at `scripts/<name>.py` the correct value is
`parents[1]`. If phase 6 later moves it to `scripts/wixqa/<name>.py` it becomes `parents[2]` —
which is exactly why phase 2 must be done *before* any script move and phase 6 stays out of scope.

### V1.2 `runs*` path literals inside the 13 + their siblings — the authoritative list

```
grep -rn "runs_hardtail|runs_lora|runs_orca|runs_rag|runs_reliability|runs_wixqa|runs/" --include=*.py scripts/ tools/ src/ tests/ run.py
```

**Live code paths (must be edited when the run roots move):**

| file:line | literal | post-move value |
|---|---|---|
| `scripts/build_calibration.py:50` | `glob.glob("runs_reliability/*/rounds.jsonl")` | `runs/rag-medquad-reliability/*/rounds.jsonl` |
| `scripts/eval_lora.py:107` | `ROOT / "runs_lora/lora_eval_result.json"` | `reports/lora-medquad/fine-tuned-vs-original.json` (phase 4.1) |
| `scripts/finish_when_groq_ready.py:64,67,70` | `"--runs-dir", "runs_rag"` ×3 | `runs/rag-medquad` |
| `scripts/rag_faithfulness.py:80` | `default="runs"` | **unchanged token, but see BLOCKER-1** |
| `scripts/rejudge.py:91` | `default="runs_rag"` | `runs/rag-medquad` |
| `scripts/reliability_analysis.py:53` | `default="runs_reliability"` | `runs/rag-medquad-reliability` |
| `scripts/selective_rag_sim.py:83` | `default="runs_rag"` | `runs/rag-medquad` |
| `scripts/wixqa_analyze.py:27` | `RUNS = ROOT / "runs_wixqa"` | `ROOT / "runs/rag-wixqa"` |
| `scripts/wixqa_baseline.py:57` | `out = ROOT / "runs_wixqa"` | `ROOT / "runs/rag-wixqa"` (+ filename change) |
| `scripts/wixqa_dose_analyze.py:27` | `RUNS = ROOT / "runs_wixqa"` | `ROOT / "runs/rag-wixqa"` |
| `scripts/wixqa_grounding_ladder.py:38` | `RL = ROOT / "runs_wixqa/retrieval_log_bge_chunk.jsonl"` | `ROOT / "runs/rag-wixqa/3-rag-better-retriever/retrieval-log.jsonl"` |
| `scripts/wixqa_rag.py:52` | `out = ROOT / "runs_wixqa"` | `ROOT / "runs/rag-wixqa"` |
| `scripts/wixqa_run3seed.py:42` | `OUT = ROOT / "runs_wixqa"` | `ROOT / "runs/rag-wixqa"` |
| `scripts/wixqa_run3seed_retriever.py:36` | `OUT = ROOT / "runs_wixqa"` | `ROOT / "runs/rag-wixqa"` |
| `scripts/wixqa_selfrefine.py:47` | `OUT = ROOT / "runs_wixqa"` | `ROOT / "runs/rag-wixqa"` |
| `src/tlw/evaluation/calibration.py:46` | `OUTPUT_DIR = PROJECT_ROOT / "runs" / "calibration"` | `PROJECT_ROOT / "runs" / "judge-calibration"` — **MISSED BY THE PROPOSAL** (see MAJOR-2) |
| `src/tlw/analysis/cli.py:42` | `--runs-dir` `default="runs"` | see BLOCKER-1 |
| `src/tlw/runner.py:76` | `RUNS_ROOT = PROJECT_ROOT / "runs"` | unchanged (new runs still land at `runs/<run_id>/`) — see MAJOR-3 |

**Docstring/usage-string literals (cosmetic but §0.3-relevant — a user copies these):**
`scripts/build_calibration.py:11`, `finish_when_groq_ready.py:10`, `rejudge.py:15`,
`reliability_analysis.py:3,12`, `selective_rag_sim.py:15`, `wixqa_analyze.py:7`,
`wixqa_grounding_compare.py:16,17`, `wixqa_judge.py:16,17`, `wixqa_repair_empty.py:13`,
`wixqa_run3seed_retriever.py:62,161`, `wixqa_selfrefine.py:163`.

### V1.3 `data/rag/` and `data/wixqa/` literals — proposal undercounts both

| file:line | literal | phase |
|---|---|---|
| `scripts/wixqa_build_index.py:10` (docstring), `:22` | `data/rag/wixqa_kb` | 4.3 |
| `scripts/wixqa_rag.py:27` | `ROOT / "data/rag/wixqa_kb"` | 4.3 |
| `scripts/wixqa_run3seed.py:41` | `ROOT / "data/rag/wixqa_kb"` | 4.3 |
| `scripts/wixqa_grounding_ladder.py:25` (docstring), `:39` | `data/rag/retriever_ladder` | 4.1/4.3 |
| `scripts/wixqa_retriever_ladder.py:37` | `data/rag/retriever_ladder` | 4.1/4.3 |
| `scripts/selective_rag_sim.py:16` (docstring), `:84` | `data/rag/diabetes_train` | 4.3 |
| `scripts/finish_when_groq_ready.py:68` | `"data/rag/diabetes_train"` | 4.3 |
| `tools/rag/builder.py:17` (docstring), `tools/rag/cli.py:8` | `data/rag/<name>` | 4.3 |
| `experiments/trackB_p3_3bRAG_diabetes.yml:8,30` | `corpus_path: data/rag/diabetes_train` | 4.3 |
| `experiments/trackB_p3_3bRAGaspect_diabetes.yml:18` | `corpus_path: data/rag/diabetes_train` | 4.3 |
| `experiments/trackB_p3_3bRAGbig_diabetes.yml:18` | `corpus_path: data/rag/all_medquad` | 4.3 |
| `experiments/trackB_p3_7bRAG_diabetes.yml:7,22` | `corpus_path: data/rag/diabetes_train` | 4.3 |
| **`tests/tlw/config/test_validation.py:184`** | `cfg["memory"]["corpus_path"] = "data/rag/diabetes_train"` | **MISSED — see MINOR-1** |
| `.gitignore` (`data/rag/` block) | ignore rule | 3.8/4.3 |
| `scripts/wixqa_baseline.py:23`, `wixqa_build_index.py:21`, `wixqa_rag.py:26`, `wixqa_retriever_ladder.py:35,36`, `wixqa_run3seed.py:40` | `data/wixqa/…` (6 literals — proposal count correct) | 4.4 |

### V1.4 `discover_runs` — the single highest-risk claim. **VERIFIED BY EXECUTION, not by reading.**

**What the code does** (`src/tlw/analysis/loaders.py:136-151`, read in full):
```python
for child in sorted(runs_dir.glob(pattern)):      # pattern defaults to "*"  -> EXACTLY ONE LEVEL
    if not child.is_dir():        continue
    if not (child / "summary.jsonl").is_file():   continue
    records.append(load_run(child))
```
So a directory is a "run" iff it is a **direct child** of `--runs-dir` **and** contains
`summary.jsonl`. `group_runs` (`:154-163`) keys off `RunRecord.arm`, which reads
`summary["arm"]` or `config_used["params"]["arm"]` (`:44-45`) — never the path.

**Executed test** (synthetic post-move tree in a temp dir, `tlw` python, §0.5 — no repo files
touched). Result:

| scan | result |
|---|---|
| `discover_runs(runs/)` — the **new top level** | **0 runs** |
| `discover_runs(runs/teaching-loop-medquad)` | **12 runs**, arms A/B/C/D × seeds 13/42/123 all resolved from `summary.jsonl` |
| pilots at `runs/teaching-loop-medquad/pilots/…` | **correctly excluded** (`pilots` is a dir with no `summary.jsonl`) |
| `discover_runs(runs/rag-medquad-reliability)` | 1 run — the nested `hard-questions-only/…` runs are **invisible** |

**Verdicts:**
- ✅ The proposal's core claim is **TRUE**: renaming run directories and grouping them one level
  deeper is invisible to `src/tlw/analysis`, *provided the conditions stay direct siblings inside
  one study directory* — which §C.4 does for every study except Study 4.
- ✅ The `pilots/` subdirectory really does make T2.7's manual "filter pilots out" precaution
  **structural** — proven, not asserted.
- ❌ **BLOCKER-1 (below):** `--runs-dir` defaults to `"runs"` (`src/tlw/analysis/cli.py:42`).
  After the move that scan finds nothing. The failure is *loud* (`cli.py:210-212` prints
  `No runs found under 'runs'` and returns exit 1) — but the default and every doc command that
  says `--runs-dir runs` stops working.
- ⚠️ **MAJOR-4 (below):** nesting `hard-questions-only/` one level deeper inside Study 4 means a
  reader pointing at `runs/rag-medquad-reliability` silently sees 16 of 26 runs.

### V1.5 Run discovery that is **name-shaped, not directory-shaped** — the proposal missed all of it

`src/tlw/analysis` is safe. **Four standalone scripts are not.** They glob the *config stem* of the
run directory, which §C.4 renames. Every one of these was read live:

| file:line | pattern (hardcoded run-dir stem) | what happens after phase 3 |
|---|---|---|
| `scripts/reliability_analysis.py:60` | `f"{runs_dir}/trackB_p3_3b_diabetes__seed*/rounds.jsonl"` | matches nothing → `questions: 0` printed, **empty report, exit 0** |
| `scripts/reliability_analysis.py:61` | `f"{runs_dir}/trackB_p3_3bRAG*/rounds.jsonl"` | same |
| `scripts/selective_rag_sim.py:92` | `f"{rd}/trackA_full_armA_diabetes__seed*/rounds.jsonl"` | no pairs → prints `no matching (question,seed) pairs found`, exit 1 (loud) |
| `scripts/selective_rag_sim.py:93` | `f"{rd}/trackB_p3_3bRAG*/rounds.jsonl"` | same |
| `scripts/rejudge.py:92` | `--pattern` default `"trackB_p3_7b*"` | 0 runs matched, loops zero times, **exit 0 silently** |
| `scripts/finish_when_groq_ready.py:64-65` | passes `--pattern trackB_p3_7b*` | same |
| `scripts/build_calibration.py:50` | `glob.glob("runs_reliability/*/rounds.jsonl")` — **CWD-relative, not `ROOT`-relative** | matches nothing |
| `scripts/selective_rag_sim.py:74` | `Path(".").glob(pat)` — **CWD-relative** | ditto |

`scripts/rag_faithfulness.py:36-46` is the one that is safe: it globs `runs_dir.glob("*")` and
filters on `summary["memory_type"] == "rag"` — directory-shaped, like `discover_runs`.

`scripts/reliability_analysis.py` is the dangerous one: **its failure mode is a clean-looking empty
report, not an error.** That is a §0.1 hazard, and it is the script behind
`docs/RAG_RELIABILITY_ANALYSIS.md`.

### V1.6 Hardcoded per-file maps in the WixQA analysers

| file:line | map | after the phase-3 file renames |
|---|---|---|
| `scripts/wixqa_analyze.py:32-35` | `FILES = {"baseline": {13:"baseline__seed13.jsonl", 42:"baseline_norag.jsonl", 123:"baseline__seed123.jsonl"}, "rag": {…"rag_top3.jsonl"…}}` | all 6 names dead → `main()` prints `MISSING run files` and returns 1 (loud). Replace with `f"{step}/seed{s}.jsonl"` as §C.4 says. |
| `scripts/wixqa_dose_analyze.py:31-39` | `VARIANTS` — **4 variants × 3 seeds = 12 filenames + 3 `hit_log` names** (`retrieval_log.jsonl`, `retrieval_log_minilm_chunk.jsonl`, `retrieval_log_bge_chunk.jsonl`) | **the proposal never mentions this map at all.** Failure mode is *silent*: `load_variant` (`:48-55`) does `if not p.is_file(): continue`, so a renamed file becomes a **missing seed, not an error** — the dose-response table would render with fewer replicates and different numbers. **This is the worst silent-failure risk in the whole migration.** |

Note also that §C.4's before→after table has **no destination for
`retrieval_log_minilm_chunk.jsonl`** — the `minilm_chunk` variant is a real dose point in
`wixqa_dose_analyze.py:36-37` and in `runs_wixqa/rag_minilm_chunk__seed*.jsonl`, but the proposal's
ladder only numbers 5 steps and maps `minilm_whole` and `bge_chunk`. See MAJOR-5.

---

## V4 — Are the approved deletions safe?

### V4.1 `runs_orca/` duplicate — **PROVEN which one is the false start. Delete is SAFE.**

```
ls -la runs_orca/*/
```
| dir | `rounds.jsonl` | `summary.jsonl` | verdict |
|---|---|---|---|
| `trackA_p2_armA_diabetes_orca__seed42__20260723T155406Z/` | **0 bytes** | **absent** | **the false start — delete** |
| `trackA_p2_armA_diabetes_orca__seed42__20260723T155536Z/` | 177,771 bytes | present | the reported run |

Read from the surviving summary: `num_questions=125`, `pass_rate=0.84`, `passed_count=105`,
`seed=42`, `judge_fallback.count=0`. That is **exactly ADR-029's "orca-student 0.840"**
(`.claude/rules/decisions.md:39`) and `todo.md:148`. No number depends on the empty dir; and
`discover_runs` already skips it (no `summary.jsonl`), so nothing changes numerically either way.
**Approved deletion confirmed safe, with evidence.**

### V4.2 `runs_hardtail/` — **BLOCKER. DO NOT DELETE.**

ADR-034 decision (5) approves deleting `runs_hardtail/` on the stated ground of "zero SSOT
references". The *directory name* has zero references — I re-ran that grep and confirm it
(`grep -rn hardtail` outside the directory hits only `decisions.md:11`,
`STRUCTURE_PROPOSAL.md`, and this file). **But the numbers it produced are published.**

`docs/RAG_RELIABILITY_ANALYSIS.md:14-17`:
```
| Set                 | metric           | baseline | 3B+RAG |   Δ    |
| 35 broad hard-tail  | per-attempt pass |  0.606   | 0.640  | +0.034 |
|                     | pass@5 (>=1 of 5)|  0.89    | 0.74   | -0.15  |
```

Recomputed live from `runs_hardtail/` with the §0.5 python (paired join on `question_id`,
5 seeds × 2 arms × 35 questions):
```
questions: 35
per-attempt  base=0.606 rag=0.640  delta=+0.034      <- exact match, all three
pass@5       base=0.89  rag=0.74                     <- exact match
```
The 10 directories are `n=35`, `arm A`, `max_rounds 1`, `memory none|rag`, seeds 1–5
(`runs_hardtail/*/config_used.json`, read). **`runs_hardtail/` is the sole surviving source of a
published table in a tracked, linked document** (`docs/RAG_LAW.md:343` and
`docs/PRODUCT_RESULTS.md:79` both link to `RAG_RELIABILITY_ANALYSIS.md`).

Deleting it makes that table unverifiable → a §0.1/§0.4 regression on a live doc, and it
contradicts the proposal's own rule (`STRUCTURE_PROPOSAL.md:569`, `:1090`): *"Deleting any run
data — Irreplaceable §0.4 evidence. Consolidate, never delete."* The proposal's own §C.4 Study 4
**moves** `runs_hardtail/` into `runs/rag-medquad-reliability/hard-questions-only/`; only ADR-034
decision (5) says delete. **The two approved documents disagree, and the proposal is right.**

→ **§0.6: this needs the user's approval to change. I am flagging, not editing ADR-034.**
Recommendation: apply §C.4 Study 4 (move, don't delete). Cost: 1.2 MB, gitignored anyway.

### V4.3 Pre-verification of the phase-3 rename — **the published numbers survive. PROVEN.**

I built the post-move Track-A tree in a temp dir (12 `trackA_full_*` runs renamed to the §C.4
English labels, 14 `trackA_p2_*` pilots moved into `pilots/`) and ran the real CLI against it:

```
python -m src.tlw.analysis --runs-dir <tmp>/teaching-loop-medquad --comparison C-B --comparison B-A
```
| | today, `--runs-dir runs` (mixed) | post-move, `--runs-dir runs/teaching-loop-medquad` | published (ADR-024) |
|---|---|---|---|
| arm A / B / C / D | 0.836 / 0.913 / 0.915 / 0.934 | **0.821 / 0.912 / 0.915 / 0.940** | 0.821 / 0.912 / 0.915 / 0.940 ✅ |
| C − B | +0.001 [−0.022,+0.025] p=1.00 | **+0.003 [−0.021,+0.029] p=1.0000** | +0.003 [−0.021,+0.029] p=1.00 ✅ |
| B − A | — | **+0.091 [+0.051,+0.133] p<0.0001** | +0.091 [+0.051,+0.133] ✅ |
| honesty banner | **FIRES** ("6 runs have num_questions < 125") | **silent** | — |

Two things this proves:
1. The rename + `pilots/` nesting is **behaviour-preserving for the headline** and actually
   *repairs* a live §0.1 hazard: today the default `--runs-dir runs` silently pools 14 pilot runs
   and returns **+0.001, not the published +0.003**. The move makes T2.7's manual precaution
   structural, exactly as claimed.
2. Therefore **the move is worth doing** — this is the strongest argument in the proposal, and it
   is now verified by execution rather than by reading.

---

## V1.7 `.gitignore` — the proposed block is **right in design and broken as written**

Tested with real `git check-ignore -v` + `git add -A -n` in throwaway repos (git 2.51.0.windows.1)
against a synthetic `runs/<study>/<condition>/{summary.jsonl,config_used.json,manifest.json,
rounds.jsonl}` + `runs/<study>/README.md` tree.

| variant | result (`git add -A -n`) |
|---|---|
| **A — `runs/**` + `!runs/**/` + the 4 file negations** | ✅ `summary.jsonl`, `config_used.json`, `manifest.json`, `README.md` addable; `rounds.jsonl` and `seed*.jsonl` ignored |
| B — same, but **without** `!runs/**/` | ❌ **nothing addable** — every negation dead |
| C — `runs/` (a directory pattern) + negations | ❌ **nothing addable** — the classic "parent directory excluded" trap |
| D — `runs/**` + `!runs/*/` (one level of dirs) | ❌ **nothing addable** — 2nd-level condition dirs stay excluded |

**So the design is correct and `!runs/**/` is load-bearing.** The proposal earns credit for
avoiding trap C.

**BLOCKER-2 — the literal block at `STRUCTURE_PROPOSAL.md:836-847` does not work.** It writes the
comments *on the same line as the pattern*:
```gitignore
!runs/**/                      # let git descend into study/run directories
!runs/**/summary.jsonl         # the §0.4 evidence (~2 KB per run)
```
`.gitignore` has **no trailing-comment syntax** — `#` only starts a comment at column 0. Copied
verbatim, git parses `!runs/**/summary.jsonl         # the §0.4 evidence (~2 KB per run)` as one
literal pattern that matches nothing. Verified:
```
$ git add -A -n            ->  (nothing)
$ git check-ignore -v runs/study/cond/summary.jsonl
.gitignore:2:runs/**    runs/study/cond/summary.jsonl
```
Consequence if pasted as written: **zero** evidence files become committable, and
`README.md:90` ("Every number below is computed from a **committed** run log") stays false —
silently. That is the exact §0.1 defect this phase exists to fix.

**The literal text that actually works** (comments on their own lines; replaces `.gitignore:236`
`runs/` and `.gitignore:241` `data/rag/` — both line numbers verified by `grep -n`):

```gitignore
# Experiment artifacts: raw generations ignored, small evidence files tracked.
# NOTE: the `!runs/**/` line is load-bearing -- without it git never descends
# into runs/<study>/<condition>/ and every negation below is dead.
# NOTE: gitignore has no trailing-comment syntax -- keep comments on their own lines.
runs/**
!runs/**/
!runs/**/summary.jsonl
!runs/**/config_used.json
!runs/**/manifest.json
!runs/**/README.md

# Rebuildable search indexes (was: data/rag/) -- python -m tools.rag.cli
indexes/

# Third-party datasets -- see scripts/dataset/fetch_wixqa.py
data/external/
```
`reports/` stays absent from `.gitignore` (everything in it is meant to be committed) — verified:
`reports/rag-wixqa/scores.csv` is addable under the block above.

**Current state for reference** (`git check-ignore -q`, run live): `runs`, `data/rag`, `models`
are IGNORED; `runs_wixqa`, `runs_rag`, `runs_hardtail`, `runs_orca`, `runs_reliability`,
`runs_lora`, `runs_rag_big`, `runs_rag_aspect`, `data/wixqa` are **NOT** ignored — the proposal's
finding 3 is accurate.

---

## V1.8 `runs_wixqa/` inventory vs the proposal's mapping

`ls runs_wixqa/` → **20 entries**: 16 `.jsonl` + 4 `_s*.txt`. Mapping check against §C.4 Study 7:

- All 16 `.jsonl` have exactly one destination; all 4 `.txt` go to `reports/rag-wixqa/`. **No
  collisions.** ✅
- ❌ The proposal's arithmetic at `:772-774` ("5 ladder steps × 3 seeds plus 2 pilots = 17
  destination paths for 17 source files") is wrong: the true count is **16**, because
  **step 5 has no full-run files at all** — only the pilot. The tree at `:711-722` advertises
  `5-rag-plus-self-refine/` as a populated ladder step; after the move it would be an **empty
  directory**, which violates the proposal's own naming rule (a name that promises data that
  isn't there). → MINOR-3.
- `runs_wixqa/rag_minilm_chunk__seed*.jsonl` and `retrieval_log_minilm_chunk.jsonl`
  **do not exist** — confirmed by `ls`. `scripts/wixqa_dose_analyze.py:36-37` declares a
  `minilm_chunk` variant for them; running it live prints
  `[skip] minilm_chunk: no judged run files yet` and renders a 3-row table. This is a *pre-existing*
  condition, not a migration regression — but it is a live demonstration that this analyser
  degrades rather than fails.

---

## V2 — Import integrity

### V2.1 The `scripts/` import graph (script→script). **15 edges, proposal count correct.**

```
grep -rn "from scripts\." --include=*.py .
```
| importer:line | imports from | symbols |
|---|---|---|
| `wixqa_grounding_ladder.py:36` | `wixqa_retriever_ladder` | `chunks_of, encode, load_data` |
| `wixqa_judge.py:28` | `wixqa_baseline` | `JUDGE_SYS` |
| `wixqa_rag.py:24` | `wixqa_baseline` | `JUDGE_SYS, judge_score` |
| `wixqa_repair_empty.py:26` | `wixqa_retriever_ladder` | `load_data, encode` |
| `wixqa_repair_empty.py:27` | `wixqa_grounding_ladder` | `window, best_chunk_word_offset` |
| `wixqa_repair_empty.py:28` | `wixqa_run3seed` | `RAG_SYS, TEMPERATURE, MAX_TOKENS` |
| `wixqa_repair_empty.py:29` | `wixqa_run3seed_retriever` | `GROUNDINGS` |
| `wixqa_run3seed_retriever.py:32` | `wixqa_retriever_ladder` | `load_data, build_ranked, encode` |
| `wixqa_run3seed_retriever.py:33` | `wixqa_grounding_ladder` | `window, best_chunk_word_offset` |
| `wixqa_run3seed_retriever.py:34` | `wixqa_run3seed` | `RAG_SYS, MAX_PASSAGE_CHARS, TEMPERATURE, MAX_TOKENS, retrieval_record` |
| `wixqa_run3seed_retriever.py:117` | `wixqa_retriever_ladder` | **runtime** `import … as ladder` → `ladder._MODELS.clear()` (frees VRAM before Ollama) |
| `wixqa_selfrefine.py:42` | `wixqa_retriever_ladder` | `load_data, encode` |
| `wixqa_selfrefine.py:43` | `wixqa_grounding_ladder` | `window, best_chunk_word_offset` |
| `wixqa_selfrefine.py:44` | `wixqa_run3seed_retriever` | `GROUNDINGS` |
| `wixqa_selfrefine.py:45` | `wixqa_run3seed` | `RAG_SYS, TEMPERATURE, MAX_TOKENS` |

**Verdict for phases 1–5: every one of these 15 survives untouched, because no script moves.**
Phase 6 (the only phase that would move them) is out of scope per ADR-034 (6). The `:117` runtime
import is the one a naive "update the imports" pass would miss — it is not at the top of the file
and it reaches into a private `_MODELS` cache.

`scripts/` → `src/` and `scripts/` → `tools/` imports: all are absolute (`from src.tlw…`,
`from src.providers…`, `from tools.rag…`) and resolve off the repo root, which every script puts on
`sys.path` itself. **Unaffected by phases 1–5.**

### V2.2 Adding `scripts/__init__.py` (phase 1.2)

`scripts/` today has **no** `__init__.py`; the 15 imports work through PEP-420 namespace packaging
plus the per-script `sys.path.insert(0, ROOT)`. Adding an empty `__init__.py` converts it to a
regular package — a strict narrowing of an already-working resolution, with the repo root already
first on `sys.path` in every one of these entrypoints. **Safe.** Sibling precedent in-repo:
`tools/__init__.py`, `tools/rag/__init__.py`, `tools/dataset/__init__.py` all exist and are
imported exactly this way (`tests/rag/test_builder.py:11`).

No name collisions: no module under `scripts/` shadows a stdlib or third-party top-level module
(checked the 31 filenames).

### V2.3 All 28 `sys.path.insert` sites, individually

| site | value inserted | depth correct? | interacts with `pytest.ini`? |
|---|---|---|---|
| `run.py:25` | `Path(__file__).resolve().parent` = repo root | ✅ | no |
| `scripts/{assess_all:17, compare_judges:26, compare_students:24, rag_faithfulness:28, rejudge:28, selective_rag_sim:27}` | `parents[1]` = repo root | ✅ | no |
| `scripts/{build_calibration:27, eval_lora:20, finish_when_groq_ready:22}` | `str(ROOT)` where `ROOT = parents[1]` | ✅ | no |
| the **13** wixqa scripts (`:17–:37`) | `str(ROOT)` where `ROOT` = **the hardcoded absolute literal** | ❌ **only on this machine** | no |
| `tools/dataset/{app:22, assessor:24, cli:18}` | `parents[2]` = repo root | ✅ | no |
| `tests/conftest.py:8` | `parents[1]` = repo root | ✅ | **YES — this is the one `pytest.ini` replaces** |

After phase 2 all 13 wixqa scripts use `parents[1]`, which is **the same value** they compute
today on this machine — behaviour-preserving by construction, and correct everywhere else.
**Do not do phase 2 and phase 6 in either order without re-deriving the depth**: `parents[1]` is
right for `scripts/x.py`, `parents[2]` for `scripts/wixqa/x.py`.

---

## V3 — Test collection under the proposed `pytest.ini`

### V3.1 Baseline, measured

```
python -m pytest tests/ -q --collect-only   ->  270 tests collected
python -m pytest --version                  ->  pytest 8.4.2     (pythonpath ini needs >= 7.0 ✅)
plugins: anyio-4.11.0 ONLY                  ->  pytest-randomly is NOT installed
rootdir (today, no ini file)                ->  <repo root>
```

### V3.2 Does `pytest.ini` + deleting `tests/conftest.py` still collect and pass 270?

Two experiments, both run with the §0.5 python:

**(a) Full suite with the ini options applied via `-o` (proves the options are compatible):**
```
python -m pytest -q -o pythonpath=. -o testpaths=tests
->  270 passed in 64.30s
```
**(b) Isolated probe proving `pythonpath = .` really replaces the conftest hack** (throwaway repo,
`pkg/` + `tests/test_x.py` importing it, **no `conftest.py` at all**, invoked from `C:/Windows` so
CWD cannot help):
```
with  pytest.ini [pytest] testpaths=tests / pythonpath=. / addopts=-q   ->  1 passed, rc=0
without pytest.ini (control)                                            ->  ModuleNotFoundError: No module named 'pkg', rc=2
```
✅ **`pythonpath = .` is resolved relative to rootdir and fully substitutes for
`tests/conftest.py:6-8`.** Deleting that file in the same commit as adding `pytest.ini` is safe.
Nothing imports `tests.conftest`; it contains only the path insert.

### V3.3 rootdir resolution

Today rootdir already resolves to the repo root (printed above) — but *by fallback*, because no
`pytest.ini`/`pyproject.toml`/`setup.cfg`/`tox.ini` exists (`ls` confirms). Adding `pytest.ini` at
the root **pins** it deterministically to the same value. No change in behaviour, one less
ambiguity. `testpaths = tests` only affects bare `pytest` with no args; explicit paths still win.
Running from a different CWD already works today (`pytest <abs>/tests` from `C:/` → 270 passed).

### V3.4 The four `conftest.py` files, and collection order

| file | job | affected by the migration? |
|---|---|---|
| `tests/conftest.py` | `sys.path.insert` only (lines 6-8) | **deleted in phase 1.3**, replaced by `pytest.ini` |
| `tests/tlw/conftest.py` | imports `src.tlw.{evaluation,memory,prompts,loop}` so **registry registration is not collection-order dependent**; the comment (`:3-4`) records the pytest-randomly bug that motivated it | **untouched — must stay** |
| `tests/tlw/analysis/conftest.py` | 163-line synthetic run-dir factory | untouched |
| `tests/tlw/loop/conftest.py` | network-free mocks | untouched |

**Collection order does not change.** `pytest-randomly` is **not installed** in this env
(`--version --version` lists only `anyio`), so ordering is pytest's deterministic
file-system order both before and after. `addopts = -q` changes verbosity only.
`tests/tlw/conftest.py`'s defence is still required — it protects against the plugin being
installed later, and against `-p randomly` — so **do not "simplify" it away**.

### V3.5 The phase-5 `__init__.py` additions — one real hazard the proposal does not mention

Current state (`find tests -type d`): `__init__.py` exists in
`tests/tlw/{analysis,evaluation,loop,prompts}` and is absent in
`tests/`, `tests/rag/`, `tests/tlw/`, `tests/tlw/{config,memory,runner}` — the proposal's count
(4 of 10) is correct.

Adding the missing ones **changes every test module's importable name** (pytest `prepend` import
mode derives the module name from the first ancestor *without* `__init__.py`). E.g.
`tests/tlw/analysis/test_loaders.py` is imported today as `analysis.test_loaders`; with
`tests/__init__.py` + `tests/tlw/__init__.py` present it becomes `tests.tlw.analysis.test_loaders`.

That transition is a classic source of
`import file mismatch … unique basename … remove __pycache__` errors from **stale bytecode**.
→ **the step must delete `tests/**/__pycache__` in the same commit.** There are 10 such
directories today. Mitigation command is in §P5 step 5.1.

Reassurance: `find tests -name "test_*.py" -printf "%f\n" | sort | uniq -d` returns **nothing** —
there are no duplicate test basenames today, so the stated motivation ("so a duplicate basename can
never shadow") is preventive, not a live bug. The change is still worth making; it is just not
urgent, and it is the only test-side change that can break collection.

---

## V5 — Evidence integrity (§0.1): every reproduce command, before → after

All commands below were read out of the five result docs (`grep -n`) and, where offline, **run**.

### `docs/RAG_LAW.md` §7 "How to verify any number here" (`:315-334`)

| line | command today | status **today** | required post-move form |
|---|---|---|---|
| `:320` | `python -m src.tlw.analysis --runs-dir runs` | ⚠️ **ALREADY BROKEN** — see below | `python -m src.tlw.analysis --runs-dir runs/teaching-loop-medquad --comparison C-B --comparison B-A` |
| `:323` | `python -m src.tlw.analysis --runs-dir runs_rag --rag` | ✅ runs, gives the published 4-arm table | `--runs-dir runs/rag-medquad --rag` |
| `:326` | `python scripts/wixqa_analyze.py` | ✅ (`+0.152 [+0.090,+0.213]`, hit-rate 0.550) | unchanged path, but the `FILES` map at `wixqa_analyze.py:32-35` **must** be rewritten |
| `:327` | `python scripts/wixqa_dose_analyze.py` | ✅ (`0.163 / 0.315 / 0.340`, `+0.025 [−0.030,+0.078] p=0.273`) | unchanged path, but `VARIANTS` at `wixqa_dose_analyze.py:31-39` **must** be rewritten |
| `:328-330` | `wixqa_grounding_compare.py --control 'runs_wixqa/rag_bge_chunk__seed*.jsonl' --treat 'runs_wixqa/rag_bge_chunk_chunk2400__seed*.jsonl'` | ✅ | `--control 'runs/rag-wixqa/3-rag-better-retriever/seed*.jsonl' --treat 'runs/rag-wixqa/4-rag-wider-context/seed*.jsonl'` |
| `:334` | `python -m pytest tests/ -q` (270 tests) | ✅ 270 passed | unchanged (count must stay 270) |

**`RAG_LAW.md:320` is a pre-existing §0.1 defect, independent of this migration.** Run live today:
```
python -m src.tlw.analysis --runs-dir runs --comparison C-B
  arm A: 0.836 … C-B: +0.001 [-0.022,+0.025]
  *** NOT the pre-registered sample … 6 run(s) have num_questions < 125 (smallest: 2) ***
```
The portfolio artifact's own verification command returns **+0.001**, not the published **+0.003**,
because `runs/` pools 14 pilot runs. The honesty banner fires, so it is not dishonest — but the
command does not reproduce the number it claims to. **The migration FIXES this** (V4.3 proves
`--runs-dir runs/teaching-loop-medquad` → exactly `+0.003 [−0.021,+0.029] p=1.0000`, banner
silent). This should be called out in the migration commit as a §0.1 repair, not buried.

### `docs/TRACK_A_RESULTS.md`
| line | today | post-move |
|---|---|---|
| `:152` | `run.py --config experiments/trackA_full_arm<ARM>_diabetes.yml` | `--config experiments/teaching-loop/<1-baseline\|2-self-refine\|3-teacher-feedback\|4-teacher-sees-answer>.yml` **plus** a `--runs-dir runs/teaching-loop-medquad` (see MAJOR-3) |
| `:156` | `python -m src.tlw.analysis --runs-dir runs --comparison C-B   # (filter to trackA_full_* / heldout)` | `--runs-dir runs/teaching-loop-medquad --comparison C-B` — **and the parenthetical warning can be deleted**, because the filter becomes structural |
| `:159` | prose: "computed directly from `runs/trackA_full_arm{A,B,C,D}_diabetes__seed{13,42,123}__*/`" | `runs/teaching-loop-medquad/{1-baseline,2-self-refine,3-teacher-feedback,4-teacher-sees-answer}__seed{13,42,123}__*/` |

### `docs/RAG_RESULTS.md`
| line | today | post-move |
|---|---|---|
| `:193-196` | `python -m tools.rag.cli … --out data/rag/diabetes_train` | `--out indexes/medquad-diabetes-train` |
| `:199-201` | `run.py --config experiments/trackB_p3_3bRAG_diabetes.yml … --runs-dir runs_rag` | `--config experiments/rag-medquad/small-model-with-rag.yml … --runs-dir runs/rag-medquad` |
| `:203` | `python -m src.tlw.analysis --runs-dir runs_rag --rag` | `--runs-dir runs/rag-medquad --rag` |
| `:205` | `scripts/rag_faithfulness.py --runs-dir runs_rag …` | `--runs-dir runs/rag-medquad` |
| `:208-209` | prose naming `runs_rag/trackB_p3_3bRAG_*` **and the reused `runs_rag/trackA_full_armA_*` baseline** | rename both; **and see MAJOR-1 — the reused baseline must NOT be deleted** |

### `docs/WIXQA_RESULTS.md`
| line | today | post-move |
|---|---|---|
| `:35`, `:103-105` | `runs_wixqa/retrieval_log.jsonl`, `runs_wixqa/{baseline,rag}__seed{13,123}.jsonl`, `{baseline_norag,rag_top3}.jsonl` | `runs/rag-wixqa/2-rag-basic/retrieval-log.jsonl`, `runs/rag-wixqa/{1-no-rag,2-rag-basic}/seed*.jsonl` |
| `:73` | `data/rag/wixqa_kb/` | `indexes/wixqa-help-centre/` |
| `:93-100` | `wixqa_run3seed.py --arm …`, `wixqa_judge.py --glob 'runs_wixqa/*__seed*.jsonl'`, `wixqa_analyze.py` | `--glob 'runs/rag-wixqa/*/seed*.jsonl'` |
| `:136` | `data/rag/retriever_ladder/hitrate_table.json` | `reports/rag-wixqa/retriever-comparison.json` |
| `:338-342` | grounding-ladder + 3-seed + judge + compare block (5 commands) | all four `runs_wixqa/…` globs rewritten as above |

### `docs/PRODUCT_RESULTS.md`
| line | today | post-move |
|---|---|---|
| `:107-109` | `scripts/{build_lora_data,train_lora,eval_lora}.py` | **unchanged in phases 1–5** (script renames are §C.9 = phase 6, out of scope) |
| `:111` | "Numbers from `runs_lora/lora_eval_result.json`" | `reports/lora-medquad/fine-tuned-vs-original.json` (phase 4.1) — **and `scripts/eval_lora.py:107` must be repointed in the same commit** |

### `docs/RAG_RELIABILITY_ANALYSIS.md`
| line | today | post-move |
|---|---|---|
| `:3-4`, `:126` | "`runs_reliability/` … **is running**" (stale — 16 completed dirs on disk) | `runs/rag-medquad-reliability/` + a truthful status (proposal finding 12) |
| `:16-17` | the **35 broad hard-tail** table row | **sourced exclusively from `runs_hardtail/` — see BLOCKER-1** |
| — | no reproduce command is given at all | add `python scripts/reliability_analysis.py --runs-dir runs/rag-medquad-reliability …` — but see MAJOR-2: its internal globs must be fixed first |

### `README.md`
`:90` "Every number below is computed from a **committed** run log" — false today (`git ls-files`
shows nothing under any `runs*`). Made true **only if** the `.gitignore` block is written in the
working form from V1.7 (BLOCKER-2). `:426, :429, :432, :483, :674` still show
`simplified_experiment_runner.py`, deleted in T2.9 — known, deferred to phase 5.3.

### Guard / permissions
`.claude/hooks/guard.py:19-23` protects only `data/Medical_Q&A/`, `data/medical_by_source/`,
`logs/experiments/`; `.claude/settings.json:25-27` denies edits to the same three. **No `runs*`,
`data/rag/`, `data/wixqa/` or `reports/` path is guard-protected** — the proposal's claim is
correct, verified by reading both files. ⚠️ Operational note for the executor: the guard matches on
the *command string*, so any `git mv`/`grep` whose text contains `logs/experiments` is blocked even
when read-only (this happened to me during this audit). Keep that literal out of migration commands.

---

## FINDINGS

### [BLOCKER] 1 — `runs_hardtail/` must NOT be deleted: it is the sole source of a published table

ADR-034 decision (5) approves deleting it on the ground of "zero SSOT references". The directory
*name* has none — but `docs/RAG_RELIABILITY_ANALYSIS.md:16-17` publishes numbers computed from it,
and I reproduced them exactly (V4.2): per-attempt `0.606 / 0.640 / +0.034`, pass@5 `0.89 / 0.74`.
That document is tracked and linked from `docs/RAG_LAW.md:343` and `docs/PRODUCT_RESULTS.md:79`.
Deleting it is a §0.1/§0.4 regression and contradicts the proposal's own standing rule
(`STRUCTURE_PROPOSAL.md:569,1090`: *"Deleting any run data — Irreplaceable §0.4 evidence.
Consolidate, never delete."*) and its own §C.4 Study 4, which **moves** it.
**§0.6: I cannot edit ADR-034. This needs the user's decision.** Recommendation: move, don't delete
(cost: 1.2 MB, gitignored).

### [BLOCKER] 2 — the `.gitignore` block as literally written produces zero tracked evidence

`STRUCTURE_PROPOSAL.md:836-847` puts `# …` comments **on the same lines as the patterns**.
`.gitignore` has no trailing-comment syntax. Verified with real git 2.51: pasted verbatim,
`git add -A -n` offers **nothing**, and `git check-ignore -v runs/study/cond/summary.jsonl` reports
`runs/**` as the winning pattern. The whole point of phase 3.8 — making `README.md:90` true —
silently fails. The corrected literal block is in V1.7; the design (`runs/**` + `!runs/**/` + file
negations) is **verified correct**, only the comment placement is wrong.

### [MAJOR] 1 — dropping the duplicated `runs_rag/trackA_full_armA_*` breaks the RAG headline

Proposal finding 4 says "keep one copy"; §C.4 Study 2 says "— or drop per finding 4". But
`discover_runs` is **one level deep and cannot see across studies** (V1.4, executed). Ran live:
`--runs-dir runs_rag --rag` produces `labels present: 3B, 3B+RAG, 7B, 7B+RAG` and the published
`3B+RAG − 3B = −0.005 [−0.067,+0.056] p=0.9088` — where the `3B` label **is** those three
duplicated directories. Delete them and `runs/rag-medquad` loses its baseline, so §D step 3.9's own
verification (`--runs-dir runs/rag-medquad --rag` → the 4-arm table) cannot pass.
**Keep the duplicate.** Record the deliberate reuse (ADR-027) in `runs/rag-medquad/README.md` and in
each `manifest.json`. Cost ~1 MB.

### [MAJOR] 2 — four scripts discover runs by hardcoded config-stem glob; the proposal lists none of them

See V1.5. `reliability_analysis.py:60,61`, `selective_rag_sim.py:92,93`, `rejudge.py:92`,
`finish_when_groq_ready.py:64-65` all glob `trackA_full_armA_diabetes__seed*` /
`trackB_p3_3b*` / `trackB_p3_7b*` directly. §C.4 renames every one of those stems. §D step 3.4 lists
only the `--runs-dir` **defaults** (`:53`, `:83`, `:91`), not the patterns.
`reliability_analysis.py` is the dangerous one: on no match it prints `questions: 0` and an empty
strata table and **exits 0** — a clean-looking wrong report. And it is the script behind
`RAG_RELIABILITY_ANALYSIS.md`.

### [MAJOR] 3 — the new layout has no writer: `runner.py` still writes to `runs/<run_id>/`

`src/tlw/runner.py:76`: `RUNS_ROOT = PROJECT_ROOT / "runs"`. Nothing in the proposal changes it.
After the migration, `run.py --config experiments/teaching-loop/1-baseline.yml` writes to
**`runs/1-baseline__seed42__<ts>/`** — at the top level, beside the study directories, and
invisible to `discover_runs(runs/teaching-loop-medquad)`. The only escape hatch is
`--runs-dir` (`runner.py:638`), whose own help text says **"tests only, not for real runs"**.
So the structure re-pollutes on the very next run — the exact failure ADR-034 exists to prevent.
Needs one of: (a) re-word `--runs-dir` help and require it in every documented run command
(cheapest, doc-only); (b) add an optional `study:` key to the config that the runner joins onto
`RUNS_ROOT`. **(a) is sufficient for phases 1–5; (b) is the real fix and should be its own task.**

### [MAJOR] 4 — `src/tlw/evaluation/calibration.py:46` writes to `runs/calibration/` and is not in any edit list

`OUTPUT_DIR = PROJECT_ROOT / "runs" / "calibration"`. Study 8 moves `runs/calibration/` →
`runs/judge-calibration/`, but re-running the probe would **recreate `runs/calibration/`**,
resurrecting the directory the migration just retired. Must be edited in the same step as the move.

### [MAJOR] 5 — nesting `hard-questions-only/` hides 10 runs from the study scan

§C.4 Study 4 puts `runs_hardtail/` one level deeper than its siblings. Executed test (V1.4):
`discover_runs(runs/rag-medquad-reliability)` returns only the top-level runs; the nested ones are
invisible. That is defensible (the `pilots/` pattern) but it is **undocumented**, and unlike
`pilots/` these runs back a *published* table. Either flatten them with a distinguishing label
(`hard-questions__no-rag__seed1__<ts>`) or state the exclusion explicitly in the study README.

### [MINOR] 1 — `tests/tlw/config/test_validation.py:184` hardcodes `data/rag/diabetes_train`

Phase 4.3's literal list omits it. It is a string in an assertion fixture, not a filesystem read,
so the suite would still pass — but it is exactly the kind of stale literal this migration exists
to kill. Update it with the others.

### [MINOR] 2 — the `experiments/` regrouping loses a file and miscounts the pilots

`ls experiments/` = 20 `.yml` + README. §B assigns: teaching-loop 4, rag-medquad 4,
rag-medquad-fair-tests 2, student-prompt 1, "**the 10** `trackA_p2_*` pilot configs". There are only
**8** `trackA_p2_*` left after `trackA_p2_armA_diabetes_orca.yml` goes to `student-prompt/` (9 total
minus 1), and **`experiments/trackB_p3_loragen_diabetes.yml` is assigned to no group at all**.
4+4+2+1+8 = 19; one config is orphaned. Also `experiments/{trackA_p2_armA_diabetes_orca,
trackB_p3_3bRAGaspect, trackB_p3_3bRAGbig, trackB_p3_loragen}.yml` carry `--runs-dir runs_*`
in their header comments (`:8`, `:10`, `:10`, `:21`) — four more literals for step 3.4.

### [MINOR] 3 — the proposed `runs/rag-wixqa/` tree advertises an empty ladder step

`STRUCTURE_PROPOSAL.md:711-722` shows `5-rag-plus-self-refine/` as a ladder step; `:772` claims
"17 destination paths for 17 source files". `ls runs_wixqa/` = 16 `.jsonl` + 4 `.txt`, and the
self-refine work only ever produced a **pilot** (the 3-seed run was stopped by the pre-registered
gate — `todo.md` T3.14). So step 5 would be an empty directory whose name promises data that does
not exist. Either omit it or name it so the absence is visible; `pilots/5-rag-plus-self-refine/` is
already correct and sufficient.

### [MINOR] 4 — `README.md:90` cannot become true for `runs/rag-wixqa/`

The tracked-file negations (`summary.jsonl`, `config_used.json`, `manifest.json`, `README.md`) are
the **framework** run shape. WixQA runs are *file-per-run* (`seed*.jsonl`,
`STRUCTURE_PROPOSAL.md:426-429`), so nothing under `runs/rag-wixqa/` except the new
`manifest.json`/`README.md` becomes tracked. The proposal's answer is `reports/<study>/scores.csv`
(§C.6, step 4.2) — that is the right answer, but it is a **new artifact that does not exist yet**
and the `--scores-csv` flag it needs is unwritten. Until 4.2 lands, no WixQA number is
clone-verifiable. Sequence 4.2 before claiming the README fix.

### [MINOR] 5 — `runs/` top level becomes an empty scan; the CLI default stops working

`src/tlw/analysis/cli.py:42` defaults `--runs-dir` to `"runs"`. Post-move that finds 0 runs
(V1.4, executed) and exits 1 with `No runs found under 'runs' (looked for */summary.jsonl)`
(`cli.py:210-212`). **Loud, not silent — acceptable**, but the default is now useless. Either
change the default to a required argument, or improve the message to list the study directories.

---

## NOT VERIFIED

1. **Anything requiring Ollama, Groq or the GPU.** No LLM call was made. The phase-4.3 RAG smoke
   run (`indexes/` repoint) is therefore unverified — I confirmed only that `corpus_path` is
   validated at config-load (`src/tlw/config/validation.py:217`), so a wrong path fails loud.
2. **`wixqa_grounding_compare.py` / `wixqa_judge.py` / `wixqa_repair_empty.py` end-to-end.** I read
   their globs; I ran only `wixqa_analyze.py` and `wixqa_dose_analyze.py` (both pure-offline).
3. **The 13 `ROOT` replacements themselves.** I verified the *depth* (`parents[1]`) is arithmetically
   correct for `scripts/*.py` and matches the 5 working siblings. I did not edit or run them.
4. **`tests/` after the phase-5 `__init__.py` additions.** V3.5 reasons about it and names the
   stale-`__pycache__` hazard; I did not create the files, so the 270-count is unproven for phase 5.
5. **Whether `data/*.jsonl` (finding 13) or `notebooks/experiment.ipynb` are still wanted.**
   Out of the scope I was given.
6. **`logs/experiments/**` internals.** Untouched by design and guard-protected.
7. **The `runs_reliability/` 16 dirs.** I did not recompute `RAG_RELIABILITY_ANALYSIS.md`'s
   confirmatory sweep; finding 12 (stale "is running") stands unverified either way.
8. **The 62 inbound `docs/*.md` links** the proposal cites as the reason not to move the reports.
   I accepted that count rather than re-deriving it; the reports are not being moved, so it is
   not load-bearing for execution.

---

## EVIDENCE LOG

**Read in full or in cited part:** `docs/plan/STRUCTURE_PROPOSAL.md` (all 1,098 lines),
`.claude/rules/decisions.md` ADR-034 + ADR-027/029/030/033 evidence lines,
`.claude/rules/{00-index,structure,todo,schema}.md`, `.claude/settings.json` (all 46 lines),
`.claude/hooks/guard.py:1-45`, `.gitignore:220-247`,
`src/tlw/analysis/loaders.py` (all 249 lines), `src/tlw/analysis/cli.py` (all 246 lines),
`tests/conftest.py`, `tests/tlw/conftest.py`, `scripts/wixqa_analyze.py:1-60`,
`scripts/wixqa_dose_analyze.py:25-60`, `scripts/reliability_analysis.py:1-90`,
`scripts/selective_rag_sim.py:60-110`, `scripts/rejudge.py:85-115`,
`scripts/rag_faithfulness.py:30-50`, `scripts/wixqa_run3seed_retriever.py:110-125`,
`docs/RAG_RELIABILITY_ANALYSIS.md:1-45`, `docs/RAG_LAW.md:308-345`,
`runs_hardtail/*/summary.jsonl` (10), `runs_hardtail/…seed1…/config_used.json`,
`runs_orca/*/` (both, with `ls -la`), `runs_orca/…155536Z/summary.jsonl`.

**Commands run** (all via `C:\Users\ham25\.conda\envs\tlw\python.exe`, §0.5; all read-only against
the repo — the only writes were to temp dirs and to this file):
```
grep -rn "^ROOT\s*=|ROOT\s*=\s*Path("  scripts/ tools/ src/ run.py tests/     # 13 hardcoded + 5 correct siblings
grep -rn "C:[\\/]Users[\\/]ham25" --include=*.py .                            # 13 + guard.py (legit)
grep -rn "runs_hardtail|runs_lora|runs_orca|runs_rag|runs_reliability|runs_wixqa|runs/" --include=*.py …
grep -rn "data/rag|data/wixqa|data/calibration" --include=*.py --include=*.yml …
grep -rn "sys.path.insert|sys.path.append" --include=*.py .                   # 28 sites
grep -rn "from scripts\." --include=*.py .                                    # 15 cross-imports
grep -rn "discover_runs|glob\.glob|\.glob\(" --include=*.py scripts/ src/ tools/
grep -rn "hardtail" … (outside runs_hardtail/)                                # 0 live references
find tests -type d + per-dir __init__.py check                                # 4 of 10
find tests -name "test_*.py" -printf "%f\n" | sort | uniq -d                  # no duplicates
git check-ignore -q <14 paths>                                                # runs/ data/rag/ models/ ignored; 8 runs_* + data/wixqa NOT
grep -n "^runs/|^data/rag/" .gitignore                                        # :236 and :241
python -m pytest tests/ -q --collect-only                                     # 270 tests collected
python -m pytest --version --version                                          # 8.4.2; plugins: anyio only (NO pytest-randomly)
python -m pytest -q -o pythonpath=. -o testpaths=tests                        # 270 passed
python -m pytest -q <abs>/tests   (from cwd C:\)                              # 270 passed
python -m src.tlw.analysis --runs-dir runs --comparison C-B                   # +0.001, banner FIRES (pilot pollution)
python -m src.tlw.analysis --runs-dir runs_rag --rag                          # 4 labels; -0.005 [-0.067,+0.056] p=0.9088
python scripts/wixqa_analyze.py                                               # +0.152 [+0.090,+0.213] p=5.156e-11
python scripts/wixqa_dose_analyze.py                                          # 0.163/0.315/0.340; +0.025 [-0.030,+0.078] p=0.273
```
**Simulations (temp dirs only, repo untouched):**
```
discover_runs() against a synthetic runs/<study>/<condition>/ + pilots/ tree   # 0 / 12 / pilots excluded / nested invisible
copy the 12 trackA_full_* into <tmp>/teaching-loop-medquad + 14 pilots into pilots/,
  then python -m src.tlw.analysis --runs-dir <tmp>/teaching-loop-medquad       # C-B +0.003 [-0.021,+0.029] p=1.0000 ; B-A +0.091 [+0.051,+0.133]
git init + 5 .gitignore variants + git add -A -n / git check-ignore -v         # only variant A works; verbatim block fails
pytest.ini(pythonpath=.) probe repo with NO conftest, run from C:/Windows      # 1 passed vs control ModuleNotFoundError
```
**Recomputation of a published table** (BLOCKER-1): paired join of
`runs_hardtail/trackB_p3_3b{,RAG}_diabetes__seed*/rounds.jsonl` on `question_id` →
`questions: 35; per-attempt base=0.606 rag=0.640 delta=+0.034; pass@5 base=0.89 rag=0.74`.

---

# EXECUTABLE CHECKLIST (V6)

**Ground rules for the executor**
- Every step below ends green: `pytest` passes, `python run.py --help` works, and the analysis CLI
  reproduces its published number. Run the named verification **after each step**, not per phase.
- All Python via `C:\Users\ham25\.conda\envs\tlw\python.exe` (§0.5).
- Never put the literal `logs/experiments` in a bash command string — the guard blocks it.
- One commit per step (not per phase) — that is what makes each step individually revertible.

**Universal smoke, referenced below as `SMOKE`:**
```
& "C:\Users\ham25\.conda\envs\tlw\python.exe" -m pytest tests/ -q          # expect: 270 passed
& "C:\Users\ham25\.conda\envs\tlw\python.exe" run.py --help                # expect: exit 0
```

---

## §P0 — Blocking decisions (no files change)

| # | Decision needed | Why |
|---|---|---|
| 0.1 | **Do not delete `runs_hardtail/`** — override ADR-034 (5) | BLOCKER-1. §0.6: only the user may change this. |
| 0.2 | **Keep the duplicated `runs_rag/trackA_full_armA_*`** | MAJOR-1 — otherwise step 3.9's own verification fails. |
| 0.3 | Choose the MAJOR-3 fix: (a) document `--runs-dir runs/<study>` in every run command + re-word `runner.py:638`'s help, or (b) add a `study:` config key | Without one, the layout re-pollutes on the next run. (a) is enough for phases 1–5. |
| 0.4 | Confirm `runs_orca/…155406Z/` may be deleted | **Already evidenced safe** (V4.1): empty `rounds.jsonl`, no `summary.jsonl`; the reported 0.840 is the other dir. |

## §P1 — Pure additions (risk: none)

| # | Action | Verification |
|---|---|---|
| 1.1 | Create `docs/README.md`, `reports/README.md`, `reports/figures/.gitkeep` | `ls reports docs/README.md` |
| 1.2 | Add empty `scripts/__init__.py` | `& …python.exe -c "import scripts.wixqa_analyze"` → no ImportError; then `SMOKE` |
| 1.3 | Add `pytest.ini` **and** delete `tests/conftest.py` **in the same commit** | `& …python.exe -m pytest tests/ -q` → **270 passed**; also `cd C:\ ; pytest <abs>/tests -q` → 270 passed |
| 1.4 | One-line `tlw` gloss in `src/tlw/__init__.py` (+ README, structure.md later in 5.2/5.3) | `SMOKE` |
| 1.5 | `git add` the untracked authored files (`tools/rag/`, 24 `scripts/*.py`, 7 `experiments/*.yml`, `docs/plan/*.md`, 5 `docs/*.md`, `src/tlw/{analysis/rag_report,evaluation/faithfulness,memory/rag_backend}.py`, `tests/rag/`, `data/processed/`) | `git status --porcelain` shows no `?? ` for authored code; `SMOKE` |

`pytest.ini` (exact content):
```ini
[pytest]
testpaths = tests
pythonpath = .
addopts = -q
```

## §P2 — Absolute paths (risk: very low). **Must precede every move.**

| # | Action | Verification |
|---|---|---|
| 2.1 | In each of the 13 files from V1.1, replace the hardcoded literal with `ROOT = Path(__file__).resolve().parents[1]`. Change **nothing else**. | after each file: `& …python.exe -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" scripts/<f>.py` |
| 2.2 | Prove the two pure-offline analysers still print the published numbers | `& …python.exe scripts/wixqa_analyze.py` → `+0.152 [+0.090, +0.213]`, McNemar `p=5.156e-11`, hit-rate `110/200 = 0.550`  ·  `& …python.exe scripts/wixqa_dose_analyze.py` → `0.163 / 0.315 / 0.340`, `+0.025 [-0.030, +0.078] p=0.273` |
| 2.3 | `SMOKE` | 270 passed |

> These are the exact values I captured **before** any change (V5) — they are the regression oracle
> for the whole migration.

## §P3 — Consolidate the run roots. **One study per step.**

Do them in this order; each is independently green.

| # | Action | Verification (run immediately) |
|---|---|---|
| 3.0 | Fix the four config-stem globs **first** so they survive the renames: `reliability_analysis.py:60,61`, `selective_rag_sim.py:92,93`, `rejudge.py:92`, `finish_when_groq_ready.py:64-65`. Make them label-driven (`no-rag__seed*`, `with-rag__seed*`, `large-model*`) *and* keep a back-compat fallback until the matching study has moved. | `& …python.exe scripts/reliability_analysis.py --runs-dir runs_reliability` → still prints `questions: 125` (**not 0**) |
| 3.1 | `mkdir runs/teaching-loop-medquad/pilots`; `git mv` the 12 `runs/trackA_full_arm{A,B,C,D}_*` to `1-baseline` / `2-self-refine` / `3-teacher-feedback` / `4-teacher-sees-answer` `__seed<N>__<ts>`; `git mv` the 14 `runs/trackA_p2_*` into `pilots/` | `& …python.exe -m src.tlw.analysis --runs-dir runs/teaching-loop-medquad --comparison C-B --comparison B-A` → **C-B `+0.003 [-0.021,+0.029]` p=1.0000; B-A `+0.091 [+0.051,+0.133]`; arms 0.821/0.912/0.915/0.940; NO honesty banner** *(pre-verified in V4.3)* |
| 3.2 | `git mv runs/calibration runs/judge-calibration` + regroup the 8 probes per §C.4 Study 8 **and edit `src/tlw/evaluation/calibration.py:46`** to `runs/judge-calibration` (MAJOR-4) | `& …python.exe -c "from src.tlw.evaluation.calibration import OUTPUT_DIR; print(OUTPUT_DIR)"` → ends `runs\judge-calibration`; `SMOKE` |
| 3.3 | `git mv runs_rag/* runs/rag-medquad/` with the 2×2 names. **KEEP all three `trackA_full_armA_*` copies** as `small-model-no-rag__seed*` (P0.2). Edit `rejudge.py:91`, `selective_rag_sim.py:83`, `finish_when_groq_ready.py:64,67,70`, `rag_faithfulness.py` docstrings | `& …python.exe -m src.tlw.analysis --runs-dir runs/rag-medquad --rag` → `labels present: 3B, 3B+RAG, 7B, 7B+RAG`; `3B+RAG-3B: -0.005 [-0.067,+0.056] p=0.9088`; `7B+RAG-7B: -0.069 [-0.120,-0.019] p=0.0004` |
| 3.4 | `git mv runs_rag_aspect/ + runs_rag_big/` → `runs/rag-medquad-fair-tests/` | `& …python.exe -m src.tlw.analysis --runs-dir runs/rag-medquad-fair-tests --rag` → 2 labels, no crash |
| 3.5 | `git mv runs_reliability/` → `runs/rag-medquad-reliability/` (`no-rag__seed{1..8}`, `with-rag__seed{1..8}`); **`git mv runs_hardtail/` → the same study** (P0.1 — do **not** delete); edit `reliability_analysis.py:53` default and `build_calibration.py:50` | `& …python.exe scripts/reliability_analysis.py --runs-dir runs/rag-medquad-reliability` → `questions: 125`, non-empty strata table |
| 3.6 | `git mv runs_orca/…155536Z` → `runs/student-prompt-medquad/detailed-prompt-style__seed42__20260723T155536Z`; **delete** `…155406Z` (P0.4, evidenced) | `& …python.exe -m src.tlw.analysis --runs-dir runs/student-prompt-medquad` → 1 run, `pass_rate 0.840` |
| 3.7 | `git mv runs_wixqa/*.jsonl` → the `runs/rag-wixqa/<step>/seed<N>.jsonl` ladder; **rewrite `wixqa_analyze.py:32-35` (`FILES`) and `wixqa_dose_analyze.py:31-39` (`VARIANTS`) in the same commit** (V1.6); edit `wixqa_{baseline,rag,run3seed,run3seed_retriever,selfrefine,grounding_ladder}.py` output/input paths | `& …python.exe scripts/wixqa_analyze.py` → **`+0.152 [+0.090, +0.213]`, `110/200 = 0.550`, nulls all 0**  ·  `& …python.exe scripts/wixqa_dose_analyze.py` → **`0.163 / 0.315 / 0.340`, `+0.025 [-0.030,+0.078] p=0.273`** — byte-for-byte the §P2.2 oracle |
| 3.8 | Write one `manifest.json` per condition directory + one `README.md` per study (additive) | `& …python.exe -c "import json,glob; [json.load(open(p)) for p in glob.glob('runs/*/*/manifest.json')]"` → no exception |
| 3.9 | Apply the **corrected** `.gitignore` block from V1.7 (replaces `.gitignore:236` and `:241`) — **not** the verbatim block from the proposal (BLOCKER-2) | `git add -A -n \| grep summary.jsonl` → non-empty; `git check-ignore -v runs/teaching-loop-medquad/1-baseline__seed13__*/rounds.jsonl` → matched by `runs/**` |
| 3.10 | Rename/regroup `experiments/*.yml` per §C.4. **Leave every `params.arm` value alone** (registry keys, `strategies.py:99`). Place `trackB_p3_loragen_diabetes.yml` (MINOR-2). Fix the 4 `--runs-dir runs_*` header comments. | `& …python.exe -c "import glob; from src.tlw.config.loader import load_config; [load_config(p) for p in glob.glob('experiments/**/*.yml', recursive=True)]"` → every config still validates |
| 3.11 | Update doc paths/commands per V5 (`RAG_LAW.md:320,323,326-330`; `RAG_RESULTS.md:199-209`; `WIXQA_RESULTS.md:35,93-105,338-342`; `TRACK_A_RESULTS.md:152,156,159`; `PRODUCT_RESULTS.md:111`; `RAG_RELIABILITY_ANALYSIS.md:3-4,126`) | copy-paste each edited command and run the offline ones; all must reproduce §P2.2's oracle |

> **Do NOT edit the ~20 `runs_*` mentions inside `.claude/rules/decisions.md`** (ADR-027/029/030/033
> evidence lines) — §0.6. The new ADR states the old→new mapping once; historical ADRs stay as
> written. Agreed with the proposal.

## §P4 — Reports, indexes, external data

| # | Action | Verification |
|---|---|---|
| 4.1 | Create `reports/<study>/`; `git mv` the 4 `runs_wixqa/_s*.txt`, the 2 `data/rag/retriever_ladder/*.json` and `runs_lora/lora_eval_result.json` in, renamed per §C.4. Edit output paths in `wixqa_grounding_ladder.py:39`, `wixqa_retriever_ladder.py:37`, `eval_lora.py:107` | `git ls-files reports/` → the moved files are tracked; `SMOKE` |
| 4.2 | Add `--scores-csv` to `wixqa_analyze.py` + `wixqa_dose_analyze.py`; generate and commit `reports/rag-wixqa/scores.csv` (MINOR-4 — **do this before claiming `README.md:90` is true**) | recompute the headline from the CSV alone and compare to `+0.152 [+0.090,+0.213]` |
| 4.3 | `git mv data/rag/` → `indexes/` (drop `retriever_ladder/`, moved in 4.1). Edit the 12 literals in V1.3 **including `tests/tlw/config/test_validation.py:184`** (MINOR-1) | `SMOKE` (270 passed) **and** a 4-question RAG smoke run — `corpus_path` is validated at load (`src/tlw/config/validation.py:217`) so a wrong path fails loud |
| 4.4 | `git mv data/wixqa/` → `data/external/wixqa/`; write `scripts/dataset/fetch_wixqa.py` recording the HF revision. Edit the 6 literals (`wixqa_baseline.py:23`, `wixqa_build_index.py:21`, `wixqa_rag.py:26`, `wixqa_retriever_ladder.py:35,36`, `wixqa_run3seed.py:40`) | `& …python.exe -c "from pathlib import Path; assert Path('data/external/wixqa/expertwritten.jsonl').is_file()"` |
| 4.5 | `docs/APPENDIX_PROMPTS_MEMORY_CODE.md` → `docs/archive/` + SUPERSEDED banner naming ADR-018 + T2.9 | `grep -rn "APPENDIX_PROMPTS" docs/ README.md` → only the archived copy |
| 4.6 | `data/*.jsonl` (6) → `data/legacy/` + README; verify the single `medical_all_clean` reference first | `SMOKE` |
| 4.7 | Correct `README.md:90` and `RAG_RELIABILITY_ANALYSIS.md:3-4,126` (finding 12 — the sweep completed) | `git ls-files "runs/**/summary.jsonl" \| wc -l` > 0, which is what makes `:90` true |

## §P5 — Tests tidy + regenerate the maps

| # | Action | Verification |
|---|---|---|
| 5.1a | `git mv tests/rag tests/tools/rag` | `& …python.exe -m pytest tests/ -q` → 270 passed |
| 5.1b | Add the 6 missing `__init__.py` **and delete stale bytecode in the same commit**: `find tests -name __pycache__ -type d -exec rm -rf {} +` (V3.5) | `& …python.exe -m pytest tests/ -q` → **270 passed** (watch for `import file mismatch`) |
| 5.1c | Extract `tests/tlw/test_providers.py` from `test_runner.py:316,329` | `& …python.exe -m pytest tests/ -q` → **still 270** (moved, not added) |
| 5.2 | Rewrite `.claude/rules/structure.md` → v3 from the executed tree. Junk checklist: drop the T2.9 DEAD list; add "run artifacts outside `runs/<study>/`", "analysis output inside `runs/`", "hardcoded absolute `ROOT`", "a run-discovery glob keyed on a config stem" (MAJOR-2), "a name only an insider can read" | `& …python.exe -c "import pathlib; [print(p) for p in pathlib.Path('.').glob('*') if p.is_dir() and not p.name.startswith('.')]"` cross-checked against the new tree |
| 5.3 | Rewrite `README.md` §Project-Structure + §Usage + §Configuration (kills the `simplified_experiment_runner.py` lines at `:426,429,432,483,674`) | `grep -n "simplified_" README.md` → 0 hits outside the retirement notice |
| 5.4 | `todo.md` line + tick; log the new ADR (`new-adr` skill) recording the old→new mapping once | — |
| 5.5 | **Final gate:** re-run every §P2.2 oracle + `SMOKE` + all V5 post-move commands | all numbers byte-identical to §P2.2 |

## Steps that cannot be made individually safe

| Step | Why | How it is split |
|---|---|---|
| 3.7 (WixQA) | The `git mv` and the `FILES`/`VARIANTS` rewrites are **mutually dependent** — either alone leaves the analysers broken | Must be **one atomic commit**. Mitigation: `wixqa_analyze.py` fails loud (`MISSING run files`, rc=1); `wixqa_dose_analyze.py` does **not** — a per-seed miss silently shrinks n. So verify on the printed `seeds 3 (600)` column, not just the delta. |
| 3.9 (`.gitignore`) | Only meaningful once the runs are in `runs/<study>/` | Sequence after 3.1–3.7; verify with `git add -A -n`, never by eye. |
| 5.1b (`__init__.py`) | Adding the files and purging `__pycache__` must be simultaneous | One commit, with the `find … -exec rm -rf` in the same change. |

## Rollback

Every step is one commit; phases 2–4 are `git mv` + literal edits, so `git revert <sha>` restores
the previous layout exactly. Phase 2 is behaviour-preserving by construction (same absolute path,
computed instead of typed). Phase 1 is additive except the `conftest.py`/`pytest.ini` swap, which is
a single commit and verified by the 270-test count. The two irreversible acts are the deletion of
`runs_orca/…155406Z/` (evidenced empty, V4.1) and — **only if the user overrides BLOCKER-1** —
`runs_hardtail/`, which is **not** recoverable and backs a published table.
