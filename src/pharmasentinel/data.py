"""Pinned PHEE download, explicit annotation adaptation and grouped splits."""

from __future__ import annotations

import hashlib
import random
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from .io import read_json, read_jsonl, sha256, write_json, write_jsonl

EVENT_TYPES = ("Adverse_event", "Potential_therapeutic_event")
ROLES = ("trigger", "drug", "effect")


def git_blob(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def fetch(root, cache=None):
    root = Path(root)
    config = read_json(root / "configs/dataset.json")
    files = {}
    for split in ("train", "dev", "test"):
        destination = root / "data/raw" / f"{split}.jsonl"
        destination.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://raw.githubusercontent.com/{config['repository']}/{config['revision']}/{config['source_directory']}/{split}.json"
        if destination.exists():
            payload = destination.read_bytes()
        elif cache is not None and (Path(cache) / f"{split}.json").exists():
            payload = (Path(cache) / f"{split}.json").read_bytes()
        else:
            request = urllib.request.Request(
                url, headers={"User-Agent": "PharmaSentinel/0.1"}
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
        if git_blob(payload) != config["git_blobs"][split]:
            raise ValueError(
                f"{split}: content does not match the pinned upstream Git blob"
            )
        destination.write_bytes(payload)
        files[split] = {
            "url": url,
            "sha256": sha256(destination),
            "git_blob": git_blob(payload),
            "records": len(read_jsonl(destination)),
        }
    manifest = {
        "dataset": config["dataset"],
        "revision": config["revision"],
        "files": files,
    }
    write_json(root / "reports/data/source_manifest.json", manifest)
    return manifest


def flatten_role(node, context, row_id, role, issues):
    segments = []
    if not node:
        return segments
    texts, starts = node.get("text", []), node.get("start", [])
    if len(texts) != len(starts):
        raise ValueError(f"{row_id}/{role}: mismatched mention arrays")
    for mention, (parts, offsets) in enumerate(zip(texts, starts)):
        if len(parts) != len(offsets):
            raise ValueError(f"{row_id}/{role}: mismatched segment arrays")
        for part, (text, start) in enumerate(zip(parts, offsets)):
            end = start + len(text)
            if start < 0 or end > len(context) or context[start:end] != text:
                issues.append(
                    {
                        "id": row_id,
                        "role": role,
                        "start": start,
                        "end": end,
                        "reason": "upstream_text_offset_mismatch",
                        "action": "exclude_entire_passage_from_training_and_scoring_with_explicit_count",
                    }
                )
                continue
            segments.append(
                {
                    "start": start,
                    "end": end,
                    "text": text,
                    "mention": mention,
                    "part": part,
                }
            )
    return segments


def adapt(raw, split):
    issues, events = [], []
    annotation_sets = raw["annotations"]
    if len(annotation_sets) != 1:
        raise ValueError(
            f"{raw['id']}: expected one annotation set; define adjudication before adapting"
        )
    for event in annotation_sets[0]["events"]:
        if event["event_type"] not in EVENT_TYPES:
            raise ValueError(f"Unknown event type: {event['event_type']}")
        before = len(issues)
        roles = {
            "trigger": flatten_role(
                event.get("Trigger"), raw["context"], raw["id"], "trigger", issues
            ),
            "drug": flatten_role(
                event.get("Treatment", {}).get("Drug"),
                raw["context"],
                raw["id"],
                "drug",
                issues,
            ),
            "effect": flatten_role(
                event.get("Effect"), raw["context"], raw["id"], "effect", issues
            ),
        }
        if len(issues) > before:
            continue
        events.append(
            {"id": event["event_id"], "event_type": event["event_type"], **roles}
        )
    row = {
        "id": raw["id"],
        "source_group": raw["id"].rsplit("_", 1)[0],
        "original_split": split,
        "split": split,
        "context": raw["context"],
        "events": events,
        "annotation_status": "quarantined" if issues else "valid",
        "quarantined_event_count": len(annotation_sets[0]["events"]) - len(events),
    }
    return row, issues


def normalized_text(text):
    return re.sub(r"\s+", " ", text).strip().casefold()


def prepare(root):
    root = Path(root)
    config = read_json(root / "configs/dataset.json")
    all_rows, issues = [], []
    metadata_mismatches = 0
    for split in ("train", "dev", "test"):
        for raw in read_jsonl(root / "data/raw" / f"{split}.jsonl"):
            row, problems = adapt(raw, split)
            all_rows.append(row)
            issues.extend(problems)
            actual_count = len(raw["annotations"][0]["events"])
            metadata_mismatches += bool(raw.get("is_mult_event")) != (actual_count > 1)
    ids = [row["id"] for row in all_rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate record IDs")
    source_sets = {
        split: {r["source_group"] for r in all_rows if r["original_split"] == split}
        for split in ("train", "dev", "test")
    }
    source_overlaps = {
        f"{a}/{b}": len(source_sets[a] & source_sets[b])
        for a, b in [("train", "dev"), ("train", "test"), ("dev", "test")]
    }
    if any(source_overlaps.values()):
        raise ValueError(f"Source leakage: {source_overlaps}")
    text_splits = defaultdict(set)
    for row in all_rows:
        text_splits[normalized_text(row["context"])].add(row["original_split"])
    duplicate_leakage = sum(len(values) > 1 for values in text_splits.values())
    if duplicate_leakage:
        raise ValueError(
            f"{duplicate_leakage} normalized texts cross original splits; regroup before training"
        )
    groups = sorted(source_sets["dev"])
    random.Random(config["seed"]).shuffle(groups)
    a, b = round(len(groups) * 0.5), round(len(groups) * 0.75)
    assignments = {
        group: subset
        for subset, values in [
            ("model_selection", groups[:a]),
            ("calibration", groups[a:b]),
            ("policy", groups[b:]),
        ]
        for group in values
    }
    for row in all_rows:
        if row["original_split"] == "dev":
            row["split"] = assignments[row["source_group"]]
    for split in ("train", "model_selection", "calibration", "policy", "test"):
        write_jsonl(
            root / "data/processed" / f"{split}.jsonl",
            [row for row in all_rows if row["split"] == split],
        )
    counts = Counter(row["split"] for row in all_rows)
    event_counts = Counter(
        event["event_type"] for row in all_rows for event in row["events"]
    )
    manifest = {
        "schema_version": 1,
        "source_revision": config["revision"],
        "seed": config["seed"],
        "records": dict(counts),
        "source_overlap": source_overlaps,
        "normalized_text_cross_split_duplicates": duplicate_leakage,
        "metadata_flag_disagreements": metadata_mismatches,
        "annotation_issues": issues,
        "quarantined_events": sum(row["quarantined_event_count"] for row in all_rows),
        "event_counts_after_quarantine": dict(event_counts),
        "source_group_status": "ID-prefix proxy; provenance verification and near-duplicate analysis remain limitations",
        "split_ids": {
            s: [r["id"] for r in all_rows if r["split"] == s] for s in counts
        },
        "file_hashes": {
            s: sha256(root / "data/processed" / f"{s}.jsonl") for s in counts
        },
    }
    write_json(root / "reports/data/preparation_manifest.json", manifest)
    return {key: value for key, value in manifest.items() if key != "split_ids"}


def load_split(root, split):
    return read_jsonl(Path(root) / "data/processed" / f"{split}.jsonl")


def audit(root):
    root = Path(root)
    rows = [
        row
        for split in ("train", "model_selection", "calibration", "policy", "test")
        for row in load_split(root, split)
    ]
    summary = {}
    for split in sorted({r["split"] for r in rows}):
        selected = [r for r in rows if r["split"] == split]
        events = [e for r in selected for e in r["events"]]
        lengths = sorted(
            len(re.findall(r"\w+|[^\w\s]", r["context"])) for r in selected
        )
        summary[split] = {
            "passages": len(selected),
            "source_groups": len({r["source_group"] for r in selected}),
            "events": len(events),
            "event_types": dict(Counter(e["event_type"] for e in events)),
            "missing_drug": sum(not e["drug"] for e in events),
            "missing_effect": sum(not e["effect"] for e in events),
            "multi_event_passages": sum(len(r["events"]) > 1 for r in selected),
            "discontinuous_role_bundles": sum(
                any(s.get("part", 0) > 0 for s in e[role])
                for e in events
                for role in ROLES
            ),
            "regex_token_length_p50": lengths[len(lengths) // 2],
            "regex_token_length_p95": lengths[int((len(lengths) - 1) * 0.95)],
            "regex_token_length_max": max(lengths),
        }
    write_json(root / "reports/data/eda_summary.json", summary)
    return summary
