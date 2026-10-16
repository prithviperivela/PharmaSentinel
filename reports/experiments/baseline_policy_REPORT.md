# PharmaSentinel: baseline results on policy

Evaluation status: development result; not final test performance.

## Dataset

Primary benchmark: pinned PHEE2 source annotations. Original source files contain 4,827 passages. Annotation issues, split IDs and hashes are recorded in `reports/data/`. One passage has an invalid upstream evidence annotation and is explicitly quarantined from training/scoring. Source-ID grouping is a proxy; the lexical near-duplicate screen does not rule out all semantic leakage.

## Evaluation definition

A strict core event requires the correct event type and exact trigger, drug-role and effect-role span sets. Matching is one-to-one; duplicate predictions are false positives. Empty roles are permitted when gold annotations are empty. This reduced-schema metric is not directly comparable with published full-PHEE scores.

| Scope | Precision | Recall | F1 |
|---|---:|---:|---:|
| Strict core event | 0.127 | 0.149 | 0.137 |
| Relaxed event (role character IoU ≥ 0.5) | 0.245 | 0.286 | 0.264 |
| trigger evidence segments | 0.582 | 0.679 | 0.627 |
| drug evidence segments | 0.696 | 0.575 | 0.630 |
| effect evidence segments | 0.438 | 0.470 | 0.453 |

Evaluated passages: **252**. Exact matches: **39**; unmatched predictions: **267**; unmatched gold events: **223**.

Standalone evidence scores do not establish correct event association. The difference from strict event F1 is part of the error analysis.

Strict event F1 source-group bootstrap interval: **0.108–0.179**, 200 resamples. This interval addresses sampled-source variation, not all training-seed variation.

## Calibration and review

Candidate Brier score (lower is better): raw **0.2002**, calibrated **0.0852**.

Calibration is fitted on the separate calibration subset. Better calibration does not guarantee better ranking or error capture at a fixed budget. Compare each policy's actual results.

| Policy | Review budget | Reviewed passages | Error capture | Missed events exposed |
|---|---:|---:|---:|---:|
| random | 10% | 26 | 10.2% | 22.9 |
| raw | 10% | 26 | 12.2% | 25.0 |
| calibrated | 10% | 26 | 5.7% | 28.0 |
| calibrated_checks | 10% | 26 | 5.7% | 28.0 |
| expected_incorrect_candidates | 10% | 26 | 18.6% | 27.0 |
| candidate_count | 10% | 26 | 17.8% | 26.0 |
| passage_length | 10% | 26 | 13.7% | 26.0 |
| random | 25% | 63 | 25.0% | 55.4 |
| raw | 25% | 63 | 29.4% | 63.0 |
| calibrated | 25% | 63 | 25.3% | 63.0 |
| calibrated_checks | 25% | 63 | 25.3% | 63.0 |
| expected_incorrect_candidates | 25% | 63 | 40.2% | 63.0 |
| candidate_count | 25% | 63 | 39.8% | 62.0 |
| passage_length | 25% | 63 | 31.0% | 64.0 |
| random | 50% | 126 | 49.9% | 111.7 |
| raw | 50% | 126 | 59.0% | 126.0 |
| calibrated | 50% | 126 | 57.6% | 123.0 |
| calibrated_checks | 50% | 126 | 57.6% | 123.0 |
| expected_incorrect_candidates | 50% | 126 | 60.2% | 124.0 |
| candidate_count | 50% | 126 | 64.3% | 119.0 |
| passage_length | 50% | 126 | 59.4% | 126.0 |

These are oracle-review simulations: every gold/prediction mismatch in a reviewed passage is assumed discoverable. The error unit is FP + FN; one wrong extraction may contribute both. Reviewer time savings and clinical benefit were not measured.

## Interpretation for interviews

Explain the data issue and how it was handled, the baseline association rule, why exact event extraction is harder than recognizing individual words, how the held-out subsets prevent leakage, and whether calibration improved the chosen operational metric. Discuss the therapeutic minority class and difficult structures rather than hiding them.

## Limitations

Passage-level, event-enriched benchmark; no clinical causality inference. Original entity grouping is retained in prepared annotations but not fully reconstructed by this reduced event-role decoder. Overlapping trigger/role spans may not be representable. The synthetic challenge suite is self-authored and not expert validation. Corpus counts are not adverse-event incidence.

Interactive aggregate report: [open charts](../figures/baseline_policy_analytics.html).
