from __future__ import annotations

from goe.integration.capabilities import handoff_eligibility, route_candidate


def test_b_router_separates_macro_facts_from_deep_asset_research():
    fx = {"asset_class": "fx", "instruments": ["US_FX_DXY"]}
    rates = {"asset_class": "fixed_income", "instruments": ["US_FI_IEF"]}
    equity = {"asset_class": "equity_index", "instruments": ["JP_EQ_N225"]}
    commodity = {"asset_class": "commodity", "instruments": ["CM_MET_GC"]}
    assert route_candidate(fx)["supported"]
    assert route_candidate(rates)["supported"]
    assert not route_candidate(equity)["supported"]
    assert not route_candidate(commodity)["supported"]
    assert handoff_eligibility(equity, tier="A", evidence_readiness="ready") == "capability_gap"
    assert handoff_eligibility(fx, tier="A", evidence_readiness="ready") == "eligible"
    assert handoff_eligibility(fx, tier="intelligence", evidence_readiness="ready") == "a_retained"
