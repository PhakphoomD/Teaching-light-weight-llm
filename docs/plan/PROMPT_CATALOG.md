# T1.5 — Prompt Catalog: the graveyard, curated into a preset registry

**Phase:** P1 (docs only — no code, no edits to `config/prompts_config.yml`) · **Owner:** prompt-engineer
**Output of:** slot **C** of the Config Contract (`schema.md` §"Experiment Config Contract v1" → PresetRegistry)
**Depends on:** T1.1 (config contract), reads T1.4 (eval arms/judge), feeds T2.3/T2.4/T2.5 (final wording + tests)

---

## 0. TL;DR

`config/prompts_config.yml` holds **42 named prompts** (13 student + 23 teacher + 6 judge) —
an experiment graveyard where every trial was kept. This catalog gives a **KEEP/ARCHIVE verdict
for every one**, cites the real Phase-2 numbers that decided the teacher style, and proposes a
**7-preset registry** (5 survivors + 2 new skeletons the arms need but that do not exist yet).

**Survivor registry (slot C + slot F names):**

| Preset name (registry key) | Role / slot | Source variant | MODE | GT? |
|---|---|---|---|---|
| `student.minimal.first` | student / C | `student.first_attempt` (`prompts_config.yml:76-80`) | measure | GT-FREE |
| `student.minimal.refine` | student / C | `student.refinement` (`prompts_config.yml:83-88`) | measure | GT-FREE |
| `student.selfrefine.critique` | student / C (arm B) | **MISSING — skeleton in §5** | measure | GT-FREE |
| `teacher.orca.sighted` | teacher / C (arm D) | `teacher.orca_critique` (`prompts_config.yml:169-201`) | data-gen/feedback | **GT-VISIBLE (teacher-only)** |
| `teacher.orca.blind` | teacher / C (arm C) | **MISSING — skeleton in §5** | feedback | GT-FREE |
| `judge.blind` | judge / F | `metrics.blind_judge` (`prompts_config.yml:628-649`) | measure | GT-FREE |
| `judge.comparison` | judge / F | `metrics.comparison_judge` (`prompts_config.yml:677-701`) | diagnostic | GT-comparing (never student-visible) |

Everything else → **ARCHIVE** (moved to `config/archive/prompts_config_legacy.yml` in P2, not now).
Two variants are **RETIRE/quarantine, never revive**: `student.last_chance` and `teacher.difficult_question`
(confirmed §0.2 leaks — LEAKAGE_AUDIT L1, L7).

---

## 1. Why these verdicts — the evidence

### 1a. Teacher style: ORCA won, decisively (real Phase-2 numbers, §0.1/§0.4)

`logs/experiments/phase2/summary.jsonl` (3 runs, n=20, seed 42, same held set, only `feedback_style` varied):

| Run | `feedback_style` | pass_rate | avg_rounds | semantic_sim | comparison_judge | teacher_tokens |
|---|---|---|---|---|---|---|
| P2C-Orca-Style | `orca` → `orca_critique` | **0.90** | **3.6** | **0.810** | **0.870** | **43,333** |
| P2A-Principle-Style | `principle` → `principle_critique` | 0.50 | 5.2 | 0.713 | 0.785 | 78,900 |
| P2B-Simple-CoT-Style | `cot` → `cot_first_time`/`cot_refinement`/`difficult_question` | 0.40 | 5.35 | 0.709 | 0.765 | 88,538 |

Source lines: `logs/experiments/phase2/summary.jsonl:1` (P2A), `:2` (P2B), `:3` (P2C).
ORCA passed **0.90 vs 0.50 (principle) vs 0.40 (CoT)**, in the **fewest rounds (3.6)** and at
roughly **half the teacher token cost** (43k vs 79k/89k). This is the single strongest empirical
signal in the prompt logs → **orca is the surviving teacher style; principle and CoT are archived losers.**
(Note: P2B was the exact `cot` run whose `difficult_question` template produced the confirmed GT
echo — LEAKAGE_AUDIT L7/Trace C — so the losing style is also the unsafe one.)

### 1b. Student style: "minimal" was the design intent

