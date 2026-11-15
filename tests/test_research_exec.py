from __future__ import annotations

import pandas as pd

from goe.research_exec import _event_date, _prior_session, _ret


def test_event_date_uses_only_bars_up_to_as_of():
    idx = pd.bdate_range("2026-01-01", periods=30)
    y = pd.Series(0.0, index=idx)
    y.iloc[10] = -0.06
    y.iloc[-1] = -0.10  # after a hypothetical as_of below
    r = pd.DataFrame({"X": y})
    as_of = str(idx[20].date())
    assert _event_date(r, "X", as_of) == str(idx[10].date())


def test_ret_returns_none_for_future_or_missing_date():
    idx = pd.bdate_range("2026-01-01", periods=3)
    r = pd.DataFrame({"X": [0.01, 0.02, 0.03]}, index=idx)
    assert _ret(r, "X", str(idx[1].date())) == 0.02
    assert _ret(r, "X", "2026-02-01") is None
    assert _ret(r, "Y", str(idx[1].date())) is None


def test_prior_session_strictly_before_event():
    idx = pd.bdate_range("2026-11-02", periods=5)
    r = pd.DataFrame({"X": [0.0, 0.0, 0.0, 0.0, 0.0]}, index=idx)
    assert _prior_session(r, "2026-11-04") == "2026-11-03"


def test_execution_uses_prior_us_session_and_writes_db(tmp_path, monkeypatch):
    import types
    import goe.research_exec as rx
    from goe.db import Store

    idx = pd.bdate_range("2026-10-01", "2026-11-13")
    n = len(idx)
    data = {c: [0.001] * n for c in rx.EVENT_ASSETS}
    event = pd.Timestamp("2026-11-06")
    pos = idx.get_loc(event)
    data["JP_EQ_N225"][pos] = -0.06
    data["JP_EQ_TOPIX"][pos] = -0.065
    data["TW_EQ_TAIEX"][pos] = -0.045
    data["KR_EQ_KOSPI"][pos] = -0.06
    # prior US session falls; same-date US close (after Asia) would be up and must not be used
    data["US_EQ_SPY"][pos - 1] = -0.044
    data["US_EQ_QQQ"][pos - 1] = -0.065
    data["US_VOL_VIX"][pos - 1] = 0.70
    data["US_EQ_SPY"][pos] = 0.10
    data["US_EQ_QQQ"][pos] = 0.10
    data["US_VOL_VIX"][pos] = -0.30
    rets = pd.DataFrame(data, index=idx)

    class FakeBuilder:
        def __init__(self, *a, **k): pass
        def build(self): return types.SimpleNamespace(returns=rets)

    monkeypatch.setattr(rx, "FeatureBuilder", FakeBuilder)
    store = Store(str(tmp_path / "t.db"))
    store.upsert_research_candidate({
        "research_id": rx.CASE_N225, "research_theme_id": "RT-N225",
        "as_of": "2026-11-13", "market": "JP", "asset_class": "equity_index",
        "instruments": ["JP_EQ_N225"], "observed_phenomenon": "x",
        "priority_tier": "intelligence", "competing_hypotheses": [], "evidence": []})
    f = rx.execute_nikkei_case(store, as_of="2026-11-13", out_dir=str(tmp_path / "out"))
    assert f.event_date == "2026-11-06"
    assert f.tests["global_lead_test"]["spy_return"] == -0.044
    assert f.tests["global_lead_test"]["pass"] is True
    assert f.hypothesis_updates["H-EQJP-GLOBAL"]["status"] == "SUPPORTED_BY_AVAILABLE_EVIDENCE"
    row = store.conn.execute("SELECT status FROM research_v2_hypotheses WHERE hypothesis_id=?",
                             (f.research_id + ":H-EQJP-GLOBAL",)).fetchone()
    assert row and row["status"] == "SUPPORTED_BY_AVAILABLE_EVIDENCE"
    assert store.conn.execute("SELECT 1 FROM research_v2_findings WHERE finding_id=?",
                              (f.finding_id,)).fetchone()


def test_generic_execution_is_idempotent_and_keeps_artifact(tmp_path, monkeypatch):
    import types
    import goe.research_engine as eng
    from goe.db import Store

    idx = pd.bdate_range("2026-01-01", "2026-02-01")
    data = {c: [0.001] * len(idx) for c in
            ["X_EQ", "HK_EQ_HSI", "JP_EQ_N225", "KR_EQ_KOSPI", "US_EQ_SPY", "US_EQ_QQQ",
             "US_VOL_VIX", "CN_FX_USDCNY"]}
    data["X_EQ"][-5] = -0.06
    rets = pd.DataFrame(data, index=idx)

    class FakeBuilder:
        def __init__(self, *a, **k): pass
        def build(self): return types.SimpleNamespace(returns=rets)

    monkeypatch.setattr(eng, "FeatureBuilder", FakeBuilder)
    store = Store(str(tmp_path / "t.db"))
    spec = eng.spec_for_asset(
        asset="X_EQ", market="TW", asset_class="equity_index", as_of="2026-02-01",
        question="q", peers={"HK_EQ_HSI": ("HK", "same_day"), "JP_EQ_N225": ("JP", "same_day"),
                             "KR_EQ_KOSPI": ("KR", "same_day"), "US_EQ_SPY": ("SPY", "prior_us_session"),
                             "US_EQ_QQQ": ("QQQ", "prior_us_session"), "US_VOL_VIX": ("VIX", "prior_us_session"),
                             "CN_FX_USDCNY": ("CNY", "prior_us_session")},
        hypotheses=[("H-LOCAL", {"label": "local", "type": "local"})],
        case_kind="equity_event", event_override="2026-01-27",
        roles={"local": "HK_EQ_HSI", "regional_tw": "JP_EQ_N225", "regional_kr": "KR_EQ_KOSPI",
               "global_equity": "US_EQ_SPY", "global_growth": "US_EQ_QQQ",
               "global_vol": "US_VOL_VIX", "fx": "CN_FX_USDCNY"},
        hypothesis_ids={"local": "H-LOCAL"})
    store.upsert_research_candidate({
        "research_id": spec.research_id, "research_theme_id": spec.research_theme_id,
        "as_of": spec.as_of, "market": "TW", "asset_class": "equity_index",
        "instruments": ["X_EQ"], "observed_phenomenon": "q", "priority_tier": "intelligence",
        "competing_hypotheses": [], "evidence": []})
    f1 = eng.execute_spec(store, spec, out_dir=str(tmp_path / "out"))
    art = tmp_path / "out" / spec.as_of / spec.asset / f1.finding_id / "finding.json"
    before = art.read_bytes()
    f2 = eng.execute_spec(store, spec, out_dir=str(tmp_path / "out"))
    assert f2.finding_id == f1.finding_id
    assert art.read_bytes() == before
    assert store.conn.execute("SELECT COUNT(*) FROM research_v2_findings").fetchone()[0] == 1
