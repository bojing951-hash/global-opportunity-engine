"""Store-level invariants: schema, idempotent upserts, uniqueness and lifecycle
bookkeeping.

These tests only use a temporary SQLite file under ``tmp_path``; the production
``data/goe.db`` is never opened.
"""

from __future__ import annotations

import json
import sqlite3

import pandas as pd
import pytest

from conftest import END_DATE, make_opportunity_row
from goe.db import SCHEMA_VERSION, Store

EXPECTED_TABLES = {
    "schema_meta", "sources", "instruments", "prices", "indicators", "series_meta",
    "ingest_runs", "quality_issues", "anomalies", "transmissions", "opportunities",
    "opportunity_events", "scan_runs", "research_tasks", "counters",
}


def _tables(store: Store) -> set[str]:
    rows = store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows if not r[0].startswith("sqlite_")}


def test_init_schema_is_idempotent(tmp_path):
    path = tmp_path / "schema.db"
    first = Store(path)
    tables = _tables(first)
    first.close()

    # Re-opening an existing database (and calling init_schema explicitly) must
    # neither fail nor duplicate metadata.
    second = Store(path)
    second.init_schema()
    second.init_schema()

    assert EXPECTED_TABLES <= _tables(second)
    assert second.scalar("SELECT COUNT(*) FROM schema_meta WHERE key='schema_version'") == 1
    assert second.scalar("SELECT value FROM schema_meta WHERE key='schema_version'") == SCHEMA_VERSION
    assert tables == _tables(second)
    second.close()


def test_upsert_prices_is_idempotent_and_updates_provenance(store, synthetic_market):
    prices = synthetic_market["prices"]
    before = store.scalar("SELECT COUNT(*) FROM prices")
    assert before == len(prices)

    # Same rows twice: row count unchanged, and the reported insert count is the
    # number of rows in the frame (not a duplicate insertion count).
    assert store.upsert_prices(prices) == len(prices)
    assert store.upsert_prices(prices) == len(prices)
    assert store.scalar("SELECT COUNT(*) FROM prices") == before

    # A re-fetch updates the provenance columns on the existing key.
    row = prices.iloc[0].to_dict()
    row["fetched_at"] = "2025-01-01T00:00:00Z"
    row["source_id"] = "stooq"
    row["close"] = float(row["close"]) + 1.0
    store.upsert_prices(pd.DataFrame([row]), run_id="run-refetch")

    stored = store.conn.execute(
        "SELECT close, source_id, fetched_at, run_id FROM prices WHERE instrument_id=? AND date=?",
        (row["instrument_id"], row["date"]),
    ).fetchone()
    assert stored["close"] == pytest.approx(row["close"])
    assert stored["source_id"] == "stooq"
    assert stored["fetched_at"] == "2025-01-01T00:00:00Z"
    assert stored["run_id"] == "run-refetch"
    assert store.scalar("SELECT COUNT(*) FROM prices") == before


def test_anomaly_unique_per_fingerprint_and_as_of(store):
    anomaly = {
        "anomaly_id": "AN-aaaaaaaaaaaaaa",
        "as_of": "2025-01-02",
        "detector": "price_return_shock",
        "family": "price",
        "instrument_id": "US_EQ_SPY",
        "direction": "down",
        "magnitude": -4.2,
        "score": 0.75,
        "percentile": 0.005,
        "window": "1d",
        "evidence": {"threshold": 3.0},
        "fingerprint": "price_return_shock|US_EQ_SPY|down|1d",
    }
    store.insert_anomalies([anomaly])
    store.insert_anomalies([anomaly])
    assert store.scalar("SELECT COUNT(*) FROM anomalies") == 1

    # Same anomaly id is an upsert, not a duplicate row.
    updated = dict(anomaly, score=0.90)
    store.insert_anomalies([updated])
    row = store.conn.execute(
        "SELECT score, evidence_json FROM anomalies WHERE anomaly_id=?", (anomaly["anomaly_id"],)
    ).fetchone()
    assert row["score"] == pytest.approx(0.90)
    assert json.loads(row["evidence_json"])["threshold"] == pytest.approx(3.0)

    # A *different* anomaly id for the same (fingerprint, as_of) violates the
    # documented uniqueness constraint and must be rejected by the database.
    conflicting = dict(anomaly, anomaly_id="AN-bbbbbbbbbbbbbb")
    with pytest.raises(sqlite3.IntegrityError):
        store.insert_anomalies([conflicting])
    assert store.scalar("SELECT COUNT(*) FROM anomalies") == 1


