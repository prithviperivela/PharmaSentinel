import copy

import pytest

from pharmasentinel.inference import attach_provenance
from pharmasentinel.inference import load_predictor
from pharmasentinel.io import write_json
from pharmasentinel.integrity import require_new_run, validate_prediction_identity


def stamped(example):
    metadata = {"run_name": "experiment_v1", "weights_sha256": "known-weight-hash"}
    return attach_provenance([example], [example], metadata), metadata


def test_wrong_model_predictions_are_rejected(example):
    predictions, metadata = stamped(example)
    predictions[0]["model_sha256"] = "different-model"
    with pytest.raises(ValueError, match="model hash"):
        validate_prediction_identity([example], predictions, metadata)


def test_changed_source_text_is_rejected(example):
    predictions, metadata = stamped(example)
    changed = copy.deepcopy(example)
    changed["context"] += " Extra text."
    with pytest.raises(ValueError, match="source-text hash"):
        validate_prediction_identity([changed], predictions, metadata)


def test_valid_identity_and_missing_prediction_count(example):
    predictions, metadata = stamped(example)
    assert (
        validate_prediction_identity([example], predictions, metadata)[
            "validated_predictions"
        ]
        == 1
    )
    assert (
        validate_prediction_identity([example], [], metadata)[
            "missing_prediction_passages"
        ]
        == 1
    )


def test_existing_run_cannot_be_overwritten(tmp_path):
    (tmp_path / "artifacts" / "experiment_v1").mkdir(parents=True)
    with pytest.raises(FileExistsError, match="already exists"):
        require_new_run(tmp_path, "experiment_v1")


def test_run_name_cannot_escape_artifact_directory(tmp_path):
    with pytest.raises(ValueError, match="run name"):
        require_new_run(tmp_path, "../another-project")


def test_changed_checkpoint_is_rejected_before_loading(tmp_path):
    (tmp_path / "model.pt").write_bytes(b"changed checkpoint")
    write_json(
        tmp_path / "metadata.json",
        {"model_type": "bilstm", "weights_sha256": "different-hash"},
    )
    with pytest.raises(ValueError, match="Checkpoint contents"):
        load_predictor(tmp_path)


def test_prediction_config_identity_is_enforced(example):
    metadata = {
        "run_name": "selected",
        "weights_sha256": "weights",
        "config_sha256": "threshold-config",
    }
    predictions = attach_provenance([example], [example], metadata)
    validate_prediction_identity([example], predictions, metadata)
    predictions[0]["config_sha256"] = "other-threshold"
    with pytest.raises(ValueError, match="configuration hash"):
        validate_prediction_identity([example], predictions, metadata)


def test_cached_encoder_is_verified_without_network(tmp_path, monkeypatch):
    from pharmasentinel.encoder_source import download_encoder
    from pharmasentinel.io import sha256
    from urllib import request

    directory = tmp_path / "data/cache/biomedbert"
    directory.mkdir(parents=True)
    files = {}
    for name in ("config.json", "vocab.txt", "pytorch_model.bin"):
        path = directory / name
        path.write_bytes(b"fixture")
        files[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    write_json(
        tmp_path / "reports/data/encoder_manifest.json",
        {"repository": "fixture", "revision": "pinned", "files": files},
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Network accessed despite a verified local encoder")

    monkeypatch.setattr(request, "urlopen", forbidden)
    assert download_encoder(tmp_path, "fixture", "pinned") == (directory, False)
    (directory / "vocab.txt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity check failed"):
        download_encoder(tmp_path, "fixture", "pinned")
