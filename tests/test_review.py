import copy

from pharmasentinel.reliability import apply_calibrator, priority, review_experiment


def test_no_event_output_is_flagged_for_review():
    assert priority({"events": [], "status": "ok"}, "calibrated_checks") == (1, 1.0)


def test_review_simulation_counts_missed_events(example):
    result = review_experiment(
        [example], [{"id": example["id"], "events": [], "status": "ok"}], budgets=(1.0,)
    )
    assert result["total_missed_events"] == 1
    assert all(r["missed_events_exposed"] == 1 for r in result["results"])


def test_calibration_does_not_overwrite_predictions(example):
    predictions = [example]
    original = copy.deepcopy(predictions)
    calibrated = apply_calibrator(predictions, {"method": "identity_fallback"})
    assert predictions == original
    assert calibrated[0]["events"][0]["calibrated_confidence"] == 0.8


def test_fixed_review_budget_includes_zero_event_passages(example):
    rows = []
    predictions = []
    for i in range(10):
        row = {**example, "id": f"doc_{i}", "source_group": f"doc{i}"}
        rows.append(row)
        predictions.append({"id": row["id"], "events": [], "status": "ok"})
    report = review_experiment(rows, predictions, budgets=(0.1, 0.5))
    assert {
        r["reviewed_passages"] for r in report["results"] if r["budget"] == 0.1
    } == {1}
    assert {
        r["reviewed_passages"] for r in report["results"] if r["budget"] == 0.5
    } == {5}


def test_full_review_capture_interval_and_workload(example):
    report = review_experiment(
        [example], [{"id": example["id"], "events": [], "status": "ok"}], budgets=(1.0,)
    )
    for result in report["results"]:
        assert result["remaining_errors"] == 0
        assert result["reviewed_characters"] == len(example["context"])
        if result["policy"] != "random":
            assert result["lift_over_random_expectation"] == 1
            assert result["capture_group_bootstrap_95pct"]["lower"] == 1
            assert result["capture_group_bootstrap_95pct"]["upper"] == 1


def test_brier_constant_is_from_calibration_not_evaluation_labels(example):
    from pharmasentinel.reliability import reliability_summary

    predictions = apply_calibrator([example], {"method": "identity_fallback"})
    result = reliability_summary([example], predictions, constant_probability=0.25)
    assert result["brier_calibration_prevalence_constant"] == 0.75**2
    assert result["brier_skill_vs_calibration_constant"] > 0
