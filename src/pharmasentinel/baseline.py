"""CPU-friendly BiLSTM baseline with independent evidence heads."""

from __future__ import annotations

import copy
import random
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from .data import load_split
from .evaluation import evaluate
from .io import environment, read_json, sha256, write_json, write_jsonl
from .labeling import (
    bio_labels,
    decode_bio,
    nearest_trigger_events,
    tokenize,
    trigger_labels,
)
from .inference import attach_provenance
from .integrity import require_new_run


def seed_everything(seed, threads=4):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(threads)
    # CPU is the reproducibility default; do not probe a user's GPU driver here.


class BiLSTM(nn.Module):
    def __init__(self, vocabulary_size, config):
        super().__init__()
        self.embedding = nn.Embedding(
            vocabulary_size, config["embedding_dim"], padding_idx=0
        )
        self.encoder = nn.LSTM(
            config["embedding_dim"],
            config["hidden_dim"],
            batch_first=True,
            bidirectional=True,
        )
        self.dropout = nn.Dropout(config["dropout"])
        self.heads = nn.ModuleDict(
            {
                name: nn.Linear(config["hidden_dim"] * 2, size)
                for name, size in [("trigger", 5), ("drug", 3), ("effect", 3)]
            }
        )

    def forward(self, ids, lengths):
        packed = nn.utils.rnn.pack_padded_sequence(
            self.embedding(ids), lengths.cpu(), batch_first=True, enforce_sorted=False
        )
        encoded, _ = self.encoder(packed)
        hidden, _ = nn.utils.rnn.pad_packed_sequence(
            encoded, batch_first=True, total_length=ids.shape[1]
        )
        return {name: head(self.dropout(hidden)) for name, head in self.heads.items()}


def collate(batch):
    length = max(len(item["ids"]) for item in batch)
    ids = torch.zeros((len(batch), length), dtype=torch.long)
    labels = {
        r: torch.full((len(batch), length), -100, dtype=torch.long)
        for r in ("trigger", "drug", "effect")
    }
    for i, item in enumerate(batch):
        n = len(item["ids"])
        ids[i, :n] = torch.tensor(item["ids"])
        for role in labels:
            labels[role][i, :n] = torch.tensor(item[role])
    return ids, torch.tensor([len(item["ids"]) for item in batch]), labels


class BaselinePredictor:
    def __init__(self, model, vocabulary, config, device="cpu"):
        self.model, self.vocabulary, self.config = model.to(device), vocabulary, config
        self.device = device
        self.model.eval()

    @classmethod
    def load(cls, directory, device="cpu"):
        directory = Path(directory)
        config, vocabulary = (
            read_json(directory / "config.json"),
            read_json(directory / "vocabulary.json"),
        )
        model = BiLSTM(len(vocabulary), config)
        model.load_state_dict(
            torch.load(directory / "model.pt", map_location=device, weights_only=True)
        )
        torch.set_num_threads(config.get("threads", 4))
        return cls(model, vocabulary, config, device)

    def predict(self, rows, batch_size=None):
        output = []
        batch_size = batch_size or self.config["batch_size"]
        self.model.eval()
        for begin in range(0, len(rows), batch_size):
            batch_rows = rows[begin : begin + batch_size]
            supported = []
            for row in batch_rows:
                words, offsets = tokenize(row["context"])
                if not words or len(words) > self.config["max_tokens"]:
                    output.append(
                        {
                            "id": row["id"],
                            "events": [],
                            "status": "unsupported_length",
                            "flags": ["unsupported_length"],
                            "latency_ms": None,
                        }
                    )
                else:
                    supported.append((row, words, offsets))
            if not supported:
                continue
            lengths = torch.tensor([len(words) for _, words, _ in supported])
            ids = torch.zeros((len(supported), int(lengths.max())), dtype=torch.long)
            for i, (_, words, _) in enumerate(supported):
                ids[i, : len(words)] = torch.tensor(
                    [self.vocabulary.get(w, 1) for w in words]
                )
            start = time.perf_counter()
            with torch.inference_mode():
                logits = self.model(ids.to(self.device), lengths)
                probabilities = {
                    key: value.softmax(-1).cpu().numpy()
                    for key, value in logits.items()
                }
            elapsed = (time.perf_counter() - start) * 1000 / len(supported)
            for i, (row, words, offsets) in enumerate(supported):
                parts = {
                    role: decode_bio(
                        probabilities[role][i, : len(words)].argmax(-1),
                        probabilities[role][i, : len(words)],
                        offsets,
                        row["context"],
                        trigger=role == "trigger",
                    )
                    for role in probabilities
                }
                events = nearest_trigger_events(
                    parts["trigger"], parts["drug"], parts["effect"]
                )
                output.append(
                    {
                        "id": row["id"],
                        "events": events,
                        "status": "ok",
                        "flags": ["no_event_extracted"] if not events else [],
                        "latency_ms": elapsed,
                    }
                )
        return output


