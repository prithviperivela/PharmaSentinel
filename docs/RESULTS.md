# Frozen final results

All four procedures were fixed before final-test performance was accessed. Test evaluation covers 967 eligible passages (1,009 gold core events); one invalid upstream passage is explicitly excluded. Values below come from saved outputs, not targets.

## Primary measure 1: complete-event extraction

Exact event type and all trigger/drug/effect span sets must agree. This reduced core-event task is not directly comparable with published full-PHEE scores.

| Mode | Precision | Recall | Strict F1 | F1 95% interval | TP / FP / FN |
|---|---:|---:|---:|---|---|
| BiLSTM baseline | 12.6% | 15.1% | 13.7% | 11.4%–15.8% | 152 / 1050 / 857 |
| Original BiomedBERT | 23.5% | 36.2% | 28.5% | 25.6%–31.1% | 365 / 1189 / 644 |
| Conservative mode | 23.8% | 35.9% | 28.6% | 25.7%–31.1% | 362 / 1161 / 647 |
| Precision-oriented mode | 44.4% | 43.0% | 43.7% | 40.6%–46.9% | 434 / 543 / 575 |

## Primary measure 2: errors exposed at 25% passage review

The development-selected policy is fixed for each model. This is an oracle simulation: benchmark annotations reveal all FP + FN in selected passages. A wrong candidate can contribute both FP and FN. These are not measured human time savings.

| Mode | Frozen policy | Capture | 95% interval | Random mean | Candidate-count comparator | Candidates inspected |
|---|---|---:|---|---:|---:|---:|
| BiLSTM baseline | expected_incorrect_candidates | 40.2% | 39.0%–41.3% | 25.1% | 38.7% | 537 |
| Original BiomedBERT | expected_incorrect_candidates | 42.9% | 40.9%–44.6% | 25.0% | 40.0% | 612 |
| Conservative mode | expected_incorrect_candidates | 43.3% | 40.9%–44.9% | 25.0% | 40.6% | 600 |
| Precision-oriented mode | raw | 35.3% | 31.7%–38.5% | 24.9% | 33.5% | 202 |

Models have different error totals; a larger fraction captured does not establish better extraction. Equal passage budgets also do not imply equal reading effort. Intervals use source-prefix groups and fixed fitted models, excluding training and reviewer variability.

## Minority-class results

The conservative rule preserved therapeutic true positives on development data only. It is not a guarantee on unseen passages. Precision mode failed that rule and remains explicitly separate.

| Mode | Adverse F1 | Therapeutic F1 | Therapeutic recall | Therapeutic TP / gold |
|---|---:|---:|---:|---:|
| BiLSTM baseline | 14.7% | 6.0% | 5.8% | 7 / 120 |
| Original BiomedBERT | 31.2% | 11.5% | 16.7% | 20 / 120 |
| Conservative mode | 31.2% | 11.8% | 16.7% | 20 / 120 |
| Precision-oriented mode | 45.8% | 23.5% | 18.3% | 22 / 120 |

## Calibration and challenge diagnostics

Brier score concerns emitted candidate correctness; it does not measure missed events or patient risk. Lower is better. The constant comparator is fitted on calibration-data prevalence.

| Mode | Raw Brier | Calibrated Brier | Constant Brier | Synthetic strict F1 | No-event passages with output |
|---|---:|---:|---:|---:|---:|
| BiLSTM baseline | 0.178 | 0.077 | 0.111 | 14.3% | 1 / 4 |
| Original BiomedBERT | 0.420 | 0.138 | 0.180 | 23.5% | 2 / 4 |
| Conservative mode | 0.425 | 0.139 | 0.182 | 23.5% | 2 / 4 |
| Precision-oriented mode | 0.295 | 0.195 | 0.247 | 11.8% | 3 / 4 |

The synthetic test contains only ten self-authored schematic passages. It is a failure probe, not clinical external validation.

## Paired comparisons

- Conservative mode versus BiLSTM baseline: F1 difference +14.8 percentage points; paired 95% interval +12.1 to +17.5.
- Precision-oriented mode versus BiLSTM baseline: F1 difference +30.0 percentage points; paired 95% interval +27.0 to +33.0.
- Conservative mode versus Original BiomedBERT: F1 difference +0.1 percentage points; paired 95% interval -0.2 to +0.3.
- Precision-oriented mode versus Original BiomedBERT: F1 difference +15.2 percentage points; paired 95% interval +12.6 to +17.7.

## What this establishes

A reproducible applied NLP study with controlled loss ablations, held-out evaluation, calibration, review simulation and explicit failures. It does not establish clinical safety, regulatory readiness, population incidence or an Optum deployment. No final-test score is used to tune this release.

The precision recipe's two development seeds achieved 42.7% and 41.8% strict F1. Seed 42 remained the frozen release checkpoint; two runs only provide a limited stability check.

Live MySQL loading remains unverified without a configured server. The schema, parameterized loader and local analytical exports are implemented. See RUNBOOK.md for reproduction and INTERVIEW_GUIDE.md for explanations.
