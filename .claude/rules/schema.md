---
paths:
  - "data/**"
  - "scripts/**"
  - "tools/**"
  - "logs/**"
  - "src/**"
---

# Data Contracts (project-wide)

Every data format in the project + where it lives and how it's read/written. Raw data is
immutable (§structure). Future direction: unify into one lightweight store (ADR-010).

## Storage map
| Artifact | Path | Format | Written by | Read by |
|---|---|---|---|---|
| Raw MedQuAD | `data/Medical_Q&A/*.csv`, `data/medical_by_source/*.jsonl` | CSV/JSONL | source | cleaner, runner |
| Cleaned records | `data/clean/*_clean.jsonl` | JSONL | `tools/dataset` | assessor, RAG, LoRA |
| Readiness report | `data/clean/*_report.json` | JSON | assessor | user |
| Memory store | `logs/experiments/*/**.jsonl` | JSONL | `src/simplified/memory.py` | loop |
| FAISS index + ids | `*.index` (binary), `*.ids.json` | FAISS/JSON | memory.py | loop |
| Experiment summary | `logs/experiments/*/summary.jsonl` | JSONL | runner | notebook, docs |
| Per-round debug | `logs/experiments/*/debug_per_round.jsonl` | JSONL | logger | analysis |
| Run debug | `logs/simplified/debug/*.json` | JSON | debug_logger | analysis |
| Configs | `config/*.yml`, `logs/experiments/*/configs/*.yml` | YAML | user/runner | loop |

## Record shapes (current, real)

**Raw MedQuAD** — `{id, question, answer, source|topic}`

**Cleaned record** (non-destructive) —
`{id, domain, question, answer, answer_raw, cleaning_flags[], word_len, is_template, split}`
Rules: keep `answer_raw`; append a `cleaning_flags` entry per transform; `is_template=true` → excluded from `heldout`.

**Memory episode** (`memory.py`) —
`{id(hex), question, teaching_feedback, attempts, success_count, success_rate, scores{exact_match,rouge_l,semantic_sim,blind_score,comparison_score,final}, timestamp}`
Paired with `*.ids.json` (array mapping FAISS row → id) + `*.index` (binary embeddings).
⚠️ `gt_memory_store.jsonl` variant stores the ground-truth **as** `teaching_feedback` ("Reference Answer…") — this is the leakage path (ADR-001, §0.2). Keep it out of any measure-mode run.

**Experiment summary** (`summary.jsonl`, one line per run) —
`{experiment_id, phase, num_questions, passed_count, pass_rate, seed, metrics{exact_match,rouge_l,semantic_similarity,blind_judge,comparison_judge}, avg_rounds, memory_hits, memory_hit_rate, student_tokens_total, teacher_tokens_total, student_teacher_tokens, timestamp, config_used{}}`

**Per-round debug** (`debug_per_round.jsonl`) —
`{phase, experiment_id, question_id, question_idx, round, question, answer, scores{}, final_score, passed, memory_used, time_ms, timestamp}`

**Readiness report** — see `rubric.md` (dimensions{score,band}, volume, overall, verdict, before/after, fixes).

## Future: unified lightweight store — SQLite (ADR-010, Proposed)
**Why:** data is scattered across JSONL + JSON + FAISS + YAML → hard to navigate, query, and hand to others. A single DB is easier for everyone.
**Choice:** **SQLite** — in Python **stdlib** (`sqlite3`, zero install), single portable file, universally known, GUI via DB Browser, trivial `pandas.read_sql`/`to_sql`, and RAG vector search via the light `sqlite-vec` extension. (DuckDB = optional analytics companion; can query the same files for heavy aggregation.)
**Proposed tables:** `records`(cleaned Q&A), `memory_episodes`, `experiments`, `rounds`, `readiness_reports`, `embeddings`(vec). JSONL stays the source of truth until migration; **migration is deferred until after the cleaning phase** (todo).

---

# Experiment Config Contract v1 (six slots A–F) — ADR-016, Accepted (P1 gate, ADR-022)

