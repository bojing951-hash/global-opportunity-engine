from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from goe.db import Store
from goe.scan_evidence import ScanEvidenceError, verify_scan_evidence


def make_scan(tmp_path):
    s = Store(tmp_path / "scan.db")
    as_of = "2026-01-03"
    for src in ("yahoo", "test"):
        s.conn.execute("INSERT INTO sources(source_id,name,kind,tier) VALUES(?,?,?,?)",
                       (src, src, "price" if src == "yahoo" else "indicator", "exchange"))
    s.conn.execute("""INSERT INTO prices(instrument_id,date,open,high,low,close,adj_close,volume,source_id,fetched_at,run_id)
                      VALUES('US_EQ_SPY',?,1,1,1,100,100,1000,'yahoo','2026-01-03T20:00:00Z','scan-1')""", (as_of,))
    for sid in ("UST:2Y", "UST:10Y", "US_CPI", "US_POLICY_RATE"):
        s.conn.execute("""INSERT INTO indicators(series_id,date,value,unit,source_id,fetched_at,run_id)
                          VALUES(?,?,1,'pct','test','2026-01-03T20:00:00Z','scan-1')""", (sid, as_of))
    s.conn.execute("""INSERT INTO anomalies(anomaly_id,as_of,available_date,detector,family,instrument_id,
                      direction,magnitude,score,percentile,window,evidence_json,fingerprint,run_id,created_at)
                      VALUES('A1',?,'2026-01-03','price_return_shock','price','US_EQ_SPY','down',-0.1,0.9,
                      0.1,'1d','{}','fp1','scan-1','2026-01-03T20:00:00Z')""", (as_of,))
    s.conn.commit()
    config = s.config_fingerprint(); data = s.data_fingerprint(as_of)
    out_fp = s.scan_output_fingerprint("scan-1")
    stats = {"data_readiness": {"ok": True, "price_rows": 1, "indicator_rows": 4},
             "output_fingerprint": out_fp,
             "ingest": {"status": "offline"},
             "anomalies": {"n": 1}, "transmissions": {"n_activated": 0},
             "opportunities": {"created": 0}}
    s.conn.execute("""INSERT INTO scan_runs(scan_id,as_of,mode,started_at,finished_at,status,config_hash,data_hash,stats_json)
                      VALUES('scan-1',?,'offline','2026-01-03T20:00:00Z','2026-01-03T20:01:00Z','success',?,?,?)""",
                   (as_of, config, data, json.dumps(stats)))
    s.conn.commit()
    return s, as_of, config, data, stats


def test_valid_scan_evidence_passes(tmp_path, monkeypatch):
    s, as_of, _, _, _ = make_scan(tmp_path)
    monkeypatch.setattr("goe.scan_evidence.check_data_readiness",
                        lambda *a, **k: SimpleNamespace(ok=True, critical=[]))
    ev = verify_scan_evidence(s, reports_dir=tmp_path / "reports",
                              exports_dir=tmp_path / "exports", require_reports=False, reference_date="2026-01-03")
    assert ev.scan_id == "scan-1" and ev.prices == 1 and ev.indicators == 4


def test_empty_or_fake_scan_is_rejected(tmp_path, monkeypatch):
    empty = Store(tmp_path / "empty.db")
    with pytest.raises(ScanEvidenceError, match="no scan_runs"):
        verify_scan_evidence(empty, reports_dir=tmp_path, require_reports=False, reference_date="2026-01-03")
    s, as_of, config, data, _ = make_scan(tmp_path)
    monkeypatch.setattr("goe.scan_evidence.check_data_readiness",
                        lambda *a, **k: SimpleNamespace(ok=True, critical=[]))
    s.conn.execute("UPDATE scan_runs SET config_hash='FAKE_CONFIG',data_hash='FAKE_DATA'")
    s.conn.commit()
    with pytest.raises(ScanEvidenceError, match="config_hash"):
        verify_scan_evidence(s, reports_dir=tmp_path, require_reports=False, reference_date="2026-01-03")
    s.conn.execute("UPDATE scan_runs SET config_hash=?,data_hash=? WHERE scan_id='scan-1'", (config, data))
    s.conn.execute("UPDATE prices SET close=101 WHERE instrument_id='US_EQ_SPY'")
    s.conn.commit()
    with pytest.raises(ScanEvidenceError, match="data_hash"):
        verify_scan_evidence(s, reports_dir=tmp_path, require_reports=False, reference_date="2026-01-03")


