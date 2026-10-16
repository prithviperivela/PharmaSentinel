"""Single-user local analytical viewer. No service or operational review workflow."""

from pathlib import Path
import html
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from pharmasentinel.io import read_json, read_jsonl
from pharmasentinel.reliability import apply_calibrator, priority

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="PharmaSentinel", page_icon="🧬", layout="wide")
st.title("PharmaSentinel")
st.caption("Biomedical event extraction · evidence · reliability analytics")
st.info(
    "Research prototype. Confidence describes extraction correctness. Corpus frequencies are not population risk; outputs do not establish clinical causality."
)

ready = [
    p.name for p in (ROOT / "artifacts").glob("*") if (p / "metadata.json").exists()
]
if not ready:
    st.warning(
        "Prepare the dataset and train a model first. See README.md for pipeline commands."
    )
    st.stop()
ordered = sorted(ready, key=lambda name: (name != "pharmasentinel_final", name))
model_labels = {
    "pharmasentinel_final": "Conservative mode (development recall safeguard)",
    "biomedbert_all_ce": "Precision-oriented mode (lower therapeutic recall in development)",
    "biomedbert": "Original BiomedBERT",
    "baseline": "BiLSTM baseline",
}
name = st.sidebar.selectbox(
    "Trained model", ordered, format_func=lambda value: model_labels.get(value, value)
)
page = st.sidebar.radio(
    "Analysis", ["Dataset", "Model quality", "Review analysis", "Try a passage"]
)
split = st.sidebar.selectbox("Results subset", ["policy", "model_selection", "test"])
metadata = read_json(ROOT / "artifacts" / name / "metadata.json")
st.sidebar.caption(
    f"Model: {metadata['model_type']} · seed {read_json(ROOT / 'artifacts' / name / 'config.json')['seed']}"
)
st.sidebar.caption(
    "Test scores appear only after the protocol is frozen and explicitly evaluated."
)


@st.cache_resource
def predictor(model_name, weights_hash, config_hash):
    from pharmasentinel.inference import load_predictor

    return load_predictor(ROOT / "artifacts" / model_name)


def highlighted(text, event):
    colors = {"trigger": "#fee8ac", "drug": "#c6e9fa", "effect": "#f8cdd3"}
    segments = [
        (s["start"], s["end"], role) for role in colors for s in event.get(role, [])
    ]
    boundaries = sorted({0, len(text), *(x for a, b, _ in segments for x in (a, b))})
    pieces = []
    for a, b in zip(boundaries, boundaries[1:]):
        active = [role for start, end, role in segments if start <= a and end >= b]
        fragment = html.escape(text[a:b])
        if active:
            color = colors[active[0]] if len(set(active)) == 1 else "#dfd4f7"
            fragment = f"<mark style='background:{color};padding:2px' title='{','.join(active)}'>{fragment}</mark>"
        pieces.append(fragment)
    return (
        "<div style='line-height:1.9;padding:16px;border:1px solid #ddd;border-radius:8px'>"
        + "".join(pieces)
        + "</div>"
    )


if page == "Dataset":
    path = ROOT / "reports/data/eda_summary.json"
    if not path.exists():
        st.warning("Run pharmasentinel audit first.")
        st.stop()
    eda = read_json(path)
    frames = pd.DataFrame(
        [
            {"split": s, **{k: v for k, v in value.items() if k != "event_types"}}
            for s, value in eda.items()
        ]
    )
    st.subheader("Dataset composition")
    st.dataframe(frames, hide_index=True, width="stretch")
    balance = pd.DataFrame(
        [
            {"split": s, "event_type": kind, "events": n}
            for s, value in eda.items()
            for kind, n in value["event_types"].items()
        ]
    )
    st.plotly_chart(
        px.bar(balance, x="split", y="events", color="event_type", barmode="group"),
        width="stretch",
    )
    manifest = read_json(ROOT / "reports/data/preparation_manifest.json")
    st.write(
        f"Metadata flag disagreements: **{manifest['metadata_flag_disagreements']}**. Quarantined annotation events: **{manifest['quarantined_events']}**."
    )
    st.caption(
        "Source groups use the upstream ID prefix as a proxy. Data manifests record the exact split IDs and hashes."
    )
