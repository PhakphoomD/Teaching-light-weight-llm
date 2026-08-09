**Table 5**

*Leakage Audit*

| path | what it does | who sees the answer | verdict | where |
|---|---|---|---|---|
| L1 | a prompt template that renders `COPY THIS EXACTLY: {ground_truth}` | **student sees it** | blocker | `config/prompts_config.yml:101-103` |
| L2 | the trigger that switches the student into that template | **student sees it** | blocker | `simplified_teaching_loop.py:358-364` |
| L3 | an early-stop path that sends the same prompt one last time | **student sees it** | blocker | `simplified_teaching_loop.py:622-644` |
| L4 | on success, the reference answer is stored as 'feedback' | **written to memory** | blocker | `simplified_teaching_loop.py:707-716` |
| L5 | a repetition detector that triggers the same hint | **student sees it** | blocker | `simplified_teaching_loop.py:319-354` |
| L6 | round 1 of every question retrieves stored feedback into the student prompt, unconditionally and with no content check | **student sees it** | blocker — structural, not gated by any flag | `simplified_teaching_loop.py:295-300, 368-376` |
| L7 | a teacher template instructing the teacher to end with `Example: {ground_truth}`, whose output is handed to the student | **student sees it** | blocker — confirmed in a production log | `config/prompts_config.yml:369` |
| L8 | teacher feedback written to memory with no leak check | written to memory | major — turns L7 into a permanent one | `simplified_teaching_loop.py:526-534` |
| L9 | the teacher is shown the reference answer on every round | teacher only | legal in isolation — but 70% of the score rewarded resembling that same answer | `config/prompts_config.yml:169-336` |
| L10-L13 | four scoring functions compare against the reference | scoring only | legal | `src/simplified/metrics.py:141-324` |
| L14-L17 | debug logs, terminal display and offline tooling print the reference | logs only | legal — and how L7 was actually caught | `src/simplified/debug_logger.py:82-94` |
| L18 | a notebook that deliberately pre-seeded memory with the answers before the final phase, tagged `source: ground_truth_injection` | **written to memory** | blocker — the direct cause of the reported 100% | `logs/experiments/phase6/gt_memory_store.jsonl` |

### The seven seals, and why each is structural rather than procedural

| seal | how it holds |
|---|---|
| the student's call signature cannot receive the reference answer | structural — a leak has to be added deliberately, not forgotten |
| a store-time tripwire rejects any note that contains the answer | three independent checks: exact substring, a 12-token shingle, and cosine similarity above 0.80; red-teamed against the 32 leaked records from the old store, which it rejects 100% of the time |
| `assert_gt_free` inspects every prompt on the framework's answering path -- the arm that is shown the reference, and every retrieval run -- before the model is called | aborts the run rather than logging a warning; it fired once, on the arm designed to leak. The WixQA study runs outside this path and is sealed differently: its retrieval index never contains the 200 expert answers, so there is nothing for a guard to catch |
| the judge must come from a different model family than the student | enforced when the configuration loads, not by convention |
| the retrieval corpus is built from the training split only | 506 records → 448 after dropping near-duplicates of held-out answers → **414** after dropping template twins that share verbatim blocks but not enough cosine similarity to be caught the first way |
| the support-documentation study is sealed by what is indexed, not by a runtime check | its index holds the 6,221 knowledge-base articles and never the 200 expert answers, so the reference is absent from anything the retriever can return |
| any retrieved passage still sharing a 12-token span with the held-out answer is dropped at run time | dropped and **counted**, so the filter's own activity is reportable rather than silent |

*Note.* Eighteen ways the answer could reach the student, and the seven seals that closed them. The audit that turned a good-looking result into a retracted one. Every row was found by reading the code rather than by observing a symptom, which matters: three of these paths were switched off by configuration at the time and would have looked clean in any log. The line the audit draws is that a model may be *taught* using the reference answer but never *shown* it while being measured — so a teacher seeing the answer is legal and a memory store handing that answer back to the student is not. The second table is what the rebuild put in place, and the design rule behind all seven is the same: make the failure impossible to reintroduce rather than remembering not to. Source: docs/LEAKAGE_AUDIT.md.
