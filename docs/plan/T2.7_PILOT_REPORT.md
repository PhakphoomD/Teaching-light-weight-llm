# T2.7 Pilot Report — Track-A ablation (n=25 train, 4 arms, seed 42)

**Date:** 2026-07-14 · **Owner:** qa-engineer (spoke) + main thread (completion after session-limit interruption)
**Scope:** pilot only (steps 1–4 of T2.7). The full run is NOT started (blocked — see VERDICT).

---

## VERDICT: **NO-GO for the full run as currently configured**

The pilot did its job: it exposed a **degenerate ablation** cheaply, before spending the
held-out budget. The runner mechanics are solid (0 errors over 100 questions), but with the
current judge + student + pass-threshold the four arms are **mechanically identical** — every
answer passes on round 1, so the teaching loop never engages and **C−B = B−A = D−C = 0 by
construction**. Running the full 125×3×4 would burn ~16 h of compute to produce a guaranteed
zero effect. The fix is the **same judge-lock decision already escalated to the hub** (T2.3,
ADR-022(d) both-fail branch) — see FINDINGS.

---

## Measured numbers (all four pilot arms, n=25 train, seed 42)

| Arm | pass_rate | judge score dist (0–4) | avg_rounds | teacher_calls | memory_used | errors | elapsed |
|---|---|---|---|---|---|---|---|
| A baseline | 25/25 = 1.000 | {3: 5, 4: 20} | 1.00 | 0 | 0 | 0 | 952 s |
| B self-refine | 25/25 = 1.000 | {3: 7, 4: 18} | 1.00 | 0 | 0 | 0 | 872 s |
| C blind-teacher | 25/25 = 1.000 | {3: 7, 4: 18} | 1.00 | 0 | 0 | 0 | 1155 s |
| D sighted-teacher | 25/25 = 1.000 | {3: 7, 4: 18} | 1.00 | 0 | 0 | 0 | 997 s |

Run dirs: `runs/trackA_p2_arm{A,B,C,D}_diabetes__seed42__20260713T1518..T1611Z/`.

**Latency (first real at-scale measurement):** student ≈ **19 s/call**, judge ≈ **19 s/call**
(both local Ollama, run sequentially → GPU contention; ~2× the dry-run's 10.4/9.1 s and ADR-014's
4.8 s/q planning figure). **Teacher (Groq) latency/token: still UNMEASURED** — arm C/D never
called it (same gap as the dry run, now confirmed unavoidable while the loop stays degenerate).

**Token spend (local, free):** student ≈ 5.5 k tok/arm, judge ≈ 9.8 k tok/arm. **Groq spend = 0**
(teacher never invoked). No daily-cap pressure at pilot scale.

---

## FINDINGS

### BLOCKER-1 — The ablation is degenerate: the judge passes everything at round 1
The blind judge (`llama3.1:8b`, PASS at `score ≥ 3` on 0–4) scored **every** first-round answer
a 3 or 4 across all 100 questions — **never a 0/1/2**. Consequences, all structural:
- Arm A (single unrefined student attempt) already passes **100%**.
- The loop is `while not passed: refine` — so if round 1 passes, **arms B/C/D never reach round
  2**. Self-refinement (B) and teacher feedback (C/D) are never exercised (`teacher_calls = 0`,
  `avg_rounds = 1.00` everywhere).
- Therefore the headline **C − B ≡ 0**, and B−A, D−C ≡ 0 too — not as a result, but because no
  arm's distinguishing machinery ever ran.

**Two coupled root causes, both feeding the open judge-lock decision:**
1. **Judge leniency** — this is the same weakness T2.3's calibration caught (PLAUSIBLE_WRONG
   pass-rate 0.92–0.95, κ 0.35–0.41), now shown to be worse in practice: the judge does not even
   separate a plain baseline answer from anything, because it passes all of them.
2. **No headroom** — `qwen2.5:7b-instruct` already answers these Diabetes questions well enough
   to clear `score ≥ 3` on the first try. Even a *perfect* judge would show a small loop effect
   only if the student sometimes fails round 1. On this domain/threshold it essentially never does.

### MAJOR-1 — gate (f) minimal-vs-orca cannot be decided at pilot
Both student presets would pass ~100% at round 1 under this judge, so pass-rate can't
discriminate them. The `orca_student` comparison run specified in the task was **not executed** —
it would cost ~16 min of compute to produce another 1.000. Deferred until the judge/threshold is
fixed (then re-decide on a sample that actually has failures). *(Preset was also not added — see
NOT DONE.)*

