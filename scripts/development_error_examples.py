"""Save reproducible development-only error examples locally, never in public Git."""

import argparse
from collections import Counter
from pathlib import Path

from pharmasentinel.data import load_split
from pharmasentinel.evaluation import candidate_correctness, overlap, span_key
from pharmasentinel.integrity import validate_prediction_identity
from pharmasentinel.io import read_json, read_jsonl, write_json, write_jsonl


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="pharmasentinel_final")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    rows = load_split(root, "model_selection")
    predictions = read_jsonl(
        root / "reports/predictions" / f"{args.name}_model_selection.jsonl"
    )
    validate_prediction_identity(
        rows, predictions, read_json(root / "artifacts" / args.name / "metadata.json")
    )
    gold = {row["id"]: row for row in rows}
    counts, examples, sampled = Counter(), [], Counter()
    for row in sorted(predictions, key=lambda row: row["id"]):
        source = gold[row["id"]]
        for event, correct in zip(
            row["events"], candidate_correctness(source["events"], row["events"])
        ):
            if correct:
                continue
            exact = [
                e
                for e in source["events"]
                if span_key(e["trigger"]) == span_key(event["trigger"])
            ]
            category = (
                "exact_trigger_wrong_fields"
                if exact
                else "trigger_boundary"
                if any(
                    overlap(e["trigger"], event["trigger"]) > 0
                    for e in source["events"]
                )
                else "no_gold_trigger_overlap"
            )
            counts[category] += 1
            if sampled[category] < 3:
                sampled[category] += 1
                examples.append(
                    {
                        "id": row["id"],
                        "category": category,
                        "context": source["context"],
                        "predicted_event": event,
                        "gold_events": source["events"],
                    }
                )
    write_jsonl(
        root / "reports/predictions" / f"{args.name}_error_examples.jsonl", examples
    )
    write_json(
        root / "reports/experiments" / f"{args.name}_error_audit.json",
        {
            "split": "model_selection",
            "category_counts": dict(counts),
            "local_example_count": len(examples),
            "sampling": "First three by passage ID per category; descriptive examples, not prevalence estimates",
            "interpretation": "Benchmark-relative errors. Annotation absence does not prove medical falsehood. Original passages remain local.",
        },
    )
    print(dict(counts))


if __name__ == "__main__":
    main()
