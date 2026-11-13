"""US BLS public API v1 adapter (official, monthly releases).

Endpoint (POST JSON, no key)::

    https://api.bls.gov/publicAPI/v1/timeseries/data/
    {"seriesid": ["CUUR0000SA0", ...], "startyear": "2015", "endyear": "2026"}

v1 limits (verified against the live API 2026-11-13): at most 25 series and at
most 10 years per request, and a small unauthenticated daily quota. Requests
are therefore split into <=10-year windows and the raw JSON responses are
cached under ``data/cache/bls`` (the current window is refreshed every 12h) so
repeated runs do not burn quota.

Response quirks: ``Results.series[*].data[*]`` carries ``year``, ``period``
(``M01``..``M12``; ``M13`` is the annual average and is skipped) and a string
``value``. Monthly dates are stored as ``YYYY-MM-01``. ``CES`` payroll levels
are already in thousands.
"""

from __future__ import annotations

import json
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from .. import project_root
from .base import FetchNote, FetchResult, IndicatorProvider, ProviderError, normalize_indicators
from .http import shared_client

CACHE_DIR = "bls"
URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
MAX_SERIES_PER_REQUEST = 25
MAX_YEARS_PER_REQUEST = 10
CACHE_TTL_HOURS = 12


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cache_path(name: str) -> Path:
    path = project_root() / "data" / "cache" / CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path / name


def parse_bls_json(payload: dict[str, Any]) -> tuple[pd.DataFrame, str, list[str]]:
    """Parse a BLS v1 response into ``date, series_id, value`` rows.

    Returns ``(frame, status, messages)``. ``M13`` annual-average rows are
    skipped; non-numeric placeholder values are dropped, never coerced to 0.
    """
    status = str(payload.get("status", ""))
    messages = [str(m) for m in (payload.get("message") or [])]
    rows: list[tuple[pd.Timestamp, str, float]] = []
    results = payload.get("Results") or {}
    for series in results.get("series") or []:
        series_id = series.get("seriesID") or series.get("seriesId")
        if not series_id:
            continue
        for item in series.get("data") or []:
            period = str(item.get("period", ""))
            if not period.startswith("M") or period == "M13":
                continue
            try:
                year = int(item["year"])
                month = int(period[1:])
            except (KeyError, TypeError, ValueError):
                continue
            if not 1 <= month <= 12:
                continue
            raw = item.get("value")
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            rows.append((pd.Timestamp(year=year, month=month, day=1), str(series_id), value))
    frame = pd.DataFrame(rows, columns=["date", "series_id", "value"])
    if not frame.empty:
        frame = frame.drop_duplicates(subset=["series_id", "date"], keep="last")
    return frame, status, messages


