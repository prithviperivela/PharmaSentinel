"""Export a static, GitHub-readable figure using measured final-test results."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pharmasentinel.io import read_json


def main():
    root = Path(__file__).resolve().parents[1]
    names = ["baseline", "biomedbert", "pharmasentinel_final", "biomedbert_all_ce"]
    metrics = [
        read_json(root / "reports/experiments" / f"{name}_test_metrics.json")
        for name in names
    ]
    review = read_json(root / "reports/experiments/biomedbert_all_ce_test_review.json")
    selected = read_json(root / "artifacts/biomedbert_all_ce/review_policy.json")[
        "selected_policy"
    ]
    by_policy = {
        r["policy"]: r for r in review["review"]["results"] if r["budget"] == 0.25
    }
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), gridspec_kw={"wspace": 0.35})
    colors = ["#99A7B1", "#46788D", "#16766D", "#9360A6"]
    values = np.array([m["strict_event"]["f1"] * 100 for m in metrics])
    bounds = [m["strict_f1_group_bootstrap_95pct"] for m in metrics]
    errors = np.array(
        [
            [
                max(0, value - bound["lower"] * 100)
                for value, bound in zip(values, bounds)
            ],
            [
                max(0, bound["upper"] * 100 - value)
                for value, bound in zip(values, bounds)
            ],
        ]
    )
    axes[0].bar(
        ["BiLSTM", "Original\nBiomedBERT", "Conservative", "Precision\nmode"],
        values,
        color=colors,
        yerr=errors,
        capsize=5,
    )
    axes[0].set(
        title="Complete-event extraction",
        ylabel="Strict core-event F1 (%)",
        ylim=(0, max(65, max(values) + 15)),
    )
    for i, value in enumerate(values):
        axes[0].text(
            i, value + errors[1, i] + 2, f"{value:.1f}", ha="center", fontweight="bold"
        )
    methods = ["random", "candidate_count", selected]
    capture = [by_policy[m]["error_capture_fraction"] * 100 for m in methods]
    axes[1].bar(
        ["Random", "Candidate\ncount", "Frozen\nreview policy"], capture, color=colors
    )
    axes[1].set(
        title="Precision mode: review 25% of passages",
        ylabel="Benchmark errors captured (%)",
        ylim=(0, 100),
    )
    for i, value in enumerate(capture):
        axes[1].text(i, value + 2, f"{value:.1f}", ha="center", fontweight="bold")
    for axis in axes:
        axis.set_axisbelow(True)
        axis.grid(axis="y", color="#DDE4E8", alpha=0.7)
    fig.suptitle(
        "PharmaSentinel | held-out benchmark results",
        fontsize=18,
        fontweight="bold",
        x=0.06,
        ha="left",
    )
    fig.text(
        0.06,
        0.02,
        "Left: exact type + trigger/drug/effect evidence; 95% source-group bootstrap intervals.\nRight: oracle-review simulation of FP + FN errors; candidate count is a simple comparator. No measured clinical or time benefit.",
        fontsize=9,
        color="#41535F",
    )
    fig.subplots_adjust(top=0.82, bottom=0.23)
    destination = root / "reports/figures/final_results.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=180, facecolor="white")
    plt.close(fig)
    print(destination)


if __name__ == "__main__":
    main()
