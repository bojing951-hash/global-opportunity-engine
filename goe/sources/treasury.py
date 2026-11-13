"""US Treasury daily par yield curve adapter (official, end-of-day).

Endpoint (one CSV per calendar year, verified 2026-11-13)::

    https://home.treasury.gov/resource-center/data-chart-center/interest-rates/
        daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve
        &field_tdr_date_value={year}&page&_format=csv

Format quirks
-------------
* The header is not stable across years: ``2 Mo`` first appears in the 2018
  file, ``4 Mo`` in the 2023 file, and a non-config ``1.5 Month`` column appears
  from 2025. Unknown columns are ignored; requested tenors that are absent from
  a year are simply not produced (never filled).
* Dates are ``MM/DD/YYYY`` (US order), values are par yields in percent.
* A year file may be missing entirely for a very recent year before the first
  business day; that is recorded as an error, not as an empty series.

Coverage 2014-2026 (observed): UST:2M starts 2018-01-02, UST:4M starts
2023-01-03; every other configured tenor is available from 2014-01-02.
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

CACHE_DIR = "treasury_us"
BASE_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
    "&field_tdr_date_value={year}&page&_format=csv"
)

# Tenor labels used by the Treasury CSV -> canonical tenor strings in config.
COLUMN_TO_TENOR = {
    "1 Mo": "1M",
    "2 Mo": "2M",
    "3 Mo": "3M",
    "4 Mo": "4M",
    "6 Mo": "6M",
    "1 Yr": "1Y",
    "2 Yr": "2Y",
    "3 Yr": "3Y",
    "5 Yr": "5Y",
    "7 Yr": "7Y",
    "10 Yr": "10Y",
    "20 Yr": "20Y",
    "30 Yr": "30Y",
}

YIELD_MIN, YIELD_MAX = 0.0, 25.0  # inclusive left: 0.00 is a real bill yield (2014-2015 ZIRP)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cache_path(name: str) -> Path:
    path = project_root() / "data" / "cache" / CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path / name


def parse_treasury_csv(text: str) -> pd.DataFrame:
    """Parse one yearly Treasury CSV into a long ``date, tenor, value`` frame.

    Pure function (no network) so the layout can be unit-tested offline.
    """
    if not text or not text.strip():
        return pd.DataFrame(columns=["date", "tenor", "value"])
    raw = pd.read_csv(io.StringIO(text))
    if "Date" not in raw.columns:
        raise ValueError("treasury CSV has no Date column")
    raw = raw.rename(columns={"Date": "date"})
    raw["date"] = pd.to_datetime(raw["date"], format="%m/%d/%Y", errors="coerce")
    raw = raw.dropna(subset=["date"])

    rows: list[pd.DataFrame] = []
    for column, tenor in COLUMN_TO_TENOR.items():
        if column not in raw.columns:
            continue
        part = pd.DataFrame(
            {
                "date": raw["date"],
                "tenor": tenor,
                "value": pd.to_numeric(raw[column], errors="coerce"),
            }
        )
        rows.append(part)
    if not rows:
        raise ValueError("treasury CSV has no recognised yield columns")
    out = pd.concat(rows, ignore_index=True)
    out = out.dropna(subset=["value"])
    return out


class TreasuryUSProvider(IndicatorProvider):
    provider_id = "treasury_us"

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Any:
        return self._client or shared_client()

    # ------------------------------------------------------------------ fetch
    def fetch_indicators(
        self, specs: Sequence[dict[str, Any]], start: str | None = None
    ) -> FetchResult:
        t0 = time.monotonic()
        fetched_at = _utc_now()
        notes: list[FetchNote] = []
        errors: list[str] = []
        frames: list[pd.DataFrame] = []
        fetched_any = False

        current_year = datetime.now(timezone.utc).year
        for spec in specs:
            if spec.get("kind") != "curve":
                notes.append(FetchNote("unsupported_spec", "warning",
                                       f"treasury_us ignores kind={spec.get('kind')}", spec.get("id", "")))
                continue
            tenors = list(spec.get("tenors") or [])
            if not tenors:
                tenors = list(COLUMN_TO_TENOR.values())
            start_year = int(str(start)[:4]) if start else int(spec.get("start_year", 2014))
            start_year = max(1990, start_year)
            found_tenors: set[str] = set()

            for year in range(start_year, current_year + 1):
                try:
                    text = self._year_text(year, current_year)
                except Exception as exc:  # noqa: BLE001 - provider boundary
                    errors.append(f"UST {year}: {type(exc).__name__}: {exc}")
                    notes.append(FetchNote("year_failed", "error", f"UST {year} download failed: {exc}", str(year)))
                    continue
                try:
                    parsed = parse_treasury_csv(text)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"UST {year} parse: {type(exc).__name__}: {exc}")
                    notes.append(FetchNote("parse_failed", "error", f"UST {year} parse failed: {exc}", str(year)))
                    continue
                if parsed.empty:
                    notes.append(FetchNote("year_empty", "warning", f"UST {year} file had no usable rows", str(year)))
                    continue
                parsed = parsed[parsed["tenor"].isin(tenors)]
                found_tenors.update(parsed["tenor"].unique())
                parsed["series_id"] = spec["id"] + ":" + parsed["tenor"]
                parsed["unit"] = "percent"
                frames.append(parsed[["series_id", "date", "value", "unit"]])

            missing = [t for t in tenors if t not in found_tenors]
            if missing:
                notes.append(
                    FetchNote(
                        "tenor_not_published",
                        "info",
                        f"{spec['id']}: tenors not published in {start_year}-{current_year}: {missing}",
                        spec["id"],
                    )
                )

        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
            columns=["series_id", "date", "value", "unit"]
        )
        if not frame.empty:
            fetched_any = True
            bad = ~frame["value"].between(YIELD_MIN, YIELD_MAX, inclusive="left") | ~frame["value"].notna()
            n_bad = int(bad.sum())
            if n_bad:
                notes.append(FetchNote("validation_dropped", "warning",
                                       f"treasury_us dropped {n_bad} rows outside ({YIELD_MIN}, {YIELD_MAX})",
                                       "treasury_us"))
                frame = frame[~bad]
            if start:
                frame = frame[frame["date"] >= pd.Timestamp(start)]
        if frame.empty:
            if fetched_any:
                notes.append(FetchNote("no_new_observations", "info",
                                       f"treasury_us: source data ends before requested start {start}",
                                       "treasury_us"))
                return FetchResult(frame=normalize_indicators(pd.DataFrame(), self.provider_id, fetched_at),
                                   source_id=self.provider_id, fetched_at=fetched_at,
                                   notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)
            raise ProviderError(f"{self.provider_id}: no UST rows fetched ({'; '.join(errors[:3])})")
        frame = normalize_indicators(frame, self.provider_id, fetched_at)
        return FetchResult(frame=frame, source_id=self.provider_id, fetched_at=fetched_at,
                           notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)

    # ------------------------------------------------------------------ cache
    def _year_text(self, year: int, current_year: int) -> str:
        """Return the CSV text for ``year``.

        Past years are immutable enough to cache indefinitely. The current year
        is always re-downloaded so a run never silently serves stale data; the
        cache copy is still refreshed for later offline inspection.
        """
        path = _cache_path(f"ust_{year}.csv")
        if year < current_year and path.exists() and path.stat().st_size > 0:
            return path.read_text(encoding="utf-8-sig")
        resp = self.client.get(BASE_URL.format(year=year))
        text = resp.content.decode("utf-8-sig", errors="replace")
        path.write_text(text, encoding="utf-8")
        return text
