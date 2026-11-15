"""Tests for splitting multi-ingredient strings.

ASSUMPTION: representative fixtures are temporary until M1 provides real staging samples.
"""

import pytest

from matching.ingredients import split_ingredients


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("amoxicillin + clavulanic acid", ["amoxicillin", "clavulanic acid"]),
        ("amoxicillin/clavulanic acid", ["amoxicillin", "clavulanic acid"]),
        ("sulfamethoxazole AND trimethoprim", ["sulfamethoxazole", "trimethoprim"]),
        ("aspirin; caffeine", ["aspirin", "caffeine"]),
        ("acetaminophen \ codeine", ["acetaminophen", "codeine"]),
        (
            "amoxicillin trihydrate + clavulanate potassium",
            ["amoxicillin trihydrate", "clavulanate potassium"],
        ),
        ("levodopa + carbidopa + entacapone", ["levodopa", "carbidopa", "entacapone"]),
        ("hydrocodone bitartrate / acetaminophen", ["hydrocodone bitartrate", "acetaminophen"]),
        ("lisinopril AND hydrochlorothiazide", ["lisinopril", "hydrochlorothiazide"]),
        (
            "metformin hydrochloride + sitagliptin phosphate",
            ["metformin hydrochloride", "sitagliptin phosphate"],
        ),
        ("Drug A + Drug B + Drug A", ["Drug A", "Drug B"]),
        ("  amlodipine  +  valsartan  ", ["amlodipine", "valsartan"]),
        ("A + B; C / D AND E", ["A", "B", "C", "D", "E"]),
        ("", []),
        ("ibuprofen", ["ibuprofen"]),
        (None, []),
    ],
)
def test_split_ingredients(value, expected):
    assert split_ingredients(value) == expected


def test_split_ingredients_deduplicates_case_insensitively_and_keeps_first_spelling():
    assert split_ingredients("Aspirin + ASPIRIN + caffeine") == ["Aspirin", "caffeine"]


def test_split_ingredients_ignores_empty_pieces_between_separators():
    assert split_ingredients("A + / ; B") == ["A", "B"]


def test_and_is_case_insensitive_and_does_not_match_inside_words():
    assert split_ingredients("one and two") == ["one", "two"]
    assert split_ingredients("candy + medicine") == ["candy", "medicine"]


def test_salts_and_qualifiers_are_preserved():
    assert split_ingredients("amoxicillin trihydrate + clavulanate potassium") == [
        "amoxicillin trihydrate",
        "clavulanate potassium",
    ]
