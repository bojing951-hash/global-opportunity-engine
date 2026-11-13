"""China government bond yields via akshare (aggregator; graceful degradation).

``akshare.bond_zh_us_yield_em`` (東财 / ChinaBond redistribution) returns a wide
daily table with China 2Y/5Y/10Y/30Y government yields plus US Treasury yields.
**Akshare renamed the function**: 1.20.42 (installed 2026-11-13) has no
``bond_zh_us_rate``, only ``bond_zh_us_yield_em`` with the same ``start_date``
argument and the same columns. The provider prefers the old name when present
and falls back to the new one, so it works on both branches of akshare.

The import is lazy and any network failure (eastmoney/jin10 are flaky from some
networks: ProxyError/SSLError/ReadTimeout) is returned as a FetchNote with
severity ``error`` rather than raised, so a blocked aggregator never aborts the
rest of the ingest.

``CN:US10Y_CHECK`` is emitted from the US 10Y column of the same call as an
internal cross-check against ``treasury_us`` (it is deliberately not part of
``docs/id_reference.md``). akshare performs its own HTTP internally; that is
the one adapter where requests cannot be routed through ``shared_client``.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from .. import project_root
from .base import FetchNote, FetchResult, IndicatorProvider, normalize_indicators

CACHE_DIR = "akshare_cn_bond"
CACHE_TTL_HOURS = 12
CACHE_NAME = "bond_zh_us_yield_em.csv"
CALL_START = "20140101"
YIELD_MIN, YIELD_MAX = 0.0, 30.0

COLUMN_MAP = {
    "中国国债收益率2年": "CN:2Y",
    "中国国债收益率5年": "CN:5Y",
    "中国国债收益率10年": "CN:10Y",
    "中国国债收益率30年": "CN:30Y",
    "美国国债收益率10年": "CN:US10Y_CHECK",
}
DATE_COLUMN = "日期"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cache_path() -> Path:
    path = project_root() / "data" / "cache" / CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path / CACHE_NAME


def parse_akshare_frame(df: pd.DataFrame, start: str | None = None) -> pd.DataFrame:
    """Melt the akshare wide table into canonical ``series_id,date,value,unit`` rows."""
    if df is None or df.empty or DATE_COLUMN not in df.columns:
        return pd.DataFrame(columns=["series_id", "date", "value", "unit"])
    dates = pd.to_datetime(df[DATE_COLUMN], errors="coerce")
    frames: list[pd.DataFrame] = []
    for column, series_id in COLUMN_MAP.items():
        if column not in df.columns:
            continue
        part = pd.DataFrame(
            {
                "series_id": series_id,
                "date": dates,
                "value": pd.to_numeric(df[column], errors="coerce"),
            }
        ).dropna(subset=["date", "value"])
        if not part.empty:
            frames.append(part)
    if not frames:
        return pd.DataFrame(columns=["series_id", "date", "value", "unit"])
    out = pd.concat(frames, ignore_index=True)
    out["unit"] = "percent"
    if start:
        out = out[out["date"] >= pd.Timestamp(start)]
    return out


class AkshareCnBondProvider(IndicatorProvider):
    provider_id = "akshare_cn_bond"

    def __init__(self, client: Any | None = None) -> None:
        self._client = client  # unused; kept for adapter-signature parity

    def fetch_indicators(
        self, specs: Sequence[dict[str, Any]], start: str | None = None
    ) -> FetchResult:
        t0 = time.monotonic()
        fetched_at = _utc_now()
        notes: list[FetchNote] = []
        errors: list[str] = []

        wanted_ids = {str(s["id"]) + ":" + t for s in specs if s.get("kind") == "curve"
                      for t in (s.get("tenors") or [])}
        tenors = {t for s in specs if s.get("kind") == "curve" for t in (s.get("tenors") or [])}
        if specs and not tenors:
            notes.append(FetchNote("no_tenors", "warning",
                                   "akshare_cn_bond: no curve tenors requested", "akshare_cn_bond"))

        raw = self._load_frame(start, notes, errors)
        frame = parse_akshare_frame(raw, start) if raw is not None else pd.DataFrame(
            columns=["series_id", "date", "value", "unit"]
        )
        if not frame.empty:
            # keep requested tenors plus the US cross-check series
            frame = frame[frame["series_id"].isin(wanted_ids | {"CN:US10Y_CHECK"})]
            bad = ~frame["value"].between(YIELD_MIN, YIELD_MAX, inclusive="neither")
            n_bad = int(bad.sum())
            if n_bad:
                notes.append(FetchNote("validation_dropped", "warning",
                                       f"akshare_cn_bond dropped {n_bad} rows outside "
                                       f"({YIELD_MIN}, {YIELD_MAX})", "akshare_cn_bond"))
                frame = frame[~bad]
            missing = sorted(wanted_ids - set(frame["series_id"]))
            if missing:
                notes.append(FetchNote("series_missing", "warning",
                                       f"akshare_cn_bond: no observations for {missing}",
                                       "akshare_cn_bond"))
            if not frame.empty:
                last = frame["date"].max()
                notes.append(FetchNote("coverage", "info",
                                       f"akshare_cn_bond observations through {last.date()}",
                                       "akshare_cn_bond"))
        if frame.empty:
            if not notes:
                notes.append(FetchNote("no_data", "error",
                                       "akshare_cn_bond returned no usable observations",
                                       "akshare_cn_bond"))
            if not errors:
                errors.append("akshare_cn_bond: no usable observations (source unavailable or blocked)")
            return FetchResult(frame=normalize_indicators(pd.DataFrame(), self.provider_id, fetched_at),
                               source_id=self.provider_id, fetched_at=fetched_at,
                               notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)
        frame = normalize_indicators(frame, self.provider_id, fetched_at)
        return FetchResult(frame=frame, source_id=self.provider_id, fetched_at=fetched_at,
                           notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)

    # ------------------------------------------------------------------ source
    def _load_frame(
        self, start: str | None, notes: list[FetchNote], errors: list[str]
    ) -> pd.DataFrame | None:
        path = _cache_path()
        cached: pd.DataFrame | None = None
        if path.exists() and (time.time() - path.stat().st_mtime) < CACHE_TTL_HOURS * 3600:
            try:
                cached = pd.read_csv(path, dtype={DATE_COLUMN: str})
            except Exception as exc:  # noqa: BLE001 - corrupt cache
                notes.append(FetchNote("cache_unreadable", "warning",
                                       f"akshare cache unreadable ({exc}); refetching",
                                       "akshare_cn_bond"))
        if cached is not None and DATE_COLUMN in cached.columns:
            cache_dates = pd.to_datetime(cached[DATE_COLUMN], errors="coerce")
            required = pd.Timestamp(start) if start else pd.Timestamp("2014-01-01")
            # A cache written from a later start must not masquerade as full history.
            if cache_dates.notna().any() and cache_dates.min() <= required + pd.Timedelta(days=5):
                return cached
            notes.append(FetchNote("cache_insufficient", "warning",
                                   f"akshare cache starts {cache_dates.min().date()} but "
                                   f"{required.date()} was requested; refetching full history",
                                   "akshare_cn_bond"))
        try:
            import akshare as ak  # lazy: akshare is an optional heavy dependency
        except Exception as exc:  # noqa: BLE001 - optional dependency
            message = f"akshare import failed: {type(exc).__name__}: {exc}"
            errors.append(message)
            notes.append(FetchNote("dependency_missing", "error", message, "akshare_cn_bond"))
            return None

        function = getattr(ak, "bond_zh_us_rate", None) or getattr(ak, "bond_zh_us_yield_em", None)
        if function is None:
            message = ("akshare has neither bond_zh_us_rate nor bond_zh_us_yield_em; "
                       "cannot fetch China government yields")
            errors.append(message)
            notes.append(FetchNote("api_missing", "error", message, "akshare_cn_bond"))
            return None

        # The akshare endpoint paginates from its own start; requesting the
        # configured first year keeps the cache full-history regardless of the
        # incremental ``start`` passed by the ingestor.
        call_start = CALL_START
        try:
            raw = function(start_date=call_start)
        except Exception as exc:  # noqa: BLE001 - flaky aggregator
            message = f"akshare {getattr(function, '__name__', 'bond')} failed: {type(exc).__name__}: {exc}"
            errors.append(message)
            notes.append(FetchNote("fetch_failed", "error", message, "akshare_cn_bond"))
            if path.exists():
                try:
                    cached = pd.read_csv(path, dtype={DATE_COLUMN: str})
                    notes.append(FetchNote("cache_fallback", "warning",
                                           "using cached akshare table after a failed refresh",
                                           "akshare_cn_bond"))
                    return cached
                except Exception:  # noqa: BLE001
                    return None
            return None
        if raw is None or raw.empty:
            message = "akshare returned an empty frame"
            errors.append(message)
            notes.append(FetchNote("empty_frame", "error", message, "akshare_cn_bond"))
            return None
        try:
            raw.to_csv(path, index=False)
        except Exception as exc:  # noqa: BLE001 - cache write is best effort
            notes.append(FetchNote("cache_write_failed", "warning",
                                   f"could not write akshare cache: {exc}", "akshare_cn_bond"))
        return raw
