"""Reproducible CLI; expensive imports remain local to each command."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .data import audit, fetch, load_split, prepare
from .io import read_json, read_jsonl, sha256, write_json, write_jsonl


def main():
    parser = argparse.ArgumentParser(description="PharmaSentinel data science pipeline")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("fetch")
    p.add_argument("--cache", type=Path)
    sub.add_parser("prepare")
    sub.add_parser("audit")
    sub.add_parser("leakage-screen")
    p = sub.add_parser("train")
    p.add_argument("--model", choices=["baseline", "biomedbert"], default="baseline")
    p.add_argument("--name")
    p.add_argument("--config", type=Path)
    p.add_argument("--limit", type=int)
    p = sub.add_parser("predict")
    p.add_argument("--name", default="baseline")
    p.add_argument("--split", default="policy")
    p.add_argument("--input", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--final-test", action="store_true")
    p = sub.add_parser("evaluate")
    p.add_argument("--name", default="baseline")
    p.add_argument("--split", default="policy")
    p.add_argument("--predictions", type=Path)
    p.add_argument("--final-test", action="store_true")
    p = sub.add_parser("calibrate")
    p.add_argument("--name", default="baseline")
    p = sub.add_parser("review")
    p.add_argument("--name", default="baseline")
    p.add_argument("--split", default="policy")
    p.add_argument("--final-test", action="store_true")
    p = sub.add_parser("report")
    p.add_argument("--name", default="baseline")
    p.add_argument("--split", default="policy")
    p = sub.add_parser("freeze")
    p.add_argument("--names", nargs="+", required=True)
    p.add_argument(
        "--replace",
        action="store_true",
        help="Archive an existing protocol; previously inspected test data is not unseen again",
    )
    p = sub.add_parser("challenge")
    p.add_argument("--name", default="baseline")
    p.add_argument(
        "--split", choices=["challenge_dev", "challenge_test"], default="challenge_dev"
    )
    p.add_argument("--final-test", action="store_true")
    p = sub.add_parser("mysql-export")
    p.add_argument("--name", default="baseline")
    p.add_argument("--split", default="policy")
    p = sub.add_parser("mysql-load")
    p.add_argument("--name", default="baseline")
    p.add_argument("--split", default="policy")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "fetch":
        result = fetch(root, args.cache)
    elif args.command == "prepare":
        result = prepare(root)
        result.pop("split_ids", None)
    elif args.command == "audit":
        result = audit(root)
    elif args.command == "leakage-screen":
        from .leakage import screen

        result = screen(root)
    elif args.command == "train":
        args.name = args.name or args.model
        if args.model == "baseline":
            from .baseline import train
        else:
            from .biomedical import train
        result = train(root, args.config, args.name, args.limit)
    elif args.command == "freeze":
        prepared_hashes = read_json(root / "reports/data/preparation_manifest.json")[
            "file_hashes"
        ]
        for split, expected in prepared_hashes.items():
            if sha256(root / "data/processed" / f"{split}.jsonl") != expected:
                parser.error(
                    f"Prepared {split} data changed; investigate before freezing"
                )
        previous = root / "reports/frozen_protocol.json"
        if previous.exists():
            if not args.replace:
                parser.error(
                    "A frozen protocol already exists. Reproduction or a deliberate revision requires --replace; prior test access must remain disclosed."
                )
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            history = root / "reports/protocol_history" / f"frozen_{stamp}.json"
            write_json(history, read_json(previous))
        result = {
            "scope": "Frozen model, calibrator and review-policy procedure before test evaluation",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "prior_test_results_exist": bool(
                list((root / "reports/experiments").glob("*_test_metrics.json"))
            ),
            "models": {},
            "data_hashes": read_json(root / "reports/data/preparation_manifest.json")[
                "file_hashes"
            ],
            "code_hashes": {
                file.name: sha256(file)
                for file in (root / "src/pharmasentinel").glob("*.py")
                if file.name not in ("reporting.py", "analytics.py")
            },
            "challenge_hashes": {
                file.name: sha256(file)
                for file in (root / "data/challenge").glob("*.jsonl")
            },
        }
        for name in args.names:
            directory = root / "artifacts" / name
            metadata = read_json(directory / "metadata.json")
            if metadata["data_hashes"] != prepared_hashes:
                parser.error(
                    f"Training data identities do not match prepared data for {name}"
                )
            if sha256(directory / "model.pt") != metadata["weights_sha256"]:
                parser.error(f"Checkpoint identity mismatch for {name}")
            if (
                "config_sha256" in metadata
                and sha256(directory / "config.json") != metadata["config_sha256"]
            ):
                parser.error(f"Inference config identity mismatch for {name}")
            for required in (
                "model.pt",
                "config.json",
                "calibrator.json",
                "review_policy.json",
            ):
                if not (directory / required).exists():
                    parser.error(
                        f"Complete model, calibration and policy selection before freezing: missing {name}/{required}"
                    )
            result["models"][name] = {
                file.relative_to(directory).as_posix(): sha256(file)
                for file in directory.rglob("*")
                if file.is_file()
            }
        write_json(root / "reports/frozen_protocol.json", result)
    elif args.command in ("predict", "evaluate", "review"):
        if args.split == "test":
            if not args.final_test:
                parser.error(
                    "Use --final-test only after freezing model and review choices; test is not a tuning set"
                )
            from .protocol import assert_frozen

            assert_frozen(root, args.name, args.split)
        predictions_path = (
            root / "reports/predictions" / f"{args.name}_{args.split}.jsonl"
        )
        if args.command == "predict":
            from .inference import load_predictor, attach_provenance

            rows = (
                read_jsonl(args.input) if args.input else load_split(root, args.split)
            )
            metadata = read_json(root / "artifacts" / args.name / "metadata.json")
            predictions = attach_provenance(
                load_predictor(root / "artifacts" / args.name, args.device).predict(
                    rows
                ),
                rows,
                metadata,
            )
            write_jsonl(args.output or predictions_path, predictions)
            result = {
                "predicted_passages": len(predictions),
                "output": str(args.output or predictions_path),
            }
        elif args.command == "evaluate":
            from .evaluation import evaluate
            from .integrity import validate_prediction_identity

            rows = load_split(root, args.split)
            path = args.predictions or predictions_path
            predictions = read_jsonl(path)
            identity = validate_prediction_identity(
                rows,
                predictions,
                read_json(root / "artifacts" / args.name / "metadata.json"),
            )
            result, details = evaluate(rows, predictions)
            result["prediction_identity_validation"] = identity
            result.update(
                split=args.split,
                run_name=args.name,
                predictions_sha256=sha256(path),
                data_sha256=sha256(root / "data/processed" / f"{args.split}.jsonl"),
                final_test=args.split == "test",
                evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
            )
            write_json(
                root / "reports/experiments" / f"{args.name}_{args.split}_metrics.json",
                result,
            )
            write_jsonl(
                root
                / "reports/predictions"
                / f"{args.name}_{args.split}_details.jsonl",
                details,
            )
        else:
            from .integrity import validate_prediction_identity
            from .reliability import (
                apply_calibrator,
                reliability_summary,
                review_experiment,
            )

            rows = load_split(root, args.split)
            validate_prediction_identity(
                rows,
                read_jsonl(predictions_path),
                read_json(root / "artifacts" / args.name / "metadata.json"),
            )
            predictions = apply_calibrator(
                read_jsonl(predictions_path),
                read_json(root / "artifacts" / args.name / "calibrator.json"),
            )
            result = {
                "split": args.split,
                "run_name": args.name,
                "reliability": reliability_summary(
                    rows,
                    predictions,
                    constant_probability=read_json(
                        root / "artifacts" / args.name / "calibrator.json"
                    ).get("training_correctness_prevalence"),
                ),
                "review": review_experiment(rows, predictions),
            }
            if args.split == "policy":
                candidates = [
                    r
                    for r in result["review"]["results"]
                    if r["budget"] == 0.25
                    and r["policy"]
                    in (
                        "raw",
                        "calibrated",
                        "calibrated_checks",
                        "expected_incorrect_candidates",
                    )
                ]
                chosen = max(candidates, key=lambda r: r["error_capture_fraction"])
                write_json(
                    root / "artifacts" / args.name / "review_policy.json",
                    {
                        "selected_policy": chosen["policy"],
                        "selection_split": "policy",
                        "selection_budget": 0.25,
                        "selection_metric": "error_capture_fraction",
                        "tie_break": "first policy in declared raw/calibrated/calibrated_checks/expected_incorrect order",
                        "development_capture": chosen["error_capture_fraction"],
                        "not_a_clinical_severity_score": True,
                    },
                )
            else:
                result["frozen_selected_policy"] = read_json(
                    root / "artifacts" / args.name / "review_policy.json"
                )["selected_policy"]
            write_json(
                root / "reports/experiments" / f"{args.name}_{args.split}_review.json",
                result,
            )
            write_jsonl(
                root
                / "reports/predictions"
                / f"{args.name}_{args.split}_calibrated.jsonl",
                predictions,
            )
    elif args.command == "calibrate":
        from .reliability import fit_calibrator
        from .integrity import validate_prediction_identity

        rows = load_split(root, "calibration")
        predictions = read_jsonl(
            root / "reports/predictions" / f"{args.name}_calibration.jsonl"
        )
        validate_prediction_identity(
            rows,
            predictions,
            read_json(root / "artifacts" / args.name / "metadata.json"),
        )

        result = fit_calibrator(
            rows,
            predictions,
            root / "artifacts" / args.name / "calibrator.json",
        )
    elif args.command == "report":
        from .reporting import build_report

        result = build_report(root, args.name, args.split)
    elif args.command == "challenge":
        from .challenge import run

        if args.split == "challenge_test" and (
            not args.final_test or not (root / "reports/frozen_protocol.json").exists()
        ):
            parser.error(
                "Freeze choices and use --final-test before the final synthetic challenge"
            )
        if args.split == "challenge_test":
            from .protocol import assert_frozen

            assert_frozen(root, args.name, args.split)
        result = run(root, args.name, args.split)
    elif args.command == "mysql-export":
        from .analytics import export_mysql

        result = export_mysql(root, args.name, args.split)
    elif args.command == "mysql-load":
        from .analytics import load_mysql

        result = load_mysql(root, args.name, args.split)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
