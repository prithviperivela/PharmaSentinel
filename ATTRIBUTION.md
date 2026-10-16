# Research and source attribution

## PHEE

Sun, Zhaoyue, et al. **PHEE: A Dataset for Pharmacovigilance Event Extraction from Text.**
EMNLP 2022. [Paper](https://aclanthology.org/2022.emnlp-main.376/).

- Original repository: https://github.com/ZhaoyueSun/PHEE
- Revised source annotations used here: https://github.com/ZhaoyueSun/phee-with-chatgpt
- Associated later paper: Sun et al., **Leveraging ChatGPT in Pharmacovigilance
  Event Extraction: An Empirical Study**, EACL 2024.
  https://aclanthology.org/2024.eacl-short.30/
- Pinned revision: `a90c680b08464e731635eb2d2f2c49be6ad5e3e5`
- Files: `data/datasets/phee2/source/{train,dev,test}.json` (JSON Lines).
- Upstream annotation, dataset construction and research baselines belong to their authors.
  This project adapts the source annotations and implements a declared reduced extraction task.
- Generated augmentation and upstream training code are not copied into this implementation.
- The PHEE paper reports trigger and argument metrics separately. Our exact
  complete-event metric and reduced role schema are project-specific; its scores
  must not be presented as published PHEE benchmark scores.

Upstream repositories provide license files. A repository code license does not automatically
resolve every underlying publication's text rights. Raw/processed source passages and source-text
exports are excluded from this public repository; the fetch command obtains them from upstream.

## Biomedical pretrained encoder

Microsoft **BiomedBERT base, uncased, abstracts and full text** (formerly PubMedBERT):
https://huggingface.co/microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext

Gu et al., **Domain-Specific Language Model Pretraining for Biomedical Natural
Language Processing**. https://arxiv.org/abs/2007.15779

Pinned revision: `e1354b7a3a09615f6aba48dfad4b7a613eef7062`.
The downloaded license is recorded with the encoder manifest. Pretraining and weights are
Microsoft's contribution; this project's trigger and role heads and supervised fine-tuning
are separate. Weights are not committed to ordinary Git.

## Implementation references

- Hugging Face token classification: https://huggingface.co/docs/transformers/tasks/token_classification
- PyTorch: https://pytorch.org/docs/stable/
- scikit-learn probability calibration background: https://scikit-learn.org/stable/modules/calibration.html
- Guo et al., **On Calibration of Modern Neural Networks**, ICML 2017:
  https://arxiv.org/abs/1706.04599 . This motivates checking whether confidence
  reflects correctness. Our implementation fits a regularized logistic calibrator
  to emitted-candidate features, not the paper's temperature-scaling recipe.

Confidence calibration, BIO labeling, transformers and budget-based review evaluation are established
methods. The project claims an attributed student implementation and empirical analysis, not their invention.

Original synthetic challenge text is included under the project's code license. Its annotations are
self-authored language expectations rather than expert pharmacovigilance adjudication.

