# PharmaSentinel: project implementation report

## Objective

Extract event-associated drug/effect evidence from biomedical passages, analyze extraction reliability, and compare review allocation at fixed passage budgets. This is a data science research prototype, not clinical decision support.

## Implemented pipeline

Pinned download → annotation audit → EDA/leakage screen → grouped development subsets → BiLSTM and biomedical fine-tuning → strict event evaluation → calibration and review comparison → frozen final evaluation → SQL exports and local viewer.

Data: 4,827 upstream PHEE2 passages. No source-prefix overlap or normalized exact-text overlap between original splits; the documented lexical near-duplicate screen found no candidates at its declared threshold. The grouping/screen do not establish absence of semantic leakage.

Quality findings: 629 multiplicity-flag disagreements; 1 invalid annotation event, with its entire passage explicitly quarantined from training/scoring. Original source text remains unchanged.

## Trained models

| Model | Training passages | Epochs run | Selected epoch | Fine-tuning |
|---|---:|---:|---:|---|
| baseline | 2898 | 8 | 8 | Learned embeddings + BiLSTM heads |
| biomedbert | 2898 | 4 | 3 | Full biomedical encoder + task heads |
| pharmasentinel_final | 2898 | 4 | 3 | Full biomedical encoder + task heads |
| biomedbert_all_ce | 2898 | 4 | 3 | Full biomedical encoder + task heads |

## Measured extraction results

F1 values below are proportions. Strict core-event matching requires exact type and trigger/drug/effect span sets; this is not the published full-PHEE metric.

| Subset | Model | Passages evaluated | Precision | Recall | Strict event F1 |
|---|---|---:|---:|---:|---:|
| Development policy subset | baseline | 252 | 0.127 | 0.149 | 0.137 |
| Development policy subset | biomedbert | 252 | 0.248 | 0.385 | 0.301 |
| Development policy subset | pharmasentinel_final | 252 | 0.253 | 0.385 | 0.306 |
| Development policy subset | biomedbert_all_ce | 252 | 0.486 | 0.469 | 0.478 |
| Frozen held-out test | baseline | 967 | 0.126 | 0.151 | 0.137 |
| Frozen held-out test | biomedbert | 967 | 0.235 | 0.362 | 0.285 |
| Frozen held-out test | pharmasentinel_final | 967 | 0.238 | 0.359 | 0.286 |
| Frozen held-out test | biomedbert_all_ce | 967 | 0.444 | 0.430 | 0.437 |

Final test evaluation is complete for the runs listed above.

## Review allocation

| Subset | Model | Random error capture | Raw-confidence capture | Development-selected policy | Selected-policy capture |
|---|---|---:|---:|---|---:|
| policy | baseline | 25.0% | 29.4% | expected_incorrect_candidates | 40.2% |
| policy | biomedbert | 25.0% | 37.6% | expected_incorrect_candidates | 45.7% |
| policy | pharmasentinel_final | 25.0% | 36.6% | expected_incorrect_candidates | 45.3% |
| policy | biomedbert_all_ce | 25.2% | 34.9% | raw | 34.9% |
| test | baseline | 25.1% | 28.0% | expected_incorrect_candidates | 40.2% |
| test | biomedbert | 25.0% | 35.7% | expected_incorrect_candidates | 42.9% |
| test | pharmasentinel_final | 25.0% | 36.1% | expected_incorrect_candidates | 43.3% |
| test | biomedbert_all_ce | 24.9% | 35.3% | raw | 35.3% |

Budget: 25% of passages. Error unit: unmatched predictions + unmatched gold core events. These are oracle-review simulations, not measured time savings. Calibration quality and ranking quality are evaluated separately. The additive policy's no-output fallback is heuristic.

## Statistical comparison

- policy: biomedical minus baseline F1 = 0.164; paired source-proxy bootstrap 95% interval 0.113–0.220 (500 resamples).
- test: selected v2 minus baseline F1 = 0.148; paired interval 0.121–0.175.
- test: selected v2 minus biomedbert F1 = 0.001; paired interval -0.002–0.003.

## Controlled development experiments

The predeclared primary measures are strict event F1 and error capture at 25% passage review. Model-selection data chooses models; calibration and policy subsets have separate jobs. See EXPERIMENT_PLAN_V2.md for loss ablations, threshold grid and recall/minority safeguards.

| Candidate | Unfiltered F1 | Unfiltered therapeutic TP | Eligible threshold | Selected F1 |
|---|---:|---:|---:|---:|
| biomedbert | 0.305 | 15 | 0.5 | 0.308 |
| biomedbert_trigger_ce | 0.394 | 9 | None | Failed safeguard |
| biomedbert_all_ce | 0.427 | 10 | None | Failed safeguard |
| biomedbert_therapeutic_ce | 0.422 | 14 | None | Failed safeguard |
| biomedbert_therapeutic5_ce | 0.404 | 13 | None | Failed safeguard |

Conservative source: **biomedbert**, trigger threshold **0.5**. The final artifact has a separate run name and configuration identity. Development selection scores are optimistic estimates because they selected the configuration.

The separately declared precision-oriented mode is `biomedbert_all_ce` at threshold 0. Its higher development F1 came with only 10 therapeutic exact matches versus the original 15. It failed the conservative safeguard and is presented as a tradeoff, not as a safeguard-compliant replacement. Both modes were declared before final-test access.

## Verification and remaining work

Focused tests cover offset integrity, one-to-one matching, empty outputs, empty roles, quarantine, review budgets, gold-independent inference and biomedical-head backpropagation. A separate preflight checks selected-checkpoint reload. Verification records live in `reports/verification/`.

The file-based pipeline, local viewer and MySQL analytical exports are implemented. Live MySQL loading requires a configured reachable server; schema and parameterized loader are provided. Public source and aggregate results are published at https://github.com/prithviperivela/PharmaSentinel; raw source passages and local predictions are excluded.

The precision-oriented recipe was repeated at a second seed: model-selection F1 was 42.7% and 41.8%. This is a limited descriptive check. Next research work: more seeds, rare therapeutic-class performance, overlap/grouping improvements and independently annotated out-of-domain/no-event text. The current synthetic suite is self-authored, schematic and not expert clinical validation.

## Interview explanation

Explain why standalone medicine recognition differs from correct complete events, why calibration does not automatically improve ranking, and why per-passage expected candidate errors can differ from weakest-confidence prioritization. Show measured error categories, denominators and failure cases. Do not claim clinical causality or guaranteed employment outcomes.

See `RESULTS.md` for all four frozen comparisons, minority-class results, calibration and review intervals. `INTERVIEW_GUIDE.md`, `EVALUATION_PROTOCOL.md` and `DATA_CARD.md` explain scope and methods.
