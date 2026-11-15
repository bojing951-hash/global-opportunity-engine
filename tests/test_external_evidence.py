from __future__ import annotations

from types import SimpleNamespace

from goe.evidence.external import attach_external, consensus_evidence, ois_evidence

OIS_HEADER = "curve_id,currency,region,curve_type,tenor,date,value,available_at,source\n"


def ois_cfg(tmp_path, rows: str):
    p = tmp_path / "ois.csv"; p.write_text(OIS_HEADER + rows, encoding="utf-8")
    return {"ois": {"enabled": True, "path": str(p), "curve_id": "US",
                    "currency": "USD", "region": "US", "curve_type": "ois",
                    "max_age_days": 10}}


def test_consensus_is_point_in_time_and_stale_safe(tmp_path):
    p = tmp_path / "consensus.csv"
    p.write_text("series_id,date,value,available_at,metric\n"
                 "US_EQ_SPY,2026-01-01,2.0,2026-01-02,eps_revision_pct\n"
                 "US_EQ_SPY,2026-02-01,9.0,2026-03-01,eps_revision_pct\n", encoding="utf-8")
    cfg = {"consensus": {"enabled": True, "path": str(p), "max_age_days": 90}}
    got = consensus_evidence("2026-02-15", "US_EQ_SPY", cfg)
    assert got and got["value"].endswith("2.0") and got["discriminating"]
    assert consensus_evidence("2026-02-15", "US_EQ_SPY",
                              {"consensus": {**cfg["consensus"], "max_age_days": 7}}) is None
    assert consensus_evidence("2026-01-01", "US_EQ_SPY", cfg) is None


def test_same_curve_slope_and_cross_currency_rejected(tmp_path):
    cfg = ois_cfg(tmp_path, "US,USD,US,ois,2Y,2026-01-01,4.0,2026-01-02,test\n"
                            "US,USD,US,ois,10Y,2026-01-01,4.5,2026-01-02,test\n")
    got = ois_evidence("2026-01-05", "US", "USD", "ois", config=cfg)
    assert got and "0.50" in got["value"] and got["curve"]["curve_id"] == "US"
    # same file also contains a EUR curve with a different curvature; must never stitch
    mixed = tmp_path / "mixed.csv"
    mixed.write_text(OIS_HEADER + "US,USD,US,ois,2Y,2026-01-01,4.0,2026-01-02,test\n"
                                  "EU,EUR,EA,ois,10Y,2026-01-01,1.0,2026-01-02,test\n", encoding="utf-8")
    cfg_mixed = {"ois": {**cfg["ois"], "path": str(mixed)}}
    assert ois_evidence("2026-01-05", "US", "USD", "ois", config=cfg_mixed) is None
    assert ois_evidence("2026-01-05", "EA", "EUR", "ois", config=cfg_mixed) is None


def test_curve_rejects_different_dates_missing_tenor_expired_and_wrong_type(tmp_path):
    different = ois_cfg(tmp_path, "US,USD,US,ois,2Y,2026-01-01,4.0,2026-01-02,test\n"
                                  "US,USD,US,ois,10Y,2026-01-02,4.5,2026-01-03,test\n")
    assert ois_evidence("2026-01-05", "US", "USD", "ois", config=different) is None
    missing = ois_cfg(tmp_path, "US,USD,US,ois,10Y,2026-01-01,4.5,2026-01-02,test\n")
    assert ois_evidence("2026-01-05", "US", "USD", "ois", config=missing) is None
    assert ois_evidence("2026-02-01", "US", "USD", "ois", config=different) is None
    wrong_type = ois_cfg(tmp_path, "US,USD,US,policy_path_proxy,2Y,2026-01-01,4.0,2026-01-02,test\n"
                                    "US,USD,US,policy_path_proxy,10Y,2026-01-01,4.5,2026-01-02,test\n")
    assert ois_evidence("2026-01-05", "US", "USD", "ois", config=wrong_type) is None


def test_attach_external_opens_fundamental_only_when_measured(tmp_path, monkeypatch):
    path = tmp_path / "c.csv"
    path.write_text("series_id,date,value,available_at,metric\n"
                    "US_EQ_SPY,2026-01-01,2.0,2026-01-02,eps_revision_pct\n", encoding="utf-8")
    cfg = {"consensus": {"enabled": True, "path": str(path), "max_age_days": 90},
           "ois": {"enabled": False}}
    monkeypatch.setattr("goe.evidence.external._config", lambda: cfg)
    bundle = {"hypotheses": [
        {"id": "H-USEQ-FUND", "status": "untestable", "evidence_for": [], "evidence_against": []},
        {"id": "H-USEQ-GLOBAL", "status": "open", "evidence_for": [], "evidence_against": []}]}
    out = attach_external(bundle, SimpleNamespace(asset_class="equity_etf", region="US"),
                          "US_EQ_SPY", "2026-01-05")
    assert out["hypotheses"][0]["status"] == "open"
    assert out["hypotheses"][0]["evidence_for"][0]["discriminating"] is True
