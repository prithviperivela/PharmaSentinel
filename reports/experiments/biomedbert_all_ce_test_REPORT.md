# PharmaSentinel: biomedbert_all_ce results on test

Evaluation status: final held-out test.

## Dataset

Primary benchmark: pinned PHEE2 source annotations. Original source files contain 4,827 passages. Annotation issues, split IDs and hashes are recorded in `reports/data/`. One passage has an invalid upstream evidence annotation and is explicitly quarantined from training/scoring. Source-ID grouping is a proxy; the lexical near-duplicate screen does not rule out all semantic leakage.

## Evaluation definition

A strict core event requires the correct event type and exact trigger, drug-role and effect-role span sets. Matching is one-to-one; duplicate predictions are false positives. Empty roles are permitted when gold annotations are empty. This reduced-schema metric is not directly comparable with published full-PHEE scores.

| Scope | Precision | Recall | F1 |
|---|---:|---:|---:|
| Strict core event | 0.444 | 0.430 | 0.437 |
| Relaxed event (role character IoU ≥ 0.5) | 0.627 | 0.608 | 0.617 |
| trigger evidence segments | 0.714 | 0.692 | 0.703 |
| drug evidence segments | 0.832 | 0.761 | 0.795 |
| effect evidence segments | 0.602 | 0.669 | 0.634 |

Evaluated passages: **967**. Exact matches: **434**; unmatched predictions: **543**; unmatched gold events: **575**.

Standalone evidence scores do not establish correct event association. The difference from strict event F1 is part of the error analysis.

Strict event F1 source-group bootstrap interval: **0.406–0.469**, 200 resamples. This interval addresses sampled-source variation, not all training-seed variation.

## Calibration and review

Candidate Brier score (lower is better): raw **0.2950**, calibrated **0.1954**.

Calibration is fitted on the separate calibration subset. Better calibration does not guarantee better ranking or error capture at a fixed budget. Compare each policy's actual results.

| Policy | Review budget | Reviewed passages | Error capture | Missed events exposed |
|---|---:|---:|---:|---:|
| random | 10% | 97 | 10.0% | 57.7 |
| raw | 10% | 97 | 11.6% | 92.0 |
| calibrated | 10% | 97 | 10.8% | 101.0 |
| calibrated_checks | 10% | 97 | 10.8% | 101.0 |
| expected_incorrect_candidates | 10% | 97 | 18.3% | 71.0 |
| candidate_count | 10% | 97 | 19.1% | 69.0 |
| passage_length | 10% | 97 | 15.2% | 92.0 |
| random | 25% | 242 | 24.9% | 143.7 |
| raw | 25% | 242 | 35.3% | 227.0 |
| calibrated | 25% | 242 | 35.8% | 228.0 |
| calibrated_checks | 25% | 242 | 35.8% | 228.0 |
| expected_incorrect_candidates | 25% | 242 | 36.0% | 207.0 |
| candidate_count | 25% | 242 | 33.5% | 151.0 |
| passage_length | 25% | 242 | 33.5% | 202.0 |
| random | 50% | 484 | 50.3% | 288.1 |
| raw | 50% | 484 | 71.8% | 417.0 |
| calibrated | 50% | 484 | 71.2% | 413.0 |
| calibrated_checks | 50% | 484 | 71.2% | 413.0 |
| expected_incorrect_candidates | 50% | 484 | 71.4% | 413.0 |
| candidate_count | 50% | 484 | 54.7% | 275.0 |
| passage_length | 50% | 484 | 61.5% | 357.0 |

These are oracle-review simulations: every gold/prediction mismatch in a reviewed passage is assumed discoverable. The error unit is FP + FN; one wrong extraction may contribute both. Reviewer time savings and clinical benefit were not measured.

## Interpretation for interviews

Explain the data issue and how it was handled, the baseline association rule, why exact event extraction is harder than recognizing individual words, how the held-out subsets prevent leakage, and whether calibration improved the chosen operational metric. Discuss the therapeutic minority class and difficult structures rather than hiding them.

## Limitations

Passage-level, event-enriched benchmark; no clinical causality inference. Original entity grouping is retained in prepared annotations but not fully reconstructed by this reduced event-role decoder. Overlapping trigger/role spans may not be representable. The synthetic challenge suite is self-authored and not expert validation. Corpus counts are not adverse-event incidence.

Interactive aggregate report: [open charts](../figures/biomedbert_all_ce_test_analytics.html).
