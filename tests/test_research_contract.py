from __future__ import annotations

import sqlite3

import pytest

from goe.db import Store
from goe.research_contract import EventNotResolved, resolve_event


def test_event_contract_binds_to_stored_anomaly(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    c = {"research_id": "R1", "research_theme_id": "T1", "as_of": "2026-11-13",
         "market": "TW", "asset_class": "equity_index", "instruments": ["TW_EQ_TAIEX"],
         "observed_phenomenon": "TAIEX 近期 price_return_shock（down，分数 0.81）"}
    store.conn.execute("""INSERT INTO anomalies(anomaly_id,as_of,detector,family,instrument_id,
        direction,magnitude,score,percentile,window,evidence_json,fingerprint,run_id,created_at)
        VALUES('A1','2026-11-06','price_return_shock','price','TW_EQ_TAIEX','down',0.05,0.8,0.0,'1d','{}','f','r','x')""")
    store.conn.commit()
    ev = resolve_event(c, store.conn)
    assert ev.event_start == "2026-11-06" and ev.detector_id == "price_return_shock"
    assert ev.decision_as_of == "2026-11-13"


def test_event_contract_never_silently_replaces_missing_event(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    c = {"research_id": "R2", "as_of": "2026-11-13", "instruments": ["X"],
         "observed_phenomenon": "drawdown"}
    with pytest.raises(EventNotResolved):
        resolve_event(c, store.conn)


def test_missing_spy_vix_is_insufficient_not_refutation(tmp_path, monkeypatch):
    import types
    import pandas as pd
    import goe.research_engine as eng

    idx = pd.bdate_range("2026-01-01", "2026-02-01")
    cols = ["X_EQ", "HK_EQ_HSI", "JP_EQ_N225", "KR_EQ_KOSPI", "US_EQ_QQQ",
            "US_VOL_VIX", "CN_FX_USDCNY"]
    rets = pd.DataFrame({c: [0.001] * len(idx) for c in cols}, index=idx)
    rets.loc[idx[-5], "X_EQ"] = -0.06

    class FakeBuilder:
        def __init__(self, *a, **k): pass
        def build(self): return types.SimpleNamespace(returns=rets)

    monkeypatch.setattr(eng, "FeatureBuilder", FakeBuilder)
    store = Store(str(tmp_path / "t.db"))
    spec = eng.spec_for_asset(
        asset="X_EQ", market="TW", asset_class="equity_index", as_of="2026-02-01",
        question="q", peers={"HK_EQ_HSI": ("HK", "same_day"), "JP_EQ_N225": ("JP", "same_day"),
                             "KR_EQ_KOSPI": ("KR", "same_day"), "US_EQ_QQQ": ("QQQ", "prior_us_session"),
                             "US_VOL_VIX": ("VIX", "prior_us_session"),
                             "CN_FX_USDCNY": ("CNY", "prior_us_session")},
        hypotheses=[("H-GLOBAL", {"label": "global", "type": "global"})],
        case_kind="equity_event", event_override="2026-01-27",
        roles={"local": "HK_EQ_HSI", "regional_tw": "JP_EQ_N225", "regional_kr": "KR_EQ_KOSPI",
               "global_equity": "US_EQ_SPY", "global_growth": "US_EQ_QQQ",
               "global_vol": "US_VOL_VIX", "fx": "CN_FX_USDCNY"},
        hypothesis_ids={"global": "H-GLOBAL"})
    store.upsert_research_candidate({
        "research_id": spec.research_id, "research_theme_id": spec.research_theme_id,
        "as_of": spec.as_of, "market": "TW", "asset_class": "equity_index",
        "instruments": ["X_EQ"], "observed_phenomenon": "q", "priority_tier": "intelligence",
        "competing_hypotheses": [], "evidence": []})
    f = eng.execute_spec(store, spec, out_dir=str(tmp_path / "out"))
    assert f.hypothesis_updates["H-GLOBAL"]["status"] == "INSUFFICIENT_DATA"
