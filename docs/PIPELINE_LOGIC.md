# Why each stage exists

## Objective

From a short biomedical passage, extract suspected adverse or potential therapeutic
events with the exact trigger, drug and effect evidence. Then evaluate whether a
limited review budget can find extraction errors more effectively than random
review. This supports a pharmacovigilance research workflow; it does not estimate
patient risk, establish causality or perform clinical decision making.

## Inputs, decisions and outputs

| Stage | Input → output | Reason | What can still fail |
|---|---|---|---|
| Acquire | Pinned PHEE2 source → verified local JSONL | Preserve reproducible data identity | Upstream annotations can contain mistakes |
| Validate | Text and role spans → exact offsets plus explicit quarantine | Evidence must point to unchanged text | Valid offsets do not guarantee correct semantics |
| Audit | Prepared examples → class/multiplicity/missing-role summaries | Understand what the benchmark actually contains | It is enriched for events, not a random stream of literature |
| Split | Official development split → source-grouped model-selection, calibration, policy subsets | Give each decision a separate labelled subset | ID prefixes are only a source proxy |
| Baseline | Training examples → independent BiLSTM tags and proximity associations | Establish a lower-complexity comparison on the same target | Proximity can attach a role to the wrong event |
| Fine-tune | Biomedical encoder + training labels → trigger and conditioned-role heads | Use context to associate evidence with an event | Gold-trigger training differs from predicted-trigger inference |
| Select | Model-selection predictions → loss variant and fixed threshold | Test specific errors without tuning on final results | Repeated development choices can overfit this subset |
| Calibrate | Separate calibration predictions → logistic correctness estimator | Relate scores to complete-candidate correctness | Missed events are absent from the candidate population |
| Prioritize | Policy-subset scores → a fixed review ranking rule | Choose allocation at a declared 25% passage budget | Passage count does not equal review time |
| Freeze | Model, config, tokenizer, code, data, calibration and policy → hashes | Fix the evaluated system before test scoring | Hashes cannot prove scientific validity |
| Evaluate | Frozen system + held-out labels → metrics, intervals and failures | Estimate performance beyond the choices used for development | One corpus and a tiny synthetic suite limit generalization |
| Explain | Aggregates + local predictions → report, viewer and SQL exports | Make both successes and errors inspectable | Human/clinical benefit needs separate validation |

## Model in simple terms

BiomedBERT converts each token into a contextual representation. One head assigns
`O`, adverse-trigger BIO, or therapeutic-trigger BIO labels. For each detected
trigger, its pooled representation is joined to every token representation; two
additional heads tag the associated drug and effect evidence. The source offsets
turn tags back into text spans. Empty roles are allowed because the benchmark
contains them; invented evidence is not filled in.

The retry experiments change loss weights, not the evaluation target. Rare-label
weighting can affect the precision/recall tradeoff, so the experiment compares
weighting choices and reports their actual results. The selected trigger threshold
is fixed before calibration, because filtering changes the candidates that the
calibrator will see.

## Two endpoints and their denominators

**Strict core-event F1**: a true positive requires the same type and exact
trigger/drug/effect span sets as one unused gold event. Precision is TP/(TP+FP),
recall TP/(TP+FN), and F1 is 2TP/(2TP+FP+FN). Duplicate predictions are extra FP;
missing predictions leave FN. A wrong complete event can contribute both FP and FN.
This is a declared reduced-schema task, not the published full PHEE evaluation.

**Error capture at 25% review**: rank eligible passages using the frozen policy,
review ceil(0.25 × passage count), and divide their FP+FN by total FP+FN. The
simulation assumes an ideal reviewer identifies every benchmark mismatch in a
reviewed passage. Also show remaining errors, reviewed characters/candidates,
random expected capture, and simple count/length comparators. Comparing capture
alone across models with different error populations can be misleading.

The additive policy sums estimated incorrect *emitted candidates*. It cannot
estimate missed events; its no-output score of 1 is a declared heuristic. A high
ranking score is not a medical severity score. Confidence does not automatically
approve any output.

## Scope of the contribution

Data-science concepts: EDA, class imbalance, token/span alignment, supervised NLP,
transfer learning, multi-task learning, controlled ablations, threshold selection,
calibration, baseline comparison, grouped bootstrap uncertainty, subgroup/error
analysis, and review-budget analytics.

Supporting software concepts: Python modules/CLI, file integrity and experiment
versioning, focused regression tests, parameterized MySQL inserts and analytical
queries, and a local Streamlit/Plotly viewer. There is no need for an API service,
microservices, orchestration cluster or Power BI to answer this research question.

The contribution is the reproducible applied system and its evidence, not an
assertion that transformers, calibration or review prioritization were invented
here. Distinguish work you implemented and validated from the pretrained model and
dataset supplied by their authors.
