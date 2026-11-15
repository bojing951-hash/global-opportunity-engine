from __future__ import annotations

from types import SimpleNamespace

from goe.evidence.external import attach_external, consensus_evidence, ois_evidence

CONS_HEADER = ("series_id,observation_date,forecast_target,publication_time,available_at,"
               "vintage,value,metric,kind,source\n")
OIS_HEADER = ("curve_id,currency,region,curve_type,provider,units,tenor,date,"
              "publication_time,available_at,vintage,value,source\n")


def cons_cfg(tmp_path, rows: str, age=90):
    p = tmp_path / "c.csv"; p.write_text(CONS_HEADER + rows, encoding="utf-8")
    return {"consensus": {"enabled": True, "path": str(p), "max_age_days": age}}


def ois_cfg(tmp_path, rows: str):
    p = tmp_path / "ois.csv"; p.write_text(OIS_HEADER + rows, encoding="utf-8")
    return {"ois": {"enabled": True, "path": str(p), "curve_id": "US",
                    "currency": "USD", "region": "US", "curve_type": "ois",
                    "provider": "TEST", "units": "percent", "max_age_days": 10}}


def test_consensus_actual_and_forecast_are_pit(tmp_path):
    rows = ("SPY,2026-01-01,2026-01-01,2026-01-02,2026-01-02,2026-01-02,2.0,eps_rev,actual,test\n"
            "SPY,2026-01-01,2026-03-31,2026-01-02,2026-01-02,2026-01-02,8.0,eps_rev,forecast,test\n")
    cfg = cons_cfg(tmp_path, rows)
    got = consensus_evidence("2026-02-15", "SPY", cfg)
    assert got and got["kind"] == "forecast" and got["forecast_target"] == "2026-03-31"
    # future publication / future vintage must not be usable
    future = ("SPY,2026-01-01,2026-01-01,2026-03-01,2026-03-01,2026-01-02,2.0,eps_rev,actual,test\n")
    assert consensus_evidence("2026-02-15", "SPY", cons_cfg(tmp_path, future)) is None
    # actual target in the future is invalid
    bad_actual = ("SPY,2026-01-01,2026-04-01,2026-01-02,2026-01-02,2026-01-02,2.0,eps_rev,actual,test\n")
    assert consensus_evidence("2026-02-15", "SPY", cons_cfg(tmp_path, bad_actual)) is None
    assert consensus_evidence("2026-04-01", "SPY", cons_cfg(tmp_path, future)) is not None


def test_same_curve_slope_and_cross_currency_rejected(tmp_path):
    base = ("US,USD,US,ois,TEST,percent,2Y,2026-01-01,2026-01-02,2026-01-02,2026-01-02,4.0,test\n"
            "US,USD,US,ois,TEST,percent,10Y,2026-01-01,2026-01-02,2026-01-02,2026-01-02,4.5,test\n")
    cfg = ois_cfg(tmp_path, base)
    got = ois_evidence("2026-01-05", "US", "USD", "ois", config=cfg)
    assert got and "0.50" in got["value"] and got["curve"]["curve_id"] == "US"
    mixed = ("US,USD,US,ois,TEST,percent,2Y,2026-01-01,2026-01-02,2026-01-02,2026-01-02,4.0,test\n"
             "EU,EUR,EA,ois,TEST,percent,10Y,2026-01-01,2026-01-02,2026-01-02,2026-01-02,1.0,test\n")
    cfg_mixed = {"ois": {**cfg["ois"], "path": str(tmp_path / "mixed.csv")}}
    (tmp_path / "mixed.csv").write_text(OIS_HEADER + mixed, encoding="utf-8")
    assert ois_evidence("2026-01-05", "US", "USD", "ois", config=cfg_mixed) is None
    assert ois_evidence("2026-01-05", "EA", "EUR", "ois", config=cfg_mixed) is None


