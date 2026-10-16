"""Development-only threshold selection with explicit recall/class safeguards."""

from copy import deepcopy
import math

from .evaluation import evaluate

THRESHOLDS = (0.0, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95)


def filter_triggers(predictions, threshold):
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Trigger threshold must be finite and in [0, 1]")
    result = deepcopy(predictions)
    for row in result:
        row["events"] = [
            e for e in row["events"] if e["trigger_confidence"] >= threshold
        ]
        row["flags"] = [f for f in row.get("flags", []) if f != "no_event_extracted"]
        if not row["events"] and row.get("status", "ok") == "ok":
            row["flags"].append("no_event_extracted")
    return result


def threshold_sweep(rows, predictions, reference):
    results = []
    minority = "Potential_therapeutic_event"
    for threshold in THRESHOLDS:
        filtered = filter_triggers(predictions, threshold)
        report, _ = evaluate(rows, filtered, bootstrap=0)
        eligible = (
            report["strict_event"]["recall"]
            >= 0.9 * reference["strict_event"]["recall"]
            and report["per_event_type"][minority]["tp"]
            >= reference["per_event_type"][minority]["tp"]
        )
        results.append(
            {
                "threshold": threshold,
                "eligible": eligible,
                "strict_event": report["strict_event"],
                "per_event_type": report["per_event_type"],
                "no_output_passages": sum(not p["events"] for p in filtered),
            }
        )
    eligible = [r for r in results if r["eligible"]]
    selected = (
        max(
            eligible,
            key=lambda r: (
                r["strict_event"]["f1"],
                r["strict_event"]["recall"],
                -r["threshold"],
            ),
        )
        if eligible
        else None
    )
    return {
        "selection_split": "model_selection",
        "candidates": results,
        "selected": selected,
    }