def test_opportunity_fingerprint_is_unique_and_upsert_refreshes(store):
    record = make_opportunity_row()
    first_id = store.upsert_opportunity(record)
    assert first_id == "OPP-0001"
    assert store.scalar("SELECT COUNT(*) FROM opportunities") == 1

    # Same fingerprint (later scan) refreshes the single row and keeps its id.
    refreshed = make_opportunity_row(opportunity_id="OPP-9999", as_of="2024-12-31",
                                     last_seen="2024-12-31")
    second_id = store.upsert_opportunity(refreshed)
    assert second_id == first_id
    assert store.scalar("SELECT COUNT(*) FROM opportunities") == 1
    assert store.scalar("SELECT COUNT(*) FROM opportunity_events") == 2
    event_types = [r[0] for r in store.conn.execute(
        "SELECT event_type FROM opportunity_events ORDER BY event_id")]
    assert event_types == ["created", "refreshed"]

    # The fingerprint column is protected at the schema level too.
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "INSERT INTO opportunities(opportunity_id,fingerprint,as_of,first_seen,last_seen,status) "
            "VALUES(?,?,?,?,?,?)",
            ("OPP-0002", record["fingerprint"], END_DATE, END_DATE, END_DATE, "watch"),
        )
    store.conn.rollback()


def test_status_transition_writes_event_and_lifecycle(store):
    record = make_opportunity_row(status="watch")
    oid = store.upsert_opportunity(record)
    events_before = store.scalar("SELECT COUNT(*) FROM opportunity_events")

    assert store.set_opportunity_status(oid, "deep_research", "评分升级", run_id="run-1") is True

    row = store.conn.execute(
        "SELECT status, status_reason, lifecycle_json FROM opportunities WHERE opportunity_id=?",
        (oid,),
    ).fetchone()
    assert row["status"] == "deep_research"
    assert row["status_reason"] == "评分升级"
    lifecycle = json.loads(row["lifecycle_json"])
    assert len(lifecycle) == 1
    assert lifecycle[0]["from"] == "watch"
    assert lifecycle[0]["to"] == "deep_research"
    assert lifecycle[0]["reason"] == "评分升级"

    events = store.opportunity_events(oid)
    assert len(events) == events_before + 1
    change = events.iloc[-1]
    assert change["event_type"] == "status_change"
    assert change["from_status"] == "watch"
    assert change["to_status"] == "deep_research"
    assert change["run_id"] == "run-1"

    # A no-op transition must not append a second lifecycle entry or event.
    assert store.set_opportunity_status(oid, "deep_research", "重复设置") is False
    assert store.scalar("SELECT COUNT(*) FROM opportunity_events") == events_before + 1
    row = store.conn.execute(
        "SELECT lifecycle_json FROM opportunities WHERE opportunity_id=?", (oid,)
    ).fetchone()
    assert len(json.loads(row["lifecycle_json"])) == 1


def test_counters_produce_incremental_opportunity_ids(store):
    assert store.next_opportunity_id() == "OPP-0001"
    assert store.next_opportunity_id() == "OPP-0002"
    assert store.scalar("SELECT value FROM counters WHERE name='opportunity'") == 2

    # Ids allocated via upsert share the same counter (when no explicit id is given).
    record = make_opportunity_row()
    record["opportunity_id"] = None
    oid = store.upsert_opportunity(record)
    assert oid == "OPP-0003"


def test_scan_run_lifecycle_is_recorded(store):
    scan_id = store.start_scan(END_DATE, "offline", "config-hash", "data-hash")
    row = store.conn.execute("SELECT * FROM scan_runs WHERE scan_id=?", (scan_id,)).fetchone()
    assert row["status"] == "running"
    assert row["config_hash"] == "config-hash"
    assert row["data_hash"] == "data-hash"

    store.finish_scan(scan_id, "success", {"anomalies": 3})
    row = store.conn.execute("SELECT * FROM scan_runs WHERE scan_id=?", (scan_id,)).fetchone()
    assert row["status"] == "success"
    assert row["finished_at"] is not None
    assert json.loads(row["stats_json"]) == {"anomalies": 3}
