"""Yale / Robert Shiller monthly valuation data (academic, monthly).

Endpoint (verified 2026-11-13)::

    http://www.econ.yale.edu/~shiller/data/ie_data.xls

Layout quirks
-------------
* Legacy BIFF ``.xls``: ``xlrd`` is required (installed in the project venv).
* The ``Data`` sheet has a multi-row title block; the real header is row 8 of
  the sheet (0-indexed 7): ``Date, P, D, E, CPI, Date Fraction, Long Interest
  Rate GS10, Real Price, ...`` and ``CAPE`` is column 12 at that header row.
  The parser searches for the ``Date`` header and the ``CAPE`` label instead of
  hard-coding them, with the historical positions as fallback.
* ``Date`` is a decimal year where the fractional part encodes the month:
  ``2026.10`` -> October, and **``2022.1`` is October too** (float formatting
  dropped the trailing zero). The parser multiplies the fractional part by 100
  rather than reading the digit count. The final row of the sheet is often a
  text note and is skipped.
* The file is updated monthly and the most recent months' CAPE can be blank;
  blanks are dropped, never filled.

Observed at verification: 1,713 CAPE observations, 1881-01 through 2023-09
(the public file itself lags; the provider emits a ``series_stale`` warning
when the latest observation is more than 100 days old).
"""

from __future__ import annotations

import io
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from .. import project_root
from .base import FetchNote, FetchResult, IndicatorProvider, ProviderError, normalize_indicators
from .http import shared_client

CACHE_DIR = "shiller"
CACHE_NAME = "ie_data.xls"
CACHE_TTL_HOURS = 24
URL = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
CAPE_MIN, CAPE_MAX = 0.0, 200.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cache_path() -> Path:
    path = project_root() / "data" / "cache" / CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path / CACHE_NAME


def decimal_year_to_month(value: Any) -> pd.Timestamp | None:
    """``2022.1`` / ``2022.01`` -> 2022-10-01; ``2023.09`` -> 2023-09-01."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not 1800.0 < number < 2200.0:
        return None
    year = int(math.floor(number + 1e-9))
    fraction = int(round((number - year) * 100.0))
    if fraction == 0:
        month = 1
    elif 1 <= fraction <= 12:
        month = fraction
    else:
        return None
    try:
        return pd.Timestamp(year=year, month=month, day=1)
    except ValueError:
        return None


def _excel_engine(data: bytes) -> str:
    """Pick the reader from the file signature (Yale ships BIFF .xls today)."""
    if data[:2] == b"PK":  # xlsx/zip container
        return "openpyxl"
    import xlrd  # noqa: F401 - lazy import; xlrd is required for legacy .xls
    return "xlrd"


def parse_shiller_xls(data: bytes) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Parse the Shiller workbook into ``date, value`` CAPE rows."""
    engine = _excel_engine(data)
    workbook = pd.ExcelFile(io.BytesIO(data), engine=engine)
    sheet = "Data" if "Data" in workbook.sheet_names else workbook.sheet_names[0]
    frame = pd.read_excel(io.BytesIO(data), sheet_name=sheet, header=None, engine=engine)
    if frame.empty:
        raise ValueError("Shiller workbook is empty")

    header_row = None
    for i in range(min(30, len(frame))):
        cells = [str(x).strip().lower() for x in frame.iloc[i].tolist()]
        if cells and cells[0] == "date":
            header_row = i
            break
    used_fallback_header = header_row is None
    if header_row is None:
        header_row = 7 if len(frame) > 7 else 0

    date_col = 0
    for c in range(frame.shape[1]):
        cell = frame.iat[header_row, c]
        if isinstance(cell, str) and cell.strip().lower() == "date":
            date_col = c
            break

    # Prefer an exact "CAPE" label on the same row as "Date": nearby header
    # stacks also contain "CAPE" as part of "Excess CAPE Yield" / "TR CAPE".
    cape_col = None
    for c in range(frame.shape[1]):
        cell = frame.iat[header_row, c]
        if isinstance(cell, str) and cell.strip().upper() == "CAPE":
            cape_col = c
            break
    if cape_col is None:
        for offset in (-1, -2, 1, 2, -3, 3):
            r = header_row + offset
            if not 0 <= r < len(frame):
                continue
            for c in range(frame.shape[1]):
                cell = frame.iat[r, c]
                if isinstance(cell, str) and cell.strip().upper() == "CAPE":
                    cape_col = c
                    break
            if cape_col is not None:
                break
    if cape_col is None:
        cape_col = 12 if frame.shape[1] > 12 else None
    if cape_col is None:
        raise ValueError("Shiller workbook: CAPE column not found")

    rows: list[tuple[pd.Timestamp, float]] = []
    dropped_dates = 0
    dropped_values = 0
    for i in range(header_row + 1, len(frame)):
        raw_date = frame.iat[i, date_col]
        if pd.isna(raw_date):
            continue
        date = decimal_year_to_month(raw_date)
        if date is None:
            dropped_dates += 1
            continue
        raw_value = frame.iat[i, cape_col]
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            dropped_values += 1
            continue
        if not math.isfinite(value):
            dropped_values += 1
            continue
        rows.append((date, value))
    out = pd.DataFrame(rows, columns=["date", "value"]).drop_duplicates(subset=["date"], keep="last")
    meta = {
        "sheet": sheet,
        "header_row": header_row,
        "cape_column": cape_col,
        "used_fallback_header": used_fallback_header,
        "dropped_dates": dropped_dates,
        "dropped_values": dropped_values,
    }
    return out.sort_values("date").reset_index(drop=True), meta