`PROMPT_STRATEGY_MAP` (`simplified_teaching_loop.py:59-64`) enumerates 4 student lineages
(`minimal`/`structured`/`reflective`/`principle`); `DEFAULT_PROMPT_KEYS = ("first_attempt", "refinement")`
(`simplified_teaching_loop.py:66`) is the code's fallback pair. No Phase-log isolates a student-style
winner (Phase-2 varied only the teacher), so the tie-breaker is **design intent — minimal prompts
for small models** — and the code's own default. The verbose `structured_*`/`reflective_*` lineages
and the Constitutional-AI `principle_rewrite` never won anything measurable → archived as unvalidated
ablation variants.

### 1c. Anti-leakage (§0.2, LEAKAGE_AUDIT) is a hard filter on KEEP eligibility

`{ground_truth}` appears in 21 templates (`Grep ground_truth config/prompts_config.yml`). Rules applied:
- **Student-visible template with `{ground_truth}` → cannot be a KEEP** (BLOCKER). Only `student.last_chance`
  (`prompts_config.yml:101-103`, L1) qualifies → RETIRE.
- **Teacher template that puts `{ground_truth}` in a *teacher-only context block* → legal** (`[Target Answer]`),
  eligible as a `*.sighted` (GT-VISIBLE) preset.
- **Teacher template that instructs the model to *echo* `{ground_truth}` into its returned text → BLOCKER**
  (the returned string is student-visible next round + memory-stored). `difficult_question`
  (`:369` `Example: {ground_truth}`, L7, production-confirmed) and `template_feedback`
  (`:512` `Example: {ground_truth}`) both fail this → RETIRE / archive.
- **Judge:** `blind_judge` GT-FREE (measure-mode student judge, §0.2 clean). `comparison_judge` sees GT
  but only in the score path, never student-visible (LEAKAGE_AUDIT L10, legal) → KEEP as diagnostic only.

---

## 2. Full inventory + verdict — STUDENT (13 variants)

| # | Variant (`student.*`) | file:line | Role | Used-by evidence | `{ground_truth}`? | Verdict → preset |
|---|---|---|---|---|---|---|
| S1 | `initial_draft` | `11-21` | first (orca-scaffold) | `active.student_first` default (`:731`); pairs w/ orca via `refine_with_teacher` | no | ARCHIVE (structured scaffold; superseded by `student.minimal.first` — see §6 caveat) |
| S2 | `refine_with_teacher` | `25-48` | refine (structured) | `active.student_refine` default (`:732`); consumes `teacher_critique`+`teacher_improvements` | no | ARCHIVE (structured; see §6 caveat) |
| S3 | `principle_rewrite` | `51-73` | refine | `PROMPT_STRATEGY_MAP["principle"]` (`loop:63`) | no | ARCHIVE (principle style lost, §1a) |
| S4 | `first_attempt` | `76-80` | first (minimal) | `DEFAULT_PROMPT_KEYS[0]` (`loop:66`); `active` option (`:731`) | no | **KEEP → `student.minimal.first`** |
| S5 | `refinement` | `83-88` | refine (minimal) | `DEFAULT_PROMPT_KEYS[1]` (`loop:66`); consumes single `{feedback}` | no | **KEEP → `student.minimal.refine`** |
| S6 | `refinement_no_feedback` | `91-97` | refine fallback | none found (grep) | no | ARCHIVE (redundant w/ S4) |
| S7 | `last_chance` | `101-103` | GT-hint | `build_ground_truth_hint_prompt` (`src/prompts/student.py:118-133`), L1/L2/L3 | **YES** | **RETIRE — §0.2 BLOCKER, quarantine (LEAKAGE_AUDIT L1)** |
| S8 | `simple_minimal` | `106-109` | first (minimal) | Phase-1.1 analysis (comment `:105`) | no | ARCHIVE (near-dup of S4) |
| S9 | `simple_minimal_refine` | `111-116` | refine | Phase-1.1 (comment `:105`) | no | ARCHIVE (near-dup of S5) |
| S10 | `structured_first` | `119-125` | first | `PROMPT_STRATEGY_MAP["structured"]` (`loop:61`) | no | ARCHIVE (unvalidated ablation, §1b) |
| S11 | `structured_refine` | `127-133` | refine | `PROMPT_STRATEGY_MAP["structured"]` (`loop:61`) | no | ARCHIVE (unvalidated ablation) |
| S12 | `reflective_first` | `137-144` | first | `PROMPT_STRATEGY_MAP["reflective"]` (`loop:62`) | no | ARCHIVE (unvalidated ablation) |
| S13 | `reflective_refine` | `146-155` | refine | `PROMPT_STRATEGY_MAP["reflective"]` (`loop:62`) | no | ARCHIVE (unvalidated ablation) |

