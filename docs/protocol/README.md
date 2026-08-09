# Protocols — what was decided before each study ran

Each file here fixes a design before the study it governs: the arms, the metric that counts, the
statistic, the pass bar, and — in two cases — the rule for stopping. They are kept as they were
written. **The bodies are never edited.** A correction is an appended, dated amendment or a new
dated file that supersedes; rewriting a protocol after seeing the result would make it something
other than a protocol.

The report cites these rather than restating them, which is the convention for pre-registered work:
the plan is a separate, dated record, and the write-up points at it.

---

## What this directory can and cannot prove

**It cannot prove the dates from version control, and it does not claim to.** The whole
`docs/plan/` directory was untracked until the repository restructure on 2026-08-07, so most of
these files entered git well after the runs they govern. Their authored dates are their own, and
`.claude/rules/todo.md` — a separate log written by different sessions — records the same dates
independently. Both of those are ordinary trust; neither is proof.

What *is* checkable is stronger than a timestamp, and it is the reason to believe these were
written in advance:

**Two of the predictions recorded in them came out wrong, and are published as wrong.** The
grounding-window plan predicted about 0.36 and the run returned 0.470; the self-refinement plan
predicted +3 points and the run returned −1.5, the sign flipped. Both are in
[Table 16](../../reports/tables/tab-16-predictions-vs-outcomes.md). A protocol written after the
fact does not contain forecasts that embarrass its author.

**One stop rule fired and cost the project a result it wanted.** The loop-plus-retrieval plan said
that if the pilot came back flat, the three-seed run would not happen. The pilot came back flat and
the run was not done — so that study is reported as a single-seed pilot, which is a weaker result
than the alternative. Reading the rule after the pilot would have made it easy to run the seeds
anyway.

**One prediction was right for a stated reason.** The mixture model forecast 0.337 before the third
retrieval rung executed; the run returned 0.340.

---

## The register

| Protocol | Written | First in git | Study it governs | Ran | Outcome vs prediction |
|---|---|---|---|---|---|
| [teaching-loop-protocol](2026-07-13-teaching-loop-protocol.md) | 2026-07-13 | 2026-07-16 | Does an iterative loop teach a small model? | 2026-07-15 | headline C−B statistic and its interval used exactly as specified |
| [rag-medquad-protocol](2026-07-16-rag-medquad-protocol.md) | 2026-07-16 | 2026-08-07 | Does retrieval help a model that already knows the domain? | 2026-07-16 | two secondary questions it posed both answered no |
| [wixqa-dose-response-plan](2026-07-24-wixqa-dose-response-plan.md) | 2026-07-24 | 2026-08-07 | Is retrieval quality the bottleneck? | 2026-07-24 | the dose-response it specified was observed |
| [wixqa-hit-rate-instrument](2026-07-24-wixqa-hit-rate-instrument.md) | 2026-07-24 | 2026-08-07 | Instrument hit rate, harden to three seeds | 2026-07-24 | hit rate reproduced the earlier single-seed draw exactly |
| [wixqa-retriever-gate](2026-07-24-wixqa-retriever-gate.md) | 2026-07-24 | 2026-08-07 | Rank retrievers offline, then gate | 2026-07-24 | gate opened; it pre-committed to reporting a ceiling had it not |
| [wixqa-dose-response-run](2026-07-25-wixqa-dose-response-run.md) | 2026-07-25 | 2026-08-07 | Run the winner end to end | 2026-07-25 | **0.337 predicted, 0.340 measured** |
| [wixqa-grounding-and-loop-plan](2026-07-25-wixqa-grounding-and-loop-plan.md) | 2026-07-25 | 2026-08-07 | Fix delivery, then add the loop | 2026-08-06 | **both predictions wrong**; its stop rule fired |

**First in git** is the commit that first contains the file, from
`git log --diff-filter=A --follow`. Where it is later than **Ran**, that is stated rather than
smoothed over.

### Studies that ran without a protocol

Naming these matters more than the seven rows above, because a register that only lists successes
is not a register.

| Study | Why there is no protocol |
|---|---|
| Fine-tuning on reference answers | The recipe changed mid-track: the planned loop-generated training set produced no signal at the smoke test, so it was replaced with standard supervised fine-tuning. The change is recorded in the decision log (ADR-028), not in a protocol fixed beforehand. |
| Retrieval fair tests (reranking, larger corpus) | Written as rescue attempts after the null, not planned in advance. They are reported as single-seed and labelled as such. |
| Student prompt style | Same — a question left open at the design gate and closed opportunistically later. |
| Reliability sweep | An extension of an existing study rather than a new design. |

---

## One document contains material added after its run

[`2026-07-25-wixqa-grounding-and-loop-plan.md`](2026-07-25-wixqa-grounding-and-loop-plan.md) has
results pasted into it — the offline ladder outcome and the pilot verdict — inside what is
otherwise a pre-run plan. It carries a note saying which sections those are. It was left in place
rather than cut, because deleting evidence of an edit is worse than labelling it.

---

## Where the rest of the working documents went

The task specifications and design notes that surrounded these protocols are not published. What
they decided is in the decision log; what mattered from them is compressed into the report; and the
full text remains recoverable from version control. See the report's §12 for the resolution table
and the recovery commit.
