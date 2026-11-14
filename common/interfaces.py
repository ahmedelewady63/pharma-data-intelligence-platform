"""Stable interfaces shared by matching, validation, and streaming components."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol


@dataclass(frozen=True)
class MatchResult:
    """One explainable drug match returned by the matcher."""

    record_id: str
    status: str
    rxcui: str | None
    match_method: str
    confidence: float
    evidence: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    match_level: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation finding."""

    rule_id: str
    field: str | None
    reason: str
    severity: str


@dataclass(frozen=True)
class ValidationResult:
    """Validation status and findings for one record."""

    record_id: str
    status: str
    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)
    score_quality: float = 100.0


class DrugMatcher(Protocol):
    """Interface implemented by both the mock and production matcher."""

    def match(self, record: Mapping[str, Any]) -> MatchResult:
        """Match one input record."""

    def match_batch(self, records: Iterable[Mapping[str, Any]]) -> list[MatchResult]:
        """Match multiple records in input order."""


class DataGuard(Protocol):
    """Interface implemented by both the mock and production validator."""

    def validate(self, record: Mapping[str, Any], source: str) -> ValidationResult:
        """Validate one input record."""

    def validate_batch(
        self, records: Iterable[Mapping[str, Any]], source: str
    ) -> list[ValidationResult]:
        """Validate multiple records in input order."""


def record_id(record: Mapping[str, Any]) -> str:
    """Return the primary FAERS identifier or streaming event identifier."""
    value = record.get("primaryid") or record.get("event_id")
    if value is None or str(value).strip() == "":
        raise ValueError("record must contain a non-empty primaryid or event_id")
    return str(value)


class MockDrugMatcher:
    """Safe placeholder that preserves records as unmatched until M2 lands."""

    def match(self, record: Mapping[str, Any]) -> MatchResult:
        key = record_id(record)
        return MatchResult(
            record_id=key,
            status="UNMATCHED",
            rxcui=None,
            match_method="none",
            confidence=0.0,
            evidence=(
                {
                    "step": 1,
                    "rule": "mock_unmatched",
                    "detail": "Production matching is not connected yet.",
                    "score": 0.0,
                    "rxcui": None,
                },
            ),
            reason="mock_matcher",
        )

    def match_batch(self, records: Iterable[Mapping[str, Any]]) -> list[MatchResult]:
        return [self.match(record) for record in records]


class MockDataGuard:
    """Basic placeholder that rejects records missing primaryid or drugname."""

    def validate(self, record: Mapping[str, Any], source: str) -> ValidationResult:
        key = record_id(record)
        missing = [
            field_name
            for field_name in ("primaryid", "drugname")
            if record.get(field_name) is None or str(record.get(field_name)).strip() == ""
        ]
        issues = tuple(
            ValidationIssue(
                rule_id=f"mock_required_{field_name}",
                field=field_name,
                reason=f"Required field {field_name} is missing.",
                severity="error",
            )
            for field_name in missing
        )
        return ValidationResult(
            record_id=key,
            status="REJECTED" if issues else "ACCEPTED",
            issues=issues,
            score_quality=0.0 if issues else 100.0,
        )

    def validate_batch(
        self, records: Iterable[Mapping[str, Any]], source: str
    ) -> list[ValidationResult]:
        return [self.validate(record, source) for record in records]