## 3. Full inventory + verdict — TEACHER (23 variants)

Dispatch table for wired teacher prompts: `src/simplified/teacher_feedback.py:82-88` (style→prompt map)
and `:155-181` (style branch). Anything not reachable from a `feedback_style` value is **graveyard**
(never wired to a runnable path).

| # | Variant (`teacher.*`) | file:line | Wired? (`feedback_style`) | GT placement | Verdict → preset |
|---|---|---|---|---|---|
| T1 | `orca_critique` | `169-201` | **yes** (`orca`, `tf.py:84`) | `[Target Answer]` teacher-only | **KEEP → `teacher.orca.sighted`** (GT-VISIBLE, arm D) + basis for `teacher.orca.blind` skeleton |
| T2 | `principle_critique` | `204-236` | yes (`principle`, `tf.py:85`) | `[Target Answer]` teacher-only | ARCHIVE (principle lost 0.50, §1a) |
| T3 | `stop_decision` | `239-269` | yes (`stop_decision`, `tf.py:159`) | **none — GT-free** | ARCHIVE (utility prompt, not a feedback style; GT-free → candidate seed for §5 blind skeleton) |
| T4 | `cot_first_time` | `272-300` | yes (`cot`, `tf.py:86`) | `[Target Answer]` teacher-only | ARCHIVE (CoT lost 0.40, §1a) |
| T5 | `cot_refinement` | `303-335` | yes (`cot`, `tf.py:86`) | `[Target Answer]` teacher-only | ARCHIVE (CoT lost) |
| T6 | `difficult_question` | `338-373` | yes (`cot` round≥4, `tf.py:172-176`) | `[Target Answer]` **+ `Example: {ground_truth}` in OUTPUT** | **RETIRE — §0.2 BLOCKER, quarantine (LEAKAGE_AUDIT L7, production-confirmed `logs/simplified/debug/20251130_024301.json:4460`)** |
| T7 | `cot_short` | `378-386` | no (graveyard) | `Target: {ground_truth}` + asks to show format | ARCHIVE (unwired ablation; echo-risk) |
| T8 | `cot_short_refine` | `388-396` | no | echo-risk | ARCHIVE |
| T9 | `cot_example` | `399-407` | no | `Correct answer: {ground_truth}` + "Use format" | ARCHIVE (echo-risk) |
| T10 | `cot_example_refine` | `409-418` | no | echo-risk | ARCHIVE |
| T11 | `cot_clean` | `421-431` | no | `Correct: {ground_truth}` + "Format:" | ARCHIVE (echo-risk) |
| T12 | `cot_clean_refine` | `433-443` | no | echo-risk | ARCHIVE |
| T13 | `direct_simple` | `448-454` | no | `Correct: {ground_truth}` | ARCHIVE |
| T14 | `direct_simple_refine` | `456-462` | no | `Target: {ground_truth}` | ARCHIVE |
| T15 | `direct_template` | `465-469` | no | `format: {ground_truth}` + "Adjust yours to match" | ARCHIVE (echo — hands GT to student) |
| T16 | `direct_template_refine` | `471-475` | no | `Expected: {ground_truth}` + "Match this format exactly" | ARCHIVE (echo) |
| T17 | `direct_diff` | `478-482` | no | brackets only | ARCHIVE (unwired) |
| T18 | `direct_diff_refine` | `484-489` | no | `+ {ground_truth}` in OUTPUT | ARCHIVE (echo) |
| T19 | `direct` | `492-499` | yes (`cot` + `use_cot:false`, `tf.py:181,352`) | `Correct: {ground_truth}` in prompt | ARCHIVE (direct style, no win evidence) |
| T20 | `template_feedback` | `502-516` | yes (`template`, `tf.py:162`) | `3. Example: {ground_truth}` in OUTPUT | ARCHIVE + echo-flag (same L7-class defect as T6) |
| T21 | `socratic_feedback` | `519-527` | yes (`socratic`, `tf.py:166`) | **none — GT-free** | ARCHIVE (weak/unvalidated; GT-free → candidate seed for §5 blind skeleton) |
| T22 | `legacy_full` | `531-577` | no (`src/prompts/teacher.py` = 0-importer DEAD, ADR-015) | `<CORRECT_ANSWER>` teacher-only | ARCHIVE (dead) |
| T23 | `legacy_simple` | `579-596` | no (dead) | none — GT-free | ARCHIVE (dead) |

