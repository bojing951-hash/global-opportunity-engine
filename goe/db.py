"""SQLite storage layer.

Design notes
------------
* One file (``data/goe.db``) holds observations, computed anomalies, the
  opportunity pipeline and all run/audit metadata. SQLite with WAL is enough for
  a single-user research system at this data volume (~150 instruments x 10y).
* Timestamps are stored as ISO-8601 UTC strings with an explicit ``Z`` suffix;
  observation dates are stored as ``YYYY-MM-DD`` in the instrument's trading
  calendar. Every row carries ``source_id`` and ``fetched_at`` so provenance is
  never lost by a downstream aggregation.
* Re-running an ingest is idempotent: ``INSERT OR REPLACE`` keyed on
  (instrument, date) / (series, date).
* Opportunities are keyed by a deterministic fingerprint so repeated scans do
  not create duplicate records for the same phenomenon (requirement §10.6).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import pandas as pd

from . import project_root

SCHEMA_VERSION = "1"

DDL = """
CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY, name TEXT, kind TEXT, tier TEXT, latency TEXT,
  license_note TEXT, covers_json TEXT, known_gaps_json TEXT, enabled INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS instruments (
  instrument_id TEXT PRIMARY KEY, name TEXT, asset_class TEXT, region TEXT,
  currency TEXT, source_id TEXT, symbol TEXT, importance REAL, liquidity TEXT,
  role TEXT, benchmark TEXT, notes TEXT, updated_at TEXT
);

CREATE TABLE IF NOT EXISTS prices (
  instrument_id TEXT NOT NULL, date TEXT NOT NULL,
  open REAL, high REAL, low REAL, close REAL, adj_close REAL, volume REAL,
  source_id TEXT NOT NULL, fetched_at TEXT NOT NULL, run_id TEXT,
  PRIMARY KEY (instrument_id, date)
);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);

CREATE TABLE IF NOT EXISTS indicators (
  series_id TEXT NOT NULL, date TEXT NOT NULL, value REAL,
  unit TEXT, source_id TEXT NOT NULL, fetched_at TEXT NOT NULL, run_id TEXT,
  PRIMARY KEY (series_id, date)
);
CREATE INDEX IF NOT EXISTS idx_indicators_series ON indicators(series_id, date);

CREATE TABLE IF NOT EXISTS series_meta (
  series_id TEXT PRIMARY KEY, name TEXT, kind TEXT, unit TEXT, region TEXT,
  frequency TEXT, provider TEXT, tier TEXT, notes TEXT, updated_at TEXT
);

CREATE TABLE IF NOT EXISTS ingest_runs (
  run_id TEXT PRIMARY KEY, kind TEXT, mode TEXT, started_at TEXT, finished_at TEXT,
  status TEXT, stats_json TEXT, errors_json TEXT
);

