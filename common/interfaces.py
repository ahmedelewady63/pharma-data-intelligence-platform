"""Shared interfaces between components.

Members 5 and 6 can build against the Mock* classes from day one, so nobody waits for the
real Drug Matching Engine (member 2) or DataGuard (member 3). The real implementations must
keep these signatures. Change them only through a contracts PR.

The neutral batch format is a list of plain dicts, so the same code works in pandas, Spark
(mapInPandas / foreachBatch) and unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, Sequence


class MatchStatus(str, Enum):
    MATCHED = "MATCHED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    UNMATCHED = "UNMATCHED"
    CONFLICT = "CONFLICT"


class QualityStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass(frozen=True)
class Evidence:
    rule: str
    detail: str
    score: float | None = None


@dataclass(frozen=True)
class MatchResult:
    original_record_id: str
    original_drug_name: str | None
    matched_drug_id: str | None  # RxNorm RXCUI when matched
    match_status: MatchStatus
    confidence_score: float  # 0.0 to 1.0
    matching_evidence: tuple[Evidence, ...] = ()
    reference_source: str | None = None  # e.g. RXNORM, NDC, EDA


@dataclass(frozen=True)
class Issue:
    rule_id: str
    field: str | None
    message: str
    severity: str = "error"  # error | warning


@dataclass(frozen=True)
class ValidationResult:
    record_id: str
    status: QualityStatus
    issues: tuple[Issue, ...] = ()
    quality_score: float | None = None  # 0 to 100, formula documented by member 3


class DrugMatcher(Protocol):
    def match(self, record: dict[str, Any]) -> MatchResult: ...

    def match_batch(self, records: Sequence[dict[str, Any]]) -> list[MatchResult]: ...


class DataGuard(Protocol):
    def validate(self, record: dict[str, Any], source: str) -> ValidationResult: ...

    def validate_batch(
        self, records: Sequence[dict[str, Any]], source: str
    ) -> list[ValidationResult]: ...


def record_id(record: dict[str, Any]) -> str:
    return str(record.get("event_id") or record.get("primaryid") or "")


class MockDrugMatcher:
    """Always UNMATCHED. Replace with the real engine at integration time."""

    def match(self, record: dict[str, Any]) -> MatchResult:
        return MatchResult(
            original_record_id=record_id(record),
            original_drug_name=record.get("drugname"),
            matched_drug_id=None,
            match_status=MatchStatus.UNMATCHED,
            confidence_score=0.0,
            matching_evidence=(Evidence("mock", "MockDrugMatcher: no matching performed"),),
            reference_source=None,
        )

    def match_batch(self, records: Sequence[dict[str, Any]]) -> list[MatchResult]:
        return [self.match(r) for r in records]


class MockDataGuard:
    """Rejects records missing required fields, accepts everything else."""

    REQUIRED = {"faers": ("primaryid", "drug_seq", "drugname")}
    DEFAULT_REQUIRED = ("primaryid", "drugname")

    def validate(self, record: dict[str, Any], source: str) -> ValidationResult:
        required = self.REQUIRED.get(source.lower(), self.DEFAULT_REQUIRED)
        issues = tuple(
            Issue("required_field", f, f"{f} is required")
            for f in required
            if record.get(f) in (None, "")
        )
        status = QualityStatus.REJECTED if issues else QualityStatus.ACCEPTED
        return ValidationResult(
            record_id=record_id(record),
            status=status,
            issues=issues,
            quality_score=0.0 if issues else 100.0,
        )

    def validate_batch(
        self, records: Sequence[dict[str, Any]], source: str
    ) -> list[ValidationResult]:
        return [self.validate(r, source) for r in records]
