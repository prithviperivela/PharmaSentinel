# Evaluation protocol

## Question and declared task

Can a biomedical, event-conditioned extractor improve complete event extraction over a simple
BiLSTM/proximity baseline, and can review prioritization expose more errors at equal passage budgets?

The reduced core event is `(event type, trigger span set, drug-role span set, effect-role span set)`.
It omits dose, severity, subject and fine-grained entity-group reconstruction. Scores are not a
reproduction of the published full-PHEE evaluation.

## Split discipline

- Fit model parameters on training only.
- Select checkpoints by strict core-event F1 on model-selection development data. Break ties by
  mean trigger/drug/effect evidence F1.
- Fit a regularized logistic candidate-correctness calibrator on calibration development data only.
  If data has fewer than 20 predicted candidates or one class, record an identity fallback.
- Compare policies on the separate policy subset. Select by error capture at a 25% passage budget;
  retain all policy results and break ties by the declared fixed order.
- Freeze weights, tokenization/configuration, calibrator, policy, pipeline code and data identities
  before final test access. A source-context integrity audit is not model tuning on test labels.
- Report final test once choices are frozen. Later changes require a versioned protocol and a clear
  disclosure that the existing test set has already been inspected.

## Matching and metrics

Strict events use multiset intersection: one gold event can match at most one prediction. Duplicates
add false positives. Missing passage predictions contribute all their gold events as false negatives.
An explicitly quarantined passage is excluded with an ID/count in the report.

Precision = TP / (TP + FP); recall = TP / (TP + FN); F1 = 2TP / (2TP + FP + FN).
Zero denominators return zero and counts remain visible. Empty gold roles can match empty predictions.

Relaxed events require the same type and character-set IoU ≥0.5 in each role, including trigger.
Empty/empty roles have IoU 1. A maximum bipartite assignment gives one-to-one matches. This is a
separately labeled diagnostic, not a substitute for the strict headline metric.

Standalone role evidence scores evaluate segment boundaries without establishing complete event
membership. Trigger scores include type. The trigger confusion matrix records exact-span type
matches plus missed/spurious trigger categories.

Strict event FN includes wrong role/boundary predictions as well as wholly absent events. Therefore
also report gold triggers with no predicted trigger overlap. Error analysis categorizes unmatched
predictions by trigger, type, role evidence and duplicate/grouping failures.

## Statistical uncertainty

Use 200 deterministic source-prefix bootstrap resamples for initial 95% F1 intervals. A paired model
comparison resamples the same groups for both models and reports the F1-difference interval. These
measure sampling variation under the proxy grouping, not seed variation or clinical generalization.
The initial experiment uses seed 42; multiple training seeds are a subsequent robustness experiment.

## Candidate calibration

The v2 primary endpoints and fixed ablation rules are recorded in
`EXPERIMENT_PLAN_V2.md`. Models are chosen using model-selection data alone, with
recall and therapeutic-class safeguards. A selected inference threshold is part of
the model configuration identity; it is not refitted on policy or test examples.

Target: strict correctness of an emitted candidate, with one-to-one gold assignment. Features:
raw candidate confidence, trigger confidence and weakest extracted-role confidence. The logistic
model is regularized and its settings are fixed rather than extensively tuned on a small subset.

The baseline raw candidate score is the minimum of trigger and extracted-role confidence; a missing
role gives a zero raw role score, which is a conservative heuristic even when a gold role is empty.
Calibrated scores are empirical correctness estimates within this task, not medical risk estimates.

Report Brier score and reliability bins outside the calibration-fitting subset. Candidate populations
differ across extractors, so do not treat cross-model Brier differences alone as a model-quality ranking.
Missed events are absent from candidate calibration and remain in passage-level error analysis.

The updated report also compares calibrated Brier score with a constant equal to
correctness prevalence in the calibration-fitting subset. This checks whether the
calibrator adds information beyond learning that most candidates are incorrect.

## Review experiments

Budget unit: passages, with `ceil(budget × evaluated passages)` reviewed at 10%, 25% and 50%.
Policies:

1. Random order, averaged over 100 seeded permutations.
2. Raw weakest-candidate confidence.
3. Calibrated weakest-candidate confidence.
4. Calibrated confidence with visible structural issues prioritized first.
5. Sum of estimated incorrect emitted candidates, `sum(1 - q)`, with a 1-point no-output/failure
   fallback. This additive score tests whether accounting for the number of candidates improves
   allocation. The fallback is heuristic and does not estimate the probability of missing an event.

Ties use descending passage ID. All passages, including zero-output passages, can be reviewed.
The error unit is unmatched predictions + unmatched gold core events. A wrong prediction may count
as both FP and FN. Capture fraction = errors in reviewed passages / all errors.

The v2 report adds candidate-count and passage-length diagnostic baselines; these
are excluded from selection among the four originally declared nonrandom policies.
Capture intervals resample source-prefix groups 300 times, recomputing rankings and
passage budgets each time. They condition on the fitted model and calibrator.
Lift uses the exact expected random capture, reviewed passages / evaluated passages.
Report residual absolute errors and reviewed candidate/character totals alongside
capture. A model with more initial errors can have higher capture and still leave
more errors after review.

This is an oracle-review simulation: all annotated mismatches in a reviewed passage are assumed
discoverable. It does not measure actual reviewer accuracy, time savings, medical severity or benefit.
Unreviewed candidates are pending; no policy automatically approves a clinical report.

## Challenge data

Run diagnostic synthetic development examples during implementation. Evaluate the reserved
synthetic examples only after freezing choices. Their small size and shared schematic categories
must be disclosed. They are not representative of deployment traffic.

