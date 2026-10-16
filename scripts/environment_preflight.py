"""Verify the intended runtime, real gradients, cache and temporary-file access."""

import argparse
import tempfile
from pathlib import Path

import torch

from pharmasentinel.encoder_source import download_encoder
from pharmasentinel.io import environment, read_json, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(
            "Requested CUDA device is unavailable; choose CPU explicitly"
        )
    tensor = torch.randn(8, 8, device=args.device, requires_grad=True)
    tensor.square().mean().backward()
    assert tensor.grad.isfinite().all()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "roundtrip.txt"
        path.write_text("preflight", encoding="utf-8")
        assert path.read_text(encoding="utf-8") == "preflight"
    config = read_json(root / "configs/biomedbert_gpu.json")
    download_encoder(root, config["encoder"], config["encoder_revision"])
    result = {
        "environment": environment(),
        "device": args.device,
        "device_name": torch.cuda.get_device_name(0)
        if args.device == "cuda"
        else "CPU",
        "gradient_check": "passed",
        "temporary_file_roundtrip": "passed",
        "encoder_integrity": "passed",
        "system_site_packages_inherited": __import__("sys").base_prefix
        != __import__("sys").prefix
        and "include-system-site-packages = true"
        in (Path(__import__("sys").prefix) / "pyvenv.cfg").read_text().lower(),
    }
    write_json(root / "reports/verification/environment_preflight.json", result)
    print(result)


if __name__ == "__main__":
    main()
