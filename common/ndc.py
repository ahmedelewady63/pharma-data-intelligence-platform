"""Small helpers for preserving and matching US drug product NDC values."""

from __future__ import annotations

import re


def normalize_ndc11(value: object) -> str | None:
    """Return an NDC as 11 digits, or ``None`` when its format is invalid.

    Dashed FDA package codes are padded by segment (5-4-2). Unseparated
    10-digit NADAC values are padded on the left, and 11-digit values stay as-is.
    """
    if value is None:
        return None

    ndc = str(value).strip()
    if not ndc:
        return None

    if "-" in ndc:
        parts = ndc.split("-")
        valid_layouts = {(4, 4, 2), (5, 3, 2), (5, 4, 1), (5, 4, 2)}
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            return None
        if tuple(map(len, parts)) not in valid_layouts:
            return None
        return f"{parts[0].zfill(5)}{parts[1].zfill(4)}{parts[2].zfill(2)}"

    if re.fullmatch(r"[0-9]{10,11}", ndc):
        return ndc.zfill(11)

    return None
