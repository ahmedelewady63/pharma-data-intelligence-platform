"""Tests for RxNorm exact candidate indexing.

ASSUMPTION: these synthetic rows mirror the approved staging contract shape. Real
RxNorm rows are checked locally and are not committed to this public repository.
"""

import json
import pickle
from collections.abc import Iterator

import pytest

from matching.candidates import generate_exact_candidates
from matching.index import RxNormIndex


@pytest.fixture
def rxnorm_rows():
    return [
        {"RXCUI": "1001", "SAB": "RXNORM", "TTY": "IN", "STR": "Alpha Ingredient", "SUPPRESS": "N"},
        {
            "RXCUI": "1002",
            "SAB": "RXNORM",
            "TTY": "PIN",
            "STR": "Alpha Ingredient",
            "SUPPRESS": "N",
        },
        {"RXCUI": "1003", "SAB": "RXNORM", "TTY": "MIN", "STR": "Alpha + Beta", "SUPPRESS": "N"},
        {"RXCUI": "1004", "SAB": "RXNORM", "TTY": "BN", "STR": "Example Brand", "SUPPRESS": "N"},
        {
            "RXCUI": "1005",
            "SAB": "RXNORM",
            "TTY": "SCD",
            "STR": "Example Product 500 MG Oral Tablet",
            "SUPPRESS": "N",
        },
        {
            "RXCUI": "1006",
            "SAB": "RXNORM",
            "TTY": "SBD",
            "STR": "Example Product 500 MG Oral Tablet [Example Brand]",
            "SUPPRESS": "N",
        },
        {"RXCUI": "1010", "SAB": "RXNORM", "TTY": "IN", "STR": "Tie Name", "SUPPRESS": "N"},
        {"RXCUI": "1009", "SAB": "RXNORM", "TTY": "IN", "STR": "Tie Name", "SUPPRESS": "N"},
        {"RXCUI": "1008", "SAB": "RXNORM", "TTY": "PIN", "STR": "Tie Name", "SUPPRESS": "N"},
        {"RXCUI": "1011", "SAB": "RXNORM", "TTY": "IN", "STR": "Suppressed Name", "SUPPRESS": "Y"},
        {"RXCUI": "1012", "SAB": "OTHER", "TTY": "IN", "STR": "Other Source", "SUPPRESS": "N"},
        {"RXCUI": "1013", "SAB": "RXNORM", "TTY": "PSN", "STR": "Not Supported", "SUPPRESS": "N"},
        {"RXCUI": "1014", "SAB": "RXNORM", "TTY": "IN", "STR": "Unknown Status", "SUPPRESS": None},
        {"RXCUI": "1015", "SAB": "RXNORM", "TTY": "BN", "STR": "No Status", "SUPPRESS": ""},
    ]


def test_exact_lookup_supports_all_contract_ttys(rxnorm_rows):
    index = RxNormIndex(rxnorm_rows)
    assert {concept.tty for concept in index.concepts} == {
        "IN",
        "PIN",
        "MIN",
        "BN",
        "SCD",
        "SBD",
    }


def test_exact_candidates_fold_case_and_whitespace_but_keep_term_details(rxnorm_rows):
    index = RxNormIndex(rxnorm_rows)
    candidates = generate_exact_candidates("  alpha\tINGREDIENT ", index)

    assert [(candidate.rxcui, candidate.tty) for candidate in candidates] == [
        ("1001", "IN"),
        ("1002", "PIN"),
    ]
    assert all(candidate.score == 0.95 for candidate in candidates)


def test_exact_product_match_keeps_strength_form_and_route(rxnorm_rows):
    index = RxNormIndex(rxnorm_rows)
    exact = generate_exact_candidates("Example Product 500 mg Oral Tablet", index)
    partial = generate_exact_candidates("Example Product", index)

    assert [(candidate.rxcui, candidate.tty) for candidate in exact] == [("1005", "SCD")]
    assert partial == []


def test_brand_hit_is_not_silently_promoted_to_ingredient(rxnorm_rows):
    index = RxNormIndex(rxnorm_rows)
    candidates = generate_exact_candidates("Example Brand", index)

    assert len(candidates) == 1
    assert candidates[0].match_level == "brand"
    assert candidates[0].score == 0.90
    assert "relation not inferred" in candidates[0].evidence[0]["detail"]


def test_tie_breaking_uses_tty_priority_then_rxcui(rxnorm_rows):
    index = RxNormIndex(rxnorm_rows)
    candidates = generate_exact_candidates("Tie Name", index)

    assert [(candidate.rxcui, candidate.tty) for candidate in candidates] == [
        ("1009", "IN"),
        ("1010", "IN"),
        ("1008", "PIN"),
    ]


def test_non_rxnorm_suppressed_and_unsupported_rows_are_not_indexed(rxnorm_rows):
    index = RxNormIndex(rxnorm_rows)

    assert index.lookup_exact("Suppressed Name") == ()
    assert index.lookup_exact("Other Source") == ()
    assert index.lookup_exact("Not Supported") == ()
    assert index.lookup_exact("Unknown Status") == ()
    assert index.lookup_exact("No Status") == ()


class OnePassRows:
    """Iterable that fails if the constructor tries to build the index twice."""

    def __init__(self, rows):
        self.rows = rows
        self.iterations = 0

    def __iter__(self) -> Iterator[dict[str, str]]:
        self.iterations += 1
        if self.iterations > 1:
            raise AssertionError("RxNorm rows were iterated more than once")
        yield from self.rows


def test_index_consumes_reference_rows_once(rxnorm_rows):
    rows = OnePassRows(rxnorm_rows)
    index = RxNormIndex(rows)

    for _ in range(3):
        generate_exact_candidates("Alpha Ingredient", index)

    assert rows.iterations == 1


def test_index_and_candidates_are_picklable(rxnorm_rows):
    index = pickle.loads(pickle.dumps(RxNormIndex(rxnorm_rows)))
    candidates = generate_exact_candidates("Example Brand", index)

    assert json.dumps(candidates[0].evidence)
    assert candidates[0].rxcui == "1004"


@pytest.mark.parametrize(
    "row",
    [
        {"SAB": "RXNORM", "TTY": "IN", "STR": "Missing CUI", "SUPPRESS": "N"},
        {"RXCUI": "2001", "SAB": "RXNORM", "TTY": "IN", "SUPPRESS": "N"},
    ],
)
def test_missing_contract_columns_raise(row):
    with pytest.raises(ValueError, match="missing contract columns"):
        RxNormIndex([row])
