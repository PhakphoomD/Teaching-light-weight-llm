# Track-A Evaluation Design Spec (T1.4)

**Phase:** P1 (docs only) · **Owner:** program-architect + qa-engineer · **Status:** Proposed (locks at P1 gate ✋)
**Depends on:** T0.3 (leakage census), T1.1 (config contract §slot F)
**Pre-registered headline:** **loop effect = C − B, reported with a 95% CI.** A small honest number
(+5–10 pp) is success; a suspicious ~100% is failure (ADR-001).

This spec is the complete measurement protocol for the 4-arm ablation (ADR-002). It is
*measurement only* — it does not change code (P1). It tells P2 (T2.3/T2.4/T2.6/T2.7/T2.8)
exactly what to build and run. Every number below is arithmetic you can re-derive from the
cited caps; every integrity rule cites §0 or `LEAKAGE_AUDIT.md`.

---

## 0. The one question

> Does an **independent teacher's feedback** improve a small student **beyond what
> self-retry alone achieves**, measured without ever showing the student or the scorer the
> reference answer?

Everything here exists to make **C − B** defensible. B already contains "try again with your
own critique"; C adds only the teacher's feedback. So **C − B isolates the teacher-feedback
effect** and nothing else. A and D are context: A = the floor (single-pass baseline,
confirmed already-decent in ADR-001), D = the **leakage ceiling** (teacher sees GT) — an
upper bound we print to show how much headroom is *only* reachable by cheating, never a
result we claim as "the loop works."

---

## 1. Arms

All four arms run on the **same held-out set** (125 Diabetes questions) with the **same seed
set**, so every comparison is paired question-by-question. **The student model and the scoring
(judge) path see the ground-truth reference in NO arm** (§0.2). The only thing that varies
across arms is *what feedback the student gets between rounds*.

| Arm | Name | Feedback source between rounds | Teacher sees GT? | Student/judge see GT? | Memory (write) | Role |
|-----|------|--------------------------------|------------------|------------------------|----------------|------|
| **A** | baseline | none — single pass, no loop | — | **No** | none (never writes) | floor |
| **B** | self-refine | the **student critiques its own** previous answer, no teacher | — | **No** | none (never writes) | the control C is measured against |
| **C** | blind-teacher | an independent **teacher** gives feedback **without seeing GT** | No | **No** | notes only (GT-free, per T1.3) | the treatment |
| **D** | sighted-teacher | teacher gives feedback **with GT visible to the teacher** | **Yes (legal §0.2 use)** | **No** | notes only (GT-free) | **leakage ceiling — labeled, not a result** |

Rules that bind every arm:
- **Student is the same model in all arms** (the thing under test). Only the between-round
  feedback differs. Same decoding params, same seeds, same prompts for the answering step.
- **A and B use `memory.type = none`** and never write to any store (T1.3 arm rules;
  seals the L6/Trace-B structural leak class, `LEAKAGE_AUDIT.md:164-167`, by construction).
- **C and D** may write teacher **notes** (never GT) if T1.3's memory design is on; those
  notes are subject to the store-time GT tripwire (seal #2, `LEAKAGE_AUDIT.md:124-126`,
  built in T2.5). **Eval position (recommended headline):** run the headline C−B with
  `memory.type = none` for **all** arms so feedback lives only in-context within a question's
  rounds — this removes cross-question memory-retrieval as a confound and keeps C−B a clean
  "teacher feedback vs self-critique" contrast. Memory-on (C′/D′) is a **separate ablation**,
  not the headline. *(If T1.3 mandates C/D memory-on for the primary run, flag to hub — the
  two specs must reconcile before P2; this spec's headline stays memory-off.)*
- **D is always printed with the literal label "leakage ceiling (teacher saw GT — upper
  bound, not a claimed result)."** It exists to quantify how much of any gain is only
  reachable by cheating. If C ≈ D, the honest loop already captures most of the achievable
  lift; if D ≫ C, the headroom is mostly cheating-only. Either way D is context, never headline.

