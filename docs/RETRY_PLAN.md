# PharmaSentinel: implementation audit and revised retry plan

Historical audit snapshot before the v2 experiments. Current decisions and results
are in `EXPERIMENT_PLAN_V2.md` and `PROJECT_REPORT.md`; the status statements below
describe the time of this audit.

**Status:** Ready for a staged retry. This audit does not start a new training run, access the held-out model test, create a GitHub repository or publish files.

## 1. What actually happened

The implementation reached data preparation, full-data training, development evaluation and a local analytical viewer. Both models trained successfully:

| Evidence | Baseline | BiomedBERT |
|---|---:|---:|
| Training passages | 2,898 | 2,898 |
| Epochs completed | 8 | 4 |
| Selected epoch | 8 | 3 |
| Strict core-event F1 on model-selection data | 0.142 | 0.305 |
| Strict core-event F1 on the separate policy subset | 0.137 | 0.301 |
| Relaxed event F1 on the policy subset | 0.264 | 0.546 |

The saved checkpoints reproduced their recorded predictions in an eight-passage preflight for each model. Removing gold annotations from those inputs did not change predictions. The earlier focused suite passed 23 tests before the retry safeguards were added.

**The final test has not been used for prediction or model-performance evaluation.** Its source text and annotation integrity were inspected during preparation; the one invalid upstream passage (`10870095_7`) is quarantined. No frozen final protocol exists yet. The current 968-record test file therefore has 967 eligible passages under this declared exclusion policy.

No Git repository or remote PharmaSentinel repository was created during the initial build. GitHub browser sign-in is now verified for the intended account. The connector still reports unavailable in this session, so browser authentication and connector authentication must be distinguished.

The browser tooling also logged separate telemetry/network errors while the authenticated GitHub dashboard loaded successfully. Those messages did not represent a failed repository upload: no create/upload operation had been attempted. The retry must verify the outcome of each GitHub action on the repository page rather than treating unrelated instrumentation logs as publishing status.

## 2. What went wrong, with evidence

### A. Environment checks happened too late

Python package setup failed because the sandbox could not read Python's temporary wheel directories. The first virtual-environment creation stopped before enabling the intended inherited packages, which caused a subsequent missing-NumPy error. Setup was repaired using approved native execution and the already installed ML packages.

The default Hugging Face cache then encountered Windows path-length and symlink privilege problems. This was repaired with a flat, upstream-hash-verified model download.

The first biomedical training attempt used CPU before GPU availability was verified. It was stopped and replaced by a complete GPU run after the RTX 4070 Laptop GPU was confirmed. No results from the interrupted CPU attempt are reported as a completed experiment.

**Change:** Verify environment, package imports, temporary-file access, model download and an actual device smoke test before selecting the training configuration. Use a clean isolated environment for the retry where practical; record exact versions and any inherited-package exception. Do not change system security settings or enable symlinks to make the model cache work.

### B. Experiment artifacts were not sufficiently protected

Training accepted an existing run directory. An interrupted rerun could overwrite configuration/vocabulary while leaving earlier weights or metadata in place.

**Correction implemented:** Training now rejects existing run names. Retry runs must use distinct names, such as `baseline_v2` and `biomedbert_v2`. The current runs remain historical references.

### C. Prediction identities were recorded but not enforced

Predictions carried model and text hashes, but the CLI evaluator could still score a different model's prediction file under the selected run name if passage IDs matched. The checkpoint loader also did not verify its recorded weight hash before loading.

**Corrections implemented:** Calibration, evaluation, review analysis and paired comparison now validate prediction run name, model hash, source-text hash, schema, evidence and score bounds. Missing predictions remain countable failures. The shared checkpoint loader checks the actual weight-file hash.

These guards protect result attribution. They do not make the underlying model more accurate.

### D. Model quality is not yet adequate for a strong general-purpose demo

On the 487-passage model-selection subset, BiomedBERT produced 775 event candidates against 510 annotated events. Of its predictions:

- 196 were strictly correct complete events.
- 322 predicted triggers had no overlap with an annotated trigger.
- 56 overlapped a gold trigger but had incorrect boundaries.
- 201 had an exact trigger but incorrect event fields.
- Within that last group, 80 had the correct trigger/type/drug and an effect overlap of at least 0.5, but incorrect exact effect evidence.

These are benchmark-relative diagnostic counts, not proof that every unannotated phrase is medically false. They show that excess triggers and effect boundaries deserve priority over adding more application features.

The therapeutic class is weak: its strict event F1 is about 0.066 on the policy subset. On the tiny synthetic development suite, BiomedBERT emitted events for two of four no-event examples. That suite is too small and schematic to estimate a deployment false-positive rate, but it exposes a real robustness gap under its declared rubric.

**Change:** Address trigger precision/no-event behavior, effect boundaries and minority-class performance on development data before final evaluation. Preserve exact scoring. Do not replace strict F1 with relaxed F1 simply to make results look better.

### E. Review-budget results needed clearer interpretation

The additive expected-incorrect-candidate policy captured more benchmark errors at a 25% passage budget in exploratory development analysis. However, passages containing many candidates can take longer to inspect. Equal passage counts do not establish equal review effort or time savings.

The additive policy was introduced after inspecting earlier development results. It is an exploratory development choice, not a pre-specified successful final-test result. The held-out test remains available to assess the frozen policy later.

