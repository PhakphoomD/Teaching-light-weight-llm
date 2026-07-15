# Roadmap / TODO (SSOT) — Renovation Plan (ADR-015)

Status: `[ ]` todo · `[~]` in progress · `[x]` done · `[?]` needs user decision · ✋ = user gate

**How work happens (ADR-015):** decisions are made at the *hub* chat with the user; execution
happens in fresh *spoke* chats. Every task below has a full spec in `docs/plan/T*.md` —
a spoke chat starts by reading `docs/plan/README.md` + its task spec, and ends by ticking its
box here with a one-line result note. Do not start P2 before the P1 gate ✋ passes.

## ACTIVE — P0: Inspect the house (read-only, parallel-safe)
- [x] **T0.1** Code map — every file: role + verdict (EXEMPLAR/ALIVE/MESSY/DEAD) → `docs/audit/CODE_MAP.md` *(owner: housekeeping)* — done 2026-07-13: 44 files mapped; 5 DEAD confirmed (1,415 ln ≈ 26% of src/); 1 MESSY (teaching_loop `run()` 214–742); ⚠️ tools/ untracked in git
- [x] **T0.2** `.claude/` environment audit — is the crew fit for the new direction? → `docs/audit/CLAUDE_ENV_AUDIT.md` *(owner: main thread)* — done 2026-07-13: PASS-WITH-NOTES; BLOCKER = `.claude/`+plan+tools untracked in git; gaps = stats/RAG/LoRA ownership; guard works (tested live) but `.env` Write hole + `2>&1` false block
- [x] **T0.3** Ground-truth leakage census → `docs/audit/LEAKAGE_CENSUS.md` *(owner: qa-engineer)* — done 2026-07-13:
  18 paths classified; confirmed known L1-L5 (explicit GT-hint, off by config only); found 2 new
  BLOCKERs beyond the hub's starting list — L6 (memory-retrieval into student prompt is a structural,
  always-on leak, not gated by `enable_last_chance`) and L7 (`difficult_question` CoT template tells
  the teacher to echo GT verbatim into `feedback`, confirmed live: `logs/simplified/debug/20251130_024301.json:4460`).
  Score path = 70% GT-exposed weight (exact, from live config). 6 seal requirements for T2.3/T2.4/T2.5.

## P1: Blueprint on paper (docs/SSOT only — no code)
- [x] **T1.1** Config Contract v1 (six slots A–F) → `schema.md` section + ADR *(program-architect)* — done 2026-07-13: schema.md §"Experiment Config Contract v1" (slot table, layering base.yml→override→env, validation V1–V7, naming); ADR-016 Proposed
- [x] **T1.2** Target architecture + `structure.md` v2 (seams, strangler migration policy) + ADR *(program-architect)* — done 2026-07-13: structure.md v2 (src/tlw/ core, 5 seams→registries, strangler policy, junk checklist v2); ADR-017 Proposed
- [x] **T1.3** Honest memory design spec (notes-not-answers, tripwire, MemoryBackend) → `schema.md` *(program-architect + prompt-engineer)* — done 2026-07-13: schema.md §"Memory v2 contract" (teaching_note + store-time tripwire seals L4/L6, MemoryBackend seam, arm write-gate A/B=none C/D=faiss); ADR-018 Proposed; 2 threshold questions → gate
- [x] **T1.4** Track-A eval spec (4 arms, judge, seeds, CI, budget) → `docs/plan/EVAL_SPEC.md` *(program-architect + qa)* — done 2026-07-13: 4-arm protocol; blind 0–4 correctness judge (headline) แยกขาดจาก reference_match (diagnostic); C−B + 95% paired-bootstrap CI; ~3-day Groq budget (local judge แนะนำ — 70B เต็ม cap ~10 วัน); ADR-019 Proposed; 3 คำถาม → gate (student model, judge mode, memory-on/off headline)
- [x] **T1.5** Prompt catalog — curate ~38 variants → preset registry proposal *(prompt-engineer)* — done 2026-07-13: 42 variants → 7 presets (`docs/plan/PROMPT_CATALOG.md`); orca wins on real logs (0.90 vs 0.50/0.40); 2 leak prompts quarantined (L1/L7); 2 missing presets specced (arm B self-critique, arm C blind teacher); ADR-020 Proposed; 1 continuity question → gate
- [x] **T1.6** Update `.claude/` crew per T0.2 findings *(project-coordinator)* — done 2026-07-13: agents refreshed to renovation era; stats→qa-engineer; ADR path fixed (decisions.md canonical); `.env` Write-deny + guard `2>&1` fix (verified live at hub); ADR-021 Proposed
- [x] **T1.7** P1 gate package — consolidate + NEEDS-USER-DECISION list → `docs/plan/P1_GATE_REVIEW.md` *(project-coordinator)* — done 2026-07-13: blueprint coherent; 6 leakage seals ทุกตัวมีเจ้าของใน T2.x; 2 contradictions escalated (memory-on/off headline, V8); decisions (a)–(g) framed พร้อม recommendation
- [x] ✋ **P1 GATE — PASSED 2026-07-13 (all (a)–(g) resolved → ADR-022):** student =
  qwen2.5:7b-instruct local · judge = blind-only, local llama3.1:8b probe-gated (70B calibrate-only)
  · headline memory-OFF all arms, memory-on = C′/D′ ablation (memory effect = C′−C) · tripwire
  thresholds + **V8** adopted · minimal presets primary (orca pair kept for pilot) · ADR-016..021
  all **Accepted**. **P2 UNLOCKED.**

