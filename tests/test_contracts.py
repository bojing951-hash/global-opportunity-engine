"""Executable checks for contracts/ (contract-first gate)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from conftest import make_feature_set
from goe.config import load_yaml_config
from goe.contracts import (ContractError, FEATURE_COLUMNS, validate_anomaly_records,
                           validate_feature_frame, validate_handoff_result,
                           validate_research_candidate, validate_v1_weights)


def test_feature_contract_columns():
    fs = make_feature_set(rows=[("instrument", "US_EQ_SPY", "equity_etf", "US",
                                 "return", "1m", "2024-01-02", 0.01)])
    assert list(fs.long.columns) == FEATURE_COLUMNS
    validate_feature_frame(fs.long)
    with pytest.raises(ContractError):
        validate_feature_frame(fs.long.drop(columns=["available_date"], errors="ignore")
                               .rename(columns={"value": "val"}))


def test_anomaly_contract_on_real_scan():
    import sqlite3
    c = sqlite3.connect("data/goe.db")
    rows = c.execute("SELECT anomaly_id, as_of, available_date, detector, family, instrument_id, "
                     "direction, window, evidence_json FROM anomalies LIMIT 50").fetchall()
    if not rows:
        pytest.skip("no scan database")
    recs = []
    for r in rows:
        recs.append({"anomaly_id": r[0], "date": r[1], "available_date": r[2],
                     "detector": r[3], "family": r[4], "entity_id": r[5],
                     "entity_kind": "instrument", "direction": r[6], "window": r[7],
                     "measure": "", "magnitude": 0.0, "score": 0.5,
                     "evidence": json.loads(r[8] or "{}")})
    if recs and not recs[0]["evidence"]:
        pytest.skip("legacy anomaly rows lack evidence")
    validate_anomaly_records(recs)


def test_research_candidate_contract():
    c = {
        "research_id": "R-1", "as_of": "2024-01-01", "market": "US",
        "asset_class": "equity_etf", "instruments": ["US_EQ_SPY"],
        "observed_phenomenon": "test", "materiality": "high",
        "competing_hypotheses": [
            {"id": "H1", "label": "risk premium", "type": "risk_premium",
             "status": "open", "implications": "x",
             "evidence_for": [], "evidence_against": []},
            {"id": "H2", "label": "data artifact", "type": "data_artifact",
             "status": "open", "implications": "y",
             "evidence_for": [], "evidence_against": []}],
        "evidence": [{"claim": "fact", "class": "observed_fact", "source": "db",
                      "available_at": "2024-01-01"}],
        "critical_unknowns": ["earnings revisions"],
        "falsification_conditions": [
            {"test": "corr sign", "threshold": "<0", "data": "prices", "hypothesis_id": "H1"},
            {"test": "artifact check", "threshold": "raw", "data": "provider", "hypothesis_id": "H2"}],
        "required_data": ["consensus"], "research_cost": {"hours": 2, "data_access": "low"},
        "decision_impact": {"if_true": "add", "if_false": "drop"},
        "priority_tier": "B", "priority_rank": 1, "rationale": "test",
        "data_quality": {"score": 0.7}, "evidence_gaps": [],
        "evidence_for": [{"claim": "fact", "class": "observed_fact", "source": "db",
                          "available_at": "2024-01-01"}],
        "evidence_against": [{"claim": "counter", "class": "unknown", "source": "gap",
                             "available_at": "2024-01-01"}],
        "evaluation_id": "D:2024-01-01:US_EQ_SPY", "method": "D_v2_triage",
    }
    validate_research_candidate(c)
    c["competing_hypotheses"] = c["competing_hypotheses"][:1]
    with pytest.raises(ContractError):
        validate_research_candidate(c)


def test_scoring_and_handoff_contracts():
    validate_v1_weights(load_yaml_config("scoring.yaml")["weights"])
    validate_handoff_result({"status": "not_ok", "semantic_status": "refused", "returncode": 0})
    with pytest.raises(ContractError):
        validate_handoff_result({"status": "ok", "semantic_status": "refused", "returncode": 0})



@pytest.mark.skipif(__import__("os").environ.get("GOE_SLOW") != "1",
                    reason="slow real-data V2 integration; run with GOE_SLOW=1")
def test_research_v2_real_scan_contract():
    from pathlib import Path
    if not Path("data/goe.db").exists():
        pytest.skip("no real DB")
    from goe.db import Store
    from goe.research_triage import run_triage

    rows = run_triage(Store("data/goe.db"), as_of="2026-11-13", max_candidates=3)
    assert rows
    for r in rows:
        validate_research_candidate(r.to_dict())
        assert r.priority_rank >= (1 if r.priority_tier != "intelligence" else 0)
        assert len(r.competing_hypotheses) >= 2
    assert any(r.priority_tier in ("A", "B", "C") for r in rows)


def test_release_gate_refuses_dirty_or_untested(monkeypatch, store):
    import goe.release as rel

    monkeypatch.setattr(rel, "_git", lambda *a: "M file")
    with pytest.raises(rel.ReleaseError, match="dirty"):
        rel.build_manifest(store, test_count=1)
    monkeypatch.setattr(rel, "_git", lambda *a: "")
    with pytest.raises(rel.ReleaseError, match="test_count"):
        rel.build_manifest(store, test_count=None)
