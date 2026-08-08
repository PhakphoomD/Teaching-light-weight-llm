# CLAUDE_ENV_AUDIT — T0.2 (.claude/ environment audit)

**Generated:** 2026-07-13 · **Owner:** main thread · **Archetype:** R (Review/Audit)
**Question under audit:** is the crew (agents/rules/skills/guard/settings) fit for the NEW direction
(Track-A honest ablation → RAG+LoRA product → eventually an app), given it was designed around the
now-finished dataset-cleaning workstream?

## VERDICT: **PASS-WITH-NOTES**

The environment is structurally sound: all 8 agent files follow the ADR-008 skeleton, the guard
hook demonstrably works (tested live), skills point at real files, and `todo.md`/`decisions.md`
already reflect the ADR-015 renovation plan. But (1) the entire `.claude/` directory is **not in
git**, (2) three P2/P3 competencies have **no owner** (ablation statistics, RAG engineering,
LoRA training), and (3) several specs contain stale or contradictory references that T1.6 must fix.

---

## FINDINGS (heaviest first)

### [BLOCKER] The whole `.claude/` environment is untracked in git
- **evidence:** `git status --short` → `?? .claude/` (command run 2026-07-13; also `?? tools/`,
  `?? docs/plan/`, `?? docs/audit/`, `?? data/clean/`, `?? scripts/dataset/assess_all.py`,
  `?? scripts/calibration/compare_judges.py`, `?? scripts/calibration/compare_students.py`).
- **why:** §0.3 reproducible / §0.4 evidence. The Constitution, guard hook, permission rules,
  agent specs, the entire renovation plan, AND the evidence scripts behind ADR-011/ADR-014
  (`scripts/calibration/compare_judges.py`, `compare_students.py`) exist only on this machine's working tree.
  A `git checkout`/clone loses the SSOT and the enforcement layer silently.
- **fix:** commit `.claude/`, `docs/plan/`, `docs/audit/`, `tools/`, the three scripts, and
  (decision needed) `data/clean/`. **Owner: main thread / user** — user decides the commit; this
  audit only flags it. (Same finding as CODE_MAP.md BLOCKER, wider scope.)

### [MAJOR] No owner for three P2/P3 competencies (expected gap — confirmed)
- **evidence:** `.claude/rules/agents.md` roster (8 agents) vs upcoming specs:
  - **Ablation statistics** — T2.8 requires "C−B with 95% CI" (`todo.md` T2.8;
    `docs/plan/T2.8-analysis-report.md`). Owner is qa-engineer, but `qa-engineer.md:17-23`
    (procedure) covers tests/repro/leakage only — no statistics/CI/bootstrap competency.
  - **RAG engineering (P3 build)** — `program-architect.md:3` covers *design* of "RAG stack";
    no agent owns building retrieval (data-engineer.md:3 scope = dataset pipeline only).
  - **LoRA/QLoRA training (P3)** — `ops-engineer.md:20` covers env/VRAM fit advice only;
    nobody owns training runs, adapters, eval of tuned models.
  - **Frontend/app (later)** — no owner anywhere; acceptable for now (out of P0–P2 scope).
- **why:** agents.md dispatch table has no route for these → work lands ad-hoc on the main thread.
- **fix (T1.6):** extend qa-engineer with a statistics section (or add an `analyst` role);
  plan RAG/LoRA ownership when P3 is planned (per ADR-015 P3 is deliberately unplanned) —
  minimum action now = one line in `agents.md` naming the future owner. **Owner: project-coordinator.**

### [MAJOR] program-architect ADR procedure contradicts the `new-adr` skill and reality
- **evidence:** `program-architect.md:21` — "write an ADR to `docs/adr/ADR-00X-*.md` and add a
  one-line summary to `decisions.md`". But `ls docs/adr` → "No such file or directory" (run
  2026-07-13), and `.claude/skills/new-adr/SKILL.md:15-17` writes the FULL entry into
  `decisions.md` (house format, top of list). All 15 existing ADRs live only in `decisions.md`.
- **why:** two conflicting ADR procedures → risk of a split/lost ADR log the first time the
  architect runs T1.1/T1.2 (both produce ADRs).
- **fix (T1.6):** align program-architect.md with the new-adr skill (decisions.md is canonical;
  `docs/adr/` stays "(planned)" per structure.md until ADR-009 restructure). **Owner: project-coordinator.**

### [MAJOR] `.env` protection has a Write-tool hole
- **evidence:** `.claude/settings.json:19-21` denies `Read(./.env)`, `Read(./.env.*)`,
  `Edit(./.env)` — there is **no `Write(./.env)` deny**. `guard.py:19-23` PROTECTED list covers
  raw data + logs/experiments only, not `.env`. So the Write tool can overwrite `.env`.
  (`CLAUDE.md` "Enforcement" section claims settings deny "edits to … `.env`" — only half true.)
