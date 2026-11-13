"""Markdown report and snapshot tables on the synthetic feature set."""

from __future__ import annotations

import pandas as pd
import pytest

from conftest import END_DATE
from goe.reports import KEY_INSTRUMENTS, build_markdown, curve_snapshot, market_snapshot

SCAN_META = {
    "scan_id": "scan-test-1",
    "as_of": END_DATE,
    "engine_version": "0.1.0",
    "feature_version": "v1",
    "config_hash": "c" * 64,
    "data_hash": "d" * 64,
    "n_instruments": 8,
    "n_macro_series": 1,
    "n_curve_systems": 1,
    "n_positioning_series": 1,
}


def _build(shared_store, feature_set, *, opportunities=None, anomalies=None):
    return build_markdown(
        store=shared_store,
        fs=feature_set,
        anomalies=anomalies if anomalies is not None else pd.DataFrame(),
        transmissions=pd.DataFrame(),
        mechanisms=[],
        opportunities=opportunities or [],
        scan_meta=SCAN_META,
        quality_issues=None,
    )


def test_build_markdown_contains_as_of_date_sections_and_disclaimer(shared_store, feature_set):
    markdown = _build(shared_store, feature_set)

    assert isinstance(markdown, str)
    assert END_DATE in markdown
    assert "全球投资机会发现报告" in markdown
    for section in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 6."):
        assert section in markdown, section
    assert "不是交易建议" in markdown
    assert "研究优先级" in markdown


def test_market_snapshot_has_expected_columns_and_values(feature_set):
    snapshot = market_snapshot(feature_set)

    assert not snapshot.empty
    assert list(snapshot.columns) == [
        "id", "name", "1w", "1m", "3m", "12m", "vol_3m", "dd_1y",
    ]
    ids = set(snapshot["id"])
    assert ids <= set(KEY_INSTRUMENTS)
    assert {"US_EQ_SPY", "CN_EQ_CSI300", "CM_MET_GC", "US_FI_IEF", "US_FX_DXY"} <= ids

    spy = snapshot[snapshot["id"] == "US_EQ_SPY"].iloc[0]
    assert spy["1m"] == pytest.approx(feature_set.value("US_EQ_SPY", "return", "1m"))
    assert spy["vol_3m"] == pytest.approx(feature_set.value("US_EQ_SPY", "ann_vol", "3m"))
    assert spy["dd_1y"] == pytest.approx(feature_set.value("US_EQ_SPY", "drawdown_252d"))
    assert spy["name"] == "SPDR S&P 500 ETF"


def test_curve_snapshot_reports_ust_slope(feature_set):
    snapshot = curve_snapshot(feature_set)

    assert not snapshot.empty
    assert list(snapshot.columns) == ["curve", "2Y", "10Y", "30Y", "2s10s", "2s10s_1m_chg"]
    ust = snapshot[snapshot["curve"] == "UST"].iloc[0]
    assert ust["2Y"] == pytest.approx(feature_set.value("UST:2Y", "level", "2Y"))
    assert ust["10Y"] == pytest.approx(feature_set.value("UST:10Y", "level", "10Y"))
    assert ust["2s10s"] == pytest.approx(feature_set.value("UST", "slope_2s10s"))
