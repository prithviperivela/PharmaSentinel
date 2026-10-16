"""Candidate calibration and passage-budget review simulations."""

from __future__ import annotations

import copy
import math

import numpy as np
from sklearn.linear_model import LogisticRegression

from .evaluation import candidate_correctness, evaluate
from .io import write_json


def features(event):
    return [
        float(event.get(k, 0.0))
        for k in ("raw_confidence", "trigger_confidence", "role_confidence")
    ]


def fit_calibrator(gold_rows, predictions, path):
    gold = {
        r["id"]: r for r in gold_rows if r.get("annotation_status") != "quarantined"
    }
    x, y = [], []
    for prediction in predictions:
        if prediction["id"] not in gold:
            continue
        events = prediction["events"]
        x.extend(features(e) for e in events)
        y.extend(candidate_correctness(gold[prediction["id"]]["events"], events))
    if len(x) < 20 or len(set(y)) < 2:
        calibrator = {
            "method": "identity_fallback",
            "reason": "fewer than 20 candidates or only one correctness class",
            "candidates": len(y),
            "positive_candidates": sum(y),
        }
    else:
        estimator = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
        estimator.fit(np.array(x), np.array(y))
        calibrator = {
            "method": "regularized_logistic_correctness",
            "features": ["raw_confidence", "trigger_confidence", "role_confidence"],
            "coefficients": estimator.coef_[0].tolist(),
            "intercept": float(estimator.intercept_[0]),
            "candidates": len(y),
            "positive_candidates": sum(y),
            "fit_split": "calibration",
            "target": "strict reduced-schema candidate correctness; missed events are not candidates",
        }
    calibrator["training_correctness_prevalence"] = float(np.mean(y)) if y else None
    write_json(path, calibrator)
    return calibrator


def apply_calibrator(predictions, calibrator):
    result = copy.deepcopy(predictions)
    for row in result:
        for event in row["events"]:
            if calibrator["method"] == "identity_fallback":
                probability = float(event.get("raw_confidence", 0))
            else:
                logit = (
                    np.dot(features(event), calibrator["coefficients"])
                    + calibrator["intercept"]
                )
                probability = float(1 / (1 + np.exp(-np.clip(logit, -50, 50))))
            event["calibrated_confidence"] = probability
    return result


def reliability_summary(gold_rows, predictions, bins=5, constant_probability=None):
    gold = {
        r["id"]: r for r in gold_rows if r.get("annotation_status") != "quarantined"
    }
    labels, raw, calibrated = [], [], []
    for row in predictions:
        if row["id"] not in gold:
            continue
        labels.extend(candidate_correctness(gold[row["id"]]["events"], row["events"]))
        raw.extend(float(e.get("raw_confidence", 0)) for e in row["events"])
        calibrated.extend(
            float(e.get("calibrated_confidence", e.get("raw_confidence", 0)))
            for e in row["events"]
        )
    if not labels:
        return {
            "candidates": 0,
            "brier_raw": None,
            "brier_calibrated": None,
            "bins": [],
        }
    y = np.array(labels)
    records = []
    for name, values in [("raw", raw), ("calibrated", calibrated)]:
        values = np.array(values)
        indices = np.minimum((values * bins).astype(int), bins - 1)
        for i in range(bins):
            mask = indices == i
            records.append(
                {
                    "score": name,
                    "lower": i / bins,
                    "upper": (i + 1) / bins,
                    "count": int(mask.sum()),
                    "mean_confidence": float(values[mask].mean())
                    if mask.any()
                    else None,
                    "observed_correctness": float(y[mask].mean())
                    if mask.any()
                    else None,
                }
            )
    constant_brier = (
        float(np.mean((constant_probability - y) ** 2))
        if constant_probability is not None
        else None
    )
    calibrated_brier = float(np.mean((np.array(calibrated) - y) ** 2))
    return {
        "candidates": len(labels),
        "correct_candidates": int(y.sum()),
        "brier_raw": float(np.mean((np.array(raw) - y) ** 2)),
        "brier_calibrated": calibrated_brier,
        "brier_calibration_prevalence_constant": constant_brier,
        "brier_skill_vs_calibration_constant": 1 - calibrated_brier / constant_brier
        if constant_brier
        else None,
        "bins": records,
        "limitation": "Candidate calibration excludes missed events; review evaluation includes all gold events.",
    }


def priority(row, method):
    if method == "candidate_count":
        return (0, len(row.get("events", [])))
    if method == "passage_length":
        return (0, row.get("source_characters", 0))
    if method == "expected_incorrect_candidates":
        # An additive candidate-error surrogate suits a passage-level review
        # budget better than its single weakest event. The no-output fallback
        # is explicitly a heuristic, not a probability of a missed event.
        return (
            0,
            sum(
                1 - e.get("calibrated_confidence", e.get("raw_confidence", 0.0))
                for e in row["events"]
            )
            if row.get("status", "ok") == "ok" and row["events"]
            else 1.0,
        )
    if row.get("status", "ok") != "ok" or not row["events"]:
        return (1, 1.0) if method == "calibrated_checks" else (0, 1.0)
    score_key = "raw_confidence" if method == "raw" else "calibrated_confidence"
    uncertainty = 1 - min(
        e.get(score_key, e.get("raw_confidence", 0.0)) for e in row["events"]
    )
    structural = any(not e.get("drug") or not e.get("effect") for e in row["events"])
    return (int(structural) if method == "calibrated_checks" else 0, float(uncertainty))


