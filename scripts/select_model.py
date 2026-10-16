"""Compare fixed development ablations; optionally materialize a selected artifact."""

import argparse
import shutil
from pathlib import Path

from pharmasentinel.data import load_split
from pharmasentinel.evaluation import evaluate
from pharmasentinel.inference import attach_provenance
from pharmasentinel.integrity import require_new_run, validate_prediction_identity
from pharmasentinel.io import read_json, read_jsonl, sha256, write_json, write_jsonl
from pharmasentinel.selection import filter_triggers, threshold_sweep


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--names", nargs="+", default=["biomedbert"])
    parser.add_argument("--output-name")
    parser.add_argument("--report", default="v2_selection")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    rows = load_split(root, "model_selection")
    original = read_jsonl(root / "reports/predictions/biomedbert_model_selection.jsonl")
    validate_prediction_identity(
        rows, original, read_json(root / "artifacts/biomedbert/metadata.json")
    )
    reference, _ = evaluate(rows, original, bootstrap=0)
    results = {}
    for name in args.names:
        predictions = read_jsonl(
            root / "reports/predictions" / f"{name}_model_selection.jsonl"
        )
        validate_prediction_identity(
            rows, predictions, read_json(root / "artifacts" / name / "metadata.json")
        )
        results[name] = threshold_sweep(rows, predictions, reference)
    eligible = [
        (name, result["selected"])
        for name, result in results.items()
        if result["selected"]
    ]
    if not eligible:
        raise ValueError("No candidate meets the predeclared recall/class safeguard")
    name, selected = max(
        eligible,
        key=lambda pair: (
            pair[1]["strict_event"]["f1"],
            pair[1]["strict_event"]["recall"],
            -pair[1]["threshold"],
        ),
    )
    report = {
        "reference": reference["strict_event"],
        "experiments": results,
        "selected_source": name,
        "selected_threshold": selected["threshold"],
        "selected_metrics": selected["strict_event"],
        "data_sha256": sha256(root / "data/processed/model_selection.jsonl"),
        "test_used": False,
        "policy_used": False,
    }
    write_json(root / "reports/experiments" / f"{args.report}.json", report)
    if args.output_name:
        target = require_new_run(root, args.output_name)
        source = root / "artifacts" / name
        target.mkdir(parents=True)
        for filename in ("model.pt", "encoder_config", "tokenizer"):
            path = source / filename
            if path.is_dir():
                shutil.copytree(path, target / filename)
            else:
                shutil.copy2(path, target / filename)
        config = read_json(source / "config.json")
        config["trigger_threshold"] = selected["threshold"]
        write_json(target / "config.json", config)
        metadata = read_json(source / "metadata.json")
        metadata.update(
            run_name=args.output_name,
            parent_run=name,
            config_sha256=sha256(target / "config.json"),
            selection_report=f"reports/experiments/{args.report}.json",
            selected_trigger_threshold=selected["threshold"],
            selected_model_selection_metrics=selected["strict_event"],
        )
        write_json(target / "metadata.json", metadata)
        cached = read_jsonl(
            root / "reports/predictions" / f"{name}_model_selection.jsonl"
        )
        write_jsonl(
            root / "reports/predictions" / f"{args.output_name}_model_selection.jsonl",
            attach_provenance(
                filter_triggers(cached, selected["threshold"]), rows, metadata
            ),
        )
    print(
        {key: value for key, value in report.items() if key != "experiments"},
        flush=True,
    )


if __name__ == "__main__":
    main()
