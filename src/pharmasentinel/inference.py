"""Load a declared artifact type, never infer from gold labels."""

from pathlib import Path
import hashlib

from .io import read_json, sha256


def attach_provenance(predictions, rows, metadata):
    texts = {row["id"]: row["context"] for row in rows}
    return [
        {
            **prediction,
            "run_name": metadata["run_name"],
            "model_sha256": metadata["weights_sha256"],
            **(
                {"config_sha256": metadata["config_sha256"]}
                if "config_sha256" in metadata
                else {}
            ),
            "schema_version": 1,
            "passage_sha256": hashlib.sha256(
                texts[prediction["id"]].encode("utf-8")
            ).hexdigest(),
        }
        for prediction in predictions
    ]


def load_predictor(directory, device="cpu"):
    directory = Path(directory)
    metadata = read_json(directory / "metadata.json")
    if sha256(directory / "model.pt") != metadata["weights_sha256"]:
        raise ValueError("Checkpoint contents do not match the recorded model hash")
    if (
        "config_sha256" in metadata
        and sha256(directory / "config.json") != metadata["config_sha256"]
    ):
        raise ValueError("Inference configuration does not match the recorded hash")
    kind = metadata["model_type"]
    if kind == "bilstm":
        from .baseline import BaselinePredictor

        return BaselinePredictor.load(directory, device)
    if kind == "biomedbert":
        from .biomedical import BiomedicalPredictor

        return BiomedicalPredictor.load(directory, device)
    raise ValueError(f"Unknown artifact model_type: {kind}")
