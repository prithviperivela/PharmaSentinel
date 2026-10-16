"""Small experiment-integrity guards, separate from statistical scoring."""

import hashlib
import math
import re
from pathlib import Path

from .evaluation import validate_event


def require_new_run(root, name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", name):
        raise ValueError(
            "Use a run name containing letters, numbers, underscores or hyphens"
        )
    directory = Path(root) / "artifacts" / name
    if directory.exists():
        raise FileExistsError(
            f"Run '{name}' already exists. Preserve it and choose a new name, such as '{name}_v2'."
        )
    return directory


def validate_prediction_identity(rows, predictions, metadata):
    gold = {row["id"]: row for row in rows}
    if len(gold) != len(rows):
        raise ValueError("Duplicate reference passage IDs")
    seen = set()
    for prediction in predictions:
        identifier = prediction["id"]
        if identifier in seen:
            raise ValueError("Duplicate prediction passage IDs")
        seen.add(identifier)
        if identifier not in gold:
            raise ValueError(f"Unexpected prediction passage ID: {identifier}")
        if prediction.get("run_name") != metadata["run_name"]:
            raise ValueError("Prediction run name does not match the selected artifact")
        if prediction.get("model_sha256") != metadata["weights_sha256"]:
            raise ValueError(
                "Prediction model hash does not match the selected artifact"
            )
        text = gold[identifier]["context"]
        if (
            "config_sha256" in metadata
            and prediction.get("config_sha256") != metadata["config_sha256"]
        ):
            raise ValueError(
                "Prediction configuration hash does not match the selected artifact"
            )
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if prediction.get("passage_sha256") != expected:
            raise ValueError(
                "Prediction source-text hash does not match the reference passage"
            )
        if prediction.get("schema_version") != 1:
            raise ValueError("Unsupported prediction schema version")
        for event in prediction.get("events", []):
            validate_event(event, text)
            for field in ("raw_confidence", "trigger_confidence", "role_confidence"):
                value = event.get(field)
                if (
                    not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or not 0 <= value <= 1
                ):
                    raise ValueError(f"Invalid candidate score: {field}")
    return {
        "validated_predictions": len(seen),
        "missing_prediction_passages": len(gold) - len(seen),
    }
