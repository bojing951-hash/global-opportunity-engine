"""Ingestion orchestration: config -> providers -> validation -> SQLite.

Modes
-----
``backfill``    fetch ten years of history (configurable) for the whole universe.
``incremental`` fetch from a short overlap window before the last stored
                observation (overlap catches provider revisions and late prints).
``asof``        fetch nothing; used by replay/validation runs.

Every run has a ``run_id``; per-symbol errors become ``quality_issues`` rows and
are never silently swallowed. A run where *nothing* could be fetched raises
``IngestError`` so a scheduled job fails loudly instead of writing an empty DB.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

import pandas as pd

from .config import (
    CurveDef,
    MacroSeries,
    PositioningSeries,
    Universe,
    load_curves,
    load_macro,
    load_positioning,
    load_sources,
    load_universe,
)
from .db import Store
from .sources.base import FetchResult, IndicatorProvider, PriceProvider

BACKFILL_START = "2015-01-01"
OVERLAP_DAYS = 10


class IngestError(RuntimeError):
    pass


@dataclass
class IngestStats:
    kind: str
    mode: str
    run_id: str = ""
    rows: int = 0
    targets: int = 0
    failed_targets: list[str] = field(default_factory=list)
    notes: list[dict[str, Any]] = field(default_factory=list)
    elapsed_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind, "mode": self.mode, "run_id": self.run_id, "rows": self.rows,
            "targets": self.targets, "failed_targets": self.failed_targets[:100],
            "n_notes": len(self.notes), "elapsed_s": round(self.elapsed_s, 2),
        }


def _default_price_providers() -> dict[str, PriceProvider]:
    from .sources.akshare_cn_index import AkshareCnIndexProvider
    from .sources.yahoo import YahooPriceProvider

    return {"yahoo": YahooPriceProvider(), "akshare_cn_index": AkshareCnIndexProvider()}


def _default_indicator_providers() -> dict[str, IndicatorProvider]:
    from .sources import registry

    return registry.build_indicator_providers()


class Ingestor:
    def __init__(
        self,
        store: Store,
        *,
        universe: Universe | None = None,
        curves: dict[str, CurveDef] | None = None,
        macro: dict[str, MacroSeries] | None = None,
        positioning: dict[str, PositioningSeries] | None = None,
        price_providers: dict[str, PriceProvider] | None = None,
        indicator_providers: dict[str, IndicatorProvider] | None = None,
    ):
        self.store = store
        self.universe = universe or load_universe()
        self.curves = curves or load_curves()
        self.macro = macro or load_macro()
        self.positioning = positioning or load_positioning()
        self.price_providers = price_providers or _default_price_providers()
        self.indicator_providers = indicator_providers or _default_indicator_providers()

    # ---------------------------------------------------------------- metadata
    def register_metadata(self) -> None:
        self.store.upsert_sources(load_sources())
        self.store.upsert_instruments(self.universe.instruments.values())
        rows = []
        for c in self.curves.values():
            rows.append({"series_id": c.id, "name": c.name, "kind": "curve", "unit": "percent",
                         "region": c.region, "frequency": "daily", "provider": c.provider,
                         "tier": c.tier, "notes": c.notes})
        for m in self.macro.values():
            rows.append({"series_id": m.id, "name": m.name, "kind": "macro", "unit": m.unit,
                         "region": m.region, "frequency": m.frequency, "provider": m.provider,
                         "tier": m.tier, "notes": m.notes})
        for p in self.positioning.values():
            rows.append({"series_id": p.id, "name": p.name, "kind": "positioning", "unit": p.unit,
                         "region": "WORLD", "frequency": "weekly", "provider": p.provider,
                         "tier": "official", "notes": f"CFTC {p.report} report"})
            rows.append({"series_id": f"{p.id}:oi", "name": p.name + " (open interest)", "kind": "positioning",
                         "unit": "contracts", "region": "WORLD", "frequency": "weekly",
                         "provider": p.provider, "tier": "official",
                         "notes": f"CFTC {p.report} report open interest"})
        self.store.upsert_series_meta(rows)

    # ------------------------------------------------------------------ prices
    def _price_start(self, instrument_id: str, mode: str) -> str:
        if mode == "backfill":
            return BACKFILL_START
        last = self.store.scalar(
            "SELECT MAX(date) FROM prices WHERE instrument_id=?", (instrument_id,)
        )
        if not last:
            return BACKFILL_START
        d = datetime.strptime(last, "%Y-%m-%d").date() - timedelta(days=OVERLAP_DAYS)
        return d.isoformat()

    def ingest_prices(self, mode: str = "incremental",
                      instruments: Sequence[str] | None = None) -> IngestStats:
        run_id = self.store.start_run("prices", mode)
        stats = IngestStats(kind="prices", mode=mode, run_id=run_id)
        t0 = datetime.now(timezone.utc)
        chosen = [self.universe.instruments[i] for i in (instruments or list(self.universe.instruments))]
        by_source: dict[str, list[dict[str, Any]]] = {}
        for inst in chosen:
            by_source.setdefault(inst.source, []).append(
                {"id": inst.id, "symbol": inst.symbol, "currency": inst.currency}
            )
        errors: list[str] = []
        try:
            for source_id, specs in by_source.items():
                provider = self.price_providers.get(source_id)
                if provider is None:
                    msg = f"no price provider registered for source '{source_id}'"
                    errors.append(msg)
                    stats.failed_targets.extend(s["id"] for s in specs)
                    self.store.log_issue(run_id, source_id, "provider_missing", "error", msg)
                    continue
                start = min(self._price_start(s["id"], mode) for s in specs)
                res: FetchResult = provider.fetch_prices(specs, start=start)
                stats.rows += self.store.upsert_prices(res.frame, run_id)
                stats.targets += len(specs)
                stats.notes.extend(n.__dict__ for n in res.notes)
                for note in res.notes:
                    self.store.log_issue(run_id, note.target, note.code,
                                         "warning" if note.severity == "warning" else note.severity, note.detail)
                errors.extend(res.errors)
                for err in res.errors[:50]:
                    self.store.log_issue(run_id, source_id, "fetch_error", "error", err)
                if res.frame.empty:
                    present: dict[str, int] = {}
                else:
                    present = res.frame.groupby("instrument_id").size().to_dict()
                missing = {s["id"] for s in specs if present.get(s["id"], 0) < 20}
                stats.failed_targets.extend(sorted(missing))
                for mid in sorted(missing):
                    self.store.log_issue(run_id, mid, "insufficient_rows", "warning",
                                         f"provider returned {present.get(mid, 0)} valid rows")
            status = "success" if not errors else ("partial" if stats.rows else "failed")
            self.store.finish_run(run_id, status, stats.to_dict(), errors)
            if stats.rows == 0:
                raise IngestError(f"price ingestion fetched 0 rows: {errors[:3]}")
            return stats
        except Exception as exc:
            self.store.finish_run(run_id, "failed", stats.to_dict(), errors + [str(exc)])
            raise
        finally:
            stats.elapsed_s = (datetime.now(timezone.utc) - t0).total_seconds()

    # -------------------------------------------------------------- indicators
    def indicator_specs(self) -> dict[str, list[dict[str, Any]]]:
        """Group indicator definitions by provider id."""
        grouped: dict[str, list[dict[str, Any]]] = {}
        for c in self.curves.values():
            grouped.setdefault(c.provider, []).append({
                "id": c.id, "kind": "curve", "name": c.name, "tenors": list(c.tenors),
                "start_year": c.start_year, "region": c.region, "currency": c.currency,
            })
        for m in self.macro.values():
            grouped.setdefault(m.provider, []).append({
                "id": m.id, "kind": "macro", "name": m.name, "series": m.series,
                "unit": m.unit, "region": m.region, "frequency": m.frequency,
                "importance": m.importance,
            })
        for p in self.positioning.values():
            grouped.setdefault(p.provider, []).append({
                "id": p.id, "kind": "positioning", "name": p.name, "report": p.report,
                "market": p.market, "metric": p.metric, "unit": p.unit,
            })
        return grouped

    def _indicator_start(self, spec: dict[str, Any], mode: str) -> str | None:
        if mode == "backfill":
            if spec["kind"] == "curve":
                return f"{spec.get('start_year', 2014)}-01-01"
            return BACKFILL_START
        existing = self.store.indicator_series_ids(spec["id"])
        prefix = spec["id"] + ":"
        relevant = [s for s in existing if s == spec["id"] or s.startswith(prefix)]
        last = None
        if relevant:
            last = self.store.scalar(
                f"SELECT MAX(date) FROM indicators WHERE series_id IN ({','.join('?' for _ in relevant)})",
                tuple(relevant),
            )
        if not last:
            if spec["kind"] == "curve":
                return f"{spec.get('start_year', 2014)}-01-01"
            return BACKFILL_START
        return (datetime.strptime(last, "%Y-%m-%d").date() - timedelta(days=OVERLAP_DAYS)).isoformat()

    def ingest_indicators(self, mode: str = "incremental",
                          providers: Sequence[str] | None = None) -> IngestStats:
        run_id = self.store.start_run("indicators", mode)
        stats = IngestStats(kind="indicators", mode=mode, run_id=run_id)
        t0 = datetime.now(timezone.utc)
        grouped = self.indicator_specs()
        if providers:
            grouped = {k: v for k, v in grouped.items() if k in providers}
        errors: list[str] = []
        try:
            for provider_id, specs in grouped.items():
                provider = self.indicator_providers.get(provider_id)
                if provider is None:
                    msg = f"no indicator provider registered for '{provider_id}'"
                    errors.append(msg)
                    self.store.log_issue(run_id, provider_id, "provider_missing", "error", msg)
                    stats.failed_targets.extend(s["id"] for s in specs)
                    continue
                # providers receive per-spec start hints; earliest wins
                starts = [s for s in (self._indicator_start(spec, mode) for spec in specs) if s]
                start = min(starts) if starts else None
                try:
                    res = provider.fetch_indicators(specs, start=start)
                except Exception as exc:  # noqa: BLE001 - isolate provider failure
                    errors.append(f"{provider_id}: {type(exc).__name__}: {exc}")
                    self.store.log_issue(run_id, provider_id, "fetch_failed", "error", str(exc))
                    stats.failed_targets.extend(s["id"] for s in specs)
                    continue
                stats.rows += self.store.upsert_indicators(res.frame, run_id)
                stats.targets += len(specs)
                for note in res.notes:
                    self.store.log_issue(run_id, note.target, note.code,
                                         "warning" if note.severity == "warning" else note.severity, note.detail)
                stats.notes.extend(n.__dict__ for n in res.notes)
                errors.extend(res.errors)
                for err in res.errors[:30]:
                    self.store.log_issue(run_id, provider_id, "fetch_error", "error", err)
            status = "success" if not errors else ("partial" if stats.rows else "failed")
            self.store.finish_run(run_id, status, stats.to_dict(), errors)
            if stats.rows == 0:
                raise IngestError(f"indicator ingestion fetched 0 rows: {errors[:3]}")
            return stats
        except Exception as exc:
            self.store.finish_run(run_id, "failed", stats.to_dict(), errors + [str(exc)])
            raise
        finally:
            stats.elapsed_s = (datetime.now(timezone.utc) - t0).total_seconds()

    # --------------------------------------------------------------------- run
    def run(self, mode: str = "daily") -> dict[str, Any]:
        self.register_metadata()
        out: dict[str, Any] = {}
        try:
            out["prices"] = self.ingest_prices(mode=mode).to_dict()
        except IngestError as exc:
            out["prices_error"] = str(exc)
        try:
            out["indicators"] = self.ingest_indicators(mode=mode).to_dict()
        except IngestError as exc:
            out["indicators_error"] = str(exc)
        return out
