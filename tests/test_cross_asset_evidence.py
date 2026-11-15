from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

from goe.evidence.cross_asset import compute_fits, count_discriminating, evidence_for_bundle


def test_cross_asset_fit_is_measured_and_attached():
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2024-01-01", periods=300)
    factor = rng.normal(0, 0.01, len(idx))
    rets = pd.DataFrame({
        "US_EQ_SPY": factor,
        "US_EQ_QQQ": factor * 1.2 + rng.normal(0, 0.002, len(idx)),
        "US_FX_DXY": -factor * 0.4 + rng.normal(0, 0.001, len(idx)),
        "US_EQ_TEST": factor * 0.8 + rng.normal(0, 0.002, len(idx)),
    }, index=idx)
    fs = SimpleNamespace(returns=rets, as_of="2025-12-31")
    spec = SimpleNamespace(region="US", asset_class="equity_etf")
    fits = compute_fits(fs, "US_EQ_TEST", spec, "2025-12-31")
    assert fits["available"] and fits["global"]["r2"] > 0.5
    bundle = {"hypotheses": [
        {"id": "H-USEQ-GLOBAL", "status": "open", "evidence_for": [], "evidence_against": []},
        {"id": "H-USEQ-LOCAL", "status": "open", "evidence_for": [], "evidence_against": []}]}
    bundle = evidence_for_bundle(bundle, fits)
    assert any(e.get("discriminating") for e in bundle["hypotheses"][0]["evidence_for"])
    assert count_discriminating(bundle) >= 1


def test_cross_asset_insufficient_data_is_untestable_not_support():
    fs = SimpleNamespace(returns=pd.DataFrame({"US_EQ_TEST": [0.1, 0.2]}), as_of="2025-12-31")
    spec = SimpleNamespace(region="US", asset_class="equity_etf")
    fits = compute_fits(fs, "US_EQ_TEST", spec, "2025-12-31")
    assert not fits["available"]
    bundle = {"hypotheses": [{"id": "H-USEQ-GLOBAL", "status": "open",
                              "evidence_for": [], "evidence_against": []}]}
    out = evidence_for_bundle(bundle, fits)
    assert out["hypotheses"][0]["evidence_for"] == []
    assert count_discriminating(out) == 0


def test_low_r2_fx_is_not_discriminating():
    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2024-01-01", periods=300)
    rets = pd.DataFrame({
        "US_EQ_SPY": rng.normal(0, 0.01, len(idx)),
        "US_EQ_QQQ": rng.normal(0, 0.01, len(idx)),
        "GX_FX_USDJPY": rng.normal(0, 0.004, len(idx)),
        "JP_EQ_N225": rng.normal(0, 0.01, len(idx)),
    }, index=idx)
    fs = SimpleNamespace(returns=rets, as_of="2025-12-31")
    spec = SimpleNamespace(region="JP", asset_class="equity_index")
    fits = compute_fits(fs, "JP_EQ_N225", spec, "2025-12-31")
    bundle = {"hypotheses": [
        {"id": "H-EQJP-GLOBAL", "type": "global_risk", "status": "open",
         "evidence_for": [], "evidence_against": []},
        {"id": "H-EQJP-FX", "type": "global_risk", "status": "open",
         "evidence_for": [], "evidence_against": []}]}
    out = evidence_for_bundle(bundle, fits)
    fx = out["hypotheses"][1]
    assert not any(e.get("discriminating") for e in fx["evidence_for"])
    assert count_discriminating(out) <= 1


def test_global_support_requires_r2_above_documented_threshold():
    fits = {"available": True, "as_of": "2026-01-01",
            "global": {"available": True, "r2": 0.40, "beta": 1.0, "residual_z": 0.5,
                       "n_obs": 252, "factor": "x", "kind": "global", "reason": ""}}
    bundle = {"hypotheses": [{"id": "H-USEQ-GLOBAL", "type": "global_risk", "status": "open",
                              "evidence_for": [], "evidence_against": []}]}
    out = evidence_for_bundle(bundle, fits)
    h = out["hypotheses"][0]
    assert h["status"] == "open"
    assert h["evidence_for"] == []
    assert count_discriminating(out) == 0


def test_high_r2_but_high_residual_is_reported_as_residual_failure():
    fits = {"available": True, "as_of": "2026-01-01",
            "global": {"available": True, "r2": 0.53, "beta": 1.0, "residual_z": 1.57,
                       "n_obs": 252, "factor": "x", "kind": "global", "reason": ""}}
    bundle = {"hypotheses": [{"id": "H-USEQ-GLOBAL", "type": "global_risk", "status": "open",
                              "evidence_for": [], "evidence_against": []}]}
    out = evidence_for_bundle(bundle, fits)
    h = out["hypotheses"][0]
    assert h["status"] == "open" and h["evidence_for"] == []
    assert "residual_z" in h["evidence_against"][0]["value"]
    assert h["evidence_against"][0]["value"].startswith("|residual_z|")
