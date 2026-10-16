"""Check checkpoint reload and absence of gold-label dependence before test access."""

import copy
import argparse
from pathlib import Path

import numpy as np

from pharmasentinel.data import load_split
from pharmasentinel.evaluation import event_key
from pharmasentinel.inference import load_predictor
from pharmasentinel.io import read_json, read_jsonl, write_json


root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--names", nargs="+", default=["baseline", "biomedbert"])
parser.add_argument("--report", default="model_preflight")
args = parser.parse_args()
results = {}
for name in args.names:
    config = read_json(root / "artifacts" / name / "config.json")
    rows = load_split(root, "policy")[:8]
    saved = {
        r["id"]: r
        for r in read_jsonl(root / "reports/predictions" / f"{name}_policy.jsonl")
    }
    predictor = load_predictor(root / "artifacts" / name, config.get("device", "cpu"))
    predicted = predictor.predict(rows)
    unlabeled = copy.deepcopy(rows)
    for row in unlabeled:
        row["events"] = []
    without_gold = predictor.predict(unlabeled)
    for a, b in zip(predicted, without_gold):
        assert a["events"] == b["events"], "Inference depends on gold annotations"
    for row in predicted:
        reference = saved[row["id"]]
        assert list(map(event_key, row["events"])) == list(
            map(event_key, reference["events"])
        ), "Reloaded artifact changed event predictions"
        assert np.allclose(
            [e["raw_confidence"] for e in row["events"]],
            [e["raw_confidence"] for e in reference["events"]],
            atol=1e-5,
        )
    results[name] = {
        "passages_checked": len(rows),
        "checkpoint_reload_matches": True,
        "gold_independent_inference": True,
    }
    del predictor
write_json(root / "reports/verification" / f"{args.report}.json", results)
print(results)
