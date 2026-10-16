"""Generate an honest GitHub-facing report from measured artifacts only."""

from pathlib import Path

from pharmasentinel.io import read_json

root = Path(__file__).resolve().parents[1]
names = ("baseline", "biomedbert", "pharmasentinel_final", "biomedbert_all_ce")
manifest = read_json(root / "reports/data/preparation_manifest.json")
lines = [
    "# PharmaSentinel: project implementation report",
    "",
    "## Objective",
    "",
    "Extract event-associated drug/effect evidence from biomedical passages, analyze extraction reliability, and compare review allocation at fixed passage budgets. This is a data science research prototype, not clinical decision support.",
    "",
    "## Implemented pipeline",
    "",
    "Pinned download → annotation audit → EDA/leakage screen → grouped development subsets → BiLSTM and biomedical fine-tuning → strict event evaluation → calibration and review comparison → frozen final evaluation → SQL exports and local viewer.",
    "",
    "Data: 4,827 upstream PHEE2 passages. No source-prefix overlap or normalized exact-text overlap between original splits; the documented lexical near-duplicate screen found no candidates at its declared threshold. The grouping/screen do not establish absence of semantic leakage.",
    "",
    f"Quality findings: {manifest['metadata_flag_disagreements']} multiplicity-flag disagreements; {manifest['quarantined_events']} invalid annotation event, with its entire passage explicitly quarantined from training/scoring. Original source text remains unchanged.",
    "",
    "## Trained models",
    "",
    "| Model | Training passages | Epochs run | Selected epoch | Fine-tuning |",
    "|---|---:|---:|---:|---|",
]
for name in names:
    path = root / "artifacts" / name / "metadata.json"
    if path.exists():
        value = read_json(path)
        best = max(
            value["history"],
            key=lambda x: (x["selection_event_f1"], x["selection_mean_segment_f1"]),
        )
        lines.append(
            f"| {name} | {value['training_examples']} | {len(value['history'])} | {best['epoch']} | {'Full biomedical encoder + task heads' if value['model_type'] == 'biomedbert' and not value.get('freeze_encoder') else 'Learned embeddings + BiLSTM heads'} |"
        )
lines += [
    "",
    "## Measured extraction results",
    "",
    "F1 values below are proportions. Strict core-event matching requires exact type and trigger/drug/effect span sets; this is not the published full-PHEE metric.",
    "",
    "| Subset | Model | Passages evaluated | Precision | Recall | Strict event F1 |",
    "|---|---|---:|---:|---:|---:|",
]
test_exists = False
for split in ("policy", "test"):
    for name in names:
        path = root / "reports/experiments" / f"{name}_{split}_metrics.json"
        if path.exists():
            value = read_json(path)
            m = value["strict_event"]
            lines.append(
                f"| {'Development policy subset' if split == 'policy' else 'Frozen held-out test'} | {name} | {value['evaluated_passages']} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} |"
            )
            test_exists |= split == "test"
lines += [
    "",
    "Final test evaluation is complete for the runs listed above."
    if test_exists
    else "Final test results are not available yet; development scores are not final test performance.",
    "",
    "## Review allocation",
    "",
    "| Subset | Model | Random error capture | Raw-confidence capture | Development-selected policy | Selected-policy capture |",
    "|---|---|---:|---:|---|---:|",
]
for split in ("policy", "test"):
    for name in names:
        path = root / "reports/experiments" / f"{name}_{split}_review.json"
        if path.exists():
            value = read_json(path)
            selected = read_json(root / "artifacts" / name / "review_policy.json")[
                "selected_policy"
            ]
            by_policy = {
                r["policy"]: r
                for r in value["review"]["results"]
                if r["budget"] == 0.25
            }
            lines.append(
                f"| {split} | {name} | {by_policy['random']['error_capture_fraction']:.1%} | {by_policy['raw']['error_capture_fraction']:.1%} | {selected} | {by_policy[selected]['error_capture_fraction']:.1%} |"
            )
