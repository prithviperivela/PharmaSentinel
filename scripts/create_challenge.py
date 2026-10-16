"""Generate original fictional examples; run once, keep files versioned."""

from pathlib import Path

from pharmasentinel.io import write_jsonl


def make_row(index, text, annotations, category, split):
    def span(phrase, occurrence=0):
        start = -1
        for _ in range(occurrence + 1):
            start = text.index(phrase, start + 1)
        return {
            "start": start,
            "end": start + len(phrase),
            "text": phrase,
            "mention": 0,
            "part": 0,
        }

    events = []
    for kind, trigger, drug, effects in annotations:
        events.append(
            {
                "event_type": kind,
                "trigger": [span(trigger)],
                "drug": [span(drug)] if drug else [],
                "effect": [
                    {**span(effect), "part": i} for i, effect in enumerate(effects)
                ],
            }
        )
    return {
        "id": f"synthetic_{split}_{index}",
        "source_group": f"synthetic_{split}_{index}",
        "context": text,
        "events": events,
        "annotation_status": "valid",
        "category": category,
        "split": split,
        "provenance": "original fictional language example; not a medical claim",
    }


A, T = "Adverse_event", "Potential_therapeutic_event"
development = [
    ("Drug A caused a rash.", [(A, "caused", "Drug A", ["rash"])], "simple_adverse"),
    ("Drug B improved the rash.", [(T, "improved", "Drug B", ["rash"])], "therapeutic"),
    ("The hospital library received new journals.", [], "unrelated_no_event"),
    ("Drug A was discussed at the meeting.", [], "medicine_without_effect"),
    ("Drug A did not cause a rash.", [], "negated_relation"),
    (
        "Drug A may cause nausea.",
        [(A, "cause", "Drug A", ["nausea"])],
        "speculative_relation",
    ),
    (
        "Drug A caused nausea. Drug B improved a rash.",
        [(A, "caused", "Drug A", ["nausea"]), (T, "improved", "Drug B", ["rash"])],
        "multiple_events",
    ),
    (
        "Drug A caused a rash and, later, swelling.",
        [(A, "caused", "Drug A", ["rash", "swelling"])],
        "discontinuous_effect",
    ),
    ("A rash was noted before Drug A was prescribed.", [], "temporal_counterexample"),
    (
        "Drug A caused an unspecified reaction.",
        [(A, "caused", "Drug A", ["unspecified reaction"])],
        "vague_effect",
    ),
]
heldout = [
    (
        "Medication X triggered dizziness.",
        [(A, "triggered", "Medication X", ["dizziness"])],
        "simple_adverse",
    ),
    (
        "Medication Y relieved the cough.",
        [(T, "relieved", "Medication Y", ["cough"])],
        "therapeutic",
    ),
    ("The laboratory updated its scheduling software.", [], "unrelated_no_event"),
    ("Medication X appears in the bibliography.", [], "medicine_without_effect"),
    ("Medication X did not induce swelling.", [], "negated_relation"),
    (
        "Medication X might induce a headache.",
        [(A, "induce", "Medication X", ["headache"])],
        "speculative_relation",
    ),
    (
        "Medication X induced a headache. Medication Y relieved nausea.",
        [
            (A, "induced", "Medication X", ["headache"]),
            (T, "relieved", "Medication Y", ["nausea"]),
        ],
        "multiple_events",
    ),
    (
        "Medication X triggered nausea and, several hours later, dizziness.",
        [(A, "triggered", "Medication X", ["nausea", "dizziness"])],
        "discontinuous_effect",
    ),
    (
        "The cough started before Medication Y was administered.",
        [],
        "temporal_counterexample",
    ),
    (
        "An unnamed treatment induced a rash.",
        [(A, "induced", None, ["rash"])],
        "missing_named_drug",
    ),
]
root = Path(__file__).resolve().parents[1]
for split, examples in [("challenge_dev", development), ("challenge_test", heldout)]:
    write_jsonl(
        root / "data/challenge" / f"{split}.jsonl",
        [make_row(i, *example, split) for i, example in enumerate(examples)],
    )
print("Wrote 10 diagnostic development and 10 frozen-evaluation synthetic examples.")
