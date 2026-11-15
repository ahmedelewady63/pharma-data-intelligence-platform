from common.interfaces import (
    DataGuard,
    DrugMatcher,
    MatchStatus,
    MockDataGuard,
    MockDrugMatcher,
    QualityStatus,
)


def test_mock_matcher_returns_unmatched():
    matcher: DrugMatcher = MockDrugMatcher()
    res = matcher.match({"event_id": "1-1", "drugname": "TYLENOL"})
    assert res.match_status is MatchStatus.UNMATCHED
    assert res.original_record_id == "1-1"
    assert 0.0 <= res.confidence_score <= 1.0


def test_mock_matcher_batch_keeps_order():
    out = MockDrugMatcher().match_batch([{"event_id": "a"}, {"event_id": "b"}])
    assert [r.original_record_id for r in out] == ["a", "b"]


def test_mock_guard_rejects_missing_required():
    guard: DataGuard = MockDataGuard()
    bad = guard.validate({"primaryid": "1", "drug_seq": 1, "drugname": ""}, "FAERS")
    ok = guard.validate({"primaryid": "1", "drug_seq": 1, "drugname": "X"}, "FAERS")
    assert bad.status is QualityStatus.REJECTED and bad.issues
    assert ok.status is QualityStatus.ACCEPTED and not ok.issues