- **why:** ADR-012 enforcement intent (secrets protected) not fully implemented; a misbehaving
  agent could clobber or exfil-stage secrets via Write.
- **fix (T1.6):** add `Write(./.env)` + `Write(./.env.*)` to deny, or add `\.env` to guard
  PROTECTED. **Owner: ops-engineer.** *(Not exercised live — writing .env to test would itself
  violate the intent; classified from rule text.)*

### [MINOR] Guard false-positive: read-only commands with `2>&1` naming a protected dir get blocked
- **evidence:** ran `ls logs/experiments/ 2>&1 | head -15` → BLOCKED by guard
  ("appears to modify an immutable/evidence directory"). Cause: `guard.py:56` regex treats the
  `>` in `2>&1` as a write redirect.
- **why:** guard is meant to be "deliberately narrow — prefers rare misses over false blocks"
  (`guard.py` header + ADR-012); this is the opposite: a false block on a read.
- **fix (T1.6):** exclude `\d>&\d` (fd duplication) from the redirect pattern. **Owner: ops-engineer.**
- Positive control also ran: bare `python --version` → correctly BLOCKED with §0.5 message. ✓

### [MINOR] Guard PROTECTED list doesn't cover the planned tree
- **evidence:** `guard.py:19-23` protects `data/Medical_Q&A/`, `data/medical_by_source/`,
  `logs/experiments/` only. Planned dirs from `structure.md` (ADR-009): `data/interim/`,
  `data/processed/`, `db/`, `models/` — unprotected; also fine for now since T2.x may need to
  write there. But P2's new experiment outputs (T2.6/T2.7 runs) will land under
  `logs/experiments/` which IS write-blocked for tools — correct per design (runs write them),
  but T2.6 runner must therefore write logs via the experiment process, never via file tools.
- **why:** spec step 4 asks whether guard matches the planned tree; answer: mostly, with the
  above nuance to keep in mind when writing T2.6.
- **fix:** no change needed now; revisit in T2.1 when config decides output paths. **Owner: ops-engineer.**

### [MINOR] qa-engineer procedure assumes a test suite that doesn't exist yet
- **evidence:** `qa-engineer.md:20` — run `-m pytest -q`; `structure.md` marks `tests/` as
  "(planned)"; Glob `tests/**` → no files (checked via repo listing).
- **why:** first invocation of qa-engineer for T2.x will follow a procedure step that can't run.
- **fix (T1.6):** reword to "create tests/ mirroring src/ (structure.md) if absent". **Owner: project-coordinator.**

### [MINOR] structure.md canonical tree omits `docs/plan/` and `docs/audit/`
- **evidence:** `structure.md` docs section lists only `docs/adr/ (planned)`; but ADR-015 made
  `docs/plan/` the task-spec home (`todo.md` header) and T0.x outputs live in `docs/audit/`
  (both exist on disk, `ls docs/` → `audit  plan ...`).
- **why:** housekeeping audits against structure.md could flag the renovation plan itself as junk.
- **fix (T1.6):** add both dirs to structure.md tree. **Owner: project-coordinator** (structure.md
  edit is SSOT work; ADR-009 is Accepted but the tree listing is descriptive, not a §0 principle —
  still, flag to user if in doubt per §0.6).

---

## Coverage matrix (upcoming task types → owner)

| Task type (from docs/plan/) | Owner per agents.md | Fit? |
|---|---|---|
| Structure/code audits (T0.1) | housekeeping | ✓ done |
| Env audit (T0.2) | main thread | ✓ this doc |
| Leakage census (T0.3) | qa-engineer | ✓ in progress |
| Config contract (T1.1) | program-architect | ✓ (fix ADR-procedure first — MAJOR above) |
| Target architecture (T1.2) | program-architect | ✓ |
| Memory design (T1.3) | program-architect + prompt-engineer | ✓ |
| Eval spec incl. CI/budget (T1.4) | program-architect + qa | ⚠ statistics competency gap |
| Prompt catalog (T1.5) | prompt-engineer | ✓ |
| Crew update (T1.6) | project-coordinator | ✓ (this doc is its input) |
| Config loader/registries (T2.1–T2.2) | ops/steward | ✓ |
| Eval/loop/memory blocks (T2.3–T2.5) | qa/steward/prompt/data | ✓ |
| Runner + runs (T2.6–T2.7) | ops + qa | ✓ (mind guard/logs nuance) |
| **Analysis, C−B with 95% CI (T2.8)** | qa-engineer | **✗ no stats competency — GAP** |
| Demolition (T2.9) | steward + housekeeping | ✓ (CODE_MAP proof in hand) |
| **RAG engineering (P3)** | — | **✗ no owner (design only) — GAP, plan at P3** |
| **LoRA/QLoRA training (P3)** | — | **✗ no owner (env only) — GAP, plan at P3** |
| **Frontend/app (later)** | — | ✗ no owner — acceptable for now |

