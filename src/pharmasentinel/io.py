"""Small, deterministic file and configuration helpers."""

from __future__ import annotations

import hashlib
import json
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def read_jsonl(path):
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def environment():
    result = {"python": platform.python_version(), "platform": platform.platform()}
    for package in [
        "torch",
        "transformers",
        "numpy",
        "pandas",
        "scikit-learn",
        "plotly",
    ]:
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = None
    return result
