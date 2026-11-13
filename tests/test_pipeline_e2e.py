"""End-to-end offline scan on the synthetic database.

``run_scan`` writes exports through ``config.exports_dir()``; the test
monkeypatches that seam so nothing is ever written to the repository's
``exports/`` directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import goe.pipeline as pipeline
from conftest import END_DATE


def _run_scan(store, tmp_path, monkeypatch):
    export_dir = tmp_path / "exports"
    monkeypatch.setattr(pipeline, "exports_dir", lambda: export_dir)
    return pipeline.run_scan(
        store,
        as_of=END_DATE,
        ingest=False,
        out_dir=tmp_path / "reports",
        export=True,
    )


def test_run_scan_produces_report_scan_json_and_exports(store, tmp_path, monkeypatch):
    result = _run_scan(store, tmp_path, monkeypatch)

    assert result.status == "success"
    assert result.as_of == END_DATE
    assert result.scan_id
    assert result.stats["feature_rows"] > 0
    assert result.stats["anomalies"]["n"] > 0
    assert result.stats["opportunities"]["created"] >= 1

    report_path = Path(result.report_paths["markdown"])
    assert report_path.exists()
    assert report_path.name == f"report_{END_DATE}.md"
    report = report_path.read_text(encoding="utf-8")
    assert "投资机会候选池" in report
    assert "数据质量" in report
    assert "不是交易建议" in report

    scan_json = Path(result.report_paths["json"])
    assert scan_json.exists()
    assert scan_json.name == f"scan_{END_DATE}.json"
    scan_payload = json.loads(scan_json.read_text(encoding="utf-8"))
    assert scan_payload["meta"]["as_of"] == END_DATE
    assert scan_payload["meta"]["config_hash"]
    assert "opportunities" in scan_payload

    exports = {key: Path(value) for key, value in result.export_paths.items() if key != "tasks"}
    for key in ("pipeline", "queue", "schema"):
        assert exports[key].exists(), key
        assert tmp_path in exports[key].parents
    assert len(result.export_paths["tasks"]) >= 1
    for task_path in result.export_paths["tasks"]:
        assert Path(task_path).exists()
        assert tmp_path in Path(task_path).parents
    pipeline_payload = json.loads(exports["pipeline"].read_text(encoding="utf-8"))
    assert pipeline_payload["summary"]["n_opportunities"] >= 1

    scan = store.conn.execute(
        "SELECT * FROM scan_runs WHERE scan_id=?", (result.scan_id,)
    ).fetchone()
    assert scan["status"] == "success"
    assert scan["as_of"] == END_DATE
    assert scan["config_hash"]
    assert scan["data_hash"]
    assert scan["finished_at"]


def test_run_scan_twice_does_not_duplicate_opportunities(store, tmp_path, monkeypatch):
    first = _run_scan(store, tmp_path, monkeypatch)
    second = _run_scan(store, tmp_path, monkeypatch)

    assert first.status == second.status == "success"
    rows = store.scalar("SELECT COUNT(*) FROM opportunities")
    distinct = store.scalar("SELECT COUNT(DISTINCT fingerprint) FROM opportunities")
    assert rows == distinct
    duplicates = store.conn.execute(
        "SELECT fingerprint, COUNT(*) AS n FROM opportunities GROUP BY fingerprint HAVING n > 1"
    ).fetchall()
    assert duplicates == []

    # The second scan refreshes the same phenomenon rather than creating a new one.
    assert second.stats["opportunities"]["created"] == 0
    assert second.stats["opportunities"]["refreshed"] >= 1
    event_types = {r[0] for r in store.conn.execute(
        "SELECT event_type FROM opportunity_events")}
    assert {"created", "refreshed"} <= event_types

    success_runs = store.conn.execute(
        "SELECT COUNT(*) FROM scan_runs WHERE status='success' AND config_hash != '' AND data_hash != ''"
    ).fetchone()[0]
    assert success_runs == 2
