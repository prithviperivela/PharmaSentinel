"""Repeat the selected training recipe; never replace the primary seed by its score."""

from pathlib import Path
import argparse

from pharmasentinel.biomedical import train
from pharmasentinel.data import load_split
from pharmasentinel.evaluation import evaluate
from pharmasentinel.integrity import validate_prediction_identity
from pharmasentinel.io import read_json, read_jsonl, write_json
from pharmasentinel.selection import filter_triggers


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    source = "biomedbert_all_ce"
    config = read_json(root / "artifacts" / source / "config.json")
    config.update(seed=43, prediction_splits=["model_selection"])
    config.pop("trigger_threshold", None)
    path = root / "configs/precision_seed43.json"
    name = "precision_seed43"
    if not args.report_only:
        write_json(path, config)
        train(root, path, name)
    rows = load_split(root, "model_selection")
    results = {}
    for current in (source, name):
        predictions = read_jsonl(
            root / "reports/predictions" / f"{current}_model_selection.jsonl"
        )
        validate_prediction_identity(
            rows, predictions, read_json(root / "artifacts" / current / "metadata.json")
        )
        report, _ = evaluate(
            rows,
            filter_triggers(predictions, 0.0),
            bootstrap=0,
        )
        results[current] = {
            "strict_event": report["strict_event"],
            "per_event_type": report["per_event_type"],
        }
    report = {
        "split": "model_selection",
        "fixed_threshold": 0.0,
        "primary_seed": 42,
        "repeat_seed": 43,
        "results": results,
        "interpretation": "Two seeds describe limited training variability. Seed 42 remains primary regardless of the repeat result. No test or policy labels used.",
    }
    write_json(root / "reports/experiments/seed_stability.json", report)
    print(report, flush=True)


if __name__ == "__main__":
    main()
