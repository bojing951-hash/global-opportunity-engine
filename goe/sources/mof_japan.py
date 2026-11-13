"""Japan MOF JGB interest-rate adapter (official, end-of-day).

Two public files are combined (both verified 2026-11-13):

* ``https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv``
  Current-month table. Small (~1 KB), **cp932** encoded, two title rows then
  ``Date,1Y,...,40Y`` and one row per business day. It carries the freshest
  observations (2026-11-12 at verification time).
* ``.../historical/jgbcme_all.csv``
  Full history in **one UTF-8 file** (1974-09-24 onward, ~13k rows). Tenors not
  yet listed are published as ``-`` and are skipped rather than filled.

Layout quirk: unlike the Euro area / US curves, the JGB file is a wide
date x tenor table, and the number of tenor columns has changed over time. The
parser keys off the ``Date`` header row and ``<n>Y`` column labels, so extra
title/footer/note rows are ignored.

Negative yields are real and published (1Y hit -0.371% in 2019), so the sanity
window is (-5, 30) percent rather than the 0..30 hint used for US par yields.
"""

from __future__ import annotations

import csv
import io
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from .. import project_root
from .base import FetchNote, FetchResult, IndicatorProvider, ProviderError, normalize_indicators
from .http import shared_client

CACHE_DIR = "mof_japan"
CURRENT_URL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"
HISTORY_URL = (
    "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv"
)