def review_experiment(gold_rows, predictions, budgets=(0.1, 0.25, 0.5), seed=42):
    _, details = evaluate(gold_rows, predictions, bootstrap=0)
    prediction_map = {r["id"]: r for r in predictions}
    passage_lengths = {row["id"]: len(row["context"]) for row in gold_rows}
    prediction_map = {
        identifier: {
            **prediction_map.get(identifier, {"events": [], "status": "missing"}),
            "source_characters": length,
        }
        for identifier, length in passage_lengths.items()
    }
    total_errors = sum(d["errors"] for d in details)
    total_missed = sum(d["fn"] for d in details)
    total_problem_passages = sum(d["errors"] > 0 for d in details)
    count = len(details)
    rng, results = np.random.default_rng(seed), []
    grouped = {}
    for index, detail in enumerate(details):
        grouped.setdefault(detail["source_group"], []).append(index)
    groups = list(grouped.values())
    interval_rng = np.random.default_rng(seed)
    # Resample whole source groups; budgets and rankings are recomputed per sample.
    bootstrap_samples = (
        [
            [
                i
                for group in interval_rng.integers(len(groups), size=len(groups))
                for i in groups[group]
            ]
            for _ in range(300)
        ]
        if groups
        else []
    )

    def order_for(indices, method):
        return sorted(
            indices,
            key=lambda i: (
                *priority(
                    prediction_map.get(
                        details[i]["id"], {"events": [], "status": "missing"}
                    ),
                    method,
                ),
                details[i]["id"],
            ),
            reverse=True,
        )

    def measure(order, n):
        chosen = [details[i] for i in order[:n]]
        errors = sum(d["errors"] for d in chosen)
        missed = sum(d["fn"] for d in chosen)
        return {
            "captured_errors": errors,
            "error_capture_fraction": errors / total_errors if total_errors else 0.0,
            "remaining_errors": total_errors - errors,
            "missed_events_exposed": missed,
            "remaining_missed_events": total_missed - missed,
            "problem_passages_found": sum(d["errors"] > 0 for d in chosen),
            "false_predictions_exposed": sum(d["fp"] for d in chosen),
            "complete_trigger_misses_exposed": sum(
                d["gold_triggers_with_no_predicted_overlap"] for d in chosen
            ),
            "reviewed_candidates": sum(d["predicted_events"] for d in chosen),
            "reviewed_characters": sum(passage_lengths[d["id"]] for d in chosen),
        }

    for budget in budgets:
        n = min(count, math.ceil(count * budget))
        if not count:
            continue
        random_records = [measure(rng.permutation(count), n) for _ in range(100)]
        results.append(
            {
                "policy": "random",
                "budget": budget,
                "reviewed_passages": n,
                **{
                    key: float(np.mean([r[key] for r in random_records]))
                    for key in random_records[0]
                },
                "random_repetitions": 100,
            }
        )
        for method in (
            "raw",
            "calibrated",
            "calibrated_checks",
            "expected_incorrect_candidates",
            "candidate_count",
            "passage_length",
        ):
            order = order_for(range(count), method)
            interval_values = []
            for sample in bootstrap_samples:
                denominator = sum(details[i]["errors"] for i in sample)
                if denominator:
                    chosen = order_for(sample, method)[
                        : math.ceil(len(sample) * budget)
                    ]
                    interval_values.append(
                        sum(details[i]["errors"] for i in chosen) / denominator
                    )
            measured = measure(order, n)
            results.append(
                {
                    "policy": method,
                    "budget": budget,
                    "reviewed_passages": n,
                    **measured,
                    "lift_over_random_expectation": measured["error_capture_fraction"]
                    / (n / count),
                    "capture_group_bootstrap_95pct": {
                        "lower": float(np.quantile(interval_values, 0.025)),
                        "upper": float(np.quantile(interval_values, 0.975)),
                        "replicates": len(interval_values),
                    }
                    if interval_values
                    else None,
                }
            )
    return {
        "simulation": "oracle-review: reviewing a passage exposes every unmatched predicted/gold event in that passage; no measured time savings",
        "error_unit": "unmatched prediction (FP) plus unmatched gold event (FN); a wrong candidate may contribute both",
        "passages": count,
        "total_errors": total_errors,
        "total_missed_events": total_missed,
        "problem_passages": total_problem_passages,
        "tie_break": "descending passage ID after priority",
        "structural_check_policy": "flags prioritize within the same fixed budget; no automatic approval or mandatory budget overrun",
        "expected_candidate_policy": "sum(1 - calibrated candidate correctness); no-output/failure fallback=1; does not probabilistically estimate missed events",
        "workload_caveat": "Equal passage counts are not equal time or effort. Candidate counts and source-character workload are reported separately; neither is a measured time cost.",
        "seed": seed,
        "interval_scope": "Source-prefix group resampling with reranking and budget recomputation; fixed model/calibrator, no training or human-review uncertainty.",
        "diagnostic_baselines": "candidate_count and passage_length are diagnostic comparisons, excluded from the predeclared four-policy selection",
        "results": results,
    }