**One run = one config file = six slots, each resolved through a registry, defaults layered, nothing hardcoded.** This is the backbone of every P2 block (T2.1–T2.6) and of future fine-tuning work: swap models / memory / presets / judges by editing YAML only. Loader + validation are **implemented in T2.1** — this section is the spec they must satisfy.

**Why now (drift this kills):** the current `config/simplified_config.yml` already rotted — the metric-weights comment (`config/simplified_config.yml:45-46`) claims `comparison(0.3), semantic(0.2), exact(0.1)` while the live dict (`config/simplified_config.yml:47-53`) is `comparison_score: 0.35, semantic_sim: 0.25`, `exact_match` commented out (§0.1 doc/value drift, per LEAKAGE_AUDIT §2); the eval `pass_threshold` hides under `teacher:` (`config/simplified_config.yml:27`) instead of under eval; and historical run configs hardcode a stale absolute path outside the repo root (`logs/experiments/phase6/configs/P6A-NoMemory-Baseline.yml:42-43`, §0.3). The contract fixes each structurally: single source of defaults, thresholds owned by slot F, path resolution in the loader.

## Slot table

| Slot | Key | Required keys | Optional keys | Types / allowed values | Resolved by |
|---|---|---|---|---|---|
| **A** | `student` | `provider`, `model` | `temperature`, `max_tokens`, `timeout` | `provider ∈ {local, groq, gemini}`; `model` = provider-known name string; `temperature` float ≥0; `max_tokens` int >0 | **ProviderRegistry** (generalize `src/providers/factory.py:6-21` — `build_client(provider, **kwargs)`) |
| **B** | `teacher` | `provider`, `model` | `temperature`, `max_tokens`, `timeout` | same domain as A. Teacher **may see GT** for feedback generation (§0.2 legal use) | **ProviderRegistry** |
| **C** | `preset` | `student`, `teacher` | — | preset **name** strings (e.g. `minimal`, `orca`, `cot`) → looked up, not inline prompt text | **PresetRegistry** (new; wraps `src/utils/prompt_loader.py` catalog — names defined by T1.5) |
| **D** | `memory` | `type` | `embedding`, `top_k`, `similarity_threshold` | `type ∈ {faiss, rag, none}`; `embedding` = encoder name (e.g. `minilm`); `top_k` int >0; `similarity_threshold` float 0–1 | **MemoryRegistry** (new; `MemoryBackend` interface — `none`=disabled, `faiss`=current `src/simplified/memory.py`, `rag`=future) |
| **E** | `params` | `seed`, `arm` | `max_rounds`, `early_stopping{}` | `seed` int (**mandatory**, §0.3); `arm ∈ {A, B, C, D}` (ADR-002 arms) → **StrategyRegistry**; `max_rounds` int >0 | **StrategyRegistry** (arm → loop strategy, new in T2.4) |
| **F** | `eval` | `judge{provider,model}`, `mode` | `pass_threshold`, `metrics{weights{}}` | `judge` = same domain as A/B; `mode ∈ {blind, gt_comparing}`; `pass_threshold` float 0–1; `weights` = metric→float map | **ProviderRegistry** (judge client) + eval block. **Thresholds live HERE, never under `teacher:`** |

Notes: `params.arm` selects the ADR-002 arm strategy (A baseline / B self-refine / C blind-teacher / D sighted-teacher). No slot G+ — extend the contract only when a real need arrives (YAGNI, ADR-015).

## Full annotated example (an experiment override file)

