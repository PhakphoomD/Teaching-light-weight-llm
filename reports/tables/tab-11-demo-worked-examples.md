**Table 11**

*Demo Worked Examples*

| question | answer's article retrieved | no retrieval | narrow window | wider window |
|---|---|---|---|---|
| I am inquiring about purchasing the yearly premium plan for $17.00, which includes a fre | yes | 1 | 2 | 2 |
| I'm want to know how much it would cost to upgrade my email plan. | yes | 2 | 3 | 3 |
| Can I start accepting payments on my site while my Wix Payments account is still under v | no | 3 | 2 | 1 |
| I want to know if the Wix store function work for selling services instead of just physi | no | 1 | 3 | 3 |

*Note.* The same questions, answered three ways by the local model Each question run through the local 3B with no retrieval, with retrieval and a narrow grounding window, and with retrieval and the wider centred window, then scored 0-4 by the same judge. The set deliberately includes a question whose answer-bearing article was not retrieved, and it gets worse rather than better -- which is the tug-of-war showing up in four examples rather than in 600 cells. Source: reports/rag-wixqa/demo-showcase.jsonl.
