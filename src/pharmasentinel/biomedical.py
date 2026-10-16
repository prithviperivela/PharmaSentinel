"""Shared biomedical encoder: typed triggers and trigger-conditioned roles."""

from __future__ import annotations

import json
import time
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from transformers import AutoConfig, AutoModel, AutoTokenizer

from .baseline import seed_everything
from .data import load_split
from .evaluation import evaluate
from .encoder_source import download_encoder
from .io import environment, read_json, sha256, write_json, write_jsonl
from .labeling import bio_labels, decode_bio, event_from_parts, trigger_labels
from .inference import attach_provenance
from .integrity import require_new_run


class BiomedicalExtractor(nn.Module):
    def __init__(self, encoder, dropout=0.1):
        super().__init__()
        self.encoder = encoder
        size = encoder.config.hidden_size
        self.dropout = nn.Dropout(dropout)
        self.trigger_head = nn.Linear(size, 5)
        self.drug_head = nn.Linear(size * 2, 3)
        self.effect_head = nn.Linear(size * 2, 3)

    def forward(self, **inputs):
        hidden = self.encoder(**inputs).last_hidden_state
        return hidden, self.trigger_head(self.dropout(hidden))

    def role_logits(self, hidden, trigger_mask):
        mask = trigger_mask.to(hidden.dtype).unsqueeze(-1)
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp_min(1)
        conditioned = torch.cat(
            [hidden, pooled.unsqueeze(1).expand(-1, hidden.shape[1], -1)], dim=-1
        )
        conditioned = self.dropout(conditioned)
        return {
            "drug": self.drug_head(conditioned),
            "effect": self.effect_head(conditioned),
        }


def trigger_mask(offsets, segments):
    return np.array(
        [
            any(b > a and a < s["end"] and b > s["start"] for s in segments)
            for a, b in offsets
        ],
        dtype=bool,
    )