elif page == "Model quality":
    path = ROOT / "reports/experiments" / f"{name}_{split}_metrics.json"
    if not path.exists():
        st.warning(
            f"No {split} evaluation exists for {name}. The final test is deliberately gated."
        )
        st.stop()
    report = read_json(path)
    st.subheader(f"{split} · strict core-event evaluation")
    columns = st.columns(3)
    for column, metric in zip(columns, ["precision", "recall", "f1"]):
        column.metric(metric.upper(), f"{report['strict_event'][metric]:.1%}")
    st.caption(report["metric_definition"])
    table = pd.DataFrame(
        [
            {"scope": role, **values}
            for role, values in report["evidence_segments"].items()
        ]
    )
    st.dataframe(table, hide_index=True, width="stretch")
    st.write(
        "Standalone span recognition and complete event association are different measurements."
    )
    st.dataframe(
        pd.DataFrame(
            [
                {"group": group, **values}
                for group, values in report["subgroups"].items()
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    with st.expander("Full measured report"):
        st.json(report)
elif page == "Review analysis":
    path = ROOT / "reports/experiments" / f"{name}_{split}_review.json"
    if not path.exists():
        st.warning("Run calibration and the review experiment for this subset first.")
        st.stop()
    report = read_json(path)
    st.subheader("Confidence and review budget")
    r = report["reliability"]
    columns = st.columns(2)
    columns[0].metric(
        "Raw candidate Brier score",
        f"{r['brier_raw']:.4f}" if r["brier_raw"] is not None else "N/A",
    )
    columns[1].metric(
        "Calibrated candidate Brier score",
        f"{r['brier_calibrated']:.4f}" if r["brier_calibrated"] is not None else "N/A",
    )
    results = pd.DataFrame(report["review"]["results"])
    st.plotly_chart(
        px.line(
            results,
            x="budget",
            y="error_capture_fraction",
            color="policy",
            markers=True,
        ),
        width="stretch",
    )
    st.caption(
        report["review"]["simulation"]
        + ". Better calibration does not guarantee better ranking."
    )
    st.dataframe(results, hide_index=True, width="stretch")
    predictions_path = ROOT / "reports/predictions" / f"{name}_{split}_calibrated.jsonl"
    if predictions_path.exists():
        predictions = read_jsonl(predictions_path)
        policy_path = ROOT / "artifacts" / name / "review_policy.json"
        policy = (
            read_json(policy_path)["selected_policy"] if policy_path.exists() else "raw"
        )
        st.caption(f"Priority table uses the development-selected policy: {policy}.")
        ranked = sorted(
            predictions,
            key=lambda row: (*priority(row, policy), row["id"]),
            reverse=True,
        )
        queue = pd.DataFrame(
            [
                {
                    "passage_id": row["id"],
                    "candidates": len(row["events"]),
                    "priority_score": priority(row, policy)[1],
                    "structural_flag": bool(priority(row, policy)[0]),
                    "status": row["status"],
                }
                for row in ranked
            ]
        )
        st.download_button(
            "Download ranked review table",
            queue.to_csv(index=False),
            file_name=f"{name}_{split}_review.csv",
            mime="text/csv",
        )
else:
    st.subheader("Inspect evidence in a short passage")
    st.caption(
        "The example is fictional. Public demo text is processed locally; no external inference API is used."
    )
    text = st.text_area(
        "Passage",
        value="Drug A caused a rash. Drug B improved the rash.",
        height=140,
        max_chars=20000,
    )
    if st.button("Extract events", type="primary"):
        with st.spinner("Running the selected model locally…"):
            result = predictor(
                name, metadata["weights_sha256"], metadata.get("config_sha256")
            ).predict([{"id": "interactive", "context": text}])
            calibrator_path = ROOT / "artifacts" / name / "calibrator.json"
            if calibrator_path.exists():
                result = apply_calibrator(result, read_json(calibrator_path))
        row = result[0]
        if row["status"] != "ok":
            st.warning(f"Input could not be processed: {row['status']}")
        elif not row["events"]:
            st.warning(
                "No event was extracted. This does not establish absence of an event; inspect the passage manually."
            )
        for i, event in enumerate(row["events"], 1):
            st.markdown(f"**Candidate {i}: {event['event_type']}**")
            st.markdown(highlighted(text, event), unsafe_allow_html=True)
            st.write(
                {
                    "drug_evidence": [s["text"] for s in event["drug"]],
                    "effect_evidence": [s["text"] for s in event["effect"]],
                    "raw_confidence": event["raw_confidence"],
                    "calibrated_confidence": event.get("calibrated_confidence"),
                    "flags": event["flags"],
                }
            )
        st.caption(
            "Highlight colors: trigger = yellow; drug = blue; effect = pink; overlapping roles = purple. Highlighting shows provenance, not semantic correctness."
        )
        st.download_button(
            "Download structured extraction",
            json.dumps(row, indent=2, ensure_ascii=False),
            file_name="pharmasentinel_prediction.json",
            mime="application/json",
        )
