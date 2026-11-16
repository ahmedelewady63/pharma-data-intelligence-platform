"""Exact-name candidate generation for RxNorm concepts."""

from __future__ import annotations

from dataclasses import dataclass

from matching.index import RxNormIndex, strict_name_key
from matching.scoring import (
    EXACT_BRAND_SCORE,
    LEVEL_PRIORITY,
    TTY_LEVEL,
    TTY_PRIORITY,
    exact_score,
)


@dataclass(frozen=True, slots=True)
class ExactCandidate:
    """One exact RxNorm candidate with score and JSON-compatible evidence."""

    rxcui: str
    tty: str
    str_text: str
    match_method: str
    match_level: str
    score: float
    evidence: tuple[dict[str, object], ...]


def generate_exact_candidates(value: str | None, index: RxNormIndex) -> list[ExactCandidate]:
    """Return every strict RxNorm STR match in deterministic tie-break order.

    Strength, dosage-form, route, and punctuation details are retained by the strict
    key. A BN hit remains brand-level; no ingredient relation is inferred here.
    """
    key = strict_name_key(value)
    if not key:
        return []

    candidates: list[ExactCandidate] = []
    for concept in index.lookup_exact(value):
        score = exact_score(concept.tty)
        level = TTY_LEVEL[concept.tty]
        detail = f"strict name key {key!r} exactly matches RxNorm STR (TTY={concept.tty})"
        if level == "brand":
            detail += "; brand-to-ingredient relation not inferred"

        candidates.append(
            ExactCandidate(
                rxcui=concept.rxcui,
                tty=concept.tty,
                str_text=concept.str_text,
                match_method="exact",
                match_level=level,
                score=score,
                evidence=(
                    {
                        "step": 1,
                        "rule": "exact_name",
                        "detail": detail,
                        "score": score,
                        "rxcui": concept.rxcui,
                        "level": level,
                    },
                ),
            )
        )

    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.score,
            LEVEL_PRIORITY[candidate.match_level],
            TTY_PRIORITY[candidate.tty],
            candidate.rxcui,
            candidate.str_text.casefold(),
            candidate.str_text,
        ),
    )


def generate_brand_candidates(value: str | None, index: RxNormIndex) -> list[ExactCandidate]:
    """Map an exact BN term to linked IN concepts with relation evidence.

    The endpoint TTYs identify the brand and ingredient roles because real RxNorm
    rows can place them on either RXCUI1 or RXCUI2.
    """
    candidates: list[ExactCandidate] = []
    for brand in index.lookup_exact(value):
        if brand.tty != "BN":
            continue

        for link in index.brand_to_ingredients.get(brand.rxcui, ()):
            if link.rxcui1 == brand.rxcui:
                orientation = f"BN RXCUI1={link.rxcui1} -> IN RXCUI2={link.rxcui2}"
            else:
                orientation = f"IN RXCUI1={link.rxcui1} -> BN RXCUI2={link.rxcui2}"

            rela = link.rela or "unspecified"
            rel = link.rel or "unspecified"
            candidates.append(
                ExactCandidate(
                    rxcui=link.ingredient.rxcui,
                    tty=link.ingredient.tty,
                    str_text=link.ingredient.str_text,
                    match_method="brand_to_ingredient",
                    match_level="ingredient",
                    score=EXACT_BRAND_SCORE,
                    evidence=(
                        {
                            "step": 1,
                            "rule": "exact_brand_name",
                            "detail": (
                                f"strict name key {strict_name_key(value)!r} "
                                f"exactly matches RxNorm BN {brand.str_text!r}"
                            ),
                            "score": EXACT_BRAND_SCORE,
                            "rxcui": brand.rxcui,
                            "level": "brand",
                        },
                        {
                            "step": 2,
                            "rule": "brand_to_ingredient_relation",
                            "detail": (
                                f"{orientation}; RELA={rela}, REL={rel}; "
                                f"ingredient={link.ingredient.str_text!r}"
                            ),
                            "score": EXACT_BRAND_SCORE,
                            "rxcui": link.ingredient.rxcui,
                            "level": "ingredient",
                        },
                    ),
                )
            )

    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.score,
            LEVEL_PRIORITY[candidate.match_level],
            TTY_PRIORITY[candidate.tty],
            candidate.rxcui,
            candidate.str_text.casefold(),
            candidate.str_text,
        ),
    )
