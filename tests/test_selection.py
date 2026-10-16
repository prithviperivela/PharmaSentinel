import copy

import pytest

from pharmasentinel.selection import filter_triggers


def test_threshold_is_inclusive_and_keeps_source_immutable():
    source = [
        {
            "id": "x",
            "events": [{"trigger_confidence": 0.5}, {"trigger_confidence": 0.49}],
            "status": "ok",
            "flags": [],
        }
    ]
    saved = copy.deepcopy(source)
    result = filter_triggers(source, 0.5)
    assert len(result[0]["events"]) == 1
    assert source == saved
    empty = filter_triggers(source, 0.8)
    assert empty[0]["events"] == []
    assert empty[0]["flags"] == ["no_event_extracted"]


@pytest.mark.parametrize("threshold", [-0.1, 1.1, float("nan"), float("inf")])
def test_threshold_rejects_invalid_values(threshold):
    with pytest.raises(ValueError):
        filter_triggers([], threshold)


def test_sweep_cannot_drop_all_events_to_look_precise(example):
    from pharmasentinel.evaluation import evaluate
    from pharmasentinel.selection import threshold_sweep

    reference, _ = evaluate([example], [example], bootstrap=0)
    result = threshold_sweep(
        [example], [{"id": example["id"], "events": []}], reference
    )
    assert result["selected"] is None
    assert all(not row["eligible"] for row in result["candidates"])