HISTORY_TTL_HOURS = 24
YIELD_MIN, YIELD_MAX = -5.0, 30.0
_TENOR_RE = re.compile(r"^\d{1,2}Y$")
_DATE_RE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")
_MISSING = {"", "-", "--", "－", "—", "n/a", "na"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cache_path(name: str) -> Path:
    path = project_root() / "data" / "cache" / CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path / name


def decode_mof_bytes(body: bytes) -> str:
    """MOF mixes encodings across files; decode without guessing silently."""
    for encoding in ("utf-8-sig", "utf-8", "cp932", "shift_jis", "latin-1"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("latin-1", errors="replace")


def parse_mof_csv(text: str) -> pd.DataFrame:
    """Parse a MOF wide CSV into a long ``date, tenor, value`` frame."""
    if not text or not text.strip():
        return pd.DataFrame(columns=["date", "tenor", "value"])
    rows = list(csv.reader(io.StringIO(text)))
    header_idx = None
    for i, row in enumerate(rows[:10]):
        cells = [c.strip() for c in row]
        if cells and cells[0].lower() == "date" and any(_TENOR_RE.match(c) for c in cells[1:]):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("MOF CSV: could not locate the 'Date,<n>Y...' header row")
    header = [c.strip() for c in rows[header_idx]]
    tenor_columns = [(j, h) for j, h in enumerate(header) if _TENOR_RE.match(h)]
    if not tenor_columns:
        raise ValueError("MOF CSV: no tenor columns found")

    out: list[tuple[pd.Timestamp, str, float]] = []
    for row in rows[header_idx + 1:]:
        if not row:
            continue
        match = _DATE_RE.match(row[0].strip())
        if not match:
            continue
        try:
            day = pd.Timestamp(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            continue
        for j, tenor in tenor_columns:
            if j >= len(row):
                continue
            raw = row[j].strip()
            if raw.lower() in _MISSING:
                continue
            try:
                value = float(raw)
            except ValueError:
                continue
            out.append((day, tenor, value))
    frame = pd.DataFrame(out, columns=["date", "tenor", "value"])
    if not frame.empty:
        frame = frame.drop_duplicates(subset=["date", "tenor"], keep="last")
    return frame


class MofJapanProvider(IndicatorProvider):
    provider_id = "mof_japan"

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

        history = self._load_history(notes, errors)
        current = self._load_current(notes, errors)
        combined = pd.concat([f for f in (history, current) if f is not None], ignore_index=True) \
            if (history is not None or current is not None) else pd.DataFrame(columns=["date", "tenor", "value"])
        if not combined.empty:
            combined = combined.drop_duplicates(subset=["date", "tenor"], keep="last")
        fetched_any = not combined.empty

        for spec in specs:
            if spec.get("kind") != "curve":
                notes.append(FetchNote("unsupported_spec", "warning",
                                       f"mof_japan ignores kind={spec.get('kind')}", spec.get("id", "")))
                continue
            tenors = list(spec.get("tenors") or [])
            if combined.empty:
                continue
            part = combined[combined["tenor"].isin(tenors)].copy()
            missing = [t for t in tenors if t not in set(part["tenor"])]
            if missing:
                notes.append(FetchNote("tenor_missing", "warning",
                                       f"{spec['id']}: no observations for tenors {missing}", spec["id"]))
            if part.empty:
                continue
            part["series_id"] = spec["id"] + ":" + part["tenor"]
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
                                       f"mof_japan dropped {n_bad} rows outside ({YIELD_MIN}, {YIELD_MAX})",
                                       "mof_japan"))
                frame = frame[~bad]
            if start:
                frame = frame[frame["date"] >= pd.Timestamp(start)]
            if not frame.empty:
                last = frame["date"].max()
                age_days = (pd.Timestamp.now().normalize() - last.normalize()).days
                if age_days > 10:
                    notes.append(FetchNote("series_stale", "warning",
                                           f"latest JGB observation is {last.date()} ({age_days}d old)",
                                           "mof_japan"))
        if frame.empty:
            if fetched_any:
                notes.append(FetchNote("no_new_observations", "info",
                                       f"mof_japan: source data ends before requested start {start}",
                                       "mof_japan"))
                return FetchResult(frame=normalize_indicators(pd.DataFrame(), self.provider_id, fetched_at),
                                   source_id=self.provider_id, fetched_at=fetched_at,
                                   notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)
            raise ProviderError(f"{self.provider_id}: no JGB rows fetched ({'; '.join(errors[:3])})")
        frame = normalize_indicators(frame, self.provider_id, fetched_at)
        return FetchResult(frame=frame, source_id=self.provider_id, fetched_at=fetched_at,
                           notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)

    # ------------------------------------------------------------------ cache
    def _load_history(self, notes: list[FetchNote], errors: list[str]) -> pd.DataFrame | None:
        path = _cache_path("jgbcme_all.csv")
        fresh = path.exists() and (time.time() - path.stat().st_mtime) < HISTORY_TTL_HOURS * 3600
        if fresh:
            try:
                return parse_mof_csv(decode_mof_bytes(path.read_bytes()))
            except Exception as exc:  # noqa: BLE001 - corrupt cache: refetch below
                notes.append(FetchNote("cache_unreadable", "warning",
                                       f"MOF history cache unreadable ({exc}); refetching", "mof_japan"))
        try:
            body = self.client.get(HISTORY_URL).content
            path.write_bytes(body)
            return parse_mof_csv(decode_mof_bytes(body))
        except Exception as exc:  # noqa: BLE001 - provider boundary
            if path.exists():
                notes.append(FetchNote("cache_fallback", "warning",
                                       f"MOF history download failed ({exc}); using cached copy", "mof_japan"))
                try:
                    return parse_mof_csv(decode_mof_bytes(path.read_bytes()))
                except Exception:  # noqa: BLE001
                    pass
            errors.append(f"MOF history: {type(exc).__name__}: {exc}")
            notes.append(FetchNote("history_failed", "error",
                                   f"MOF full-history download failed: {exc}", "mof_japan"))
            return None

    def _load_current(self, notes: list[FetchNote], errors: list[str]) -> pd.DataFrame | None:
        path = _cache_path("jgbcme_current.csv")
        try:
            body = self.client.get(CURRENT_URL).content
            path.write_bytes(body)
            return parse_mof_csv(decode_mof_bytes(body))
        except Exception as exc:  # noqa: BLE001
            if path.exists():
                notes.append(FetchNote("cache_fallback", "warning",
                                       f"MOF current-month download failed ({exc}); using cached copy",
                                       "mof_japan"))
                try:
                    return parse_mof_csv(decode_mof_bytes(path.read_bytes()))
                except Exception:  # noqa: BLE001
                    pass
            errors.append(f"MOF current month: {type(exc).__name__}: {exc}")
            notes.append(FetchNote("current_failed", "error",
                                   f"MOF current-month download failed: {exc}", "mof_japan"))
            return None