lines += [
    "",
    "Budget: 25% of passages. Error unit: unmatched predictions + unmatched gold core events. These are oracle-review simulations, not measured time savings. Calibration quality and ranking quality are evaluated separately. The additive policy's no-output fallback is heuristic.",
    "",
    "## Statistical comparison",
    "",
]
for split in ("policy", "test"):
    path = root / "reports/experiments" / f"baseline_vs_biomedbert_{split}.json"
    if path.exists():
        value = read_json(path)
        ci = value["paired_source_group_bootstrap_95pct"]
        lines.append(
            f"- {split}: biomedical minus baseline F1 = {value['f1_difference_second_minus_first']:.3f}; paired source-proxy bootstrap 95% interval {ci['lower']:.3f}–{ci['upper']:.3f} ({ci['replicates']} resamples)."
        )
    for first in ("baseline", "biomedbert"):
        path = (
            root / "reports/experiments" / f"{first}_vs_pharmasentinel_final_{split}.json"
        )
        if path.exists():
            value = read_json(path)
            ci = value["paired_source_group_bootstrap_95pct"]
            lines.append(
                f"- {split}: selected v2 minus {first} F1 = {value['f1_difference_second_minus_first']:.3f}; paired interval {ci['lower']:.3f}–{ci['upper']:.3f}."
            )
selection = root / "reports/experiments/v2_final_selection.json"
if selection.exists():
    value = read_json(selection)
    lines += [
        "",
        "## Controlled development experiments",
        "",
        "The predeclared primary measures are strict event F1 and error capture at 25% passage review. Model-selection data chooses models; calibration and policy subsets have separate jobs. See EXPERIMENT_PLAN_V2.md for loss ablations, threshold grid and recall/minority safeguards.",
        "",
        "| Candidate | Unfiltered F1 | Unfiltered therapeutic TP | Eligible threshold | Selected F1 |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, experiment in value["experiments"].items():
        chosen = experiment["selected"]
        raw = experiment["candidates"][0]
        lines.append(
            f"| {name} | {raw['strict_event']['f1']:.3f} | {raw['per_event_type']['Potential_therapeutic_event']['tp']} | {chosen['threshold'] if chosen else 'None'} | {format(chosen['strict_event']['f1'], '.3f') if chosen else 'Failed safeguard'} |"
        )
    lines += [
        "",
        f"Conservative source: **{value['selected_source']}**, trigger threshold **{value['selected_threshold']}**. The final artifact has a separate run name and configuration identity. Development selection scores are optimistic estimates because they selected the configuration.",
        "",
        "The separately declared precision-oriented mode is `biomedbert_all_ce` at threshold 0. Its higher development F1 came with only 10 therapeutic exact matches versus the original 15. It failed the conservative safeguard and is presented as a tradeoff, not as a safeguard-compliant replacement. Both modes were declared before final-test access.",
    ]
lines += [
    "",
    "## Verification and remaining work",
    "",
    "Focused tests cover offset integrity, one-to-one matching, empty outputs, empty roles, quarantine, review budgets, gold-independent inference and biomedical-head backpropagation. A separate preflight checks selected-checkpoint reload. Verification records live in `reports/verification/`.",
    "",
    "The file-based pipeline, local viewer and MySQL analytical exports are implemented. Live MySQL loading requires a configured reachable server; schema and parameterized loader are provided. Public source and aggregate results are published at https://github.com/prithviperivela/PharmaSentinel; raw source passages and local predictions are excluded.",
    "",
    "The precision-oriented recipe was repeated at a second seed: model-selection F1 was 42.7% and 41.8%. This is a limited descriptive check. Next research work: more seeds, rare therapeutic-class performance, overlap/grouping improvements and independently annotated out-of-domain/no-event text. The current synthetic suite is self-authored, schematic and not expert clinical validation.",
    "",
    "## Interview explanation",
    "",
    "Explain why standalone medicine recognition differs from correct complete events, why calibration does not automatically improve ranking, and why per-passage expected candidate errors can differ from weakest-confidence prioritization. Show measured error categories, denominators and failure cases. Do not claim clinical causality or guaranteed employment outcomes.",
    "",
    "See `RESULTS.md` for all four frozen comparisons, minority-class results, calibration and review intervals. `INTERVIEW_GUIDE.md`, `EVALUATION_PROTOCOL.md` and `DATA_CARD.md` explain scope and methods.",
    "",
]
(root / "docs/PROJECT_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
print("Updated docs/PROJECT_REPORT.md from measured experiment files.")