**Round structure.** A = 1 pass. B/C/D = up to `max_rounds = 3` (answer → feedback → answer →
feedback → answer). Feedback each round is carried **in-context** into the next student prompt
(round-to-round), which is *not* a leak as long as the feedback text is GT-free — that GT-free
guarantee is enforced by seal #1 (no-raw-GT-substring test on every student-bound prompt,
`LEAKAGE_AUDIT.md:118-123`) and seal #3 (teacher-template lint, `:127-133`). Arm D's teacher
*sees* GT to reason, but its returned feedback string must still pass the same GT-substring
gate before it reaches the student — otherwise D degenerates into the explicit
ground-truth-hint cheat (L1/L7) rather than a clean "teacher-informed-by-GT" ceiling.

---

## 2. Two metrics — computed side by side, NEVER merged

The core error in ADR-001 was folding "is it correct?" and "does it look like the reference?"
into one hybrid score that was **70% reference-proximity** (`comparison 0.35 + semantic 0.25 +
rouge 0.10`, reproduced from live config in `LEAKAGE_AUDIT.md:50-76`). Track-A keeps them in
**separate columns** and lets only the first decide pass/fail.

| Metric | What it is | Sees GT? | Decides pass/fail? | Reported as |
|--------|-----------|----------|--------------------|-------------|
| **`correctness`** | blind LLM-judge verdict on (Q, answer) → integer 0–4 → **PASS iff ≥ 3** | **No** | **YES — this is the headline** | pass-rate per arm; C−B with 95% CI |
| **`reference_match`** | MiniLM cosine + ROUGE-L of answer vs the reference | Yes (score-path, legal L10–L12) | **No — diagnostic only** | mean per arm, alongside correctness, never added to it |

- **`correctness`** is the pass-rate that drives C−B. Nothing GT-derived enters it.
- **`reference_match`** is kept *only* to expose the old confound: if an arm raises
  `reference_match` but not `correctness`, it is learning to *mimic the reference wording*,
  not to be *more correct*. Reporting both side by side is the honesty check (§0.1).
- **No weighted fusion of the two.** Slot F's `metrics.weights` (schema.md:87-92) carries
  **`{ blind_score: 1.0 }`** — the weighted `final_score` *is* the blind correctness score and
  nothing else (satisfies validation V1, sum = 1.0). `reference_match` is computed and logged
  outside the weighted score, as a diagnostic field on each per-round record.

---

## 3. Judge design

### 3.1 Constraints (all mandatory)
1. **Family ≠ student family** (§0.2; schema V2, `schema.md:106`). If student = Qwen → judge =
   Llama; if student = Llama → judge = Qwen. Enforced fail-loud at config load (T2.1).
2. **Judge ≠ teacher model** where feasible — the scorer should not be the same instance that
   generated the feedback it is grading. (Teacher family itself is unconstrained, §0.2.)
3. **Blind — the judge prompt contains Q + answer only, never the reference.** This is the
   default `QUALITY_PROMPT` posture already in `tools/dataset/judge.py:24-33` (scores blind,
   temperature 0). Track-A extends it from a 0–1 quality float to a 0–4 correctness verdict.
4. **Deterministic:** temperature = 0, fixed `max_tokens`, first-integer parse
   (mirrors `_parse_score`, `tools/dataset/judge.py:35-47`).

### 3.2 Rubric prompt (draft — blind correctness, 0–4)

```
You are a strict medical-QA evaluator. Judge the ANSWER to the QUESTION on its own merits.
You are NOT given a reference answer — judge correctness from your own medical knowledge.

QUESTION: {q}
ANSWER:   {a}

Score 0-4 on this scale:
  4 = fully correct AND complete: directly answers THIS question, medically accurate,
      nothing misleading, no important omissions.
  3 = correct and useful: right and on-topic, minor gaps or minor imprecision only.
  2 = partially correct: addresses the question but has a notable gap or a minor error.
  1 = mostly wrong / off-topic: touches the topic but misleading, incomplete, or largely
      incorrect.
  0 = wrong, irrelevant, empty, or harmful.

Output STRICT JSON on one line: {"score": <0-4 integer>, "reason": "<=12 words"}
```

- **Parse rule:** extract `score` (first integer 0–4 if JSON parse fails — reuse the
  `_NUM`/clamp fallback of `judge.py:35-47`). Missing/unparseable → record as `null`, exclude
  from pass-rate denominator, and **report the null-rate** (a high null-rate invalidates the
  run — must be <2%).