def train(root, config_path=None, name="baseline", limit=None):
    root = Path(root)
    directory = require_new_run(root, name)
    if limit is not None and limit <= 0:
        raise ValueError("Training --limit must be positive")
    config = read_json(config_path or root / "configs/baseline.json")
    seed_everything(config["seed"], config.get("threads", 4))
    rows = [
        r
        for r in load_split(root, "train")
        if r.get("annotation_status") != "quarantined"
    ]
    if limit:
        rows = rows[:limit]
    counts = Counter(word for row in rows for word in tokenize(row["context"])[0])
    vocabulary = {"<PAD>": 0, "<UNK>": 1}
    vocabulary.update(
        {
            word: i + 2
            for i, word in enumerate(
                sorted(w for w, n in counts.items() if n >= config["min_frequency"])
            )
        }
    )
    examples, skipped, alignment = [], [], Counter()
    for row in rows:
        words, offsets = tokenize(row["context"])
        if not words or len(words) > config["max_tokens"]:
            skipped.append(row["id"])
            continue
        trigger, problem = trigger_labels(offsets, row["events"])
        alignment.update(problem)
        example = {"ids": [vocabulary.get(w, 1) for w in words], "trigger": trigger}
        for role in ("drug", "effect"):
            example[role], problem = bio_labels(
                offsets, [s for e in row["events"] for s in e[role]]
            )
            alignment.update(problem)
        examples.append(example)
    if not examples:
        raise ValueError("No supported training examples")
    device = config.get("device", "cpu")
    model = BiLSTM(len(vocabulary), config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"])
    losses = {}
    for role, n in [("trigger", 5), ("drug", 3), ("effect", 3)]:
        c = np.ones(n)
        for example in examples:
            c += np.bincount(example[role][example[role] >= 0], minlength=n)
        weights = np.sqrt(c.sum() / c)
        weights /= weights.mean()
        losses[role] = nn.CrossEntropyLoss(
            weight=torch.tensor(weights, dtype=torch.float32, device=device),
            ignore_index=-100,
        )
    loader = DataLoader(
        examples,
        batch_size=config["batch_size"],
        shuffle=True,
        collate_fn=collate,
        num_workers=0,
    )
    validation = load_split(root, "model_selection")
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "config.json", config)
    write_json(directory / "vocabulary.json", vocabulary)
    best, state, stale, history = (-1.0, -1.0), None, 0, []
    start = time.perf_counter()
    for epoch in range(1, config["epochs"] + 1):
        model.train()
        total = 0.0
        for ids, lengths, labels in loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(ids.to(device), lengths)
            loss = (
                sum(
                    losses[r](
                        logits[r].reshape(-1, logits[r].shape[-1]),
                        labels[r].to(device).reshape(-1),
                    )
                    for r in labels
                )
                / 3
            )
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total += float(loss.detach())
        predictions = BaselinePredictor(model, vocabulary, config, device).predict(
            validation
        )
        report, _ = evaluate(validation, predictions, bootstrap=0)
        segment_f1 = sum(v["f1"] for v in report["evidence_segments"].values()) / 3
        selection = (report["strict_event"]["f1"], segment_f1)
        record = {
            "epoch": epoch,
            "training_loss": total / len(loader),
            "selection_event_f1": selection[0],
            "selection_mean_segment_f1": selection[1],
        }
        history.append(record)
        print(record, flush=True)
        if selection > best:
            best, state, stale = (
                selection,
                copy.deepcopy({k: v.cpu() for k, v in model.state_dict().items()}),
                0,
            )
        else:
            stale += 1
        if stale >= config["patience"]:
            break
    model.load_state_dict(state)
    torch.save(state, directory / "model.pt")
    preparation = read_json(root / "reports/data/preparation_manifest.json")
    metadata = {
        "model_type": "bilstm",
        "run_name": name,
        "scope": "reduced event schema",
        "training_examples": len(examples),
        "training_limit": limit,
        "unsupported_training_ids": skipped,
        "quarantined_training_passages": sum(
            r.get("annotation_status") == "quarantined"
            for r in load_split(root, "train")
        ),
        "alignment_diagnostics": dict(alignment),
        "selection_rule": "maximize strict core-event F1, break ties by mean segment F1",
        "history": history,
        "best_selection": list(best),
        "training_seconds": time.perf_counter() - start,
        "data_hashes": preparation["file_hashes"],
        "environment": environment(),
        "weights_sha256": sha256(directory / "model.pt"),
        "test_evaluated": False,
    }
    write_json(directory / "metadata.json", metadata)
    write_json(root / "reports/experiments" / f"{name}_training.json", metadata)
    predictor = BaselinePredictor(model, vocabulary, config, device)
    for split in ("model_selection", "calibration", "policy"):
        selected_rows = load_split(root, split)
        write_jsonl(
            root / "reports/predictions" / f"{name}_{split}.jsonl",
            attach_provenance(
                predictor.predict(selected_rows), selected_rows, metadata
            ),
        )
    return metadata
