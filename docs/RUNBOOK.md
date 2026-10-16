# Reproducing and explaining the pipeline

Run commands from the repository root in the configured Python environment.
The local experiment used Python 3.13 with inherited system packages; its exact
core versions and GPU check are recorded in `reports/verification/environment_preflight.json`.
For another machine use a clean venv, install a compatible PyTorch build, then
`python -m pip install -c constraints-tested.txt -e ".[dev,viewer,mysql]"`. Inheritance is a local setup
exception, not a prerequisite or a portable environment lock.
Install the `figures` extra to regenerate the static results chart. Git attributes
preserve file bytes because the frozen protocol hashes code and data exactly.
The committed freeze records the original experiment. When reproducing with new
artifacts, retain a copy of that record elsewhere and create a fresh local freeze.

## Data and runtime

```powershell
python -m pharmasentinel fetch
python -m pharmasentinel prepare
python -m pharmasentinel audit
python -m pharmasentinel leakage-screen
python scripts/environment_preflight.py --device cuda
python -m pytest -q -p no:cacheprovider
```

The first encoder download needs internet access. Subsequent runs verify and reuse
the saved cache offline. Use CPU configurations if CUDA is unavailable. The CLI
rejects existing run directories: choose new names for independent experiments.

## Controlled development

Train the baseline and original biomedical model using the README commands. Then:

```powershell
python -m pharmasentinel train --model biomedbert --name biomedbert_trigger_ce --config configs/biomedbert_trigger_ce.json
python -m pharmasentinel train --model biomedbert --name biomedbert_all_ce --config configs/biomedbert_all_ce.json
python -m pharmasentinel train --model biomedbert --name biomedbert_therapeutic_ce --config configs/biomedbert_therapeutic_ce.json
python -m pharmasentinel train --model biomedbert --name biomedbert_therapeutic5_ce --config configs/biomedbert_therapeutic5_ce.json
python scripts/select_model.py --report v2_final_selection --names biomedbert biomedbert_trigger_ce biomedbert_all_ce biomedbert_therapeutic_ce biomedbert_therapeutic5_ce --output-name pharmasentinel_final
python scripts/repeat_seed.py
python scripts/predict_development.py --names pharmasentinel_final biomedbert_all_ce --device cuda
python scripts/development_results.py --names baseline biomedbert pharmasentinel_final biomedbert_all_ce
python scripts/development_error_examples.py --name pharmasentinel_final
python scripts/preflight.py --names baseline biomedbert pharmasentinel_final biomedbert_all_ce --report release_model_preflight
python scripts/verify_viewer.py
```

`select_model.py` records the full threshold grid and rejects choices that violate
the predeclared recall/minority safeguard. A new selected artifact includes the
threshold and its config hash. Calibration is refitted for its actual emitted
candidate population. The second training seed is a robustness check, not an
opportunity to replace the primary seed with a higher score.
The repeat script trains `precision_seed43`; `--report-only` uses an already trained
repeat without overwriting it. The precision-oriented mode is a separately declared
comparison that failed the conservative therapeutic-recall safeguard. Both are
retained so the tradeoff is visible.

## Freeze and final evaluation

Complete development choices and inspect diagnostics before running:

```powershell
python -m pharmasentinel freeze --names baseline biomedbert pharmasentinel_final biomedbert_all_ce
python scripts/final_evaluation.py --names baseline biomedbert pharmasentinel_final biomedbert_all_ce
python scripts/compare_models.py --first baseline --second pharmasentinel_final --split test
python scripts/compare_models.py --first biomedbert --second pharmasentinel_final --split test
python scripts/compare_models.py --first baseline --second biomedbert_all_ce --split test
python scripts/compare_models.py --first biomedbert --second biomedbert_all_ce --split test
python scripts/update_project_report.py
python scripts/plot_results.py
python -m pharmasentinel mysql-export --name pharmasentinel_final --split test
python -m streamlit run ui/app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

The freeze checks prepared-data identities, training-data identities, selected
weights and inference config. Final commands check the frozen code, all processed
subsets, model metadata, tokenizer, calibrator and policy. A final-test result is
reported as final; subsequent development cannot turn that test set into unseen
data again. Tests and hash checks reduce specific failure modes, not all possible
research error.

## What to show in an interview

1. Explain the complete-event target using a synthetic example and exact evidence.
2. Show the fixed splits and one explicitly quarantined annotation.
3. Compare baseline, original transformer and selected model on the same final set.
4. Explain precision, recall and rare-class tradeoffs in the ablation table.
5. Show review capture, random/candidate-count baselines, remaining errors and
   workload. These are oracle simulations, not measured time savings.
6. Demonstrate local extraction, structured outputs, charts and MySQL schema/queries.
   Live MySQL loading is optional and must be described as unverified until tested.

Raw passages, prediction examples, local SQL exports, credentials and weights stay
outside Git. Aggregate results, original synthetic diagnostics and reproducible
source code form the public project.