- **Pass threshold: score ≥ 3** ⇒ PASS. Chosen so "partially correct with a notable gap"
  (score 2) does **not** pass — the bar is "correct and useful," not "on-topic." The threshold
  is a slot-F value (`eval.pass_threshold`), not hardcoded, so it can be re-tuned from the
  calibration probe before locking.
- **Scale = 0–4 (not 0–1 float):** an integer rubric with worded anchors is more reproducible
  across calls than a continuous float and gives a crisp pass boundary; the existing 0–1 float
  judge is kept only for the dataset-quality D4 use, not for Track-A pass/fail.

### 3.3 Calibration probe (gate the judge BEFORE the real run)

Extends the honest, label-free method already in `scripts/calibration/compare_judges.py:1-14` (build
candidates whose quality ordering we *know*, no human labels). **Built and run on the TRAIN
split (506 recs) or the clean pool excluding heldout — NEVER on the 125 held-out questions**
(§0.2; do not contaminate the measurement set). Candidate classes per question:

| Class | Construction | Expected verdict |
|-------|--------------|------------------|
| `GOOD` | the real cleaned answer | PASS (score 3–4) |
| `WRONG` | a fluent answer from a *different* question (`compare_judges.py:41-45`) | FAIL (0–1) |
| `TRUNCATED` | first ~12 words of the real answer (`:44`) | FAIL / borderline (0–2) |
| `PLAUSIBLE_WRONG` *(new)* | real answer with one clinically-material fact negated/altered | FAIL (0–2) — the hardest, tests real discrimination not just fluency |

**Acceptance gates before the judge is locked (n ≥ 40 questions × 4 classes):**
- GOOD pass-rate **≥ 0.80**; WRONG pass-rate **≤ 0.15**; PLAUSIBLE_WRONG pass-rate **≤ 0.30**.
- Discrimination `mean(GOOD) − mean(WRONG) ≥ +0.6` on the 0–4 scale normalized (parallels
  ADR-011's GOOD−WRONG +0.68/+0.70 finding for the 0–1 judges).
- **Inter-judge agreement** between the chosen judge and a Groq Llama-3.3-70B cross-check on
  the same probe: Cohen's κ on PASS/FAIL **≥ 0.6**. ADR-011 (n=8) already showed local
  Qwen-7B and Groq-70B judge nearly identically (|diff| 0.10); this re-confirms it at n≥40 on
  the *correctness* rubric before we rely on it.
- If any gate fails → tune threshold / rubric wording, re-run the probe. The probe is cheap
  (see budget) and is the single thing standing between us and another inflated number.

---

## 4. Determinism & statistics

### 4.1 Seeds & temperature policy
- **Seeds: 3** — `{13, 42, 123}` (logged; `params.seed` is mandatory per schema V4,
  `schema.md:108`). Three is the minimum that gives a spread; more seeds cost only local
  student time (§4.4), so 5 is a stretch option if wall-clock allows.
- **Temperature policy (isolate stochasticity to the student under test):**
  - **Student answering: 0.3** — low but non-zero, so different seeds produce genuinely
    different runs and we capture real generation variance (temp 0 would make all 3 seeds
    identical and collapse the seed dimension).
  - **Teacher feedback: 0.0** — deterministic feedback, so C/D differ from B *only* because of
    feedback content, not feedback noise.
  - **Judge: 0.0** — deterministic scoring (as `judge.py` already does).
- All decoding params + the fully-merged resolved config are recorded into `summary.jsonl`'s
  `config_used{}` (schema.md:101) so every number is reproducible from its exact config (§0.3/§0.4).

### 4.2 CI method for the headline — recommendation: **paired cluster bootstrap over questions**
The headline is a **difference of two paired proportions** (arm C vs arm B on the *same* 125
questions). Recommendation and justification:

- **Primary — paired cluster bootstrap over questions.** Resample the 125 questions with
  replacement (the cluster = a question, carrying its per-arm PASS/FAIL and, if seeds vary,
  its seed replicates); recompute `pass_rate(C) − pass_rate(B)` on each resample;
  95% CI = the 2.5/97.5 percentiles over ≥10,000 resamples. **Why over Wilson:** Wilson is a
  *single-proportion* interval — it ignores the pairing, so it would over-state the CI width
  of a *difference* measured on the same items. Bootstrapping the question-level pairs uses the
  positive within-question correlation between arms (a question B gets right, C usually also
  gets right), which is exactly the variance-reduction the paired design buys us.
- **Companion significance — McNemar's test** on the B-vs-C discordant pairs (b = B-pass/C-fail,
  c = B-fail/C-pass), reported as a p-value beside the bootstrap CI. Bootstrap gives the effect
  *size* CI (what we pre-registered); McNemar gives the paired *significance* — both, not either.
