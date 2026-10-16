"""Build a compact release report from all four frozen final evaluations."""

from pathlib import Path

from pharmasentinel.io import read_json, write_json
from pharmasentinel.protocol import assert_frozen


def main():
    root = Path(__file__).resolve().parents[1]
    labels = {
        "baseline": "BiLSTM baseline",
        "biomedbert": "Original BiomedBERT",
        "pharmasentinel_final": "Conservative mode",
        "biomedbert_all_ce": "Precision-oriented mode",
    }
    records = {}
    for name in labels:
        assert_frozen(root, name, "test")
        metrics = read_json(root / f"reports/experiments/{name}_test_metrics.json")
        review = read_json(root / f"reports/experiments/{name}_test_review.json")
        policy = read_json(root / f"artifacts/{name}/review_policy.json")["selected_policy"]
        records[name] = {
            "label": labels[name],
            "metrics": metrics,
            "selected_review_policy": policy,
            "review_at_25pct": {r["policy"]: r for r in review["review"]["results"] if r["budget"] == 0.25},
            "reliability": review["reliability"],
            "challenge": read_json(root / f"reports/experiments/{name}_challenge_test_metrics.json"),
        }
    lines = [
        "# Frozen final results", "",
        "All four procedures were fixed before final-test performance was accessed. Test evaluation covers 967 eligible passages (1,009 gold core events); one invalid upstream passage is explicitly excluded. Values below come from saved outputs, not targets.", "",
        "## Primary measure 1: complete-event extraction", "",
        "Exact event type and all trigger/drug/effect span sets must agree. This reduced core-event task is not directly comparable with published full-PHEE scores.", "",
        "| Mode | Precision | Recall | Strict F1 | F1 95% interval | TP / FP / FN |",
        "|---|---:|---:|---:|---|---|",
    ]
    for name, record in records.items():
        m = record["metrics"]["strict_event"]
        ci = record["metrics"]["strict_f1_group_bootstrap_95pct"]
        lines.append(f"| {record['label']} | {m['precision']:.1%} | {m['recall']:.1%} | {m['f1']:.1%} | {ci['lower']:.1%}–{ci['upper']:.1%} | {m['tp']} / {m['fp']} / {m['fn']} |")
    lines += ["", "## Primary measure 2: errors exposed at 25% passage review", "",
              "The development-selected policy is fixed for each model. This is an oracle simulation: benchmark annotations reveal all FP + FN in selected passages. A wrong candidate can contribute both FP and FN. These are not measured human time savings.", "",
              "| Mode | Frozen policy | Capture | 95% interval | Random mean | Candidate-count comparator | Candidates inspected |",
              "|---|---|---:|---|---:|---:|---:|"]
    for record in records.values():
        r = record["review_at_25pct"]
        chosen = r[record["selected_review_policy"]]
        ci = chosen["capture_group_bootstrap_95pct"]
        lines.append(f"| {record['label']} | {record['selected_review_policy']} | {chosen['error_capture_fraction']:.1%} | {ci['lower']:.1%}–{ci['upper']:.1%} | {r['random']['error_capture_fraction']:.1%} | {r['candidate_count']['error_capture_fraction']:.1%} | {chosen['reviewed_candidates']} |")
    lines += ["", "Models have different error totals; a larger fraction captured does not establish better extraction. Equal passage budgets also do not imply equal reading effort. Intervals use source-prefix groups and fixed fitted models, excluding training and reviewer variability.", "",
              "## Minority-class results", "",
              "The conservative rule preserved therapeutic true positives on development data only. It is not a guarantee on unseen passages. Precision mode failed that rule and remains explicitly separate.", "",
              "| Mode | Adverse F1 | Therapeutic F1 | Therapeutic recall | Therapeutic TP / gold |",
              "|---|---:|---:|---:|---:|"]
    for record in records.values():
        types = record["metrics"]["per_event_type"]
        therapeutic = types["Potential_therapeutic_event"]
        lines.append(f"| {record['label']} | {types['Adverse_event']['f1']:.1%} | {therapeutic['f1']:.1%} | {therapeutic['recall']:.1%} | {therapeutic['tp']} / {therapeutic['tp']+therapeutic['fn']} |")
    lines += ["", "## Calibration and challenge diagnostics", "",
              "Brier score concerns emitted candidate correctness; it does not measure missed events or patient risk. Lower is better. The constant comparator is fitted on calibration-data prevalence.", "",
              "| Mode | Raw Brier | Calibrated Brier | Constant Brier | Synthetic strict F1 | No-event passages with output |",
              "|---|---:|---:|---:|---:|---:|"]
    for record in records.values():
        r, c = record["reliability"], record["challenge"]
        lines.append(f"| {record['label']} | {r['brier_raw']:.3f} | {r['brier_calibrated']:.3f} | {r['brier_calibration_prevalence_constant']:.3f} | {c['strict_event']['f1']:.1%} | {c['no_event_passages_with_spurious_output']} / {c['no_event_passages']} |")
    lines += ["", "The synthetic test contains only ten self-authored schematic passages. It is a failure probe, not clinical external validation.", "", "## Paired comparisons", ""]
    for first in ("baseline", "biomedbert"):
        for second in ("pharmasentinel_final", "biomedbert_all_ce"):
            comparison = read_json(root / f"reports/experiments/{first}_vs_{second}_test.json")
            ci = comparison["paired_source_group_bootstrap_95pct"]
            lines.append(f"- {labels[second]} versus {labels[first]}: F1 difference {100*comparison['f1_difference_second_minus_first']:+.1f} percentage points; paired 95% interval {100*ci['lower']:+.1f} to {100*ci['upper']:+.1f}.")
    lines += ["", "## What this establishes", "",
              "A reproducible applied NLP study with controlled loss ablations, held-out evaluation, calibration, review simulation and explicit failures. It does not establish clinical safety, regulatory readiness, population incidence or an Optum deployment. No final-test score is used to tune this release.", "",
              "The precision recipe's two development seeds achieved 42.7% and 41.8% strict F1. Seed 42 remained the frozen release checkpoint; two runs only provide a limited stability check.", "",
              "Live MySQL loading remains unverified without a configured server. The schema, parameterized loader and local analytical exports are implemented. See RUNBOOK.md for reproduction and INTERVIEW_GUIDE.md for explanations.", ""]
    write_json(root / "reports/release_summary.json", {"split": "test", "models": records})
    (root / "docs/RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("Generated docs/RESULTS.md and reports/release_summary.json")


if __name__ == "__main__":
    main()
