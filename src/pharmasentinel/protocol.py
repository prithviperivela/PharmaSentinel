"""Check immutable experiment identities before accessing final evaluation data."""

from pathlib import Path

from .io import read_json, sha256


def assert_frozen(root, name, split):
    root = Path(root)
    protocol = read_json(root / "reports/frozen_protocol.json")
    if name not in protocol["models"]:
        raise ValueError("Model is absent from the frozen protocol")
    current_code = {
        p.name
        for p in (root / "src/pharmasentinel").glob("*.py")
        if p.name not in ("reporting.py", "analytics.py")
    }
    if current_code != set(protocol["code_hashes"]):
        raise ValueError("Frozen protocol code file set changed")
    for file, expected in protocol["models"][name].items():
        if sha256(root / "artifacts" / name / file) != expected:
            raise ValueError(f"Frozen artifact changed: {file}")
    for file, expected in protocol["code_hashes"].items():
        if sha256(root / "src/pharmasentinel" / file) != expected:
            raise ValueError(f"Frozen protocol code changed: {file}")
    for subset, expected in protocol["data_hashes"].items():
        if sha256(root / "data/processed" / f"{subset}.jsonl") != expected:
            raise ValueError(f"Frozen data changed: {subset}")
    if split == "test":
        if (
            sha256(root / "data/processed/test.jsonl")
            != protocol["data_hashes"]["test"]
        ):
            raise ValueError("Frozen test data changed")
    elif split == "challenge_test":
        if (
            sha256(root / "data/challenge/challenge_test.jsonl")
            != protocol["challenge_hashes"]["challenge_test.jsonl"]
        ):
            raise ValueError("Frozen challenge data changed")
    return protocol
