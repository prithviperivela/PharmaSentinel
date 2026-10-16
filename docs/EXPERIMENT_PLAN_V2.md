# Controlled improvement and release plan

This plan was written before the v2 experiments or final test evaluation. The v1
artifacts remain intact. The final test is reserved until model and review choices
are frozen.

## Two primary measures

1. **Strict core-event micro F1**, with precision, recall, class breakdown and a
   source-group bootstrap interval. Exact type and all three evidence roles must
   match; missing and extra events count. This is the model-quality endpoint.
2. **Error capture at 25% passage review**, with lift over random review of the
   *same model*, residual errors, candidate/character workload and uncertainty.
   This is an oracle simulation of assistance value, not clinical impact or time
   saved. Compare residual absolute errors as well as capture: models with different
   error populations cannot be ranked by capture percentage alone.

Relaxed F1, role-level F1 and Brier scores explain results; they do not replace a
weak primary outcome. A candidate-prevalence constant is included for Brier context.
No metric or subset is selected simply because it produces a flattering score.

## Fixed experiment sequence

- Recheck GPU forward/backward and regression tests. Reuse pinned data and encoder.
- Sweep trigger-confidence acceptance on saved v1 model-selection predictions:
  thresholds 0, .5, .6, .7, .8, .85, .9 and .95. No test or policy labels enter this step.
- Train two controlled variants from the same pretrained encoder, seed 42, four
  epochs and the existing batch size/learning rate: (A) unweighted trigger loss,
  original square-root role weights; (B) unweighted trigger and role losses.
  Weighting rare BIO labels can improve recall but can also encourage extra spans.
  These ablations test that explanation; neither is assumed superior beforehand.
- Compare each selected checkpoint and the same threshold grid on model-selection
  data. Maximize strict F1 subject to retaining at least 90% of v1 strict recall and
  at least v1's number of correct therapeutic events. Break ties by higher recall,
  then lower threshold. Retain v1 if no eligible variant improves it.
  Preserving therapeutic true positives is a conservative development constraint,
  not a clinically validated utility function. A rejected candidate can still have
  higher minority-class F1 by trading recall for precision; report both quantities.
- Repeat the winning training configuration with seed 43 when feasible. Record
  variability; keep seed 42 as the primary run rather than cherry-picking the seed.
- Create a distinct selected artifact containing the chosen threshold. Checkpoint
  and inference configuration identities must follow every prediction. Verify that
  live inference and filtering cached predictions agree.
- Fit a new calibrator on the separate calibration subset. Choose the review policy
  on the policy subset; never use those scores to switch model architecture.
- Verify robustness on the existing synthetic development diagnostics, document
  failures, run the viewer and export analytics. MySQL remains optional.
- Freeze all model/data/code/calibration/policy identities, then evaluate the
  reserved test and synthetic challenge. Compare baseline, v1 and selected model
  on identical eligible passages. Do not retune after seeing the final scores.
- Publish source and aggregate reports only when GitHub write access works. Keep
  raw passages, weights and local credentials out of the repository.

## Interpretation

### Recorded development amendment after the first ablation

The unweighted-trigger run reached 39.4% model-selection F1, but therapeutic exact
matches fell from 15 to 9, failing the existing safeguard. Before seeing final-test
or new-model policy results, one additional variant is therefore declared:
unweighted role losses and trigger weights `[1, 1, 1, 3, 3]` for
`O, B-adverse, I-adverse, B-therapeutic, I-therapeutic`. This targets the observed
minority recall loss while retaining equal O/adverse weighting. The four-epoch
budget, seed 42, threshold grid, metrics and eligibility rules remain unchanged.
This is an adaptive development hypothesis, not an initially preregistered result.
All tried variants are retained in the comparison, including failed safeguards.

The multiplier-3 run subsequently achieved 42.2% F1 and 14 therapeutic true positives,
still one below the fixed threshold of 15. A final multiplier-5 run is declared on
the same development subset with the same four-epoch budget and all other settings
fixed. This ends the loss-weight search for this release. No threshold or safeguard
is loosened. The conservative interim artifact `pharmasentinel_v2` and its selection
report remain preserved; the release candidate uses `pharmasentinel_final` and
`v2_final_selection.json` so that no experiment is overwritten.

### Final scope fixed before held-out evaluation

The multiplier-5 run reached 40.4% model-selection F1 with 13 therapeutic true
positives. None of the new training recipes passed the preserved-therapeutic-TP
constraint. `pharmasentinel_final` therefore retains the original weights and the
eligible 0.5 trigger threshold. This is the **conservative mode**, not a claim that
it maximizes overall F1.

The unweighted `biomedbert_all_ce` checkpoint is also frozen and evaluated as a
separately labelled **precision-oriented mode**: 42.7% development F1, 44.7%
precision, 41.0% overall recall, but 10/69 therapeutic events recovered exactly
versus the original 15/69. It is the best unfiltered development-F1 loss variant;
its threshold remains 0. It is not silently promoted past the failed safeguard.
The final comparison contains baseline, original transformer, conservative mode
and this precision-oriented mode. Each has separate calibration and review-policy
selection. No mode is switched based on final-test scores. A seed-43 repeat checks
the precision-oriented recipe; seed 42 remains its evaluated release checkpoint.

Before final-test access, the repeat returned 41.8% model-selection F1 versus
42.7% for seed 42; therapeutic exact matches were 14 versus 10. This is a two-seed
descriptive check, not a confidence interval over training randomness. The separate
policy subset selected raw-confidence review for precision mode and the additive
expected-incorrect-candidate policy for conservative mode. These policy choices
are frozen separately; the same policy need not win for different models.

### Reporting standard

A 35–40% development F1 is an aspiration, not an acceptance criterion or forecast.
The result may be better or worse. A valuable student contribution can be a measured
improvement plus a reproducible account of remaining errors. Neither a strong
review-ranking score nor perfect offset validity establishes clinical readiness.
