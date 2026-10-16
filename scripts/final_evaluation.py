"""Run the hash-checked final protocol; do not use results to retune choices."""

import argparse
from pathlib import Path

from development_results import run
from pharmasentinel.io import read_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--names", nargs="+", default=["baseline", "biomedbert"])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not (root / "reports/frozen_protocol.json").exists():
        raise SystemExit("Freeze the protocol before final evaluation.")
    log = root / "reports/final_evaluation.log"
    log.write_text("", encoding="utf-8")
    for name in args.names:
        config = read_json(root / "artifacts" / name / "config.json")
        device = config.get("device", "cpu")
        for command in [
            [
                "predict",
                "--name",
                name,
                "--split",
                "test",
                "--final-test",
                "--device",
                device,
            ],
            ["evaluate", "--name", name, "--split", "test", "--final-test"],
            ["review", "--name", name, "--split", "test", "--final-test"],
            ["challenge", "--name", name, "--split", "challenge_test", "--final-test"],
            ["report", "--name", name, "--split", "test"],
        ]:
            run(command, root, log)
    print(
        "Frozen final reports complete. Keep results distinct from subsequent development.",
        flush=True,
    )


if __name__ == "__main__":
    main()
