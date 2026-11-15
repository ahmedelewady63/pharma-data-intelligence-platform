"""Tests for M2 name normalization.

ASSUMPTION: these fixtures are representative because M1 has not supplied FAERS samples.
Replace or supplement them after reviewing real values from stg_faers_drug.
"""

import pytest

from matching.normalize import (
    extract_form_route_hints,
    extract_strength,
    fold_unicode,
    is_noninformative,
    normalize_name,
    split_parenthetical,
    strip_dose,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ＡＳＰＩＲＩＮ", "ASPIRIN"),
        ("Café aspirin", "CAFE ASPIRIN"),
        ("ASPIRIN 81MG.", "ASPIRIN"),
        ("ACETAMINOPHEN 500 MG TABLETS", "ACETAMINOPHEN"),
        ("TYLENOL (ACETAMINOPHEN)", "TYLENOL ACETAMINOPHEN"),
        ("AMOXICILLIN 250 mg capsule oral", "AMOXICILLIN"),
        ("METFORMIN HYDROCHLORIDE 500 mg tablet", "METFORMIN HYDROCHLORIDE"),
        ("LISINOPRIL 10 MG USP", "LISINOPRIL"),
        ("Vitamin D3 1000 IU softgel", "VITAMIN D3"),
        ("Fluconazole 150-mg tablet", "FLUCONAZOLE"),
        ("ASPIRIN 0.5 g", "ASPIRIN"),
        ("Acetaminophen 325 mg PO tab", "ACETAMINOPHEN"),
        ("aspirin oral", "ASPIRIN"),
        ("AMOXICILLIN 500 mg/5 mL oral suspension", "AMOXICILLIN"),
        ("ASPIRIN...", "ASPIRIN"),
        ("  aspirin   81 mg  ", "ASPIRIN"),
        ("", ""),
        (None, ""),
        ("UNKNOWN", "UNKNOWN"),
        ("NOT SPECIFIED", "NOT SPECIFIED"),
        ("NOT REPORTED", "NOT REPORTED"),
        ("N/A", "N A"),
        ("UNSPECIFIED", "UNSPECIFIED"),
        ("VACCINE LOT ABC123", "VACCINE LOT ABC123"),
        ("TYLENOL EXTRA STRENGTH 500 MG", "TYLENOL EXTRA STRENGTH"),
    ],
)
def test_normalize_name_examples(value, expected):
    assert normalize_name(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ＡＳＰＩＲＩＮ", "ASPIRIN"),
        ("Café aspirin", "CAFE ASPIRIN"),
    ],
)
def test_fold_unicode(value, expected):
    assert fold_unicode(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ASPIRIN 81MG.", [("81", "MG")]),
        ("ASPIRIN 0.5 g", [("0.5", "G")]),
        ("AMOXICILLIN 500 mg/5 mL", [("500", "MG/5ML")]),
        ("Vitamin D3 1000 IU", [("1000", "IU")]),
        ("ASPIRIN", []),
        (None, []),
    ],
)
def test_extract_strength(value, expected):
    assert extract_strength(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "ACETAMINOPHEN 500 mg tablets oral",
            {"dosage_form": "TABLET", "route": "ORAL"},
        ),
        ("AMOXICILLIN capsule", {"dosage_form": "CAPSULE", "route": None}),
        ("ASPIRIN", {"dosage_form": None, "route": None}),
        ("Acetaminophen 325 mg PO tab", {"dosage_form": "TABLET", "route": "ORAL"}),
    ],
)
def test_extract_form_route_hints(value, expected):
    assert extract_form_route_hints(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("TYLENOL (ACETAMINOPHEN)", ("TYLENOL", "ACETAMINOPHEN")),
        (
            "Tylenol (Acetaminophen) 325 mg oral tablets",
            ("TYLENOL", "ACETAMINOPHEN"),
        ),
        ("ASPIRIN", None),
        ("TYLENOL ()", None),
    ],
)
def test_split_parenthetical(value, expected):
    assert split_parenthetical(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "UNKNOWN",
        "unknown",
        "NOT SPECIFIED",
        "NOT REPORTED",
        "N/A",
        "UNSPECIFIED",
        "VACCINE LOT ABC123",
        "LOT NUMBER 12345",
    ],
)
def test_noninformative_names(value):
    assert is_noninformative(value)


@pytest.mark.parametrize("value", ["ASPIRIN", "TYLENOL", "AMOXICILLIN"])
def test_informative_names(value):
    assert not is_noninformative(value)


def test_strength_removal_preserves_other_words():
    assert strip_dose("AMOXICILLIN 250 mg capsule oral") == "AMOXICILLIN CAPSULE ORAL"


def test_salt_spelling_is_preserved_without_an_approved_synonym():
    assert normalize_name("METFORMIN HYDROCHLORIDE 500 mg tablet") == ("METFORMIN HYDROCHLORIDE")
