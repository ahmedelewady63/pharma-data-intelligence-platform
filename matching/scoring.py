"""Named starting scores and stable priorities for exact RxNorm candidates.

Scores are starting defaults from the Member 2 design and must be evaluated on a
human-reviewed golden set before production thresholds are finalized.
"""

EXACT_PRODUCT_SCORE = 0.98
EXACT_INGREDIENT_SCORE = 0.95
EXACT_BRAND_SCORE = 0.90
FUZZY_MIN_RATIO = 78.0
FUZZY_SCORE_SCALE = 0.90
FUZZY_MAX_SCORE = 0.85

TTY_PRIORITY = {
    "IN": 0,
    "PIN": 1,
    "MIN": 2,
    "BN": 3,
    "SCD": 4,
    "SBD": 5,
}
ALLOWED_TTYS = frozenset(TTY_PRIORITY)

TTY_LEVEL = {
    "IN": "ingredient",
    "PIN": "ingredient",
    "MIN": "ingredient",
    "BN": "brand",
    "SCD": "product",
    "SBD": "product",
}
LEVEL_PRIORITY = {
    "product": 0,
    "ingredient": 1,
    "brand": 2,
}


def exact_score(tty: str) -> float:
    """Return the starting exact score for a supported RxNorm term type."""
    if tty in {"SCD", "SBD"}:
        return EXACT_PRODUCT_SCORE
    if tty in {"IN", "PIN", "MIN"}:
        return EXACT_INGREDIENT_SCORE
    if tty == "BN":
        return EXACT_BRAND_SCORE
    raise ValueError(f"Unsupported RxNorm TTY: {tty}")
