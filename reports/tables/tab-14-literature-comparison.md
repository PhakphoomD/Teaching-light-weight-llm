**Table 14**

*Literature Comparison*

| work | what it claims or provides | what was measured here | verdict |
|---|---|---|---|
| Lewis et al. 2020 (arXiv:2005.11401) | Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | the architecture implemented here | used |
| Ovadia et al. 2024 (arXiv:2312.05934) | Fine-Tuning or Retrieval? Comparing Knowledge Injection in LLMs | retrieval +0.152 where a gap existed; fine-tuning −0.292 | **confirmed** |
| Zhou et al. 2023 (arXiv:2305.11206) | LIMA: Less Is More for Alignment | the adapter transferred style and cost completeness (−0.292) | **confirmed** |
| Madaan et al. 2023 (arXiv:2303.17651) | Self-Refine: Iterative Refinement with Self-Feedback | held on a saturated domain (+0.091); did not transfer on top of retrieval at 3B (−0.015, p=0.77) | **contradicted at this scale** |
| Huang et al. 2024 (arXiv:2310.01798) | Large Language Models Cannot Self-Correct Reasoning Yet | the 3B called itself complete 79/133 times; oracle gate +0.038, its own gate +0.000 | **confirmed** |
| Mallen et al. 2023 (arXiv:2212.10511) | When Not to Trust Language Models: Investigating Effectiveness of Parametric and Non-Parametric Memories | reproduced as the tug-of-war: 15 repairs on the hardest, 35 regressions on the easiest | **confirmed** |
| Cuconasu et al. 2024 (arXiv:2401.14887) | The Power of Noise: Redefining Retrieval for RAG Systems | the mechanism behind the MedQuAD null | **confirmed** |
| Shi et al. 2023 (arXiv:2302.00093) | Large Language Models Can Be Easily Distracted by Irrelevant Context | 35 of 39 regressions landed on questions already answered correctly | **confirmed** |
| Liu et al. 2024 (arXiv:2307.03172) | Lost in the Middle: How Language Models Use Long Contexts | centring the window on the matched chunk: +0.071 coverage for 7% more prompt | **confirmed** |
| Kadavath et al. 2022 (arXiv:2207.05221) | Language Models (Mostly) Know What They Know | no cheap uncertainty signal correlated with failure at 3B | **confirmed** (scale-dependent, as predicted) |
| Xiong et al. 2024 (arXiv:2306.13063) | Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs | verbalised self-assessment was uninformative at 3B | **confirmed** |
| Shinn et al. 2023 (arXiv:2303.11366) | Reflexion: Language Agents with Verbal Reinforcement Learning | its lesson applied — grounding kept in every refinement round | applied |
| Xiao et al. 2023 (arXiv:2309.07597) | C-Pack: Packed Resources For General Chinese Embeddings (BGE) | won the offline retriever ladder at 0.665 hit@3 | used |
| Es et al. 2023 (arXiv:2309.15217) | RAGAS: Automated Evaluation of Retrieval Augmented Generation | used as a diagnostic only; unusable here at a 61% null rate | used, with a caveat |
| Luo et al. 2023 (arXiv:2308.08747) | An Empirical Study of Catastrophic Forgetting in LLMs During Continual Fine-tuning | the mechanism behind the −0.292 | **confirmed** |
| Ouyang et al. 2022 (arXiv:2203.02155) | Training Language Models to Follow Instructions with Human Feedback | the alignment-tax framing for the fine-tuning result | applied |
| Chen et al. 2021 (arXiv:2107.03374) | Evaluating Large Language Models Trained on Code (pass@k) | grounding traded diversity for consistency; pass@5 fell 0.89 → 0.74 | used |
| Wang et al. 2023 (arXiv:2203.11171) | Self-Consistency Improves Chain of Thought Reasoning in Language Models | diversity as the source of multi-sample gains, and what grounding spends | applied |
| Geifman et al. 2017 (arXiv:1705.08500) | Selective Classification for Deep Neural Networks | the reliable@k framing — dependable correctness with abstention | applied |
| Kamath et al. 2020 (ACL Anthology 2020.acl-main.503) | Selective Question Answering under Domain Shift | the selective-QA instance of the same framing | applied |
| Ben Abacha et al. 2019 (doi:10.1186/s12859-019-3119-4) | A Question-Entailment Approach to Question Answering (MedQuAD) | testbed 1 — 12,428 pairs in, 10,024 after cleaning; CC BY 4.0 | used |
| Cohen et al. 2025 (arXiv:2505.08643) | WixQA: A Multi-Dataset Benchmark for Enterprise Retrieval-Augmented Generation | testbed 2 — 200 expert questions over 6,221 help-centre articles; MIT | used |
| Lee et al. 2022 (arXiv:2107.06499) | Deduplicating Training Data Makes Language Models Better | the near-duplicate threshold in the cleaning rubric and the corpus scrub | applied |
| Liu et al. 2024 (arXiv:2312.15685) | What Makes Good Data for Alignment? A Comprehensive Study of Automatic Data Selection in Instruction Tuning (DEITA) | the complexity/quality/diversity axes of the readiness rubric | applied |
| Wilson et al. 1927 (doi:10.2307/2276774) | Probable Inference, the Law of Succession, and Statistical Inference | every per-arm interval in this report | applied |
| McNemar et al. 1947 (doi:10.1007/BF02295996) | Note on the Sampling Error of the Difference Between Correlated Proportions or Percentages | the paired significance test on every difference | applied |
| Efron et al. 1993 (ISBN 978-0412042317) | An Introduction to the Bootstrap | the paired cluster bootstrap over questions, 10,000 resamples | applied |
| Rougier et al. 2014 (doi:10.1371/journal.pcbi.1003833) | Ten Simple Rules for Better Figures | message-first design and self-contained captions in every figure here | applied |
| Cleveland et al. 1984 (doi:10.2307/2288400) | Graphical Perception: Theory, Experimentation, and Application to the Development of Graphical Methods | why differences are drawn as position on a common scale, never as bars | applied |
| Appelbaum et al. 2018 (doi:10.1037/amp0000191) | Journal Article Reporting Standards for Quantitative Research in Psychology: The APA Publications and Communications Board Task Force Report | the section structure of the report, the primary/secondary/exploratory grouping of its questions, and the requirement to state registration status plainly | applied |
| Pineau et al. 2021 (arXiv:2003.12206) | Improving Reproducibility in Machine Learning Research (A Report from the NeurIPS 2019 Reproducibility Program) | seeds and resampling counts, compute and cost, and an artifact index — all reported rather than assumed | applied |

