# ADR Log (Architecture Decision Records)

Stable IDs — cite as `ADR-00X`. Status: Accepted unless noted. Numbered in creation order;
newest shown first. Do not edit an Accepted ADR's decision without user approval (§0.6);
supersede it with a new ADR instead.

---

## ADR-015 — Renovation plan: hub-and-spoke, P0–P3, six-slot config contract (2026-07-13) · Accepted
**Context:** results inflated (ADR-001) + structure/todo grown messy; user ordered a disciplined restart ("renovate the old house") — decisions at a hub chat, execution in fresh spoke chats.
**Decision:** (1) **Track A before Track B**; headline = honest loop effect **C − B** with CI. (2) Product models: floor **3B** (Qwen2.5-3B/Llama-3.2-3B class), ceiling **7B**; 1B = stretch only. (3) Sequence **P0 audit → P1 blueprint (docs only) → user gate ✋ → P2 Track-A rebuild (strangler; legacy deleted only in T2.9) → P3 planned after T2.8 results**. Task specs = `docs/plan/` (one file per task); index = `todo.md`. (4) **Six-slot config contract** — A student / B teacher / C preset / D memory / E params / F eval; every slot registry-resolved, layered base+override, no hardcode (formalized in `schema.md` by T1.1). (5) Memory never stores raw ground truth — store-time tripwire (T1.3/T2.5). (6) Loop = offline data-gen/eval **factory**, not a runtime component.
**Evidence:** hub-session audit 2026-07-13 — dead code (0 importers): `src/eval/retrieval.py`, `src/eval/reports.py`, `src/prompts/teacher.py`, `src/simplified/{logger_manager,console_logger}.py` (~1.6k lines); GT-leak paths `simplified_teaching_loop.py` ~358-364/622-740, GT-as-feedback store ~709; config drift `config/simplified_config.yml:45-53`; Assessment-3 PDF (55 pp) reviewed; user approval in hub chat.

## ADR-014 — Local student = Qwen2.5-7B; judge flips to Llama-70B (2026-07-12) · Proposed
**Context:** pick the local student; §0.2 requires judge family ≠ student family.
**Evidence** (`scripts/compare_students.py`, n=6 Diabetes, zero-shot, bias-free MiniLM ref-proximity): `qwen2.5:7b-instruct` beats `llama3.1:8b` — proximity 0.549 vs 0.507, more concise (60 vs 131 words), faster (4.8 vs 8.3 s/q), higher floor (min 0.056 vs −0.011). Matches general Qwen2.5-7B ≥ Llama-3.1-8B benchmarks.
**Recommendation:** **product student = `qwen2.5:7b-instruct` (local)** → measure judge = **Groq `llama-3.3-70b-versatile`** (independent, §0.2). This resolves ADR-011's direction (its Qwen-judge assumed a Llama student). Teacher = either big model.
**Nuance:** Phase-A honest ablation may keep `llama-3.1-8b` as student for continuity with the ADR-001 baseline; the Qwen switch is primarily for the Phase-B product. n=6 = directional; proximity ≠ correctness (ADR-001). Confirm before locking.

## ADR-013 — Provider/model config: Groq free tier (2026-07-12) · Accepted
**Decision:** cloud = Groq **free tier**; enabled models = `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`, `qwen/qwen3-32b`, `qwen/qwen3.6-27b`. Local = Ollama (`qwen2.5:7b-instruct`, `llama3.1:8b`). Role rule (§0.2): **judge family ≠ student family**. Details + rate limits in `providers.md`.
**Consequence:** free-tier daily caps (70B: 1K req/day, 100K tok/day) → batch bulk scoring on 8B/32B; reserve 70B for small eval sets.

## ADR-012 — Enforcement layer for the Constitution (2026-07-12) · Accepted
**Context:** §0 rules (bare-python ban, immutable raw data, logs-as-evidence) were prose only — nothing stopped an agent from violating them; `.claude/CLAUDE.md` itself showed bare-`python` commands.
**Decision:** add an enforcement layer: `.claude/settings.json` (permission denies: edit raw data / `logs/experiments/` / `.env`; allowlist for git-read + tlw python) + `.claude/hooks/guard.py` (PreToolUse: blocks bare `python`/`pip` in command position and writes into immutable/evidence dirs, exit 2 with the rule cited) + `.claude/skills/` (`run-pipeline`, `reconcile-numbers`, `new-adr`). Guard is deliberately narrow (command-position regex) — prefers rare misses over false blocks.
**Evidence:** hooks/permissions schema from code.claude.com/docs (hooks, settings); guard verified 12/12 scenarios via `scratchpad/test_guard.py` run with tlw python.

## ADR-011 — Judge model selection (2026-07-12) · Proposed
**Context:** D4 (dataset answer quality) and Phase-A eval need an LLM judge; §0.2 wants independence from the Llama student/teacher.
**Evidence** (`scripts/compare_judges.py`, n=8 discrimination probe): Groq Llama-3.3-70B vs local Qwen2.5-7B judge **nearly identically** — inter-judge |diff| 0.10; discrimination GOOD−WRONG +0.70 vs +0.68, GOOD−TRUNC +0.40 vs +0.44. Groq ~42× faster (0.07 vs 2.99 s/call).
**Recommendation:** use **local Qwen2.5-7B (Ollama)** as the *measure/eval* judge — different family from Llama (§0.2), free, private, and it judges as well as the 70B. Use **Groq** for throughput-bound *dataset* scoring (D4 over full sets) where independence isn't required. Small sample (n=8) — directional; confirm before locking.

