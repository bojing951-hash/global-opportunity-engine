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
    ({"run_ok": True, "evidence_index": [{"id": 1}],
      "layers": {"L1_事实层": {"available": True, "rows": [{"fact": 1}]}},
      "steps": [{"step": "S8_grounded_qa", "semantic_ok": True,
                 "envelope": {"data": {"status": "answered"}}}]}, "ok_valid"),
    ({"run_ok": True, "evidence_index": [{"id": 1}], "layers": {"L2_机构观点层": {"views": {"n": 17}}},
      "steps": [{"step": "S8_grounded_qa", "semantic_ok": False,
                 "envelope": {"data": {"status": "out_of_scope"}}}]}, "refused"),
    ({"run_ok": False, "evidence_index": [], "steps": []}, "rejected"),
    ({"run_ok": True, "evidence_index": [], "layers": {"L1_事实层": {"available": True, "rows": []}},
      "steps": [{"step": "S8_grounded_qa", "semantic_ok": True,
                 "envelope": {"data": {"status": "answered"}}}]}, "insufficient_data"),
    ({"run_ok": True, "evidence_index": [{"id": 1}],
      "steps": [{"step": "S8_grounded_qa", "semantic_ok": False}]}, "partial"),
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


def test_region_outage_blocks_even_if_global_coverage_looks_ok(store):
    """A dead market must not be hidden by a healthy global freshness ratio."""
    import pandas as pd

    from goe.readiness import check_data_readiness

    stale = pd.DataFrame([
        {"instrument_id": iid, "date": "2024-10-01", "close": 100.0, "adj_close": 100.0,
         "source_id": "yahoo", "fetched_at": "2024-10-01T22:00:00Z"}
        for iid in ("CN_EQ_CSI500", "CN_EQ_CSI1000", "CN_EQ_ETF300")
    ])
    store.upsert_prices(stale)
    res = check_data_readiness(store, as_of=END_DATE, min_coverage=0.0)
    assert res.ok is False
    assert any("CN 市场数据失效" in c for c in res.critical), res.critical
    assert res.regions["CN"]["coverage"] < 0.5


def test_stale_curve_is_critical_not_silent(store):
    from goe.readiness import check_data_readiness

    store.conn.execute("DELETE FROM indicators WHERE series_id LIKE 'UST:%' AND date > '2023-06-30'")
    store.conn.commit()
    res = check_data_readiness(store, as_of=END_DATE, min_coverage=0.0)
    assert res.ok is False
    assert any("收益率曲线" in c or "曲线" in c for c in res.critical), res.critical
    assert res.degraded is True


def test_stale_macro_is_degraded_and_disclosed(store):
    from goe.readiness import check_data_readiness

    store.conn.execute("DELETE FROM indicators WHERE series_id='US_CPI' AND date > '2023-06-30'")
    store.conn.commit()
    res = check_data_readiness(store, as_of=END_DATE, min_coverage=0.0)
    assert any("新鲜度" in w or "宏观序列" in w for w in res.warnings), res.warnings
    assert res.degraded is True


def test_historical_asof_is_not_blocked_by_future_dates(store):
    """Regional freshness must be computed as-of, not against the latest DB row."""
    from goe.readiness import check_data_readiness

    res = check_data_readiness(store, as_of="2024-06-28", min_coverage=0.0)
    assert res.ok is True, res.critical
    for region, info in res.regions.items():
        if info["age_days"] is None:
            continue  # a configured market with no rows at all is warned/critical separately
        assert info["last_date"] <= "2024-06-28", (region, info)
        assert info["age_days"] >= 0, (region, info)


def test_historical_readiness_uses_latest_available_publication(store):
    """Do not call the newest (unpublished) print stale; use the newest AVAILABLE one."""
    from goe.readiness import check_data_readiness

    res = check_data_readiness(store, as_of="2024-06-28", min_coverage=0.0)
    assert not any("US_CPI" in x for x in res.stale_indicators), res.stale_indicators
    # 2024-05-01 + 45d = 2024-06-15 is available at 2024-06-28.
    assert res.fresh_macro_series >= 1


def test_pipeline_implicit_latest_uses_wall_clock(tmp_path):
    """`run_scan` with no --as-of must not bypass the stale-wall-clock guard."""
    import goe.pipeline as pipeline
    from conftest import seed_store

    store = seed_store(tmp_path / "stale.db")
    try:
        with pytest.raises(ScanBlockedError):
            pipeline.run_scan(store, as_of=None, ingest=False, export=False,
                              out_dir=tmp_path, readiness_min_coverage=0.0)
    finally:
        store.close()


def test_missing_region_is_not_hidden_by_global_coverage(store):
    from goe.config import load_universe
    from goe.readiness import check_data_readiness

    uk_ids = [iid for iid, spec in load_universe().instruments.items() if spec.region == "UK"]
    assert len(uk_ids) >= 3
    store.conn.execute(
        f"DELETE FROM prices WHERE instrument_id IN ({','.join('?' for _ in uk_ids)})", tuple(uk_ids))
    store.conn.commit()
    res = check_data_readiness(store, as_of=END_DATE, min_coverage=0.8)
    assert any("UK" in c and "市场" in c for c in res.critical), res.critical


def test_single_stale_series_is_disclosure_not_global_deep_cap(store):
    """One stale optional series must not set critical_degraded (which caps all deep research)."""
    from goe.config import load_macro
    from goe.readiness import check_data_readiness

    ids = list(load_macro())[:7]
    for sid in ids:
        store.conn.execute("INSERT OR REPLACE INTO indicators(series_id,date,value,unit,source_id,fetched_at) "
                           "VALUES(?,?,?,?,?,?)", (sid, "2024-09-01", 1.0, "index", "test",
                                                   "2024-01-01T22:00:00Z"))
    store.conn.execute("INSERT OR REPLACE INTO indicators(series_id,date,value,unit,source_id,fetched_at) "
                       "VALUES(?,?,?,?,?,?)", (ids[-1], "2023-01-01", 1.0, "index", "test", "2023-01-01T22:00:00Z"))
    store.conn.commit()
    res = check_data_readiness(store, as_of=END_DATE, min_coverage=0.0)
    assert res.degraded is True
    assert res.critical_degraded is False, res.warnings


def test_small_market_stale_is_warned(store):
    from goe.readiness import check_data_readiness

    store.conn.execute("DELETE FROM prices WHERE instrument_id='CA_EQ_TSX'")
    store.conn.commit()
    res = check_data_readiness(store, as_of=END_DATE, min_coverage=0.0)
    assert any("CA" in w for w in res.warnings), res.warnings
