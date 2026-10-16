"""Offset-aware BIO conversion; exact gold boundaries remain in evaluation."""

from __future__ import annotations

import re

import numpy as np

from .data import EVENT_TYPES

TRIGGER_LABELS = [
    "O",
    "B-Adverse_event",
    "I-Adverse_event",
    "B-Potential_therapeutic_event",
    "I-Potential_therapeutic_event",
]
ROLE_LABELS = ["O", "B", "I"]


def tokenize(text):
    matches = list(re.finditer(r"\w+|[^\w\s]", text, flags=re.UNICODE))
    return [m.group().casefold() for m in matches], [
        (m.start(), m.end()) for m in matches
    ]


def bio_labels(offsets, segments, begin=1, inside=2):
    labels = np.zeros(len(offsets), dtype=np.int64)
    collisions, unaligned = 0, 0
    for segment in sorted(segments, key=lambda s: (s["start"], s["end"])):
        hits = [
            i
            for i, (a, b) in enumerate(offsets)
            if b > a and a < segment["end"] and b > segment["start"]
        ]
        if not hits:
            unaligned += 1
            continue
        if (
            offsets[hits[0]][0] != segment["start"]
            or offsets[hits[-1]][1] != segment["end"]
        ):
            unaligned += 1
        if any(labels[i] for i in hits):
            collisions += 1
            continue
        for j, i in enumerate(hits):
            labels[i] = begin if j == 0 else inside
    # Special/padding positions are ignored by all losses.
    for i, (a, b) in enumerate(offsets):
        if b <= a:
            labels[i] = -100
    return labels, {"collisions": collisions, "unaligned_gold_segments": unaligned}


def trigger_labels(offsets, events):
    labels = np.zeros(len(offsets), dtype=np.int64)
    issues = {"collisions": 0, "unaligned_gold_segments": 0}
    for event in events:
        begin = 1 + 2 * EVENT_TYPES.index(event["event_type"])
        local, problem = bio_labels(offsets, event["trigger"], begin, begin + 1)
        for key in issues:
            issues[key] += problem[key]
        for i, value in enumerate(local):
            if value > 0:
                if labels[i] and labels[i] != value:
                    issues["collisions"] += 1
                else:
                    labels[i] = value
            elif value == -100:
                labels[i] = -100
    for i, (a, b) in enumerate(offsets):
        if b <= a:
            labels[i] = -100
    return labels, issues


def decode_bio(labels, probabilities, offsets, context, trigger=False):
    result, current, scores = [], None, []

    def close():
        nonlocal current, scores
        if current is not None:
            start, end, kind = current
            result.append(
                {
                    "span": {
                        "start": int(start),
                        "end": int(end),
                        "text": context[start:end],
                    },
                    "confidence": float(np.mean(scores)),
                    "event_type": EVENT_TYPES[kind] if trigger else None,
                }
            )
        current, scores = None, []

    for i, value in enumerate(labels):
        start, end = offsets[i]
        if value <= 0 or end <= start:
            close()
            continue
        kind = (int(value) - 1) // 2 if trigger else 0
        begin = int(value) % 2 == 1 if trigger else int(value) == 1
        if current is None or begin or current[2] != kind:
            close()
            current = [start, end, kind]
        else:
            current[1] = end
        scores.append(float(probabilities[i, int(value)]))
    close()
    return result


def event_from_parts(trigger, drug, effect):
    role_confidence = min(
        [
            min((x["confidence"] for x in values), default=0.0)
            for values in (drug, effect)
        ]
    )
    return {
        "event_type": trigger["event_type"],
        "trigger": [trigger["span"]],
        "drug": [s["span"] for s in drug],
        "effect": [s["span"] for s in effect],
        "trigger_confidence": trigger["confidence"],
        "role_confidence": role_confidence,
        "raw_confidence": min(trigger["confidence"], role_confidence),
        "flags": [
            f"missing_{role}"
            for role, values in [("drug", drug), ("effect", effect)]
            if not values
        ],
    }


def nearest_trigger_events(triggers, drug, effect):
    attachments = [{"drug": [], "effect": []} for _ in triggers]
    for role, spans in [("drug", drug), ("effect", effect)]:
        for value in spans:
            if triggers:
                center = (value["span"]["start"] + value["span"]["end"]) / 2
                index = min(
                    range(len(triggers)),
                    key=lambda i: abs(
                        center
                        - (triggers[i]["span"]["start"] + triggers[i]["span"]["end"])
                        / 2
                    ),
                )
                attachments[index][role].append(value)
    return [
        event_from_parts(t, attachment["drug"], attachment["effect"])
        for t, attachment in zip(triggers, attachments)
    ]
