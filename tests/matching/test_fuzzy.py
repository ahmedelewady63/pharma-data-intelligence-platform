"""Tests for blocked fuzzy RxNorm candidate generation."""

import json

import pytest

from matching.fuzzy import generate_fuzzy_candidates
from matching.index import RxNormIndex


@pytest.fixture
def index():
    rows = [
        {"RXCUI": "1191", "SAB": "RXNORM", "TTY": "IN", "STR": "aspirin", "SUPPRESS": "N"},
        {"RXCUI": "723", "SAB": "RXNORM", "TTY": "IN", "STR": "amoxicillin", "SUPPRESS": "N"},
        {
            "RXCUI": "2001",
            "SAB": "RXNORM",
            "TTY": "SCD",
            "STR": "aspirin 325 MG Oral Tablet",
            "SUPPRESS": "N",
        },
        {"RXCUI": "3001", "SAB": "OTHER", "TTY": "IN", "STR": "asprin", "SUPPRESS": "N"},
    ]
    return RxNormIndex(rows)


def test_fuzzy_finds_typo_and_caps_score(index):
    candidates = generate_fuzzy_candidates("asprin", index)

    assert candidates
    assert candidates[0].rxcui == "1191"
    assert candidates[0].match_method == "fuzzy"
    assert candidates[0].score == pytest.approx(0.85)
    assert candidates[0].evidence[0]["rule"] == "fuzzy_wratio"
    assert json.dumps(candidates[0].evidence)


def test_fuzzy_is_deterministic_and_preserves_product_level(index):
    first = generate_fuzzy_candidates("aspirin 325 MG Oral Tabl", index)
    second = generate_fuzzy_candidates("aspirin 325 MG Oral Tabl", index)

    assert first == second
    assert any(
        candidate.rxcui == "2001" and candidate.match_level == "product" for candidate in first
    )


def test_fuzzy_threshold_is_configurable(index):
    assert generate_fuzzy_candidates("asprin", index, min_ratio=99) == []


def test_empty_and_invalid_inputs_return_no_candidates(index):
    assert generate_fuzzy_candidates(None, index) == []
    assert generate_fuzzy_candidates("", index) == []
    assert generate_fuzzy_candidates("asprin", index, min_ratio=-1) == []


def test_index_blocks_against_a_reduced_bucket():
    rows = [
        {
            "RXCUI": str(i),
            "SAB": "RXNORM",
            "TTY": "IN",
            "STR": f"unrelated compound {i}",
            "SUPPRESS": "N",
        }
        for i in range(100)
    ]
    rows.append({"RXCUI": "999", "SAB": "RXNORM", "TTY": "IN", "STR": "aspirin", "SUPPRESS": "N"})
    index = RxNormIndex(rows)

    assert len(index.lookup_fuzzy("asprin")) < len(index.concepts)
    assert any(item.rxcui == "999" for item in index.lookup_fuzzy("asprin"))
