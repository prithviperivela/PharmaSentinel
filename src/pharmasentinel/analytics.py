"""Batch analytical exports and an optional parameterized MySQL loader."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pandas as pd

from .data import load_split
from .evaluation import candidate_correctness
from .integrity import validate_prediction_identity
from .io import read_json, read_jsonl, write_json


def tables(root, name, split):
    root = Path(root)
    if split == "test":
        from .protocol import assert_frozen

        assert_frozen(root, name, split)
    rows = load_split(root, split)
    predictions_path = root / "reports/predictions" / f"{name}_{split}_calibrated.jsonl"
    if not predictions_path.exists():
        predictions_path = root / "reports/predictions" / f"{name}_{split}.jsonl"
    metadata = read_json(root / "artifacts" / name / "metadata.json")
    prediction_rows = read_jsonl(predictions_path)
    validate_prediction_identity(rows, prediction_rows, metadata)
    predictions = {r["id"]: r for r in prediction_rows}
    run_id = f"{name}_{split}_{metadata['weights_sha256'][:12]}"
    gold_run = "phee2_annotations_v1"
    passages = pd.DataFrame(
        [
            {
                "passage_id": r["id"],
                "source_group": r["source_group"],
                "split_name": r["split"],
                "original_text": r["context"],
                "annotation_status": r.get("annotation_status", "valid"),
                "character_count": len(r["context"]),
            }
            for r in rows
        ]
    )
    metrics_path = root / "reports/experiments" / f"{name}_{split}_metrics.json"
    metrics = read_json(metrics_path) if metrics_path.exists() else {}
    runs = pd.DataFrame(
        [
            {
                "run_id": gold_run,
                "model_type": "gold_annotation",
                "configuration_json": json.dumps(
                    {
                        "source_revision": read_json(root / "configs/dataset.json")[
                            "revision"
                        ]
                    }
                ),
                "metrics_json": "{}",
            },
            {
                "run_id": run_id,
                "model_type": metadata["model_type"],
                "configuration_json": json.dumps(
                    read_json(root / "artifacts" / name / "config.json")
                ),
                "metrics_json": json.dumps(metrics),
            },
        ]
    )
    events = []
    for row in rows:
        if row.get("annotation_status") == "quarantined":
            continue
        prediction = predictions.get(row["id"], {"events": []})
        correct = candidate_correctness(row["events"], prediction["events"])
        for kind, source, rid in [
            ("gold", row["events"], gold_run),
            ("predicted", prediction["events"], run_id),
        ]:
            for i, event in enumerate(source):
                events.append(
                    {
                        "passage_id": row["id"],
                        "record_kind": kind,
                        "run_id": rid,
                        "event_index": i,
                        "event_type": event["event_type"],
                        "drug_text": " | ".join(s["text"] for s in event["drug"]),
                        "effect_text": " | ".join(s["text"] for s in event["effect"]),
                        "evidence_json": json.dumps(
                            {
                                role: event[role]
                                for role in ("trigger", "drug", "effect")
                            },
                            ensure_ascii=False,
                        ),
                        "raw_confidence": event.get("raw_confidence"),
                        "calibrated_confidence": event.get("calibrated_confidence"),
                        "is_correct": correct[i] if kind == "predicted" else None,
                    }
                )
    columns = [
        "passage_id",
        "record_kind",
        "run_id",
        "event_index",
        "event_type",
        "drug_text",
        "effect_text",
        "evidence_json",
        "raw_confidence",
        "calibrated_confidence",
        "is_correct",
    ]
    return {
        "passages": passages,
        "experiment_runs": runs,
        "event_records": pd.DataFrame(events, columns=columns),
    }


def export_mysql(root, name, split):
    root = Path(root)
    directory = root / "reports/review_exports" / f"{name}_{split}"
    directory.mkdir(parents=True, exist_ok=True)
    frames = tables(root, name, split)
    for table, frame in frames.items():
        frame.to_csv(directory / f"{table}.csv", index=False)
    result = {
        "export_directory": str(directory),
        "rows": {table: len(frame) for table, frame in frames.items()},
        "database_loaded": False,
        "note": "Local CSV exports may include source passages; ignored by Git. Use mysql-load with a dedicated configured local database to import.",
    }
    write_json(directory / "manifest.json", result)
    return result


def load_mysql(root, name, split):
    import mysql.connector

    database = os.environ.get("PHARMASENTINEL_MYSQL_DATABASE", "pharmasentinel")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database):
        raise ValueError("Invalid dedicated database identifier")
    user = os.environ.get("PHARMASENTINEL_MYSQL_USER")
    if not user:
        raise ValueError(
            "Configure PHARMASENTINEL_MYSQL_USER and local credentials first; the file-based pipeline does not need a server"
        )
    connection = mysql.connector.connect(
        host=os.environ.get("PHARMASENTINEL_MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("PHARMASENTINEL_MYSQL_PORT", "3306")),
        user=user,
        password=os.environ.get("PHARMASENTINEL_MYSQL_PASSWORD", ""),
        connection_timeout=5,
    )
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4"
        )
        cursor.execute(f"USE `{database}`")
        schema = "\n".join(
            line
            for line in (Path(root) / "sql/schema.sql")
            .read_text(encoding="utf-8")
            .splitlines()
            if not line.lstrip().startswith("--")
        )
        for statement in schema.split(";"):
            if statement.strip():
                cursor.execute(statement)
        frames = tables(root, name, split)
        for table in ("passages", "experiment_runs", "event_records"):
            frame = frames[table]
            if frame.empty:
                continue
            columns = list(frame.columns)
            sql = (
                f"INSERT INTO `{table}` ({','.join('`' + c + '`' for c in columns)}) VALUES ({','.join(['%s'] * len(columns))}) ON DUPLICATE KEY UPDATE "
                + ",".join(f"`{c}`=VALUES(`{c}`)" for c in columns)
            )
            values = [
                tuple(None if pd.isna(value) else value for value in record)
                for record in frame.itertuples(index=False, name=None)
            ]
            cursor.executemany(sql, values)
        connection.commit()
        return {
            "database": database,
            "loaded_rows": {table: len(frame) for table, frame in frames.items()},
            "database_loaded": True,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