def test_scan_asof_stats_and_report_mismatch_rejected(tmp_path, monkeypatch):
    s, as_of, config, data, stats = make_scan(tmp_path)
    monkeypatch.setattr("goe.scan_evidence.check_data_readiness",
                        lambda *a, **k: SimpleNamespace(ok=True, critical=[]))
    s.conn.execute("UPDATE scan_runs SET as_of='2026-01-02'")
    s.conn.commit()
    with pytest.raises(ScanEvidenceError, match="as_of"):
        verify_scan_evidence(s, reports_dir=tmp_path, require_reports=False, reference_date="2026-01-03")
    s.conn.execute("UPDATE scan_runs SET as_of='2026-01-03'")
    bad = dict(stats); bad["anomalies"] = {"n": 99}
    s.conn.execute("UPDATE scan_runs SET stats_json=?", (json.dumps(bad),)); s.conn.commit()
    with pytest.raises(ScanEvidenceError, match="anomaly count"):
        verify_scan_evidence(s, reports_dir=tmp_path, require_reports=False, reference_date="2026-01-03")
    s.conn.execute("UPDATE scan_runs SET stats_json=?", (json.dumps(stats),)); s.conn.commit()
    with pytest.raises(ScanEvidenceError, match="artifact missing"):
        verify_scan_evidence(s, reports_dir=tmp_path / "missing", require_reports=True, reference_date="2026-01-03")


def _write_artifacts(tmp_path, config, data, out_fp="", *, wrong_scan=False, wrong_count=False):
    rep = tmp_path / "reports"; exp = tmp_path / "exports"
    rep.mkdir(); exp.mkdir()
    sid = "scan-1"
    (rep / "report_2026-01-03.md").write_text(
        f"scan {sid} as_of 2026-01-03 config {config[:16]} data {data[:16]}\n", encoding="utf-8")
    (rep / "scan_2026-01-03.json").write_text(json.dumps({
        "meta": {"scan_id": sid, "as_of": "2026-01-03", "config_hash": "WRONG" if wrong_scan else config,
                 "data_hash": data, "output_fingerprint": out_fp},
        "anomalies": [{"id": 1}] * (2 if wrong_count else 1), "opportunities": []}), encoding="utf-8")
    (exp / "pipeline_2026-01-03.json").write_text(json.dumps({
        "provenance": {"config_hash": config, "data_hash": data},
        "summary": {"n_opportunities": 0}, "opportunities": []}), encoding="utf-8")
    return rep, exp


def test_artifacts_missing_mismatched_or_valid(tmp_path, monkeypatch):
    s, as_of, config, data, _ = make_scan(tmp_path)
    monkeypatch.setattr("goe.scan_evidence.check_data_readiness",
                        lambda *a, **k: SimpleNamespace(ok=True, critical=[]))
    rep, exp = _write_artifacts(tmp_path, config, data, s.scan_output_fingerprint("scan-1"))
    ev = verify_scan_evidence(s, reports_dir=rep, exports_dir=exp, require_reports=True, reference_date="2026-01-03")
    assert ev.scan_id == "scan-1"
    # fake scan id in reports
    (rep / "report_2026-01-03.md").write_text("no provenance", encoding="utf-8")
    with pytest.raises(ScanEvidenceError, match="provenance"):
        verify_scan_evidence(s, reports_dir=rep, exports_dir=exp, require_reports=True, reference_date="2026-01-03")
    # wrong count in scan json
    (rep / "report_2026-01-03.md").write_text(
        f"scan scan-1 as_of 2026-01-03 config {config[:16]} data {data[:16]}\n", encoding="utf-8")
    (rep / "scan_2026-01-03.json").write_text(json.dumps({
        "meta": {"scan_id": "scan-1", "as_of": "2026-01-03", "config_hash": config, "data_hash": data,
                 "output_fingerprint": s.scan_output_fingerprint("scan-1")},
        "anomalies": [{"id": 1}, {"id": 2}], "opportunities": []}), encoding="utf-8")
    with pytest.raises(ScanEvidenceError, match="anomaly count"):
        verify_scan_evidence(s, reports_dir=rep, exports_dir=exp, require_reports=True, reference_date="2026-01-03")


