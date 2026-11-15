"""Deterministic splitting of multi-ingredient drug-name fields.

ASSUMPTION: the supported separators indicate ingredient boundaries. Ingredient spelling,
salts, and qualifiers are preserved. Validate separator behavior against M1 samples.
"""

from __future__ import annotations

import re

_INGREDIENT_SEPARATOR_RE = re.compile(r"[\\/;+]|\bAND\b", re.IGNORECASE)


def split_ingredients(text: str | None) -> list[str]:
    """Split ingredient text, preserving first-seen order and spelling.

    Supported separators are backslash, slash, semicolon, plus, and the standalone
    word AND. Empty pieces are ignored. Duplicate pieces are removed case-insensitively.
    """
    if text is None:
        return []

    seen: set[str] = set()
    ingredients: list[str] = []

    for piece in _INGREDIENT_SEPARATOR_RE.split(text):
        ingredient = piece.strip()
        if not ingredient:
            continue

        key = ingredient.casefold()
        if key in seen:
            continue

        seen.add(key)
        ingredients.append(ingredient)

    return ingredients
