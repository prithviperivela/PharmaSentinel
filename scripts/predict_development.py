"""Generate calibration/policy predictions with one model load per run."""

import argparse
from pathlib import Path

from pharmasentinel.data import load_split
from pharmasentinel.inference import attach_provenance, load_predictor
from pharmasentinel.io import read_json, write_jsonl


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--names", nargs="+", required=True)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    for name in args.names:
        metadata = read_json(root / "artifacts" / name / "metadata.json")
        predictor = load_predictor(root / "artifacts" / name, args.device)
        for split in ("calibration", "policy"):
            rows = load_split(root, split)
            predictions = attach_provenance(predictor.predict(rows), rows, metadata)
            write_jsonl(root / "reports/predictions" / f"{name}_{split}.jsonl", predictions)
            print({"run": name, "split": split, "passages": len(predictions)}, flush=True)
        del predictor


if __name__ == "__main__":
    main()
