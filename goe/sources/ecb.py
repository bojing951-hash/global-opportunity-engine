"""Euro area AAA central-government yield curve adapter (ECB Data Portal).

SDMX endpoint, one series per tenor (verified 2026-11-13)::

    https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y
        ?format=csvdata&startPeriod=2014-01-01

The flow key prefix ``YC/B.U2.EUR.4F.G_N_A.SV_C_YM.`` is fixed and only the
``SR_<tenor>`` dimension changes. Response is a plain CSV with
``TIME_PERIOD``/``OBS_VALUE``; no key is required.

Notes
-----
* The curve is the AAA-rated euro-area central-government curve, not a single
  issuer, and it traded negative for long stretches (3M min -0.93% in 2021) so
  the sanity window is (-5, 30) percent.
* Missing tenors (404 or an empty CSV) become a warning note, never a crash.
* Per-tenor CSVs are cached under ``data/cache/ecb``; an incremental run tops
  up only the recent tail (see ``_load_tenor``) instead of re-downloading the
  full 2014+ history.
"""

from __future__ import annotations

import io
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from .. import project_root
from .base import FetchNote, FetchResult, IndicatorProvider, ProviderError, normalize_indicators
from .http import shared_client

CACHE_DIR = "ecb"
CACHE_TTL_HOURS = 12
BASE_URL = (
    "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_{tenor}"
    "?format=csvdata&startPeriod={start}"
)
YIELD_MIN, YIELD_MAX = -5.0, 30.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cache_path(tenor: str) -> Path:
    path = project_root() / "data" / "cache" / CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path / f"SR_{tenor}.csv"


def parse_ecb_csv(text: str) -> pd.DataFrame:
    """Parse an ECB ``csvdata`` response into ``date, value``."""
    if not text or not text.strip():
        return pd.DataFrame(columns=["date", "value"])
    raw = pd.read_csv(io.StringIO(text))
    if "TIME_PERIOD" not in raw.columns or "OBS_VALUE" not in raw.columns:
        raise ValueError("ECB CSV lacks TIME_PERIOD/OBS_VALUE columns")
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(raw["TIME_PERIOD"], errors="coerce"),
            "value": pd.to_numeric(raw["OBS_VALUE"], errors="coerce"),
        }
    )
    return out.dropna(subset=["date", "value"]).drop_duplicates(subset=["date"], keep="last")


class EcbProvider(IndicatorProvider):
    provider_id = "ecb"

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
        frames: list[pd.DataFrame] = []
        fetched_any = False

        for spec in specs:
            if spec.get("kind") != "curve":
                notes.append(FetchNote("unsupported_spec", "warning",
                                       f"ecb ignores kind={spec.get('kind')}", spec.get("id", "")))
                continue
            tenors = list(spec.get("tenors") or [])
            for tenor in tenors:
                try:
                    series = self._load_tenor(tenor, start, notes)
                except Exception as exc:  # noqa: BLE001 - provider boundary
                    errors.append(f"ECB {tenor}: {type(exc).__name__}: {exc}")
                    notes.append(FetchNote("tenor_failed", "error",
                                           f"ECB {tenor} request failed: {exc}", f"{spec['id']}:{tenor}"))
                    continue
                if series is None or series.empty:
                    notes.append(FetchNote("tenor_empty", "warning",
                                           f"ECB {tenor}: no observations returned (tenor may not exist)",
                                           f"{spec['id']}:{tenor}"))
                    continue
                part = series.copy()
                fetched_any = True
                if start:
                    part = part[part["date"] >= pd.Timestamp(start)]
                if part.empty:
                    notes.append(FetchNote("tenor_empty_window", "warning",
                                           f"ECB {tenor}: no observations on/after {start}",
                                           f"{spec['id']}:{tenor}"))
                    continue
                part["series_id"] = f"{spec['id']}:{tenor}"
                part["unit"] = "percent"
                frames.append(part[["series_id", "date", "value", "unit"]])

        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
            columns=["series_id", "date", "value", "unit"]
        )
        if not frame.empty:
            bad = ~frame["value"].between(YIELD_MIN, YIELD_MAX, inclusive="neither") | ~frame["value"].notna()
            n_bad = int(bad.sum())
            if n_bad:
                notes.append(FetchNote("validation_dropped", "warning",
                                       f"ecb dropped {n_bad} rows outside ({YIELD_MIN}, {YIELD_MAX})", "ecb"))
                frame = frame[~bad]
        if frame.empty:
            if fetched_any:
                notes.append(FetchNote("no_new_observations", "info",
                                       f"ecb: source data ends before requested start {start}", "ecb"))
                return FetchResult(frame=normalize_indicators(pd.DataFrame(), self.provider_id, fetched_at),
                                   source_id=self.provider_id, fetched_at=fetched_at,
                                   notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)
            raise ProviderError(f"{self.provider_id}: no euro-area curve rows fetched ({'; '.join(errors[:3])})")
        frame = normalize_indicators(frame, self.provider_id, fetched_at)
        return FetchResult(frame=frame, source_id=self.provider_id, fetched_at=fetched_at,
                           notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)

    # ------------------------------------------------------------------ cache
    def _load_tenor(self, tenor: str, start: str | None, notes: list[FetchNote]) -> pd.DataFrame | None:
        path = _cache_path(tenor)
        cached: pd.DataFrame | None = None
        if path.exists() and path.stat().st_size > 0:
            try:
                cached = parse_ecb_csv(path.read_text(encoding="utf-8-sig"))
            except Exception as exc:  # noqa: BLE001 - corrupt cache
                notes.append(FetchNote("cache_unreadable", "warning",
                                       f"ECB cache for {tenor} unreadable ({exc}); refetching", f"ecb:{tenor}"))
        required_start = pd.Timestamp(start) if start else pd.Timestamp("2014-01-01")
        covers_window = (
            cached is not None
            and not cached.empty
            and cached["date"].min() <= required_start + pd.Timedelta(days=5)
        )
        age_ok = path.exists() and (time.time() - path.stat().st_mtime) < CACHE_TTL_HOURS * 3600
        if cached is not None and age_ok and covers_window:
            return cached

        # Full history when the cache cannot cover the requested window;
        # otherwise only top up the tail (with a small overlap for revisions).
        request_start = "2014-01-01"
        if cached is not None and not cached.empty and covers_window and start:
            cache_last = cached["date"].max()
            tail_start = min(pd.Timestamp(start), cache_last - pd.Timedelta(days=10))
            request_start = tail_start.date().isoformat()
        elif cached is None and start:
            request_start = str(start)

        body = self.client.get(BASE_URL.format(tenor=tenor, start=request_start)).content
        text = body.decode("utf-8-sig", errors="replace")
        fresh = parse_ecb_csv(text)
        if cached is not None and not cached.empty and request_start != "2014-01-01":
            merged = pd.concat([cached, fresh], ignore_index=True)
            merged = merged.drop_duplicates(subset=["date"], keep="last").sort_values("date")
        else:
            merged = fresh
        # Store the cache in the same two-column shape the parser consumes.
        # (The raw csvdata response has ~40 columns incl. long descriptions.)
        canonical = merged.rename(columns={"date": "TIME_PERIOD", "value": "OBS_VALUE"})
        path.write_text(canonical.to_csv(index=False), encoding="utf-8")
        return merged.reset_index(drop=True)