## 4. Full inventory + verdict — JUDGE / metrics (6 variants)

`src/simplified/metrics.py:90-98` builds two judge clients keyed `blind_judge` + `comparison_judge`;
prompts resolved via `get_metrics_prompt` (`prompt_loader.py:134-158`).

| # | Variant (`metrics.*`) | file:line | Sees GT? | MODE | Verdict → preset |
|---|---|---|---|---|---|
| J1 | `blind_judge` | `628-649` | no | measure (student-blind) | **KEEP → `judge.blind`** (primary correctness judge, T1.4 §3 blind-first) |
| J2 | `blind_judge_strict` | `603-613` | no | measure | ARCHIVE (calibration variant — revive in T2.3 calibration if needed) |
| J3 | `blind_judge_lenient` | `615-625` | no | measure | ARCHIVE (calibration variant) |
| J4 | `comparison_judge` | `677-701` | yes (score path) | diagnostic (`reference_match`) | **KEEP → `judge.comparison`** (never student-visible; LEAKAGE_AUDIT L10 legal) |
| J5 | `comparison_judge_strict` | `652-662` | yes | diagnostic | ARCHIVE (calibration variant) |
| J6 | `comparison_judge_lenient` | `664-674` | yes | diagnostic | ARCHIVE (calibration variant) |

> Note: `judge.blind` is the pass/fail correctness metric per T1.4 §2 ("two metrics, never merged").
> `judge.comparison` is a **diagnostic column only** and must never gate the loop nor reach the student.
> The current hybrid weights (`comparison 0.35 + semantic 0.25 + rouge 0.10 = 70%` reference-proximity,
> LEAKAGE_AUDIT §2) are the ADR-001 defect; T1.4/T2.3 own the fix — this catalog only supplies the
> two prompt names, not the weighting.

---

## 5. Missing presets — skeletons the arms require (final wording lands in T2.3/T2.4)

Per T1.4/T2.4 arm table, two survivors **do not exist in the current file** and must be authored.
Skeletons only (design intent + slot placement); final text + leakage tests are T2.3/T2.4 scope.

### 5a. `teacher.orca.blind` — arm C (blind-teacher), GT-FREE

Arm C = "teacher feedback WITHOUT seeing GT" (T1.4 §1, T2.4 step 1C). **No such prompt exists** — every
wired feedback style except `stop_decision`/`socratic_feedback` shows GT to the teacher, and those two
are weak. Derive from the WINNING `orca_critique` (T1) by **removing the `[Target Answer] {ground_truth}`
block** and asking the teacher to critique on its own domain knowledge.

```yaml
# GT-FREE: no {ground_truth} placeholder anywhere. MODE=feedback (arm C).
# Skeleton — final wording + leakage test in T2.4. Derived from orca_critique minus [Target Answer].
teacher.orca.blind: |
  You are the Teacher model.
  [Task] {question}
  [Student Answer] {student_answer}
  Evaluate using your own knowledge (no reference answer is provided).
  1. Critique: concrete factual/reasoning gaps.
  2. Score: 0-100.
  3. Improvements: step-by-step; do NOT rewrite the whole answer.
  # invariant: template MUST NOT contain {ground_truth}; verified by grep + T2.4 leakage test
```

### 5b. `student.selfrefine.critique` — arm B (self-refine), GT-FREE

Arm B = "student critiques itself, no teacher" (T1.4 §1, T2.4 step 1B). **No self-critique prompt exists.**
Arm B pipeline = `student.minimal.first` (draft) → `student.selfrefine.critique` (self-critique) →
`student.minimal.refine` (revise, consuming the self-critique as `{feedback}`). Only the critique step is new.

