# Dataset card

## Sources used

1. **PHEE2 source files**, pinned to the revision in `configs/dataset.json`.
2. **Original synthetic diagnostic suite**, 10 development and 10 reserved examples.

No FDA reporting database, proprietary Optum data or unrelated GitHub profile projects are used.
Additional clinical corpora are outside this initial build.

## Task and units

Input: an English biomedical passage. Output: event type plus trigger, drug-role and effect-role
evidence span sets. Character offsets are half-open `[start, end)` Unicode code-point indices into
the immutable original context. Original nested mention and discontinuous-segment identifiers are
retained during adaptation. The model output does not fully reconstruct every original grouping.

## Size and allocation

| Subset | Passages | Purpose |
|---|---:|---|
| Train | 2,898 | Model fitting; any quarantined passages are excluded explicitly |
| Model selection | 487 | Early stopping and model choices |
| Calibration | 222 | Fit candidate correctness calibration |
| Policy | 252 | Select review method at a declared 25% budget |
| Test | 968 | Frozen final evaluation only |

The development subsets come from the original 961-record development file, split by shuffled
source-ID prefix groups using seed 42. Prefixes are a source-identity proxy, not an independently
verified guarantee of document independence. Original train/dev/test prefix overlap is zero.

## Observed quality issues

- All records have unique IDs; normalized exact texts do not cross the original splits.
- A lexical screen uses word-trigram Jaccard ≥0.9 for passages with at least eight distinct trigrams.
  Results are in `reports/data/near_duplicate_screen.json`; it does not detect all paraphrases.
- The `is_mult_event` flag disagrees with event-array multiplicity in 629 records. Its upstream
  meaning may differ; this project derives multiplicity from retained event arrays instead of
  assuming the flag is a reliable count.
- One effect annotation fails exact source-text validation (`10870095_7`). The passage is retained
  in prepared files with `annotation_status=quarantined` and excluded from training/scoring. No
  guessed whitespace correction or silent test-label repair is performed. Metrics disclose exclusions.
- Drug/effect roles can be empty and evidence can be discontinuous. Empty roles are not fabricated.
- BIO alignment limitations and collisions are logged for each training run. Difficult gold cases
  remain in evaluation; unsupported input outputs are counted as empty predictions with status flags.

## Interpretation limits

This is an event-enriched, passage-level research benchmark. Its medicine/effect frequencies are
sample counts, not exposure-adjusted incidence, causal risk or population prevalence. No chronological
trend analysis is justified by these files. A medicine text bundle is not a validated normalized drug ID.

The synthetic suite is small and deliberately schematic; held-out categories share constructions with
development examples. It detects obvious weaknesses but is not independent clinical validation.

The held-out split is held out from this project's supervised training and model
selection. Overlap between the pretrained encoder's original corpus and benchmark
source publications was not audited, so complete pretraining independence is not claimed.

## Reproducibility and rights

`source_manifest.json` records upstream URLs, immutable revision, Git blob identity and SHA-256.
`preparation_manifest.json` records splits, file hashes, exclusions and adaptation schema.
Dataset files and source-text exports remain local and are ignored by Git. Consult upstream source
terms for research and redistribution; the project's MIT license applies to original code, not all data.

