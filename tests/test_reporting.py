from pharmasentinel.io import write_json
from pharmasentinel.reporting import build_report


def test_no_candidate_report_is_generated(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "pharmasentinel.reporting.audit",
        lambda root: {
            "train": {
                "event_types": {"Adverse_event": 1},
                "events": 1,
                "missing_drug": 0,
                "missing_effect": 0,
            }
        },
    )
    write_json(
        tmp_path / "reports/experiments/empty_policy_review.json",
        {
            "reliability": {
                "candidates": 0,
                "bins": [],
                "brier_raw": None,
                "brier_calibrated": None,
            },
            "review": {
                "results": [
                    {
                        "policy": "raw",
                        "budget": 0.25,
                        "reviewed_passages": 1,
                        "error_capture_fraction": 1.0,
                        "missed_events_exposed": 1,
                    }
                ]
            },
        },
    )
    result = build_report(tmp_path, "empty", "policy")
    from pathlib import Path

    assert "No emitted candidates" in Path(result["interactive_html"]).read_text(
        encoding="utf-8"
    )
    assert "No emitted candidates" in Path(result["markdown"]).read_text(
        encoding="utf-8"
    )