def test_curve_rejects_dates_tenor_provider_units_type_and_staleness(tmp_path):
    def one(rows): return ois_cfg(tmp_path, rows)
    different = one("US,USD,US,ois,TEST,percent,2Y,2026-01-01,2026-01-02,2026-01-02,2026-01-02,4.0,t\n"
                    "US,USD,US,ois,TEST,percent,10Y,2026-01-02,2026-01-03,2026-01-03,2026-01-02,4.5,t\n")
    assert ois_evidence("2026-01-05", "US", "USD", "ois", config=different) is None
    missing = one("US,USD,US,ois,TEST,percent,10Y,2026-01-01,2026-01-02,2026-01-02,2026-01-02,4.5,t\n")
    assert ois_evidence("2026-01-05", "US", "USD", "ois", config=missing) is None
    mixed_provider = one("US,USD,US,ois,TEST,percent,2Y,2026-01-01,2026-01-02,2026-01-02,2026-01-02,4.0,t\n"
                         "US,USD,US,ois,OTHER,percent,10Y,2026-01-01,2026-01-02,2026-01-02,2026-01-02,4.5,t\n")
    assert ois_evidence("2026-01-05", "US", "USD", "ois", config=mixed_provider) is None
    wrong_units = one("US,USD,US,ois,TEST,bps,2Y,2026-01-01,2026-01-02,2026-01-02,2026-01-02,4.0,t\n"
                      "US,USD,US,ois,TEST,bps,10Y,2026-01-01,2026-01-02,2026-01-02,2026-01-02,4.5,t\n")
    assert ois_evidence("2026-01-05", "US", "USD", "ois", config=wrong_units) is None
    future_pub = one("US,USD,US,ois,TEST,percent,2Y,2026-01-01,2026-02-01,2026-02-01,2026-01-02,4.0,t\n"
                     "US,USD,US,ois,TEST,percent,10Y,2026-01-01,2026-02-01,2026-02-01,2026-01-02,4.5,t\n")
    assert ois_evidence("2026-01-05", "US", "USD", "ois", config=future_pub) is None
    assert ois_evidence("2026-02-01", "US", "USD", "ois", config=future_pub) is not None


def test_attach_external_opens_fundamental_only_when_measured(tmp_path, monkeypatch):
    rows = "SPY,2026-01-01,2026-01-31,2026-01-02,2026-01-02,2026-01-02,2.0,eps_rev,forecast,test\n"
    cfg = cons_cfg(tmp_path, rows)
    monkeypatch.setattr("goe.evidence.external._config", lambda: cfg)
    bundle = {"hypotheses": [
        {"id": "H-USEQ-FUND", "status": "untestable", "evidence_for": [], "evidence_against": []},
        {"id": "H-USEQ-GLOBAL", "status": "open", "evidence_for": [], "evidence_against": []}]}
    out = attach_external(bundle, SimpleNamespace(asset_class="equity_etf", region="US"),
                          "SPY", "2026-01-05")
    assert out["hypotheses"][0]["status"] == "open"
    assert out["hypotheses"][0]["evidence_for"][0]["discriminating"] is True


def test_future_vintage_observation_and_curve_date_rejected(tmp_path):
    future_vintage = ("SPY,2026-01-01,2026-01-01,2026-01-02,2026-01-02,2027-01-01,2.0,"
                      "eps_rev,actual,test\n")
    assert consensus_evidence("2026-02-15", "SPY", cons_cfg(tmp_path, future_vintage)) is None
    future_obs = ("SPY,2026-06-01,2026-01-01,2026-01-02,2026-01-02,2026-01-02,2.0,"
                  "eps_rev,actual,test\n")
    assert consensus_evidence("2026-02-15", "SPY", cons_cfg(tmp_path, future_obs)) is None
    future_curve = ("US,USD,US,ois,TEST,percent,2Y,2026-06-01,2026-01-02,2026-01-02,"
                    "2026-01-02,4.0,t\n"
                    "US,USD,US,ois,TEST,percent,10Y,2026-06-01,2026-01-02,2026-01-02,"
                    "2026-01-02,4.5,t\n")
    assert ois_evidence("2026-02-15", "US", "USD", "ois", config=ois_cfg(tmp_path, future_curve)) is None
