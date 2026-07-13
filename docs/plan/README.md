# Renovation Plan — Hub-and-Spoke Execution

**How this works (decided 2026-07-13, ADR-015):**
- The **hub** is a planning conversation with the user (Ham). It makes decisions and writes them here.
- **Execution happens in fresh chats** ("spokes"). A fresh chat has NO memory of the hub
  discussion — everything it needs must be in this folder, `.claude/rules/`, and the repo itself.
- To execute a task, the user opens a new chat and says e.g. `ทำ T0.1` / `do T0.1`.

## Executor protocol (every spoke chat MUST follow)
1. Read this README, then the task's spec file `docs/plan/T<id>-*.md`, then every file in its
   **Read first** list. Rules in `.claude/rules/` auto-load — obey §0 Constitution.
2. Stay inside the task's scope. **One task = one chat = one tangible output.**
3. If you hit a decision the spec doesn't cover → do NOT improvise architecture. Write the
   question into your output under `NEEDS-HUB-DECISION` and stop that thread of work.
4. On completion: (a) produce the Output file(s), (b) tick the task in `.claude/rules/todo.md`
   and add a one-line result note, (c) if any durable decision was made, record it via the
   `new-adr` skill (§0.6).
5. Evidence rule (§0.4): every claim in your output cites file:line you actually read or a
   command + output you actually ran. Python only via the tlw full path (§0.5).

## Phase map & gates
- **P0 — Inspect** (T0.1–T0.3): read-only audit. No file in `src/`, `config/`, `tools/` may be modified.
- **P1 — Blueprint** (T1.1–T1.7): documents/SSOT only. Still no code changes.
- **GATE ✋:** after T1.7, the user reviews the blueprint at the hub before P2 starts.
- **P2 — Rebuild Track-A core** (T2.1–T2.9): code, strangler-style (new blocks grow beside old
  code; old code is deleted only in T2.9 after new blocks are proven).
- **P3 — Track B (RAG+LoRA product):** deliberately NOT broken down yet. It will be planned at
  the hub after T2.8 results exist. Do not invent P3 tasks.

## Task spec template
Each `T*.md` has: Objective · Why (hub context) · Read first · Steps · Definition of Done ·
Must NOT do · Known evidence (facts the hub already verified, with file:line).

## Dependency graph
```
T0.1  T0.2  T0.3        (parallel, read-only)
  └──┬──┴────┘
     ▼
T1.1 → T1.2 → T1.3/T1.4/T1.5 (T1.6 needs T0.2) → T1.7 (gate package)
     ▼  ✋ USER GATE
T2.1 → T2.2 → T2.3 + T2.5 → T2.4 → T2.6 → T2.7 → T2.8 → T2.9
```
