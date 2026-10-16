# Explaining PharmaSentinel in interviews

## A short explanation

“I built a biomedical NLP and analytics pipeline that extracts event-associated drug and effect
evidence from research passages. I compared a BiLSTM baseline with a fine-tuned biomedical
transformer, measured complete-event errors, and evaluated confidence-based prioritization under
fixed review budgets. Every extraction links back to its source text.”

Use measured results from the final report when they exist. Do not substitute development results
for test performance or say the project proves clinical causality.

See [RESULTS.md](RESULTS.md) for the frozen four-model comparison and confidence intervals.
The primary measures are strict core-event F1 and error capture at a 25% passage budget.
Describe the latter as a benchmark review simulation, never as measured operational savings.

## Research lineage and evaluation answer

The [PHEE paper](https://aclanthology.org/2022.emnlp-main.376/) motivates the
pharmacovigilance event task and provides the original dataset and schema. We used
the revised source annotations linked from the authors' later
[empirical study](https://aclanthology.org/2024.eacl-short.30/). Microsoft's
[BiomedBERT model](https://huggingface.co/microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext)
supplies the pretrained biomedical encoder, based on
[Gu et al.](https://arxiv.org/abs/2007.15779). Confidence calibration is an
established idea discussed by [Guo et al.](https://arxiv.org/abs/1706.04599);
our actual implementation uses a regularized logistic model on candidate features.
We built the task-specific heads, data audit, reduced event evaluator, ablations,
calibration/review experiment and viewer. We do not claim to have invented the
dataset, transformer or calibration method.

**A useful 45-second answer:** “I chose exact complete-event F1 as the primary
measure because a pharmacovigilance event is useful only when the event type and
its trigger, drug and effect evidence are connected correctly. A system can find
the drug name yet link it to the wrong effect, so a drug-span score alone would
overstate performance. I match predictions one-to-one against gold events, count
duplicates as false positives and misses as false negatives, and report precision,
recall and the adverse/therapeutic breakdown. I kept separate development subsets
for model choice, confidence calibration and review-policy choice, froze those
decisions, then scored 967 eligible test passages once. The selected mode reached
43.7% strict F1 versus 28.5% for our original transformer. Its therapeutic recall
was only 18.3%, so I present this as an evaluated research prototype.”

**If asked about published PHEE scores:** The original paper reports trigger and
argument extraction separately and includes a larger hierarchical schema. Our
reduced exact *joint* event score requires all retained fields to agree at once;
it is not numerically comparable with their trigger, argument or token-overlap F1.
The relaxed overlap score and 83.2% drug-span precision are diagnostics, not
replacements for the complete-event headline.

**If asked about uncertainty:** The 95% interval resamples source-prefix groups
with fixed trained models. It captures sampling variation under that grouping,
not variation across training seeds, hospital populations or clinical reviewers.
The 25% review result assumes an ideal reviewer finds every benchmark error in
a selected passage; it is not measured time savings.

## Measured project bullets

Use these only when you can explain the implementation and your own contributions:

- Built a biomedical NLP pipeline on 4,827 PHEE2 passages, comparing a BiLSTM
  baseline with trigger-conditioned BiomedBERT; achieved **43.7% strict core-event
  F1 on 967 held-out passages**, versus **28.5%** for the original transformer.
- Evaluated calibrated extraction confidence and review prioritization; the frozen
  policy exposed **35.3% of benchmark FP + FN errors at a 25% passage-review budget**,
  versus **24.9%** for random review, with source-group bootstrap uncertainty.
- Implemented data/offset audits, controlled loss ablations, a second-seed check,
  **41 passing tests**, a Streamlit evidence viewer and MySQL analytical exports.

Explain that 43.7% is exact-event F1, not classification accuracy; review capture is
simulated, not a measured reduction in staff workload. Therapeutic recall was 18.3%,
and precision mode failed on 3/4 synthetic no-event passages. These limitations
give concrete next research questions rather than reasons to hide the results.

## Questions you should be able to answer

**Why this problem?** Drug-safety text can describe adverse associations and beneficial treatment
uses in the same passage. Correct association and traceable evidence matter beyond name recognition.

**Which data?** Pinned PHEE2 source annotations, plus an explicitly synthetic diagnostic suite.
Explain the source attribution, class imbalance, empty roles and passage-level scope.

**What data issue did you find?** One annotation failed exact text/offset validation; its passage
was quarantined explicitly. The multiplicity metadata also did not consistently describe event-array
counts, so multiplicity was derived from the actual annotations. Explain why silent repair is risky.

**Why BiomedBERT?** It supplies biomedical pretrained representations. Task-specific heads learn
typed triggers and associated role spans. Pretraining, task fine-tuning and new research invention are
different contributions.

**Why a baseline?** It isolates whether a more contextual, event-conditioned model improves the
declared task over independent tagging and proximity. Both use identical evaluation scope and splits.

**What did the loss experiments teach you?** Inverse-frequency weighting encouraged more
predictions, including false positives. Unweighted cross-entropy improved development F1;
boosting therapeutic trigger weights partly recovered minority detections but did not meet the
fixed safeguard. This is empirical evidence about this setup, not a universal rule against weights.

**Why retain two modes?** Overall F1 and therapeutic recall can disagree. The precision-oriented
recipe failed the conservative development safeguard, so I disclosed it as a separate tradeoff
and froze both before testing. The safeguard was never relaxed to make a result look better.

**Was the improvement just a lucky seed?** Two development runs gave 42.7% and 41.8% F1.
That is a useful limited check; more seeds and external data are needed for broader robustness.
I retained the primary seed regardless of the repeat result.

**How do you prevent leakage?** Source-prefix grouping, exact/lexical duplicate checks, separate
model-selection/calibration/policy subsets, and a hash-checked frozen test protocol. State the proxy
grouping and semantic-leakage limitations rather than promising perfect independence.

**Why is event F1 lower than medicine F1?** A complete event needs the correct trigger, type, drug
evidence, effect evidence and association together. Good standalone word recognition is insufficient.

**What is calibration?** Whether a candidate's confidence corresponds to its observed correctness.
Show a reliability plot and Brier score. Better calibration does not necessarily improve ranking,
especially when passages contain different numbers of candidates.

**What is your evaluated component?** Evidence highlighting plus confidence/review analysis,
including an additive expected-incorrect-candidate score. Compare actual error capture at equal
passage budgets. If raw confidence performs better, explain that finding honestly.

**Are you measuring actual review savings?** No. The current experiment simulates an ideal reviewer
using benchmark annotations. Real time savings require a separate timed, appropriately designed study.

**What did SQL add?** Joins between source passages, gold/predicted events and experiment runs;
conditional aggregation for missing fields; corpus frequencies; and passage-ranking queries.
If the database was not connected, say schema/export code was prepared rather than claiming live use.

**What does the dashboard show?** Data composition, exact event quality, difficult subgroups,
confidence reliability and review curves. Evidence highlights show source provenance, not causal proof.

**What would you improve next?** Robustness across seeds, better rare-class performance, difficult
grouping/overlap handling, independently annotated no-event text and external validation. Select based
on the measured error report, not the number of technologies that can be added.

**Why is this relevant to a healthcare analytics employer?** It demonstrates extracting traceable
information from biomedical text and making error-aware review decisions. These skills can support
pharmacy and evidence-analysis workflows. This project uses no Optum data, has no Optum integration,
and does not claim to reproduce an internal company system.

## Role emphasis

Data Analyst: data audit, SQL, denominators, visualization, statistical uncertainty and decisions from
measured comparisons. Data Science: model architecture, loss/imbalance, calibration and ablations.
Associate Software Engineer: modular Python, schema design, reliable offsets, evaluator tests and
reproducibility. This version intentionally has less backend breadth than a service-heavy application.

## Claims to avoid

- “The model detects dangerous medicines” or “proves a drug caused harm.”
- “The corpus frequency is a population adverse-event rate.”
- “I achieved published PHEE performance” with a different schema or split.
- “I saved reviewers X% time” based only on oracle-review simulations.
- “This guarantees selection at Optum.”
- “I invented transformers, confidence calibration or the dataset.”

State your own actual work and assistance accurately; be ready to reproduce and explain every result.
