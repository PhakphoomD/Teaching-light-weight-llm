# How the answer key reached the student, and what closed each path

The original system reported a rise from 25% to 83%, and 100% with what it called
"ground-truth memory". This is the audit that established those numbers were not
measuring learning. It enumerates **every path by which the reference answer could reach
the student model, the memory store, or the score** — read out of the code rather than
inferred from a symptom — and pairs each one with the mechanism in the rebuilt system that
makes it unreachable.

It is the long form of **Table 5**, [*Leakage Audit*](../reports/tables/tab-05-leakage-audit.md).
The table is the summary; this is the derivation, the propagation traces, and the parts a
summary cannot carry.

Read it as history. Every file cited in §2–§4 was deleted in the rebuild
([`.claude/rules/decisions.md`](../.claude/rules/decisions.md), ADR-015 → T2.9); the code
cited in §5 is what runs today.

---

## §1 The line: teaching with the answer is legal, measuring with it is not

A model may be *taught* using the reference answer. It may never be *shown* it while being
measured. Concretely:

**Legal.** The teacher model's prompt may contain the reference — generating feedback is its
job. A judge that scores by comparison may see it, and so may the deterministic
reference-match metrics (embedding similarity, ROUGE-L, exact match). These measure
resemblance to a reference, which is a legitimate thing to measure, *provided* the student
never sees the text and the pass/fail decision handed back to the student does not carry it.

**Illegal.** Anything that puts the reference string, or a close paraphrase of it, into
(a) a prompt sent to the **student**, or (b) a **memory record** that will later be retrieved
into a student prompt. Either one converts "the student learned" into "the student was handed
the answer."

The second clause is the one that is easy to miss, and it is where the original system failed
worst: a leak written into a persistent store is not a leak that happens once. It leaks
forward in time, into later runs, across process restarts, on questions that never triggered
the original mechanism.

---

## §2 The eighteen paths

Severity is about eval integrity, not about code quality. "Blocker" means a number produced
while this path was reachable cannot be read as a measurement of learning.

| | What it did | Who saw the answer | Verdict |
|---|---|---|---|
| **L1** | A student prompt template rendering `COPY THIS EXACTLY:\n{ground_truth}` | student | blocker — a deliberate mechanism |
| **L2** | The trigger that switched the student into that template | student | blocker |
| **L3** | An early-stop path that sent the same prompt one last time | student | blocker |
| **L4** | On success, the reference stored verbatim as "feedback" | memory | blocker — becomes L6 later |
| **L5** | A repetition detector firing the same hint | student | blocker |
| **L6** | Round 1 of **every** question retrieved stored feedback into the student prompt, unconditionally and with no content check | student | **blocker — structural, gated by no flag** |
| **L7** | A teacher template instructing the teacher to end with `Example: {ground_truth}`, whose output was handed to the student | student + memory | **blocker — confirmed in a production log** |
| **L8** | Teacher feedback written to memory with no leak check, on success *and* on failure | memory | major — makes L7 permanent |
| **L9** | Teacher shown the reference every round in the other feedback templates | teacher only | legal as designed; nothing enforced that its *output* did not quote it |
| **L10–L13** | Four scoring functions comparing against the reference | scoring | legal — see §3 for what that cost |
| **L14–L17** | Debug logs, terminal display, and offline tooling printing the reference | logs | legal — and how L7 was actually caught |
| **L18** | A notebook that pre-seeded memory with the answers before the final phase, tagged `source: ground_truth_injection` | memory | blocker — the direct cause of the reported 100% |

**L6 is the finding that matters most.** L1–L5 were switched off by configuration at the time,
so they would have looked clean in any log. L6 was not gated by anything: it ran on round 1 of
every question, and it returned whatever string had been stored, with no check on its content.
So turning off the *hint* mechanism did nothing to stop already-stored reference text from
being retrieved and shown to the student on a completely unrelated later question.

**L7 was previously undocumented.** The audit went looking for the known mechanisms and found
this one by reading templates: a chain-of-thought feedback template whose instruction to the
teacher was to return `"Error: … Fix: … Format: … Example: {ground_truth}"`. The teacher
complied. The captured output is in the run logs — a `feedback` field beginning "Example:"
followed by the reference text, which then became the next round's student prompt.

---

## §3 Seventy per cent of the score was resemblance, not correctness

The composite the system optimised and reported, read from its live configuration rather than
from its comment:

| component | weight | sees the reference? |
|---|---|---|
| comparison judge | 0.35 | **yes** |
| embedding similarity to the reference | 0.25 | **yes** |
| ROUGE-L against the reference | 0.10 | **yes** |
| blind judge (correctness only) | 0.30 | no |

**0.35 + 0.25 + 0.10 = 0.70.** Seventy per cent of the reported score rewarded resembling the
reference answer; thirty per cent asked whether the answer was right.

Combine that with §2 and the shape of the original result stops being surprising. The teacher
was shown the reference on every round. The memory store kept it and handed it back. And the
score was mostly a measure of how closely the output resembled the text that had been
circulating through the loop the whole time. A high number under that arrangement is what the
arrangement was built to produce.

Two smaller defects fell out of the same read: the configuration's own comment listed
different weights from the live dictionary (both summed to 1.0, so nothing crashed — the
documentation was simply wrong about which metric dominated), and the archived run configs
hardcoded an absolute path to a directory that no longer existed, so they could not be re-run
as committed. This is the same class of defect the restructure later found in thirteen live
scripts (ADR-034).

---

## §4 How a leak propagated — three traces

Three independent routes, which is why fixing any one of them would not have been enough.

