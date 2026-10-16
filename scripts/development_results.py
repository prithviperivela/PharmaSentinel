"""Sequential development analysis, keeping test predictions untouched."""

import argparse
import os
from pathlib import Path
import subprocess
import sys


def run(command, root, log):
    print("Running: " + " ".join(command), flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "pharmasentinel", *command],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    with log.open("a", encoding="utf-8") as handle:
        handle.write(
            "COMMAND: "
            + " ".join(command)
            + "\n"
            + result.stdout
            + "\n"
            + result.stderr
            + "\n"
        )
    if result.returncode:
        print(result.stdout[-4000:] + result.stderr[-4000:])
        raise SystemExit(result.returncode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--names", nargs="+", default=["baseline", "biomedbert"])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    log = root / "reports/development_pipeline.log"
    log.write_text("", encoding="utf-8")
    for name in args.names:
        for command in [
            ["calibrate", "--name", name],
            ["evaluate", "--name", name, "--split", "model_selection"],
            ["evaluate", "--name", name, "--split", "policy"],
            ["review", "--name", name, "--split", "policy"],
            ["challenge", "--name", name],
            ["report", "--name", name, "--split", "policy"],
            ["mysql-export", "--name", name, "--split", "policy"],
        ]:
            run(command, root, log)
    print("Development reports complete. No final test prediction was run.", flush=True)


if __name__ == "__main__":
    main()
