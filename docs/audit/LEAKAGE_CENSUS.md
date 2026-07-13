# T0.3 — Ground-Truth Leakage Census

**Phase:** P0 (read-only) · **Owner:** qa-engineer · **Status:** complete
**Objective:** enumerate every path by which the reference answer (ground truth, "GT") can
reach the student, the memory store, or the score, with file:line evidence, so P2 (T2.3/T2.4/T2.5)
can seal each one with a test. No files modified except this one (§ Must-NOT-do honored).

---

## 0. Legal vs illegal, per §0.2

- **LEGAL (teacher-sees-GT for feedback/training-data generation):** the teacher LLM prompt
  (`orca_critique`, `cot_first_time`, `principle_critique`, etc. in `config/prompts_config.yml`)
  is allowed to see `{ground_truth}` — that is its job. The **comparison judge** and **metrics
  (`semantic_sim`, `rouge_l`, `exact_match`)** are also allowed to see GT — that is measurement-
  *of-reference-match*, not the eval-integrity violation §0.2 forbids, **provided** the student
  itself and the *pass/fail* decision fed back to the student never surface the raw GT text.
- **ILLEGAL under §0.2:** anything that puts the literal GT string (or a close paraphrase/quote
  of it) into (a) a prompt sent to the **student** model, or (b) a **memory record** that will
  later be retrieved and placed into a student prompt. Both of these corrupt "the student learned"
  into "the student was shown/handed the answer."

---

## 1. Classified hits (every live `ground_truth` reference)