**A — the explicit hint.** Last-chance enabled, plus either a repetition detected or the final
round reached → render `COPY THIS EXACTLY: {reference}` → send to the student. If that forced
round then passed, the reference was stringified as `"The correct answer is: …"` and written
into memory. That write is a **second-generation leak**: any later question whose embedding
was similar enough retrieved that record and received the reference as "feedback" **in its
first round**, without ever triggering last-chance itself.

**B — memory into the first prompt.** Round 1 of any question, unconditionally: look up the
most similar stored record; if one clears the similarity and success gates, put its stored
string into the student's prompt. Nothing validated that string. This is the route by which
the deliberately seeded store (L18) and any accidental A- or C-trace leak became
student-visible on unrelated later runs. Its signature is in the logs: the phase with a 0.95
similarity threshold, top-k of 1, and the same questions re-asked recorded a memory hit rate
of 1.0 and a pass rate of 1.0.

**C — the teacher echo.** Chain-of-thought style, round 4 or later, previous feedback present
→ the L7 template → the teacher returns the reference under "Example:" → that string becomes
the next round's student prompt **and** is persisted to memory, feeding trace B for every
future similar question. Not the default style, but one archived phase config selected it, and
the debug log from that run is the confirmation.

---

## §5 What closed each path

The audit ended in six requirements, and retrieval later added a seventh. Each is now a mechanism in the code, not a convention.
**The numbering is load-bearing** — a dozen modules and tests cite these as "seal #N", so the
order below is fixed.

| Seal | What shipped | Closes |
|---|---|---|
| **#1** No reference text in any student-bound prompt | `assert_gt_free` (`src/tlw/loop/core.py:56`) inspects every prompt on the framework's answering path before the model is called, and **aborts the run** rather than logging a warning. It is reached where a reference is in scope at all — the sighted-teacher arm and every retrieval run; on the three arms that never hold one it is a no-op, and there the protection is that the reference is not in scope to leak. The blind judge's signature cannot receive a reference at all, so a leak has to be added deliberately rather than forgotten. | L1, L2, L3, L5, L6, L7 (student side) |
| **#2** A store-time tripwire on memory | `src/tlw/memory/tripwire.py` — three independent checks: exact substring or a ≥12-token shingle (T-1), cosine similarity ≥ 0.80 (T-2), and a length-plus-overlap smell test that catches a lightly reworded full answer (T-3). Red-teamed against the 32 seeded records from the old store, which it rejects 100% of the time. | L4, L6, L7 (memory side), L8, L18 |
| **#3** Lint the teacher templates | `last_chance` and `difficult_question` are quarantined by name at load time (`src/tlw/prompts/loader.py:24`). Loading a prompt file containing either raises. | L1, L7 at authoring time |
| **#4** Remove the dead paths, not just default them off | T2.9 deleted the entire legacy core, so there is no toggle left to flip. A test greps for the identifier to keep it that way. | L1–L5 structurally |
| **#5** Judge independence | Validation rule V2 rejects a configuration whose judge shares a model family with the student, at load, before anything runs. | adjacent risk: a same-family judge shares the student's priors |
| **#6** Quarantine the seeded artifacts | Validation rule V6 denies any memory seed path matching the phase-6 directory or containing `gt_memory` / `ground_truth`. | L18 |
| **#7** The support-documentation study is sealed by what is indexed, not by a runtime check | Its retrieval index contains the 6,221 knowledge-base articles and never the 200 expert answers (`src/tlw/wixqa/retrieval.py`). Those scripts answer outside the framework loop, so seal #1 does not run there; the reference is instead absent from everything the retriever can return. | the WixQA studies |

Retrieval, added later, brought the same problem in a new shape and needed its own seals: the
corpus is built from the training split only and scrubbed twice — 506 records → 448 after
dropping near-duplicates of held-out answers → **414** after dropping template twins, which
share verbatim blocks with a held-out answer while sitting well below the cosine threshold
that would have caught them. At run time any surviving passage that still shares a 12-token
span with the held-out answer is dropped **and counted**, so the filter's own activity is
reportable rather than silent.

**The guard has fired.** One run of the arm designed to leak — the arm where the teacher is
shown the reference — was aborted by `assert_gt_free` catching a real echo. That run is
reported as aborted rather than quietly re-run, which is why the leakage-ceiling arm has two
seeds where every other arm has three.

---

## §6 What this audit did not establish

Stated because a survey that claims completeness it does not have is the same failure it was
written to catch.

- Whether the **other** teacher templates ever echoed the reference in a real run. The
  templates carry no instruction to do so and no instance was found, but the search was a
  targeted grep for the known pattern, not an exhaustive fuzzy match of every logged feedback
  field across all phases. Nothing structurally prevented it; the blanket tripwire in §5 now
  covers all styles rather than only the known-bad template.
- Whether any configuration outside the phase-6 set pointed memory at a seeded store. The
  phase-6 files were opened; the other archived configs were not.
- Runtime behaviour. The audit was read-only by design — every claim above comes from reading
  code or pre-existing logs, not from executing the leaking system.

---

*Formerly `docs/audit/LEAKAGE_CENSUS.md`, and cited under that name by ADR-018, ADR-019 and
ADR-024. Those entries are accepted decisions and are frozen (§0.6), so they still name the
document as it was; this file is the same audit, rewritten for a reader rather than as a task
report. The original wording is in git history.*

*Provenance: the classification was produced by reading every `ground_truth` reference in the
then-live code; the weight arithmetic in §3 was reproduced from the configuration file on
disk; the L7 confirmation is a captured teacher output in
`logs/simplified/debug/20251130_024301.json:4460`, and the trace-B confirmation is
`logs/experiments/phase6/summary.jsonl`. Both log directories are immutable and
guard-protected. Originally written as the T0.3 audit, 2026-07-13.*
