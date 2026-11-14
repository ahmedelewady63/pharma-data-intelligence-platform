"""Shared NDC normalization."""

from __future__ import annotations

import re


def normalize_ndc11(value: str | None) -> str | None:
    """Normalize a package NDC or NADAC NDC to an 11-digit string.

    Hyphenated FDA package codes are padded by segment (4-4-2, 5-3-2, or
    5-4-1). Unhyphenated 10-digit NADAC values are left-padded. Leading zeros
    are preserved by returning text. Invalid non-empty values raise ValueError.
    """
    if value is None or not str(value).strip():
        return None

    text = str(value).strip()
    if re.fullmatch(r"\d{11}", text):
        return text
    if re.fullmatch(r"\d{10}", text):
        return text.zfill(11)

    pieces = text.split("-")
    if len(pieces) != 3 or not all(piece.isdigit() for piece in pieces):
        raise ValueError(f"Invalid NDC value: {value!r}")

    lengths = tuple(len(piece) for piece in pieces)
    padding = {
        (4, 4, 2): (1, 0, 0),
        (5, 3, 2): (0, 1, 0),
        (5, 4, 1): (0, 0, 1),
    }.get(lengths)
    if padding is None:
        raise ValueError(f"Unsupported hyphenated NDC layout: {value!r}")

    normalized = "".join(piece.zfill(len(piece) + pad) for piece, pad in zip(pieces, padding))
    if len(normalized) != 11:
        raise ValueError(f"Could not normalize NDC to 11 digits: {value!r}")
    return normalized
