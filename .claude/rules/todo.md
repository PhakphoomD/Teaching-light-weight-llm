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
- [ ] **T1.1** Config Contract v1 (six slots A–F) → `schema.md` section + ADR *(program-architect)*
- [ ] **T1.2** Target architecture + `structure.md` v2 (seams, strangler migration policy) + ADR *(program-architect)*
- [ ] **T1.3** Honest memory design spec (notes-not-answers, tripwire, MemoryBackend) → `schema.md` *(program-architect + prompt-engineer)*
- [ ] **T1.4** Track-A eval spec (4 arms, judge, seeds, CI, budget) → `docs/plan/EVAL_SPEC.md` *(program-architect + qa)*
- [ ] **T1.5** Prompt catalog — curate ~38 variants → preset registry proposal *(prompt-engineer)*
- [ ] **T1.6** Update `.claude/` crew per T0.2 findings *(project-coordinator)*
- [ ] **T1.7** P1 gate package — consolidate + NEEDS-USER-DECISION list → `docs/plan/P1_GATE_REVIEW.md` *(project-coordinator)*
- [?] ✋ **P1 GATE** — user reviews blueprint at the hub; must decide: Track-A student model
  (Qwen-7B-local vs Llama-8b-continuity), judge mode (blind vs GT-comparing-independent)

## P2: Rebuild Track-A core (code; strangler — legacy stays until T2.9)
- [ ] **T2.1** Config loader + validation (`base.yml`, fail-loud rules incl. §0.2 family check) *(ops/steward)*
- [ ] **T2.2** Registries for all slots (Memory/Preset/Judge; pattern from `providers/factory.py`) *(steward)*
- [ ] **T2.3** Eval block — correctness judge ≠ reference-match diagnostics; leakage tests; calibration *(qa + prompt-engineer)*
- [ ] **T2.4** Loop block v2 — arms A/B/C/D as strategies; NO ground-truth hint paths; mock tests *(steward + prompt-engineer)*
- [ ] **T2.5** Memory block v2 — faiss+none backends, store-time GT tripwire *(data-engineer)*
- [ ] **T2.6** Runner + 4 arm configs + dry run (n=5, train split) *(ops-engineer)*
- [ ] **T2.7** Pilot (n≈25, train) ✅→ full run (held-out 125 × arms × seeds, within Groq caps) *(ops + qa)*
- [ ] **T2.8** Analysis + honest report — **C−B with 95% CI** → `docs/TRACK_A_RESULTS.md` + ADR verdict *(qa)*
- [ ] **T2.9** Demolition — delete DEAD code + legacy core per CODE_MAP; tree = structure v2 *(steward + housekeeping)*

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