### MINOR-1 — student/judge latency ~2× the planning estimate
At ~19 s/call each, run sequentially, a full 125×3-seed×4-arm run of **round-1-only** work is
≈ 125×3×4×(19+19) ≈ **16 h** of local compute (Groq 0 while degenerate). If the judge is fixed
and answers start failing round 1, add teacher rounds on top. The EVAL_SPEC §5 schedule should be
re-projected from these measured numbers, not the 4.8 s/q figure.

---

## Integrity checks (T2.7 step 5) — all green

- Row counts: each `rounds.jsonl` = 25 records, each `summary.jsonl` = 1 line. ✅
- No duplicate `question_id` within a run. ✅
- `seed = 42` recorded in every summary + round record. ✅
- `config_used` snapshot present in every run dir (`config_used.json`). ✅
- `run_id` encodes arm + `memory_type=none` (headline vs C′/D′ can't be conflated, V8). ✅
- `errors = 0` for student and judge across all 4 arms (100 questions). ✅
- Preflight: train = 506 rows, heldout = 125 rows (counts only, no heldout content read, §0.2). ✅

## Leakage spot-check (arm D)

- Max 12-gram verbatim overlap between any arm-D student answer and its reference = **0**. ✅
- `teacher_called = False` and `feedback = None` for all 25 arm-D rounds → the sighted-teacher
  GT path was **never exercised** in this pilot. The arm-D leakage seal is therefore **NOT
  VERIFIED empirically here** (it is covered structurally by T2.4's mock test
  `test_arm_d_gt_reaches_only_the_teacher_bound_prompt`). It can only be exercised live once some
  round actually fails round 1 — i.e. after the judge fix.
- No `memory_rejects.jsonl` written anywhere (headline `memory.type=none`, nothing to store). ✅

---

## NOT VERIFIED (pilot could not reach these)

- Teacher (Groq `qwen/qwen3-32b`) feedback quality, latency, and token cost — never invoked.
- Arm B self-critique behaviour — never invoked (round 1 always passed).
- Arm D live leakage seal — GT path never activated (structurally covered by T2.4 tests only).
- Memory write/tripwire in a live run — headline is memory-off; untested here (T2.5 unit tests
  cover it; the C′/D′ ablation would exercise it).

---

## Recommendation to the hub (one coupled decision)

The full run should **not** proceed until the **judge-lock** question is resolved, because the
pilot proves the ablation produces a guaranteed **zero** with the current judge+threshold+student.
Resolving the judge is necessary but may not be sufficient — the **no-headroom** problem
(BLOCKER-1 cause 2) means even a good judge may show a near-zero effect on this domain. Options
for the hub, in rough order of leverage:

1. **Raise the bar so the baseline can fail.** Move `pass_threshold` to `score ≥ 4` (strict
   "correct AND complete") and/or adopt a stronger judge (EVAL_SPEC §5.3 J2 Groq-70B for the
   small held-out set, ~budgeted days) so round-1 answers don't all pass. This is the most direct
   fix for the degeneracy and folds the judge-lock decision in.
2. **Harder questions / harder domain slice** — pick held-out questions where the 7B student
   genuinely struggles, so the loop has room to help. Risks §0.2 peeking if done by inspecting
   held-out content; would need a principled (difficulty-by-length or by-source) rule set on the
   *train* split.
3. **Accept a documented null result** — if the honest finding is "on this domain a 7B student
   already answers well enough that independent teacher feedback adds ~0," that is itself a
   legitimate §0.1 result for Track A, and P3 planning proceeds on "loop = marginal here, lean on
   RAG/LoRA." But this should be a *deliberate* choice, not a side effect of a lenient judge.

My read: do **(1)** — it simultaneously answers the judge-lock (stronger/strict judge) and
restores ablation headroom, and it's the cheapest path to a *meaningful* C−B (positive, zero, or
negative — all honest).

---

## EVIDENCE LOG

- Score/timing/integrity numbers: computed live from `runs/trackA_p2_arm{A,B,C,D}_diabetes__seed42__*/`
  `summary.jsonl` + `rounds.jsonl` (see commands in the session transcript, 2026-07-14).
- Judge score distribution (`score` field, 0–4): A={3:5,4:20}, B/C/D={3:7,4:18}.
- Latency: student/judge `_calls` dicts in each `summary.jsonl` (`seconds`/`calls`).
- Leakage spot-check: 12-gram overlap of arm-D answers vs train references = 0.
- Calibration context: `runs/calibration/probe_seed42_n40_*.json`,
  `runs/calibration/probe_fallback_8binstant_seed42_n40_*.json` (T2.3).
- Preflight counts: `wc -l` train=506, heldout=125.