class BlsProvider(IndicatorProvider):
    provider_id = "bls"

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Any:
        return self._client or shared_client()

    def fetch_indicators(
        self, specs: Sequence[dict[str, Any]], start: str | None = None
    ) -> FetchResult:
        t0 = time.monotonic()
        fetched_at = _utc_now()
        notes: list[FetchNote] = []
        errors: list[str] = []

        macro_specs = [s for s in specs if s.get("kind") == "macro" and s.get("series")]
        skipped = [s for s in specs if s.get("kind") != "macro"]
        for spec in skipped:
            notes.append(FetchNote("unsupported_spec", "warning",
                                   f"bls ignores kind={spec.get('kind')}", spec.get("id", "")))
        if not macro_specs:
            raise ProviderError("bls: no macro specs supplied")

        current_year = datetime.now(timezone.utc).year
        start_year = int(str(start)[:4]) if start else 2015
        start_year = max(1990, start_year)
        series_ids = sorted({str(s["series"]) for s in macro_specs})
        unit_by_series = {str(s["series"]): str(s.get("unit") or "") for s in macro_specs}
        id_by_series = {str(s["series"]): str(s["id"]) for s in macro_specs}

        frames: list[pd.DataFrame] = []
        for window_start in range(start_year, current_year + 1, MAX_YEARS_PER_REQUEST):
            window_end = min(window_start + MAX_YEARS_PER_REQUEST - 1, current_year)
            for i in range(0, len(series_ids), MAX_SERIES_PER_REQUEST):
                batch = series_ids[i : i + MAX_SERIES_PER_REQUEST]
                try:
                    payload = self._request_window(batch, window_start, window_end, current_year, notes)
                except Exception as exc:  # noqa: BLE001 - provider boundary
                    errors.append(f"BLS {window_start}-{window_end}: {type(exc).__name__}: {exc}")
                    notes.append(FetchNote("window_failed", "error",
                                           f"BLS {window_start}-{window_end} request failed: {exc}",
                                           "bls"))
                    continue
                parsed, status, messages = parse_bls_json(payload)
                if status != "REQUEST_SUCCEEDED":
                    errors.append(f"BLS status={status} for {window_start}-{window_end}: {messages[:2]}")
                    notes.append(FetchNote("api_status", "error",
                                           f"BLS returned status={status}: {messages[:2]}", "bls"))
                for message in messages:
                    # v1 informational messages (e.g. year range reduced) are useful provenance.
                    if "range has been reduced" in message.lower():
                        notes.append(FetchNote("window_clamped", "warning", message, "bls"))
                if parsed.empty:
                    notes.append(FetchNote("window_empty", "warning",
                                           f"BLS {window_start}-{window_end}: no usable observations",
                                           "bls"))
                    continue
                frames.append(parsed)

        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
            columns=["date", "series_id", "value"]
        )
        fetched_any = not frame.empty
        if not frame.empty:
            frame = frame[frame["series_id"].isin(series_ids)]
            if start:
                frame = frame[frame["date"] >= pd.Timestamp(start)]
            frame = frame.drop_duplicates(subset=["series_id", "date"], keep="last")

        # ------------------------------------------------------------ validate
        out = frame.copy()
        out["unit"] = out["series_id"].map(unit_by_series).fillna("")
        out["id"] = out["series_id"].map(id_by_series)
        if not out.empty:
            finite = out["value"].notna() & out["value"].apply(lambda v: abs(float(v)) != float("inf"))
            index_ok = ~out["unit"].eq("index") | (out["value"] > 0)
            thousands_ok = ~out["unit"].eq("thousands") | (out["value"] > 0)
            percent_ok = ~out["unit"].eq("percent") | out["value"].between(-100, 100)
            keep = finite & index_ok & thousands_ok & percent_ok
            n_bad = int((~keep).sum())
            if n_bad:
                notes.append(FetchNote("validation_dropped", "warning",
                                       f"bls dropped {n_bad} rows failing unit/range checks", "bls"))
                out = out[keep]

        self._cross_check_cpi(out, notes)

        if out.empty:
            if fetched_any:
                notes.append(FetchNote("no_new_observations", "info",
                                       f"bls: source data ends before requested start {start}", "bls"))
                return FetchResult(frame=normalize_indicators(pd.DataFrame(), self.provider_id, fetched_at),
                                   source_id=self.provider_id, fetched_at=fetched_at,
                                   notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)
            raise ProviderError(f"{self.provider_id}: no BLS rows fetched ({'; '.join(errors[:3])})")
        out["series_id"] = out["id"]
        out = out[["series_id", "date", "value", "unit"]]
        result = normalize_indicators(out, self.provider_id, fetched_at)
        return FetchResult(frame=result, source_id=self.provider_id, fetched_at=fetched_at,
                           notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)

    # ------------------------------------------------------------------ cache
    def _request_window(
        self,
        series: list[str],
        start_year: int,
        end_year: int,
        current_year: int,
        notes: list[FetchNote],
    ) -> dict[str, Any]:
        path = _cache_path(
            f"bls_{start_year}_{end_year}_{hashlib.md5(','.join(series).encode()).hexdigest()[:8]}.json"
        )
        covers_current = end_year >= current_year
        fresh = path.exists() and (
            not covers_current
            or (time.time() - path.stat().st_mtime) < CACHE_TTL_HOURS * 3600
        )
        if fresh:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001 - corrupt cache
                notes.append(FetchNote("cache_unreadable", "warning",
                                       f"BLS cache {path.name} unreadable ({exc}); refetching", "bls"))
        body = {"seriesid": series, "startyear": str(start_year), "endyear": str(end_year)}
        try:
            resp = self.client.request("POST", URL, json=body,
                                       headers={"Content-Type": "application/json"})
            payload = resp.json()
        except Exception:
            if path.exists():
                notes.append(FetchNote("cache_fallback", "warning",
                                       f"BLS {start_year}-{end_year} request failed; using cached response",
                                       "bls"))
                return json.loads(path.read_text(encoding="utf-8"))
            raise
        if str(payload.get("status", "")) == "REQUEST_SUCCEEDED":
            path.write_text(json.dumps(payload), encoding="utf-8")
        elif path.exists():
            # Never let a rate-limit / failure response poison the cache.
            notes.append(FetchNote("cache_fallback", "warning",
                                   f"BLS {start_year}-{end_year} returned "
                                   f"status={payload.get('status')}; using cached response",
                                   "bls"))
            return json.loads(path.read_text(encoding="utf-8"))
        return payload

    # ------------------------------------------------------------------ checks
    def _cross_check_cpi(self, frame: pd.DataFrame, notes: list[FetchNote]) -> None:
        cpi = frame[frame["series_id"] == "CUUR0000SA0"].sort_values("date")
        if len(cpi) < 13:
            return
        latest = cpi.iloc[-1]
        prior_date = latest["date"] - pd.DateOffset(months=12)
        prior = cpi[cpi["date"] == prior_date]
        if prior.empty:
            notes.append(FetchNote(
                "cpi_crosscheck_skipped", "info",
                f"no CPI observation at {prior_date.date()} in the BLS response; YoY cross-check skipped",
                "US_CPI",
            ))
            return
        yoy = (float(latest["value"]) / float(prior.iloc[-1]["value"]) - 1.0) * 100.0
        if not -15.0 < yoy < 15.0:
            notes.append(FetchNote("cpi_crosscheck", "warning",
                                   f"US_CPI YoY for {latest['date'].date()} is {yoy:.2f}% (outside -15..15%)",
                                   "US_CPI"))
        else:
            notes.append(FetchNote("cpi_crosscheck", "info",
                                   f"US_CPI YoY for {latest['date'].date()} = {yoy:.2f}%", "US_CPI"))
