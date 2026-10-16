"""Aggregate-only analytical reports; source passages stay in local data files."""

from pathlib import Path
import html

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .data import audit
from .io import read_json


def build_report(root, name="baseline", split="policy"):
    root = Path(root)
    eda = audit(root)
    metrics_path = root / "reports/experiments" / f"{name}_{split}_metrics.json"
    review_path = root / "reports/experiments" / f"{name}_{split}_review.json"
    metrics = read_json(metrics_path) if metrics_path.exists() else None
    review = read_json(review_path) if review_path.exists() else None
    figures = []
    balance = pd.DataFrame(
        [
            {"split": s, "event_type": kind, "events": n}
            for s, values in eda.items()
            for kind, n in values["event_types"].items()
        ]
    )
    figures.append(
        px.bar(
            balance,
            x="split",
            y="events",
            color="event_type",
            barmode="group",
            title="Gold event mix in the selected benchmark (after explicit quarantine)",
        )
    )
    missing = pd.DataFrame(
        [
            {
                "split": s,
                "role": role,
                "missing_fraction": v[f"missing_{role}"] / v["events"]
                if v["events"]
                else 0,
            }
            for s, v in eda.items()
            for role in ("drug", "effect")
        ]
    )
    figures.append(
        px.bar(
            missing,
            x="split",
            y="missing_fraction",
            color="role",
            barmode="group",
            title="Annotation completeness: absent roles / retained events",
        )
    )
    if metrics:
        comparisons = []
        for path in sorted(
            (root / "reports/experiments").glob(f"*_{split}_metrics.json")
        ):
            value = read_json(path)
            if value.get("split") != split:
                continue
            for metric in ("precision", "recall", "f1"):
                comparisons.append(
                    {
                        "model": value["run_name"],
                        "metric": metric,
                        "value": value["strict_event"][metric],
                    }
                )
        figures.append(
            px.bar(
                pd.DataFrame(comparisons),
                x="model",
                y="value",
                color="metric",
                barmode="group",
                title=f"Strict reduced core-event metrics — {split}",
            )
        )
        evidence = pd.DataFrame(
            [
                {"role": role, "metric": metric, "value": values[metric]}
                for role, values in metrics["evidence_segments"].items()
                for metric in ("precision", "recall", "f1")
            ]
        )
        figures.append(
            px.bar(
                evidence,
                x="role",
                y="value",
                color="metric",
                barmode="group",
                title=f"{name}: standalone evidence segments; association scored separately",
            )
        )
        matrix = metrics["trigger_type_confusion"]
        xs = sorted({x for values in matrix.values() for x in values})
        ys = sorted(matrix)
        figures.append(
            px.imshow(
                [[matrix[y].get(x, 0) for x in xs] for y in ys],
                x=xs,
                y=ys,
                text_auto=True,
                aspect="auto",
                title="Event type at exactly matched triggers, with missed/spurious categories",
            )
        )
        subgroups = pd.DataFrame(
            [
                {"group": g, "f1": v["f1"], "passages": v["passages"]}
                for g, v in metrics["subgroups"].items()
            ]
        )
        figures.append(
            px.bar(
                subgroups,
                x="group",
                y="f1",
                hover_data=["passages"],
                title="Subgroup event F1 (small groups need cautious interpretation)",
            )
        )
    if review:
        reliability = pd.DataFrame(
            [r for r in review["reliability"]["bins"] if r["count"]],
            columns=["mean_confidence", "observed_correctness", "score", "count"],
        )
        figure = px.line(
            reliability,
            x="mean_confidence",
            y="observed_correctness",
            color="score",
            markers=True,
            hover_data=["count"],
            title="Candidate reliability: confidence versus observed strict correctness",
        )
        figure.add_trace(
            go.Scatter(
                x=[0, 1],
                y=[0, 1],
                mode="lines",
                name="ideal",
                line={"dash": "dash", "color": "gray"},
            )
        )
        if reliability.empty:
            figure.add_annotation(
                text="No emitted candidates: reliability cannot be estimated.",
                x=0.5,
                y=0.5,
                showarrow=False,
            )
        figures.append(figure)
        figures.append(
            px.line(
                pd.DataFrame(
                    review["review"]["results"],
                    columns=["budget", "error_capture_fraction", "policy"],
                ),
                x="budget",
                y="error_capture_fraction",
                color="policy",
                markers=True,
                title="Oracle-review simulation: captured unmatched-event errors / total errors",
            )
        )
    for figure in figures:
        figure.update_layout(
            template="plotly_white", font={"family": "Arial"}, margin={"t": 75, "b": 65}
        )
    title = f"PharmaSentinel · {name} · {split}"
    document = [
        f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>body{{font-family:Arial;max-width:1200px;margin:32px auto;padding:0 20px;color:#183047}}.notice{{background:#eef4f8;padding:18px;border-radius:8px}}section{{margin:28px 0}}h1{{color:#163b54}}</style></head><body><h1>{html.escape(title)}</h1><div class='notice'>Research prototype. Counts describe the benchmark, not population incidence. Confidence concerns extraction correctness, not clinical severity. Review curves are simulations, not measured time savings.</div>"
    ]
    for i, figure in enumerate(figures):
        document.append(
            "<section>"
            + figure.to_html(
                full_html=False, include_plotlyjs=True if i == 0 else False
            )
            + "</section>"
        )
    document.append("</body></html>")
    path = root / "reports/figures" / f"{name}_{split}_analytics.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(document), encoding="utf-8")
    lines = [
        f"# PharmaSentinel: {name} results on {split}",
        "",
        f"Evaluation status: {'final held-out test' if split == 'test' else 'development result; not final test performance'}.",
        "",
        "## Dataset",
        "",
        "Primary benchmark: pinned PHEE2 source annotations. Original source files contain 4,827 passages. Annotation issues, split IDs and hashes are recorded in `reports/data/`. One passage has an invalid upstream evidence annotation and is explicitly quarantined from training/scoring. Source-ID grouping is a proxy; the lexical near-duplicate screen does not rule out all semantic leakage.",
        "",
        "## Evaluation definition",
        "",
        "A strict core event requires the correct event type and exact trigger, drug-role and effect-role span sets. Matching is one-to-one; duplicate predictions are false positives. Empty roles are permitted when gold annotations are empty. This reduced-schema metric is not directly comparable with published full-PHEE scores.",
        "",
    ]
    if metrics:
        lines.extend(["| Scope | Precision | Recall | F1 |", "|---|---:|---:|---:|"])
        for label, value in [
            ("Strict core event", metrics["strict_event"]),
            (
                "Relaxed event (role character IoU ≥ 0.5)",
                metrics["relaxed_event_iou_0.5"],
            ),
            *[
                (f"{r} evidence segments", v)
                for r, v in metrics["evidence_segments"].items()
            ],
        ]:
            lines.append(
                f"| {label} | {value['precision']:.3f} | {value['recall']:.3f} | {value['f1']:.3f} |"
            )
        c = metrics["strict_event"]
        lines.extend(
            [
                "",
                f"Evaluated passages: **{metrics['evaluated_passages']}**. Exact matches: **{c['tp']}**; unmatched predictions: **{c['fp']}**; unmatched gold events: **{c['fn']}**.",
                "",
                "Standalone evidence scores do not establish correct event association. The difference from strict event F1 is part of the error analysis.",
            ]
        )
        ci = metrics.get("strict_f1_group_bootstrap_95pct")
        if ci:
            lines.extend(
                [
                    "",
                    f"Strict event F1 source-group bootstrap interval: **{ci['lower']:.3f}–{ci['upper']:.3f}**, {ci['replicates']} resamples. This interval addresses sampled-source variation, not all training-seed variation.",
                ]
            )
    if review:
        r = review["reliability"]
        lines.extend(
            [
                "",
                "## Calibration and review",
                "",
                f"Candidate Brier score (lower is better): raw **{r['brier_raw']:.4f}**, calibrated **{r['brier_calibrated']:.4f}**."
                if r["brier_raw"] is not None
                else "No emitted candidates; candidate calibration cannot be measured.",
                "",
                "Calibration is fitted on the separate calibration subset. Better calibration does not guarantee better ranking or error capture at a fixed budget. Compare each policy's actual results.",
                "",
                "| Policy | Review budget | Reviewed passages | Error capture | Missed events exposed |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in review["review"]["results"]:
            lines.append(
                f"| {row['policy']} | {row['budget']:.0%} | {row['reviewed_passages']} | {row['error_capture_fraction']:.1%} | {row['missed_events_exposed']:.1f} |"
            )
        lines.extend(
            [
                "",
                "These are oracle-review simulations: every gold/prediction mismatch in a reviewed passage is assumed discoverable. The error unit is FP + FN; one wrong extraction may contribute both. Reviewer time savings and clinical benefit were not measured.",
            ]
        )
    lines.extend(
        [
            "",
            "## Interpretation for interviews",
            "",
            "Explain the data issue and how it was handled, the baseline association rule, why exact event extraction is harder than recognizing individual words, how the held-out subsets prevent leakage, and whether calibration improved the chosen operational metric. Discuss the therapeutic minority class and difficult structures rather than hiding them.",
            "",
            "## Limitations",
            "",
            "Passage-level, event-enriched benchmark; no clinical causality inference. Original entity grouping is retained in prepared annotations but not fully reconstructed by this reduced event-role decoder. Overlapping trigger/role spans may not be representable. The synthetic challenge suite is self-authored and not expert validation. Corpus counts are not adverse-event incidence.",
            "",
            f"Interactive aggregate report: [open charts](../figures/{name}_{split}_analytics.html).",
            "",
        ]
    )
    markdown = root / "reports/experiments" / f"{name}_{split}_REPORT.md"
    markdown.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text("\n".join(lines), encoding="utf-8")
    return {
        "markdown": str(markdown),
        "interactive_html": str(path),
        "figures": len(figures),
    }
