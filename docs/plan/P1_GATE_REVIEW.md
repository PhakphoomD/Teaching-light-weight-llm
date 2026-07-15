# P1 GATE REVIEW — Renovation Blueprint for Hub Sign-off (T1.7)

**Phase:** P1 (docs only) · **Owner:** project-coordinator · **Status:** awaiting user gate ✋
**Purpose:** one document the user (Ham) reviews at the hub to unlock P2. "เซ็นแบบก่อนเทปูน" —
sign the blueprint before we pour concrete. **No P2 (code) task starts until this gate passes.**
Everything below is derived from the P1 outputs; each claim cites the file it came from.

---

## PLAN — what P1 produced (the whole blueprint in one page)

Six blueprint documents + six Proposed ADRs turn ADR-015's renovation order into an executable
P2. The spine is the **six-slot Config Contract**: one run = one YAML = six registry-resolved
slots (A student / B teacher / C preset / D memory / E params+arm / F eval), nothing hardcoded.

| # | Blueprint artifact | Slot / concern | ADR | Source |
|---|---|---|---|---|
| T1.1 | Experiment Config Contract v1 (slots A–F, validation V1–V7, layering) | all six slots | **ADR-016** | `schema.md` §"Experiment Config Contract v1" |
| T1.2 | Target architecture v2 + strangler policy (`src/tlw/` core, 5 seams, registries) | module boundaries | **ADR-017** | `structure.md` v2 |
| T1.3 | Honest memory v2 (notes-not-answers, store-time GT tripwire, arm write-gate) | slot D | **ADR-018** | `schema.md` §"Memory v2 contract" |
| T1.4 | Track-A eval protocol (4 arms, blind correctness judge, C−B with CI, budget) | slot F | **ADR-019** | `docs/plan/EVAL_SPEC.md` |
| T1.5 | Prompt preset registry (42 → 7 survivors, orca teacher, 2 new skeletons) | slot C | **ADR-020** | `docs/plan/PROMPT_CATALOG.md` |
| T1.6 | Crew fitted to renovation (stats→qa-engineer; guard/`.env` fixes; P3 roles deferred) | agents/env | **ADR-021** | `agents.md` + `agents/*.md` |

**The one question Track A answers** (`EVAL_SPEC.md:15-27`): *does an independent teacher's
feedback improve a small student beyond self-retry, measured without ever showing the student
or the scorer the reference answer?* Headline = **pass_rate(C) − pass_rate(B) with a 95% CI**;
a small honest number (+5–10 pp) is success, a suspicious ~100% is failure (ADR-001).

---

## What changes vs today (why this is worth pouring concrete)

| Today (the rotted house) | After P2 (the blueprint) | Fixes |
|---|---|---|
| 843-line monolith `simplified_teaching_loop.py`, run() spans 214–742 (`CODE_MAP.md:25`) | 7 single-responsibility blocks under `src/tlw/`, wired by registries | `structure.md` §C |
| Config drift: weights comment ≠ live dict (`config/simplified_config.yml:45-53`); `pass_threshold` hidden under `teacher:` (`:27`); hardcoded abs paths (`phase6/configs/*.yml:42-43`) | `config/base.yml` single source; thresholds only in slot F; loader resolves paths; fail-loud validation | `schema.md` V1/V3/V5, ADR-016 |
| Score = 70% reference-proximity fused with correctness (`LEAKAGE_CENSUS.md:73-76`) | Two never-merged columns: `correctness` (blind, headline) vs `reference_match` (diagnostic); weights = `{blind_score: 1.0}` | `EVAL_SPEC.md:73-92` |
| Memory stores raw teacher feedback incl. verbatim GT, retrieved unconditionally round 1 → "leaks forward in time" (`LEAKAGE_CENSUS.md` L4/L6, P6C 100%) | Memory stores a bounded `teaching_note` only; store-time GT tripwire makes an answer-key *impossible to write*; fresh per-run store; arms A/B = `none` | `schema.md` §Memory v2, ADR-018 |
| 42 prompts, one confirmed GT-echo leak live in a CoT style (`LEAKAGE_CENSUS.md` L7) | 7 curated presets; `difficult_question` + `last_chance` quarantined, forbidden as registry keys | `PROMPT_CATALOG.md:16-30` |
| 3 P2/P3 competencies unowned; `.claude/` untracked; guard false-blocks `2>&1`; `.env` Write-hole | stats folded into qa-engineer; guard fixes shipped; P3 roles deferred by design | `CLAUDE_ENV_AUDIT.md`, ADR-021 |

