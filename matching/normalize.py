"""Pure normalization and attribute extraction for free-text drug names.

The synonym table is intentionally small and versioned. It standardizes spelling only;
it does not claim that different drug products are clinically interchangeable.
"""

from __future__ import annotations

import re
import unicodedata

SYNONYM_MAP_VERSION = "1"

_NAME_SYNONYMS = {
    "HYDROCHLORIDE": "HCL",
}

_STRENGTH_UNIT = r"MCG|UG|MG|KG|G|GRAMS?|ML|L|IU|MEQ|MMOL|UNITS?|UNIT|%"
_STRENGTH_RE = re.compile(
    rf"(?<![A-Z0-9])"
    rf"(?P<value>\d+(?:[.,]\d+)?)\s*[- ]?\s*"
    rf"(?P<unit>{_STRENGTH_UNIT})"
    rf"(?:\s*/\s*(?P<per_value>\d+(?:[.,]\d+)?)\s*[- ]?\s*"
    rf"(?P<per_unit>{_STRENGTH_UNIT}))?"
    rf"(?![A-Z0-9])",
    re.IGNORECASE,
)

_FORM_TOKENS = (
    ("TABLETS", "TABLET"),
    ("TABLET", "TABLET"),
    ("TABS", "TABLET"),
    ("TAB", "TABLET"),
    ("CAPSULES", "CAPSULE"),
    ("CAPSULE", "CAPSULE"),
    ("CAPS", "CAPSULE"),
    ("CAP", "CAPSULE"),
    ("SOFTGEL", "SOFTGEL"),
    ("SUSPENSION", "SUSPENSION"),
    ("SUSP", "SUSPENSION"),
    ("SOLUTION", "SOLUTION"),
    ("SYRUP", "SYRUP"),
    ("INJECTION", "INJECTION"),
    ("INJECTABLE", "INJECTION"),
    ("CREAM", "CREAM"),
    ("OINTMENT", "OINTMENT"),
    ("GEL", "GEL"),
    ("DROPS", "DROPS"),
    ("SUPPOSITORY", "SUPPOSITORY"),
    ("PATCH", "PATCH"),
)

_ROUTE_TOKENS = (
    ("ORAL", "ORAL"),
    ("PO", "ORAL"),
    ("INTRAVENOUS", "INTRAVENOUS"),
    ("IV", "INTRAVENOUS"),
    ("INTRAMUSCULAR", "INTRAMUSCULAR"),
    ("IM", "INTRAMUSCULAR"),
    ("TOPICAL", "TOPICAL"),
    ("SUBCUTANEOUS", "SUBCUTANEOUS"),
    ("SC", "SUBCUTANEOUS"),
    ("OPHTHALMIC", "OPHTHALMIC"),
    ("OTIC", "OTIC"),
    ("NASAL", "NASAL"),
    ("INHALATION", "INHALATION"),
    ("RECTAL", "RECTAL"),
    ("VAGINAL", "VAGINAL"),
)

_NOISE_TOKENS = {
    "TABLET",
    "TABLETS",
    "TAB",
    "TABS",
    "CAPSULE",
    "CAPSULES",
    "CAP",
    "CAPS",
    "SOFTGEL",
    "SUSPENSION",
    "SUSP",
    "SOLUTION",
    "SYRUP",
    "INJECTION",
    "INJECTABLE",
    "CREAM",
    "OINTMENT",
    "GEL",
    "DROPS",
    "SUPPOSITORY",
    "PATCH",
    "ORAL",
    "PO",
    "INTRAVENOUS",
    "IV",
    "INTRAMUSCULAR",
    "IM",
    "TOPICAL",
    "SUBCUTANEOUS",
    "SC",
    "OPHTHALMIC",
    "OTIC",
    "NASAL",
    "INHALATION",
    "RECTAL",
    "VAGINAL",
    "USP",
}

