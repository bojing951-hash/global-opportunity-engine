from __future__ import annotations

from goe.investment_intel import analyze


def test_no_market_expectation_baseline_means_no_mispricing_claim():
    f = {"research_id": "R", "decision_as_of": "2026-11-13", "event_date": "2026-11-06",
         "observed": {}, "tests": {}, "hypothesis_updates": {"H": {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE"}}}
    out = analyze(f)
    assert out["market_expectations"]["status"] == "MARKET_EXPECTATIONS_NOT_ESTABLISHED"
    assert out["expectation_gap"]["status"] == "MISPRICING_NOT_ESTABLISHED"
    assert out["discovery_value"] == "NOT VALIDATED"
