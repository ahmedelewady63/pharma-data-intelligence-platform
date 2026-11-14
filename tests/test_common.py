import pytest

from common.interfaces import MockDataGuard, MockDrugMatcher
from common.ndc import normalize_ndc11


def test_record_id_prefers_primaryid_then_event_id():
    from common.interfaces import record_id

    assert record_id({"primaryid": "123", "event_id": "123-1"}) == "123"
    assert record_id({"event_id": "123-1"}) == "123-1"


def test_mock_matcher_returns_unmatched_with_evidence():
    result = MockDrugMatcher().match({"primaryid": "123", "drugname": "ASPIRIN"})
    assert result.status == "UNMATCHED"
    assert result.confidence == 0.0
    assert result.evidence


def test_mock_guard_rejects_missing_required_fields():
    result = MockDataGuard().validate({"primaryid": "123"}, source="faers_drug")
    assert result.status == "REJECTED"
    assert result.issues[0].field == "drugname"


def test_mock_guard_can_report_missing_primaryid():
    result = MockDataGuard().validate({"drugname": "ASPIRIN"}, source="faers_drug")
    assert result.status == "REJECTED"
    assert any(issue.field == "primaryid" for issue in result.issues)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1234-5678-90", "01234567890"),
        ("12345-678-90", "12345067890"),
        ("12345-6789-0", "12345678900"),
        ("01234567890", "01234567890"),
        ("1234567890", "01234567890"),
    ],
)
def test_normalize_ndc11(value, expected):
    assert normalize_ndc11(value) == expected


@pytest.mark.parametrize("value", ["123-456-7890", "abc", "123456789"])
def test_normalize_ndc11_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_ndc11(value)
