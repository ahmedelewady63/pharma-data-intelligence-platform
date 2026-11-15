"""One-pass, deterministic index over contract-shaped RxNorm concepts."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from matching.normalize import fold_unicode
from matching.scoring import ALLOWED_TTYS, TTY_PRIORITY

_SPACE_RE = re.compile(r"\s+")
_REQUIRED_COLUMNS = ("RXCUI", "SAB", "TTY", "STR", "SUPPRESS")


@dataclass(frozen=True, slots=True)
class RxNormConcept:
    """The fields needed by the M2 exact candidate generator."""

    rxcui: str
    sab: str
    tty: str
    str_text: str
    suppress: str | None


def strict_name_key(value: str | None) -> str:
    """Case/Unicode-fold and collapse whitespace without stripping product detail."""
    if value is None:
        return ""
    return _SPACE_RE.sub(" ", fold_unicode(value)).strip()


class RxNormIndex:
    """Build a picklable exact-name index from stg_rxnorm_concept rows once."""

    def __init__(self, rows: Iterable[Mapping[str, object]]) -> None:
        by_name: dict[str, list[RxNormConcept]] = {}
        concepts: list[RxNormConcept] = []
        seen: set[tuple[str, str, str]] = set()

        for row_number, row in enumerate(rows, start=1):
            missing = [column for column in _REQUIRED_COLUMNS if column not in row]
            if missing:
                raise ValueError(f"RxNorm row {row_number} is missing contract columns: {missing}")

            rxcui = str(row["RXCUI"]).strip()
            sab = str(row["SAB"]).strip().upper()
            tty = str(row["TTY"]).strip().upper()
            str_text = str(row["STR"]).strip()
            suppress_value = row["SUPPRESS"]
            suppress = str(suppress_value).strip().upper() if suppress_value is not None else None

            if not rxcui or not str_text:
                raise ValueError(f"RxNorm row {row_number} has an empty RXCUI or STR")
            if sab != "RXNORM" or tty not in ALLOWED_TTYS or suppress != "N":
                continue

            dedupe_key = (rxcui, tty, str_text)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            concept = RxNormConcept(
                rxcui=rxcui,
                sab=sab,
                tty=tty,
                str_text=str_text,
                suppress=suppress,
            )
            key = strict_name_key(str_text)
            if not key:
                continue
            concepts.append(concept)
            by_name.setdefault(key, []).append(concept)

        self.name_to_concepts = {
            key: tuple(
                sorted(
                    values,
                    key=lambda concept: (
                        TTY_PRIORITY[concept.tty],
                        concept.rxcui,
                        concept.str_text.casefold(),
                        concept.str_text,
                    ),
                )
            )
            for key, values in sorted(by_name.items())
        }
        self.concepts = tuple(
            sorted(
                concepts,
                key=lambda concept: (
                    TTY_PRIORITY[concept.tty],
                    concept.rxcui,
                    concept.str_text.casefold(),
                    concept.str_text,
                ),
            )
        )

    def lookup_exact(self, value: str | None) -> tuple[RxNormConcept, ...]:
        """Return eligible concepts whose strict name key exactly matches value."""
        key = strict_name_key(value)
        if not key:
            return ()
        return self.name_to_concepts.get(key, ())
