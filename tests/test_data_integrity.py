"""Regression tests for data-integrity fixes found by the independent audit.

Covers: calendar-aligned macro YoY (missing month), split adjustment vs glitch
quarantine, conditional-return publication lag, and evidence-diversity capping.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from conftest import END_DATE, make_feature_set
from goe.config import load_macro
from goe.features import FeatureBuilder, clean_price_panel
from goe.transmission.evaluator import MechanismEvaluator


def test_cpi_yoy_uses_calendar_months_when_a_month_is_missing():
    spec = load_macro()["US_CPI"]
    # monthly index with October 2025 missing (real BLS gap)
    months = pd.date_range("2024-01-01", "2026-10-01", freq="MS")
    values = 300.0 * (1.003 ** np.arange(len(months)))
    s = pd.Series(values, index=months)
    s = s.drop(pd.Timestamp("2025-10-01"))
    yoy = FeatureBuilder._transform(s, spec)
    # 2026-10 must compare with the (missing) 2025-10 -> NaN, never a row-shifted value
    assert pd.isna(yoy.loc["2026-10-01"])
    # a month with a valid 12-month-ago observation is computed on the index values
    expected = (s.loc["2026-09-01"] / s.loc["2025-09-01"] - 1) * 100
    assert yoy.loc["2026-09-01"] == pytest.approx(expected, rel=1e-9)


def test_etf_split_is_adjusted_and_index_glitch_is_quarantined():
    from goe.config import load_universe

    universe = load_universe()
    idx = pd.date_range("2024-01-01", periods=8, freq="B")
    # ETF: 2:1 split (100 -> 50)
    etf = pd.Series([100, 101, 100, 102, 51, 50, 51, 52.0], index=idx)
    # ETF: 10x glitch pair (drop then recovery) must NOT be treated as a split
    glitch = pd.Series([380, 382, 381, 38.2, 383, 384, 385, 386.0], index=idx)
    index = pd.Series([380, 382, 381, 379, 383, 384, 385, 386.0], index=idx)
    px = pd.DataFrame({"US_SEC_XLE": etf, "US_SEC_XLF": glitch, "CN_EQ_CSI300": index})
    cleaned, issues = clean_price_panel(px, universe)
    kinds = {(i["instrument_id"], i["kind"]) for i in issues}
    assert ("US_SEC_XLE", "split_adjusted") in kinds
    # split adjustment rescales prior prices so returns are continuous
    pre = cleaned["US_SEC_XLE"].iloc[:4]
    assert pre.max() < 60 and cleaned["US_SEC_XLE"].pct_change().abs().max() < 0.1
    assert ("US_SEC_XLF", "extreme_move_quarantined") in kinds
    assert np.isnan(cleaned["US_SEC_XLF"].iloc[3])
    # no residual jump on either basis, and index (no split logic) untouched
    for col in ("US_SEC_XLE", "US_SEC_XLF"):
        assert cleaned[col].pct_change().abs().max() < 0.4, col
    assert not np.isnan(cleaned["CN_EQ_CSI300"]).any()


def test_conditional_return_entries_respect_publication_lag():
    idx = pd.bdate_range("2024-01-01", periods=400)
    target = pd.Series(100.0 * (1.001 ** np.arange(len(idx))), index=idx)
    cond_idx = pd.date_range("2024-01-01", periods=20, freq="MS")
    cond = pd.Series([1.0] * 10 + [5.0] * 10, index=cond_idx)  # above threshold from 2024-11
    fs = make_feature_set(macro=pd.DataFrame({"US_CPI": cond}),
                          prices=pd.DataFrame({"TGT": target}))
    ev = MechanismEvaluator(fs, {"mechanisms": {}})
    res = ev.conditional_return_test({
        "type": "conditional_return", "condition_series": "US_CPI", "operator": ">",
        "threshold": 3.0, "target": "TGT", "horizon_days": 10, "expected_sign": 1,
        "min_observations": 3,
    })
    if res.stats.get("n", 0) == 0:
        pytest.skip("not enough forward windows in fixture")
    assert res.stats["publication_lag_days"] == 45
    # the first entry must be at least 45 calendar days after the condition observation
    first_obs = cond_idx[10]
    assert pd.Timestamp(res.stats["first_entry"]) >= first_obs + pd.Timedelta(days=45)


def test_collinear_tests_do_not_inflate_mechanism_confidence():
    idx = pd.bdate_range("2024-01-01", periods=400)
    base = pd.Series(np.random.default_rng(3).normal(size=400), index=idx)
    fs = make_feature_set(
        prices=pd.DataFrame({"A": 100 * np.exp(base.cumsum() / 100),
                             "B": 100 * np.exp(base.cumsum() / 100),
                             "C": 100 * np.exp(base.cumsum() / 100)})
    )
    mech = {
        "title": "collinear test", "family": "test",
        "triggers": [{"series": "A", "direction": "any"}],
        "affected_assets": [{"id": "A", "role": "primary"}],
        "evidence_tests": [
            {"type": "corr", "a": "A", "b": "B", "window": 120, "expected_sign": 1, "min_abs": 0.1},
            {"type": "corr", "a": "A", "b": "C", "window": 120, "expected_sign": 1, "min_abs": 0.1},
            {"type": "corr", "a": "A", "b": "B", "window": 60, "expected_sign": 1, "min_abs": 0.1},
        ],
        "conditions": [], "falsifiers": [],
    }
    ev = MechanismEvaluator(fs, {"mechanisms": {"M_TEST": mech}})
    anomalies = pd.DataFrame([{
        "date": "2024-12-31", "anomaly_id": "AN1", "detector": "price_return_shock",
        "family": "price", "entity_id": "A", "entity_kind": "instrument", "asset_class": "x",
        "region": "US", "direction": "up", "window": "1m", "measure": "m", "magnitude": 2.0,
        "score": 0.8, "percentile": 0.99, "evidence": {},
    }])
    results = ev.evaluate(anomalies)
    assert results
    # three collinear tests = one distinct lead; confidence must stay below the
    # level a naive 3-test count would produce (0.25 + 3*0.18 + 0.10 = 0.89)
    assert results[0].confidence < 0.80
