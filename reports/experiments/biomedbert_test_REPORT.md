# PharmaSentinel: biomedbert results on test

Evaluation status: final held-out test.

## Dataset

Primary benchmark: pinned PHEE2 source annotations. Original source files contain 4,827 passages. Annotation issues, split IDs and hashes are recorded in `reports/data/`. One passage has an invalid upstream evidence annotation and is explicitly quarantined from training/scoring. Source-ID grouping is a proxy; the lexical near-duplicate screen does not rule out all semantic leakage.

## Evaluation definition

A strict core event requires the correct event type and exact trigger, drug-role and effect-role span sets. Matching is one-to-one; duplicate predictions are false positives. Empty roles are permitted when gold annotations are empty. This reduced-schema metric is not directly comparable with published full-PHEE scores.

| Scope | Precision | Recall | F1 |
|---|---:|---:|---:|
| Strict core event | 0.235 | 0.362 | 0.285 |
| Relaxed event (role character IoU ≥ 0.5) | 0.441 | 0.680 | 0.535 |
| trigger evidence segments | 0.486 | 0.748 | 0.589 |
| drug evidence segments | 0.514 | 0.910 | 0.657 |
| effect evidence segments | 0.336 | 0.724 | 0.459 |

Evaluated passages: **967**. Exact matches: **365**; unmatched predictions: **1189**; unmatched gold events: **644**.

Standalone evidence scores do not establish correct event association. The difference from strict event F1 is part of the error analysis.

Strict event F1 source-group bootstrap interval: **0.256–0.311**, 200 resamples. This interval addresses sampled-source variation, not all training-seed variation.

## Calibration and review

Candidate Brier score (lower is better): raw **0.4200**, calibrated **0.1379**.

Calibration is fitted on the separate calibration subset. Better calibration does not guarantee better ranking or error capture at a fixed budget. Compare each policy's actual results.

| Policy | Review budget | Reviewed passages | Error capture | Missed events exposed |
|---|---:|---:|---:|---:|
| random | 10% | 97 | 10.1% | 65.2 |
| raw | 10% | 97 | 12.9% | 78.0 |
| calibrated | 10% | 97 | 13.3% | 79.0 |
| calibrated_checks | 10% | 97 | 13.3% | 79.0 |
| expected_incorrect_candidates | 10% | 97 | 21.3% | 96.0 |
| candidate_count | 10% | 97 | 20.9% | 92.0 |
| passage_length | 10% | 97 | 14.8% | 95.0 |
| random | 25% | 242 | 25.0% | 161.3 |
| raw | 25% | 242 | 35.7% | 202.0 |
| calibrated | 25% | 242 | 36.2% | 204.0 |
| calibrated_checks | 25% | 242 | 36.2% | 204.0 |
| expected_incorrect_candidates | 25% | 242 | 42.9% | 220.0 |
| candidate_count | 25% | 242 | 40.0% | 194.0 |
| passage_length | 25% | 242 | 33.3% | 213.0 |
| random | 50% | 484 | 50.1% | 322.6 |
| raw | 50% | 484 | 68.6% | 410.0 |
| calibrated | 50% | 484 | 69.0% | 409.0 |
| calibrated_checks | 50% | 484 | 69.0% | 409.0 |
| expected_incorrect_candidates | 50% | 484 | 70.6% | 372.0 |
| candidate_count | 50% | 484 | 70.3% | 368.0 |
| passage_length | 50% | 484 | 61.2% | 383.0 |

These are oracle-review simulations: every gold/prediction mismatch in a reviewed passage is assumed discoverable. The error unit is FP + FN; one wrong extraction may contribute both. Reviewer time savings and clinical benefit were not measured.

## Interpretation for interviews

Explain the data issue and how it was handled, the baseline association rule, why exact event extraction is harder than recognizing individual words, how the held-out subsets prevent leakage, and whether calibration improved the chosen operational metric. Discuss the therapeutic minority class and difficult structures rather than hiding them.

## Limitations

Passage-level, event-enriched benchmark; no clinical causality inference. Original entity grouping is retained in prepared annotations but not fully reconstructed by this reduced event-role decoder. Overlapping trigger/role spans may not be representable. The synthetic challenge suite is self-authored and not expert validation. Corpus counts are not adverse-event incidence.

Interactive aggregate report: [open charts](../figures/biomedbert_test_analytics.html).
