# PharmaSentinel: biomedbert_all_ce results on policy

Evaluation status: development result; not final test performance.

## Dataset

Primary benchmark: pinned PHEE2 source annotations. Original source files contain 4,827 passages. Annotation issues, split IDs and hashes are recorded in `reports/data/`. One passage has an invalid upstream evidence annotation and is explicitly quarantined from training/scoring. Source-ID grouping is a proxy; the lexical near-duplicate screen does not rule out all semantic leakage.

## Evaluation definition

A strict core event requires the correct event type and exact trigger, drug-role and effect-role span sets. Matching is one-to-one; duplicate predictions are false positives. Empty roles are permitted when gold annotations are empty. This reduced-schema metric is not directly comparable with published full-PHEE scores.

| Scope | Precision | Recall | F1 |
|---|---:|---:|---:|
| Strict core event | 0.486 | 0.469 | 0.478 |
| Relaxed event (role character IoU ≥ 0.5) | 0.652 | 0.630 | 0.641 |
| trigger evidence segments | 0.798 | 0.771 | 0.784 |
| drug evidence segments | 0.794 | 0.719 | 0.754 |
| effect evidence segments | 0.649 | 0.719 | 0.682 |

Evaluated passages: **252**. Exact matches: **123**; unmatched predictions: **130**; unmatched gold events: **139**.

Standalone evidence scores do not establish correct event association. The difference from strict event F1 is part of the error analysis.

Strict event F1 source-group bootstrap interval: **0.409–0.556**, 200 resamples. This interval addresses sampled-source variation, not all training-seed variation.

## Calibration and review

Candidate Brier score (lower is better): raw **0.2870**, calibrated **0.1994**.

Calibration is fitted on the separate calibration subset. Better calibration does not guarantee better ranking or error capture at a fixed budget. Compare each policy's actual results.

| Policy | Review budget | Reviewed passages | Error capture | Missed events exposed |
|---|---:|---:|---:|---:|
| random | 10% | 26 | 10.2% | 14.2 |
| raw | 10% | 26 | 10.8% | 21.0 |
| calibrated | 10% | 26 | 9.7% | 24.0 |
| calibrated_checks | 10% | 26 | 9.7% | 24.0 |
| expected_incorrect_candidates | 10% | 26 | 19.3% | 18.0 |
| candidate_count | 10% | 26 | 18.2% | 14.0 |
| passage_length | 10% | 26 | 17.1% | 23.0 |
| random | 25% | 63 | 25.2% | 34.9 |
| raw | 25% | 63 | 34.9% | 55.0 |
| calibrated | 25% | 63 | 34.9% | 54.0 |
| calibrated_checks | 25% | 63 | 34.9% | 54.0 |
| expected_incorrect_candidates | 25% | 63 | 34.6% | 47.0 |
| candidate_count | 25% | 63 | 34.2% | 37.0 |
| passage_length | 25% | 63 | 33.5% | 50.0 |
| random | 50% | 126 | 49.9% | 69.7 |
| raw | 50% | 126 | 72.5% | 100.0 |
| calibrated | 50% | 126 | 74.3% | 103.0 |
| calibrated_checks | 50% | 126 | 74.3% | 103.0 |
| expected_incorrect_candidates | 50% | 126 | 74.3% | 103.0 |
| candidate_count | 50% | 126 | 57.6% | 70.0 |
| passage_length | 50% | 126 | 66.9% | 96.0 |

These are oracle-review simulations: every gold/prediction mismatch in a reviewed passage is assumed discoverable. The error unit is FP + FN; one wrong extraction may contribute both. Reviewer time savings and clinical benefit were not measured.

## Interpretation for interviews

Explain the data issue and how it was handled, the baseline association rule, why exact event extraction is harder than recognizing individual words, how the held-out subsets prevent leakage, and whether calibration improved the chosen operational metric. Discuss the therapeutic minority class and difficult structures rather than hiding them.

## Limitations

Passage-level, event-enriched benchmark; no clinical causality inference. Original entity grouping is retained in prepared annotations but not fully reconstructed by this reduced event-role decoder. Overlapping trigger/role spans may not be representable. The synthetic challenge suite is self-authored and not expert validation. Corpus counts are not adverse-event incidence.

Interactive aggregate report: [open charts](../figures/biomedbert_all_ce_policy_analytics.html).
