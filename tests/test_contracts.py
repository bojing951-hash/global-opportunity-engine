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
             "evidence_for": [{"claim": "measured factor", "class": "statistical_association",
                               "source": "derived", "available_at": "2024-01-01",
                               "discriminating": True}],
             "evidence_against": []},
            {"id": "H2", "label": "data artifact", "type": "data_artifact",
             "status": "open", "implications": "y",
             "evidence_for": [{"claim": "measured artifact", "class": "statistical_association",
                               "source": "derived", "available_at": "2024-01-01",
                               "discriminating": True}],
             "evidence_against": []}],
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
        "research_readiness": "evidence_ok",
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


def _v3_proof(**over):
    import sys

    from goe.release import CATEGORY_MARKERS, command_template

    base = {
        "schema": "goe-test-proof/v4",
        "git_commit": "abc123",
        "git_dirty": False,
        "category": "offline",
        "marker_expr": CATEGORY_MARKERS["offline"],
        "command_template": command_template("offline"),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "exit_code": 0,
        "passed": 179,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "required": {"count": 179, "sha256": "deadbeef"},
        "executed": {"count": 179, "sha256": "deadbeef"},
        "log_path": "audit/test_evidence/x.log",
        "log_sha256": "deadbeef",
        "junit_path": "audit/test_evidence/x.xml",
        "junit_sha256": "deadbeef",
    }
    base.update(over)
    return base


def test_release_rejects_missing_or_forged_proof(monkeypatch, store, tmp_path):
    import json

    import goe.release as rel

    monkeypatch.setattr(rel, "_git", lambda *a, **k: "abc123")
    monkeypatch.setattr(rel, "_git_root", lambda *a, **k: tmp_path.resolve())
    monkeypatch.setattr(rel, "_dirty_code", lambda **k: False)
    with pytest.raises(rel.ReleaseError, match="missing"):
        rel.verify_test_proof(tmp_path / "nope.json")

    # legacy v1 evidence is no longer accepted
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({"schema": "goe-test-proof/v1"}), encoding="utf-8")
    with pytest.raises(rel.ReleaseError, match="unknown test proof schema"):
        rel.verify_test_proof(legacy)

    # v2 but with an untrusted selector injected into the command template
    poisoned = tmp_path / "poisoned.json"
    cmd = list(rel.command_template("offline")) + ["--ignore=tests/test_research_v2.py"]
    poisoned.write_text(json.dumps(_v3_proof(command_template=cmd)), encoding="utf-8")
    with pytest.raises(rel.ReleaseError, match="forbidden selector|canonical"):
        rel.verify_test_proof(poisoned)


def test_release_rejects_shell_spoof_and_rename_dirty(monkeypatch, tmp_path):
    import json

    import goe.release as rel

    real_dirty = rel._dirty_code
    monkeypatch.setattr(rel, "_git", lambda *a, **kk: "abc123")
    monkeypatch.setattr(rel, "_git_root", lambda *a, **kk: tmp_path.resolve())
    monkeypatch.setattr(rel, "_dirty_code", lambda **k: False)
    p = tmp_path / "proof.json"
    p.write_text(json.dumps(_v3_proof(command_template=["sh", "-c", "printf 179", "tests"])),
                 encoding="utf-8")
    with pytest.raises(rel.ReleaseError, match="forbidden selector|canonical"):
        rel.verify_test_proof(p)
    monkeypatch.setattr(rel, "_git", lambda *a, **kk: "R  audit/test_evidence/x -> goe/payload.py")
    assert real_dirty() is True


def test_release_rejects_reverse_rename_and_subset(monkeypatch, tmp_path):
    import json

    import goe.release as rel

    real_dirty = rel._dirty_code
    monkeypatch.setattr(rel, "_git", lambda *a, **kk: "R  goe/cli.py -> audit/test_evidence/cli.py")
    assert real_dirty() is True
    monkeypatch.setattr(rel, "_git", lambda *a, **kk: "abc123")
    monkeypatch.setattr(rel, "_git_root", lambda *a, **kk: tmp_path.resolve())
    monkeypatch.setattr(rel, "_dirty_code", lambda **k: False)
    # narrowing by marker is rejected even when the marker strings look plausible
    p = tmp_path / "proof"
    subset = list(rel.command_template("offline"))
    subset[subset.index("-m") + 1] = "not network and not realdata and not smoke"
    p.write_text(json.dumps(_v3_proof(command_template=subset)), encoding="utf-8")
    with pytest.raises(rel.ReleaseError, match="forbidden selector|canonical"):
        rel.verify_test_proof(p)
    # -k subsetting is rejected as well
    k_subset = ["python", "-m", "pytest", "tests", "-k", "smoke"]
    p.write_text(json.dumps(_v3_proof(command_template=k_subset)), encoding="utf-8")
    with pytest.raises(rel.ReleaseError, match="forbidden selector|canonical"):
        rel.verify_test_proof(p)


def test_research_tier_requires_two_measured_discriminators():
    c = {
        "research_id": "R-2", "as_of": "2024-01-01", "market": "US",
        "asset_class": "equity_etf", "instruments": ["US_EQ_SPY"],
        "observed_phenomenon": "x", "materiality": "high",
        "competing_hypotheses": [
            {"id": "H1", "label": "a", "type": "risk_premium", "status": "open",
             "implications": "", "evidence_for": [{"claim": "m", "class": "statistical_association",
             "source": "d", "available_at": "2024-01-01", "discriminating": True}],
             "evidence_against": []},
            {"id": "H2", "label": "b", "type": "data_artifact", "status": "open",
             "implications": "", "evidence_for": [], "evidence_against": []}],
        "evidence": [{"claim": "m", "class": "statistical_association", "source": "d",
                      "available_at": "2024-01-01"}],
        "critical_unknowns": ["x"],
        "falsification_conditions": [{"test": "a", "threshold": "1", "data": "d", "hypothesis_id": "H1"},
                                     {"test": "b", "threshold": "2", "data": "d", "hypothesis_id": "H2"}],
        "required_data": [], "research_cost": {"hours": 2, "data_access": "low"},
        "decision_impact": {"if_true": "a", "if_false": "b"},
        "priority_tier": "B", "priority_rank": 1, "rationale": "x",
        "data_quality": {}, "evidence_gaps": [], "evidence_for": [{"claim": "m"}],
        "evidence_against": [{"claim": "u"}], "evaluation_id": "D:x:y", "method": "D_v2_triage",
        "research_readiness": "evidence_ok",
    }
    with pytest.raises(ContractError):
        validate_research_candidate(c)
