# Documentation

This project asked one question: **what actually makes a small local language model better at one
domain, and what only looks like it does?**

There is one document that answers it, and everything else supports that document. No file in this
directory other than the report states a headline number, so there is nowhere for a number to drift
to.

| | | |
|---|---|---|
| **[EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md)** | **The report.** Purpose, objectives and the rules fixed before each run, method, eight studies, discussion, limitations. | ~35 min |
| [LEAKAGE_AUDIT.md](LEAKAGE_AUDIT.md) | *Appendix A.* How the reference answer reached the model in the original system — eighteen paths — and the six mechanisms that closed them. | ~7 min |
| [protocol/](protocol/README.md) | *Appendix B.* What was decided before each study ran, dated, with a register stating what those dates can and cannot prove. | browse |
| [HOW_TO_RUN.md](HOW_TO_RUN.md) | **The operating manual.** Setup, how to verify each published number without running a model, every test file and how to run one, how to run an experiment, and what to do when a command fails. | ~8 min |
| [archive/](archive/) | Superseded documents, each with a banner naming what was wrong in it and which decision corrects it. Kept deliberately: the correction is part of the record. | browse |
| `plan/` | Working notes — the task specifications written before each piece of work. Not published; recoverable from version control at the commit named in the report's §12.4. | — |

## Where the evidence is

- **[`reports/`](../reports/README.md)** — the committed analysis outputs behind every number, one
  directory per study, each carrying the command that regenerates it. Also
  [17 figures](../reports/figures/README.md) and
  [21 tables](../reports/tables/).
- **`runs/`** — raw run artifacts, grouped by the question each study answers. Gitignored except the
  small evidence files; every one is rebuildable from a config and a seed.

## The rules everything here follows

Decisions live in [`.claude/rules/decisions.md`](../.claude/rules/decisions.md) and the constitution
in [`.claude/rules/00-index.md`](../.claude/rules/00-index.md). Two of them shape these documents
more than the rest:

- **Honesty over optics** — every reported number must match its source log. Negative results are
  reported as plainly as positive ones, and most of the findings here are negative.
- **Evidence-backed** — a claim cites a file, a line, or a command that was actually run.
