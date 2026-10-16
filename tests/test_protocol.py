import pytest

from pharmasentinel.io import sha256, write_json
from pharmasentinel.protocol import assert_frozen


def test_freeze_guards_metadata_training_data_and_added_code(tmp_path):
    paths = [
        "artifacts/run/metadata.json",
        "src/pharmasentinel/model.py",
        "data/processed/train.jsonl",
        "data/processed/test.jsonl",
    ]
    for relative in paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    write_json(
        tmp_path / "reports/frozen_protocol.json",
        {
            "models": {"run": {"metadata.json": sha256(tmp_path / paths[0])}},
            "code_hashes": {"model.py": sha256(tmp_path / paths[1])},
            "data_hashes": {
                split: sha256(tmp_path / f"data/processed/{split}.jsonl")
                for split in ("train", "test")
            },
        },
    )
    assert_frozen(tmp_path, "run", "test")
    (tmp_path / paths[2]).write_text("changed")
    with pytest.raises(ValueError, match="Frozen data changed: train"):
        assert_frozen(tmp_path, "run", "test")
    (tmp_path / paths[2]).write_text("fixture")
    (tmp_path / "src/pharmasentinel/new_model.py").write_text("extra")
    with pytest.raises(ValueError, match="code file set changed"):
        assert_frozen(tmp_path, "run", "test")
