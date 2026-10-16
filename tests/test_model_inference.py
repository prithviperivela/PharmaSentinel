import copy

import torch

torch.set_num_threads(2)

from pharmasentinel.baseline import BaselinePredictor, BiLSTM
from pharmasentinel.labeling import tokenize


def test_baseline_inference_is_independent_of_gold_annotations(example):
    torch.manual_seed(42)
    vocabulary = {"<PAD>": 0, "<UNK>": 1}
    vocabulary.update(
        {w: i + 2 for i, w in enumerate(sorted(set(tokenize(example["context"])[0])))}
    )
    config = {
        "embedding_dim": 8,
        "hidden_dim": 8,
        "dropout": 0.0,
        "batch_size": 2,
        "max_tokens": 100,
    }
    predictor = BaselinePredictor(BiLSTM(len(vocabulary), config), vocabulary, config)
    unlabeled = copy.deepcopy(example)
    unlabeled["events"] = []
    a = predictor.predict([example])[0]
    b = predictor.predict([unlabeled])[0]
    assert a["events"] == b["events"]


def test_unsupported_length_is_explicit(example):
    config = {
        "embedding_dim": 8,
        "hidden_dim": 8,
        "dropout": 0.0,
        "batch_size": 2,
        "max_tokens": 1,
    }
    predictor = BaselinePredictor(BiLSTM(2, config), {"<PAD>": 0, "<UNK>": 1}, config)
    result = predictor.predict([example])[0]
    assert result["status"] == "unsupported_length"
    assert result["events"] == []


def test_biomedical_heads_backpropagate_without_remote_weights():
    from transformers import BertConfig, BertModel
    from pharmasentinel.biomedical import BiomedicalExtractor

    encoder = BertModel(
        BertConfig(
            vocab_size=24,
            hidden_size=16,
            num_hidden_layers=1,
            num_attention_heads=2,
            intermediate_size=32,
        )
    )
    model = BiomedicalExtractor(encoder, dropout=0)
    ids = torch.tensor([[2, 5, 6, 7, 3]])
    hidden, trigger = model(input_ids=ids, attention_mask=torch.ones_like(ids))
    roles = model.role_logits(
        hidden, torch.tensor([[False, False, True, False, False]])
    )
    loss = trigger.sum() + sum(value.sum() for value in roles.values())
    loss.backward()
    assert trigger.shape == (1, 5, 5)
    assert all(value.shape == (1, 5, 3) for value in roles.values())
    assert model.encoder.embeddings.word_embeddings.weight.grad is not None
    assert model.drug_head.weight.grad is not None
