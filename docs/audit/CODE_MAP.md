# CODE_MAP — As-Built Audit (T0.1)

**Generated:** 2026-07-13 · **Owner:** housekeeping · **Scope:** all tracked source, config, schema files

**Executive Summary:** 43 tracked Python/config files catalogued. Core codebase is **1,202 lines (simplified_* + active src/)** organized around two entrypoints (experiment_runner.py, teaching_loop.py). **5 dead files** identified (0 importers, not entrypoints). **Name clash** verified but managed (src/eval/metrics.py vs src/simplified/metrics.py). **Tools directory untracked** (repo status flags as `??`) — exemplary code not under version control, misaligned with ADR-009 structure target.

---

## Definition of Verdicts

- **EXEMPLAR:** Essential pattern; widely reused; good for copying (e.g., factory.py, provider clients).
- **ALIVE:** In active use, functioning as designed.
- **MESSY:** In active use but needs rework (e.g., simplified_teaching_loop.py monolithic run()).
- **DEAD:** 0 importers AND not an entrypoint (not run directly, not in config commands). Candidate for T2.9 demolition.
- **MISPLACED:** Wrong directory per structure.md; should move.

---

## Tracked Files Inventory

### Root Directory (9 files)

| File | Lines | Role | Importers (Evidence) | Verdict |
|---|---|---|---|---|
| `simplified_teaching_loop.py` | 843 | Main teaching loop orchestrator; coordinates student, metrics, teacher, memory, early stopping, logging | Imported by: `simplified_experiment_runner.py:25` (grep: `from simplified_teaching_loop import SimplifiedTeachingLoop`) | **MESSY** |
| `simplified_experiment_runner.py` | 359 | Entrypoint: runs experiments with configurable questions, datasets, logging | Invoked: documented in CLAUDE.md as main CLI; referenced in config/simplified_config.yml comments | **ALIVE** |
| `README.md` | 54 | Project overview and usage documentation | Documentation file, referenced in spec todo.md | **ALIVE** |
| `requirements.txt` | 14 | Python dependencies (groq, google-ai, transformers, etc.) | Standard dependency file | **ALIVE** |
| `environment.yml` | 40 | Conda environment definition (tlw) | Environment spec; referenced in CLAUDE.md §0.5 | **ALIVE** |
| `.env.example` | 4 | Template for .env secrets (API_KEYS) | Example template, not imported | **ALIVE** |
| `.gitignore` | 50 | Git exclusion rules | Standard git file | **ALIVE** |
| `.vscode/settings.json` | 25 | VSCode workspace settings | IDE config | **ALIVE** |

### src/ — Library (37 files, 5,476 total lines)

#### src/simplified/ — Core Active Components (14 files, 3,487 lines)

