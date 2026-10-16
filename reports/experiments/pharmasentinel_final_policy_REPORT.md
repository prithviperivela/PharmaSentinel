# PharmaSentinel: pharmasentinel_final results on policy

Evaluation status: development result; not final test performance.

## Dataset

Primary benchmark: pinned PHEE2 source annotations. Original source files contain 4,827 passages. Annotation issues, split IDs and hashes are recorded in `reports/data/`. One passage has an invalid upstream evidence annotation and is explicitly quarantined from training/scoring. Source-ID grouping is a proxy; the lexical near-duplicate screen does not rule out all semantic leakage.

## Evaluation definition

A strict core event requires the correct event type and exact trigger, drug-role and effect-role span sets. Matching is one-to-one; duplicate predictions are false positives. Empty roles are permitted when gold annotations are empty. This reduced-schema metric is not directly comparable with published full-PHEE scores.

| Scope | Precision | Recall | F1 |
|---|---:|---:|---:|
| Strict core event | 0.253 | 0.385 | 0.306 |
| Relaxed event (role character IoU ≥ 0.5) | 0.459 | 0.698 | 0.554 |
| trigger evidence segments | 0.516 | 0.786 | 0.623 |
| drug evidence segments | 0.492 | 0.896 | 0.635 |
| effect evidence segments | 0.375 | 0.775 | 0.505 |

Evaluated passages: **252**. Exact matches: **101**; unmatched predictions: **298**; unmatched gold events: **161**.

Standalone evidence scores do not establish correct event association. The difference from strict event F1 is part of the error analysis.

Strict event F1 source-group bootstrap interval: **0.250–0.365**, 200 resamples. This interval addresses sampled-source variation, not all training-seed variation.

## Calibration and review

Candidate Brier score (lower is better): raw **0.3980**, calibrated **0.1391**.

Calibration is fitted on the separate calibration subset. Better calibration does not guarantee better ranking or error capture at a fixed budget. Compare each policy's actual results.

| Policy | Review budget | Reviewed passages | Error capture | Missed events exposed |
|---|---:|---:|---:|---:|
| random | 10% | 26 | 10.0% | 16.1 |
| raw | 10% | 26 | 13.5% | 21.0 |
| calibrated | 10% | 26 | 15.0% | 21.0 |
| calibrated_checks | 10% | 26 | 15.0% | 21.0 |
| expected_incorrect_candidates | 10% | 26 | 21.6% | 22.0 |
| candidate_count | 10% | 26 | 21.1% | 21.0 |
| passage_length | 10% | 26 | 14.4% | 23.0 |
| random | 25% | 63 | 25.0% | 39.8 |
| raw | 25% | 63 | 36.6% | 52.0 |
| calibrated | 25% | 63 | 37.7% | 52.0 |
| calibrated_checks | 25% | 63 | 37.7% | 52.0 |
| expected_incorrect_candidates | 25% | 63 | 45.3% | 57.0 |
| candidate_count | 25% | 63 | 42.0% | 49.0 |
| passage_length | 25% | 63 | 32.9% | 51.0 |
| random | 50% | 126 | 49.8% | 80.5 |
| raw | 50% | 126 | 70.6% | 106.0 |
| calibrated | 50% | 126 | 71.0% | 106.0 |
| calibrated_checks | 50% | 126 | 71.0% | 106.0 |
| expected_incorrect_candidates | 50% | 126 | 72.3% | 97.0 |
| candidate_count | 50% | 126 | 70.2% | 92.0 |
| passage_length | 50% | 126 | 63.8% | 100.0 |

These are oracle-review simulations: every gold/prediction mismatch in a reviewed passage is assumed discoverable. The error unit is FP + FN; one wrong extraction may contribute both. Reviewer time savings and clinical benefit were not measured.

## Interpretation for interviews

Explain the data issue and how it was handled, the baseline association rule, why exact event extraction is harder than recognizing individual words, how the held-out subsets prevent leakage, and whether calibration improved the chosen operational metric. Discuss the therapeutic minority class and difficult structures rather than hiding them.

## Limitations

Passage-level, event-enriched benchmark; no clinical causality inference. Original entity grouping is retained in prepared annotations but not fully reconstructed by this reduced event-role decoder. Overlapping trigger/role spans may not be representable. The synthetic challenge suite is self-authored and not expert validation. Corpus counts are not adverse-event incidence.

Interactive aggregate report: [open charts](../figures/pharmasentinel_final_policy_analytics.html).
