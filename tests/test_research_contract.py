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


def test_missing_risk_data_is_insufficient_for_fx_and_commodity(tmp_path, monkeypatch):
    import types
    import pandas as pd
    import goe.research_engine as eng

    idx = pd.bdate_range("2026-01-01", "2026-02-01")

    class FakeBuilder:
        def __init__(self, *a, **k): pass
        def build(self): return types.SimpleNamespace(returns=FakeBuilder.rets)

    monkeypatch.setattr(eng, "FeatureBuilder", FakeBuilder)
    store = Store(str(tmp_path / "t.db"))

    def run(asset, peers, roles, kind, cols):
        FakeBuilder.rets = pd.DataFrame({c: [0.001] * len(idx) for c in cols}, index=idx)
        FakeBuilder.rets.iloc[-5, 0] = 0.07
        spec = eng.spec_for_asset(
            asset=asset, market="US", asset_class=("fx" if kind == "fx_level" else "commodity"),
            as_of="2026-02-01", question="q", peers=peers,
            hypotheses=[("H-RISK", {"label": "risk", "type": "risk"})],
            case_kind=kind, event_override="2026-01-27", roles=roles,
            hypothesis_ids={"risk": "H-RISK"})
        store.upsert_research_candidate({
            "research_id": spec.research_id, "research_theme_id": spec.research_theme_id,
            "as_of": spec.as_of, "market": "US", "asset_class": spec.asset_class,
            "instruments": [asset], "observed_phenomenon": "q", "priority_tier": "intelligence",
            "competing_hypotheses": [], "evidence": []})
        f = eng.execute_spec(store, spec, out_dir=str(tmp_path / ("out_" + kind)))
        assert f.hypothesis_updates["H-RISK"]["status"] == "INSUFFICIENT_DATA"

    run("X_FX", {"GX_FX_EURUSD": ("EUR", "same_day"), "GX_FX_USDJPY": ("JPY", "same_day"),
                 "US_FI_IEF": ("IEF", "same_day")},
        {"cross1": "GX_FX_EURUSD", "cross2": "GX_FX_USDJPY", "rates": "US_FI_IEF",
         "risk": "US_EQ_SPY", "vol": "US_VOL_VIX"}, "fx_level", ["X_FX", "GX_FX_EURUSD", "GX_FX_USDJPY", "US_FI_IEF"])
    run("X_CMD", {"US_FX_DXY": ("DXY", "same_day"), "CM_MET_GC": ("Gold", "same_day"),
                  "US_FI_IEF": ("IEF", "same_day")},
        {"dollar": "US_FX_DXY", "gold": "CM_MET_GC", "rates": "US_FI_IEF",
         "risk": "US_EQ_SPY", "vol": "US_VOL_VIX"}, "commodity_event",
        ["X_CMD", "US_FX_DXY", "CM_MET_GC", "US_FI_IEF"])