## Recommendation table for T1.6 (per agent)

| Agent | Verdict | Action for T1.6 |
|---|---|---|
| project-coordinator | KEEP | none — spec current |
| program-architect | UPDATE | fix ADR output path (decisions.md canonical, not docs/adr/) |
| data-engineer | KEEP | none — memory notes still accurate (medical_all_clean caveat, GHR) |
| prompt-engineer | KEEP | none — §0.2 focus is exactly the T1.5/T2.3 need |
| qa-engineer | UPDATE | add statistics/CI competency (bootstrap/t-test, seeds) for T1.4/T2.8; fix pytest step (tests/ doesn't exist yet) |
| ops-engineer | UPDATE | own the two guard fixes (`2>&1` false block, `.env` Write hole) |
| codebase-steward | KEEP | line-number drift only ("~500 lines" vs actual 529 in run(), simplified_teaching_loop.py:214-742 per CODE_MAP) — harmless |
| housekeeping | KEEP | after structure.md gains docs/plan+docs/audit, no change |
| **(new or extend)** | ADD-LATER | RAG engineer + LoRA trainer roles at P3 planning; statistics could be folded into qa instead of a new role (recommended) |

## Rules/skills/settings status

| File | Status | Notes |
|---|---|---|
| `rules/todo.md` | CURRENT | reflects ADR-015 renovation plan; hub's "outdated priority" note is already resolved |
| `rules/decisions.md` | CURRENT | ADR-011/014 both `Proposed` and interlocked (judge↔student) — flagged for P1 GATE decision, already listed there ✓ |
| `rules/structure.md` | STALE (minor) | missing docs/plan, docs/audit (finding above) |
| `rules/schema.md` | CURRENT | leakage warning on gt_memory_store matches ADR-001; six-slot contract lands here in T1.1 as planned |
| `rules/rubric.md` | CURRENT | config-driven thresholds; unchanged direction |
| `rules/providers.md` | CURRENT* | *model list/limits not re-verified against Groq console (see NOT VERIFIED) |
| `skills/run-pipeline` | WORKS (paths) | `tools/dataset/cli.py` + `cleaning_config.yaml` exist (ls verified) |
| `skills/reconcile-numbers` | WORKS (paths) | `logs/experiments/phase0..6/summary.jsonl` exist (ls verified) |
| `skills/new-adr` | WORKS | consistent with decisions.md house format |
| `settings.json` | WORKS (hook) | hook registration fires (observed live); `.env` Write hole (finding above) |
| `hooks/guard.py` | WORKS | §0.5 block verified live; one false-positive class found (finding above) |

## NOT VERIFIED
- **Groq model list & rate limits in providers.md** (incl. odd-looking `qwen/qwen3.6-27b`) —
  needs an API call/console check; out of read-only scope. → ops-engineer, before T2.7 budgeting.
- **`.env` Write-hole exploitability** — intentionally not exercised (would touch secrets file);
  classified from rule text only. → ops-engineer can test with a sandbox path in T1.6.
- **Agent `memory: project` frontmatter behavior** (all 8 agents) — whether persistent agent
  memory is active in this harness wasn't tested; no task depends on it yet.
- **Skills execution end-to-end** — path targets verified to exist; skills not actually run
  (run-pipeline would regenerate data/clean — out of P0 read-only scope).

## EVIDENCE LOG
- Read (full): `.claude/CLAUDE.md`, `rules/{00-index,agents,decisions,providers,structure,todo,schema,rubric}.md`,
  `agents/{housekeeping,qa-engineer,project-coordinator,data-engineer,program-architect,prompt-engineer,ops-engineer,codebase-steward}.md`,
  `skills/{run-pipeline,reconcile-numbers,new-adr}/SKILL.md`, `hooks/guard.py`, `settings.json`,
  `docs/plan/README.md`, `docs/plan/T0.2-claude-env-audit.md`, plan spec titles T1.1–T2.9.
- Commands run (with output captured): `python --version` → guard BLOCK (§0.5 ✓);
  `ls logs/experiments/ 2>&1 | head` → guard BLOCK (false positive ✓ documented);
  `ls docs/; ls docs/adr; ls tools/dataset/cli.py tools/dataset/cleaning_config.yaml` →
  docs/adr missing, tool paths exist; `ls logs/experiments | head` + `ls logs/experiments/*/summary.jsonl`
  → phase0–6 summaries exist; `git status --short` → `.claude/` etc. untracked.
