"""Verified flat encoder download, avoiding Windows symlink/long-path issues."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from .data import git_blob
from .io import read_json, sha256, write_json


def download_encoder(root, repository, revision):
    directory = Path(root) / "data/cache/biomedbert"
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(root) / "reports/data/encoder_manifest.json"
    if manifest_path.exists():
        cached = read_json(manifest_path)
        if (
            cached.get("repository") == repository
            and cached.get("revision") == revision
        ):
            files = cached.get("files", {})
            weights = (
                "model.safetensors"
                if "model.safetensors" in files
                else "pytorch_model.bin"
            )
            if "config.json" in files and "vocab.txt" in files and weights in files:
                for name, identity in files.items():
                    if Path(name).name != name:
                        raise ValueError(
                            "Encoder manifest contains an invalid filename"
                        )
                    path = directory / name
                    if (
                        not path.is_file()
                        or path.stat().st_size != identity["bytes"]
                        or sha256(path) != identity["sha256"]
                    ):
                        raise ValueError(
                            f"Cached encoder integrity check failed: {name}"
                        )
                print(
                    "Reusing encoder verified against the saved upstream manifest",
                    flush=True,
                )
                return directory, weights.endswith(".safetensors")
    request = urllib.request.Request(
        f"https://huggingface.co/api/models/{repository}/revision/{revision}?blobs=true",
        headers={"User-Agent": "PharmaSentinel/0.1"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        metadata = json.load(response)
    if metadata["sha"] != revision:
        raise ValueError("Encoder revision mismatch")
    entries = {item["rfilename"]: item for item in metadata["siblings"]}
    weights = (
        "model.safetensors" if "model.safetensors" in entries else "pytorch_model.bin"
    )
    names = [
        name
        for name in (
            "config.json",
            "tokenizer_config.json",
            "tokenizer.json",
            "special_tokens_map.json",
            "vocab.txt",
            "LICENSE.md",
            weights,
        )
        if name in entries
    ]
    manifest = {"repository": repository, "revision": revision, "files": {}}
    for name in names:
        destination, entry = directory / name, entries[name]

        def verified():
            if not destination.exists() or destination.stat().st_size != entry["size"]:
                return False
            if entry.get("lfs"):
                return sha256(destination) == entry["lfs"]["sha256"]
            return git_blob(destination.read_bytes()) == entry["blobId"]

        if not verified():
            url = f"https://huggingface.co/{repository}/resolve/{revision}/{name}"
            request = urllib.request.Request(
                url, headers={"User-Agent": "PharmaSentinel/0.1"}
            )
            part = directory / (name + ".part")
            print(f"Downloading {name} ({entry['size']:,} bytes)", flush=True)
            with (
                urllib.request.urlopen(request, timeout=120) as response,
                part.open("wb") as handle,
            ):
                received, last = 0, 0
                while chunk := response.read(1024 * 1024):
                    handle.write(chunk)
                    received += len(chunk)
                    if received - last >= 64 * 1024 * 1024:
                        print(f"  {name}: {received / 1024**2:.0f} MiB", flush=True)
                        last = received
            part.replace(destination)
            if not verified():
                raise ValueError(
                    f"Encoder file failed upstream integrity check: {name}"
                )
        manifest["files"][name] = {
            "bytes": destination.stat().st_size,
            "sha256": sha256(destination),
            "upstream_blob": entry["blobId"],
        }
    write_json(Path(root) / "reports/data/encoder_manifest.json", manifest)
    return directory, weights.endswith(".safetensors")