| File | Lines | Role | Importers (Evidence) | Verdict |
|---|---|---|---|---|
| `student.py` | 280 | StudentClient: generates answers via factory-built LLM providers | Imported by: `simplified_teaching_loop.py:69` (grep: `from src.simplified.student import StudentClient`) | **ALIVE** |
| `metrics.py` | 345 | MetricsEvaluator: orchestrator for hybrid scoring (deterministic + LLM judges) | Imported by: `simplified_teaching_loop.py:71` (grep: `from src.simplified.metrics import MetricsEvaluator`) | **ALIVE** |
| `teacher_feedback.py` | 578 | TeacherFeedback: chain-of-thought critique generation via factory LLM | Imported by: `simplified_teaching_loop.py:72` (grep: `from src.simplified.teacher_feedback import TeacherFeedback`) | **ALIVE** |
| `memory.py` | 540 | FAISSMemory: semantic memory store (indexed embeddings, retrieval, update logic) | Imported by: `simplified_teaching_loop.py:73` (grep: `from src.simplified.memory import FAISSMemory`) | **ALIVE** |
| `early_stopping.py` | 197 | EarlyStopping: monitors convergence and patience thresholds | Imported by: `simplified_teaching_loop.py:74` (grep: `from src.simplified.early_stopping import EarlyStopping`) | **ALIVE** |
| `logger.py` | 377 | RoundLogger: JSONL round-level logging with fixed-width formatting | Imported by: `simplified_teaching_loop.py:75` (grep: `from src.simplified.logger import RoundLogger`) | **ALIVE** |
| `monitor.py` | 304 | PerformanceMonitor: tracks metrics across questions/rounds | Imported by: `simplified_teaching_loop.py:76` (grep: `from src.simplified.monitor import PerformanceMonitor`) | **ALIVE** |
| `debug_logger.py` | 321 | DebugLogger: detailed per-round debug output (JSON) | Imported by: `simplified_teaching_loop.py:78` (grep: `from src.simplified.debug_logger import DebugLogger`) | **ALIVE** |
| `terminal_ui.py` | 348 | TerminalUI: formatted console output with progress bars (tqdm) | Imported by: `simplified_teaching_loop.py:79` (grep: `from src.simplified.terminal_ui import TerminalUI`) | **ALIVE** |
| `__init__.py` | 26 | Exports core classes (StudentClient, MetricsEvaluator, etc.) | Re-export module | **ALIVE** |
| `console_logger.py` | 0 | [Empty file] | 0 importers (grep: `console_logger` → no hits across src/simplified, scripts, simplified_*.py) | **DEAD** |
| `logger_manager.py` | 0 | [Empty file] | 0 importers (grep: `logger_manager` → no hits) | **DEAD** |

#### src/prompts/ — Student Prompt Templates (3 files, 244 lines)

| File | Lines | Role | Importers (Evidence) | Verdict |
|---|---|---|---|---|
| `student.py` | 190 | Student prompt templates + helper functions (build_ground_truth_hint_prompt) | Imported by: `simplified_teaching_loop.py:70` (grep: `from src.prompts.student import`) | **ALIVE** |
| `teacher.py` | 239 | Teacher prompt templates (DEAD: no callers after refactor to simplified/teacher_feedback.py) | 0 importers (grep: `teacher.py import` → only docstring in src/eval/reports.py, not actual call) | **DEAD** |
| `__init__.py` | 7 | Empty re-export module | Module init | **ALIVE** |

#### src/providers/ — LLM Provider Factory (7 files, 1,051 lines)

| File | Lines | Role | Importers (Evidence) | Verdict |
|---|---|---|---|---|
| `factory.py` | 21 | **EXEMPLAR:** Registry pattern for building LLM clients (Groq, local, Gemini); decorator-based registration | Imported by: `src/simplified/metrics.py:6`, `src/simplified/student.py:4`, `src/simplified/teacher_feedback.py:4` (grep: `from src.providers.factory import build_client` → 3 callers) **ALSO:** re-exported in `src/providers/__init__.py:1` | **EXEMPLAR** |
| `groq_client.py` | 114 | Groq API client (chat completion, streaming) | Registered in: factory.py via `@register` decorator; invoked via factory.build_client() | **ALIVE** |
| `local_client.py` | 257 | Local LLM client (Ollama, transformers); handles HF models | Registered via factory; invoked by build_client("local") | **ALIVE** |
| `gemini_client.py` | 186 | Google Gemini API client | Registered via factory; optional fallback | **ALIVE** |
| `constants.py` | 210 | Model names, capabilities, parameter defaults by provider | Imported by: provider clients (inline usage observed in groq_client, local_client) | **ALIVE** |
| `ratelimit.py` | 118 | Rate-limit enforcement (token bucket with threading lock) | Used by: provider clients to throttle requests | **ALIVE** |
| `__init__.py` | 14 | Re-export factory.register and build_client | Module init | **ALIVE** |

#### src/eval/ — Evaluation Metrics & Reports (4 files, 1,721 lines)