class ShillerProvider(IndicatorProvider):
    provider_id = "shiller"

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

        data = self._load_bytes(notes, errors)
        if data is None:
            raise ProviderError(f"{self.provider_id}: Shiller workbook unavailable ({'; '.join(errors[:3])})")
        try:
            parsed, meta = parse_shiller_xls(data)
        except Exception as exc:  # noqa: BLE001 - provider boundary
            errors.append(f"Shiller parse: {type(exc).__name__}: {exc}")
            raise ProviderError(f"{self.provider_id}: Shiller parse failed: {exc}") from exc

        if meta.get("used_fallback_header"):
            notes.append(FetchNote("header_fallback", "warning",
                                   "Shiller header located by fallback position, not by label", "US_CAPE"))
        if meta.get("dropped_dates") or meta.get("dropped_values"):
            notes.append(FetchNote("rows_dropped", "info",
                                   f"Shiller skipped {meta.get('dropped_dates')} non-date and "
                                   f"{meta.get('dropped_values')} non-CAPE rows", "US_CAPE"))
        if parsed.empty:
            raise ProviderError(f"{self.provider_id}: Shiller workbook parsed to zero CAPE rows")

        frame = parsed.copy()
        fetched_any = not frame.empty
        if start:
            frame = frame[frame["date"] >= pd.Timestamp(start)]
        keep = frame["value"].between(CAPE_MIN, CAPE_MAX, inclusive="neither")
        n_bad = int((~keep).sum())
        if n_bad:
            notes.append(FetchNote("validation_dropped", "warning",
                                   f"US_CAPE dropped {n_bad} rows outside ({CAPE_MIN}, {CAPE_MAX})",
                                   "US_CAPE"))
            frame = frame[keep]
        if frame.empty:
            if fetched_any:
                notes.append(FetchNote("no_new_observations", "info",
                                       f"shiller: source data ends before requested start {start}", "US_CAPE"))
                return FetchResult(frame=normalize_indicators(pd.DataFrame(), self.provider_id, fetched_at),
                                   source_id=self.provider_id, fetched_at=fetched_at,
                                   notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)
            raise ProviderError(f"{self.provider_id}: no US_CAPE rows fetched")

        last = frame["date"].max()
        age_days = (pd.Timestamp.now().normalize() - last.normalize()).days
        if age_days > 100:
            notes.append(FetchNote("series_stale", "warning",
                                   f"latest Shiller CAPE observation is {last.date()} ({age_days}d old); "
                                   f"the public workbook itself lags", "US_CAPE"))
        notes.append(FetchNote("coverage", "info",
                               f"Shiller CAPE {frame['date'].min().date()}..{last.date()} "
                               f"({len(frame)} observations)", "US_CAPE"))

        for spec in specs:
            if spec.get("kind") != "macro":
                notes.append(FetchNote("unsupported_spec", "warning",
                                       f"shiller ignores kind={spec.get('kind')}", spec.get("id", "")))
            elif str(spec.get("series", "")).upper() not in {"CAPE", "PE10", ""}:
                notes.append(FetchNote("unsupported_series", "warning",
                                       f"shiller only serves CAPE/PE10, got {spec.get('series')!r}",
                                       spec.get("id", "")))

        out = frame.copy()
        # One configured source series (US_CAPE); keep the spec id for provenance.
        spec_id = next((str(s["id"]) for s in specs if s.get("kind") == "macro"), "US_CAPE")
        out["series_id"] = spec_id
        out["unit"] = "ratio"
        out = out[["series_id", "date", "value", "unit"]]
        out = normalize_indicators(out, self.provider_id, fetched_at)
        return FetchResult(frame=out, source_id=self.provider_id, fetched_at=fetched_at,
                           notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)

    # ------------------------------------------------------------------ cache
    def _load_bytes(self, notes: list[FetchNote], errors: list[str]) -> bytes | None:
        path = _cache_path()
        if path.exists() and (time.time() - path.stat().st_mtime) < CACHE_TTL_HOURS * 3600:
            return path.read_bytes()
        try:
            body = self.client.get(URL).content
            path.write_bytes(body)
            return body
        except Exception as exc:  # noqa: BLE001 - provider boundary
            if path.exists():
                notes.append(FetchNote("cache_fallback", "warning",
                                       f"Shiller download failed ({exc}); using cached workbook",
                                       "shiller"))
                return path.read_bytes()
            errors.append(f"Shiller download: {type(exc).__name__}: {exc}")
            notes.append(FetchNote("download_failed", "error",
                                   f"Shiller workbook download failed: {exc}", "shiller"))
            return None
