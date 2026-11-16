"""Tests for brand-to-ingredient relation lookup.

ASSUMPTION: these synthetic rows mirror the contract and the observed RXNREL
directions. Real RxNorm source rows are not committed to this public repository.
"""

import json

from matching.candidates import generate_brand_candidates
from matching.index import RxNormIndex


def _concept(rxcui: str, tty: str, term: str) -> dict[str, str]:
    return {
        "RXCUI": rxcui,
        "SAB": "RXNORM",
        "TTY": tty,
        "STR": term,
        "SUPPRESS": "N",
    }


def _relation(rxcui1: str, rel: str, rxcui2: str, rela: str) -> dict[str, str]:
    return {
        "RXCUI1": rxcui1,
        "REL": rel,
        "RXCUI2": rxcui2,
        "RELA": rela,
        "SAB": "RXNORM",
    }


def _index() -> RxNormIndex:
    concepts = [
        _concept("38", "BN", "Parlodel"),
        _concept("1760", "IN", "bromocriptine"),
        _concept("218330", "BN", "Mesnex"),
        _concept("44", "IN", "mesna"),
        _concept("3000", "BN", "Combination Brand"),
        _concept("5001", "IN", "ingredient alpha"),
        _concept("5002", "IN", "ingredient beta"),
    ]
    relations = [
        _relation("38", "RB", "1760", "has_tradename"),
        _relation("44", "RN", "218330", "tradename_of"),
        _relation("5001", "RN", "3000", "tradename_of"),
        _relation("3000", "RB", "5002", "has_tradename"),
        _relation("38", "RO", "44", "unrelated"),
        {
            **_relation("38", "RB", "44", "has_tradename"),
            "SAB": "OTHER",
        },
    ]
    return RxNormIndex(concepts, relations)


def test_brand_relation_supports_brand_on_rxcui1():
    candidates = generate_brand_candidates("Parlodel", _index())

    assert [(item.rxcui, item.str_text) for item in candidates] == [("1760", "bromocriptine")]
    assert candidates[0].match_method == "brand_to_ingredient"
    assert candidates[0].match_level == "ingredient"
    assert candidates[0].score == 0.90
    assert "BN RXCUI1=38 -> IN RXCUI2=1760" in candidates[0].evidence[1]["detail"]
    assert json.dumps(candidates[0].evidence)


def test_brand_relation_supports_brand_on_rxcui2():
    candidates = generate_brand_candidates("Mesnex", _index())

    assert [(item.rxcui, item.str_text) for item in candidates] == [("44", "mesna")]
    assert "IN RXCUI1=44 -> BN RXCUI2=218330" in candidates[0].evidence[1]["detail"]


def test_brand_with_multiple_ingredients_returns_all_ordered_candidates():
    candidates = generate_brand_candidates("Combination Brand", _index())

    assert [(item.rxcui, item.str_text) for item in candidates] == [
        ("5001", "ingredient alpha"),
        ("5002", "ingredient beta"),
    ]
    assert all(item.score == 0.90 for item in candidates)


def test_brand_without_related_ingredient_returns_no_candidates():
    assert generate_brand_candidates("Unknown Brand", _index()) == []
