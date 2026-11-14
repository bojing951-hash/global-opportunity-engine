"""Readiness gate (P1-07) and downstream semantic status (P1-06)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from conftest import END_DATE, seed_store
from goe.integration.ia_adapter import parse_research_artifact
from goe.readiness import ScanBlockedError, check_data_readiness


def _write_report(path, payload):
    path.mkdir(parents=True, exist_ok=True)
    (path / "report.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@pytest.mark.parametrize("payload,expected", [
    ({"run_ok": True, "evidence_index": [{"id": 1}, {"id": 2}], "steps": [{"semantic_ok": True}]}, "ok_valid"),
    ({"run_ok": False, "evidence_index": [], "steps": []}, "rejected"),
    ({"run_ok": True, "evidence_index": [], "steps": [{"semantic_ok": True}]}, "insufficient_data"),
    ({"run_ok": True, "evidence_index": [{"id": 1}], "steps": [{"semantic_ok": False}]}, "partial"),
])
def test_parse_research_artifact_semantics(tmp_path, payload, expected):
    _write_report(tmp_path, payload)
    res = parse_research_artifact(tmp_path)
    assert res["semantic_status"] == expected


def test_parse_research_artifact_missing_report_is_partial(tmp_path):
    res = parse_research_artifact(tmp_path)
    assert res["semantic_status"] == "partial"
    assert res["run_ok"] is None


def test_stdout_envelope_with_ok_false_is_not_success(tmp_path):
    res = parse_research_artifact(tmp_path, stdout='{"ok": false, "n_evidence_rows": 0}')
    assert res["semantic_status"] == "rejected"
    assert res["run_ok"] is False


def test_readiness_blocks_stale_or_incomplete_market(tmp_path):
    store = seed_store(tmp_path / "r.db")
    try:
        # explicit as-of matches the stored data -> ready
        ok = check_data_readiness(store, as_of=END_DATE, today=END_DATE, min_coverage=0.0)
        assert ok.ok, ok.critical
        # implicit latest but wall clock far in the future -> blocked
        stale = check_data_readiness(store, as_of=None, today="2026-11-14", min_coverage=0.0)
        assert not stale.ok
        assert any("天" in c for c in stale.critical)
    finally:
        store.close()


def test_readiness_coverage_gate(tmp_path):
    store = seed_store(tmp_path / "r2.db")
    try:
        store.conn.execute("DELETE FROM prices WHERE instrument_id NOT IN ('US_EQ_SPY','US_EQ_QQQ')")
        store.conn.commit()
        res = check_data_readiness(store, as_of=END_DATE, today=END_DATE)
        assert not res.ok
        assert any("覆盖率" in c for c in res.critical)
    finally:
        store.close()


def test_pipeline_blocks_when_price_ingest_fails(tmp_path, monkeypatch):
    import goe.pipeline as pipeline

    store = seed_store(tmp_path / "r3.db")
    try:
        class FailingIngestor:
            def __init__(self, *a, **k):
                pass

            def run(self, mode="daily"):
                return {"status": "failed", "prices_error": "provider down", "price_ok": False,
                        "indicator_ok": True}

        monkeypatch.setattr(pipeline, "Ingestor", FailingIngestor)
        with pytest.raises(ScanBlockedError):
            pipeline.run_scan(store, ingest=True, export=False, out_dir=tmp_path)
    finally:
        store.close()
