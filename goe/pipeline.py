"""End-to-end scan pipeline.

    ingest -> features -> anomalies -> transmission -> opportunities -> persist
           -> reports -> handoff export

Each stage is idempotent and every run is recorded in ``scan_runs`` with a
config hash and a data hash so a result can be reproduced or audited later.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__, project_root
from .config import exports_dir
from .anomalies import detect_anomalies, summarize as summarize_anomalies
from .config import load_yaml_config
from .db import Store, utc_now
from .readiness import ScanBlockedError, check_data_readiness
from .events import EventCalendar
from .features import FEATURE_VERSION, FeatureBuilder
from .ingest import Ingestor
from .opportunities import OpportunityEngine, persist_drafts
from .reports import write_reports
from .transmission.evaluator import activation_summary, evaluate_transmissions


@dataclass
class ScanResult:
    scan_id: str
    as_of: str
    status: str
    stats: dict[str, Any] = field(default_factory=dict)
    opportunities: list[dict[str, Any]] = field(default_factory=list)
    report_paths: dict[str, str] = field(default_factory=dict)
    export_paths: dict[str, Any] = field(default_factory=dict)


def _persisted_rows(store: Store, ids: list[str]) -> list[dict[str, Any]]:
    out = []
    for oid in ids:
        row = store.conn.execute("SELECT * FROM opportunities WHERE opportunity_id=?", (oid,)).fetchone()
        if row:
            out.append(dict(row))
    return out


def run_scan(store: Store, as_of: str | None = None, *, ingest: bool = False,
             ingest_mode: str = "incremental", out_dir: str | Path | None = None,
             export: bool = True, export_dir: str | Path | None = None,
             run_ia: bool = False, ia_path: str | None = None,
             max_candidates: int = 25, point_in_time: bool = True,
             readiness_min_coverage: float = 0.80,
             mechanisms_cfg: dict[str, Any] | None = None) -> ScanResult:
    t0 = time.time()
    as_of_arg = as_of
    ingest_stats: dict[str, Any] = {}
    if ingest:
        ingest_stats = Ingestor(store).run(mode=ingest_mode)
        if ingest_stats.get("status") == "failed":
            raise ScanBlockedError(
                "数据采集失败（价格源不可用）：拒绝在陈旧/缺失数据上生成机会。"
                f" details={ {k: v for k, v in ingest_stats.items() if k.endswith('_error')} }")

    if as_of is None:
        as_of = store.scalar("SELECT MAX(date) FROM prices")
    _hist_start = (pd.Timestamp(as_of) - pd.DateOffset(years=6, months=6)).strftime("%Y-%m-%d") if as_of else None
    readiness = check_data_readiness(store, as_of=as_of_arg,
                                     min_coverage=readiness_min_coverage)
    if not readiness.ok:
        blocked_id = store.start_scan(str(as_of or ""), "blocked", store.config_fingerprint(),
                                      store.data_fingerprint(str(as_of or "")))
        store.finish_scan(blocked_id, "blocked_data", {"readiness": readiness.to_dict()})
        raise ScanBlockedError("数据就绪检查未通过: " + "; ".join(readiness.critical))
    builder = FeatureBuilder(store, as_of=as_of, point_in_time=point_in_time,
                             history_start=_hist_start)
    fs = builder.build()
    config_hash = store.config_fingerprint()
    data_hash = store.data_fingerprint(fs.as_of)
    scan_id = store.start_scan(fs.as_of, "live" if ingest else "offline", config_hash, data_hash)
    stats: dict[str, Any] = {"feature_rows": int(len(fs.long)), "data_readiness": readiness.to_dict(),
                             "ingest": ingest_stats, **fs.meta}

    try:
        # one atomic unit: a failure must not leave anomalies/transmissions/
        # opportunities/status events half-written (QA residual).
        with store.transaction():
            _since = (pd.Timestamp(fs.as_of) - pd.Timedelta(days=200)).strftime("%Y-%m-%d")
            anomalies = detect_anomalies(fs, since=_since)
            det_errors = anomalies.attrs.get("errors") or []
            stats["detector_errors"] = det_errors
            if det_errors:
                # A swallowed detector exception means the scan silently misses a
                # whole signal family. Never publish a "successful" scan in that case.
                raise RuntimeError("异常检测器失败，拒绝发布不完整扫描: " + "; ".join(det_errors))
            stats["anomalies"] = summarize_anomalies(anomalies)
            if not anomalies.empty:
                records_a = []
                for r in anomalies.to_dict("records"):
                    records_a.append({
                        "anomaly_id": r["anomaly_id"],
                        "as_of": pd.Timestamp(r["date"]).strftime("%Y-%m-%d"),
                        "available_date": pd.Timestamp(r.get("available_date", r["date"])).strftime("%Y-%m-%d"),
                        "detector": r["detector"],
                        "family": r["family"], "instrument_id": r["entity_id"],
                        "direction": r["direction"], "magnitude": r["magnitude"], "score": r["score"],
                        "percentile": r.get("percentile"), "window": r.get("window", ""),
                        "evidence": r.get("evidence", {}),
                        "fingerprint": "|".join([r["detector"], r["entity_id"], str(r["direction"]),
                                                 str(r.get("window", ""))]),
                    })
                store.insert_anomalies(records_a, run_id=scan_id)

            tx_df, mechanisms = evaluate_transmissions(fs, anomalies, mechanisms_cfg)
            stats["transmissions"] = activation_summary(mechanisms)
            if not tx_df.empty:
                store.insert_transmissions(tx_df.to_dict("records"), run_id=scan_id)

            events = EventCalendar.load()
            engine = OpportunityEngine(fs, anomalies, mechanisms, events, load_yaml_config("scoring.yaml"),
                                       max_candidates=max_candidates, store=store,
                                   data_degraded=readiness.critical_degraded)
            drafts = engine.generate()
            persist_stats = persist_drafts(store, engine, drafts, run_id=scan_id)
            stats["opportunities"] = persist_stats
            _created_ids = persist_stats.get("created_ids", [])

            # read back persisted records (canonical, includes opportunity_id & lifecycle)
            ids = []
            for d in drafts:
                row = store.find_opportunity(d.fingerprint())
                if row:
                    ids.append(row["opportunity_id"])
            records = _persisted_rows(store, ids)
            result = ScanResult(scan_id=scan_id, as_of=fs.as_of, status="success", stats=stats,
                                opportunities=records)

            out = Path(out_dir) if out_dir else (project_root() / "reports")
            meta = {
                "scan_id": scan_id, "as_of": fs.as_of, "engine_version": __version__,
                "feature_version": FEATURE_VERSION, "config_hash": config_hash, "data_hash": data_hash,
                "generated_at": utc_now(), "data_readiness": readiness.to_dict(), **fs.meta,
            }
            issues = store.recent_issues(limit=30)
            result.report_paths = write_reports(out, store, fs, anomalies, tx_df, mechanisms, records, meta, issues)

            if export:
                from .integration.exporter import export_all

                result.export_paths = export_all(store, records, meta,
                                                 base_dir=Path(export_dir) if export_dir else exports_dir())
                if run_ia:
                    from .integration.ia_adapter import IAAdapter

                    adapter = IAAdapter(ia_path or os.environ.get("GOE_IA_PATH") or str(Path.home() / "investment-agent-dev"))
                    result.export_paths["ia_runs"] = adapter.run_queue(
                        store, records, limit=3,
                        out_dir=(Path(export_dir) if export_dir else exports_dir()) / "ia_runs",
                    )
            stats["elapsed_s"] = round(time.time() - t0, 2)
            store.finish_scan(scan_id, "success", stats)
            return result
    except Exception as exc:
        stats["error"] = f"{type(exc).__name__}: {exc}"
        try:
            store.rollback_scan(scan_id, locals().get("_created_ids", []))
        except Exception:
            pass
        store.finish_scan(scan_id, "failed", stats)
        raise
