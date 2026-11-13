"""Opportunity scoring: bounded components, configured weights, status gates and
determinism."""

from __future__ import annotations

import pandas as pd
import pytest

from conftest import END_DATE, make_draft, make_feature_set
from goe.config import load_yaml_config
from goe.opportunities import OpportunityEngine


def _engine(rows=None) -> OpportunityEngine:
    fs = make_feature_set(rows=rows)
    return OpportunityEngine(fs, pd.DataFrame())


def _high_score_draft():
    return make_draft(
        discovery={
            "what": "SPY 价格下行但信用市场未确认风险厌恶",
            "why_now": "异常已触发",
            "hypothesis": "悲观情形可能已被过度定价",
            "anomalies": [{"score": 1.0}],
            "cape_pctile": 0.95,
            "positioning_percentile": 0.95,
        },
        evidence_for=[
            {"claim": "传导机制 M01 被激活", "evidence": "机制触发变量异常"},
            {"claim": "价格已显著回撤", "evidence": "距 1 年高点回撤 20%"},
            {"claim": "信用代理未恶化", "evidence": "HY/国债 z=+0.5"},
        ],
        catalysts=[{"date": "2025-01-05", "title": "FOMC", "type": "central_bank"}],
        mechanism={"id": None, "chain": ["a", "b"], "confidence": 0.85},
        data_quality={"score": 1.0, "gaps": []},
        horizon="1-3m",
    )


def _low_score_draft():
    return make_draft(
        instruments=[{
            "id": "US_FAC_VLUE", "name": "iShares MSCI USA Value Factor",
            "role": "primary", "asset_class": "equity_etf", "region": "US",
            "importance": 0.3, "liquidity": "medium",
        }],
        discovery={"what": "一般波动", "hypothesis": "无", "anomalies": [{"score": 0.0}]},
        evidence_for=[
            {"claim": "价格小幅波动", "evidence": "1 个月收益 -1%"},
            {"claim": "无其他证据", "evidence": "数据有限"},
        ],
        evidence_against=[],
        catalysts=[],
        mechanism={"id": None, "chain": [], "confidence": 0.3},
        data_quality={"score": 0.5, "gaps": ["数据有限"]},
        horizon="1-3m",
    )


def test_scoring_weights_sum_to_one():
    scoring = load_yaml_config("scoring.yaml")
    weights = scoring["weights"]
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)
    assert set(weights) == {
        "anomaly_strength", "economic_impact", "expectation_gap", "repricing_potential",
        "catalyst", "timing_window", "risk_liquidity", "evidence_quality",
    }
    # Documented thresholds are ordered.
    thresholds = scoring["status_thresholds"]
    assert thresholds["archive_below"] <= thresholds["low_priority"] < \
        thresholds["watch"] < thresholds["deep_research"]


def test_score_components_are_bounded_and_weighted_sum_reproduces_score():
    engine = _engine(rows=[
        ("instrument", "US_EQ_SPY", "equity_etf", "US", "ma_gap_200d", "", END_DATE, 0.20),
        ("instrument", "US_EQ_SPY", "equity_etf", "US", "drawdown_252d", "", END_DATE, -0.25),
    ])
    scoring = load_yaml_config("scoring.yaml")
    weights = scoring["weights"]

    for draft in (_high_score_draft(), _low_score_draft()):
        engine._score(draft)
        assert set(draft.score_components) == set(weights)
        for name, value in draft.score_components.items():
            assert 0.0 <= value <= 1.0, f"{name}={value} outside [0,1]"
        expected = sum(weights[name] * value for name, value in draft.score_components.items())
        assert draft.score == pytest.approx(expected, abs=2e-4)
        assert 0.0 <= draft.score <= 1.0


def test_high_score_draft_maps_to_deep_research():
    engine = _engine(rows=[
        ("instrument", "US_EQ_SPY", "equity_etf", "US", "ma_gap_200d", "", END_DATE, 0.20),
        ("instrument", "US_EQ_SPY", "equity_etf", "US", "drawdown_252d", "", END_DATE, -0.25),
    ])
    draft = _high_score_draft()
    engine._score(draft)
    scoring = load_yaml_config("scoring.yaml")
    assert draft.score >= scoring["status_thresholds"]["deep_research"]
    assert draft.status == "deep_research"


def test_low_score_draft_is_excluded_or_low_priority():
    engine = _engine()
    draft = _low_score_draft()
    engine._score(draft)
    scoring = load_yaml_config("scoring.yaml")
    assert draft.score < scoring["status_thresholds"]["watch"]
    assert draft.status in {"excluded", "low_priority"}


def test_gate_min_evidence_items_excludes_draft():
    engine = _engine()
    draft = _high_score_draft()
    draft.evidence_for = draft.evidence_for[:1]
    engine._score(draft)
    assert draft.status == "excluded"
    assert "证据" in draft.status_reason


def test_gate_min_data_quality_excludes_draft():
    engine = _engine()
    draft = _high_score_draft()
    # Enough evidence, but the data cannot support a judgement.
    draft.data_quality = {"score": 0.10, "gaps": ["关键数据缺失"]}
    engine._score(draft)
    assert draft.status == "excluded"
    assert "数据质量" in draft.status_reason
    assert draft.score >= 0  # the score is still computed and auditable


def test_scoring_is_deterministic():
    engine = _engine(rows=[
        ("instrument", "US_EQ_SPY", "equity_etf", "US", "ma_gap_200d", "", END_DATE, 0.20),
        ("instrument", "US_EQ_SPY", "equity_etf", "US", "drawdown_252d", "", END_DATE, -0.25),
    ])
    first, second = _high_score_draft(), _high_score_draft()
    engine._score(first)
    engine._score(second)
    assert first.score == second.score
    assert first.score_components == second.score_components
    assert first.status == second.status == "deep_research"