```yaml
# experiments/trackA_p2_armC_diabetes.yml
# Run: run.py --config experiments/trackA_p2_armC_diabetes.yml
# Only the diffs from config/base.yml appear here.

student:  { provider: local,  model: qwen2.5:3b }          # A — answerer under test (product floor 3B, ADR-015)
teacher:  { provider: groq,   model: llama-3.3-70b }       # B — feedback generator (may see GT, §0.2 legal)
preset:   { student: minimal, teacher: orca }              # C — preset NAMES → PresetRegistry (no inline prompts)
memory:   { type: faiss, embedding: minilm, top_k: 3 }     # D — type → MemoryRegistry (faiss|rag|none)
params:   { arm: C, max_rounds: 3, seed: 42 }              # E — arm strategy + loop params; seed MANDATORY (§0.3)
eval:                                                       # F — judge + thresholds live HERE, not under teacher
  judge: { provider: groq, model: llama-3.3-70b }          #     judge family (Llama) ≠ student family (Qwen), §0.2
  mode: blind                                              #     blind = judge never sees GT (measures learning)
  pass_threshold: 0.7
  metrics:
    weights: { blind_score: 1.0 }                          #     weights must sum to 1.0 ± ε (validated, T2.1)
```

## Layering rules

1. **`config/base.yml` holds ALL defaults** — the single source of truth for every slot key. This kills comment-drift: there is exactly one place a default lives, so a comment can never disagree with a value the way `config/simplified_config.yml:45-53` does today.
2. **Experiment files (`experiments/*.yml`) override only diffs** — they contain just the keys that differ from base. A reader sees the experiment's *intent* at a glance, not a 127-line wall.
3. **Merge order (last wins):** `config/base.yml` → `experiments/<file>.yml` → `EXPERIMENT_*` environment overrides. Deep-merge per slot (an experiment that sets only `memory.top_k` keeps base's `memory.type`).
4. **Env overrides** — `EXPERIMENT_*` variables map to dotted paths (e.g. `EXPERIMENT_PARAMS_SEED=7` → `params.seed`), for sweeps/CI without editing files. This generalizes the existing `EXPERIMENT_DIR/PHASE/NAME` convention (`config/simplified_config.yml:105`).
5. **The fully-merged, resolved config is recorded with the run** (into `summary.jsonl`'s `config_used{}`, per this file's Experiment-summary shape) so every number is reproducible from its exact config (§0.3, §0.4).

## Validation rules (specified now, implemented in T2.1 loader — fail-loud)

- **V1 — Metric weights sum to 1.0 ± ε** (ε = 1e-6). `sum(eval.metrics.weights.values())` must ≈ 1.0. Prevents silent mis-scaling; documents intent explicitly instead of relying on runtime normalization (LEAKAGE_AUDIT §2 notes `metrics.py` normalizes anyway, which *masks* a wrong config — validation surfaces it).
- **V2 — Judge family ≠ student family (§0.2).** Families per `providers.md`: **Llama** = {`llama3.1:8b`, `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`}; **Qwen** = {`qwen2.5:7b-instruct`, `qwen2.5:3b`, `qwen/qwen3-32b`, `qwen/qwen3.6-27b`}. `family(eval.judge.model)` must ≠ `family(student.model)`. Fail-loud at load (LEAKAGE_AUDIT seal #5). Teacher family is unconstrained (it is not the measurement).
- **V3 — Unknown keys rejected.** Any key not in the slot table above → hard error (no silent typo-drift; a mistyped `pass_treshold` must fail, not vanish).
- **V4 — `seed` mandatory for experiment runs (§0.3).** Missing `params.seed` → hard error. Reproducibility is non-negotiable.
- **V5 — `eval.pass_threshold` must live under slot F only.** A `pass_threshold` (or any threshold) appearing under `teacher:` → hard error, pointing the author to slot F. Directly retires the `config/simplified_config.yml:27` misplacement.
- **V6 — Memory-store denylist (§0.2, LEAKAGE_AUDIT seal #6).** `memory` storage paths matching `phase6` / containing `gt_memory` / `ground_truth` in the filename → hard error (quarantines GT-seeded historical artifacts from any measured run).
- **V7 — Enum/type validation** per the slot table: `provider`, `memory.type`, `params.arm`, `eval.mode` must be in their allowed sets; numeric ranges enforced (`0 ≤ threshold ≤ 1`, `top_k > 0`, `max_rounds > 0`).
- **V8 — Arm×memory cross-check (P1 gate (e), ADR-022).** `params.arm ∈ {A, B}` REQUIRES `memory.type: none` — a measured baseline must not accumulate notes; any other combination → hard error naming this rule. For arms C/D both values are legal but mean different experiments: `none` = the **headline** run (ADR-022 (c)); `faiss` = the **C′/D′ memory-on ablation** — the runner records which in the run id/summary so the two can never be conflated (§0.1).

## Naming convention

`experiments/<track><phase>_<arm>_<slug>.yml` — e.g. `experiments/trackA_p2_armC_diabetes.yml`.
- `<track>` = `trackA` | `trackB`; `<phase>` = `p2`, `p3`, …; `<arm>` = `armA`..`armD` (ADR-002); `<slug>` = short domain/variant tag.
- `config/base.yml` is the only non-experiment config; it carries defaults, never a full experiment identity.

---

# Memory v2 contract (honest memory: notes-not-answers) — ADR-018, Accepted (P1 gate, ADR-022)

**One core rule: memory stores what *worked* (reusable teaching notes), never the *answer*.** This is the structural fix for ADR-001's "100% = the system quoting its own answer key" and for the always-on retrieval leak (LEAKAGE_AUDIT L4/L6). It is slot **D** of the Config Contract, realized through the **MemoryBackend** seam (`structure.md` §D:111). Interface + tripwire are **implemented in T2.5**; this section is the spec they must satisfy. Deliberately single-user, single-machine, local-first (no multi-user/prod scale, per T1.3 Must-NOT).

**Why the old shape was unsafe.** Today `FAISSMemory` stores a free `teaching_feedback` string with **no content check** (`src/simplified/memory.py:305-395` store; `:237-303` `get_best_feedback`), and the loop injects it into a student prompt in round 1 unconditionally (`simplified_teaching_loop.py:295-300, 368-376`). So any GT-bearing string — whether seeded (`logs/experiments/phase6/gt_memory_store.jsonl`, L18), echoed by a teacher template (L7), or promoted from a last-chance pass (L4) — becomes a persistent, retrievable answer key that "leaks forward in time" across runs (LEAKAGE_AUDIT §4 Trace B, confirmed `phase6/summary.jsonl` P6C `memory_hit_rate:1.0, pass_rate:1.0`). v2 makes that shape *impossible to write*.

**What to keep from v1.** The success-aware ranking (`success_rate > final_score > attempts`, `src/simplified/memory.py:282-291`), FAISS `IndexFlatIP` cosine search over normalized MiniLM embeddings (`:104-105, 168-183`), embedding-hash ids (`:185-198`), and JSONL-for-inspection persistence are good ideas and are retained. What changes is **the payload** (a bounded teaching note, never GT) and **the write path** (a store-time tripwire + arm gating).

## 1. Episode schema v2

A memory episode is a *note about how to coach*, keyed by the question it came from. Inspired by A-MEM (arXiv 2502.12110) — memory as linked, tagged notes (keywords + links between related notes) rather than raw text dumps — adapted down to one local store; and by "From RAG to Memory" / HippoRAG 2 (arXiv 2502.14802) — memory as a non-parametric retrieval store, not model weights. Adapted, not copied: we keep A-MEM's *keywords + links* idea but drop its LLM-driven memory-evolution loop (YAGNI for a single local store, ADR-015).

```jsonc
{
  "id": "a1b2c3d4e5f6a7b8",          // hex16 = sha256(question_embedding)[:16] — dedup key (v1 scheme kept)
  "question": "What raises blood sugar after meals?",  // source question (retrieval anchor; NOT the answer)
  "embedding_key": "minilm/a1b2c3d4e5f6a7b8",          // <encoder>/<id> — which encoder produced the vector (vector lives in *.index)
  "teaching_note": "Anchor the reply to the post-prandial mechanism and name 2-3 concrete\ncontributors; the passing answer stayed under ~80 words and led with the mechanism, not a list.",
    // ^ STRATEGY / CRITIQUE THAT WORKED — the coaching move, never the reference answer text. See §2 forbidden-content rule.
  "tags": ["diabetes", "mechanism-first", "concise"],   // keywords for filtering / future graph grouping (A-MEM style)
  "links": ["9f8e7d6c5b4a3210"],     // ids of related episodes (same topic/strategy) — optional, for future graph retrieval
  "stats": {
    "attempts": 3,                   // times this note was used/updated
    "success_count": 2,
    "success_rate": 0.67,            // success_count / attempts — primary ranking key (v1 idea kept)
    "best_final_score": 0.81         // best diagnostic final_score seen with this note (secondary ranking key)
  },
  "provenance": {
    "run_id": "trackA_p2_armC_diabetes__seed42",  // which experiment run wrote it (traceability, §0.4)
    "arm": "C",                      // arm strategy that produced it — only memory-on C′/D′ runs may write (§5 gate, ADR-022 (c))
    "teacher_model": "groq/llama-3.3-70b",        // model whose feedback the note distills
    "created": "2026-07-13T10:00:00", // ISO-8601
    "updated": "2026-07-13T10:05:00"
  }
}
```

Field notes:
- **`teaching_note`** replaces v1's `teaching_feedback`. It is a *distilled coaching move* (what strategy/critique moved the answer toward passing) — imperative, generalizable, and **content-restricted by §2**. It is **not** the teacher's raw feedback string (which may quote GT, L7) and **not** the reference answer.
- **`embedding_key`** namespaces the vector by encoder so a future encoder swap (slot D `embedding`) can't silently mix incompatible vectors — the FAISS index is rebuilt per encoder (matches v1 rebuild-from-question behavior, `src/simplified/memory.py:117-166`).
- **`links`** is optional and unused by the `faiss` backend's core retrieval in v2; it is reserved for the future `rag` backend's graph grouping. Present in schema so we don't need a migration later (design the seam now, build later — ADR-015).
- **`provenance`** is new and mandatory: it makes every stored note traceable to the run/arm/teacher that created it (§0.4), and it is what the arm-gate (§5) and audits check.
- Storage: JSONL at a per-run path (`memory_episodes.jsonl`) + paired `*.index` / `*.ids.json`, same trio as v1 (this file's Storage map). The `gt_memory_store.jsonl` shape is **retired** — v2 has no field that can hold a reference answer.

## 2. Forbidden-content rule (as schema) — the store-time tripwire

**Hard schema invariant:** `teaching_note` MUST NOT contain the reference answer, verbatim or near-verbatim. This is not advisory prose — it is a **write-time gate inside `MemoryBackend.store()`** that rejects any offending episode and logs it. Seals LEAKAGE_AUDIT L4, L6 (memory side), L7 (memory side), L8, L18 structurally (a compliant store *cannot* persist an answer key). Test lands in **T2.5** (unit) + **T2.3** (integration), per LEAKAGE_AUDIT seal #2.

**Preferred design — GT never enters memory's call signature.** The cleanest guarantee is that `store()` does **not accept `ground_truth` as a parameter at all** (contrast v1, whose caller passes GT-bearing strings freely). The loop distills a note *before* calling memory; the tripwire below is defense-in-depth for when GT is available at the call site (e.g. arm D) and must be checked against.

**Tripwire (runs at every `store()`), given the note text `n` and the run's ground-truth `g` (when available):**

| Check | Rule | On fail |
|---|---|---|
| **T-1 Substring** | normalized `g` (lowercased, whitespace/punct-collapsed) is NOT a substring of normalized `n`; and no contiguous **≥ 12-token** shingle of `g` appears in `n` | reject write |
| **T-2 Near-duplicate similarity** | `cosine(embed(n), embed(g)) < 0.80` (MiniLM, same encoder as retrieval) | reject write |
| **T-3 Length/verbatim smell** | `n` is not ≥ 0.60·len(`g`) AND ≥ 0.90 token-overlap with `g` (catches lightly-reworded full answers that dodge T-1) | reject write |

- **On any fail:** the episode is **not written**; the backend logs a structured rejection `{event:"memory_reject", reason:"T-1|T-2|T-3", run_id, question_id, note_hash}` to the run's memory log (never the note or GT text itself — don't re-leak into logs). The loop continues without a stored note (a rejected note is a bug in note-distillation, surfaced loudly, §0.1).
- **Thresholds are config-visible** (slot D optional keys, defaulted in `base.yml`): `gt_substring_shingle: 12`, `gt_similarity_max: 0.80`. Defaults are deliberately strict; T2.5 calibrates against the phase6 GT corpus as a red-team fixture (a known answer key must be rejected 100% of the time — that is the acceptance test).
- **Scope limit:** the tripwire proves a note is *not the answer*; it cannot prove a note is *useful*. Usefulness is measured downstream by `success_rate` (§3/§4), not here.

## 3. Retrieval contract

`retrieve(query, top_k)` returns **guidance notes only**, ranked, and its output is injected **only into refinement-round prompts, never presented as answer text**. Mirrors LEAKAGE_AUDIT seal #1 (no student-bound prompt may contain GT — and a v2 note structurally cannot).

1. **Search:** embed `query` (same encoder as store), FAISS top-k over the index (v1 `search`, `src/simplified/memory.py:200-235`).
2. **Similarity floor:** keep only candidates with `cosine ≥ similarity_threshold` (slot D, default 0.75 — v1 default kept).
3. **Success gate:** drop candidates with `stats.success_rate < min_success_rate` (default 0.30 — v1 idea kept). A note that has not helped is not offered.
4. **Rank (unchanged from v1, the part worth keeping):** sort by `success_rate` desc → `best_final_score` desc → `attempts` desc → `similarity` desc.
5. **Return** the top note(s) as `{id, teaching_note, success_rate, best_final_score, attempts, similarity}`. The caller (loop) may inject `teaching_note` into a **refinement** prompt's guidance slot **only**. It is never used to build a first-attempt answer verbatim, never concatenated as "the answer is…", and never shown when `arm ∈ {A, B}` (§5).
6. **Empty is normal:** no candidate clears the floor/gate → return `[]`; the round proceeds with no memory hint (memory is an aid, not a dependency).

## 4. `MemoryBackend` interface (slot D seam)

Method names align **exactly** with `structure.md` §D:111 (the seam is authoritative; T2.5 finalizes signatures):

| Method | Purpose | Contract |
|---|---|---|
| `store(episode)` | Persist one episode v2 | Runs the §2 tripwire first; rejects (no write) + logs on fail. Dedups by `id` (update if same question, per v1 `store` update/create logic `src/simplified/memory.py:328-395`). **Does not accept `ground_truth` as a stored field.** Returns `id` or `None` (rejected). |
| `retrieve(query, top_k)` | Get ranked guidance notes | Implements §3. Returns a list (possibly empty). Never returns raw GT (guaranteed by §2 at write time). |
| `update_outcome(id, scores)` | Record whether a retrieved note helped | Updates `stats` (`attempts`, `success_count`, `success_rate`, `best_final_score`) — generalizes v1 `update_success` (`src/simplified/memory.py:397-437`). No new vector. |
| `stats()` | Store health | Returns `{total_episodes, total_attempts, overall_success_rate, index_size, rejects}` — extends v1 `get_stats` with a `rejects` counter (§2 observability). |

- **Registry (slot D):** `MemoryRegistry`, `type ∈ {none, faiss, rag}` (Config Contract slot D table; registry pattern = copy `src/providers/factory.py`, `structure.md` §D:116).
  - **`none`** — disabled backend: `retrieve` always returns `[]`, `store` is a no-op. This is the backend for the **no-memory baseline arms** (see §5) and makes "memory off" a first-class, testable config rather than a magic `top_k ≤ 0` guard (v1 hack, `src/simplified/memory.py:214-217`).
  - **`faiss`** — the v2 store above; a port of `src/simplified/memory.py` with the payload/tripwire/arm-gate changes.
  - **`rag`** — future (Track B): same interface, retrieval over the domain corpus + notes; may use `links`/`tags`. Not built in P2.
- All three satisfy the same interface, so the loop and runner depend only on the seam (blocks never import a concrete backend — `structure.md` §C:88-89).

## 5. Lifecycle (write gating, isolation, drift control)

- **Arm write-gate (§0.2, the honest-measurement rule) — reconciled to the P1 gate (ADR-022 (c)):** whether memory *writes* is a property of the run, enforced at the seam, not left to prompt discipline:
  - **Headline runs (arms A, B, C, D)** — memory **type = `none`** for ALL four arms: never read, never write. C−B therefore isolates *teacher feedback* over plain self-refinement with zero cross-question confound (kills L6 in the headline by construction).
  - **Memory-on ablation (C′/D′)** — arm C/D strategies re-run with **type = `faiss`**: write teaching notes (subject to §2 tripwire) and read them in refinement rounds. **Memory's marginal value = C′ − C** — its own honest number, measured separately.
  - The gate is structural: an Arm-A/B run configured with `memory.type: faiss` **fails validation** — adopted as Config Contract **V8** at the P1 gate (ADR-022 (e)).
- **Per-experiment isolation (§0.3).** Each run gets a **fresh, empty store by default** — path derived from `run_id` (e.g. `logs/experiments/<run>/memory_episodes.jsonl`), created empty at start. No cross-run contamination: this is the direct antidote to Trace B "leak forward in time." A run may opt into a *seed store* only via an explicit config key (`memory.seed_from: <path>`), which is itself subject to the §2 tripwire on load **and** the Config Contract V6 denylist (no `phase6`/`gt_memory`/`ground_truth` paths). Default = no seed.
- **Capacity / eviction (drift control).** Optional `memory.max_episodes` (slot D, default e.g. 1000 — ample for one domain, one run). On overflow, evict by **lowest utility** = `(success_rate, attempts)` ascending (drop notes that never helped first), never by recency alone (a proven note must outlive a fresh useless one). For P2 measured runs (heldout 125 × arms × seeds) the cap is rarely hit; it exists so an unbounded store can't silently degrade retrieval quality.
- **Update flow.** On a passing refinement that used a retrieved note → `update_outcome(id, scores)` bumps `success_count`/`success_rate`. On a new passing (C/D) round → `store(episode)` with the distilled note (tripwire-checked). Failures do **not** store a note in v2 (contrast v1's unconditional store-on-failure, `simplified_teaching_loop.py:748-759`, which is exactly how bad/GT strings persisted) — only notes that *worked* earn a place.

## Alignment recap (what this seals / satisfies)

- LEAKAGE_AUDIT seal #2 (store-time tripwire) → §2; seal #1 (no GT in student prompts) → §3 (notes are structurally GT-free); seal #6 (historical-artifact quarantine) → §5 seed-store + Config V6.
- Config Contract slot D (`type ∈ {faiss, rag, none}`, `embedding`, `top_k`, `similarity_threshold`) → §4 backend + §3 retrieval; adds optional `min_success_rate`, `max_episodes`, `gt_similarity_max`, `gt_substring_shingle`, `seed_from`.
- `structure.md` §D MemoryBackend seam (`store`/`retrieve`/`update_outcome`/`stats`) → §4, names matched exactly.
- ADR-001 root cause (memory-as-answer-key) → retired by §1 payload change + §2 invariant + §5 store-only-what-worked.

---

# Slot-D `rag` backend contract (RAG retrieval) — ADR-026, Proposed (full spec: `docs/protocol/2026-07-16-rag-medquad-protocol.md`)

**The third `MemoryBackend` implementation (`type: rag`) — a corpus-backed, read-only retriever, not a note store.** `rag` is reserved-but-unregistered in `src/tlw/registries.py:16` (a `rag` run fails loud until T3.3 builds it). It satisfies the **same MemoryBackend seam** (`store`/`retrieve`/`update_outcome`/`stats`, `src/tlw/registries.py:75-100`) so the T2.6 runner is unchanged — the loop just injects the returned passages at the first answer attempt instead of a refinement round. Built by T3.3; corpus/index built by T3.2. This section is the spec they satisfy; the honesty/eval design lives in `docs/protocol/2026-07-16-rag-medquad-protocol.md`.

## How `rag` differs from `faiss` (both are slot D)
| Aspect | `faiss` (memory, ADR-018) | `rag` (ADR-026) |
|---|---|---|
| Payload | teaching **notes** distilled from feedback, written during the run | domain **passages** (TRAIN answers), built ONCE offline, read-only at run time |
| `store()` | writes tripwire-checked notes | **no-op** (returns `None`) — corpus immutable during a run |
| `retrieve()` returns | `{id, teaching_note, success_rate, …}` | `{id, passage, question, similarity, source_id}` |
| Injection point | refinement rounds only (Memory v2 §3) | **first answer attempt** (grounding) + carried through refinement |
| Corpus | empty per-run store, `run_id`-isolated | prebuilt index from `data/clean/…_train.jsonl` via `corpus_path`; **held-out excluded** |
| Retrieval key | question → note | question → question (return the matched train record's **answer** as passage) |

## Slot-D keys `rag` uses
Reuses `type`, `embedding` (`minilm`, same encoder), `top_k` (default 3), `similarity_threshold` (**default 0.35 — deliberately lower than memory's 0.75**; RAG wants *related* context, not a near-exact question twin). Adds two **`rag`-only optional keys**: `corpus_path` (path to the T3.2 index dir; carries a build manifest of indexed ids) and `max_passage_words` (default 150; sub-chunk cap, only if sub-chunking is enabled).

## Anti-leak invariants (rag-medquad-protocol §5 — the honesty seals, analogues of memory's tripwire)
- **RAG-L1 — corpus = TRAIN split only.** The held-out 125 must NEVER be indexed. T3.2 writes a build manifest of every indexed `id`; it must contain **zero** held-out ids. A `corpus_path` whose manifest reports a held-out id → hard validation error (a slot-D analogue of Config Contract **V6**).
- **RAG-L2a — cosine near-dup scrub.** T3.2 drops any train record whose `question` OR `answer` is ≥ 0.90 cosine (MiniLM, rubric D3) to any held-out record (semantic twins).
- **RAG-L2b — verbatim-block scrub (added 2026-07-16).** Whole-answer cosine is blind to *templated* leaks — MedQuAD's "What to do for X?" answers reuse one NIH advice template across GI diseases (Crohn's vs Ulcerative Colitis: ~100% shared verbatim text yet only ~0.76 cosine). So T3.2 ALSO drops any train record sharing **≥ 8 contiguous 12-token shingles** with any held-out answer (`--block-shingle-min`, default 8). This is the seal that removes template answer-by-proxy leaks.
- **RAG-L3 — run-time per-passage filter.** `grounding_block(...)` (`src/tlw/loop/core.py`) drops+counts any retrieved passage that still shares a ≥12-token shingle with the held-out gold, then grounds on the survivors — it does NOT abort the run (hub decision 2026-07-16). This handles the residual innocent case: same-topic passages share a single definitional sentence with the gold without being the answer. Dropped-passage count is reported (`grounding_filtered_total`, §0.1). `assert_gt_free` remains the final whole-prompt backstop (aborts only if gold reaches a prompt through any path).
- **RAG-L4 — judge stays blind.** Blind correctness (`BlindJudge`, `src/tlw/evaluation/judge.py:128`, PASS ≥ 4) is the headline, unchanged from Track A. Faithfulness (RAGAS groundedness, rag-medquad-protocol §4.2) sees passages but never gold, is a NEW judge mode (not the unbuilt `gt_comparing`), and is a **diagnostic column only — never the pass gate**.

## V8 exemption (flag to T2.1 owner)
Config Contract **V8** forbids arms A/B + accumulating memory (`faiss`). `type: rag` is a read-only corpus, not a note-accumulating store, so it does **not** create the "baseline that learns" problem V8 exists to stop — the RAG headline arms answer single-pass (`arm: A`, `max_rounds: 1`) *with* `type: rag`. T3.3 adds a one-line V8 exemption: `arm ∈ {A,B}` requires `memory.type ∈ {none, rag}` (rag allowed, faiss still forbidden).
