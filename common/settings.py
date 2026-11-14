"""Path settings loaded from environment variables or a local .env file."""

from __future__ import annotations

import os
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _load_local_env() -> None:
    """Load simple KEY=VALUE entries from the repository .env without overriding the shell."""
    env_file = REPOSITORY_ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if not item or item.startswith("#") or "=" not in item:
            continue
        key, value = item.split("=", maxsplit=1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_data_dir() -> Path:
    """Return the configured data directory; it must be set outside the repository."""
    _load_local_env()
    raw_path = os.environ.get("DIR_DATA", "").strip()
    if not raw_path:
        raise RuntimeError("DIR_DATA is not set; configure it in .env or the environment.")
    path = Path(raw_path).expanduser().resolve()
    if path == REPOSITORY_ROOT or REPOSITORY_ROOT in path.parents:
        raise RuntimeError("DIR_DATA must be outside the repository.")
    return path


def data_path(*parts: str) -> Path:
    """Build a path beneath DIR_DATA."""
    return get_data_dir().joinpath(*parts)
