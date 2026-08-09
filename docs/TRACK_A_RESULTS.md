# Track-A Results — Does an iterative teaching loop actually help a small LLM?

**Status:** Complete (full pre-registered run, 2026-07-15) · **Owner:** qa-engineer + main thread
**One-line verdict:** The loop helps — but the benefit comes from the student **re-attempting its
own answer (self-refinement)**, not from an independent **teacher**. Teacher feedback adds
**nothing measurable** over plain self-refinement (**C − B = +0.3%, 95% CI [−2.1%, +2.9%],
McNemar p = 1.00**), while self-refinement itself is a real, significant gain over the baseline
(**B − A = +9.1%, 95% CI [+5.1%, +13.3%], p < 0.0001**).

---

## 1. Method (see `docs/protocol/2026-07-13-teaching-loop-protocol.md` for the pre-registered protocol)

Four arms, same held-out set, same seeds, honest-by-construction (no ground truth on the
student/judge path — §0.2, enforced structurally by `src/tlw/loop/core.py::assert_gt_free`):

| Arm | Between-round feedback | Teacher sees GT? | Role |
|---|---|---|---|
| **A** baseline | none (single answer) | — | the floor |
| **B** self-refine | student critiques its own answer | no | loop without a teacher |
| **C** blind-teacher | teacher feedback, teacher does NOT see GT | no | **the headline treatment** |
| **D** sighted-teacher | teacher feedback, teacher DOES see GT | yes | leakage ceiling (not a result) |

- **Student** = `qwen2.5:3b` (local, product floor per ADR-015). Chosen because a stronger 7B
  already answered these questions correctly on the first try (100% at the score≥3 bar) — no
  room for any loop to help. See §5 (headroom).
- **Judge** = Groq `llama-3.1-8b-instant`, **blind** (question + answer only, never the
  reference), integer 0–4 correctness verdict, **PASS iff score ≥ 4** ("correct AND complete").
  Family Llama ≠ Qwen student (§0.2, contract V2). Temperature 0. 100% of 1,656 judge calls ran
  on Groq (0 fallbacks) → a single, consistent judge across the whole run.
- **Data** = 125 held-out Diabetes questions (`data/clean/…_heldout.jsonl`), **3 seeds
  {13, 42, 123}**, students at temperature 0.3 so seeds are genuinely different runs.
- **Headline stat** (pre-registered, teaching-loop-protocol §4): pass-rate difference **C − B** with a 95%
  **paired cluster-bootstrap** CI (cluster = question, 3 seeds pooled, 10,000 resamples), exact
  McNemar alongside, Wilson per-arm descriptive. Correctness and reference-match are **never
  merged** (ADR-019).

---

## 2. Headline result

| Comparison | Estimate | 95% CI (paired cluster bootstrap) | McNemar | Reading |
|---|---|---|---|---|
| **C − B** (teacher vs self-refine) | **+0.003** | **[−0.021, +0.029]** | b=16, c=15, **p=1.00** | **No effect.** An independent teacher adds nothing over self-retry. |
| **B − A** (self-refine vs baseline) | **+0.091** | **[+0.051, +0.133]** | b=43, c=9, **p<0.0001** | **Real, significant.** Self-refinement genuinely helps. |

The headline **C − B** confidence interval is tight and straddles zero; McNemar p = 1.00
(16 questions C won that B lost, 15 the reverse — a wash). The teaching loop's value is **entirely
in the student re-working its own answer**, not in the external teacher.

---

## 3. Full table (per-arm, blind correctness pass-rate)

Pooled over 3 seeds (n = 375 question-runs per arm; arm D = 250, one run aborted — see §6):

| Arm | Pass-rate | Wilson 95% CI | seed 13 | seed 42 | seed 123 |
|---|---|---|---|---|---|
| A baseline | **0.821** | [0.779, 0.857] | 0.832 | 0.864 | 0.768 |
| B self-refine | **0.912** | [0.879, 0.937] | 0.944 | 0.952 | 0.840 |
| C blind-teacher | **0.915** | [0.882, 0.939] | 0.928 | 0.920 | 0.896 |
| D sighted-teacher (ceiling) | **0.940** | [0.903, 0.963] | 0.952 | 0.928 | — |

Even the **leakage ceiling** (arm D, teacher sees the answer) lands at 0.940 — only ~2.5 points
above the blind teacher (C) and within noise of self-refine (B). Seeing the ground truth barely
moves the needle: further evidence the loop is near its ceiling once the student self-refines.

---

## 4. Secondary views

- **Reference-match diverges from correctness (a finding in itself).** Semantic similarity to the
  gold answer is essentially FLAT across arms — A 0.715, B 0.697, C 0.691, D 0.705 — even as blind
  correctness rises A→B by +9 points. The loop makes answers *more correct/complete in the
  student's own words*, not *more similar to the reference phrasing*. This is exactly why the old
  reference-proximity metric was misleading: it would have shown the self-refinement gain as flat
  or slightly negative. (Diagnostic only, never part of pass/fail — ADR-019.)