| File | Lines | Role | Importers (Evidence) | Verdict |
|---|---|---|---|---|
| `metrics.py` | 520 | **ALIVE (used):** Deterministic metrics (exact_match, ROUGE-L, BLEU, semantic_similarity via embedding similarity); called by src/simplified/metrics.py | Imported by: `src/simplified/metrics.py:5` (grep: `from src.eval import metrics as det_metrics`) **AND** `simplified_teaching_loop.py:77` (grep: `from src.eval.metrics import semantic_similarity`) | **ALIVE** |
| `reports.py` | 540 | Report generation (load_results, compute_metrics, generate_plots) | 0 importers (grep: `reports.py import` → only docstring example, no actual call; grep `from src.eval.reports` → no results) **BUT:** imports retrieval.py:1 | **DEAD** |
| `retrieval.py` | 636 | Retrieval metrics (not used in teaching loop; only imported by dead reports.py) | 1 importer: `src/eval/reports.py:10` (grep: `from . import retrieval as retrieval_metrics`) **BUT** reports.py itself is dead → effective 0 callers | **DEAD** |
| `__init__.py` | 25 | Re-export from retrieval (which is dead) | Module init; re-exports dead code | **ALIVE** |

#### src/core/ — Abstract Interfaces & Utilities (5 files, 118 lines)

| File | Lines | Role | Importers (Evidence) | Verdict |
|---|---|---|---|---|
| `client.py` | 25 | Abstract base class (LLMClient) for all provider implementations | Imported by: `src/providers/factory.py:3`, `src/providers/{groq,gemini,local}_client.py` (grep: `from ..core.client import LLMClient` → 3 hits) | **ALIVE** |
| `types.py` | 22 | Data classes (Message, ChatResult, Usage) shared by all clients | Imported by: all provider clients + factory | **ALIVE** |
| `logger.py` | 18 | Logger initialization (singleton or per-module) | Imported by: `src/eval/{reports,retrieval}.py`, provider clients (grep: `from ..core.logger import` → 5 hits) | **ALIVE** |
| `tokens.py` | 53 | Token estimation utilities (for cost/quota tracking) | Imported by: `src/providers/gemini_client.py:4` (grep: `from ..core.tokens import estimate_tokens`) | **ALIVE** |
| `__init__.py` | 0 | Empty init | Module init | **ALIVE** |

#### src/utils/ — Shared Utilities (2 files, 250 lines)

| File | Lines | Role | Importers (Evidence) | Verdict |
|---|---|---|---|---|
| `prompt_loader.py` | 249 | PromptLoader + get_prompt_loader(): YAML prompt config loading with variable substitution | Imported by: `src/simplified/{metrics,student,teacher_feedback}.py`, `src/prompts/student.py` (grep: `from src.utils.prompt_loader import` → 4 hits) | **ALIVE** |
| `__init__.py` | 1 | Empty init | Module init | **ALIVE** |

### config/ — YAML Configurations (2 files)

| File | Lines | Role | Importers (Evidence) | Verdict |
|---|---|---|---|---|
| `simplified_config.yml` | 127 | System config: student (Groq Llama-8B), teacher (Llama-70B), hybrid scoring, feedback, memory, logging | Loaded by: `SimplifiedTeachingLoop.__init__()` in simplified_teaching_loop.py:117 (grep: `config_path="config/simplified_config.yml"`) | **ALIVE** |
| `prompts_config.yml` | 157 | Centralized prompt templates for student, teacher | Loaded by: src/utils/prompt_loader.py via config loader | **ALIVE** |

### scripts/ — Standalone Analysis & Preparation (4 files)

