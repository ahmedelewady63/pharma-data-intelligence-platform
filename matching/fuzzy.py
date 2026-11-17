"""Fuzzy candidate generation over a pre-blocked RxNorm index."""

from __future__ import annotations

from rapidfuzz import fuzz, process

from matching.candidates import ExactCandidate
from matching.index import RxNormIndex, strict_name_key
from matching.scoring import (
    FUZZY_MAX_SCORE,
    FUZZY_MIN_RATIO,
    FUZZY_SCORE_SCALE,
    LEVEL_PRIORITY,
    TTY_LEVEL,
    TTY_PRIORITY,
)


def generate_fuzzy_candidates(
    value: str | None,
    index: RxNormIndex,
    *,
    min_ratio: float = FUZZY_MIN_RATIO,
) -> list[ExactCandidate]:
    """Return deterministic WRatio candidates from the index's reduced block."""
    key = strict_name_key(value)
    if not key or not 0 <= min_ratio <= 100:
        return []

    concepts = index.lookup_fuzzy(value)
    if not concepts:
        return []

    terms = [concept.str_text for concept in concepts]
    scored = process.extract(
        key,
        terms,
        scorer=fuzz.WRatio,
        processor=strict_name_key,
        score_cutoff=min_ratio,
        limit=None,
    )
    output: list[ExactCandidate] = []
    seen: set[tuple[str, str]] = set()
    for _term, ratio, position in scored:
        concept = concepts[position]
        identity = (concept.rxcui, concept.tty)
        if identity in seen:
            continue
        seen.add(identity)
        level = TTY_LEVEL[concept.tty]
        score = min(FUZZY_MAX_SCORE, ratio / 100 * FUZZY_SCORE_SCALE)
        output.append(
            ExactCandidate(
                rxcui=concept.rxcui,
                tty=concept.tty,
                str_text=concept.str_text,
                match_method="fuzzy",
                match_level=level,
                score=score,
                evidence=(
                    {
                        "step": 6,
                        "rule": "fuzzy_wratio",
                        "detail": (
                            f"WRatio={ratio:.1f} for normalized input {key!r} "
                            f"and RxNorm STR {concept.str_text!r}"
                        ),
                        "score": score,
                        "rxcui": concept.rxcui,
                        "level": level,
                    },
                ),
            )
        )

    return sorted(
        output,
        key=lambda candidate: (
            -candidate.score,
            LEVEL_PRIORITY[candidate.match_level],
            TTY_PRIORITY[candidate.tty],
            candidate.rxcui,
            candidate.str_text.casefold(),
            candidate.str_text,
        ),
    )
