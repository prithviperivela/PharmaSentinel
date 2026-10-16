"""Self-authored synthetic language checks; not clinical/expert validation."""

from pathlib import Path

from .evaluation import evaluate
from .inference import load_predictor, attach_provenance
from .integrity import validate_prediction_identity
from .io import read_json, read_jsonl, write_json, write_jsonl


def run(root, name, split="challenge_dev"):
    root = Path(root)
    rows = read_jsonl(root / "data/challenge" / f"{split}.jsonl")
    metadata = read_json(root / "artifacts" / name / "metadata.json")
    predictions = attach_provenance(
        load_predictor(root / "artifacts" / name).predict(rows), rows, metadata
    )
    validate_prediction_identity(rows, predictions, metadata)
    report, details = evaluate(rows, predictions, bootstrap=0)
    report.update(
        dataset=split,
        annotation="Self-authored synthetic text, a deliberately small diagnostic suite. Not clinical or external validation.",
        run_name=name,
    )
    report["no_event_passages"] = sum(not r["events"] for r in rows)
    by_id = {r["id"]: r for r in predictions}
    report["no_event_passages_with_spurious_output"] = sum(
        bool(by_id[r["id"]]["events"]) for r in rows if not r["events"]
    )
    write_json(root / "reports/experiments" / f"{name}_{split}_metrics.json", report)
    write_jsonl(root / "reports/predictions" / f"{name}_{split}.jsonl", predictions)
    write_jsonl(root / "reports/predictions" / f"{name}_{split}_details.jsonl", details)
    return report