## ACTIVE — P2: Rebuild Track-A core (code; strangler — legacy stays until T2.9)
Gate answers are law for P2: `base.yml` hardcodes them (T2.1); order per `P1_GATE_REVIEW.md` §SEQUENCE.
Pre-T2.7 assignment: ops-engineer re-verifies `providers.md` caps vs Groq console (gate R6).
- [x] **T2.1** Config loader + validation (`base.yml`, fail-loud rules incl. §0.2 family check) *(ops/steward)* — done 2026-07-13: `src/tlw/config/` (schema/loader/validation), `config/base.yml` hardcodes ADR-022 gate answers; V1–V8 + REQUIRED + PATH all named-error, collect-all; 44 tests pass (`tests/tlw/config/`, tlw python); base.yml deliberately omits `params.seed`/`arm` (run identity — keeps V4 meaningful); legacy untouched & compiles
- [x] **T2.2** Registries for all slots (Memory/Preset/Judge; pattern from `providers/factory.py`) *(steward)* — done 2026-07-13: `src/tlw/registries.py` — generic `Registry` + 4 seam ABCs (MemoryBackend/PromptPreset/Judge/ArmStrategy ตาม structure.md §D) + MEMORY/PRESET/JUDGE/STRATEGY registries; `none` memory จริง (แทน top_k≤0 hack), placeholders บางๆ ชี้ไป T2.3/T2.4; `faiss`+`gt_comparing` จงใจไม่ register (ต้อง fail loud จนกว่า block จริงจะมา); 15 tests ใหม่, รวม 59 ผ่าน (tlw python)
- [x] **T2.3** Eval block — correctness judge ≠ reference-match diagnostics; leakage tests; calibration *(qa + prompt-engineer)* — done 2026-07-14: `src/tlw/evaluation/{judge,diagnostics,calibration}.py`; BlindJudge ไม่มี ground_truth ใน signature เชิงโครงสร้าง; reference_match แยก module/แยก field; 33 tests ใหม่. **⚠️ Calibration probe FAILS both judges** (ADR-022(d) both-fail branch): local llama3.1:8b → PLAUSIBLE_WRONG 0.95, disc 0.52, κ 0.35; fallback groq 8b-instant → disc 0.787 PASS แต่ PLAUSIBLE_WRONG 0.925, κ 0.411 FAIL. ไม่ tune rubric/threshold (§0.1). Evidence: `runs/calibration/probe_*.json` × 2. **[?] JUDGE LOCK → needs user decision at hub** (options a–d ใน probe report) — blocks T2.7 full run, ไม่ block T2.4/T2.6 build
- [x] **T2.4** Loop block v2 — arms A/B/C/D as strategies; NO ground-truth hint paths; mock tests *(steward + prompt-engineer)* — done 2026-07-14: `src/tlw/loop/{core,strategies}.py` (4 arm strategies + a shared honest-by-construction round loop with a structural leakage guard, `assert_gt_free`) + `src/tlw/prompts/{loader,presets}.py` (real `minimal`/`orca` PromptPresets over new `config/prompts/{student,teacher}.yml`, ADR-020 survivor set; quarantines `last_chance`/`difficult_question` at load time); registries.py placeholders for these 6 names deleted. 32 new tests (call-pattern, leakage seals incl. an L7-echo simulation, preset quarantine); full `tests/tlw` suite: 144 passed.
- [x] **T2.5** Memory block v2 — faiss+none backends, store-time GT tripwire *(data-engineer)* — done 2026-07-14: `src/tlw/memory/{tripwire,faiss_backend}.py`; `FaissMemory` registers as "faiss" (MemoryBackend seam, `store(episode, reference_answer=None)` — ABC signature updated); T-1/T-2/T-3 tripwire rejects GT-bearing notes at store time (never persisted, only a hash logged to `memory_rejects.jsonl`); red-team fixture (`phase6/gt_memory_store.jsonl`, 15 records) rejected 100%; `tests/tlw/memory/` (26 tests: round-trip, ranking, all 3 tripwire rules, isolation, update_outcome math, red-team) + `tests/tlw/test_registries.py` updated (faiss now real, rag still placeholder) — full `tests/tlw` suite: 112 passed
- [x] **T2.6** Runner + 4 arm configs + dry run (n=5, train split) *(ops-engineer)* — done 2026-07-14:
  `src/tlw/runner.py` + root `run.py` (composition root: config -> 6 slots via registries -> arm
  run -> `runs/<run_id>/{config_used.json,rounds.jsonl,summary.jsonl}`); `src/tlw/providers.py`
  fixes the "local"=Ollama gap flagged in T2.3 (registers a real Ollama HTTP client under "local",
  overwriting `LocalTinyLlama`'s registration for any process importing the new core only — legacy
  untouched, verified no duplicate-key guard exists in `factory.py`); 4 configs
  `experiments/trackA_p2_arm{A,B,C,D}_diabetes.yml` (diffs = `params.arm`+`seed` only) +
  `experiments/README.md`. Dry run (arms A+C, n=5, TRAIN split, seed 42, real
  Ollama qwen2.5:7b-instruct student + llama3.1:8b judge + Groq qwen3-32b teacher): mechanics
  proven — files complete, summary/rounds parse, judge scores in [0,4]; both arms pass_rate=5/5
  (ceiling effect at n=5 with an uncalibrated judge, not a result); arm B/D verified load+build
  without executing. 19 new tests (`tests/tlw/runner/`); full suite 163/163 green (no regressions).
  ADR-023 logged (Ollama "local" provider + `runs/` output location). **Judge is NOT
  calibration-locked** (T2.3 probe FAILED both candidates, `[?]` still open at the hub) — this
  dry run proves runner mechanics only, per its own scope; T2.7's full run is blocked on the
  judge-lock decision, same as T2.3 already flagged.