class BiomedicalPredictor:
    def __init__(self, model, tokenizer, config, device="cpu"):
        self.model, self.tokenizer, self.config, self.device = (
            model.to(device),
            tokenizer,
            config,
            device,
        )
        self.model.eval()

    @classmethod
    def load(cls, directory, device="cpu"):
        directory = Path(directory)
        config = read_json(directory / "config.json")
        encoder_config = AutoConfig.from_pretrained(
            directory / "encoder_config", local_files_only=True
        )
        encoder_config._attn_implementation = "eager"
        encoder = AutoModel.from_config(encoder_config)
        model = BiomedicalExtractor(encoder, config["dropout"])
        model.load_state_dict(
            torch.load(directory / "model.pt", map_location=device, weights_only=True)
        )
        tokenizer = AutoTokenizer.from_pretrained(
            directory / "tokenizer", use_fast=True, local_files_only=True
        )
        torch.set_num_threads(config.get("threads", 4))
        return cls(model, tokenizer, config, device)

    def predict(self, rows, batch_size=None):
        self.model.eval()
        output = []
        batch_size = batch_size or self.config["batch_size"]
        for begin in range(0, len(rows), batch_size):
            supported = []
            for row in rows[begin : begin + batch_size]:
                encoding = self.tokenizer(
                    row["context"], return_offsets_mapping=True, truncation=False
                )
                if (
                    not row["context"].strip()
                    or len(encoding["input_ids"]) > self.config["max_tokens"]
                ):
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
                    supported.append((row, encoding))
            if not supported:
                continue
            offsets = [enc["offset_mapping"] for _, enc in supported]
            inputs = self.tokenizer.pad(
                [
                    {k: v for k, v in enc.items() if k != "offset_mapping"}
                    for _, enc in supported
                ],
                padding=True,
                return_tensors="pt",
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            start = time.perf_counter()
            with torch.inference_mode():
                hidden, logits = self.model(**inputs)
                trigger_probs = logits.softmax(-1).cpu().numpy()
                for i, (row, encoding) in enumerate(supported):
                    n = len(offsets[i])
                    triggers = decode_bio(
                        trigger_probs[i, :n].argmax(-1),
                        trigger_probs[i, :n],
                        offsets[i],
                        row["context"],
                        trigger=True,
                    )
                    events = []
                    for trigger in triggers:
                        mask = torch.tensor(
                            trigger_mask(offsets[i], [trigger["span"]]),
                            device=self.device,
                        ).unsqueeze(0)
                        roles = self.model.role_logits(hidden[i : i + 1, :n], mask)
                        parts = {}
                        for role, value in roles.items():
                            probs = value[0].softmax(-1).cpu().numpy()
                            parts[role] = decode_bio(
                                probs.argmax(-1), probs, offsets[i], row["context"]
                            )
                        events.append(
                            event_from_parts(trigger, parts["drug"], parts["effect"])
                        )
                    output.append(
                        {
                            "id": row["id"],
                            "events": events,
                            "status": "ok",
                            "flags": ["no_event_extracted"] if not events else [],
                            "latency_ms": None,
                        }
                    )
            elapsed = (time.perf_counter() - start) * 1000 / len(supported)
            for prediction in output[-len(supported) :]:
                prediction["latency_ms"] = elapsed
        from .selection import filter_triggers

        return filter_triggers(output, self.config.get("trigger_threshold", 0.0))


def prepare_example(row, tokenizer, max_tokens):
    encoding = tokenizer(row["context"], return_offsets_mapping=True, truncation=False)
    offsets = encoding.pop("offset_mapping")
    if len(encoding["input_ids"]) > max_tokens:
        return None, {"unsupported_length": 1}
    trigger, issues = trigger_labels(offsets, row["events"])
    roles = []
    for event in row["events"]:
        mask = trigger_mask(offsets, event["trigger"])
        if not mask.any():
            issues["unrepresented_trigger"] = issues.get("unrepresented_trigger", 0) + 1
            continue
        target = {"mask": mask}
        for role in ("drug", "effect"):
            target[role], problem = bio_labels(offsets, event[role])
            for key, value in problem.items():
                issues[key] = issues.get(key, 0) + value
        roles.append(target)
    return {"encoding": encoding, "trigger": trigger, "roles": roles}, issues


def train(root, config_path=None, name="biomedbert", limit=None):
    root = Path(root)
    directory = require_new_run(root, name)
    if limit is not None and limit <= 0:
        raise ValueError("Training --limit must be positive")
    config = read_json(config_path or root / "configs/biomedbert.json")
    seed_everything(config["seed"], config.get("threads", 4))
    if not config.get("encoder_revision"):
        request = urllib.request.Request(
            f"https://huggingface.co/api/models/{config['encoder']}",
            headers={"User-Agent": "PharmaSentinel/0.1"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            config["encoder_revision"] = json.load(response)["sha"]
    print(
        f"Loading pinned encoder {config['encoder']} @ {config['encoder_revision']}",
        flush=True,
    )
    local_encoder, use_safetensors = download_encoder(
        root, config["encoder"], config["encoder_revision"]
    )
    tokenizer = AutoTokenizer.from_pretrained(
        local_encoder, use_fast=True, local_files_only=True, trust_remote_code=False
    )
    encoder = AutoModel.from_pretrained(
        local_encoder,
        local_files_only=True,
        trust_remote_code=False,
        attn_implementation="eager",
        use_safetensors=use_safetensors,
        weights_only=True,
    )
    model = BiomedicalExtractor(encoder, config["dropout"])
    if config.get("freeze_encoder"):
        for parameter in model.encoder.parameters():
            parameter.requires_grad = False
    device = config.get("device", "cpu")
    model.to(device)
    rows = [
        r
        for r in load_split(root, "train")
        if r.get("annotation_status") != "quarantined"
    ]
    if limit:
        rows = rows[:limit]
    examples, issues, skipped = [], Counter(), []
    for row in rows:
        example, problem = prepare_example(row, tokenizer, config["max_tokens"])
        issues.update(problem)
        if example is None:
            skipped.append(row["id"])
        else:
            examples.append(example)
    if not examples:
        raise ValueError("No supported training examples")
    role_counts = {
        role: np.ones(size)
        for role, size in [("trigger", 5), ("drug", 3), ("effect", 3)]
    }
    for example in examples:
        labels = example["trigger"]
        role_counts["trigger"] += np.bincount(labels[labels >= 0], minlength=5)
        for target in example["roles"]:
            for role in ("drug", "effect"):
                labels = target[role]
                role_counts[role] += np.bincount(labels[labels >= 0], minlength=3)
    losses = {}
    for role, counts in role_counts.items():
        exponent = config.get("class_weight_exponents", {}).get(role, 0.5)
        if not 0 <= exponent <= 1:
            raise ValueError("Class-weight exponents must be in [0, 1]")
        weights = (counts.sum() / counts) ** exponent
        multipliers = np.asarray(
            config.get("class_weight_multipliers", {}).get(role, np.ones(len(counts))),
            dtype=float,
        )
        if (
            multipliers.shape != counts.shape
            or not np.isfinite(multipliers).all()
            or (multipliers <= 0).any()
        ):
            raise ValueError(
                "Class-weight multipliers must be finite, positive and match the label count"
            )
        weights *= multipliers
        weights /= weights.mean()
        losses[role] = nn.CrossEntropyLoss(
            weight=torch.tensor(weights, dtype=torch.float32, device=device),
            ignore_index=-100,
        )
    optimizer = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad), lr=config["learning_rate"]
    )
    loader = DataLoader(
        examples,
        batch_size=config["batch_size"],
        shuffle=True,
        collate_fn=lambda batch: batch,
        num_workers=0,
    )
    validation = load_split(root, "model_selection")
    directory.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(directory / "tokenizer")
    model.encoder.config.save_pretrained(directory / "encoder_config")
    write_json(directory / "config.json", config)
    best, stale, history = (-1.0, -1.0), 0, []
    started = time.perf_counter()
    for epoch in range(1, config["epochs"] + 1):
        model.train()
        if config.get("freeze_encoder"):
            model.encoder.eval()
        total = 0.0
        for step, batch in enumerate(loader, 1):
            inputs = tokenizer.pad(
                [e["encoding"] for e in batch], padding=True, return_tensors="pt"
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}
            length = inputs["input_ids"].shape[1]
            trigger = torch.full(
                (len(batch), length), -100, dtype=torch.long, device=device
            )
            for i, example in enumerate(batch):
                trigger[i, : len(example["trigger"])] = torch.tensor(
                    example["trigger"], device=device
                )
            optimizer.zero_grad(set_to_none=True)
            hidden, logits = model(**inputs)
            trigger_loss = losses["trigger"](logits.reshape(-1, 5), trigger.reshape(-1))
            per_document = []
            for i, example in enumerate(batch):
                event_losses = []
                n = len(example["trigger"])
                for target in example["roles"]:
                    mask = torch.tensor(target["mask"], device=device).unsqueeze(0)
                    roles = model.role_logits(hidden[i : i + 1, :n], mask)
                    event_losses.append(
                        sum(
                            losses[r](
                                roles[r].reshape(-1, 3),
                                torch.tensor(target[r], device=device),
                            )
                            for r in roles
                        )
                        / 2
                    )
                if event_losses:
                    per_document.append(torch.stack(event_losses).mean())
            loss = (
                (trigger_loss + torch.stack(per_document).mean()) / 2
                if per_document
                else trigger_loss
            )
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total += float(loss.detach())
            if step % 100 == 0:
                print(
                    {
                        "epoch": epoch,
                        "batch": step,
                        "batches": len(loader),
                        "mean_loss": total / step,
                    },
                    flush=True,
                )
        predictor = BiomedicalPredictor(model, tokenizer, config, device)
        report, _ = evaluate(validation, predictor.predict(validation), bootstrap=0)
        selection = (
            report["strict_event"]["f1"],
            sum(x["f1"] for x in report["evidence_segments"].values()) / 3,
        )
        record = {
            "epoch": epoch,
            "training_loss": total / len(loader),
            "selection_event_f1": selection[0],
            "selection_mean_segment_f1": selection[1],
        }
        history.append(record)
        print(record, flush=True)
        if selection > best:
            best, stale = selection, 0
            torch.save(
                {k: v.detach().cpu() for k, v in model.state_dict().items()},
                directory / "model.pt",
            )
        else:
            stale += 1
        if stale >= config["patience"]:
            break
    model.load_state_dict(
        torch.load(directory / "model.pt", map_location=device, weights_only=True)
    )
    metadata = {
        "model_type": "biomedbert",
        "run_name": name,
        "encoder": config["encoder"],
        "encoder_revision": config["encoder_revision"],
        "freeze_encoder": config.get("freeze_encoder", False),
        "training_limit": limit,
        "training_examples": len(examples),
        "unsupported_training_ids": skipped,
        "alignment_diagnostics": dict(issues),
        "history": history,
        "best_selection": list(best),
        "training_seconds": time.perf_counter() - started,
        "environment": environment(),
        "data_hashes": read_json(root / "reports/data/preparation_manifest.json")[
            "file_hashes"
        ],
        "weights_sha256": sha256(directory / "model.pt"),
        "config_sha256": sha256(directory / "config.json"),
        "test_evaluated": False,
        "architecture": "shared encoder; typed trigger BIO head; trigger-pooled representation concatenated to token states for separate drug/effect BIO heads",
        "limitation": "Gold triggers condition role training; predicted triggers condition inference. Fine-grained entity grouping and overlapping same-role spans remain limitations.",
    }
    write_json(directory / "metadata.json", metadata)
    write_json(root / "reports/experiments" / f"{name}_training.json", metadata)
    predictor = BiomedicalPredictor(model, tokenizer, config, device)
    for split in config.get(
        "prediction_splits", ["model_selection", "calibration", "policy"]
    ):
        selected_rows = load_split(root, split)
        write_jsonl(
            root / "reports/predictions" / f"{name}_{split}.jsonl",
            attach_provenance(
                predictor.predict(selected_rows), selected_rows, metadata
            ),
        )
    return metadata
