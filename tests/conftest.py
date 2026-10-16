import pytest


@pytest.fixture
def example():
    text = "Drug A caused a rash."

    def span(part):
        start = text.index(part)
        return {"start": start, "end": start + len(part), "text": part}

    event = {
        "event_type": "Adverse_event",
        "trigger": [span("caused")],
        "drug": [span("Drug A")],
        "effect": [span("rash")],
        "raw_confidence": 0.8,
        "trigger_confidence": 0.9,
        "role_confidence": 0.8,
    }
    return {
        "id": "source_1",
        "source_group": "source",
        "context": text,
        "events": [event],
        "annotation_status": "valid",
    }
