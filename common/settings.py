"""Paths and settings shared by every component. No hardcoded machine paths anywhere else."""

from __future__ import annotations

import os
from pathlib import Path

LAYERS = ("raw", "staging", "processed", "sample")


def data_dir() -> Path:
    """Root data folder. Set DATA_DIR in .env (outside the repo, outside OneDrive)."""
    return Path(os.environ.get("DATA_DIR", "data")).expanduser()


def layer_dir(layer: str) -> Path:
    if layer not in LAYERS:
        raise ValueError(f"unknown layer {layer!r}; expected one of {LAYERS}")
    return data_dir() / layer
