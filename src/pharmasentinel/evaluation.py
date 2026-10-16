"""Declared reduced-schema evaluation: one-to-one matching and missed events."""

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
from scipy.optimize import linear_sum_assignment

from .data import EVENT_TYPES, ROLES


def span_key(segments):
    return tuple(sorted((int(s["start"]), int(s["end"])) for s in segments))


def event_key(event):
    return (event["event_type"], *(span_key(event.get(role, [])) for role in ROLES))


def validate_event(event, context):
    if event["event_type"] not in EVENT_TYPES:
        raise ValueError("Unknown predicted event type")
    for role in ROLES:
        for segment in event.get(role, []):
            start, end = segment["start"], segment["end"]
            if (
                not isinstance(start, int)
                or not isinstance(end, int)
                or start < 0
                or end <= start
                or end > len(context)
            ):
                raise ValueError(f"Invalid {role} evidence bounds")
            if segment.get("text") != context[start:end]:
                raise ValueError(f"Invalid {role} evidence text")
    if not event.get("trigger"):
        raise ValueError("A predicted event must have trigger evidence")


def prf(tp=0, fp=0, fn=0):
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
    }


def overlap(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    # Character sets preserve gaps in discontinuous evidence.
    ca = {i for s in a for i in range(s["start"], s["end"])}
    cb = {i for s in b for i in range(s["start"], s["end"])}
    return len(ca & cb) / len(ca | cb) if ca | cb else 0.0


def relaxed_matches(gold, predicted, threshold=0.5):
    if not gold or not predicted:
        return 0
    valid = np.array(
        [
            [
                g["event_type"] == p["event_type"]
                and all(overlap(g.get(r, []), p.get(r, [])) >= threshold for r in ROLES)
                for p in predicted
            ]
            for g in gold
        ],
        dtype=int,
    )
    # Maximize valid match count, rather than greedily taking an overlapping pair.
    gi, pi = linear_sum_assignment(-valid)
    return int(valid[gi, pi].sum())


def candidate_correctness(gold_events, predicted_events):
    remaining = Counter(event_key(e) for e in gold_events)
    labels = []
    for event in predicted_events:
        key = event_key(event)
        correct = remaining[key] > 0
        labels.append(int(correct))
        if correct:
            remaining[key] -= 1
    return labels


def evaluate(gold_rows, predictions, bootstrap=200, seed=42):
    by_id = {row["id"]: row for row in predictions}
    if len(by_id) != len(predictions):
        raise ValueError("Duplicate prediction passage IDs")
    if len({r["id"] for r in gold_rows}) != len(gold_rows):
        raise ValueError("Duplicate gold passage IDs")
    unexpected = set(by_id) - {row["id"] for row in gold_rows}
    if unexpected:
        raise ValueError(f"Predictions contain {len(unexpected)} unexpected IDs")
    counts = Counter()
    components = {role: Counter() for role in ROLES}
    classes = {label: Counter() for label in EVENT_TYPES}
    confusion = defaultdict(Counter)
    details, excluded = [], []
    error_categories = Counter()
    for row in gold_rows:
        if row.get("annotation_status") == "quarantined":
            excluded.append(row["id"])
            continue
        prediction = by_id.get(
            row["id"], {"events": [], "status": "missing_prediction"}
        )
        predicted, gold = prediction.get("events", []), row["events"]
        for event in predicted:
            validate_event(event, row["context"])
        gc, pc = Counter(map(event_key, gold)), Counter(map(event_key, predicted))
        tp = sum((gc & pc).values())
        fp, fn = len(predicted) - tp, len(gold) - tp
        correct_labels = candidate_correctness(gold, predicted)
        for event, correct in zip(predicted, correct_labels):
            if correct:
                continue
            same_trigger = [
                g for g in gold if span_key(g["trigger"]) == span_key(event["trigger"])
            ]
            if not same_trigger:
                category = "spurious_or_wrong_boundary_trigger"
            elif all(g["event_type"] != event["event_type"] for g in same_trigger):
                category = "wrong_event_type_at_correct_trigger"
            else:
                comparable = [
                    g for g in same_trigger if g["event_type"] == event["event_type"]
                ]
                drug_ok = any(
                    span_key(g["drug"]) == span_key(event["drug"]) for g in comparable
                )
                effect_ok = any(
                    span_key(g["effect"]) == span_key(event["effect"])
                    for g in comparable
                )
                category = (
                    "wrong_drug_and_effect"
                    if not drug_ok and not effect_ok
                    else "wrong_drug"
                    if not drug_ok
                    else "wrong_effect"
                    if not effect_ok
                    else "duplicate_or_event_grouping"
                )
            error_categories[category] += 1
        relaxed_tp = relaxed_matches(gold, predicted)
        counts.update(
            tp=tp,
            fp=fp,
            fn=fn,
            relaxed_tp=relaxed_tp,
            relaxed_fp=len(predicted) - relaxed_tp,
            relaxed_fn=len(gold) - relaxed_tp,
        )
        for role in ROLES:

            def keys(events):
                return Counter(
                    (
                        e["event_type"] if role == "trigger" else role,
                        s["start"],
                        s["end"],
                    )
                    for e in events
                    for s in e.get(role, [])
                )

            g, p = keys(gold), keys(predicted)
            matched = sum((g & p).values())
            components[role].update(
                tp=matched, fp=sum(p.values()) - matched, fn=sum(g.values()) - matched
            )
        for label in EVENT_TYPES:
            g, p = (
                Counter(event_key(e) for e in gold if e["event_type"] == label),
                Counter(event_key(e) for e in predicted if e["event_type"] == label),
            )
            matched = sum((g & p).values())
            classes[label].update(
                tp=matched, fp=sum(p.values()) - matched, fn=sum(g.values()) - matched
            )
        # Classification confusion is conditional on exact trigger span matching;
        # missed/spurious triggers are explicit extra categories.
        available = list(range(len(predicted)))
        for event in gold:
            matches = [
                i
                for i in available
                if span_key(predicted[i]["trigger"]) == span_key(event["trigger"])
            ]
            if matches:
                i = matches[0]
                available.remove(i)
                confusion[event["event_type"]][predicted[i]["event_type"]] += 1
            else:
                confusion[event["event_type"]]["missed_trigger"] += 1
        for i in available:
            confusion["spurious_trigger"][predicted[i]["event_type"]] += 1
        detection_misses = sum(
            not any(overlap(g["trigger"], p["trigger"]) > 0 for p in predicted)
            for g in gold
        )
        details.append(
            {
                "id": row["id"],
                "source_group": row["source_group"],
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "errors": fp + fn,
                "gold_events": len(gold),
                "predicted_events": len(predicted),
                "gold_triggers_with_no_predicted_overlap": detection_misses,
                "candidate_correct": correct_labels,
                "multi_event": len(gold) > 1,
                "multi_drug": any(
                    len({s.get("mention", i) for i, s in enumerate(e["drug"])}) > 1
                    for e in gold
                ),
                "discontinuous": any(
                    s.get("part", 0) > 0
                    for e in gold
                    for role in ROLES
                    for s in e[role]
                ),
                "status": prediction.get("status", "ok"),
            }
        )
    strict = prf(counts["tp"], counts["fp"], counts["fn"])
    report = {
        "metric_definition": "Reduced core event: exact event type + trigger/drug/effect span sets; one-to-one multiset matching. Empty gold roles are valid. Not full PHEE schema.",
        "input_passages": len(gold_rows),
        "evaluated_passages": len(details),
        "excluded_quarantined_ids": excluded,
        "strict_event": strict,
        "relaxed_event_iou_0.5": prf(
            counts["relaxed_tp"], counts["relaxed_fp"], counts["relaxed_fn"]
        ),
        "evidence_segments": {role: prf(**value) for role, value in components.items()},
        "per_event_type": {label: prf(**value) for label, value in classes.items()},
        "trigger_type_confusion": {a: dict(b) for a, b in confusion.items()},
        "missing_or_failed_outputs": sum(d["status"] != "ok" for d in details),
        "subgroups": {},
    }
    report["unmatched_prediction_error_categories"] = dict(error_categories)
    report["gold_triggers_with_no_predicted_overlap"] = sum(
        d["gold_triggers_with_no_predicted_overlap"] for d in details
    )
    report["miss_definition"] = (
        "Strict FN includes wrong fields/boundaries. Gold triggers with no predicted overlap separately measures more complete detection misses."
    )
    for group in ("multi_event", "multi_drug", "discontinuous"):
        for value in (False, True):
            subset = [d for d in details if d[group] == value]
            c = {key: sum(d[key] for d in subset) for key in ("tp", "fp", "fn")}
            report["subgroups"][f"{group}={value}"] = {
                "passages": len(subset),
                **prf(**c),
            }
    if bootstrap and details:
        grouped = defaultdict(lambda: np.zeros(3, dtype=int))
        for d in details:
            grouped[d["source_group"]] += [d["tp"], d["fp"], d["fn"]]
        values = np.stack(list(grouped.values()))
        rng, scores = np.random.default_rng(seed), []
        for _ in range(bootstrap):
            sample = values[rng.integers(len(values), size=len(values))].sum(axis=0)
            scores.append(prf(*sample)["f1"])
        report["strict_f1_group_bootstrap_95pct"] = {
            "lower": float(np.quantile(scores, 0.025)),
            "upper": float(np.quantile(scores, 0.975)),
            "replicates": bootstrap,
            "seed": seed,
            "grouping": "source-ID prefix proxy",
        }
    return report, details