- [x] **T2.7** Pilot + **FULL RUN DONE** 2026-07-16 (125 heldout × 3 seeds × 4 arms; 11/12 runs, arm-D
  seed123 aborted by the leak guard = seal working). Headline **C−B=+0.003 [−0.021,+0.029] p=1.00**,
  **B−A=+0.091 [+0.051,+0.133] p<0.0001** → ADR-024. Path to a valid ablation went through the score≥4
  headroom fix (below). *(ops + qa)* — original pilot NO-GO note kept below for the record:
  - [~] Pilot DONE (n=25 train × 4 arms × seed42); **full run BLOCKED — NO-GO** *(ops + qa)* —
  pilot 2026-07-14 (`docs/plan/T2.7_PILOT_REPORT.md`): mechanics solid (0 errors/100 q, integrity
  all green, arm-D 0 verbatim GT overlap). **BLOCKER — degenerate ablation:** judge (llama3.1:8b,
  PASS≥3) scores EVERY round-1 answer 3–4 (never ≤2) → arm A baseline passes 100% → B/C/D never
  reach round 2 → teacher/self-refine never run (`teacher_calls=0`, `avg_rounds=1.0` all arms) →
  **C−B ≡ 0 by construction.** Two coupled causes: judge leniency (same as T2.3 calibration fail)
  + no headroom (qwen2.5:7b already clears these Diabetes Q's round 1). gate (f) minimal-vs-orca
  UNDECIDABLE at pilot (both ~100%); `orca_student` preset+run NOT added. Real latency:
  student/judge ~19 s/call each (~2× plan) → full run ≈16 h local; teacher/Groq still unmeasured.
  **[?] Folds into JUDGE-LOCK hub decision** — report §Recommendation options 1–3 (rec: option 1,
  raise threshold to ≥4 and/or stronger judge = fixes judge-lock + restores headroom in one move).
- **T2.3b Judge rubric v2 experiment (2026-07-14, user chose "try 8b rubric first"):** reasoning-first
  hard-fail rubric FIXED PLAUSIBLE_WRONG (0.95→0.20-0.30) but OVERCORRECTED — GOOD pass 0.975→0.25,
  discrimination 0.52→0.12, κ 0.35→0.21; seed 42 & seed 123 agree (systematic, not noise). **Conclusion:
  llama3.1:8b lacks the capability to be a reliable judge at ANY rubric strictness** (lenient→passes
  wrong; strict→fails right). Only viable independent judge left = Groq `llama-3.3-70b-versatile`
  (family≠Qwen). Evidence: `runs/calibration/probe_seed{42,123}_n40_1784002100.json`. Code: `judge.py`
  RUBRIC_PROMPT v2 + max_tokens 16→256 + parse_verdict last-match — LEFT IN PLACE, unvalidated for 8B,
  may suit a 70B judge (re-validate fresh if adopted). **→ hub decision: which judge + scope.**
- **T2.3c Groq-70B judge test (2026-07-14):** 70B FIXES the 8B's good-answer-rejection (good 0.25→0.75-0.80,
  discrimination 0.07→0.70+, wrong 0.00) — a real independent capable judge. Apparent 70B failure = plausible_wrong
  pass 0.62-0.70 (want ≤0.30), BUT **confounded by a flawed adversarial test**: `make_plausible_wrong` flips the
  FIRST is/are/can... it finds → main-thread spot-check of 6 seed-42 items found ~2/6 not-clearly-wrong (Acromegaly
  flip stays TRUE; NHPP flip is non-clinical trivia). So the plausible_wrong gate is unreliable for ALL judges.
  Also: **Groq 70B 100K TPD is ORG-WIDE shared + exhausted daily** (429 at 99.5K used, ~66K not ours) — a real
  full-run constraint; providers.md should note this (ops). Probe budget-crippled (null 0.60, n≈8-10 valid) so
  numbers partial. Code: `calibration.py` gained judge-provider routing + `_GroqAdapter` 4s pacing + κ=N/A guard
  (self-compare meaningless). Evidence: `runs/calibration/probe_seed42_n{2,20,15}_1784030*.json`. 228 tests green.
  **→ hub: fix adversarial test + re-probe 70B on fresh budget, OR accept harness+finding and pivot to P3.**
