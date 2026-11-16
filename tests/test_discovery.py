from __future__ import annotations

from goe.discovery import qualify


def cand(**kw):
    b = {"research_id": "R", "instruments": ["X"], "materiality": {"importance": .8, "gap_score": .8},
         "research_worthiness": "high", "evidence_readiness": "ready", "research_queue": "research",
         "competing_hypotheses": [{"id": "H1", "implications": "a"}, {"id": "H2", "implications": "b"}],
         "decision_impact": {"if_true": "x"}}
    b.update(kw); return b


def test_four_discovery_classes_are_distinguishable():
    assert qualify(cand())["classification"] == "RESEARCH_READY"
    assert qualify(cand(research_worthiness="high", evidence_readiness="partial"))["classification"] == "EVIDENCE_TO_COLLECT"
    assert qualify(cand(materiality={"gap_score": 0}, research_worthiness="low"))["classification"] == "INTELLIGENCE_ONLY"
    assert qualify(cand(materiality={"gap_score": .8, "near_month_end": True}))["classification"] == "DATA_ARTIFACT"
