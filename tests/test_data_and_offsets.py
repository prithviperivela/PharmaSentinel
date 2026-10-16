import numpy as np

from pharmasentinel.data import adapt
from pharmasentinel.labeling import bio_labels, decode_bio, tokenize


def test_unicode_offsets_round_trip():
    text = "🙂 Drug A caused a rash."
    _, offsets = tokenize(text)
    start = text.index("Drug A")
    labels, issues = bio_labels(offsets, [{"start": start, "end": start + 6}])
    probs = np.eye(3)[labels]
    decoded = decode_bio(labels, probs, offsets, text)
    assert decoded[0]["span"]["text"] == "Drug A"
    assert issues["unaligned_gold_segments"] == 0


def test_discontinuous_role_decodes_as_two_segments():
    text = "rash and swelling"
    _, offsets = tokenize(text)
    labels, _ = bio_labels(offsets, [{"start": 0, "end": 4}, {"start": 9, "end": 17}])
    decoded = decode_bio(labels, np.eye(3)[labels], offsets, text)
    assert [x["span"]["text"] for x in decoded] == ["rash", "swelling"]


def test_special_tokens_are_ignored():
    labels, _ = bio_labels([(0, 0), (0, 4), (0, 0)], [{"start": 0, "end": 4}])
    assert labels.tolist() == [-100, 1, -100]


def raw_example():
    return {
        "id": "doc_1",
        "context": "Drug A caused rash.",
        "annotations": [
            {
                "events": [
                    {
                        "event_id": "E1",
                        "event_type": "Adverse_event",
                        "Trigger": {"text": [["caused"]], "start": [[7]]},
                        "Treatment": {"Drug": {"text": [["Drug A"]], "start": [[0]]}},
                        "Effect": {"text": [["rash"]], "start": [[14]]},
                    }
                ]
            }
        ],
    }


def test_invalid_upstream_offset_is_quarantined_visibly():
    raw = raw_example()
    raw["annotations"][0]["events"][0]["Effect"]["start"] = [[13]]
    row, issues = adapt(raw, "train")
    assert row["annotation_status"] == "quarantined"
    assert row["quarantined_event_count"] == 1
    assert len(issues) == 1


def test_missing_annotation_role_is_preserved_as_empty():
    raw = raw_example()
    del raw["annotations"][0]["events"][0]["Effect"]
    row, issues = adapt(raw, "train")
    assert row["annotation_status"] == "valid"
    assert row["events"][0]["effect"] == []
    assert issues == []
