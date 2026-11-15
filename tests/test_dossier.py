from __future__ import annotations

from goe.dossier import SECTIONS, build_dossier, render_markdown


def candidate(**kw):
    base = {
        "research_id": "RC-T-1", "research_theme_id": "RT-T-1", "as_of": "2026-01-01",
        "market": "JP", "asset_class": "equity_index", "instruments": ["JP_EQ_N225"],
        "observed_phenomenon": "drawdown", "materiality": {"importance": 0.8, "gap_score": 0.7},
        "priority_tier": "intelligence", "research_worthiness": "high",
        "evidence_readiness": "partial", "research_queue": "watch",
        "handoff_eligibility": "a_retained",
        "competing_hypotheses": [
            {"id": "H1", "label": "local", "type": "global_risk", "status": "open",
             "implications": "local explains", "evidence_for": [{"claim": "local R2", "value": "0.72",
             "class": "statistical_association", "source": "derived", "available_at": "2026-01-01",
             "discriminating": True}], "evidence_against": []},
            {"id": "H2", "label": "global", "type": "global_risk", "status": "open",
             "implications": "global explains", "evidence_for": [], "evidence_against": [
                 {"claim": "global R2 low", "value": "0.07", "class": "statistical_association",
                  "source": "derived", "available_at": "2026-01-01"}]}],
        "evidence": [{"claim": "1m", "value": "-9.7%", "class": "observed_fact",
                      "source": "prices", "available_at": "2026-01-01"}],
        "critical_unknowns": ["一致预期"], "falsification_conditions": [],
        "research_cost": {"hours": 8, "data_access": "medium"},
        "decision_impact": {"if_true": "a", "if_false": "b"}, "rationale": "r",
    }
    base.update(kw); return base


def test_dossier_has_all_sections_and_never_claims_validation():
    d = build_dossier(candidate(), artifact_path="evaluation/x.json",
                      scan_meta={"scan_id": "s"})
    assert list(d["sections"]) == SECTIONS
    assert d["discovery_value"] == "NOT VALIDATED"
    assert d["sections"]["Independent Quality Review"]["status"] == "NOT_INDEPENDENTLY_REVIEWED"
    assert "DISCOVERY VALUE: NOT VALIDATED" in render_markdown(d)
    assert d["sections"]["B Capability / Handoff"]["supported"] is False


def test_watch_next_action_is_collect_not_handoff():
    d = build_dossier(candidate())
    assert "Collect" in d["sections"]["Next Research Action"]
    assert d["sections"]["Research Worthiness"]["rating"] == "high"
