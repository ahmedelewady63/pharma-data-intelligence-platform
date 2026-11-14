"""Deterministic splitting of multi-ingredient drug-name fields.

ASSUMPTION: the input is a single ingredient field (such as FAERS prod_ai or
Egyptian name_scientific), and the listed separators indicate ingredient boundaries.
Ingredient spelling, salts, and qualifiers are preserved as supplied.
"""

from __future__ import annotations

import re

_INGREDIENT_SEPARATOR_RE = re.compile(r"\\|/|;|\+|\s+AND\s+", re.IGNORECASE)


def split_ingredients(text: str) -> list[str]:
    """Split an ingredient string while preserving first-seen order and spelling.

    Separators are backslash, slash, semicolon, plus, and the standalone word AND.
    Empty pieces are ignored. Duplicate pieces are removed case-insensitively.
    """
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
