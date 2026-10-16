"""Paired source-group bootstrap comparisons of fixed model predictions."""

from collections import defaultdict
from pathlib import Path

import numpy as np

from .data import load_split
from .evaluation import evaluate, prf
from .io import read_jsonl, sha256, write_json
from .io import read_json
from .integrity import validate_prediction_identity


def compare(root, first, second, split="policy", replicates=500, seed=42):
    root = Path(root)
    if split == "test":
        from .protocol import assert_frozen

        for name in (first, second):
            assert_frozen(root, name, split)
    rows = load_split(root, split)
    grouped = defaultdict(lambda: np.zeros((2, 3), dtype=int))
    reports = {}
    for index, name in enumerate((first, second)):
        path = root / "reports/predictions" / f"{name}_{split}.jsonl"
        predictions = read_jsonl(path)
        validate_prediction_identity(
            rows, predictions, read_json(root / "artifacts" / name / "metadata.json")
        )
        report, details = evaluate(rows, predictions, bootstrap=0)
        reports[name] = report["strict_event"]
        for item in details:
            grouped[item["source_group"]][index] += [item["tp"], item["fp"], item["fn"]]
    groups = np.stack(list(grouped.values()))
    rng = np.random.default_rng(seed)
    differences = []
    for _ in range(replicates):
        counts = groups[rng.integers(len(groups), size=len(groups))].sum(axis=0)
        differences.append(prf(*counts[1])["f1"] - prf(*counts[0])["f1"])
    result = {
        "split": split,
        "first": first,
        "second": second,
        "strict_core_event": reports,
        "f1_difference_second_minus_first": reports[second]["f1"]
        - reports[first]["f1"],
        "paired_source_group_bootstrap_95pct": {
            "lower": float(np.quantile(differences, 0.025)),
            "upper": float(np.quantile(differences, 0.975)),
            "replicates": replicates,
            "seed": seed,
        },
        "data_sha256": sha256(root / "data/processed" / f"{split}.jsonl"),
        "limitation": "Source-ID prefix proxy grouping; fixed training runs, not training-seed uncertainty or clinical validation.",
    }
    write_json(
        root / "reports/experiments" / f"{first}_vs_{second}_{split}.json", result
    )
    return result
