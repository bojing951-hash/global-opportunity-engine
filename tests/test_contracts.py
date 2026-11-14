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


def test_anomaly_contract_synthetic():
    """Contract test uses an in-memory-style record; no developer DB dependency."""
    rec = {
        "anomaly_id": "A-1", "date": "2024-01-02", "available_date": "2024-01-02",
        "detector": "price_return_shock", "family": "price", "entity_id": "US_EQ_SPY",
        "entity_kind": "instrument", "direction": "down", "window": "1d",
        "measure": "return_z", "magnitude": -4.0, "score": 0.9,
        "evidence": {"threshold": -3, "formula": "z(ret)", "raw": -4.0,
                     "source": {"id": "yahoo", "tier": "exchange"},
                     "data_quality": 0.9},
    }
    validate_anomaly_records([rec])
    bad = dict(rec, evidence={})
    with pytest.raises(ContractError):
        validate_anomaly_records([bad])



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



@pytest.mark.realdata
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


def test_release_rejects_missing_or_forged_proof(monkeypatch, store, tmp_path):
    import hashlib, json
    import goe.release as rel

    monkeypatch.setattr(rel, "_git", lambda *a: "abc123")
    with pytest.raises(rel.ReleaseError, match="missing"):
        rel.verify_test_proof(tmp_path / "nope.json")

    log = tmp_path / "run.log"
    log.write_text("167 passed, 1 skipped in 60s\n", encoding="utf-8")
    proof = {"schema": "goe-test-proof/v1", "git_commit": "abc123", "git_dirty": False,
             "command": ["python", "-m", "pytest", "tests", "-q"], "exit_code": 0,
             "passed": 167, "failed": 0, "errors": 0, "skipped": 1,
             "log_path": str(log), "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()}
    path = tmp_path / "proof.json"
    path.write_text(json.dumps(proof), encoding="utf-8")
    assert rel.verify_test_proof(path)["passed"] == 167
    forged = dict(proof, passed=9999)
    path.write_text(json.dumps(forged), encoding="utf-8")
    with pytest.raises(rel.ReleaseError, match="disagrees|hash"):
        rel.verify_test_proof(path)
