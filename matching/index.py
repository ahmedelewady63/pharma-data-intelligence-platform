"""One-pass, deterministic index over contract-shaped RxNorm concepts."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from matching.normalize import fold_unicode
from matching.scoring import ALLOWED_TTYS, TTY_PRIORITY

_SPACE_RE = re.compile(r"\s+")
_NGRAM_SIZE = 3
_REQUIRED_COLUMNS = ("RXCUI", "SAB", "TTY", "STR", "SUPPRESS")
_RELATION_COLUMNS = ("RXCUI1", "REL", "RXCUI2", "RELA", "SAB")
_BRAND_RELATIONS = frozenset({"HAS_TRADENAME", "TRADENAME_OF"})


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


@dataclass(frozen=True, slots=True)
class BrandIngredientRelation:
    """One contract relation connecting a BN concept to an IN concept."""

    ingredient: RxNormConcept
    rxcui1: str
    rel: str | None
    rxcui2: str
    rela: str | None


class RxNormIndex:
    """Build picklable name and brand relation indexes from staging rows once."""

    def __init__(
        self,
        rows: Iterable[Mapping[str, object]],
        relations: Iterable[Mapping[str, object]] = (),
    ) -> None:
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
        by_first_char: dict[str, list[RxNormConcept]] = {}
        by_ngram: dict[str, list[RxNormConcept]] = {}
        for concept in self.concepts:
            key = strict_name_key(concept.str_text)
            compact = re.sub(r"[^A-Z0-9]", "", key)
            if compact:
                by_first_char.setdefault(compact[0], []).append(concept)
            for ngram in self._char_ngrams(compact):
                by_ngram.setdefault(ngram, []).append(concept)
        self.fuzzy_by_first_char = {
            key: tuple(values) for key, values in sorted(by_first_char.items())
        }
        self.fuzzy_by_ngram = {
            key: tuple(values) for key, values in sorted(by_ngram.items())
        }
        concepts_by_rxcui: dict[str, list[RxNormConcept]] = {}
        for concept in self.concepts:
            concepts_by_rxcui.setdefault(concept.rxcui, []).append(concept)

        brand_links: dict[str, list[BrandIngredientRelation]] = {}
        seen_relations: set[tuple[str, str, str, str]] = set()
        for row_number, row in enumerate(relations, start=1):
            missing = [column for column in _RELATION_COLUMNS if column not in row]
            if missing:
                raise ValueError(
                    f"RxNorm relation row {row_number} is missing contract columns: {missing}"
                )
            if str(row["SAB"]).strip().upper() != "RXNORM":
                continue

            rela_value = row["RELA"]
            rela = str(rela_value).strip().upper() if rela_value is not None else None
            if rela not in _BRAND_RELATIONS:
                continue

            rxcui1 = str(row["RXCUI1"]).strip()
            rxcui2 = str(row["RXCUI2"]).strip()
            rel_value = row["REL"]
            rel = str(rel_value).strip().upper() if rel_value is not None else None
            left = concepts_by_rxcui.get(rxcui1, ())
            right = concepts_by_rxcui.get(rxcui2, ())

            for left_concept in left:
                for right_concept in right:
                    if left_concept.tty == "BN" and right_concept.tty == "IN":
                        brand, ingredient = left_concept, right_concept
                    elif left_concept.tty == "IN" and right_concept.tty == "BN":
                        brand, ingredient = right_concept, left_concept
                    else:
                        continue

                    relation_key = (brand.rxcui, ingredient.rxcui, rela, rel or "")
                    if relation_key in seen_relations:
                        continue
                    seen_relations.add(relation_key)
                    brand_links.setdefault(brand.rxcui, []).append(
                        BrandIngredientRelation(
                            ingredient=ingredient,
                            rxcui1=rxcui1,
                            rel=rel,
                            rxcui2=rxcui2,
                            rela=rela,
                        )
                    )

        self.brand_to_ingredients = {
            rxcui: tuple(
                sorted(
                    links,
                    key=lambda link: (
                        link.ingredient.rxcui,
                        link.ingredient.str_text.casefold(),
                        link.ingredient.str_text,
                        link.rela or "",
                        link.rel or "",
                        link.rxcui1,
                        link.rxcui2,
                    ),
                )
            )
            for rxcui, links in sorted(brand_links.items())
        }

    @staticmethod
    def _char_ngrams(value: str) -> set[str]:
        if len(value) < _NGRAM_SIZE:
            return {value} if value else set()
        return {
            value[position : position + _NGRAM_SIZE]
            for position in range(len(value) - _NGRAM_SIZE + 1)
        }

    def lookup_exact(self, value: str | None) -> tuple[RxNormConcept, ...]:
        """Return eligible concepts whose strict name key exactly matches value."""
        key = strict_name_key(value)
        if not key:
            return ()
        return self.name_to_concepts.get(key, ())

    def lookup_fuzzy(self, value: str | None) -> tuple[RxNormConcept, ...]:
        """Return a deterministic blocking bucket from first character and trigrams."""
        key = strict_name_key(value)
        compact = re.sub(r"[^A-Z0-9]", "", key)
        if not compact:
            return ()

        bucket = set(self.fuzzy_by_first_char.get(compact[0], ()))
        for ngram in self._char_ngrams(compact):
            bucket.update(self.fuzzy_by_ngram.get(ngram, ()))

        min_length = max(1, int(len(compact) * 0.60))
        max_length = max(min_length, int(len(compact) / 0.60) + 1)
        filtered = [
            concept
            for concept in bucket
            if min_length
            <= len(re.sub(r"[^A-Z0-9]", "", strict_name_key(concept.str_text)))
            <= max_length
        ]
        return tuple(
            sorted(
                filtered,
                key=lambda concept: (
                    TTY_PRIORITY[concept.tty],
                    concept.rxcui,
                    concept.str_text.casefold(),
                    concept.str_text,
                ),
            )
        )
