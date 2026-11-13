"""Transmission mechanism evaluation: activation, statistical tests, evidence
bookkeeping and direction mapping."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from conftest import make_feature_set, make_mechanism
from goe.transmission.evaluator import (
    MechanismEvaluator,
    direction_sign,
    evaluate_transmissions,
)


def _anomalies(entity_id: str = "UST:10Y", direction: str = "yields_up",
               date: str = "2024-12-31") -> pd.DataFrame:
    return pd.DataFrame([{
        "date": date, "anomaly_id": "AN-test", "detector": "curve_change",
        "family": "macro", "entity_id": entity_id, "entity_kind": "series",
        "direction": direction, "score": 0.7, "window": "1m",
    }])


def _correlated_fs(a: pd.Series, b: pd.Series):
    return make_feature_set(macro=pd.DataFrame({"A": a, "B": b}))


def _negatively_correlated_pair(n: int = 120) -> tuple[pd.Series, pd.Series]:
    index = pd.bdate_range("2024-01-01", periods=n)
    a = pd.Series(np.sin(np.arange(n) / 7.0), index=index)
    return a, -a


# ---------------------------------------------------------------- activation
def test_activation_requires_matching_anomaly_entity_and_direction():
    fs = make_feature_set()
    mechanisms = make_mechanism(triggers=[{"series": "UST:10Y", "direction": "up"}])
    evaluator = MechanismEvaluator(fs, mechanisms)

    matched = evaluator.evaluate(_anomalies("UST:10Y", "yields_up"))
    assert [r.mechanism_id for r in matched] == ["M_TEST"]
    assert matched[0].triggers[0]["anomaly_id"] == "AN-test"
    assert matched[0].as_of == "2024-12-31"

    # Same entity, opposite direction: the trigger is direction-aware.
    assert evaluator.evaluate(_anomalies("UST:10Y", "yields_down")) == []

    # Same direction, different entity: no activation.
    assert evaluator.evaluate(_anomalies("US_FX_DXY", "up")) == []

    # No anomalies at all: no transmission.
    assert evaluator.evaluate(pd.DataFrame()) == []
    rows, results = evaluate_transmissions(fs, pd.DataFrame(), mechanisms)
    assert rows.empty and results == []


# --------------------------------------------------------------------- tests
def test_corr_test_accepts_expected_negative_sign_and_rejects_positive():
    a, b = _negatively_correlated_pair()
    fs = _correlated_fs(a, b)
    evaluator = MechanismEvaluator(fs, {"mechanisms": {}})
    spec = {"type": "corr", "a": "A", "b": "B", "window": 60,
            "transform": "level", "expected_sign": -1, "min_abs": 0.15}

    passed = evaluator.corr_test(spec)
    assert passed.passed is True
    assert passed.stats["corr"] <= -0.99
    assert passed.stats["expected_sign"] == -1

    rejected = evaluator.corr_test(dict(spec, expected_sign=1))
    assert rejected.passed is False
    assert rejected.reason == "符号不符"
    assert rejected.stats["corr"] <= -0.99


def test_corr_test_treats_window_as_trading_days_for_daily_series():
    """config/mechanisms.yaml: "window 以交易日计" (window is in trading days).

    Build daily series whose *250-day* correlation is negative while the very
    short (last 12 days) correlation is positive.  The documented 250-day test
    must pass with expected_sign=-1.

    Regression guard: an earlier implementation inverted the frequency
    conversion, dividing the window by 21 for daily inputs (250 days became a
    12-day window) while treating monthly inputs as months.
    """
    rng = np.random.default_rng(7)
    n = 270
    index = pd.bdate_range("2024-01-01", periods=n)
    a = pd.Series(rng.normal(size=n), index=index)
    b = pd.Series(-0.9 * a.values + 0.1 * rng.normal(size=n), index=index)
    b.iloc[-12:] = 2.0 * a.iloc[-12:] + 0.1 * rng.normal(size=12)

    evaluator = MechanismEvaluator(_correlated_fs(a, b), {"mechanisms": {}})
    result = evaluator.corr_test({
        "type": "corr", "a": "A", "b": "B", "window": 250,
        "transform": "level", "expected_sign": -1, "min_abs": 0.15,
    })

    assert result.passed is True, result.reason
    assert result.stats["window"] == 250


def test_conditional_return_with_too_few_observations_is_not_support():
    index = pd.bdate_range("2024-01-01", periods=300)
    target = pd.DataFrame({"TGT": pd.Series(100.0 * np.exp(np.linspace(0, 0.1, 300)), index=index)})
    condition = pd.Series(1.0, index=index)
    condition.iloc[[0, 10, 20, 30, 40]] = 2.0  # only five events above threshold

    fs = make_feature_set(prices=target, macro=pd.DataFrame({"COND": condition}))
    mechanisms = make_mechanism(
        triggers=[{"series": "COND", "direction": "up"}],
        tests=[{
            "type": "conditional_return", "condition_series": "COND", "operator": ">",
            "threshold": 1.5, "target": "TGT", "horizon_days": 21,
            "expected_sign": 1, "min_observations": 15,
        }],
    )
    evaluator = MechanismEvaluator(fs, mechanisms)
    as_of = str(index[-1].date())
    results = evaluator.evaluate(_anomalies("COND", "up", date=as_of))

    assert len(results) == 1
    result = results[0]
    assert result.status == "insufficient_data"
    assert result.evidence_for == []
    assert len(result.evidence_against) == 1
    failed = result.evidence_against[0]
    assert failed["test_type"] == "conditional_return"
    assert failed["passed"] is False
    assert failed["reason"] == "insufficient_data"


def test_failed_test_is_reported_in_evidence_against():
    a, b = _negatively_correlated_pair()
    fs = _correlated_fs(a, b)
    mechanisms = make_mechanism(
        triggers=[{"series": "UST:10Y", "direction": "up"}],
        tests=[{
            "type": "corr", "a": "A", "b": "B", "window": 60,
            "transform": "level", "expected_sign": 1, "min_abs": 0.15,
        }],
    )
    evaluator = MechanismEvaluator(fs, mechanisms)
    results = evaluator.evaluate(_anomalies())

    assert len(results) == 1
    result = results[0]
    assert result.status == "unsupported"
    assert result.evidence_for == []
    assert any(e["test_type"] == "corr" and e["reason"] == "符号不符"
               for e in result.evidence_against)
    assert 0.05 <= result.confidence <= 0.85


# --------------------------------------------------------------- direction map
@pytest.mark.parametrize("direction,expected", [
    ("up", 1),
    ("down", -1),
    ("outperform", 1),
    ("underperform", -1),
    ("steepening", 1),
    ("flattening", -1),
    ("expansion", 1),
    ("compression", -1),
    ("above_norm", 1),
    ("below_norm", -1),
    ("golden_cross", 1),
    ("death_cross", -1),
    ("yields_up", 1),
    ("yields_down", -1),
    ("risk_on", 1),
    ("risk_off", -1),
    ("not_a_direction", 0),
    ("", 0),
])
def test_direction_sign_mapping(direction, expected):
    assert direction_sign(direction) == expected