| ID | Path | File:line | Class | Severity | Legal? |
|----|------|-----------|-------|----------|--------|
| L1 | `build_ground_truth_hint_prompt(question, ground_truth, previous_answer)` renders `last_chance` template = `"COPY THIS EXACTLY:\n{ground_truth}"` | `src/prompts/student.py:118-133` → `config/prompts_config.yml:101-103` | **STUDENT-VISIBLE** | BLOCKER | ILLEGAL (by design — a deliberate "cheat" mechanism) |
| L2 | LAST_CHANCE mode selection: `mode = "LAST_CHANCE"` when `enable_last_chance and (use_ground_truth or (round_num >= ground_truth_hint_round and ...))`; calls L1 | `simplified_teaching_loop.py:358-364` | **STUDENT-VISIBLE** (trigger site) | BLOCKER | ILLEGAL |
| L3 | Early-stop "one last chance" block: builds `prompt_last = build_ground_truth_hint_prompt(...)`, sends to student (`self.student.answer(prompt_last)`) | `simplified_teaching_loop.py:622-644` | **STUDENT-VISIBLE** | BLOCKER | ILLEGAL |
| L4 | If L3's forced round passes, GT is stored **verbatim as feedback**: `ground_truth_feedback = f"The correct answer is: {ground_truth}"` → `self.memory.store(...)` | `simplified_teaching_loop.py:707-716` | **MEMORY-STORED** (also re-surfaces as L6 later) | BLOCKER | ILLEGAL |
| L5 | Repetition-triggered ground truth: same L1/L2 mechanism, gated by `rep_config.get('trigger_ground_truth', True)` | `simplified_teaching_loop.py:319-354` (esp. 347-354) | **STUDENT-VISIBLE** (trigger site) | BLOCKER | ILLEGAL |
| L6 | **Memory retrieval → student prompt.** Round 1: `feedback_info = self.memory.get_best_feedback(question)`; if found, `prompt = build_refinement_prompt(..., feedback=feedback_info['feedback'], ...)` sent straight to the student. `get_best_feedback` returns whatever string is stored as `teaching_feedback` — **with no filter for GT content.** | retrieval: `simplified_teaching_loop.py:295-300, 368-376`; prompt build: `src/simplified/student.py:61-128`; store read: `src/simplified/memory.py:237-303` | **STUDENT-VISIBLE** (structural — independent of L1-L5) | **BLOCKER** | ILLEGAL when the stored feedback contains GT (see L4, L7, L8) |
| L7 | `difficult_question` teacher prompt (round ≥4, `feedback_style: cot`) **instructs the teacher to output GT verbatim**: `"...Return ONLY: 'Error: ... Format: ... Example: {ground_truth}'"` — the teacher's returned `feedback` string literally contains the GT text under the "Example:" label. | prompt template: `config/prompts_config.yml:337-373` (esp. 369); wired in: `src/simplified/teacher_feedback.py:172-176, 266-283` | **STUDENT-VISIBLE** (feedback re-enters student prompt next round via `last_generated_feedback`) **+ MEMORY-STORED** (saved via `memory.store` below) | **BLOCKER — confirmed in real logs, see §4** | ILLEGAL (teacher is allowed to *see* GT, but here it is told to *echo* GT into the artifact that is shown to the student) |
| L8 | Teacher-generated feedback (any style) saved to memory unconditionally as long as final feedback text exists — no leak-content check before writing to disk/FAISS | store on success: `simplified_teaching_loop.py:526-534`; store on failure: `simplified_teaching_loop.py:748-759` | **MEMORY-STORED** (vector for whatever `last_generated_feedback` happens to contain — including L7's leak) | MAJOR (amplifies L7 into a persistent, reusable leak) | Depends on content — currently unchecked |
| L9 | `orca_critique`/`principle_critique`/`cot_first_time`/`cot_refinement` teacher prompts show `[Target Answer] {ground_truth}` to the **teacher LLM only** — this is the legal per-§0.2 feedback-generation use. Feedback text extracted afterward (`_extract_feedback`, `_parse_orca_feedback`, etc.) is *supposed* to summarize without quoting GT, but nothing enforces that (see L7 for the one template that explicitly asks it to quote GT; the others rely on LLM behavior/prompting discipline only). | `config/prompts_config.yml:169-336`; `src/simplified/teacher_feedback.py:109-152` | **TEACHER-ONLY (allowed)** input side; **unverified** on the output side for orca/principle/cot templates other than L7 | MINOR (residual risk — no verbatim instruction, but no output filter either) | LEGAL as designed; residual risk flagged |
| L10 | Comparison judge sees GT to score accuracy: `self._get_comparison_score(question, student_answer, ground_truth)` → `comparison_judge` prompt shows `{ground_truth}` | `src/simplified/metrics.py:171, 273-324`; template `config/prompts_config.yml:677-701` | **SCORE-PATH** | — (see §2 for weight) | LEGAL (measurement, not student-visible) |
| L11 | `semantic_sim` computed against GT: `det_metrics.semantic_similarity(student_answer, ground_truth, ...)` | `src/simplified/metrics.py:150-156` | **SCORE-PATH** | — | LEGAL (reference-match diagnostic, not shown to student) |
| L12 | `rouge_l` computed against GT: `det_metrics.rouge_scores(student_answer, ground_truth)` | `src/simplified/metrics.py:146-148` | **SCORE-PATH** | — | LEGAL |
| L13 | `exact_match` computed against GT (currently commented out of active weights — see §2) | `src/simplified/metrics.py:141-144` | **SCORE-PATH** | — | LEGAL |
| L14 | Debug logger records `ground_truth` verbatim per-question for later analysis: `self.debug_logger.start_question(..., ground_truth=ground_truth)` → written to `logs/simplified/debug/*.json` | `simplified_teaching_loop.py:281-285`; `src/simplified/debug_logger.py:82-94, 252-272` | **LOG-ONLY** | MINOR | LEGAL (write-once evidence, never read back into a prompt) — but see §4, these logs are how L7 was *caught*, so keep them |
| L15 | Terminal UI displays a truncated GT string to the human operator during a run | `src/simplified/terminal_ui.py:147-172` | **LOG-ONLY** (console, not fed back to model) | MINOR | LEGAL |
| L16 | `src/eval/metrics.py` / `src/eval/reports.py` / `tools/dataset/judge.py` accept a `ground_truth` dict for **offline** text-metric computation (BLEU/ROUGE/F1) and dataset-quality judging — not part of the live loop's student path | `src/eval/metrics.py:144-483`; `src/eval/reports.py` (docstring only, no functional ref) | **SCORE-PATH** (offline analysis) | — | LEGAL |
| L17 | `scripts/compare_students.py` explicitly computes proximity to "the reference answer" **without showing it to the model** (comment states "§0.2" awareness) | `scripts/compare_students.py:5` | **SCORE-PATH** | — | LEGAL, self-documented |
| L18 | Notebook `notebooks/experiment.ipynb` deliberately **pre-seeds** a memory JSONL with GT-as-feedback (`"source": "ground_truth_injection"`) before running P6B/P6C — this is a controlled demonstration of L4/L6, not a hidden production path, but it is the literal mechanism behind ADR-001's "P6C 100% = memorization" claim | `notebooks/experiment.ipynb` cells ~2871-2876, ~3210-3254 | **MEMORY-STORED** (research artifact) | BLOCKER (as demonstration) / not a live-loop bug since it required manual injection | Deliberately illegal-for-measurement, legal-as-a-diagnostic-experiment (ADR-001 evidence) |

---

## 2. Score-path weight audit (real values from `config/simplified_config.yml`)

Active weights (`teacher.metrics.weights`, lines 47-53 — `exact_match` is commented out at line 53):
```
blind_score:       0.30   # no GT (blind judge)
comparison_score:  0.35   # SEES GT
semantic_sim:      0.25   # SEES GT (embedding vs. GT)
rouge_l:           0.10   # SEES GT (LCS vs. GT)
```
Sum of **active** weights = 0.30 + 0.35 + 0.25 + 0.10 = **1.00** exactly. `MetricsEvaluator._compute_final_score`
(`src/simplified/metrics.py:198-220`) also normalizes by `total_weight` regardless, so even a
non-1.0 sum would not silently mis-scale the score — but the comment above the block is wrong (see below).

**Finding on the comment (line 45-46 vs 47-53):**
```
config/simplified_config.yml:45  # Total: blind(0.3) + comparison(0.3) + semantic(0.2) + rouge(0.1) + exact(0.1) = 1.0
config/simplified_config.yml:47-53  blind_score: 0.3 / comparison_score: 0.35 / semantic_sim: 0.25 / rouge_l: 0.10  (exact_match commented out)
```
The comment's numbers (`comparison=0.3`, `semantic=0.2`, `exact=0.1` present) **do not match** the
actual active dict (`comparison=0.35`, `semantic=0.25`, `exact_match` absent). Both the comment's
implied sum and the real dict's sum happen to equal 1.0, but the comment is **stale/wrong** about
which metric carries which weight — an honesty (§0.1) documentation defect, not a scoring-math bug.

**GT-exposed fraction of final_score:** `comparison_score(0.35) + semantic_sim(0.25) + rouge_l(0.10)`
= **0.70 / 1.00 = 70%** of the weighted final score is reference-proximity, vs. 30% from the blind
(no-GT) judge. This matches the hub's directional "~65-75%" estimate — confirmed exactly at 70%
against the real config values on disk today.

---

## 3. Artifacts under `logs/experiments/` (list only — NOT modified, immutable evidence)

| Artifact | What it is | Relevant to |
|---|---|---|
| `logs/experiments/phase6/gt_memory_store.jsonl` (32 records) | Pre-seeded memory: `teaching_feedback` = `"Reference Answer for similar question:\n...\nCorrect Answer: <verbatim GT>\n\nUse this verified answer as guidance..."`, `source: "ground_truth_injection"` | L6, L18 |
| `logs/experiments/phase6/ground_truth_memory.json` (7841 lines) | Raw GT + embeddings staged before being turned into `gt_memory_store.jsonl` | L18 |
| `logs/experiments/phase6/summary.jsonl` | 3 lines: P6A (no memory) pass_rate 0.75; **P6B (GT-in-memory) pass_rate 0.90**; **P6C (same-questions, similarity_threshold 0.95, top_k 1) pass_rate 1.00, memory_hit_rate 1.00** | direct quantitative evidence that L6+L18 (memory-fed GT) drives "100%" — corroborates ADR-001 |
| `logs/experiments/phase6/configs/P6B-WithGroundTruth-Memory.yml`, `P6C-SameQuestions-PerfectMatch.yml`, `P6A-NoMemory-Baseline.yml` | Run configs for the above — **note:** all three hardcode an absolute path `C:\Users\ham25\Desktop\Teaching-light-weight-llm-based-project\...` (a different path than the current repo root `...\ITA602\Teaching-light-weight-llm-based-project`) — a structure.md-flagged smell, non-reproducible (§0.3) | separate MINOR finding, not a leakage path itself |
| `logs/simplified/debug/20251130_024301.json:4460` | Real captured teacher output: `"feedback": "Example: Almost anyone, including children and teens, can have hematuria. Factors that increase..."` | **direct confirmation of L7** — the `difficult_question` CoT template caused the teacher to literally echo the GT answer text into the `feedback` field that flows back to the student and to memory |
| `logs/simplified/debug/*.json` (~190 files) | Per-round debug logs; each records `ground_truth` under `start_question` (L14) — write-once, not read back into any prompt; safe as LOG-ONLY | L14 |

---

## 4. End-to-end traces (STUDENT-VISIBLE / MEMORY-STORED paths)

**Trace A — explicit "last chance" (L1/L2/L3/L5):**
Trigger: `enable_last_chance=True` AND (repetition detected for `consecutive_rounds` OR `round_num >= max_rounds-1` with a failing previous round) OR early-stopping's forced extra round.
→ `build_ground_truth_hint_prompt(question, ground_truth, previous_answer)` renders `"COPY THIS EXACTLY:\n{ground_truth}"` → sent directly to `self.student.answer(...)`.
→ If it passes, GT is stringified as `"The correct answer is: {ground_truth}"` and written into `FAISSMemory.store(...)` (L4) — a **second-generation leak**: any future question whose embedding is similar (`similarity_threshold`, default 0.75) will retrieve this record via `get_best_feedback` and receive the GT text as "feedback" in its **very first round**, without ever triggering last-chance itself.
**Current config posture:** `config/simplified_config.yml:77` `enable_last_chance: false`, `:93` `trigger_ground_truth: false` — both OFF today. **The code paths remain live** (nothing in `simplified_teaching_loop.py` short-circuits based on these flags except the `if enable_last_chance and (...)` gate at line 358 and the `if rep_config.get('trigger_ground_truth', True) and ...` gate at line 624/347). A future config edit (or an older `configs/*.yml` snapshot, e.g. anything predating these two flags) re-enables the entire path with zero code changes.

**Trace B — memory-fed feedback (L6, independent of Trace A):**
Trigger: round 1 of *any* question, unconditionally: `feedback_info = self.memory.get_best_feedback(question)` (`simplified_teaching_loop.py:296`).
→ If a similar-enough record exists (`similarity_threshold`, `min_success_rate` gates in `memory.py:237-303`), its `teaching_feedback` string — **whatever it contains** — is placed into `build_refinement_prompt(..., feedback=feedback_info['feedback'], ...)` (`simplified_teaching_loop.py:370-376`) and sent to the student.
→ **Nothing validates that `teaching_feedback` is GT-free before this happens.** This is how `gt_memory_store.jsonl` (deliberately seeded, L18) and any accidental Trace-A/Trace-C leak (L4, L7+L8) become student-visible on completely unrelated future runs — the leak "leaks forward in time" via the persistent JSONL + FAISS index, across process restarts.
→ Confirmed quantitatively: `phase6/summary.jsonl` — P6C (`memory_similarity_threshold=0.95`, `top_k=1`, same-question re-run) → `memory_hit_rate: 1.0`, `pass_rate: 1.0`.

**Trace C — teacher-feedback echo (L7/L8, independent of Trace A/B):**
Trigger: `feedback_style: cot` AND `round_num >= 4` AND a `previous_feedback` exists (`teacher_feedback.py:172-176`) → `_build_difficult_question_cot_prompt` → `config/prompts_config.yml:337-373` template, whose *own instructions to the teacher LLM* are: `"Return ONLY: 'Error: [diagnosis]. Fix: [specific instruction]. Format: ...'. Example: {ground_truth}"`.
→ The teacher LLM complies and returns a `feedback` string containing the literal GT text after "Example:" — **observed in production logs** (`logs/simplified/debug/20251130_024301.json:4460`).
→ This `feedback` becomes `last_generated_feedback` (`simplified_teaching_loop.py:607`) → used to build the **next round's student prompt** (`simplified_teaching_loop.py:402-412`, feedback_text path) → **STUDENT-VISIBLE**.
→ It is also unconditionally persisted via `self.memory.store(question, feedback=last_generated_feedback, ...)` on both success (`:528-534`) and failure (`:750-759`) → **MEMORY-STORED**, feeding Trace B for all future similar questions.
**Current config posture:** default `config/simplified_config.yml:26` sets `feedback_style: "orca"`, so Trace C is **not active by default today** — but `phase2/configs/P2B-Simple-CoT-Style.yml:34` set `feedback_style: cot`, and the debug log above is from a `cot`-style run, confirming this path executed in a real historical experiment.

---

## 5. Seal requirements for P2 (consumable by T2.3/T2.4/T2.5)

1. **No raw-GT-substring test on every student-bound prompt.** Any function that builds a
   prompt destined for the student model (`build_first_attempt_prompt`, `build_refinement_prompt`,
   `build_ground_truth_hint_prompt`, and their v2 successors) must be covered by a test that
   asserts `ground_truth not in prompt` (or a fuzzy/substring variant with normalization) for
   every code path that can reach it. Seals L1, L2, L3, L5, L6, L7(student side).
2. **Store-time tripwire on the memory backend (T2.5, per ADR-015).** `FAISSMemory.store()` (or
   its v2 replacement) must reject/strip any `feedback` string containing the `ground_truth`
   passed in at write time, or must refuse to accept `ground_truth` as an input at all (v2 memory
   should never receive GT in its call signature). Seals L4, L6, L7(memory side), L8, L18.
3. **Prompt-template lint for teacher templates.** Any teacher-facing prompt template (`orca_*`,
   `principle_*`, `cot_*`, `difficult_question`, `stop_decision`, etc.) must be scanned for
   instructions that ask the model to **echo** `{ground_truth}` into its *returned* text (e.g. the
   literal string `"{ground_truth}"` appearing outside of a clearly-teacher-only `[Target Answer]`
   block). `difficult_question` (`config/prompts_config.yml:369`) currently fails this check and
   must be rewritten or retired before P2 adopts a `cot`-family feedback style. Seals L7 at the
   template-authoring level (defense in depth alongside seal #1/#3 runtime checks).
4. **Config-flag dead-path removal, not just default-off.** `enable_last_chance` and
   `trigger_ground_truth` being `false` today (`config/simplified_config.yml:77,93`) is a config
   choice, not a structural guarantee — P2's rebuilt loop (T2.4) should not carry these branches
   forward as toggleable dead code; the "last chance" behavior (if kept at all) must live outside
   the arms used for the honest measurement (Arms A-D of ADR-002), never reachable from a measured
   run regardless of config.
5. **Judge/measure independence check (§0.2, family rule).** Track-A eval config must assert the
   student model family ≠ judge model family (`providers.md`) at config-load time (T2.1) — this is
   adjacent to leakage (a same-family judge is a softer form of "seeing" the same priors as the
   student) and should be a fail-loud validation, not a convention.
6. **Historical-artifact quarantine.** `logs/experiments/phase6/*` (gt_memory_store.jsonl,
   ground_truth_memory.json) and the notebook cells that generated them must never be pointed to
   by any Track-A config (`memory.storage_path`) — add a denylist/allowlist check in T2.1's config
   loader for `memory.storage_path` values matching `phase6` or containing `gt_memory` / `ground_truth`
   in the filename.

---

## VERDICT: PASS-WITH-NOTES

The census is complete and evidence-backed: every `ground_truth` reference in live code has been
read and classified, the score-path weight math has been reproduced from the real config file, and
one **previously-undocumented, production-confirmed** leak (L7/Trace C — teacher-instructed GT echo
via the `difficult_question` CoT template) was found beyond the hub's known starting points, with a
real log line as proof. "PASS-WITH-NOTES" rather than plain PASS because this is a survey deliverable,
not a code fix — the NOT VERIFIED items below are genuine gaps the spec's steps didn't require closing
but that P2 should be aware of.

## FINDINGS (heaviest first)

- **[BLOCKER] Memory-retrieval path is a structural, always-on student-visible leak (L6/Trace B), independent of `enable_last_chance`/`trigger_ground_truth` flags**
  - evidence: `simplified_teaching_loop.py:295-300, 368-376` (unconditional round-1 `memory.get_best_feedback` → `build_refinement_prompt(feedback=...)`); `src/simplified/memory.py:237-303` (`get_best_feedback` has no content filter); `logs/experiments/phase6/gt_memory_store.jsonl:1-5` (stored `teaching_feedback` = verbatim GT); `logs/experiments/phase6/summary.jsonl:3` (P6C `memory_hit_rate: 1.0`, `pass_rate: 1.0`)
  - why: §0.2 — the student must never see the reference answer; a config flag that disables the *hint* mechanism (L1-L3/L5) does nothing to stop *already-stored* GT-as-feedback from being retrieved and shown to the student on any future question, including ones outside the original experiment
  - fix: seal requirement #2 (store-time tripwire) is mandatory for T2.5, not optional; owner: data-engineer (T2.5) + qa-engineer (test coverage, T2.3)

- **[BLOCKER] Teacher template instructs verbatim GT echo into student-bound feedback — confirmed in production logs (L7/L8/Trace C)**
  - evidence: `config/prompts_config.yml:369` (`"Example: {ground_truth}"` inside the *returned-output* instruction, not a teacher-only context block); `src/simplified/teacher_feedback.py:172-176, 266-283` (wiring); real captured output `logs/simplified/debug/20251130_024301.json:4460`: `"feedback": "Example: Almost anyone, including children and teens, can have hematuria..."`; historical activation confirmed via `logs/experiments/phase2/configs/P2B-Simple-CoT-Style.yml:34` (`feedback_style: cot`)
  - why: §0.2 — this is not "teacher sees GT for feedback" (legal), it is "teacher is told to copy GT into the artifact the student will read next round," which is functionally the same violation as the explicit ground-truth-hint prompt, just hidden inside a normal-looking CoT feedback flow
  - fix: seal requirement #3 (template lint) + rewrite/retire `difficult_question`; owner: prompt-engineer, verified by qa-engineer

- **[BLOCKER] Known explicit ground-truth-hint mechanism, off by config only (L1-L5)**
  - evidence: `src/prompts/student.py:118-133`; `config/prompts_config.yml:101-103`; `simplified_teaching_loop.py:358-364, 622-740`; current OFF switches at `config/simplified_config.yml:77` (`enable_last_chance: false`) and `:93` (`trigger_ground_truth: false`)
  - why: §0.2 — code paths remain reachable by config edit alone; not a structural guarantee
  - fix: seal requirement #1 + #4; owner: prompt-engineer/steward (T2.4)

- **[MAJOR] Config comment (line 45-46) does not match the actual active metric weights (line 47-53)**
  - evidence: comment claims `comparison(0.3), semantic(0.2), exact(0.1)`; actual dict (read live) is `comparison_score: 0.35, semantic_sim: 0.25`, `exact_match` commented out entirely — `config/simplified_config.yml:45-53`
  - why: §0.1 honesty — a reader trusting the comment would misreport which metric dominates the score; both happen to sum to 1.0 so the *math* isn't broken, but the *documentation* is
  - fix: correct the comment to match the live weights, or vice versa; owner: data-engineer/steward, low effort

- **[MAJOR] Historical experiment configs hardcode a stale absolute path outside the current repo root**
  - evidence: `logs/experiments/phase6/configs/P6A-NoMemory-Baseline.yml:42-43`, `P6B-WithGroundTruth-Memory.yml:42-43`, `P6C-SameQuestions-PerfectMatch.yml:42-43` all reference `C:\Users\ham25\Desktop\Teaching-light-weight-llm-based-project\...` (missing the `ITA602\` segment present in today's repo path)
  - why: structure.md junk-checklist item ("Hardcoded absolute paths in committed configs") + §0.3 reproducibility — these configs cannot be re-run as committed
  - fix: T2.1's config loader should resolve paths relative to project root, not accept absolute hardcodes (already on the P2 backlog per `todo.md`); no action needed on the immutable historical files themselves
  - owner: ops-engineer/steward (T2.1), no edit to `logs/experiments/` (immutable)

- **[MINOR] `orca_critique`/`principle_critique`/`cot_first_time`/`cot_refinement` teacher templates rely on LLM discipline, not an enforced output filter, to avoid quoting GT in the returned Critique/Improvements text (L9)**
  - evidence: `config/prompts_config.yml:169-336`; extraction logic `src/simplified/teacher_feedback.py:466-490` has no GT-substring check on the parsed `feedback` string before it is returned/stored
  - why: §0.2 residual risk — no confirmed instance found in the logs sampled for this census (unlike L7), but nothing structurally prevents it
  - fix: add the same store-time / prompt-time substring check from seal #1/#2 as a blanket safety net covering *all* feedback styles, not just the known-bad `difficult_question` template; owner: qa-engineer (test), prompt-engineer (templates)

## NOT VERIFIED

- Whether `orca_critique`/`principle_critique`/other non-`difficult_question` templates have ever
  actually echoed GT text into feedback in a real run — I sampled `logs/simplified/debug/*.json`
  broadly via grep for `"Example:"` but did not exhaustively read all ~190 debug files for other
  quoting patterns (e.g. a model spontaneously copying a phrase from the `[Target Answer]` block
  without being asked to). This would need a scripted scan (e.g. fuzzy substring match of GT text
  against every logged `feedback` field across all phases) — recommend as a T2.3 test fixture, not
  hand-verifiable here.
- Whether any config *other than* the phase6 P6B/P6C files points `memory.storage_path` at a
  GT-seeded JSONL in production runs — I checked the phase6 configs specifically (grep hit) but did
  not open every one of the ~15 other phase config files for `storage_path` overrides.
- Runtime behavior of the current codebase end-to-end (I did not execute `simplified_teaching_loop.py`
  myself for this task — it is read-only per the T0.3 spec; all evidence above is either static
  code reading or pre-existing log files I read, not a run I triggered).
- Whether `src/prompts/teacher.py` (referenced in ADR-015 as dead code, 0 importers) contains
  additional leak paths — ADR-015 marks it DEAD (no importers) so it was out of scope for a
  *live-code* census, but flagging for T2.9 demolition to confirm it's truly unreferenced.

## EVIDENCE LOG

Files read in full: `docs/plan/T0.3-leakage-census.md`, `docs/plan/README.md`,
`simplified_teaching_loop.py`, `src/prompts/student.py`, `src/simplified/memory.py`,
`src/simplified/metrics.py`, `src/simplified/teacher_feedback.py`, `src/simplified/student.py`,
`config/simplified_config.yml`, `config/prompts_config.yml`,
`logs/experiments/phase6/configs/{P6A-NoMemory-Baseline,P6B-WithGroundTruth-Memory,P6C-SameQuestions-PerfectMatch}.yml`,
`logs/experiments/phase6/summary.jsonl`.

Files partially read (targeted line ranges/grep context):
`logs/experiments/phase6/gt_memory_store.jsonl` (first 5 records),
`logs/simplified/debug/20251130_024301.json:4418-4462`,
`notebooks/experiment.ipynb` (grep context around ~2871-2876, ~3141-3267, ~3626-3632).

Commands run:
- `Grep "ground_truth|ground truth|gt_memory|reference_answer|reference answer" **/*.py` → 14 files
- `Grep "ground_truth|gt_memory|ground_truth_memory" logs/` → 218 files (mostly per-round debug JSON, expected/benign per L14)
- Targeted `Grep` with content mode + line numbers on: `debug_logger.py`, `prompt_loader.py`,
  `simplified_experiment_runner.py`, `src/eval/metrics.py`, `terminal_ui.py`, `src/eval/reports.py`,
  `tools/dataset/judge.py`, `scripts/compare_students.py`, `scripts/analyze_lhs_strategy.py`,
  `scripts/estimate_cost.py` — confirmed all non-loop hits are docstrings/comments or offline
  (non-student-facing) analysis code
- `Bash wc -l logs/experiments/phase6/gt_memory_store.jsonl logs/experiments/phase6/ground_truth_memory.json` → 32 / 7841 lines
- `Grep "ground_truth_injection|Reference Answer for similar question"` across repo → confirmed
  `notebooks/experiment.ipynb` as the injection source for phase6 artifacts
- `Grep "feedback_style" logs/experiments/**` → confirmed `orca` is the near-universal historical
  choice; `phase2/configs/P2B-Simple-CoT-Style.yml` is the one `cot` exception
- `Grep "Example: " logs/` → found `logs/simplified/debug/20251130_024301.json` and
  `logs/experiments/phase5/P5A-Baseline-Medical100.jsonl`; read the former at the matched line —
  **confirmed real verbatim GT echo in a logged teacher `feedback` field**