- **The loop engages.** Arms B/C/D averaged ~1.2–1.5 rounds (vs A's 1.0); the teacher was called
  175 times across arms C/D. This is a real, exercised loop — not a degenerate one (contrast the
  earlier pilots at score≥3, where everything passed round 1).
- **Cost.** Judge: 1,656 Groq calls, 0 fallbacks. Teacher: 175 Groq calls, 116,705 tokens (well
  under the 500K/day cap). Student + judge on the free/local + cheap-cloud path; no 70B needed.

---

## 5. Why score≥4, and why a 3B student (the headroom problem)

At the original bar (score ≥ 3 = "correct and useful"), **every** arm passed ~100% on the first
round — even a 3B student — because MedQuAD Diabetes questions are largely definitional ("What is
X?") that small models already answer adequately. With no baseline failures, no loop can show an
effect (C − B ≡ 0 by construction). Raising the bar to **score ≥ 4 ("correct AND complete")**
dropped the baseline to ~82%, restoring room for the loop to matter. This is a change to what
"pass" means, made *before* seeing held-out results and applied identically to all arms — so the
**difference** C − B is robust to it even though the absolute pass-rate is not calibrated at the
3-vs-4 boundary (see Limitations).

---

## 6. Honest comparison to the original inflated result

The pre-renovation project reported **25% → 83% → 100%** (ADR-001). This run explains that number:

- The **real** effect of iterating is **+9 points from self-refinement** (A 82% → B 91%), not
  tens of points. The rest of the old headline was inflation: the student was shown the reference
  answer (ground-truth leakage, LEAKAGE_AUDIT L1/L4/L6/L7) and the metric rewarded copying the
  reference, not correctness.
- The old "100%" (P6C) was memorisation via a ground-truth memory store — retired structurally in
  v2 (the memory tripwire, T2.5).
- Here, ground truth **cannot** reach the student or judge: the leakage guard is not a config
  flag, it's an assertion. It fired for real in arm D, seed 123 — the sighted teacher echoed a
  12-token reference shingle into its feedback and the guard **aborted that run rather than leak**
  (that arm-D run has no summary; arm D is the ceiling, not a headline number, so C − B is
  unaffected). That crash is the seal working as designed.

---

## 7. Limitations (state claims narrowly)

- **Single domain.** Diabetes/Digestive/Kidney MedQuAD only. Do not generalise to other domains
  or harder question types (these are largely definitional).
- **Judge validity at the 3-vs-4 line.** The blind judge was calibrated (teaching-loop-protocol §3.3) at the
  PASS/FAIL (≥3) boundary; the 3-vs-4 boundary used here for the score≥4 bar was **not**
  separately calibrated, and no free LLM judge (local 8B, Groq 8B, even Groq 70B on a flawed
  adversarial probe) cleanly passed all calibration gates (see `reports/teaching-loop-medquad/2026-07-14-pilot-report.md`
  and the T2.3b/c notes in `todo.md`). C − B is a **difference** measured with one consistent
  judge, so it is robust to a mis-placed-but-consistent absolute bar; the per-arm absolute
  pass-rates are softer.
- **n and power.** 125 held-out × 3 seeds. The C − B CI half-width is ~±2.5 points — enough to
  rule out a large teacher effect, not to prove *exactly* zero.
- **Arm D incomplete** (2 of 3 seeds) and is a leakage ceiling, not a claimed result.

---

## 8. Verdict and implication for P3 (see ADR-024)

**The teaching-loop hypothesis, tested honestly, is: the loop helps a little, and the teacher is
the part that does not matter.** Self-refinement (a small model critiquing and re-answering
itself) is a real, cheap, local win (+9 pts). An independent teacher model — the expensive,
cloud-dependent component — adds nothing over it on this domain. Therefore, for the Track-B
product (ADR-002/003): **do not build a teacher-in-the-loop as a runtime improver.** Lean on
(i) self-refinement (free, local), (ii) RAG for domain knowledge, (iii) a small LoRA for style —
and keep the loop only as an offline data-generation/evaluation *factory*, which is exactly what
ADR-003 anticipated. This result redirects P3 effort to where the measured value is.

---

### Reproduce

```
# per seed ∈ {13,42,123}, per arm config ∈ {1-baseline, 2-self-refine,
# 3-teacher-feedback, 4-teacher-sees-answer}:
EXPERIMENT_PARAMS_SEED=<seed> \
  python run.py --config experiments/teaching-loop/<CONFIG>.yml \
  --data data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl \
  --teacher-fallback local:qwen2.5:7b-instruct --judge-fallback local:llama3.1:8b
# then the headline stats (paired cluster bootstrap + McNemar + Wilson):
python -m src.tlw.analysis --runs-dir runs/teaching-loop-medquad --comparison C-B
```

The pre-registration pilots live one directory deeper, in `runs/teaching-loop-medquad/pilots/`, which
`discover_runs` cannot reach — so a headline command structurally cannot pool them (ADR-034).

All numbers above were computed directly from
`runs/teaching-loop-medquad/{1-baseline,2-self-refine,3-teacher-feedback,4-teacher-sees-answer}__seed{13,42,123}__*/`
`summary.jsonl` + `rounds.jsonl` on 2026-07-15/16 using `src/tlw/analysis/stats.py`.
