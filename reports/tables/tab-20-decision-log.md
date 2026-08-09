**Table 20**

*Decision Log*

|  | date | what was decided | status |
|---|---|---|---|
| ADR-001 | 2026-07-10 | Original results are inflated; model is not the bottleneck | **Accepted** |
| ADR-002 | 2026-07-11 | Two-phase plan: honest research → product | **Accepted** |
| ADR-003 | 2026-07-11 | Architecture: RAG primary + LoRA + loop-as-tool | **Accepted** |
| ADR-004 | 2026-07-11 | Deep-domain choice: Diabetes (leading), Cancer (alt) | Proposed |
| ADR-005 | 2026-07-12 | Build a Dataset Readiness Assessor, not a one-off | **Accepted** |
| ADR-006 | 2026-07-12 | Dataset identified as MedQuAD | **Accepted** |
| ADR-007 | 2026-07-12 | Claude environment as SSOT | **Accepted** |
| ADR-008 | 2026-07-12 | Agent design standard | **Accepted** |
| ADR-009 | 2026-07-12 | Project structure standard | **Accepted** |
| ADR-010 | 2026-07-12 | Unify storage into lightweight SQLite | Proposed (deferred) |
| ADR-011 | 2026-07-12 | Judge model selection | Proposed |
| ADR-012 | 2026-07-12 | Enforcement layer for the Constitution | **Accepted** |
| ADR-013 | 2026-07-12 | Provider/model config: Groq free tier | **Accepted** |
| ADR-014 | 2026-07-12 | Local student = Qwen2.5-7B; judge flips to Llama-70B | Proposed |
| ADR-015 | 2026-07-13 | Renovation plan: hub-and-spoke, P0–P3, six-slot config contract | **Accepted** |
| ADR-016 | 2026-07-13 | Experiment Config Contract v1 (six slots A–F) | **Accepted** (P1 gate, ADR-022; (e): +V8 arm×memory cross-check) |
| ADR-017 | 2026-07-13 | Target architecture v2 & strangler migration policy | **Accepted** (P1 gate, ADR-022) |
| ADR-018 | 2026-07-13 | Honest memory v2: notes-not-answers | **Accepted** (P1 gate, ADR-022; (c): write-gate now = C′/D′ ablation arms, headline all-`none`; (e): thresholds confirmed) |
| ADR-019 | 2026-07-13 | Track-A eval protocol: blind correctness judge, C−B with CI | **Accepted** (P1 gate, ADR-022) |
| ADR-020 | 2026-07-13 | Prompt preset registry v1 (slot C/F curation) | **Accepted** (P1 gate, ADR-022; (f): + `student.orca.*` kept registered, pilot decides) |
| ADR-021 | 2026-07-13 | Crew fitted to the renovation; statistics folded into qa-engineer; P3 roles deferred | **Accepted** (P1 gate, ADR-022) |
| ADR-022 | 2026-07-13 | P1 gate resolutions: blueprint approved, P2 unlocked | **Accepted** |
| ADR-023 | 2026-07-14 | Runner composition root (T2.6): Ollama as "local", `runs/` output, ground_truth scoping | **Accepted** |
| ADR-024 | 2026-07-16 | Track-A verdict: the loop's benefit is self-refinement, not the teacher | Proposed |
| ADR-025 | 2026-07-16 | P3 (Track B) planned: RAG first, then LoRA, gated on the RAG number | **Accepted** |
| ADR-026 | 2026-07-16 | RAG architecture + grounded-QA eval protocol (T3.1, paper) | Proposed |
| ADR-027 | 2026-07-16 | RAG verdict: no NET effect on a 3B, but a real tug-of-war (helps hard, hurts easy) → RAG must be selective | Proposed |
| ADR-028 | 2026-07-23 | LoRA verdict: naive gold-SFT HURTS the 3B (−29pt) — style transfer succeeds but conflicts with the completeness objective | Proposed |
| ADR-029 | 2026-07-24 | MedQuAD RAG "fair-test" exhausted: aspect-rerank + comprehensive corpus BOTH fail → the null is structural, not a retriever/corpus artifact; + orca≈minimal (gate-f closed) | Proposed |
| ADR-030 | 2026-07-24 | WixQA verdict: RAG WORKS when a real knowledge gap exists (+13pt, causally proven to be the retrieved data) — the honest mirror image of the MedQuAD null | Proposed |
| ADR-031 | 2026-07-24 | P3-E launched: prove "retrieval is RAG's bottleneck" via a WixQA dose-response | **Accepted** |
| ADR-032 | 2026-07-24 | Scope correction: run Loop+RAG together (the actual system) before write-up — T3.14 | **Accepted** |
| ADR-033 | 2026-08-06 | PROVEN: RAG's bottleneck is evidence delivery, not the RAG concept — the unified law (T3.12/T3.14) | Proposed |
| ADR-034 | 2026-08-07 | Repository restructure: artifacts leave the source tree, names become readable — supersedes the layout parts of ADR-016/017/023 | **Accepted** (user-approved at the hub) |
| ADR-035 | 2026-08-07 | P3-C launched: build the demo + portfolio narrative (the product half + the story) | **Accepted** |
| ADR-036 | 2026-08-08 | Two documents, no notebook: `README.md` + `docs/EXPERIMENT_RESULTS.md` supersede both the planned narrative notebook and `RAG_LAW.md` | **Accepted** (user decision) |

*Note.* 36 decisions, when each was made and what it settled. Parsed from the project's decision log rather than retyped, so a decision cannot appear in a report without existing in the record that governs the work. Read top to bottom it is the project's actual sequence: what the original results were worth (ADR-001), the two-phase plan that followed, the dataset and rubric choices, the six-slot configuration contract and the memory redesign that made leakage unwritable, the evaluation protocol and its arms, then each result as it landed. Two conventions matter for reading it: an accepted decision is never edited, only superseded by a later one that says why — so a contradiction between two entries is a record of a mind changed by evidence, not an inconsistency. And the `Proposed` entries are findings awaiting ratification, not open questions. Full text with the evidence behind each: `.claude/rules/decisions.md`.