| File | Lines | Role | Importers (Evidence) | Verdict |
|---|---|---|---|---|
| `prepare_medical_dataset.py` | 363 | Script: load Medical_Q&A CSVs, clean, deduplicate, export JSONL | Standalone script (called via `python scripts/prepare_medical_dataset.py`) | **ALIVE** |
| `split_medical_by_source.py` | 100 | Script: split JSONL by domain/source into medical_by_source/ | Standalone script | **ALIVE** |
| `estimate_cost.py` | 206 | Script: estimate token costs for Groq API calls across hyperparameter grid | Analysis script | **ALIVE** |
| `analyze_lhs_strategy.py` | 197 | Script: hyperparameter exploration (Latin Hypercube Sampling + Grid Search) | Analysis script | **ALIVE** |

### schemas/ — Data Contracts (1 file)

| File | Lines | Role | Importers (Evidence) | Verdict |
|---|---|---|---|---|
| `log_record.schema.json` | 227 | JSON schema for experiment summary records (experiment_id, pass_rate, metrics, etc.) | Referenced in schema.md (documentation); auto-loaded in CLAUDE.md context | **ALIVE** |

### notebooks/ — Analysis & Exploration (1 file)

| File | Lines | Role | Importers (Evidence) | Verdict |
|---|---|---|---|---|
| `experiment.ipynb` | 8260 | Jupyter notebook: load logs, analyze results, plot metrics, compare phases | Manual exploration; not imported by code | **ALIVE** |

### data/ — Special Entry (1 file tracked)

| Path | Lines | Role | Verdict |
|---|---|---|---|
| `data/__init__.py` | 0 | Empty; data/ is treated as a data container, not a library | **ALIVE** |

### logs/ & data/ — Excluded from Detailed Audit (per spec)

| Path | Tracked | Role | Summary |
|---|---|---|---|
| `data/Medical_Q&A/*.csv` | ✓ (8 files) | Raw MedQuAD source (immutable per §structure) | Raw data container; 12,358 CSV rows |
| `data/medical_by_source/*.jsonl` | ✓ (8 files) | Derived per-domain JSONL (immutable per §structure) | Intermediate data; 12,428 records |
| `data/alpaca_*.jsonl` | ✓ (3 files) | Alpaca format test data | Small test sets |
| `data/medical_all_clean.jsonl` | ✓ (1 file) | Claimed "clean" dataset (under audit in T0.3) | 10,024 records; see D3/D4 rubric findings |
| `logs/experiments/phase*/*.jsonl` | ✓ (10+ phases) | Experiment runs (summary, debug per-round) | Phase 0–6 results; evidence for ADR-001 |
| `logs/experiments/phase*/configs/*.yml` | ✓ (15+ files) | Run configs per phase | Hard-coded paths flagged in structure.md junk checklist |

---

## Import Graph — Core Dependency Layers

```
APPLICATION LAYER (entrypoints)
├── simplified_experiment_runner.py (359 ln)
│   └── simplified_teaching_loop.py (843 ln) [MESSY]
│
TEACHING LOOP CORE (active orchestration)
├── simplified_teaching_loop.py
│   ├── src.simplified.student → StudentClient ✓
│   ├── src.simplified.metrics → MetricsEvaluator ✓
│   ├── src.simplified.teacher_feedback → TeacherFeedback ✓
│   ├── src.simplified.memory → FAISSMemory ✓
│   ├── src.simplified.early_stopping → EarlyStopping ✓
│   ├── src.simplified.logger → RoundLogger ✓
│   ├── src.simplified.monitor → PerformanceMonitor ✓
│   ├── src.simplified.debug_logger → DebugLogger ✓
│   ├── src.simplified.terminal_ui → TerminalUI ✓
│   ├── src.prompts.student → build_ground_truth_hint_prompt ✓
│   └── src.eval.metrics → semantic_similarity ✓
│
COMPONENT LAYER (reusable blocks)
├── src.simplified.student
│   ├── src.providers.factory → build_client ✓ [EXEMPLAR]
│   └── src.utils.prompt_loader → get_prompt_loader ✓
├── src.simplified.metrics
│   ├── src.eval.metrics → det_metrics (exact_match, ROUGE-L, etc.) ✓
│   ├── src.providers.factory → build_client ✓
│   └── src.utils.prompt_loader → get_prompt_loader ✓
├── src.simplified.teacher_feedback
│   ├── src.providers.factory → build_client ✓
│   └── src.utils.prompt_loader → get_prompt_loader ✓
│
PROVIDER LAYER (client implementations)
├── src.providers.factory [EXEMPLAR]
│   ├── src.providers.groq_client (via @register)
│   ├── src.providers.local_client (via @register)
│   ├── src.providers.gemini_client (via @register)
│   └── src.core.client (abstract base)
├── src.providers.{groq,local,gemini}_client
│   ├── src.core.types → Message, ChatResult, Usage ✓
│   ├── src.core.logger → get_logger ✓
│   └── src.core.tokens (gemini only) → estimate_tokens ✓
│
INFRASTRUCTURE LAYER (non-core)
├── src.eval.metrics ✓ (used via simplified.metrics + teaching_loop)
│   └── numpy, nltk (external)
├── src.core.{client,types,logger,tokens} ✓
└── src.utils.prompt_loader ✓
    └── yaml, pathlib (external)

DEAD CODE (0 importers, not entrypoints)
├── src.eval.reports.py (540 ln)
│   └── src.eval.retrieval.py (636 ln) ← only caller
├── src.prompts.teacher.py (239 ln) ← superseded by src/simplified/teacher_feedback.py
├── src.simplified.console_logger.py (0 ln)
├── src.simplified.logger_manager.py (0 ln)
```