- **T2.7 HEADROOM pilot (2026-07-14, hub-approved):** ROOT CAUSE of degeneracy = the pass BAR, not model
  size. 3B student STILL passed 100% at score≥3 (MedQuAD Q's are definitional/easy). Fix = raise bar to
  **score≥4 ("correct AND complete")** → baseline drops to 67-73% = headroom restored, ALL on the FREE local
  8B judge (no Groq). Reverted judge rubric to v1 (lenient) since v2 overcorrected. 4-arm pilot (3B, bar≥4,
  n=15 train, seed42, `experiments/trackA_p2_arm{A,B,C,D}_diabetes_3b.yml`): A=0.733 B=0.800 C=0.800 D=0.733
  → **HEADLINE C−B = +0.000** (B−A=+0.067, D−C=−0.067). Loop ENGAGES now (avg 1.4-1.5 rounds, teacher called
  7-8×) but teacher feedback ≈ self-refine ≈ baseline — directionally the honest loop effect is ~0, exactly
  as ADR-001 predicted. n=15/1-seed = directional only; real number needs 125×3seeds (now FEASIBLE: 3B local
  + 8B local judge free, teacher Groq qwen3-32b within 500K TPD; ~1 day local compute). Caveat: bar≥4 raised
  without calibrating the judge's 3-vs-4 line — but C−B (a difference) is robust to a consistent judge.
  **→ hub: run full 125×3 for the real pre-registered C−B, or accept the directional ~0 + write up.**
- **T2.7 FULL RUN launched 2026-07-14 (hub said go):** 3 seeds {13,42,123} × 4 arms on HELDOUT 125,
  student=qwen2.5:3b local, bar≥4, judge=Groq `llama-3.1-8b-instant` (frees GPU → student runs alone,
  ~3x faster; Llama≠Qwen §0.2 ok), teacher=Groq qwen3-32b; ALL Groq slots have local fallback
  (`run.py --judge-fallback local:llama3.1:8b --teacher-fallback local:qwen2.5:7b-instruct`, ops-engineer
  `_FallbackClient` retry→backoff→local, 70B would be pace-only no-fallback per hub). Preflight: Groq pools
  FRESH (qwen3-32b 999/1000 req, 8b-instant 14399/14400). configs `experiments/trackA_full_arm{A,B,C,D}_diabetes.yml`.
  239 tests green. **T2.8 analysis MUST filter to run_id prefix `trackA_full_*` + heldout data_path** — the
  pilot 3b runs (`trackA_p2_*_3b`, TRAIN, bar≥4) share (arm,seed,mem,3b) keys so pool by run_id/data_path.
- [x] **T2.8** Analysis + honest report — **C−B with 95% CI** → `docs/TRACK_A_RESULTS.md` + ADR-024 *(qa)* —
  DONE 2026-07-16: SCRIPT half (`src/tlw/analysis/`, 61 tests) computed the pre-registered headline from
  the `trackA_full_*` heldout runs: **C−B=+0.003 [−0.021,+0.029] McNemar p=1.00** (teacher adds 0),
  **B−A=+0.091 [+0.051,+0.133] p<0.0001** (self-refine real). REPORT half = `docs/TRACK_A_RESULTS.md`
  (methods/table/limitations/old-25→83-comparison) + ADR-024 verdict. reference_match flat while
  correctness rose → ADR-019 split validated. Numbers computed live from run logs (§0.1/§0.4).
- [x] **T2.9** Demolition — DONE 2026-07-16 *(steward)*: safety-grep confirmed the new `src/tlw/` stack
  imports NOTHING legacy, then deleted the 5 CODE_MAP DEAD files + the whole frozen legacy core
  (`simplified_teaching_loop.py`, `simplified_experiment_runner.py`, `src/simplified/*`, `src/prompts/*`,
  `src/eval/*` incl. now-orphaned `metrics.py`, `config/simplified_config.yml`); archived the prompt
  catalog → `config/archive/prompts_config_legacy.yml` (ADR-020). 239 tests green post-deletion; `run.py`
  + `import src.tlw.runner` OK. Left `src/utils/prompt_loader.py` + `notebooks/experiment.ipynb` (exploratory,
  now dead — retire in P3 housekeeping). CODE_MAP.md pre-demolition tables marked historical (banner).
  **P2 COMPLETE.**

## P3: Track B (RAG + LoRA product) — NOT PLANNED YET, by design
See `docs/plan/P3-track-b-placeholder.md`. Locked already (ADR-015): 3B floor / 7B ceiling /
1B stretch; RAG=knowledge, LoRA=style, loop=offline factory. Hub plans P3 after T2.8.

## Standing backlog (fold into tasks, don't do ad-hoc)
- Reconcile README/docs numbers with logs → covered by T2.8 (reconcile-numbers)
- Mislabeled `growth_hormone_receptor` (=GHR) relabel → data note, revisit in P3 corpus work
- Hardcoded absolute paths in committed configs → killed structurally by T2.1 (path resolution)
- ADR-009 restructure + ADR-010 SQLite migration → absorbed into T1.2 blueprint / P3 planning

## DONE (pre-renovation) — kept for the record
- [x] Dataset tooling workstream Stages 0–5 (cleaner → assessor → split → verify → UI).
  Result: 12,428 → 10,024 clean across 7 domains; Diabetes train 506 / heldout 125; Streamlit
  UI built. Tools live in `tools/dataset/`. Details: ADR-005, ADR-006, ADR-011, ADR-013, ADR-014.
- [x] A1 dataset quality analysis across 7 domains (ADR-004/006)
