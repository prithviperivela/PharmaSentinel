# Release verification

- Scientific/inference test suite: **41 passed** (73.07 seconds in the recorded run).
- Ruff undefined/unused-name checks (`--select F`): passed.
- All four release checkpoints reloaded and reproduced eight saved policy-subset
  predictions each. Removing gold annotations did not change their predictions.
- Streamlit AppTest exercised Dataset, Model quality, Review analysis and Try a
  passage for both release modes. Live extraction and structured downloads passed.
- The frozen protocol recorded no prior final-test results. All four final runs
  passed code, data, tokenizer, configuration, checkpoint and calibration identity checks.
- Paired comparisons used the same eligible test passages and source-prefix groups.
- The static benchmark chart was rendered and visually inspected.
- Final MySQL analytical exports were generated for both release modes. A live
  MySQL server was not configured, so database loading is **not verified**.

Machine-readable records are in `reports/verification/`, with the immutable
experiment identities in `reports/frozen_protocol.json`. Files whose names begin
with `retry_` describe the earlier audit stage, not the final release state.

These checks address specific implementation errors. They do not prove absence
of all leakage, correctness of upstream annotations, external generalization,
clinical suitability or human-review benefit. See RESULTS.md for measured failures.