def test_old_success_or_partial_ingest_is_rejected(tmp_path, monkeypatch):
    s, as_of, config, data, stats = make_scan(tmp_path)
    monkeypatch.setattr("goe.scan_evidence.check_data_readiness",
                        lambda *a, **k: SimpleNamespace(ok=True, critical=[]))
    s.conn.execute("""INSERT INTO scan_runs(scan_id,as_of,mode,started_at,finished_at,status,config_hash,data_hash,stats_json)
                      VALUES('scan-new',?,'offline','2026-01-03T21:00:00Z','2026-01-03T21:01:00Z','failed',?,?,?)""",
                   (as_of, config, data, json.dumps(stats)))
    s.conn.commit()
    with pytest.raises(ScanEvidenceError, match="latest scan"):
        verify_scan_evidence(s, reports_dir=tmp_path, require_reports=False, reference_date="2026-01-03")
    s.conn.execute("DELETE FROM scan_runs WHERE scan_id='scan-new'")
    bad = dict(stats); bad["ingest"] = {"status": "partial"}
    s.conn.execute("UPDATE scan_runs SET stats_json=?", (json.dumps(bad),)); s.conn.commit()
    with pytest.raises(ScanEvidenceError, match="ingest status"):
        verify_scan_evidence(s, reports_dir=tmp_path, require_reports=False, reference_date="2026-01-03")


def test_build_manifest_rejects_empty_scan_store(monkeypatch, tmp_path):
    import goe.release as rel

    fake_proof = {"category": "offline", "passed": 1, "skipped": 0,
                  "required": {"sha256": "x"}, "executed": {"sha256": "x"},
                  "command_template": [], "git_commit": "x"}
    monkeypatch.setattr(rel, "verify_test_proof", lambda *a, **k: fake_proof)
    monkeypatch.setattr(rel, "_dirty_code", lambda *a, **k: False)
    with pytest.raises(rel.ReleaseError, match="verified scan evidence"):
        rel.build_manifest(Store(tmp_path / "empty.db"), proof_path="unused",
                           out_dir=tmp_path / "rel", require_clean=False)


def test_next_day_fetch_is_legitimate_but_stale_scan_is_not(tmp_path, monkeypatch):
    s, as_of, config, data, stats = make_scan(tmp_path)
    monkeypatch.setattr("goe.scan_evidence.check_data_readiness",
                        lambda *a, **k: SimpleNamespace(ok=True, critical=[]))
    # simulate an incremental fetch the next morning, then a scan later that day
    s.conn.execute("UPDATE prices SET fetched_at='2026-01-04T01:00:00Z'")
    s.conn.execute("UPDATE scan_runs SET started_at='2026-01-04T02:00:00Z', finished_at='2026-01-04T02:01:00Z'")
    s.conn.commit()
    assert verify_scan_evidence(s, reports_dir=tmp_path, require_reports=False,
                                reference_date="2026-01-04").scan_id == "scan-1"
    with pytest.raises(ScanEvidenceError, match="stale"):
        verify_scan_evidence(s, reports_dir=tmp_path, require_reports=False,
                             reference_date="2026-01-20")


def test_ohlcv_and_derived_output_tamper_is_rejected(tmp_path, monkeypatch):
    s, as_of, config, data, stats = make_scan(tmp_path)
    monkeypatch.setattr("goe.scan_evidence.check_data_readiness",
                        lambda *a, **k: SimpleNamespace(ok=True, critical=[]))
    s.conn.execute("UPDATE prices SET open=2 WHERE instrument_id='US_EQ_SPY'")
    s.conn.commit()
    with pytest.raises(ScanEvidenceError, match="data_hash"):
        verify_scan_evidence(s, reports_dir=tmp_path, require_reports=False,
                             reference_date=as_of)
    s.conn.execute("UPDATE prices SET open=1 WHERE instrument_id='US_EQ_SPY'")
    s.conn.execute("UPDATE anomalies SET score=0.1 WHERE anomaly_id='A1'")
    s.conn.commit()
    with pytest.raises(ScanEvidenceError, match="output content"):
        verify_scan_evidence(s, reports_dir=tmp_path, require_reports=False,
                             reference_date=as_of)