- **Secondary/descriptive — Wilson score interval** per arm for the raw pass-rate of A, B, C, D
  individually (Wilson is the right tool for a *single* proportion and behaves well at the small
  n=125 and near 0/1). These are descriptive per-arm bars, not the headline.
- **Across seeds:** pool the 3 seeds into the bootstrap (question is the cluster; seed
  replicates ride inside the cluster), and *also* report mean ± spread of C−B across the 3
  seeds as a robustness check. If the seed spread is large relative to the bootstrap CI, report
  that honestly — it means the effect is generation-sensitive.

### 4.3 Pre-registered claim (frozen before the run)
> **Track-A loop effect = pass_rate(C) − pass_rate(B), reported with a 95% paired-bootstrap
> CI over the 125 held-out questions, pooled across 3 seeds; McNemar p-value alongside; A =
> baseline floor, D = leakage ceiling (labeled, not a result).**

Pre-registering this *before* looking at heldout results is what stops post-hoc metric-shopping
(the ADR-001 failure mode). The metric, threshold, arms, seeds, and CI method above are the
registration. `reference_match` is reported but is **not** the claim.

### 4.4 Held-out set — do not touch
- Measurement set = `data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl`,
  **125 records** (verified: `Grep -c "question"` → 125). Train = `..._train.jsonl`,
  **506 records** (verified → 506). Calibration/probe work uses the **train** split only;
  the heldout 125 are read by the loop at run time and by the judge/reference-match scorer —
  never edited, never inspected by hand, never used for probe construction (§0.2; T1.4 Must-NOT).

---

## 5. API budget (arithmetic against Groq daily caps)

**Design that minimizes cloud spend:** the **student runs locally** (Ollama, free — §5.1), so
only the **teacher** (arms C/D) and possibly the **judge** hit Groq. Caps from `providers.md`:

| Groq model | RPM | RPD | TPM | TPD | Track-A use |
|---|---|---|---|---|---|
| `llama-3.3-70b-versatile` | 30 | **1K** | 12K | **100K** | judge (option J2) / calibration cross-check |
| `qwen/qwen3-32b` | 60 | **1K** | 6K | **500K** | teacher (recommended) |
| `llama-3.1-8b-instant` | 30 | **14.4K** | 6K | **500K** | judge (option J3, family≠Qwen) |

### 5.1 Student (LOCAL Ollama — $0, wall-clock only)
Generations per question (rounds): A=1, B=3, C=3, D=3 → **10 / question / seed**.
`10 × 125 × 3 seeds = 3,750` local generations. At ~5 s/gen (ADR-014: Qwen-7B ≈ 4.8 s/q)
≈ **5.2 h** of local GPU time. No Groq cap applies. (Llama-8b student ≈ 8.3 s/q → ~8.6 h.)

### 5.2 Teacher (Groq, arms C + D only)
`calls = Q × 2 arms × S × (max_rounds−1) = 125 × 2 × 3 × 2 = ` **1,500 calls.**
Tokens/call ≈ 1,000 (Q + student answer + feedback prompt; arm D adds GT to the *teacher's*
input, ~1,200) → **≈ 1.5M tokens** total.

| Teacher model | requests vs RPD | tokens vs TPD | wall-clock (binding cap) |
|---|---|---|---|
| **`qwen3-32b`** (recommended) | 1,500 / 1,000 = **2 days** | 1.5M / 500K = **3 days** | **~3 days** |
| `llama-3.1-8b-instant` | 1,500 / 14.4K = <1 day | 1.5M / 500K = 3 days | ~3 days (weaker feedback → smaller, still-honest C−B) |
| `llama-3.3-70b` | 1,500 / 1,000 = 2 days | **1.5M / 100K = 15 days** ✗ | infeasible — 70B TPD too small for teacher volume |