CREATE TABLE IF NOT EXISTS quality_issues (
  issue_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, target TEXT, code TEXT,
  severity TEXT, detail TEXT, created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_qi_target ON quality_issues(target, created_at);

CREATE TABLE IF NOT EXISTS anomalies (
  anomaly_id TEXT PRIMARY KEY, as_of TEXT NOT NULL, available_date TEXT,
  detector TEXT NOT NULL,
  family TEXT NOT NULL, instrument_id TEXT, direction TEXT, magnitude REAL,
  score REAL, percentile REAL, window TEXT, evidence_json TEXT, fingerprint TEXT NOT NULL,
  run_id TEXT, created_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_anomaly_fp ON anomalies(fingerprint, as_of);
CREATE INDEX IF NOT EXISTS idx_anomaly_asof ON anomalies(as_of);

CREATE TABLE IF NOT EXISTS transmissions (
  transmission_id TEXT PRIMARY KEY, as_of TEXT NOT NULL, mechanism_id TEXT NOT NULL,
  title TEXT, trigger_json TEXT, assets_json TEXT, evidence_for_json TEXT,
  evidence_against_json TEXT, conditions_json TEXT, confidence REAL,
  status TEXT, notes TEXT, run_id TEXT, created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_trans_asof ON transmissions(as_of);

CREATE TABLE IF NOT EXISTS opportunities (
  opportunity_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE,
  as_of TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
  archetype TEXT, title TEXT, market TEXT, asset_class TEXT, instruments_json TEXT,
  horizon TEXT, status TEXT NOT NULL, status_source TEXT DEFAULT 'auto',
  status_reason TEXT, score REAL, score_json TEXT,
  discovery_json TEXT, mechanism_json TEXT, evidence_for_json TEXT,
  evidence_against_json TEXT, catalysts_json TEXT, open_questions_json TEXT,
  invalidation TEXT, data_quality TEXT, lifecycle_json TEXT, run_id TEXT,
  created_at TEXT, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_opp_status ON opportunities(status, score DESC);
CREATE INDEX IF NOT EXISTS idx_opp_asof ON opportunities(as_of);

CREATE TABLE IF NOT EXISTS opportunity_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id TEXT NOT NULL,
  at TEXT NOT NULL, event_type TEXT NOT NULL, from_status TEXT, to_status TEXT,
  note TEXT, run_id TEXT
);

CREATE TABLE IF NOT EXISTS scan_runs (
  scan_id TEXT PRIMARY KEY, as_of TEXT, mode TEXT, started_at TEXT, finished_at TEXT,
  status TEXT, config_hash TEXT, data_hash TEXT, stats_json TEXT
);

CREATE TABLE IF NOT EXISTS research_tasks (
  task_id TEXT PRIMARY KEY, opportunity_id TEXT, created_at TEXT,
  target_system TEXT, payload_json TEXT, exported_at TEXT, export_path TEXT, status TEXT
);

CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id(prefix: str = "run") -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"


def hash_json(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def default_db_path() -> Path:
    return project_root() / "data" / "goe.db"


class Store:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.init_schema()

    # ------------------------------------------------------------------ schema
    def init_schema(self) -> None:
        self.conn.executescript(DDL)
        cur = self.conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'")
        row = cur.fetchone()
        # lightweight migrations for existing databases
        opp_cols = {r[1] for r in self.conn.execute("PRAGMA table_info(opportunities)").fetchall()}
        if opp_cols and "status_source" not in opp_cols:
            self.conn.execute("ALTER TABLE opportunities ADD COLUMN status_source TEXT DEFAULT 'auto'")
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(anomalies)").fetchall()}
        if "available_date" not in cols:
            self.conn.execute("ALTER TABLE anomalies ADD COLUMN available_date TEXT")
        if row is None:
            self.conn.execute(
                "INSERT INTO schema_meta(key,value) VALUES('schema_version',?)", (SCHEMA_VERSION,)
            )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Transaction context that nests safely via SAVEPOINT.

        The scan wants one atomic unit around anomalies + transmissions +
        opportunities + status events. Store methods themselves open transactions,
        so a nested call must not commit the outer unit early: use a savepoint when
        a transaction is already active, otherwise BEGIN/COMMIT.
        """
        if self.conn.in_transaction:
            name = f"sp_{uuid.uuid4().hex[:12]}"
            self.conn.execute(f"SAVEPOINT {name}")
            try:
                yield self.conn
                self.conn.execute(f"RELEASE {name}")
            except Exception:
                self.conn.execute(f"ROLLBACK TO {name}")
                self.conn.execute(f"RELEASE {name}")
                raise
        else:
            self.conn.execute("BEGIN")
            try:
                yield self.conn
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    # ------------------------------------------------------------------ metadata
    def upsert_sources(self, sources: dict[str, dict[str, Any]]) -> None:
        now = utc_now()
        with self.transaction() as c:
            for sid, spec in sources.items():
                c.execute(
                    """INSERT INTO sources(source_id,name,kind,tier,latency,license_note,covers_json,known_gaps_json)
                       VALUES(?,?,?,?,?,?,?,?)
                       ON CONFLICT(source_id) DO UPDATE SET
                         name=excluded.name, kind=excluded.kind, tier=excluded.tier,
                         latency=excluded.latency, license_note=excluded.license_note,
                         covers_json=excluded.covers_json, known_gaps_json=excluded.known_gaps_json""",
                    (
                        sid,
                        spec.get("name", sid),
                        spec.get("kind", ""),
                        spec.get("tier", ""),
                        spec.get("latency", ""),
                        spec.get("license_note", ""),
                        json.dumps(spec.get("covers", []), ensure_ascii=False),
                        json.dumps(spec.get("known_gaps", []), ensure_ascii=False),
                    ),
                )
        del now

    def upsert_instruments(self, instruments: Iterable[Any]) -> int:
        now = utc_now()
        n = 0
        with self.transaction() as c:
            for i in instruments:
                c.execute(
                    """INSERT INTO instruments(instrument_id,name,asset_class,region,currency,source_id,symbol,
                         importance,liquidity,role,benchmark,notes,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(instrument_id) DO UPDATE SET
                         name=excluded.name, asset_class=excluded.asset_class, region=excluded.region,
                         currency=excluded.currency, source_id=excluded.source_id, symbol=excluded.symbol,
                         importance=excluded.importance, liquidity=excluded.liquidity, role=excluded.role,
                         benchmark=excluded.benchmark, notes=excluded.notes, updated_at=excluded.updated_at""",
                    (
                        i.id, i.name, i.asset_class, i.region, i.currency, i.source, i.symbol,
                        float(i.importance), i.liquidity, i.role, i.benchmark, i.notes, now,
                    ),
                )
                n += 1
        return n

    def upsert_series_meta(self, rows: Iterable[dict[str, Any]]) -> int:
        now = utc_now()
        n = 0
        with self.transaction() as c:
            for r in rows:
                c.execute(
                    """INSERT INTO series_meta(series_id,name,kind,unit,region,frequency,provider,tier,notes,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(series_id) DO UPDATE SET
                         name=excluded.name, kind=excluded.kind, unit=excluded.unit, region=excluded.region,
                         frequency=excluded.frequency, provider=excluded.provider, tier=excluded.tier,
                         notes=excluded.notes, updated_at=excluded.updated_at""",
                    (
                        r["series_id"], r.get("name", r["series_id"]), r.get("kind", "indicator"),
                        r.get("unit", ""), r.get("region", ""), r.get("frequency", ""),
                        r.get("provider", ""), r.get("tier", ""), r.get("notes", ""), now,
                    ),
                )
                n += 1
        return n

    # ------------------------------------------------------------------ loading
    def load_prices(
        self,
        instrument_ids: Sequence[str] | None = None,
        start: str | None = None,
        end: str | None = None,
        field: str = "adj_close",
        fallback_field: str = "close",
    ) -> pd.DataFrame:
        """Wide frame: index=date (ascending), columns=instrument_id.

        ``field`` falls back to ``fallback_field`` per row when the preferred
        column is NULL (e.g. adjusted close missing for some exchanges). Which
        column was used is recorded at row level in the database, never guessed.
        """
        if field not in {"close", "adj_close", "open", "high", "low", "volume"}:
            raise ValueError(f"unsupported price field {field}")
        where, params = [], []
        if instrument_ids:
            where.append(f"instrument_id IN ({','.join('?' for _ in instrument_ids)})")
            params.extend(instrument_ids)
        if start:
            where.append("date >= ?")
            params.append(start)
        if end:
            where.append("date <= ?")
            params.append(end)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        sql = (
            f"SELECT instrument_id, date, COALESCE({field}, {fallback_field}) AS value "
            f"FROM prices{clause} ORDER BY date"
        )
        df = pd.read_sql_query(sql, self.conn, params=params)
        if df.empty:
            return pd.DataFrame()
        wide = df.pivot_table(index="date", columns="instrument_id", values="value", aggfunc="last")
        wide.index = pd.to_datetime(wide.index)
        return wide.sort_index()

    def load_indicator(
        self, series_id: str, start: str | None = None, end: str | None = None
    ) -> pd.Series:
        sql = "SELECT date, value FROM indicators WHERE series_id=?"
        params: list[Any] = [series_id]
        if start:
            sql += " AND date >= ?"
            params.append(start)
        if end:
            sql += " AND date <= ?"
            params.append(end)
        sql += " ORDER BY date"
        df = pd.read_sql_query(sql, self.conn, params=params)
        if df.empty:
            return pd.Series(dtype=float, name=series_id)
        s = pd.Series(df["value"].values, index=pd.to_datetime(df["date"]), name=series_id)
        return s.sort_index()

    def load_indicators_wide(
        self, series_ids: Sequence[str], start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        if not series_ids:
            return pd.DataFrame()
        placeholders = ",".join("?" for _ in series_ids)
        sql = f"SELECT series_id, date, value FROM indicators WHERE series_id IN ({placeholders})"
        params: list[Any] = list(series_ids)
        if start:
            sql += " AND date >= ?"
            params.append(start)
        if end:
            sql += " AND date <= ?"
            params.append(end)
        df = pd.read_sql_query(sql, self.conn, params=params)
        if df.empty:
            return pd.DataFrame()
        wide = df.pivot_table(index="date", columns="series_id", values="value", aggfunc="last")
        wide.index = pd.to_datetime(wide.index)
        return wide.sort_index()

    def indicator_series_ids(self, prefix: str | None = None) -> list[str]:
        if prefix:
            rows = self.conn.execute(
                "SELECT DISTINCT series_id FROM indicators WHERE series_id LIKE ? ORDER BY series_id",
                (prefix + "%",),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT DISTINCT series_id FROM indicators ORDER BY series_id").fetchall()
        return [r[0] for r in rows]

    def instrument_ids(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT instrument_id FROM instruments ORDER BY instrument_id")]

    def price_coverage(self) -> pd.DataFrame:
        sql = """SELECT instrument_id, MIN(date) AS first_date, MAX(date) AS last_date,
                        COUNT(*) AS n, SUM(CASE WHEN adj_close IS NULL THEN 1 ELSE 0 END) AS n_no_adj
                 FROM prices GROUP BY instrument_id ORDER BY instrument_id"""
        return pd.read_sql_query(sql, self.conn)

    # ------------------------------------------------------------------ writing
    def upsert_prices(self, df: pd.DataFrame, run_id: str | None = None) -> int:
        if df is None or df.empty:
            return 0
        required = {"instrument_id", "date", "close", "source_id", "fetched_at"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"price frame missing columns: {sorted(missing)}")
        cols = ["instrument_id", "date", "open", "high", "low", "close", "adj_close", "volume",
                "source_id", "fetched_at"]
        frame = df.copy()
        for c in cols:
            if c not in frame.columns:
                frame[c] = None
        frame = frame[cols]
        frame["run_id"] = run_id
        rows = [tuple(None if (isinstance(v, float) and pd.isna(v)) else v for v in r)
                for r in frame.itertuples(index=False, name=None)]
        with self.transaction() as c:
            c.executemany(
                """INSERT INTO prices(instrument_id,date,open,high,low,close,adj_close,volume,
                     source_id,fetched_at,run_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(instrument_id,date) DO UPDATE SET
                     open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close,
                     adj_close=excluded.adj_close, volume=excluded.volume,
                     source_id=excluded.source_id, fetched_at=excluded.fetched_at, run_id=excluded.run_id""",
                rows,
            )
        return len(rows)

    def upsert_indicators(self, df: pd.DataFrame, run_id: str | None = None) -> int:
        if df is None or df.empty:
            return 0
        required = {"series_id", "date", "value", "source_id", "fetched_at"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"indicator frame missing columns: {sorted(missing)}")
        frame = df.copy()
        for c in ("unit",):
            if c not in frame.columns:
                frame[c] = None
        frame = frame[["series_id", "date", "value", "unit", "source_id", "fetched_at"]]
        frame["run_id"] = run_id
        rows = [tuple(None if (isinstance(v, float) and pd.isna(v)) else v for v in r)
                for r in frame.itertuples(index=False, name=None)]
        with self.transaction() as c:
            c.executemany(
                """INSERT INTO indicators(series_id,date,value,unit,source_id,fetched_at,run_id)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(series_id,date) DO UPDATE SET
                     value=excluded.value, unit=excluded.unit, source_id=excluded.source_id,
                     fetched_at=excluded.fetched_at, run_id=excluded.run_id""",
                rows,
            )
        return len(rows)

    # ------------------------------------------------------------------ runs
    def start_run(self, kind: str, mode: str) -> str:
        run_id = new_run_id(kind)
        with self.transaction() as c:
            c.execute(
                "INSERT INTO ingest_runs(run_id,kind,mode,started_at,status) VALUES(?,?,?,?,?)",
                (run_id, kind, mode, utc_now(), "running"),
            )
        return run_id

    def finish_run(self, run_id: str, status: str, stats: dict[str, Any] | None = None,
                   errors: list[Any] | None = None) -> None:
        with self.transaction() as c:
            c.execute(
                "UPDATE ingest_runs SET finished_at=?, status=?, stats_json=?, errors_json=? WHERE run_id=?",
                (utc_now(), status, json.dumps(stats or {}, ensure_ascii=False, default=str),
                 json.dumps(errors or [], ensure_ascii=False, default=str), run_id),
            )

    def log_issue(self, run_id: str | None, target: str, code: str, severity: str, detail: str) -> None:
        with self.transaction() as c:
            c.execute(
                "INSERT INTO quality_issues(run_id,target,code,severity,detail,created_at) VALUES(?,?,?,?,?,?)",
                (run_id, target, code, severity, detail, utc_now()),
            )

    def recent_issues(self, limit: int = 50) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM quality_issues ORDER BY issue_id DESC LIMIT ?", self.conn, params=[limit]
        )

    # ------------------------------------------------------------------ anomalies
    def insert_anomalies(self, anomalies: Sequence[dict[str, Any]], run_id: str | None = None) -> int:
        rows = []
        now = utc_now()
        for a in anomalies:
            rows.append((
                a["anomaly_id"], a["as_of"], a.get("available_date") or a["as_of"],
                a["detector"], a["family"], a.get("instrument_id"),
                a.get("direction"), a.get("magnitude"), a.get("score"), a.get("percentile"),
                a.get("window"), json.dumps(a.get("evidence", {}), ensure_ascii=False, default=str),
                a["fingerprint"], run_id, now,
            ))
        with self.transaction() as c:
            c.executemany(
                """INSERT INTO anomalies(anomaly_id,as_of,available_date,detector,family,instrument_id,direction,
                     magnitude,score,percentile,window,evidence_json,fingerprint,run_id,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(anomaly_id) DO UPDATE SET
                     magnitude=excluded.magnitude, score=excluded.score, percentile=excluded.percentile,
                     evidence_json=excluded.evidence_json, run_id=excluded.run_id, created_at=excluded.created_at""",
                rows,
            )
        return len(rows)

    def anomalies_on(self, as_of: str) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM anomalies WHERE as_of=? ORDER BY score DESC", self.conn, params=[as_of]
        )

    # ------------------------------------------------------------------ transmissions
    def insert_transmissions(self, rows_in: Sequence[dict[str, Any]], run_id: str | None = None) -> int:
        rows = []
        now = utc_now()
        for t in rows_in:
            rows.append((
                t["transmission_id"], t["as_of"], t["mechanism_id"], t.get("title"),
                json.dumps(t.get("triggers", []), ensure_ascii=False, default=str),
                json.dumps(t.get("assets", []), ensure_ascii=False, default=str),
                json.dumps(t.get("evidence_for", []), ensure_ascii=False, default=str),
                json.dumps(t.get("evidence_against", []), ensure_ascii=False, default=str),
                json.dumps(t.get("conditions", []), ensure_ascii=False, default=str),
                t.get("confidence"), t.get("status", "proposed"), t.get("notes", ""), run_id, now,
            ))
        with self.transaction() as c:
            c.executemany(
                """INSERT INTO transmissions(transmission_id,as_of,mechanism_id,title,trigger_json,
                     assets_json,evidence_for_json,evidence_against_json,conditions_json,confidence,
                     status,notes,run_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(transmission_id) DO UPDATE SET
                     evidence_for_json=excluded.evidence_for_json,
                     evidence_against_json=excluded.evidence_against_json,
                     conditions_json=excluded.conditions_json, confidence=excluded.confidence,
                     status=excluded.status, notes=excluded.notes, run_id=excluded.run_id,
                     created_at=excluded.created_at""",
                rows,
            )
        return len(rows)

    # ------------------------------------------------------------------ opportunities
    def next_opportunity_id(self) -> str:
        with self.transaction() as c:
            row = c.execute("SELECT value FROM counters WHERE name='opportunity'").fetchone()
            value = (row[0] if row else 0) + 1
            c.execute(
                "INSERT INTO counters(name,value) VALUES('opportunity',?) "
                "ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                (value,),
            )
        return f"OPP-{value:04d}"

    def find_opportunity(self, fingerprint: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM opportunities WHERE fingerprint=?", (fingerprint,)
        ).fetchone()
        return dict(row) if row else None

    def upsert_opportunity(self, opp: dict[str, Any], run_id: str | None = None) -> str:
        """Insert a new opportunity or refresh an existing one (same fingerprint).

        The UPDATE path deliberately does **not** write ``status``: status
        transitions are owned by ``set_opportunity_status`` / the lifecycle
        module so that manual decisions are never silently reverted by a scan.
        """
        now = utc_now()
        dq = opp.get("data_quality")
        if isinstance(dq, (dict, list)):
            dq = json.dumps(dq, ensure_ascii=False, default=str)
        existing = self.find_opportunity(opp["fingerprint"])
        if existing is None:
            oid = opp.get("opportunity_id") or self.next_opportunity_id()
            with self.transaction() as c:
                c.execute(
                    """INSERT INTO opportunities(opportunity_id,fingerprint,as_of,first_seen,last_seen,
                         archetype,title,market,asset_class,instruments_json,horizon,status,status_source,
                         status_reason,score,score_json,discovery_json,mechanism_json,evidence_for_json,
                         evidence_against_json,catalysts_json,open_questions_json,invalidation,
                         data_quality,lifecycle_json,run_id,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        oid, opp["fingerprint"], opp["as_of"], opp["as_of"], opp["as_of"],
                        opp.get("archetype"), opp.get("title"), opp.get("market"),
                        opp.get("asset_class"), json.dumps(opp.get("instruments", []), ensure_ascii=False),
                        opp.get("horizon"), opp.get("status", "new"),
                        opp.get("status_source", "auto"), opp.get("status_reason"),
                        opp.get("score"), json.dumps(opp.get("score_breakdown", {}), ensure_ascii=False),
                        json.dumps(opp.get("discovery", {}), ensure_ascii=False, default=str),
                        json.dumps(opp.get("mechanism", {}), ensure_ascii=False, default=str),
                        json.dumps(opp.get("evidence_for", []), ensure_ascii=False, default=str),
                        json.dumps(opp.get("evidence_against", []), ensure_ascii=False, default=str),
                        json.dumps(opp.get("catalysts", []), ensure_ascii=False, default=str),
                        json.dumps(opp.get("open_questions", []), ensure_ascii=False, default=str),
                        opp.get("invalidation"), dq,
                        json.dumps(opp.get("lifecycle", []), ensure_ascii=False, default=str),
                        run_id, now, now,
                    ),
                )
            self.add_opportunity_event(oid, "created", None, opp.get("status", "new"),
                                       f"first detected by {opp.get('archetype')}", run_id)
            return oid
        oid = existing["opportunity_id"]
        with self.transaction() as c:
            c.execute(
                """UPDATE opportunities SET last_seen=?, as_of=?, score=?, score_json=?,
                     discovery_json=?, mechanism_json=?, evidence_for_json=?, evidence_against_json=?,
                     catalysts_json=?, open_questions_json=?, invalidation=?, data_quality=?,
                     run_id=?, updated_at=? WHERE opportunity_id=?""",
                (
                    opp["as_of"], opp["as_of"], opp.get("score"),
                    json.dumps(opp.get("score_breakdown", {}), ensure_ascii=False),
                    json.dumps(opp.get("discovery", {}), ensure_ascii=False, default=str),
                    json.dumps(opp.get("mechanism", {}), ensure_ascii=False, default=str),
                    json.dumps(opp.get("evidence_for", []), ensure_ascii=False, default=str),
                    json.dumps(opp.get("evidence_against", []), ensure_ascii=False, default=str),
                    json.dumps(opp.get("catalysts", []), ensure_ascii=False, default=str),
                    json.dumps(opp.get("open_questions", []), ensure_ascii=False, default=str),
                    opp.get("invalidation"), dq, run_id, now, oid,
                ),
            )
        self.add_opportunity_event(oid, "refreshed", existing["status"], existing["status"],
                                   f"re-detected on {opp['as_of']}", run_id)
        return oid

    def add_opportunity_event(self, opportunity_id: str, event_type: str,
                              from_status: str | None, to_status: str | None,
                              note: str = "", run_id: str | None = None) -> None:
        with self.transaction() as c:
            c.execute(
                """INSERT INTO opportunity_events(opportunity_id,at,event_type,from_status,to_status,note,run_id)
                   VALUES(?,?,?,?,?,?,?)""",
                (opportunity_id, utc_now(), event_type, from_status, to_status, note, run_id),
            )

    def set_opportunity_status(self, opportunity_id: str, status: str, reason: str,
                               run_id: str | None = None, source: str = "auto") -> bool:
        row = self.conn.execute(
            "SELECT status, lifecycle_json FROM opportunities WHERE opportunity_id=?", (opportunity_id,)
        ).fetchone()
        if row is None:
            return False
        old = row["status"]
        if old == status:
            return False
        lifecycle = json.loads(row["lifecycle_json"] or "[]")
        lifecycle.append({"at": utc_now(), "from": old, "to": status, "reason": reason})
        with self.transaction() as c:
            c.execute(
                "UPDATE opportunities SET status=?, status_source=?, status_reason=?, lifecycle_json=?, "
                "updated_at=? WHERE opportunity_id=?",
                (status, source, reason, json.dumps(lifecycle, ensure_ascii=False), utc_now(),
                 opportunity_id),
            )
        self.add_opportunity_event(opportunity_id, "status_change", old, status, reason, run_id)
        return True

    def opportunities(self, status: str | None = None, limit: int = 200) -> pd.DataFrame:
        if status:
            return pd.read_sql_query(
                "SELECT * FROM opportunities WHERE status=? ORDER BY score DESC LIMIT ?",
                self.conn, params=[status, limit],
            )
        return pd.read_sql_query(
            "SELECT * FROM opportunities ORDER BY score DESC LIMIT ?", self.conn, params=[limit]
        )

    def opportunity_events(self, opportunity_id: str | None = None) -> pd.DataFrame:
        if opportunity_id:
            return pd.read_sql_query(
                "SELECT * FROM opportunity_events WHERE opportunity_id=? ORDER BY event_id",
                self.conn, params=[opportunity_id],
            )
        return pd.read_sql_query("SELECT * FROM opportunity_events ORDER BY event_id", self.conn)

    # ------------------------------------------------------------------ scans
    def start_scan(self, as_of: str, mode: str, config_hash: str, data_hash: str) -> str:
        scan_id = new_run_id("scan")
        with self.transaction() as c:
            c.execute(
                "INSERT INTO scan_runs(scan_id,as_of,mode,started_at,status,config_hash,data_hash) "
                "VALUES(?,?,?,?,?,?,?)",
                (scan_id, as_of, mode, utc_now(), "running", config_hash, data_hash),
            )
        return scan_id

    def rollback_scan(self, scan_id: str, created_opportunity_ids: Sequence[str] = ()) -> None:
        """Remove artifacts written by a failed scan (no half-finished records)."""
        with self.transaction() as c:
            c.execute("DELETE FROM anomalies WHERE run_id=?", (scan_id,))
            c.execute("DELETE FROM transmissions WHERE run_id=?", (scan_id,))
            for oid in created_opportunity_ids:
                c.execute("DELETE FROM opportunity_events WHERE opportunity_id=?", (oid,))
                c.execute("DELETE FROM opportunities WHERE opportunity_id=?", (oid,))
            c.execute("UPDATE scan_runs SET status='rolled_back' WHERE scan_id=?", (scan_id,))

    def finish_scan(self, scan_id: str, status: str, stats: dict[str, Any]) -> None:
        with self.transaction() as c:
            c.execute(
                "UPDATE scan_runs SET finished_at=?, status=?, stats_json=? WHERE scan_id=?",
                (utc_now(), status, json.dumps(stats, ensure_ascii=False, default=str), scan_id),
            )

    # ------------------------------------------------------------------ research tasks
    def upsert_research_task(self, task: dict[str, Any]) -> None:
        with self.transaction() as c:
            c.execute(
                """INSERT INTO research_tasks(task_id,opportunity_id,created_at,target_system,
                     payload_json,exported_at,export_path,status) VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(task_id) DO UPDATE SET payload_json=excluded.payload_json,
                     exported_at=excluded.exported_at, export_path=excluded.export_path,
                     status=excluded.status""",
                (
                    task["task_id"], task["opportunity_id"], task.get("created_at", utc_now()),
                    task.get("target_system", "investment-agent"),
                    json.dumps(task.get("payload", {}), ensure_ascii=False, default=str),
                    task.get("exported_at"), task.get("export_path"), task.get("status", "pending"),
                ),
            )

    # ------------------------------------------------------------------ utility
    def scalar(self, sql: str, params: Sequence[Any] = ()) -> Any:
        row = self.conn.execute(sql, params).fetchone()
        return row[0] if row else None

    def config_fingerprint(self) -> str:
        """Hash of config inputs that influence scan output (for reproducibility)."""
        parts: dict[str, Any] = {}
        root = project_root() / "config"
        for name in ["universe.yaml", "curves.yaml", "macro.yaml", "positioning.yaml",
                     "thresholds.yaml", "scoring.yaml", "mechanisms.yaml", "events.yaml"]:
            p = root / name
            if p.exists():
                parts[name] = hashlib.sha256(p.read_bytes()).hexdigest()
        return hash_json(parts)

    def data_fingerprint(self, as_of: str) -> str:
        price_stats = self.conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(MAX(date),'') AS last FROM prices WHERE date<=?", (as_of,)
        ).fetchone()
        ind_stats = self.conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(MAX(date),'') AS last FROM indicators WHERE date<=?", (as_of,)
        ).fetchone()
        return hash_json({"prices_n": price_stats["n"], "prices_last": price_stats["last"],
                          "indicators_n": ind_stats["n"], "indicators_last": ind_stats["last"],
                          "as_of": as_of})
