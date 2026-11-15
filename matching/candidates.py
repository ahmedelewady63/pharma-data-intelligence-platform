"""Exact-name candidate generation for RxNorm concepts."""

from __future__ import annotations

from dataclasses import dataclass

from matching.index import RxNormConcept, RxNormIndex, strict_name_key
from matching.scoring import LEVEL_PRIORITY, TTY_LEVEL, TTY_PRIORITY, exact_score


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


def generate_exact_candidates(
    value: str | None, index: RxNormIndex
) -> list[ExactCandidate]:
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
        detail = (
            f"strict name key {key!r} exactly matches RxNorm STR "
            f"(TTY={concept.tty})"
        )
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