## ADR-010 — Unify storage into lightweight SQLite (2026-07-12) · Proposed (deferred)
**Context:** data is scattered across JSONL + JSON + FAISS + YAML → hard to navigate/query/share.
**Decision (target):** migrate to a single **SQLite** store (`db/`). Chosen for stdlib `sqlite3` (zero install), single portable file, universal familiarity, GUI (DB Browser), pandas-friendly, RAG via `sqlite-vec`. DuckDB = optional analytics companion. See `schema.md` for proposed tables.
**Status:** Proposed — **not implemented; deferred until after the cleaning phase.** JSONL stays source of truth for now. Needs user go-ahead to build.
**Evidence:** DuckDB-vs-SQLite comparisons (SQLite = OLTP app store, universal); `sqlite3` in Python stdlib.

## ADR-009 — Project structure standard (2026-07-12) · Accepted
**Decision:** adopt ML best-practice layout (cookiecutter-data-science + Real Python `src` layout): `data/{raw,interim,processed}`, `src/`, `scripts/`, `tools/`, `tests/` (mirrors src), `models/`, `reports/figures/`, `docs/adr/`, `db/`. Documented in `structure.md`; planned dirs created as needed. **Actual restructuring is incremental — cleaning phase stays the priority; do not churn the tree now.**
**Evidence:** Real Python project-layout guide; cookiecutter-data-science.

## ADR-008 — Agent design standard (2026-07-12) · Accepted
**Context:** first-pass agents were too generic (no output contract, no evidence rule).
**Decision:** every agent uses the skeleton Identity / Must-read / Procedure / Checklist(DoD) / Output-contract / Guardrails. Three output archetypes: **R** (Review: VERDICT+FINDINGS[BLOCKER/MAJOR/MINOR]+NOT VERIFIED+EVIDENCE LOG) for auditors; **B** (Build: SUMMARY/CHANGES/EVIDENCE/VERIFICATION/DECISIONS/NOT-DONE) for makers; **P** (Plan) for the coordinator. Rules gain `§0` anchors + ADR IDs so findings cite authority.
**Evidence:** Anthropic context-engineering ("right altitude"), prompting best practices (role, output contract), 2500-config analysis (commands early).

## ADR-007 — Claude environment as SSOT (2026-07-12) · Accepted
**Decision:** `.claude/` with `.claude/rules/` (auto-loaded) + `.claude/agents/` (8 specialists) + lean `.claude/CLAUDE.md`. Heavy specs (`schema.md`, `rubric.md`) are `paths:`-scoped to save context. **Why:** `.claude/rules/` is first-class + scopable; a custom `rules/` would need manual `@import`.

## ADR-006 — Dataset identified as MedQuAD (2026-07-12) · Accepted
MedQuAD (Ben Abacha & Demner-Fushman, *BMC Bioinformatics* 2019; 47,457 QA, 12 NIH sites; CC BY 4.0). Verbose answers are inherent (auto-extracted NIH sections) → justifies cleaning. "growth_hormone_receptor" is mislabeled = **GHR = Genetics Home Reference**. ⚠️ MedQuAD removed some cancer.gov answers for licensing → verify CancerQA completeness.

## ADR-005 — Build a Dataset Readiness Assessor, not a one-off (2026-07-12) · Accepted
Reusable tool: raw Q&A → cleaned dataset + transparent readiness report (per-target rag/lora/eval). Rubric = DEITA (complexity×quality×diversity) + RAGAS (answerability) + dedup (Lee 2022), config-driven. See `rubric.md`.

## ADR-004 — Deep-domain choice: Diabetes (leading), Cancer (alt) (2026-07-11) · Proposed
Diabetes/Digestive/Kidney (656) is cleanest sizable + coherent + practical. Cancer is punchier but needs Key-Points stripping + has licensing gaps. **Not final — confirm before Phase B.**

## ADR-003 — Architecture: RAG primary + LoRA + loop-as-tool (2026-07-11) · Accepted
LIMA's Superficial Alignment Hypothesis → fine-tuning teaches format/style, not deep knowledge. So **RAG** delivers domain depth; small curated **LoRA** (LIMA 1k / DEITA 6k scale) adds style; the teaching-loop becomes a **data-generation + evaluation** tool.

## ADR-002 — Two-phase plan: honest research → product (2026-07-11) · Accepted
(A) Clean ablation: arms A/B/C/D (baseline / self-refine / blind-teacher / sighted-teacher), held-out set, **independent judge (non-Llama family)**, split correctness vs reference-match. Genuine loop effect = C − B. (B) RAG + LoRA product on cleaned data.

## ADR-001 — Original results are inflated; model is not the bottleneck (2026-07-10) · Accepted
Reported "25%→83%" ≠ committed logs (33%→84%). Metric measures similarity to a noisy reference, not correctness; teacher sees GT every round (guided imitation); "100%" (P6C) = memorization. Baseline Llama-3.1-8B already answers well. Root cause = loop design + evaluation + dataset quality. TinyLlama fails on capability floor, not concept.
