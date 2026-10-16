# PharmaSentinel: baseline results on test

Evaluation status: final held-out test.

## Dataset

Primary benchmark: pinned PHEE2 source annotations. Original source files contain 4,827 passages. Annotation issues, split IDs and hashes are recorded in `reports/data/`. One passage has an invalid upstream evidence annotation and is explicitly quarantined from training/scoring. Source-ID grouping is a proxy; the lexical near-duplicate screen does not rule out all semantic leakage.

## Evaluation definition

A strict core event requires the correct event type and exact trigger, drug-role and effect-role span sets. Matching is one-to-one; duplicate predictions are false positives. Empty roles are permitted when gold annotations are empty. This reduced-schema metric is not directly comparable with published full-PHEE scores.

| Scope | Precision | Recall | F1 |
|---|---:|---:|---:|
| Strict core event | 0.126 | 0.151 | 0.137 |
| Relaxed event (role character IoU ≥ 0.5) | 0.250 | 0.298 | 0.272 |
| trigger evidence segments | 0.523 | 0.623 | 0.569 |
| drug evidence segments | 0.693 | 0.602 | 0.644 |
| effect evidence segments | 0.382 | 0.440 | 0.409 |

Evaluated passages: **967**. Exact matches: **152**; unmatched predictions: **1050**; unmatched gold events: **857**.

Standalone evidence scores do not establish correct event association. The difference from strict event F1 is part of the error analysis.

Strict event F1 source-group bootstrap interval: **0.114–0.158**, 200 resamples. This interval addresses sampled-source variation, not all training-seed variation.

## Calibration and review

Candidate Brier score (lower is better): raw **0.1779**, calibrated **0.0768**.

Calibration is fitted on the separate calibration subset. Better calibration does not guarantee better ranking or error capture at a fixed budget. Compare each policy's actual results.

| Policy | Review budget | Reviewed passages | Error capture | Missed events exposed |
|---|---:|---:|---:|---:|
| random | 10% | 97 | 10.0% | 85.6 |
| raw | 10% | 97 | 11.5% | 96.0 |
| calibrated | 10% | 97 | 5.2% | 100.0 |
| calibrated_checks | 10% | 97 | 5.2% | 100.0 |
| expected_incorrect_candidates | 10% | 97 | 18.0% | 99.0 |
| candidate_count | 10% | 97 | 17.3% | 92.0 |
| passage_length | 10% | 97 | 13.5% | 107.0 |
| random | 25% | 242 | 25.1% | 215.3 |
| raw | 25% | 242 | 28.0% | 237.0 |
| calibrated | 25% | 242 | 26.3% | 243.0 |
| calibrated_checks | 25% | 242 | 26.3% | 243.0 |
| expected_incorrect_candidates | 25% | 242 | 40.2% | 241.0 |
| candidate_count | 25% | 242 | 38.7% | 228.0 |
| passage_length | 25% | 242 | 30.3% | 248.0 |
| random | 50% | 484 | 50.2% | 429.4 |
| raw | 50% | 484 | 58.2% | 468.0 |
| calibrated | 50% | 484 | 59.0% | 475.0 |
| calibrated_checks | 50% | 484 | 59.0% | 475.0 |
| expected_incorrect_candidates | 50% | 484 | 60.1% | 467.0 |
| candidate_count | 50% | 484 | 62.9% | 436.0 |
| passage_length | 50% | 484 | 56.8% | 469.0 |

These are oracle-review simulations: every gold/prediction mismatch in a reviewed passage is assumed discoverable. The error unit is FP + FN; one wrong extraction may contribute both. Reviewer time savings and clinical benefit were not measured.

## Interpretation for interviews

Explain the data issue and how it was handled, the baseline association rule, why exact event extraction is harder than recognizing individual words, how the held-out subsets prevent leakage, and whether calibration improved the chosen operational metric. Discuss the therapeutic minority class and difficult structures rather than hiding them.

## Limitations

Passage-level, event-enriched benchmark; no clinical causality inference. Original entity grouping is retained in prepared annotations but not fully reconstructed by this reduced event-role decoder. Overlapping trigger/role spans may not be representable. The synthetic challenge suite is self-authored and not expert validation. Corpus counts are not adverse-event incidence.

Interactive aggregate report: [open charts](../figures/baseline_test_analytics.html).