_NONINFORMATIVE_NAMES = {
    "",
    "UNKNOWN",
    "UNK",
    "NOT SPECIFIED",
    "NOT REPORTED",
    "NOT AVAILABLE",
    "UNSPECIFIED",
    "N A",
    "NA",
    "NONE",
    "NULL",
    "NO NAME",
    "NO NAME AVAILABLE",
}

_PARENTHESES_RE = re.compile(r"^\s*(.*?)\s*\(([^()]*)\)\s*$")
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")
_MULTI_SPACE_RE = re.compile(r"\s+")


def fold_unicode(value: str | None) -> str:
    """Fold compatible Unicode characters to ASCII and uppercase the result."""
    if value is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    return decomposed.encode("ascii", errors="ignore").decode("ascii").upper()


def extract_strength(value: str | None) -> list[tuple[str, str]]:
    """Return strength values and units, preserving concentration ratios.

    A concentration such as 500 mg/5 mL is returned as (500, MG/5ML).
    """
    text = fold_unicode(value)
    strengths: list[tuple[str, str]] = []
    for match in _STRENGTH_RE.finditer(text):
        numeric_value = match.group("value").replace(",", ".")
        unit = match.group("unit").upper()
        per_value = match.group("per_value")
        per_unit = match.group("per_unit")
        if per_value and per_unit:
            unit = f"{unit}/{per_value.replace(',', '.')} {per_unit.upper()}"
        strengths.append((numeric_value, unit.replace(" ", "")))
    return strengths


def strip_dose(value: str | None) -> str:
    """Remove recognized strength expressions while leaving other name text intact."""
    text = fold_unicode(value)
    without_strength = _STRENGTH_RE.sub(" ", text)
    without_loose_separators = re.sub(r"(?<![A-Z0-9])[./-]+(?![A-Z0-9])", " ", without_strength)
    return _MULTI_SPACE_RE.sub(" ", without_loose_separators).strip()


def _remove_noise_tokens(text: str) -> str:
    """Remove dosage-form, route, and pharmacopeia tokens from a matching name."""
    for token in sorted(_NOISE_TOKENS, key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(token)}\b", " ", text)
    return _MULTI_SPACE_RE.sub(" ", text).strip()


def extract_form_route_hints(value: str | None) -> dict[str, str | None]:
    """Extract the first recognized dosage form and route in stable token order."""
    text = fold_unicode(value)

    def first_hint(tokens: tuple[tuple[str, str], ...]) -> str | None:
        for token, canonical in tokens:
            if re.search(rf"\b{re.escape(token)}\b", text):
                return canonical
        return None

    return {
        "dosage_form": first_hint(_FORM_TOKENS),
        "route": first_hint(_ROUTE_TOKENS),
    }


def normalize_name(value: str | None) -> str:
    """Create a matching key without recognized dose, form, route, or punctuation noise."""
    text = _remove_noise_tokens(strip_dose(value))
    for source, replacement in _NAME_SYNONYMS.items():
        text = re.sub(rf"\b{re.escape(source)}\b", replacement, text)
    return _MULTI_SPACE_RE.sub(" ", _NON_ALNUM_RE.sub(" ", text)).strip()


def split_parenthetical(value: str | None) -> tuple[str, str] | None:
    """Return normalized text before and inside one parenthetical expression."""
    text = _remove_noise_tokens(strip_dose(value)).strip(" .,-")
    match = _PARENTHESES_RE.fullmatch(text)
    if not match:
        return None

    leading = normalize_name(match.group(1))
    parenthetical = normalize_name(match.group(2))
    if not leading or not parenthetical:
        return None
    return leading, parenthetical


def is_noninformative(value: str | None) -> bool:
    """Identify empty placeholders and vaccine lot text that must not be fuzzy-matched."""
    text = fold_unicode(value).strip()
    if not text:
        return True
    if re.match(r"^(?:VACCINE\s+)?LOT\b", text):
        return True

    canonical = normalize_name(text)
    return canonical in _NONINFORMATIVE_NAMES
