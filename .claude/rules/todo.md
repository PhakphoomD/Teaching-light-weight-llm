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

## DONE — P2: Track-A core rebuilt + honest result (verified at hub 2026-07-16)
Verdict (ADR-024): teacher adds nothing (C−B=+0.003, p=1.00); self-refine real (B−A=+0.091,
p<0.0001). New `src/tlw/` core; legacy demolished; 239 tests pass; independently re-computed from
`runs/trackA_full_*` at the hub. Gate answers hardcoded in `base.yml`; full task notes below.
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

## ACTIVE — P3: Track B (RAG + LoRA product) — PLANNED 2026-07-16 (ADR-025)
Index + rationale: `docs/plan/P3-track-b-placeholder.md`. RAG sub-track first (user decision).
Ownership (ADR-025, no new agents): corpus→data-engineer, backend→codebase-steward, eval→qa,
training→ops, design→program-architect.

### P3-A — RAG (detailed; start here)
- [x] **T3.1** RAG blueprint + grounded-eval design (paper) → `docs/plan/RAG_SPEC.md` + ADR *(program-architect + qa)* — done 2026-07-16: `docs/plan/RAG_SPEC.md` + schema.md §"Slot-D `rag` backend contract" + ADR-026 (Proposed). Retriever = MiniLM+FAISS-IP over TRAIN questions→return answers as passages, top_k 3, floor 0.35 (lower than memory's 0.75), grounding injected at the FIRST answer attempt. `rag` = corpus-backed read-only MemoryBackend (`store()` no-op), same seam → runner unchanged. Eval = blind correctness reused from Track A (PASS≥4, comparable) as headline; faithfulness DECIDED = RAGAS groundedness ratio (GT-free, diagnostic only, never merged); reference_match kept as leakage smell-test. Headline = 3B+RAG−3B, 95% paired-bootstrap CI (reuse `src/tlw/analysis`), arms {3B,3B+RAG,7B,7B+RAG} single-pass. Anti-leak: corpus=TRAIN-only + manifest (zero heldout ids) + train↔heldout ≥0.90 near-dup scrub + `assert_gt_free` run-time guard. Budget ≈ free (all local). 2 small hub flags: 3B+RAG+self-refine secondary arm? + V8 one-line exemption for `type: rag` on arms A/B.
- [x] **T3.2** Build retrieval corpus + index from `data/clean/` Diabetes (held-out excluded) → `tools/rag/` *(data-engineer)* — done 2026-07-16: reusable config-driven `tools/rag/{builder,cli}.py` (reuses `tools/dataset/embeddings.embed` MiniLM + FAISS IndexFlatIP like `faiss_backend.py`). Diabetes build: 506 source → 0 dropped by id (RAG-L1, splits disjoint) → **58 dropped by near-dup scrub (RAG-L2, ≥0.90 cosine vs heldout, q OR a)** → **448 indexed**; both exclusion checks PASS. Artifacts `data/rag/diabetes_train/{faiss.index,passages.jsonl,faiss.ids.json,manifest.json,build_report.md}` (gitignored, rebuildable via `python -m tools.rag.cli`). Sample retrievals sane (same-topic passages sim 0.61–0.84, NOT the exact heldout answer → validates the 0.35 floor). 5 tests pass (`tests/rag/`); generality smoke on Heart/Lung (246 rec) OK.
- [x] **T3.3** slot-D `type: rag` backend + grounding into answer prompt; leak guard *(codebase-steward + data)* — done 2026-07-16: `src/tlw/memory/rag_backend.py` (`RagMemory`, registers "rag", read-only corpus, `store`/`update_outcome` no-op, `grounds_first_attempt=True`); grounding wired via `core.grounding_block` + `_BaseArm._first_prompt` (passages → `grounded_first` preset at round 1); config: `corpus_path`/`max_passage_words` keys, V8 exempts rag on A/B, rag-requires-corpus_path check. **Leak handling strengthened after first real run surfaced templated leaks** (hub-approved): RAG-L2b build-time verbatim-block scrub (drop train records sharing ≥8 twelve-shingles w/ any heldout answer — cosine is blind to MedQuAD "What to do for X" template reuse, e.g. Crohn's/Colitis 108 shingles @ 0.76 cos) + RAG-L3 changed from abort-run to **filter-per-passage** (drop+count leaky passage, ground on survivors; `grounding_filtered_total` in summary). Index rebuilt: 506→ L2a 58 + L2b 34 → **414 indexed**. E2E smoke (5 heldout, 3B+RAG): completed, all grounded, 1 residual passage filtered, no abort. Full suite **257 pass**. ⚠️ Ops: set `HF_HUB_OFFLINE=1` for embed runs (see [[hf-offline-embedding-stall]]).
- [x] **T3.4** Grounded-QA eval — blind correctness (headline) + faithfulness (diagnostic), never merged *(qa)* — done 2026-07-16: reused Track-A `BlindJudge` unchanged (headline, comparability); `src/tlw/evaluation/faithfulness.py` `FaithfulnessJudge` (RAGAS-style groundedness ratio, single-call, §0.2-safe — sees (answer, passages) only, no gold; NEW judge not `gt_comparing`); runner computes it post-hoc for rag runs (loop persists `grounding_context`), aggregates `metrics.faithfulness` + `grounding_filtered_total` in summary. Analysis: `src/tlw/analysis/rag_report.py` groups by RAG label {3B,3B+RAG,7B,7B+RAG} (NO V8 guard — crossing memory none/rag is the design), reuses the Track-A CI machinery; `--rag` CLI flag renders per-label Wilson + headline 3B+RAG−3B (paired bootstrap+McNemar) + **three never-merged columns** (correctness/faithfulness/reference_match) + honesty banner. 13 new tests; suite **270 pass**. E2E verified: real 3B & 3B+RAG runs (4 heldout) → faithfulness populated, `--rag` table renders, banner flags n<125.
- [x] **T3.5** RAG ablation → `docs/RAG_RESULTS.md` + ADR → **GATE ✋ PASSED** *(ops + qa)* — done 2026-07-21 (4-arm table clean, ADR-027). Pilot (25 heldout×seed42, Groq judge) showed RAG HURTS: 3B 0.96→3B+RAG 0.80 (−0.16), broke 4/fixed 0. **Diagnosed:** (1) first-25 heldout are unusually easy (96% baseline, near-ceiling — no knowledge gap); (2) MiniLM retrieval is disease-name-dominated so "treatments for X" retrieves "symptoms of X" (right topic, wrong aspect) → grounding distracts the 3B off its already-correct answer. **Similarity floor is NOT the lever** (broken cases at 0.70-0.85, same as ok cases). Hardened grounding prompt (v2) BACKFIRED (0.80→0.56 — 3B fixates on passages, prefaces "the passage doesn't cover this") → reverted to v1. **Decisive hard-subset test:** on the 13 Qs the 3B baseline failed in ALL 3 Track-A seeds, 3B+RAG recovers **5/13 (38%)** → RAG DOES help where a knowledge gap exists; the pilot negative was an easy-question artifact. Net effect on 125 = tug-of-war (helps hard, hurts easy) → needs full run. **User chose headline pair (~4h):** reuse Track-A `trackA_full_armA` as 3B baseline (125×3, copied to `runs_rag/`), running **3B+RAG × {13,42,123} × 125** now (`--no-faithfulness`, correctness=Groq to fit TPD + stay consistent w/ baseline; faithfulness computed offline via `scripts/rag_faithfulness.py` local judge). **HEADLINE DONE 2026-07-16 (ADR-027):** 3B+RAG − 3B = **−0.005, 95% CI [−0.067,+0.056], McNemar p=0.91 → NO net effect** (3B 0.821 / 3B+RAG 0.816; 100% Groq judge). **Tug-of-war:** RAG broke 39 (35 on easy) + fixed 37 (all on baseline-failed, ~38% recovery on hardest) → net ~0. Faithfulness ≈0.81 (61% null, local judge weak — indicative). `docs/RAG_RESULTS.md` + ADR-027. **Gate ✋ passed — user (2026-07-17) said do 7B then selective RAG.**
  - **7B pair — DONE 2026-07-21 (clean 4-arm table):** original runs got Groq-cap-contaminated (mixed judge) + a same-day re-judge corrupted scores to nulls; **recovered** by re-judging the 2 still-null 7bRAG runs on fresh Groq (`rejudge.py --only-nulls`, idempotent; student answers were always intact). **7B 0.904 / 7B+RAG 0.835 → 7B+RAG−7B = −0.069 [−0.120,−0.019] p=0.0004 → RAG SIGNIFICANTLY HURTS the 7B** (fixed 13/broke 39), MORE than the 3B. **3B+RAG 0.816 < 7B 0.904** → RAG can't lift a 3B to 7B. Full 4-arm table in `docs/RAG_RESULTS.md §8` + ADR-027. Lesson: RAG's distraction dominates its repair the stronger the base model. **Ops lesson: Groq free-tier TPD (500K 8b / 100K 70b) is org-wide + too small for ~750-call judging — use local judge or batch across days; never destructive-rewrite scores without checking budget first.**
  - **Selective RAG (P3-B, `docs/plan/SELECTIVE_RAG.md`) — oracle +9.9pt real, cheap gates FAIL:** ground-only-baseline-failures = 0.920 (+0.099). But uncertainty gates (length/hedging/self-consistency) corr ~0 (3B is confidently wrong); 8B verify-then-ground LLM gate is bimodal-useless (99% lenient / 0% strict prompt). User chose: **try Groq 70B gate on reset** (queued in `finish_when_groq_ready.py`, seed-42 subset). If 70B also fails → selective RAG needs a learned gate / aspect-aware retriever (future work). New tools: `scripts/{rag_faithfulness,selective_rag_sim,rejudge,finish_when_groq_ready}.py`.

### P3-B — LoRA (LIGHT specs — scope firms up only after the T3.5 gate)
- [x] **T3.6** LoRA data-gen *(data-engineer)* — done 2026-07-23: recipe PIVOTED per T3.5 gate — loop-factory yields no signal (self-refine doesn't engage on near-ceiling train, smoke 5/5 round-1; RAG hurts, ADR-027) → **standard gold-SFT** on (TRAIN question → TRAIN gold answer). `scripts/build_lora_data.py` → `data/processed/lora_diabetes_sft.jsonl` (**506 pairs**, 0 held-out leak verified by id+question, cloud-free — no Groq). Data card written.
- [x] **T3.7** QLoRA 4-bit fine-tune *(ops-engineer)* — done 2026-07-23: precondition-checked FIRST (PyPI/HF/bnb-Windows-wheel/CUDA all ✓; bnb 4-bit-on-CUDA verified). Installed peft/bnb/trl, downloaded Qwen2.5-3B-Instruct (6.2GB), `scripts/train_lora.py` (NF4 4-bit + LoRA r=16 on attn+MLP, grad-checkpoint, trl SFTTrainer). Trained 2 epochs on RTX 4060 (GPU 6.5/8GB, 23min): **loss 1.98→0.99, token-acc 0.59→0.75**. Adapter → `models/lora_diabetes/` (60MB).
- [x] **T3.8** Combined eval *(qa)* — done 2026-07-23: `scripts/eval_lora.py`, base 3B vs 3B+LoRA on held-out 125 (same HF stack, adapter on/off), 2 seeds, **validated Groq judge** (0 fallback). **3B+LoRA − base = −0.292, 95% CI [−0.360, −0.224] → LoRA HURTS**. Diagnosed: style transfer SUCCEEDED (LoRA adopts NIH gold phrasing) but answers ~30-45% shorter → fail "complete" (≥4) bar (alignment-tax/forgetting). `docs/PRODUCT_RESULTS.md` + ADR-028. **T3 (P3) COMPLETE** — all 8 tasks done; combined verdict: no lever (loop/RAG/LoRA) improves the near-ceiling aggregate, value is on the hard tail.

### P3-D — Honest RAG re-test (2026-07-24 spoke session) — findings PROPOSED, awaiting hub ratification
Motivation: before accepting the MedQuAD RAG null, exhaust the "fair-test" objections, then test RAG's other half (does it add knowledge where the model genuinely lacks it?) on a gap-heavy SME testbed.
- [x] **Fair-test on MedQuAD** *(ADR-029)* — aspect-rerank RAG **0.760** (worse) + comprehensive 7-domain corpus 9,798-passage RAG **0.816** (still <0.864 baseline) → RAG null is **structural** (leak-free single-source corpus can't hold the answer), not a retriever/corpus artifact. Configs `experiments/trackB_p3_3bRAG{aspect,big}_diabetes.yml`, runs `runs_rag_{aspect,big}/`.
- [x] **gate-(f) closed** *(ADR-029)* — orca-student **0.840** ≈ minimal **0.864** (McNemar p=0.58) → prompt is not the lever. `experiments/trackA_p2_armA_diabetes_orca.yml`, `runs_orca/`.
- [x] **WixQA — first POSITIVE RAG** *(ADR-030)* — Wix support KB (6,221 articles + 200 expert QA, HF `Wix/WixQA`, MIT). 3B baseline **0.175** (no gap-free ceiling — real knowledge gap) → 3B+RAG **0.305 (+13pt, p=0.0026)**; **causally proven from the data** (gold retrieved: 0.136→0.409 +27pt; gold missed: 0.222→0.178 −4pt). Unified law: RAG helps iff retrieval holds the answer. Tools `scripts/wixqa_{baseline,build_index,rag}.py`, data `data/wixqa/`, index `data/rag/wixqa_kb/`, runs `runs_wixqa/`.
- [x] **NEXT hub decision RESOLVED 2026-07-24 (ADR-031):** user chose **prove the RAG law via the
  retriever** (option a) — folds in (b) 3-seed CI + (d) stale-doc fix. Options (c) TechQA + product-FE
  deferred. → P3-E below.

### ACTIVE — P3-E: Prove "retrieval is RAG's bottleneck" via WixQA dose-response (ADR-031)
Index + design: `docs/plan/P3-E-retrieval-proof.md`. Proof = pass-rate tracks hit-rate toward the
0.409 gold-retrieved anchor. Hold student/judge/PASS≥3/top-k fixed across variants; KB articles only.
- [x] **T3.9** Instrument per-question hit-rate + re-run WixQA RAG at 3 seeds (CI on the +13pt) *(data + qa)* —
  DONE 2026-07-24 (all 600/600 replicates judged). New tools `scripts/wixqa_{run3seed,judge,analyze}.py`
  (seeded via new Ollama `options.seed` in `src/tlw/providers.py`; decoupled generation + resumable
  budget-graceful judger that stops cleanly on the Groq TPD cap and resumes idempotently; reuses
  `src/tlw/analysis` bootstrap/McNemar). **Retrieval instrument** → `runs_wixqa/retrieval_log.jsonl`
  {gold_rank, gold_retrieved, top_sim}; **hit-rate 110/200 = 0.550 reproduces ADR-030 EXACTLY** (0 retrieved_ids
  mismatches vs seed-42). **3-seed headline (600 paired replicates): 3B+RAG − 3B = +0.152, 95% CI
  [+0.090, +0.213], McNemar p=5.2e-11** (per-seed +0.160/+0.130/+0.165 — ADR-030's +0.130 sits inside the CI).
  **Gold split holds across seeds:** gold-RETRIEVED (n=110) 0.127→0.400 (+0.273); gold-MISSED (n=90) 0.207→0.211
  (+0.004 ≈ 0) — the robust signal is the CONTRAST (mirrors ADR-030's single-seed +27/−4). pass@≥4≈0
  (baseline 0.000/rag 0.010 → the T3.14 completeness floor). Report `docs/WIXQA_RESULTS.md` (variant #1 =
  MiniLM/whole-article of the T3.10 ladder). Judge held fixed (Groq llama-3.1-8b ref-comparing, §0.2-legal);
  seed 42 = ADR-030 draw reused verbatim. **→ T3.10 (retriever ladder) unblocked.**
- [x] **T3.10** Offline retriever ladder (chunking / encoder>MiniLM / hybrid BM25+dense), rank by hit-rate@k → **GATE**
  *(data-engineer)* — DONE 2026-07-24, **GATE = GO**. `scripts/wixqa_retriever_ladder.py` (offline hit-rate@k, no LLM;
  KB-only seal re-verified) → `data/rag/retriever_ladder/hitrate_table.json`. 7 variants, article-level hit@3 vs the
  0.550 baseline: **`bge_chunk` = 0.665 (+11.5pt) WINS** (bge-base-en-v1.5 + 180-word chunks); minilm_chunk 0.645
  (+9.5pt, chunking is the dominant lever — whole-article MiniLM truncates long KB articles at ~256 tok). Honest
  negatives: BM25 alone 0.465 (−8.5pt); hybrid RRF 0.605 HURTS the strong dense; cross-encoder rerank 0.640 (wash at
  k=3 — helps @5/@10 recall, hurts @3 precision). Ceiling: even bge_chunk @10=0.845 (~15% of gold hard to surface).
  **Advance `bge_chunk` to T3.11** (+ minilm_chunk as a cheaper middle dose point → 3 hit-rate levels 0.550/0.645/0.665).
  Pre-registered prediction (T3.9 mixture, which reproduces the 0.315 point exactly): hit 0.665 → aggregate pass ~0.337
  (+2.2pt, bounded by P(pass|retrieved)=0.400 → the completeness ceiling T3.14 targets). Report → `docs/WIXQA_RESULTS.md`
  §"Retriever ladder (T3.10)". New deps: `rank_bm25`, encoders bge-base-en-v1.5 + ms-marco cross-encoder (local).
- [x] **T3.11** E2e dose-response run of the winner (3B, 3 seeds) → the PROOF (hit-rate↔pass-rate vs 0.400) *(ops + qa)* —
  DONE 2026-07-25, **all 600/600 judged** (final: bge_chunk pass **0.340** vs predicted 0.337 — within 0.003;
  gold-split retrieved **0.411** / missed 0.199; paired Δ vs minilm_whole +0.025 [−0.030,+0.078] p=0.27 n.s. as
  expected). Generation
  ran via auto-resume once the user's *other* Claude session freed the shared GPU. `scripts/wixqa_run3seed_retriever.py`
  (grounds 3B on a retriever's top-k, IDENTICAL prompt/judge/top-k to T3.9 — only retriever changes) +
  `scripts/wixqa_dose_analyze.py`. **DOSE-RESPONSE (monotonic):** no-RAG hit0→pass 0.163; minilm_whole hit0.55→0.315;
  **bge_chunk hit0.665→0.329**. **MECHANISM (the proof):** gold-split P(pass|retrieved) pinned at **0.400** for BOTH
  minilm_whole AND bge_chunk (missed 0.211/0.186) → the retriever changes HOW OFTEN gold is retrieved, not the payoff
  when it is → retrieval IS the bottleneck, demonstrated not asserted. Mixture `hit·0.400+(1−hit)·0.211` predicts both
  points (0.315 exact, 0.329 vs 0.337). HONEST: aggregate lift bge−minilm = +0.025 [−0.030,+0.078] p=0.27 NOT significant
  (expected — bounded by the 0.400 ceiling, < CI; proof is dose-response+gold-split, not a big jump). 2nd bottleneck =
  3B completeness (pass caps ~0.40 even w/ perfect retrieval) → T3.14. Report → `docs/WIXQA_RESULTS.md` §"Dose-response".
  **→ T3.14 (Loop+RAG) + T3.12 (write-up) unblocked.**
- **CAPSTONE PLAN v2 (2026-07-25)** → `docs/plan/P3E-CAPSTONE-PLAN.md` — method/measurement/prediction for the last
  two tasks. **v2 restructured T3.14 after a pre-run diagnostic (offline, 0 LLM calls) found 3 things:**
  **F1** failure mode is fact *selection*, not length (student writes 153 words vs reference 125; length doesn't
  separate scores) → refine must REWRITE in budget, not append. **F2 (decisive)** grounding shows only the first 900
  chars but gold articles are median 3,555 → **92.5% truncated, student sees 25% of the article**; measured on answer
  content-words the full article covers **72%** but what we show covers **36%** → we discard 31pt of answer coverage
  (65% of questions lose >20pt). So "gold retrieved" ≠ "answer in context" → running self-refine FIRST (v1 plan) would
  have tested it under a broken premise. **F2b** `bge_chunk` retrieves by CHUNK but we ground on the ARTICLE HEAD —
  the retriever's localisation is discarded (nearly free to fix). **F3** pass@≥4 is near-unreachable (full article
  covers only ~72% of the reference) → weak primary metric; added a continuous judge-free **reference-coverage**
  metric. Observational coverage→pass is suggestive but CONFOUNDED (top tercile 0.511 vs bottom 0.353, yet overall
  r=+0.025) → needs the paired interventional test. **New structure:** T3.14 **Stage 1** grounding repair
  (offline coverage ladder → gate → pilot → full) then **Stage 2** self-refine on the repaired grounding. Blockers
  carried over: arm B `refine` (`strategies.py:154`) drops grounding after round 1 → needs `grounded_refine`; §0.2 —
  ref-comparing judge must NOT gate iteration (fixed 1+2 rounds, judged offline; blind self-stop logged for offline
  evaluation). **Revised predictions:** aggregate pass@≥3 0.340→~0.38 (0.32–0.44), pass@≥4 0.010→~0.04 (0.01–0.08);
  null probability raised to **35–45%** (F1). Pre-registered decision rules in §6 of the plan.
- [x] **T3.14** **Loop+RAG capstone** *(ops + qa)* — **STAGE 1 (grounding repair) COMPLETE 2026-08-06, 600/600
  judged; Stage 2 (self-refine) awaiting user go.** Pre-run diagnostic found a confound that would have made
  Stage 2 uninterpretable: grounding showed only the first 900 chars but gold articles are median 3,555 →
  92.5% truncated, student saw 25% of the article, and only 36% of the expert answer's content (full article
  holds 72%). Fixed via an offline 2×2 coverage ladder (`scripts/wixqa_grounding_ladder.py`, 0 LLM calls) →
  **`chunk2400`** (matched-chunk-centred window, 2400 chars/article) raises in-context answer coverage
  0.412→**0.655** (90% of the 0.726 ceiling); chunk-centring alone gives +0.071 at +7% prompt (uses the
  retriever's own localisation, which T3.11 discarded). Verified no Ollama context truncation at 1,323 tokens.
  **E2E (only the grounding window changed; retrieval reused verbatim from T3.11): aggregate pass@≥3
  0.340→0.470 (+0.130 [+0.072,+0.188], McNemar p=3.5e-08)**; gold-retrieved 0.411→**0.534**; gold-missed
  0.199→**0.343**; reference-coverage +0.042 [+0.032,+0.053]; catastrophes 0.298→0.232; answers SHORTER
  (152→144 w — better fact selection, not more text). **pass@≥4 flat at 0.007** (structurally unreachable —
  full article covers only ~72% of the reference). **Delivery > retriever as a lever:** +13pt vs the retriever
  ladder's +2.5pt. Ladder now: no-RAG 0.163 → MiniLM 0.315 → +best retriever 0.340 → **+grounding 0.470**.
  **Extraction ratio 88%→61%** = the model leaves ~39% of available answer content unused → the Stage-2 target.
  Integrity: 5 empty answers from a mid-run Ollama crash regenerated before judging (`repaired: true`, §0.1).
  New tools: `wixqa_{grounding_ladder,grounding_compare,repair_empty}.py` + `--grounding` in
  `wixqa_run3seed_retriever.py`. Report → `docs/WIXQA_RESULTS.md` §"Grounding delivery".
  **STAGE 2 (self-refine + RAG = the Loop+RAG system) PILOT COMPLETE 2026-08-06** (133/133 judged,
  gold-retrieved, seed 42; `scripts/wixqa_selfrefine.py`, grounding persisted in EVERY round — fixes the
  `strategies.py:154` blocker; fixed rounds + offline judging so the ref-comparing judge never gates the
  loop, §0.2; teacher stays dead per ADR-024). **VERDICT: self-refine does NOT compound with RAG.**
  Mechanically it works — reference-coverage **0.414→0.445 (+0.031 [+0.018,+0.047], CI excludes 0)**,
  extraction 63%→68%, 62% of answers edited — but the judged bar is flat/negative: **pass@≥3 0.571→0.556
  (−0.015 [−0.068,+0.038], p=0.77)**, mean score 2.35→2.35, answers +16% longer. **Mechanism = the ADR-027
  tug-of-war, replicated for iteration:** helps weak answers (score0 +0.33, score1 +0.38) but damages good
  ones (score3 n=74: −0.11, 0 improved / 7 worsened) — and 57% were already at score 3. **Selective
  refinement has real headroom but the small model can't self-gate:** ORACLE (refine only if ≤2) = 0.609
  (+0.038) vs blind self-assessment gate = 0.571 (+0.000); the 3B called its own answer "complete" 59% of
  the time. This REPLICATES the selective-RAG finding (ADR-027 oracle +9.9pt, cheap gates fail) on a second
  intervention → **the missing piece is a reliable gate, not the intervention.** Per the pre-registered gate
  (plan §6) the 3-seed full run was NOT run (null at pilot) → ship single-pass RAG. Report →
  `docs/WIXQA_RESULTS.md` §"Loop+RAG". **T3.14 COMPLETE** (both stages; Stage-2 full run intentionally not run per the pre-registered gate).
- [x] **T3.12** Unified `docs/RAG_LAW.md` + ADR *(qa + main thread)* — DONE 2026-08-06. `docs/RAG_LAW.md`
  (~10-min read, portfolio artifact): states the law as a **3-stage pipeline** (retrieval 0.550→0.665 →
  delivery 0.412→0.655 → extraction 88%→61% = the unsolved bottleneck), then the full evidence chain with
  CI + source for every number: loop (teacher +0.003 / self-refine +0.091) → MedQuAD RAG null −0.005 (+ the
  3 failed fair-tests) → WixQA +0.152 with the causal gold-split → dose-response proof → **delivery +0.130
  (the biggest lever, beats the retriever's +0.025 at zero inference cost)** → Loop+RAG does not compound
  (+ oracle 0.609 vs blind gate 0.571 = the gate is the missing piece) → LoRA −0.292. Plus the 2-testbed
  design, the recurring tug-of-war pattern (3 replications), 7 product recommendations, limitations
  (incl. both wrong predictions), verification commands, and 12 cited papers with how each was used/tested.
  **ADR-033** logged. §0.1 reconcile caught + fixed a real drift: the retriever delta was written as
  +0.014/p=0.6 from partially-judged data; recomputed on the complete 600 = **+0.025 [−0.030,+0.078] p=0.27**
  (corrected in RAG_LAW.md and this file).
- [x] **T3.13** *(MUST-before-commit)* retire the stale inflated narrative *(qa)* — DONE 2026-08-06.
  Audit found the violation was **wider than the task spec said**: not only
  `docs/PROJECT_OVERVIEW_AND_RESULTS.md` (11 hits) but **README.md itself** — line 3, the project's first
  sentence, claimed "Achieves 83% pass rate (up from 25%)" and the Key-Results table listed "Ground Truth
  Memory 100%". Actions: (1) archived the overview → `docs/archive/PROJECT_OVERVIEW_AND_RESULTS.md` with a
  SUPERSEDED banner that names each false claim, why it is false, and which ADR corrects it (archived, not
  deleted — the correction is part of the honest record, per the spec's Must-NOT); (2) **rewrote README's
  headline, Overview, Key Results, phase history and cost tables** to the real numbers with links to the
  source reports, incl. an explicit retirement notice for the old claim; also fixed the Overview's internal
  contradiction (it still described a 70B-teacher architecture that ADR-024 disproved and T2.9 deleted).
  Verified: no live doc asserts 25→83→100 — remaining greps are the retirement notice, the phase history,
  the labelled historical comparison in `TRACK_A_RESULTS.md:101`, an unrelated "~25% of the article", and a
  progress-bar "100%". **Known remaining staleness (deliberately deferred to the housekeeping pass):**
  README's architecture diagram/Project-Structure/Usage sections still describe the pre-T2.9 layout.

### P3-C — Product surface (placeholder) — deferred until after the RAG-law write-up
Minimal local chat UI for SME use; storage upgrade (revisit ADR-010 SQLite/sqlite-vec). Unowned.

## DONE — Repo restructure (ADR-034) — phases 1–5, 2026-08-07
Executed after a housekeeping audit (FAIL, 18 findings) + an independent pre-execution safety check
(`docs/plan/MIGRATION_CHECKLIST.md`, 909 lines, 2 BLOCKERs). Every step verified against a regression
oracle captured *before* any change; all published numbers reproduce byte-for-byte.
- **P1** additions: `pytest.ini` (replaces a `sys.path` hack in `tests/conftest.py`), `scripts/__init__.py`,
  `docs/README.md`, `reports/README.md`, and a one-line gloss of what "tlw" stands for.
- **P2** the §0.3 fix: **13 scripts** hardcoded `ROOT = Path("C:/Users/ham25/…")` — the scripts that
  produced ADR-030…033 could not run from a clone. Now `Path(__file__).resolve().parents[1]`; oracle unchanged.
- **P3** 9 run roots → `runs/<study>/` grouped by the question each answers, names in English
  (`4-rag-wider-context`, not `rag_bge_chunk_chunk2400`), condition in a `manifest.json` (74 written).
  Ordinals only where step N+1 contains step N. **Fixed a live §0.1 defect**: `--runs-dir runs` pooled
  14 pilots into the Track-A headline (+0.001 instead of the published +0.003); pilots now sit in
  `pilots/`, which `discover_runs` (one level deep) structurally cannot reach.
- **P4** `reports/` (tracked evidence, makes README's "committed run log" claim true) · `data/rag/` →
  `indexes/` · `data/wixqa/` → `data/external/` + `scripts/dataset/fetch_wixqa.py` · loose `data/*.jsonl`
  → `data/legacy/` · the 553-line appendix describing T2.9-deleted code → `docs/archive/` with a banner.
- **P5** `tests/rag/` → `tests/tools/rag/`, uniform `__init__.py`, `structure.md` **v3 regenerated from
  the executed tree**, README architecture/usage/config/troubleshooting rewritten (0 references to
  deleted code remain).
- **Deviations from the plan, and why:** (1) `runs_hardtail/` was **NOT deleted** — the audit's "zero
  references" was true of the name but false of the numbers; it is the sole source of the published
  table at `RAG_RELIABILITY_ANALYSIS.md:16-17` (ADR-034 clause 5 amended). (2) Both `runs_orca/` dirs
  kept as evidence, by user decision. (3) The `.gitignore` block from the proposal was **broken as
  written** — gitignore has no trailing-comment syntax, so it silently ignored nothing; verified the
  corrected form with real `git check-ignore` runs.
- **Two root causes fixed rather than patched:** V4's error message told authors to hardcode a seed,
  which would have silently broken the 3-seed protocol — it now names the env-var route, and a new
  `tests/tlw/config/test_experiment_configs.py` (42 cases) validates every shipped config permanently.
  A test that *skipped* when its fixture moved now **fails** on layout drift and skips only when
  `runs/` is absent entirely (fresh clone). `tests/__init__.py` prevents `tests/tools/` from shadowing
  the real `tools/` package.
- **Verified:** 312 tests pass (was 270; +42 new guards), `run.py` works, and Track-A, MedQuAD-RAG,
  WixQA, dose-response and the hard-tail table all reproduce their published values exactly.

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