**Correction implemented:** The simulation now also reports reviewed candidates, reviewed source characters, exposed false predictions and complete trigger misses. The workload caveat is explicit. A future cost-sensitive analysis may use declared proxy review units, but those are not measured seconds.

### F. Passing unit tests did not establish full release readiness

The original tests protected important metric and span behavior, but did not cover wrong-model files, changed source text or accidental run overwrites. A zero-candidate analytical report also needed a chart fallback.

**Corrections implemented:** Added run/provenance regression tests and an empty-reliability chart fallback. Repeated operational checks, final evaluation and publication remain separate gates. MySQL schema/exports exist, but live database loading is unverified because no configured local server is available.

**Audit verification:** The revised suite passes **30 tests**. Formatting/lint checks pass. Both weight files match their recorded hashes, and all 1,922 saved development predictions (961 per model) passed model/source identity validation. No held-out test prediction files exist.

## 3. Revised problem and objective

**Problem:** Extracting medicine/effect names from research passages is insufficient when therapeutic uses, uncertain associations and multiple events coexist.

**Objective:** Extract event-associated evidence, measure where it fails, and evaluate uncertainty-based review allocation using clearly defined budgets and workload indicators.

The project remains centered on NLP, deep learning, statistics, SQL and analytical communication. No API service, microservices or operational reviewer-management system is added.

## 4. Revised workflow and gates

```text
Environment and device preflight
          ↓
Pinned data and annotation contract
          ↓
Versioned baseline and error diagnosis
          ↓
One targeted model improvement at a time
          ↓
Separate calibration and policy selection
          ↓
Development robustness and workload checks
          ↓
Freeze model, data, code and policy
          ↓
One final evaluation + uncertainty report
          ↓
Minimal viewer, SQL analytics and public GitHub release
```

| Stage | Required work | Gate |
|---|---|---|
| 0. Runtime | Verify Python environment, exact core packages, temporary-file access, GPU and flat encoder source | Small model forward/backward and artifact read/write work on the selected device |
| 1. Data contract | Reuse pinned PHEE2; validate offsets, empty roles, splits, multiplicity and quarantined passage | Audit counts reproducible; no unexplained source/exact-text overlap |
| 2. Experiment integrity | Preserve v1; create new run names; enforce model/text identities | A wrong-model file and an overwrite attempt fail before producing a report |
| 3. Model improvement | Use model-selection data to investigate excess triggers, effect boundaries and minority errors | Improvements and recall tradeoffs documented against v1 on the same task |
| 4. Reliability | Fit calibration on calibration subset; select policy on policy subset | Brier/reliability, FP/FN capture and workload reported separately |
| 5. Robustness | Check no-event/negated/therapeutic cases, grouping limits and selected-run stability | No hidden exclusions; remaining failures explicit; repeat selected settings across seeds if feasible |
| 6. Freeze | Save weight, tokenizer, label, data, code, calibration and policy identities | Final command accepts unchanged artifacts and rejects changed ones |
| 7. Final evaluation | Evaluate eligible held-out passages and reserved challenge once choices are fixed | Strict/relaxed metrics, rare-class results, misses and paired intervals clearly labeled |
| 8. Presentation | Update interview report, verify viewer and publish approved source/aggregate files | Public repository verified; no raw source passages, credentials or weight files uploaded |

## 5. Targeted modeling experiments for the retry

Limit initial experiments to the measured problems:

1. **Trigger precision:** inspect no-gold-overlap predictions; evaluate development-selected trigger acceptance thresholds with recall and no-output counts visible. Determine whether additional genuinely annotated no-event training text is needed. Absence of an annotation alone must not be treated as a negative label.
2. **Effect boundaries:** inspect near misses and annotation conventions; then test a focused boundary/role-loss adjustment. Keep original source evidence and strict metrics. Add structured decoding only if observed sequence errors justify it.
3. **Therapeutic minority:** compare a small number of class/loss balancing choices and report per-class precision/recall. The existing model already uses square-root inverse-frequency weights; repeating that under a new name is not an improvement.

Use the model-selection subset for model choices. Do not repeatedly choose model variants using the policy subset. Keep calibration fitting separate. Any additional no-event dataset requires a checked source/license, explicit annotation rubric and source-separated allocation before it joins training. Existing synthetic development and reserved challenge examples do not become training examples.

Only after choosing the model should its calibrator and review policy be refitted. Retraining changes candidate populations, so old calibrators must not be silently reused.

## 6. What we keep and what we defer

**Keep:** verified PHEE2 files, original text/offsets, prepared splits, v1 checkpoints, strict evaluator, synthetic diagnostic files, analytical plots, three-table MySQL design and a small viewer.

**Defer:** final-test access, public publication, live MySQL claims, reviewer-time claims and additional model families until the relevant gate is met. The signed-in GitHub browser can be used at the release stage; it does not imply that CLI or connector publishing is authenticated.

## 7. Retry sequence

1. Run environment/device and integrity checks before any training.
2. Verify the new regression tests and the zero-candidate reporting case.
3. Review a small, documented sample of the diagnosed trigger/effect/minority errors.
4. Agree the first targeted experiment and its development-only selection rule.
5. Run it under a new name, preserving v1 artifacts and logs.
6. Inspect development results and failure examples before deciding whether further modeling or final evaluation is appropriate.

This staged sequence avoids repeating the whole setup or discarding the work already completed. **The workflow and retry preparation are ready; no new training or publication was initiated by this audit.**
