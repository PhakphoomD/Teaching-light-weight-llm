---
name: new-adr
description: Record an architecture/design decision as a new ADR in .claude/rules/decisions.md following the project's ADR conventions (§0.6 — never edit an Accepted ADR; supersede it). Use whenever a decision is made that future sessions must know about.
---

# Add an ADR to the SSOT

Authority: `00-index §0.6`, `rules/decisions.md` header.

## Procedure
1. Read `.claude/rules/decisions.md`; take the next ADR number (newest is at the top).
2. If this decision changes an **Accepted** ADR: do NOT edit it. Write the new ADR with
   "Supersedes ADR-00X" and (only after user approval) mark the old one
   `· Superseded by ADR-0YY` in its status line.
3. Write the entry at the TOP of the list in the house format:
   `## ADR-0NN — <title> (YYYY-MM-DD) · <Accepted|Proposed>` then **Context** (1–2 lines),
   **Decision**, **Evidence** (what was actually read/run — §0.4).
4. Status rules: `Accepted` only if the user explicitly approved; otherwise `Proposed`.
5. Update the ripple: if the decision changes the roadmap → `rules/todo.md`; if it changes
   layout → `rules/structure.md`; if agents' ownership changes → `rules/agents.md`.
6. Keep it under ~6 lines — decisions.md is loaded every session; long analysis goes to
   `docs/` with a link.
