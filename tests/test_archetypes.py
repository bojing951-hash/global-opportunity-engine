"""Each opportunity archetype must actually be able to fire.

The live pipeline only shows the archetypes the current market supports; these
tests construct the minimal anomaly constellation for the less frequent ones so
that a regression in the generation rules cannot go unnoticed.
"""

from __future__ import annotations

import pandas as pd
import pytest

from conftest import END_DATE, make_feature_set
from goe.events import Event, EventCalendar
from goe.opportunities import OpportunityEngine


def anomaly(entity_id: str, detector: str, family: str, direction: str, *, score: float = 0.8,
            window: str = "", kind: str = "instrument", percentile: float = float("nan")) -> dict:
    return {
        "date": END_DATE, "anomaly_id": f"AN-{entity_id}-{detector}", "detector": detector,
        "family": family, "entity_id": entity_id, "entity_kind": kind, "asset_class": "x",
        "region": "US", "direction": direction, "window": window, "measure": "m",
        "magnitude": 2.5, "score": score, "percentile": percentile, "evidence": {},
    }


def engine(anomalies: list[dict], events: EventCalendar | None = None) -> OpportunityEngine:
    df = pd.DataFrame(anomalies)
    return OpportunityEngine(
        make_feature_set(as_of=END_DATE), df, transmissions=[], events=events,
        scoring={"weights": {"anomaly_strength": 1.0}, "status_thresholds": {"deep_research": 0.9,
                                                                              "watch": 0.8,
                                                                              "low_priority": 0.1},
                  "gates": {"min_evidence_items": 1, "min_data_quality": 0.0}},
        max_candidates=25,
    )


def test_relative_value_archetype_fires_for_opposite_relative_strength():
    anoms = [
        anomaly("US_SEC_XLE", "relative_strength_extreme", "industry", "outperform", window="3m"),
        anomaly("US_SEC_XLF", "relative_strength_extreme", "industry", "underperform", window="3m"),
    ]
    eng = engine(anoms)
    eng.generate()
    kinds = {d.archetype for d in eng.all_scored}
    assert "relative_value" in kinds
    rel = [d for d in eng.all_scored if d.archetype == "relative_value"][0]
    assert set(rel.primary_ids()) == {"US_SEC_XLE", "US_SEC_XLF"}
    assert "相对强弱" in rel.title


def test_expectation_overshoot_fires_for_crowded_long_into_strength():
    anoms = [
        anomaly("POS_GOLD_MM", "positioning_extreme", "positioning", "crowded_long", percentile=0.98,
                kind="positioning"),
        anomaly("CM_MET_GC", "price_return_shock", "price", "up", window="1m"),
    ]
    eng = engine(anoms)
    eng.generate()
    overshoot = [d for d in eng.all_scored if d.archetype == "expectation_overshoot"]
    assert overshoot, "拥挤多头 + 价格上涨应生成预期过度原型"
    d = overshoot[0]
    assert d.discovery["case"] == "optimism"
    assert d.mechanism["chain"] and d.evidence_against
    assert d.invalidation


def test_event_revision_fires_for_verified_event_nearby():
    events = EventCalendar([Event(id="FOMC_TEST", date="2025-01-15", region="US", type="central_bank",
                                  title="FOMC decision", affects=["US_EQ_SPY"],
                                  source="https://www.federalreserve.gov/", verified=True)])
    anoms = [anomaly("US_EQ_SPY", "price_return_shock", "price", "down", window="1m")]
    eng = engine(anoms, events=events)
    eng.generate()
    ev = [d for d in eng.all_scored if d.archetype == "event_revision"]
    assert ev, "已核验事件 + 异常应生成事件修正原型"
    assert any(c["id"] == "FOMC_TEST" for c in ev[0].catalysts)


def test_event_revision_ignores_unverified_events():
    events = EventCalendar([Event(id="LPR_TEST", date="2025-01-15", region="CN", type="central_bank",
                                  title="LPR (convention)", affects=["US_EQ_SPY"], source="", verified=False)])
    anoms = [anomaly("US_EQ_SPY", "price_return_shock", "price", "down", window="1m")]
    eng = engine(anoms, events=events)
    eng.generate()
    assert not [d for d in eng.all_scored if d.archetype == "event_revision"]
