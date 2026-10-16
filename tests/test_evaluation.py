import copy

import pytest

from pharmasentinel.evaluation import (
    candidate_correctness,
    evaluate,
    overlap,
    validate_event,
)


def test_exact_event_is_correct(example):
    report, _ = evaluate(
        [example], [{"id": example["id"], "events": example["events"]}], bootstrap=0
    )
    assert report["strict_event"]["f1"] == 1


def test_duplicate_prediction_does_not_earn_double_credit(example):
    report, _ = evaluate(
        [example], [{"id": example["id"], "events": example["events"] * 2}], bootstrap=0
    )
    assert report["strict_event"]["tp"] == 1
    assert report["strict_event"]["fp"] == 1
    assert candidate_correctness(example["events"], example["events"] * 2) == [1, 0]


def test_completely_missing_prediction_counts_gold_event(example):
    report, details = evaluate([example], [], bootstrap=0)
    assert report["strict_event"]["fn"] == 1
    assert report["missing_or_failed_outputs"] == 1
    assert details[0]["errors"] == 1


def test_spurious_event_in_no_event_passage(example):
    gold = copy.deepcopy(example)
    gold["events"] = []
    report, _ = evaluate(
        [gold], [{"id": example["id"], "events": example["events"]}], bootstrap=0
    )
    assert report["strict_event"]["fp"] == 1


def test_wrong_type_is_not_correct(example):
    prediction = copy.deepcopy(example)
    prediction["events"][0]["event_type"] = "Potential_therapeutic_event"
    report, _ = evaluate([example], [prediction], bootstrap=0)
    assert report["strict_event"]["tp"] == 0
    assert report["strict_event"]["fp"] == report["strict_event"]["fn"] == 1
    assert (
        report["trigger_type_confusion"]["Adverse_event"]["Potential_therapeutic_event"]
        == 1
    )


def test_empty_roles_can_be_correct(example):
    example["events"][0]["effect"] = []
    report, _ = evaluate([example], [example], bootstrap=0)
    assert report["strict_event"]["f1"] == 1


def test_quarantined_passage_has_explicit_exclusion(example):
    example["annotation_status"] = "quarantined"
    report, _ = evaluate([example], [], bootstrap=0)
    assert report["evaluated_passages"] == 0
    assert report["excluded_quarantined_ids"] == [example["id"]]


def test_wrong_evidence_is_rejected(example):
    event = copy.deepcopy(example["events"][0])
    event["drug"][0]["text"] = "Wrong medicine"
    with pytest.raises(ValueError, match="evidence text"):
        validate_event(event, example["context"])


def test_unexpected_and_duplicate_ids_are_rejected(example):
    with pytest.raises(ValueError, match="Duplicate prediction"):
        evaluate([example], [example, example], bootstrap=0)
    with pytest.raises(ValueError, match="unexpected"):
        evaluate([example], [{**example, "id": "unknown"}], bootstrap=0)


def test_discontinuous_overlap_preserves_gap():
    a = [{"start": 0, "end": 2}, {"start": 8, "end": 10}]
    b = [{"start": 0, "end": 10}]
    assert overlap(a, b) == 0.4


def test_bootstrap_is_repeatable(example):
    a, _ = evaluate([example], [example], bootstrap=20, seed=7)
    b, _ = evaluate([example], [example], bootstrap=20, seed=7)
    assert a["strict_f1_group_bootstrap_95pct"] == b["strict_f1_group_bootstrap_95pct"]