### References

1. Lewis, P., Perez, E., Piktus, A., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS 2020. arXiv:2005.11401.
2. Ovadia, O., Brief, M., Mishaeli, M., Elisha, O. (2024). *Fine-Tuning or Retrieval? Comparing Knowledge Injection in LLMs*. EMNLP 2024. arXiv:2312.05934.
3. Zhou, C., Liu, P., Xu, P., et al. (2023). *LIMA: Less Is More for Alignment*. NeurIPS 2023. arXiv:2305.11206.
4. Madaan, A., Tandon, N., Gupta, P., et al. (2023). *Self-Refine: Iterative Refinement with Self-Feedback*. NeurIPS 2023. arXiv:2303.17651.
5. Huang, J., Chen, X., Mishra, S., et al. (2024). *Large Language Models Cannot Self-Correct Reasoning Yet*. ICLR 2024. arXiv:2310.01798.
6. Mallen, A., Asai, A., Zhong, V., et al. (2023). *When Not to Trust Language Models: Investigating Effectiveness of Parametric and Non-Parametric Memories*. ACL 2023. arXiv:2212.10511.
7. Cuconasu, F., Trappolini, G., Siciliano, F., et al. (2024). *The Power of Noise: Redefining Retrieval for RAG Systems*. SIGIR 2024. arXiv:2401.14887.
8. Shi, F., Chen, X., Misra, K., et al. (2023). *Large Language Models Can Be Easily Distracted by Irrelevant Context*. ICML 2023. arXiv:2302.00093.
9. Liu, N. F., Lin, K., Hewitt, J., et al. (2024). *Lost in the Middle: How Language Models Use Long Contexts*. TACL 2024. arXiv:2307.03172.
10. Kadavath, S., Conerly, T., Askell, A., et al. (2022). *Language Models (Mostly) Know What They Know*. preprint. arXiv:2207.05221.
11. Xiong, M., Hu, Z., Lu, X., et al. (2024). *Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs*. ICLR 2024. arXiv:2306.13063.
12. Shinn, N., Cassano, F., Berman, E., et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning*. NeurIPS 2023. arXiv:2303.11366.
13. Xiao, S., Liu, Z., Zhang, P., Muennighoff, N. (2023). *C-Pack: Packed Resources For General Chinese Embeddings (BGE)*. preprint. arXiv:2309.07597.
14. Es, S., James, J., Espinosa-Anke, L., Schockaert, S. (2023). *RAGAS: Automated Evaluation of Retrieval Augmented Generation*. preprint. arXiv:2309.15217.
15. Luo, Y., Yang, Z., Meng, F., et al. (2023). *An Empirical Study of Catastrophic Forgetting in LLMs During Continual Fine-tuning*. preprint. arXiv:2308.08747.
16. Ouyang, L., Wu, J., Jiang, X., et al. (2022). *Training Language Models to Follow Instructions with Human Feedback*. NeurIPS 2022. arXiv:2203.02155.
17. Chen, M., Tworek, J., Jun, H., et al. (2021). *Evaluating Large Language Models Trained on Code (pass@k)*. preprint. arXiv:2107.03374.
18. Wang, X., Wei, J., Schuurmans, D., et al. (2023). *Self-Consistency Improves Chain of Thought Reasoning in Language Models*. ICLR 2023. arXiv:2203.11171.
19. Geifman, Y., El-Yaniv, R. (2017). *Selective Classification for Deep Neural Networks*. NeurIPS 2017. arXiv:1705.08500.
20. Kamath, A., Jia, R., Liang, P. (2020). *Selective Question Answering under Domain Shift*. ACL 2020. ACL Anthology 2020.acl-main.503.
21. Ben Abacha, A., Demner-Fushman, D. (2019). *A Question-Entailment Approach to Question Answering (MedQuAD)*. BMC Bioinformatics 20(1):511. doi:10.1186/s12859-019-3119-4.
22. Cohen, D., Shalom, A., et al. (2025). *WixQA: A Multi-Dataset Benchmark for Enterprise Retrieval-Augmented Generation*. preprint. arXiv:2505.08643.
23. Lee, K., Ippolito, D., Nystrom, A., et al. (2022). *Deduplicating Training Data Makes Language Models Better*. ACL 2022. arXiv:2107.06499.
24. Liu, W., Zeng, W., He, K., et al. (2024). *What Makes Good Data for Alignment? A Comprehensive Study of Automatic Data Selection in Instruction Tuning (DEITA)*. ICLR 2024. arXiv:2312.15685.
25. Wilson, E. B. (1927). *Probable Inference, the Law of Succession, and Statistical Inference*. JASA 22(158):209-212. doi:10.2307/2276774.
26. McNemar, Q. (1947). *Note on the Sampling Error of the Difference Between Correlated Proportions or Percentages*. Psychometrika 12(2):153-157. doi:10.1007/BF02295996.
27. Efron, B., Tibshirani, R. J. (1993). *An Introduction to the Bootstrap*. Chapman & Hall. ISBN 978-0412042317.
28. Rougier, N. P., Droettboom, M., Bourne, P. E. (2014). *Ten Simple Rules for Better Figures*. PLOS Computational Biology 10(9). doi:10.1371/journal.pcbi.1003833.
29. Cleveland, W. S., McGill, R. (1984). *Graphical Perception: Theory, Experimentation, and Application to the Development of Graphical Methods*. JASA 79(387):531-554. doi:10.2307/2288400.
30. Appelbaum, M., Cooper, H., Kline, R. B., et al. (2018). *Journal Article Reporting Standards for Quantitative Research in Psychology: The APA Publications and Communications Board Task Force Report*. American Psychologist 73(1):3-25. doi:10.1037/amp0000191.
31. Pineau, J., Vincent-Lamarre, P., Sinha, K., et al. (2021). *Improving Reproducibility in Machine Learning Research (A Report from the NeurIPS 2019 Reproducibility Program)*. JMLR 22(164):1-20. arXiv:2003.12206.

*Note.* Every work this project used or tested, and what happened when it was measured here Most were confirmed. One was not: iterative self-critique is well established at frontier scale and did not transfer to a 3B model on top of retrieval — which is itself consistent with the self-correction literature, since that predicts precisely this failure when the model must supply its own correctness signal. Rows marked *applied* are methods or frameworks this project adopted rather than tested, and rows marked *used* are components and datasets. The numbered list below is the full bibliography, and it is the single source for the references in `docs/EXPERIMENT_RESULTS.md` — a test asserts every work named in that report appears here.
