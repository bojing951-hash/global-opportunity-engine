from __future__ import annotations

from goe.research_quality import evaluate_candidates


def cand(rid="R", tier="B", readiness="evidence_ok", measured=2, open_n=2):
    hyps = []
    for i in range(open_n):
        ev = ([{"claim": f"measured-{i}", "class": "statistical_association",
                "source": "derived", "available_at": "2026-01-01", "discriminating": True}]
              if i < measured else [{"claim": f"unknown-{i}", "class": "unknown",
                                     "source": "gap", "available_at": "2026-01-01"}])
        hyps.append({"id": f"H{i}", "type": "global_risk" if i == 0 else "fundamental",
                     "status": "open", "evidence_for": ev})
    return {"research_id": rid, "priority_tier": tier, "research_readiness": readiness,
            "materiality": {"importance": 0.8, "gap_score": 0.4},
            "competing_hypotheses": hyps,
            "falsification_conditions": [
                {"test": "t", "threshold": "x", "data": "d", "hypothesis_id": "H0",
                 "data_status": "available"}]}


def test_quality_audit_measures_but_never_validates():
    r = evaluate_candidates([cand(), cand("I", "intelligence", "evidence_gap", 0)])
    assert r["n_candidates"] == 2
    assert r["n_research_candidates"] == 1
    assert r["n_measured_two_or_more"] == 1
    assert r["discovery_value"] == "NOT VALIDATED"
    assert r["candidates"][0]["evidence_coverage"] == 1.0
    assert r["candidates"][1]["evidence_coverage"] == 0.0


def test_duplicate_claims_are_exposed_not_rewarded():
    c = cand()
    c["competing_hypotheses"][1]["evidence_for"] = c["competing_hypotheses"][0]["evidence_for"]
    r = evaluate_candidates([c])["candidates"][0]
    assert r["duplicate_claims"] == 1
