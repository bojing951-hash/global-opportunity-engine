from __future__ import annotations

from types import SimpleNamespace

from goe.evidence.external import attach_external, consensus_evidence, ois_evidence


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


def test_ois_slope_and_missing(tmp_path):
    p = tmp_path / "ois.csv"
    p.write_text("series_id,tenor,date,value,available_at\n"
                 "USD,2Y,2026-01-01,4.0,2026-01-02\n"
                 "USD,10Y,2026-01-01,4.5,2026-01-02\n", encoding="utf-8")
    cfg = {"ois": {"enabled": True, "path": str(p), "max_age_days": 10}}
    got = ois_evidence("2026-01-05", "US", cfg)
    assert got and "0.50" in got["value"] and got["discriminating"]
    assert ois_evidence("2026-02-01", "US", cfg) is None
    assert ois_evidence("2026-01-05", "US", {"ois": {"enabled": False}}) is None


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