```yaml
# GT-FREE: student sees only its own question + answer. MODE=measure (arm B, no teacher).
# Skeleton — final wording + leakage test in T2.4.
student.selfrefine.critique: |
  Question: {question}
  Your answer: {previous_answer}
  List the specific weaknesses in your answer (missing facts, unclear parts, wrong claims).
  Do not rewrite it yet — only critique.
  Weaknesses:
  # invariant: no {ground_truth}; consumes only {question}+{previous_answer}
```

---

## 6. Design decision surfaced (needs hub awareness, not resolved here)

**Minimal students vs the structured orca-paired pair.** The Phase-2 winner ran with the *default active*
student pair `initial_draft`/`refine_with_teacher` (S1/S2, `active` `:731-732`), which consume orca's
**structured** `teacher_critique` + `teacher_improvements` fields. This catalog recommends the **minimal**
pair `first_attempt`/`refinement` (S4/S5) instead — matching the "minimal prompts for small models" design
intent and the code's own `DEFAULT_PROMPT_KEYS`. That recommendation **assumes T2.4's loop v2 flattens
teacher feedback into a single `{feedback}` string** (which `student.minimal.refine` consumes), rather than
threading two structured fields. This is a reasonable simplification (T2.4 explicitly wants a one-screen
loop), but it means archiving the only student pair that has a validated end-to-end Phase-2 run.

→ **NEEDS-HUB-DECISION (flag for gate, do not resolve here):** confirm the loop v2 flattens feedback to a
single string (→ keep minimal pair, archive S1/S2), **or** retain `initial_draft`/`refine_with_teacher` as
`student.orca.first`/`student.orca.refine` for structured-feedback continuity with the Phase-2 baseline.
If unresolved at T2.4 start, keep BOTH pairs (registry supports it) and let the arm C/D pilot (T2.7) decide.

---

## 7. Target file layout (proposal — moves happen in P2/T2.x, NOT now)

`config/prompts_config.yml` stays untouched (runtime still reads it — Must-NOT-do). Proposed P2 split,
one file per role, names = PresetRegistry keys:

```
config/
  prompts/
    student.yml   # student.minimal.first, student.minimal.refine, student.selfrefine.critique
    teacher.yml   # teacher.orca.sighted   # GT-VISIBLE: teacher-only
                  # teacher.orca.blind     # GT-FREE
    judge.yml     # judge.blind (measure), judge.comparison (diagnostic, GT in score-path only)
  archive/
    prompts_config_legacy.yml   # all 35 ARCHIVE variants (frozen, never registry-resolved)
                                # incl. RETIRE/quarantine block: student.last_chance, teacher.difficult_question
                                #   -> quarantined even within archive: MUST NOT be a registry key (§0.2)
```

**PresetRegistry resolution (slot C, `schema.md`):** `preset: {student: minimal, teacher: orca}` →
- `student: minimal` → family `{first: student.minimal.first, refine: student.minimal.refine}`
  (+ `selfrefine` adds `critique` for arm B).
- `teacher: orca` → family `{sighted: teacher.orca.sighted, blind: teacher.orca.blind}`.
- **Slot E `arm` selects the variant within the family:** arm C → `teacher.orca.blind`; arm D →
  `teacher.orca.sighted`; arm A → no teacher, `student.minimal.first` only; arm B → `student.selfrefine.*`,
  no teacher. This keeps slot C stable across arms C/D (same preset name, arm picks blind vs sighted).

**Slot F (judge)** is resolved separately via `eval.judge` + `eval.mode` (`schema.md` slot F): `mode: blind`
→ `judge.blind`; the `comparison`/`reference_match` diagnostic → `judge.comparison`. Judge presets live in
`judge.yml` but are NOT part of slot C's `preset:` dict.

**Header notation convention (for the P2 files):** every GT-visible teacher template carries a first-line
comment `# GT-VISIBLE: teacher-only` (per this task's step 3). GT-free templates carry `# GT-FREE`.

---

## 8. Naming convention (locked for the registry)

`<role>.<style>.<variant>` — lowercase, dot-separated:
- `<role>` ∈ `{student, teacher, judge}`
- `<style>` = the surviving strategy (`minimal`, `selfrefine`, `orca`, `blind`, `comparison`)
- `<variant>` = position/mode in the loop (`first`, `refine`, `critique`, `sighted`, `blind`)

Examples: `student.minimal.first`, `teacher.orca.sighted`, `judge.blind`.