---

## STEPS — consistency cross-check (slots ↔ seams ↔ memory ↔ eval ↔ presets)

I cross-read all six P1 outputs against each other. Result: **the blueprint is internally
coherent.** Confirmed alignments and every mismatch (fixed or escalated) below.

**Confirmed consistent (no action):**
- **Slot C ↔ presets.** `schema.md:84` `preset: {student: minimal, teacher: orca}` resolves
  through PromptPreset (`structure.md:112`) to the exact 7 survivor keys in `PROMPT_CATALOG.md:16-30`;
  arm (slot E) picks the variant within a family (arm C → `teacher.orca.blind`, arm D →
  `teacher.orca.sighted`, `PROMPT_CATALOG.md:237-239`). Naming `<role>.<style>.<variant>` locked.
- **Slot D ↔ MemoryBackend seam.** `schema.md` Memory §4 method names (`store`/`retrieve`/
  `update_outcome`/`stats`) match `structure.md:111` §D seam exactly; `type ∈ {none, faiss, rag}`
  identical in both and in the slot-D table (`schema.md:69`).
- **Slot F ↔ eval spec.** `EVAL_SPEC.md:286-308` resolves cleanly into slot F; `mode ∈ {blind,
  gt_comparing}`, `weights: {blind_score: 1.0}` (sum = 1.0, satisfies V1), judge family ≠ student
  family (V2) — all consistent with `schema.md:71,106` and the Judge seam (`structure.md:113`).