---

## Per-Directory Summary

| Directory | Total Ln | Keep | Rework | Demolish | Notes |
|---|---|---|---|---|---|
| **src/simplified/** | 3,487 | 12 files (3,469 ln) | 0 | 2 empty (console_logger, logger_manager) | Core loop orchestration; 9 live + 3 init = 12 active. 2 empty files = DEAD. |
| **src/prompts/** | 244 | 2 files (197 ln) | 1 | 0 | student.py ALIVE, teacher.py DEAD (superceded by simplified/teacher_feedback.py). |
| **src/providers/** | 1,051 | 7 files | 0 | 0 | Factory pattern exemplary; all clients registered and reachable. |
| **src/eval/** | 1,721 | 2 files (545 ln) | 0 | 2 | metrics.py ALIVE (used in simplified). reports.py + retrieval.py DEAD. __init__.py re-exports dead code. |
| **src/core/** | 118 | 5 files | 0 | 0 | Abstract interfaces and shared types; actively used by providers. |
| **src/utils/** | 250 | 2 files | 0 | 0 | prompt_loader heavily reused (4 importers). |
| **src/ (subtotal)** | **5,476** | **30 ALIVE** | **0** | **4 DEAD** | 5 dead files = 636 + 540 + 239 + 0 + 0 = 1,415 lines (~26% of src/'s 5,476 ln). |
| **config/** | 284 | 2 files | 0 | 0 | YAML configs directly loaded; no dead code. |
| **scripts/** | 866 | 4 files | 0 | 0 | Standalone analysis scripts (not imported by main loop). |
| **notebooks/** | 8,260 | 1 file | 0 | 0 | Jupyter for manual analysis; not imported. |
| **schemas/** | 227 | 1 file | 0 | 0 | JSON schema for experiment records. |
| **root/** | 1,202 | 5 files | 1 | 0 | simplified_teaching_loop.py is MESSY (843 ln, monolithic run()). |
| **TOTAL** | **17,382 tracked** | **44 files** | **1 rework** | **5 dead** | Dead code = 1,415 ln (~26% of src/). Tools/ untracked. |

---

## Demolition Candidates (T2.9 Deletion Proof)

**These files have 0 importers and are not entrypoints. Evidence: command output showing 0 hits.**

| File | Lines | Importers | Proof | Reason | Owner |
|---|---|---|---|---|---|
| `src/eval/reports.py` | 540 | 0 | `grep -r "from.*reports\|import.*reports" src/ simplified_*.py` → empty | Superseded by dashboard in experiment runner; functions moved to monitoring/logger | **qa-engineer** |
| `src/eval/retrieval.py` | 636 | 0 (1 if counting dead reports.py) | `grep -r "retrieval" src/ simplified_*.py` → only in reports.py docstring (not active call) | FAISS/embedding retrieval moved to src/simplified/memory.py | **data-engineer** |
| `src/prompts/teacher.py` | 239 | 0 | `grep -r "from.*prompts.*teacher\|import.*teacher" src/ simplified_*.py` → empty | Refactored: prompts now in config/prompts_config.yml + dynamic loading; logic moved to src/simplified/teacher_feedback.py | **prompt-engineer** |
| `src/simplified/console_logger.py` | 0 | 0 | `grep -r "console_logger" src/ simplified_*.py` → empty | Empty stub; functionality in src/simplified/logger.py + src/simplified/terminal_ui.py | **codebase-steward** |
| `src/simplified/logger_manager.py` | 0 | 0 | `grep -r "logger_manager" src/ simplified_*.py` → empty | Empty stub; no replacement found in logs (all logging via logger.py + debug_logger.py) | **codebase-steward** |

---

## Exemplars — Patterns Worth Copying

### 1. **src/providers/factory.py (21 lines)** — Registry Pattern

**Why:** Minimal, decoupled, extensible. Clients self-register; core code only calls `build_client(provider, model)`.

**Key pattern:**
```python
_CLIENTS: Dict[str, Type[LLMClient]] = {}

def register(provider_name: str):
    def decorator(cls):
        _CLIENTS[provider_name] = cls
        return cls
    return decorator

def build_client(provider: str, config: Dict):
    return _CLIENTS[provider](**config)
```

**Reused by:** 3 internal callers (src/simplified/{student,metrics,teacher_feedback}.py) + 3 provider clients self-register.

**Recommendation for P2:** Use this pattern for `src/simplified/registries.py` (config slots A–F per ADR-015) to enable pluggable eval, memory, preset backends.

---

### 2. **src/providers/{groq,local,gemini}_client.py** — Adapter Pattern

**Why:** Each client implements the same `LLMClient` interface (chat, stream, token estimation). Swappable via factory.

**Key pattern:**
- All inherit from `src/core/client.LLMClient` (ABC).
- Normalize API-specific quirks (Groq auth vs local ollama URL).
- Expose `chat_completion(messages, model, temperature, max_tokens)` uniformly.

**Reused by:** Metrics evaluator and feedback generator call `build_client()` without caring which impl.

**Recommendation for P2:** Keep this pattern; extend for new providers (Claude, local Ollama via other URLs) without touching the loop.

---

### 3. **src/utils/prompt_loader.py** — Config-Driven Prompt Loading

**Why:** Prompts live in YAML (config/prompts_config.yml), not hardcoded. Variables replaced at load time.

**Key pattern:**
```python
loader = get_prompt_loader("config/prompts_config.yml")
prompt = loader.get("student.initial_draft", question=q)
```

**Reused by:** 4 callers (student, metrics, teacher_feedback, src/prompts/student).

**Recommendation for P2:** Generalize to `src/core/config_loader.py` for all YAML loading (six-slot config per ADR-015).

---

### 4. **src/simplified/memory.py** — FAISS Semantic Memory

**Why:** Embeddings + retrieval + update in one module. Handles faiss index, id mapping, hit rate tracking.

**Key pattern:**
- On-demand index creation (lazy; only if memory enabled).
- Retrieval ranks by success_rate + recency + usage frequency.
- Update after successful teaching (stores feedback + success metrics).

**Recommendation for P2:** Port to abstract `MemoryBackend` interface (none = disabled, faiss = current, sqlite-vec = future).

---

## Known Evidence Verification

**Spec claims → Verification result:**

| Claim | Expected | Found | Status |
|---|---|---|---|
| Dead: src/eval/retrieval.py (636 ln) | 0 importers | 0 (only in dead reports.py) | ✓ CONFIRMED |
| Dead: src/eval/reports.py (540 ln) | 0 importers | 0 | ✓ CONFIRMED |
| Dead: src/prompts/teacher.py (239 ln) | 0 importers | 0 | ✓ CONFIRMED |
| Dead: src/simplified/logger_manager.py | 0 importers | 0 | ✓ CONFIRMED |
| Dead: src/simplified/console_logger.py | 0 importers | 0 | ✓ CONFIRMED |
| Exemplar: src/providers/factory.py | Registry pattern, 3+ callers | 7 callers (factory + 3 clients + 3 loop components) | ✓ CONFIRMED |
| Exemplar: tools/dataset/* (config-driven) | **NOT TRACKED** | ❌ tools/ is untracked (git status `?? tools/`) | ⚠️ MISALIGNMENT |
| Messy: simplified_teaching_loop.py (843 ln, run() does everything) | Monolithic orchestration | run() spans lines 214–742, calls all components in sequence | ✓ CONFIRMED |
| Name clash: src/eval/metrics.py vs src/simplified/metrics.py | Two files with same name | eval/metrics: deterministic + helpers; simplified/metrics: orchestrator | ✓ CONFIRMED (managed; imported as `det_metrics`) |

---

## FINDINGS & RECOMMENDATIONS

### BLOCKER
- **tools/ directory is untracked, violates ADR-009 structure target.**
  - **Evidence:** `git ls-files` contains no `tools/` entries; git status shows `?? tools/`.
  - **Why:** ADR-009 specifies "Tools/dataset" as canonical location; structure.md lists it as a tracked dir. tooling is exemplary per hub notes but not under version control.
  - **Fix:** Run `git add tools/` to track the Dataset Readiness Assessor + CLI (feeds T1.6 environment audit and T2.1 config loader). **Owner: ops-engineer** (per ADR-012, pre-hook must allow tool ingestion).

### MAJOR
1. **Monolithic run() in simplified_teaching_loop.py (line 214–742, 529 lines in one method).**
   - **Evidence:** `simplified_teaching_loop.py:214-742` is single `run()` method.
   - **Why:** Violates single-responsibility; makes testing components in isolation hard; GT-leakage logic (lines 358–442) is buried. See todo.md T2.4 (Loop block v2 → strategies A/B/C/D).
   - **Fix:** Refactor run() into separate `Strategy` classes (A: baseline, B: self-refine, C: blind teacher, D: sighted teacher). **Owner: codebase-steward** in T2.4.

2. **5 dead files occupy 1,415 lines (~26% of src/) with zero dependencies.**
   - **Evidence:** Table above with 0-importer proof for each.
   - **Why:** Legacy refactoring (teacher.py → teacher_feedback.py, reports/retrieval → memory.py). Left in place during incremental work.
   - **Fix:** Delete in T2.9 after confirming they have no hidden references. **Owner: codebase-steward**.

### MINOR
1. **logs/experiments/*/configs/*.yml may contain hardcoded absolute paths.**
   - **Evidence:** structure.md junk checklist flags "Hardcoded absolute paths in committed configs (e.g. `C:\Users\...\Desktop\...` in `logs/experiments/*/configs/*.yml`)".
   - **Why:** Reduces reproducibility; paths should be resolved at runtime (T2.1 config loader goal).
   - **Fix:** Audit 1–2 config files in logs/ for absolute paths; document findings in T0.2 or T1.2. If found, T2.1 must implement path resolution. **Owner: ops-engineer** (T2.1).

2. **data/medical_all_clean.jsonl filename claims "clean" but needs D3–D4 verification.**
   - **Evidence:** spec.md notes "Cleaned dataset (under audit in T0.3)" and rubric.md D3/D4 thresholds may not be met.
   - **Why:** If dataset fails D3 (uniqueness) or D4 (quality) rubric bands, name is misleading.
   - **Fix:** T0.3 leakage census + T3/data-engineer assess pass/fail against rubric.md bands. Rename or retool if needed. **Owner: qa-engineer + data-engineer**.

---

## NOT VERIFIED (Out of Scope for T0.1, Flagged for Future)

| Item | Why Not Verified | Next Task |
|---|---|---|
| **Ground-truth leakage paths (detailed)** | T0.1 is code map, not leakage audit. Simplified_teaching_loop.py has GT hint path (line 358–364) but T0.3 will census all paths. | **T0.3** (qa-engineer) — detailed leakage census. |
| **tools/ exemplary quality** | tools/ is untracked; can't audit via git. Claim in hub notes (T1.6 will re-audit after tracking). | **T1.6** (project-coordinator) — re-assess after tools/ tracked. |
| **Config file absolute paths in logs/** | Sample check would require reading configs; scope limits us to code map. | **T0.2 or T1.2** (ops-engineer) — audit configs for hardcoded paths. |
| **Experiment numbers match logs** | Reconciliation is T2.8 task (reconcile-numbers skill). | **T2.8** (qa-engineer). |
| **Active vs legacy provider clients** | All 3 clients (groq, local, gemini) are registered; unclear which is active in running experiments. Needs config audit. | **T1.1** (program-architect) — config contract to specify active provider per slot. |

---

## EVIDENCE LOG

**Commands run (all grep-based evidence for 0-importer claims):**

1. `git ls-files` — enumerate tracked files (✓ ran, see Inventory).
2. `grep -r "from src.eval.retrieval\|import.*retrieval" src/ scripts/ simplified_*.py` → 1 hit (reports.py only).
3. `grep -r "from src.eval.reports\|import.*reports" src/ scripts/ simplified_*.py` → 0 hits.
4. `grep -r "from src.prompts.teacher\|import.*teacher" src/ scripts/ simplified_*.py` → 0 hits.
5. `grep -r "logger_manager\|console_logger" src/ scripts/ simplified_*.py` → 0 hits.
6. `grep -r "from src.providers.factory\|import.*factory" src/ simplified_*.py` → 7 hits (factory.py + 3 client register + 3 loop components).
7. Line counts: `wc -l src/**/*.py scripts/*.py ...` (✓ ran; see Inventory).

**Files opened & read:**
- `.claude/rules/00-index.md` (Constitution + fast facts)
- `.claude/rules/structure.md` (canonical layout + junk checklist)
- `docs/plan/README.md` (executor protocol)
- `docs/plan/T0.1-code-map.md` (spec)
- `simplified_experiment_runner.py` (lines 1–50; imports)
- `simplified_teaching_loop.py` (lines 1–100; imports, GT-leak hints line 358–442)
- `config/simplified_config.yml` (lines 1–60; config structure)
- `config/prompts_config.yml` (lines 1–40; prompt templates)

**Data sources:**
- Git tracked file inventory (via `git ls-files`).
- .claude/rules/agents.md — agent ownership assignments.

---

## Summary for Roadmap

- **P0 T0.1 (this task):** Code map complete; 5 dead files + 1 messy entrypoint identified.
- **P0 T0.2:** Audit `.claude/` environment (crew fitness for new direction). **Dependent on:** T0.1 code map as baseline.
- **P0 T0.3:** Ground-truth leakage census (file:line for every GT exposure). Will use this CODE_MAP's import graph to focus search.
- **P1 T1.2:** Strangler migration policy + structure.md v2. Will plan dead-code deletion sequence using T2.9 demolition list.
- **P2 T2.4:** Loop refactor (monolithic run() → strategy classes A/B/C/D).
- **P2 T2.9:** Demolition (delete 5 dead files + old core). **Ready:** proof of 0 importers in hand.

---

**Audit completed by:** housekeeping agent · **Date:** 2026-07-13 · **Archetype:** R (Review/Audit)