→ **Teacher = Groq `qwen3-32b`** (biggest model that fits the volume; teacher family is
unconstrained by §0.2, and it is ≠ the Llama judge, satisfying "judge ≠ teacher").

### 5.3 Judge (correctness, 1 call / question / arm / seed)
`calls = Q × 4 arms × S = 125 × 4 × 3 = ` **1,500 calls.** Tokens/call ≈ 650 (rubric + Q +
answer + short JSON) → **≈ 975K tokens** total.

| Judge option | fits family rule? | requests vs cap | tokens vs cap | wall-clock |
|---|---|---|---|---|
| **J1 — LOCAL Ollama `llama3.1:8b`** *(recommended)* | ✓ (Llama ≠ Qwen student) | no cap | no cap | ~1.3 h local, **$0** |
| J2 — Groq `llama-3.3-70b` *(hub leaning)* | ✓ | 1,500 / 1K = 2 days | **975K / 100K = ~10 days** ✗ | **budget-infeasible at full scope** |
| J3 — Groq `llama-3.1-8b-instant` | ✓ | 1,500 / 14.4K <1 day | 975K / 500K = 2 days | ~2 days |

- **J2 (the hub's current leaning) is the tight one:** Groq-70B's 100K TPD makes a full 1,500-call
  judge pass take ~10 days. Mitigations if the hub still wants a 70B judge: (i) judge only 1 seed
  on 70B (500 calls, 325K tok → ~4 days) and use the local judge for the other seeds, or
  (ii) subsample. Neither is as clean as J1.
- **Recommended: J1 — local Llama-3.1-8b judge** (free, uncapped, private), **cross-checked
  against Groq-70B on the ~60-item calibration probe only** (60 × 650 ≈ 39K tok < 100K TPD →
  <1 day, well inside caps). ADR-011 evidence (n=8: local judge GOOD−WRONG +0.68 vs 70B +0.70,
  |diff| 0.10) says a small local judge scores essentially like the 70B — so the 70B's role
  shrinks to a one-time calibration audit, not the per-answer scorer. This removes the judge
  from the critical Groq budget entirely.

### 5.4 Multi-day schedule (recommended config: local student, `qwen3-32b` teacher, local judge)
- **Only the teacher touches Groq** → ~**3 days** (qwen3-32b TPD-bound), spread as ~500K
  teacher-tokens/day. Run arms C and D across 3 days; A and B (no teacher) plus all judging and
  all student generation run locally and can overlap on day 1.
- Total honest end-to-end ≈ **3 days**, dominated by the teacher's Groq token cap, not compute.
- If the hub picks J2 (Groq-70B judge), add ~7–10 days for judging or apply a J2 mitigation.

---

## 6. Slot-F config fit (schema.md §Config Contract v1)

The eval block above resolves cleanly into slot F (`schema.md:71`, example `:87-92`). Blind
headline config for arm C, Qwen student, local Llama judge:

```yaml
# experiments/trackA_p2_armC_diabetes.yml  (diffs from config/base.yml)
student: { provider: local, model: qwen2.5:7b-instruct, temperature: 0.3 }   # A — under test
teacher: { provider: groq,  model: qwen/qwen3-32b, temperature: 0.0 }         # B — feedback gen (may see GT in arm D)
memory:  { type: none }                                                       # D — headline = memory-off (see §1)
params:  { arm: C, max_rounds: 3, seed: 42 }                                  # E — seed mandatory (V4)
eval:                                                                          # F — thresholds live HERE (V5)
  judge: { provider: local, model: llama3.1:8b }   # Llama judge ≠ Qwen student family (V2, §0.2)
  mode: blind                                       # judge never sees GT
  pass_threshold: 0.75                              # normalized 0-4→0-1 boundary = score ≥3 (0.75)
  metrics:
    weights: { blind_score: 1.0 }                   # correctness only; reference_match is diagnostic (V1 sum=1.0)
```

Validation this satisfies: **V1** weights sum to 1.0; **V2** judge family (Llama) ≠ student
(Qwen); **V4** seed present; **V5** threshold under `eval`, not `teacher`; **V7** `mode ∈
{blind, gt_comparing}`, `arm ∈ {A,B,C,D}`. Arm A/B files set `arm: A|B` and drop `teacher`
usage; arm D sets `arm: D` (teacher sees GT for feedback, still `mode: blind` for the judge).

---

## 7. NEEDS-USER-DECISION (framed for the P1 gate — NOT decided here)

### (a) Track-A student model
| Option | For | Against |
|---|---|---|
| **`qwen2.5:7b-instruct` (local)** — *hub leaning* | product-relevant (ADR-014: beats Llama-8b on proximity, more concise, faster, higher floor); Track A directly informs the Track-B product | breaks strict continuity with the ADR-001 Llama baseline (mitigated: A-arm re-establishes a clean baseline anyway) |
| **`llama3.1:8b` (local)** | continuity with the ADR-001 baseline the whole diagnosis rests on | not the product model; ADR-014 shows it slower and weaker for this domain |
- **Judge follows from this (§0.2 family rule):** Qwen student → **Llama judge**; Llama student
  → **Qwen judge**. Recommended judge deployment either way = **local** (free, uncapped;
  §5.3 J1), with a Groq big-model calibration cross-check.
- **Recommendation to carry to the gate:** student = **`qwen2.5:7b-instruct` local**, judge =
  **local `llama3.1:8b`** (+ Groq-70B calibration audit). *(Hub's stated leaning was Qwen +
  Groq Llama-70B judge; §5.3 shows the Groq-70B judge is ~10× over the daily token cap at full
  scope, so this spec recommends the **local** Llama judge and demotes Groq-70B to
  calibration-only — a budget correction for the hub to confirm.)*

### (b) Judge mode — blind vs GT-comparing
| Option | Role |
|---|---|
| **Blind (judge sees Q + answer only)** — *hub leaning, recommended primary* | zero GT in the score path → measures *correctness*, not reference-match; this is the headline pass/fail |
| **GT-comparing-but-independent (a second judge that sees GT)** | **secondary diagnostic column only** — maps to the legal score-path L10 (`LEAKAGE_AUDIT.md:38`); reported next to `reference_match`, never fed back to the student, never the headline |
- **Recommendation:** **blind is the primary/headline** correctness judge; a GT-comparing
  independent judge may be added purely as a diagnostic column (alongside `reference_match`) to
  show how blind-correctness and reference-agreement diverge. It must never enter the pass/fail
  decision or any student-bound prompt. Confirm at the gate whether to spend the extra budget on
  the secondary GT-comparing judge or rely on the deterministic `reference_match` metrics alone.

---

## 8. Definition-of-Done check (T1.4)
- [x] Arms table (A/B/C/D, same heldout + seeds, student/judge GT-blind in all arms, memory per arm) — §1
- [x] Two metrics defined and never merged (correctness headline / reference_match diagnostic) — §2
- [x] Judge design: family rule, blind, rubric prompt draft, 0–4 scale, parse rules, calibration probe — §3
- [x] Determinism & stats: 3 seeds, temperature policy, CI method chosen+justified (paired bootstrap), pre-registered C−B claim — §4
- [x] Budget: calls/tokens per arm×seed×125×rounds vs Groq caps, model choices, multi-day schedule, arithmetic shown — §5
- [x] Slot-F config fit (schema V1–V7) — §6
- [x] NEEDS-USER-DECISION framed, not resolved — §7

## 9. Open risks / not-done
- **T1.3 reconciliation:** §1 recommends memory-off for the headline C−B; if T1.3's arm rules
  mandate C/D memory-on for the primary run, the hub must pick which is the headline (this spec
  keeps memory-on as a separate C′/D′ ablation). Flagged, not resolved.
- **Judge validity ceiling:** a small blind judge can only measure correctness as well as its
  own medical knowledge allows. The §3.3 calibration gates (incl. PLAUSIBLE_WRONG and 70B
  κ-agreement) bound this risk but do not eliminate it; report the probe results with the headline.
- **max_rounds = 3 is an assumption** driving the teacher budget (§5.2). If the hub wants
  `max_rounds` sweeps, teacher tokens scale linearly (each extra round ≈ +750K teacher tokens →
  +~1.5 days on qwen3-32b). Fixed at 3 for the headline.
- Token-per-call estimates (~1,000 teacher, ~650 judge) are planning figures; T2.6's n=5 dry
  run should measure the real per-call token counts and the budget re-checked before the full run.
```
