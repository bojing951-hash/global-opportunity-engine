"""Verified scan evidence for release manifests.

A `scan_runs.status='success'` row is only a claim. This module independently
reconstructs the evidence from the database, config, reports and exports and
rejects stale, forged or internally inconsistent scans.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import pandas as pd

from . import project_root
from .db import Store
from .readiness import check_data_readiness

CORE_SERIES = {
    "UST:2Y": 15,
    "UST:10Y": 15,
    "US_CPI": 90,
    "US_POLICY_RATE": 120,
}


class ScanEvidenceError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject(msg: str) -> None:
    raise ScanEvidenceError(msg)


def _stat_int(d: dict | None, key: str) -> int:
    value = (d or {}).get(key)
    if value is None:
        return -1
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


@dataclass
class ScanEvidence:
    scan_id: str
    as_of: str
    mode: str
    config_hash: str
    data_hash: str
    prices: int
    indicators: int
    anomalies: int
    transmissions: int
    opportunities: int
    report_path: str
    scan_json_path: str
    pipeline_path: str
    report_sha256: str
    scan_json_sha256: str
    pipeline_sha256: str
    readiness_ok: bool
    ingest_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_scan_evidence(store: Store, *, reports_dir: str | Path | None = None,
                         exports_dir: str | Path | None = None,
                         require_reports: bool = True) -> ScanEvidence:
    root = project_root()
    reports = Path(reports_dir) if reports_dir else root / "reports"
    exports = Path(exports_dir) if exports_dir else root / "exports"

    scans = store.conn.execute(
        "SELECT * FROM scan_runs ORDER BY started_at DESC LIMIT 2").fetchall()
    if not scans:
        _reject("no scan_runs evidence")
    scan = scans[0]
    if scan["status"] != "success":
        _reject(f"latest scan is not success: {scan['scan_id']} ({scan['status']})")
    if not scan["finished_at"]:
        _reject("latest scan has no finished_at")
    if len(scans) > 1 and scans[1]["started_at"] > scan["started_at"]:
        _reject("scan ordering is inconsistent")

    as_of = str(scan["as_of"])
    price_n = int(store.scalar("SELECT COUNT(*) FROM prices WHERE date<=?", (as_of,)) or 0)
    ind_n = int(store.scalar("SELECT COUNT(*) FROM indicators WHERE date<=?", (as_of,)) or 0)
    if price_n <= 0:
        _reject("no price observations at scan as_of")
    if ind_n <= 0:
        _reject("no indicator observations at scan as_of")
    last_price = store.scalar("SELECT MAX(date) FROM prices WHERE date<=?", (as_of,))
    if last_price != as_of:
        _reject(f"scan as_of {as_of} != last price date {last_price}")

    # Independent hashes, not values copied from scan_runs.
    config_hash = store.config_fingerprint()
    data_hash = store.data_fingerprint(as_of)
    if scan["config_hash"] != config_hash:
        _reject("scan config_hash does not match current config")
    if scan["data_hash"] != data_hash:
        _reject("scan data_hash does not match recomputed DB content")

    readiness = check_data_readiness(store, as_of=as_of)
    if not readiness.ok:
        _reject("data readiness failed: " + "; ".join(readiness.critical))
    try:
        stats = json.loads(scan["stats_json"] or "{}")
    except Exception as exc:
        raise ScanEvidenceError(f"scan stats_json invalid: {exc}") from exc
    rs = stats.get("data_readiness") or {}
    if rs.get("ok") is not True:
        _reject("scan stats do not record readiness ok=true")
    if _stat_int(rs, "price_rows") != price_n:
        _reject("scan stats price_rows disagrees with DB")
    if _stat_int(rs, "indicator_rows") != ind_n:
        _reject("scan stats indicator_rows disagrees with DB")
    ingest_status = str((stats.get("ingest") or {}).get("status") or "offline")
    if ingest_status in ("failed", "partial"):
        _reject(f"scan ingest status is {ingest_status}; release requires complete ingest")

    for sid, max_age in CORE_SERIES.items():
        last = store.scalar("SELECT MAX(date) FROM indicators WHERE series_id=? AND date<=?",
                            (sid, as_of))
        if not last:
            _reject(f"critical series missing: {sid}")
        if (pd.Timestamp(as_of) - pd.Timestamp(last)).days > max_age:
            _reject(f"critical series stale: {sid} last={last}")

    anomaly_n = int(store.scalar(
        "SELECT COUNT(*) FROM anomalies WHERE run_id=?", (scan["scan_id"],)) or 0)
    tx_n = int(store.scalar(
        "SELECT COUNT(*) FROM transmissions WHERE run_id=?", (scan["scan_id"],)) or 0)
    opp_n = int(store.scalar(
        "SELECT COUNT(*) FROM opportunities WHERE run_id=?", (scan["scan_id"],)) or 0)
    if anomaly_n <= 0:
        _reject("scan has no anomalies")
    if _stat_int(stats.get("anomalies"), "n") != anomaly_n:
        _reject("scan stats anomaly count disagrees with DB")
    if _stat_int(stats.get("transmissions"), "n_activated") != tx_n:
        _reject("scan stats transmission count disagrees with DB")
    opp_stats = stats.get("opportunities") or {}
    created = opp_stats.get("created")
    refreshed = opp_stats.get("refreshed")
    if created is not None:
        expected_opp = int(created) + int(refreshed or 0)
        if expected_opp != opp_n:
            _reject("scan stats opportunity count disagrees with DB")

    report_md = reports / f"report_{as_of}.md"
    scan_json = reports / f"scan_{as_of}.json"
    pipeline = exports / f"pipeline_{as_of}.json"
    for p in (report_md, scan_json, pipeline):
        if require_reports and not p.exists():
            _reject(f"required artifact missing: {p}")
        if p.exists() and p.stat().st_mtime < pd.Timestamp(scan["started_at"]).timestamp() - 120:
            _reject(f"artifact predates scan: {p}")

    if scan_json.exists():
        try:
            doc = json.loads(scan_json.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ScanEvidenceError(f"scan json invalid: {exc}") from exc
        meta = doc.get("meta") or {}
        for k, v in (("scan_id", scan["scan_id"]), ("as_of", as_of),
                     ("config_hash", config_hash), ("data_hash", data_hash)):
            if meta.get(k) != v:
                _reject(f"scan json meta.{k} disagrees with DB")
        if int(len(doc.get("anomalies") or [])) != anomaly_n:
            _reject("scan json anomaly count disagrees with DB")
        if int(len(doc.get("opportunities") or [])) != opp_n:
            _reject("scan json opportunity count disagrees with DB")
    if report_md.exists():
        text = report_md.read_text(encoding="utf-8", errors="replace")
        for token in (scan["scan_id"], as_of, config_hash[:16], data_hash[:16]):
            if token not in text:
                _reject(f"report does not contain provenance token: {token}")
    if pipeline.exists():
        try:
            pdoc = json.loads(pipeline.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ScanEvidenceError(f"pipeline export invalid: {exc}") from exc
        prov = pdoc.get("provenance") or {}
        if prov.get("config_hash") != config_hash or prov.get("data_hash") != data_hash:
            _reject("pipeline export provenance hashes disagree with DB")
        if _stat_int(pdoc.get("summary"), "n_opportunities") != opp_n:
            _reject("pipeline export opportunity count disagrees with DB")
        ids = {o.get("opportunity", {}).get("opportunity_id") for o in pdoc.get("opportunities") or []}
        db_ids = {r[0] for r in store.conn.execute(
            "SELECT opportunity_id FROM opportunities WHERE run_id=?", (scan["scan_id"],))}
        if ids != db_ids:
            _reject("pipeline export opportunity ids disagree with DB")

    return ScanEvidence(
        scan_id=scan["scan_id"], as_of=as_of, mode=scan["mode"],
        config_hash=config_hash, data_hash=data_hash,
        prices=price_n, indicators=ind_n, anomalies=anomaly_n,
        transmissions=tx_n, opportunities=opp_n,
        report_path=str(report_md), scan_json_path=str(scan_json),
        pipeline_path=str(pipeline),
        report_sha256=_sha256(report_md) if report_md.exists() else "",
        scan_json_sha256=_sha256(scan_json) if scan_json.exists() else "",
        pipeline_sha256=_sha256(pipeline) if pipeline.exists() else "",
        readiness_ok=True, ingest_status=ingest_status,
    )