- **Leakage seals ↔ specs.** All three specs reference the same `LEAKAGE_CENSUS.md` seal numbers
  for the same fixes (memory §2 tripwire = seal #2; eval §1 = seals #1/#3; V2/V6 = seals #5/#6).

**Mismatches found — FIXED (trivial):** **none.** No typo/naming/broken-cross-reference errors
were found across the six outputs; the registry keys, seam method names, slot enums, and ADR
cross-references all line up. Nothing met the "trivial fix" bar, so no P1 output was edited.

**Mismatches found — ESCALATED (real disagreements — do NOT resolve here):**
- **CONTRA-1 — Memory-on vs memory-off for the headline C/D run.** `schema.md` Memory §5 (T1.3)
  says arms C/D use `memory.type: faiss` (write+read notes), so "C−B isolates the loop+memory
  effect." `EVAL_SPEC.md:52-56` (T1.4) recommends `memory.type: none` for **all** arms in the
  headline (removes cross-question retrieval as a confound), keeping memory-on as a *separate*
  C′/D′ ablation. Both specs flag this and defer to the hub. → **NEEDS-USER-DECISION (c).**
- **CONTRA-2 — a slot-D×arm validation rule that the Config Contract doesn't list.** `schema.md`
  Memory §5 recommends T2.1 fail-loud reject an arm-A/B run configured with `memory.type: faiss`.
  The Config Contract's validation list stops at **V7** (`schema.md:104-111`) and does not include
  this cross-check. Adding it = a new **V8** rule → that is a contract change, escalated, not
  edited in. → **NEEDS-USER-DECISION (e).**

**Intentional differences (NOT contradictions, no fix):**
- The `schema.md:82-92` full example (`qwen2.5:3b` student, `memory: faiss`, Groq-70B judge,
  `pass_threshold: 0.7`) is a *generic* contract illustration showing the 3B product floor; the
  `EVAL_SPEC.md:291-303` example is the *specific* Track-A config (`qwen2.5:7b-instruct`,
  `memory: none`, local Llama judge, `0.75`). Different purpose, both valid — left as-is.
- The GT-seeing diagnostic carries three layer-local names: `eval.mode: gt_comparing` (config) /
  `judge.comparison` (preset) / `reference_match` (metric). Consistent per layer; noted for P2
  authors so the three names aren't mistaken for three things.

---

## STEPS — leakage seal → owning P2 task (every seal has an owner)

Every one of the six `LEAKAGE_CENSUS.md:116-148` seal requirements is owned by a named P2 task.
Seals #5/#6 correctly land in T2.1 (config-load validation), not T2.3/4/5 — noted, consistent
with `schema.md` V2/V6.

| Seal | Requirement | Seals leaks | Owning task(s) | Where specified |
|---|---|---|---|---|
| #1 | No-raw-GT-substring test on every student-bound prompt | L1,L2,L3,L5,L6,L7(student) | **T2.4** build (loop prompts) + **T2.3** test | `EVAL_SPEC.md:66-69`; `structure.md:98,97` |
| #2 | Store-time GT tripwire in `MemoryBackend.store()` | L4,L6,L7(mem),L8,L18 | **T2.5** build + **T2.3** integration test | `schema.md` Memory §2 (`:165-181`) |
| #3 | Teacher-template lint; rewrite/retire `difficult_question` | L7 (template level) | **T2.4** (prompt-engineer rewrite) + **T2.3** test | `PROMPT_CATALOG.md:110,160-174`; `EVAL_SPEC.md:66-69` |
| #4 | Remove config-flag dead paths (`last_chance`/`trigger_ground_truth`), not just default-off | L1–L5 (reachability) | **T2.4** (loop v2 carries no toggleable GT branch) | `structure.md:98` (no GT hint paths) |
| #5 | Judge family ≠ student family, fail-loud at load | family-priors leak | **T2.1** loader (validation **V2**) | `schema.md:106`; todo T2.1 |
| #6 | Historical-artifact quarantine (deny `phase6`/`gt_memory`/`ground_truth` paths) | L18 (seed reuse) | **T2.1** loader (validation **V6**) | `schema.md:110`; §Memory §5 `:217` |

---

## SEQUENCE — suggested P2 spoke chat order

Dependency chain (from `docs/plan/README.md:41` + the seam graph). One task = one fresh chat.

```
T2.1 config loader ──► T2.2 registries ──► T2.3 eval  ┐
                                    └────► T2.5 memory ┴─► T2.4 loop ─► T2.6 runner ─► T2.7 pilot→full ─► T2.8 report ─► T2.9 demolition
```

1. **T2.1** config loader + `base.yml` + validation V1–V7 (+V8 if hub approves) — *ops/steward*.
   First because every block resolves through it; it also lands seals #5/#6.
2. **T2.2** registries (Memory/Preset/Strategy, copy `providers/factory.py`) — *steward*.
3. **T2.3** eval block (blind judge, correctness ≠ reference-match, calibration probe, leakage
   tests) **and** **T2.5** memory block (none/faiss, store-time tripwire) — parallel-safe,
   both depend only on T2.1/T2.2 — *qa+prompt* / *data-engineer*.
4. **T2.4** loop block v2 (arms A/B/C/D as strategies, no GT paths) — *steward+prompt* — needs
   eval + memory seams to exist.
5. **T2.6** runner + 4 arm configs + n=5 dry run — *ops*.
6. **T2.7** pilot (n≈25 train) ✅→ full run (heldout 125 × arms × seeds) — *ops+qa*.
7. **T2.8** analysis + honest report (C−B with 95% CI) — *qa*.
8. **T2.9** demolition (delete DEAD + frozen legacy per CODE_MAP) — *steward+housekeeping* — last.

**Gate-dependent:** the P2 order is fixed, but T2.1 (student model → base.yml), T2.3 (judge
mode/deployment), and T2.4/T2.5 (memory-on/off) **cannot start until decisions (a)–(f) below are
made** — they hardcode the answers into `base.yml` and the arm strategies.

---

## RISKS — register for P2

| # | Risk | Impact | Mitigation (owner) |
|---|---|---|---|
| R1 | **Judge validity ceiling** — a small blind judge only measures correctness as well as its own medical knowledge | headline could be noisy/miscalibrated | §3.3 calibration gates incl. PLAUSIBLE_WRONG + 70B κ≥0.6 before locking; report probe with headline (qa, T2.3) — `EVAL_SPEC.md:351-354` |
| R2 | **Budget infeasibility if hub keeps Groq-70B judge** | ~10 days (100K TPD cap) vs ~3 days | recommend local Llama judge + 70B calibration-only cross-check (decision d) — `EVAL_SPEC.md:262-275` |
| R3 | **Token estimates are planning figures** (~1k teacher, ~650 judge/call) | budget could slip | T2.6 n=5 dry run measures real per-call tokens, re-check before full run (ops) — `EVAL_SPEC.md:360-361` |
| R4 | **Memory-on/off unresolved (CONTRA-1)** | changes what C−B *means*; blocks T2.4/T2.5 | resolve at gate (decision c) before T2.4 starts |
| R5 | ~~`.claude/`, `tools/`, `docs/` untracked in git~~ **RESOLVED 2026-07-13** — committed at hub (`7bf669c`, 82 files) before T1.1 | residual: P1 outputs (schema/structure/ADRs/EVAL_SPEC/PROMPT_CATALOG/gate doc) are tracked-but-uncommitted | user commits the P1 batch at the gate |
| R6 | **`providers.md` model list/limits not re-verified** against Groq console (incl. odd `qwen/qwen3.6-27b`) | budget arithmetic rests on unverified caps | ops-engineer verify before T2.7 budgeting — `CLAUDE_ENV_AUDIT.md:158-159` |
| R7 | **max_rounds = 3 is an assumption** driving teacher budget | a rounds-sweep scales teacher tokens linearly | fixed at 3 for the headline; sweeps are a separate ablation — `EVAL_SPEC.md:357-359` |
| R8 | ~~`.env` Write-hole~~ **RESOLVED 2026-07-13** — T1.6 added `Write(./.env)` + `Write(./.env.*)` + `Edit(./.env.*)` denies (`settings.json:22-25`) | — | closed (ADR-021) |

---

## NEEDS-USER-DECISION (the hub decides these; P2 is blocked on them)

Each has options + a **hub-leaning recommendation**. (a)–(b) are the gate items ADR-015 named;
(c)–(f) surfaced during P1; (g) is the ADR batch.

**(a) Track-A student model** — *blocks T2.1 `base.yml`, and (via §0.2) the judge family.*
- **Opt 1 — `qwen2.5:7b-instruct` (local):** product-relevant; ADR-014 shows it beats Llama-8b
  on proximity, more concise, faster, higher floor. Breaks strict continuity with the ADR-001
  Llama baseline (mitigated: arm A re-establishes a clean baseline anyway).
- **Opt 2 — `llama3.1:8b` (local):** continuity with the ADR-001 baseline the diagnosis rests on;
  but not the product model, slower/weaker here.
- **▶ Recommendation (hub leaning): Opt 1 (Qwen-7B).** Judge then must be **Llama** family (§0.2).
  Source: `EVAL_SPEC.md:314-326`, ADR-014.

**(b) Judge mode** — *blocks T2.3.*
- **Opt 1 — blind only** (judge sees Q + answer, never GT): zero GT in the score path; this is
  the headline correctness pass/fail.
- **Opt 2 — blind primary + a GT-comparing secondary diagnostic** (a second judge that sees GT,
  reported next to `reference_match`, never fed to the student, never the headline).
- **▶ Recommendation (hub leaning): blind is the primary/headline; add the GT-comparing judge
  only if you want the extra diagnostic column and its budget** — else rely on the deterministic
  `reference_match`. Source: `EVAL_SPEC.md:328-337`.

**(c) NEW — headline memory-off vs C/D memory-on (CONTRA-1)** — *blocks T2.4/T2.5.*
- **Opt 1 — memory-off for all arms in the headline** (`EVAL_SPEC.md:52-56`): C−B is a clean
  "teacher feedback vs self-critique" contrast; memory-on becomes a *separate* C′/D′ ablation.
- **Opt 2 — C/D memory-on for the primary run** (`schema.md` Memory §5): C−B measures the
  loop+memory effect together.
- **▶ Recommendation (hub leaning): Opt 1 (memory-off headline).** It removes cross-question
  retrieval as a confound and keeps the pre-registered claim about *teacher feedback* alone;
  memory earns its own ablation. The two specs must reconcile to whichever the hub picks before
  T2.4 starts.

**(d) NEW — judge deployment: local Ollama vs Groq-70B** — *blocks T2.3 budget.*
- **Opt 1 — local Llama-3.1-8b judge** (`EVAL_SPEC.md:262`): free, uncapped, ~3-day total run;
  cross-checked against Groq-70B on the ~60-item calibration probe only.
- **Opt 2 — Groq `llama-3.3-70b` judge** (hub's original leaning): ~975K tokens vs 100K TPD →
  **~10 days**, budget-infeasible at full scope (`EVAL_SPEC.md:263`).
- **▶ Recommendation (hub leaning correction): Opt 1 (local judge) + Groq-70B for calibration
  only.** ADR-011 (n=8) already shows the local judge scores essentially like the 70B (|diff|
  0.10), so the 70B's job shrinks to a one-time audit. This is a budget correction to the hub's
  original Groq-70B leaning — please confirm.

**(e) NEW — memory tripwire acceptance bar + slot-D×arm as V8 (CONTRA-2)** — *blocks T2.1/T2.5.*
- Tripwire thresholds (`schema.md:175-180`): `gt_substring_shingle: 12`, `gt_similarity_max: 0.80`,
  T-3 length/overlap smell. Acceptance test: the phase6 GT corpus (a known answer key) must be
  **rejected 100%** as a red-team fixture (T2.5).
- Slot-D×arm cross-check (arm A/B + `memory.type: faiss` → fail validation) is proposed but not
  in the V1–V7 contract.
- **▶ Recommendation: accept the tripwire thresholds as the T2.5 starting bar (they are
  deliberately strict and calibrated against the phase6 corpus), and adopt the slot-D×arm
  cross-check as Config Contract V8** — it is cheap, structural, and enforces the arm write-gate
  that (c) depends on. Confirm both.

**(f) From T1.5 — student prompt pair** — *affects T2.4.*
- **Opt 1 — `student.minimal.{first,refine}`** (hub-leaning per catalog): matches "minimal
  prompts for small models" + the code's own `DEFAULT_PROMPT_KEYS`; requires T2.4's loop to
  flatten teacher feedback into a single `{feedback}` string. Archives S1/S2.
- **Opt 2 — keep `initial_draft`/`refine_with_teacher` as `student.orca.{first,refine}`:** the
  only student pair with a validated end-to-end Phase-2 run (structured feedback continuity).
- **▶ Recommendation: Opt 1 (minimal pair), and if unresolved at T2.4 start keep BOTH pairs and
  let the C/D pilot (T2.7) decide** — the registry supports it. Source: `PROMPT_CATALOG.md:197-211`.

**(g) ADR batch approval: Proposed → Accepted** — *unlocks P2 entirely.*
- **ADR-016** (Config Contract v1), **ADR-017** (target architecture v2 + strangler), **ADR-018**
  (honest memory v2), **ADR-019** (Track-A eval protocol), **ADR-020** (prompt preset registry),
  **ADR-021** (crew fitted). All six are currently **Proposed** and are the gate items.
- **▶ Recommendation: accept all six as a batch** — they are mutually consistent (verified above)
  and each is the paper spec a P2 task builds against. Note: ADR-019 itself carries sub-decisions
  (a)/(b)/(c) inside it, so accept ADR-019 *conditioned on* the hub's answers to (a)–(d) above.

**Plus — standing audit items to acknowledge (not blocking, but decide/assign):**
- **Git-tracking (R5): already done** — `.claude/`, `docs/plan/`, `docs/audit/`, `tools/`,
  `scripts/*.py`, `data/clean/` committed at the hub (`7bf669c`, 2026-07-13). Residual: commit the
  P1 batch (schema/structure/ADR/EVAL_SPEC/PROMPT_CATALOG/gate doc edits) — **user decides** at the gate.
- **`providers.md` caps unverified (R6)** — assign to ops-engineer before T2.7. (`.env` Write-hole
  R8 already closed by T1.6.)

---

## Housekeeping note for the parent (NOT edited by this task)
- **ADR ordering in `decisions.md` reads slightly out of sequence:** entries run 021 → 020 → 019
  → 018 → **016 → 017** → 015. For strict newest-first it should be **018 → 017 → 016 → 015**
  (017 before 016). Content is fine; only the display order of the two adjacent Proposed ADRs is
  swapped. Flagged for the parent to fix if desired — I did not edit `decisions.md` (out of scope).
- `todo.md` P0/P1 status ticks + the "P2 unlocked-pending-gate" marker are the parent's to apply
  (this task was scoped out of editing `todo.md`/`decisions.md`).

---

## Definition-of-Done (T1.7)
- [x] 1-page blueprint summary + what-changes-vs-today — §PLAN / §What changes
- [x] Consistency cross-check, contradictions listed (0 fixed, 2 escalated + intentional-diffs noted) — §STEPS
- [x] Every leakage seal mapped to an owning P2 task — §STEPS seal table
- [x] NEEDS-USER-DECISION with options + recommendation, incl. mandated (a)–(g) — §NEEDS-USER-DECISION
- [x] P2 risk register — §RISKS
- [x] Suggested P2 spoke order — §SEQUENCE
- [x] Self-contained, readable in <10 min, archetype P
</content>
</invoke>
