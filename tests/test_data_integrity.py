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
    # Macro feature dates are already availability dates; the evaluator must NOT
    # add the publication lag a second time (round-2 audit finding).
    assert res.stats["publication_lag_days"] == 0
    assert pd.Timestamp(res.stats["first_entry"]) >= cond_idx[10]


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


def test_positioning_never_contains_rows_after_as_of(shared_store):
    """P1-03 regression: a Friday COT print must not be visible mid-week."""
    from goe.features import FeatureBuilder

    as_of = "2024-12-28"          # between the 12-27 report and its 12-31 visibility
    fs = FeatureBuilder(shared_store, as_of=as_of, point_in_time=True).build()
    if fs.positioning.empty:
        pytest.skip("synthetic positioning unavailable")
    assert fs.positioning.index.max() <= pd.Timestamp(as_of)


def test_net_to_oi_is_a_ratio_not_raw_contracts(shared_store):
    """P1-04 regression: net_to_oi = net position / open interest."""
    from goe.features import FeatureBuilder

    fs = FeatureBuilder(shared_store, as_of=END_DATE, point_in_time=True).build()
    net = fs.value("POS_GOLD_MM", "net_position")
    ratio = fs.value("POS_GOLD_MM", "net_to_oi")
    oi_series = shared_store.load_indicator("POS_GOLD_MM:oi").dropna()
    net_series = shared_store.load_indicator("POS_GOLD_MM").dropna()
    common = net_series.index.intersection(oi_series.index)
    assert len(common) > 0
    expected = float(net_series.loc[common[-1]] / oi_series.loc[common[-1]])
    assert np.isfinite(net) and np.isfinite(ratio)
    assert ratio == pytest.approx(expected, rel=1e-9)
    assert abs(ratio) < 5   # a ratio, not hundreds of thousands of contracts


def test_monday_returns_survive_a_union_calendar(tmp_path):
    """P1: a crypto weekend row must not turn every Monday return into NaN."""
    from goe.db import Store
    from goe.features import FeatureBuilder

    store = Store(tmp_path / "cal.db")
    try:
        bd = pd.bdate_range("2023-01-02", periods=320)
        spy = pd.DataFrame({
            "instrument_id": "US_EQ_SPY", "date": bd.strftime("%Y-%m-%d"),
            "close": 300 + np.arange(len(bd)), "adj_close": 300 + np.arange(len(bd)),
            "source_id": "yahoo", "fetched_at": "2024-12-31T23:00:00Z"})
        # crypto trades every day, including weekends
        all_days = pd.date_range("2023-01-02", periods=460)
        btc = pd.DataFrame({
            "instrument_id": "CR_BTC", "date": all_days.strftime("%Y-%m-%d"),
            "close": 20000 + np.arange(len(all_days)), "adj_close": 20000 + np.arange(len(all_days)),
            "source_id": "yahoo", "fetched_at": "2024-12-31T23:00:00Z"})
        store.upsert_prices(pd.concat([spy, btc], ignore_index=True))
        fs = FeatureBuilder(store, as_of="2024-03-29").build()
        r = fs.series("US_EQ_SPY", "return", "1d")
        assert r.notna().sum() > 250, "per-instrument returns must not lose Mondays"
        assert r.loc[pd.Timestamp("2024-03-04")] != 0.0 or np.isfinite(r.loc[pd.Timestamp("2024-03-04")])
    finally:
        store.close()


def test_large_persistent_etf_jump_is_rebased_not_quarantined():
    from goe.config import load_universe

    idx = pd.bdate_range("2024-01-01", periods=8)
    # 3.213:1 non-standard share conversion, level persists
    px = pd.DataFrame({"CN_SEC_NEWEN": pd.Series([1.0, 1.01, 0.99, 3.2, 3.21, 3.19, 3.22, 3.20], index=idx)})
    cleaned, issues = clean_price_panel(px, load_universe())
    kinds = {(i["instrument_id"], i["kind"]) for i in issues}
    assert ("CN_SEC_NEWEN", "level_rebased") in kinds
    assert cleaned["CN_SEC_NEWEN"].notna().all()
    assert cleaned["CN_SEC_NEWEN"].pct_change().abs().max() < 0.4


def test_bls_incremental_lookback_covers_revisions(shared_store):
    from goe.ingest import Ingestor

    ing = Ingestor(shared_store)
    spec = {"id": "US_CPI", "kind": "macro", "frequency": "monthly"}
    start = ing._indicator_start(spec, mode="incremental")
    last = shared_store.scalar("SELECT MAX(date) FROM indicators WHERE series_id='US_CPI'")
    assert (pd.Timestamp(last) - pd.Timestamp(start)).days >= 150


def test_incomplete_intraday_bar_is_not_used(tmp_path):
    from goe.db import Store
    from goe.features import FeatureBuilder

    store = Store(tmp_path / "bar.db")
    try:
        bd = pd.bdate_range("2023-12-01", periods=260)
        rows = []
        for i, d in enumerate(bd):
            fetched = "2024-12-31T23:00:00Z" if d != bd[-1] else "2024-12-31T10:00:00Z"
            rows.append({"instrument_id": "US_EQ_SPY", "date": d.strftime("%Y-%m-%d"),
                         "close": 400 + i, "adj_close": 400 + i, "source_id": "yahoo",
                         "fetched_at": fetched})
        store.upsert_prices(pd.DataFrame(rows))
        fs = FeatureBuilder(store, as_of=bd[-1].strftime("%Y-%m-%d")).build()
        assert fs.prices["US_EQ_SPY"].dropna().index.max() < bd[-1]
    finally:
        store.close()


def test_breadth_is_computed_on_business_day_calendar(tmp_path):
    from goe.db import Store
    from goe.features import FeatureBuilder

    store = Store(tmp_path / "breadth.db")
    try:
        bd = pd.bdate_range("2023-01-02", periods=320)
        rows = []
        for i, iid in enumerate(["US_SEC_XLE", "US_SEC_XLF", "US_SEC_XLK", "US_SEC_XLV"]):
            px = 100 * np.exp(0.001 * (i + 1) * np.arange(len(bd)))
            rows.append(pd.DataFrame({"instrument_id": iid, "date": bd.strftime("%Y-%m-%d"),
                                      "close": px, "adj_close": px, "source_id": "yahoo",
                                      "fetched_at": "2024-12-31T23:00:00Z"}))
        store.upsert_prices(pd.concat(rows, ignore_index=True))
        fs = FeatureBuilder(store, as_of=bd[-1].strftime("%Y-%m-%d")).build()
        breadth = fs.series("US", "breadth_above_ma200")
        assert len(breadth) > 50
        assert breadth.iloc[-1] == pytest.approx(1.0), "all four uptrending sectors are above MA200"
        assert fs.series("US", "breadth_z_3y").empty or np.isfinite(fs.series("US", "breadth_z_3y").iloc[-1])
    finally:
        store.close()


def test_missing_open_interest_makes_net_to_oi_unknown_not_raw(store):
    """P1-04 regression guard: no OI -> net_to_oi unknown, never raw contracts."""
    from goe.features import FeatureBuilder

    store.conn.execute("DELETE FROM indicators WHERE series_id='POS_GOLD_MM:oi'")
    store.conn.commit()
    fs = FeatureBuilder(store, as_of=END_DATE, point_in_time=True).build()
    assert fs.series("POS_GOLD_MM", "net_to_oi").empty or fs.series("POS_GOLD_MM", "net_to_oi").notna().sum() == 0
    # raw net positions remain available and clearly named
    assert fs.series("POS_GOLD_MM", "net_position").notna().sum() > 0
