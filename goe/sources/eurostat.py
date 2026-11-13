"""Eurostat dissemination API adapter (official; JSON-stat 2.0).

Endpoint::

    https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/
        prc_hicp_manr?geo=EA&coicop=CP00&unit=RCH_A&format=JSON&lang=EN

``spec["series"]`` is ``"<dataset>?<query>"``. The JSON-stat response carries a
``value`` object keyed by a *linear* cell index plus, for every dimension, an
``id``/``size`` list and a ``category.index`` label->position map. The parser
implements the general JSON-stat linear-index decode (dimension order + sizes +
category maps), not just the one-dimension shortcut.

For the configured HICP query only ``time`` varies; every other dimension has a
single category, and a response where more than one non-time dimension varies
is rejected as ambiguous rather than silently collapsed.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any, Sequence

import pandas as pd

from .base import FetchNote, FetchResult, IndicatorProvider, ProviderError, normalize_indicators
from .http import shared_client

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{path}"
_QUARTER_RE = re.compile(r"^(\d{4})-Q([1-4])$")
_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR_RE = re.compile(r"^(\d{4})$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _period_to_date(period: str) -> pd.Timestamp | None:
    text = str(period).strip()
    match = _QUARTER_RE.match(text)
    if match:
        return pd.Timestamp(year=int(match.group(1)), month=int(match.group(2)) * 3, day=1)
    match = _MONTH_RE.match(text)
    if match:
        return pd.Timestamp(year=int(match.group(1)), month=int(match.group(2)), day=1)
    match = _YEAR_RE.match(text)
    if match:
        return pd.Timestamp(year=int(match.group(1)), month=12, day=1)
    try:
        return pd.Timestamp(text)
    except (ValueError, TypeError):
        return None


def parse_eurostat_json(payload: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Decode a JSON-stat 2.0 dataset into ``date, value`` rows."""
    if not isinstance(payload, dict):
        raise ValueError("Eurostat payload is not a JSON object")
    if payload.get("error"):
        raise ValueError(f"Eurostat error payload: {payload.get('error')}")
    dims = list(payload.get("id") or [])
    sizes = [int(s) for s in (payload.get("size") or [])]
    if not dims or len(dims) != len(sizes):
        raise ValueError("Eurostat payload lacks a consistent id/size dimension list")

    categories: dict[str, dict[int, str]] = {}
    for dim in dims:
        entry = (payload.get("dimension") or {}).get(dim) or {}
        cat = entry.get("category") or {}
        index = cat.get("index")
        if isinstance(index, dict):
            categories[dim] = {int(pos): str(code) for code, pos in index.items()}
        elif isinstance(index, list):
            categories[dim] = {i: str(code) for i, code in enumerate(index)}
        else:
            categories[dim] = {}

    values = payload.get("value") or {}
    if isinstance(values, list):
        cells = [(i, v) for i, v in enumerate(values) if v is not None]
    elif isinstance(values, dict):
        cells = [(int(k), v) for k, v in values.items() if v is not None]
    else:
        raise ValueError("Eurostat payload has an unsupported value container")

    time_pos = dims.index("time") if "time" in dims else len(dims) - 1
    varying_non_time = [d for i, d in enumerate(dims) if i != time_pos and sizes[i] > 1]
    if varying_non_time:
        raise ValueError(
            "Eurostat response varies over non-time dimensions "
            f"{varying_non_time}; the query must filter them to one category"
        )

    rows: list[tuple[pd.Timestamp, float]] = []
    for linear, raw in cells:
        remainder = int(linear)
        coords = [0] * len(dims)
        for i in range(len(dims) - 1, -1, -1):
            size = sizes[i] or 1
            coords[i] = remainder % size
            remainder //= size
        period = categories.get(dims[time_pos], {}).get(coords[time_pos])
        if period is None:
            continue
        date = _period_to_date(period)
        if date is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        rows.append((date, value))
    frame = pd.DataFrame(rows, columns=["date", "value"])
    if not frame.empty:
        frame = frame.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    meta = {
        "dims": dims,
        "sizes": sizes,
        "updated": payload.get("updated"),
        "label": payload.get("label"),
    }
    return frame, meta


class EurostatProvider(IndicatorProvider):
    provider_id = "eurostat"

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
            if spec.get("kind") != "macro" or not spec.get("series"):
                notes.append(FetchNote("unsupported_spec", "warning",
                                       f"eurostat ignores spec {spec.get('id')}", spec.get("id", "")))
                continue
            dataset, _, query = str(spec["series"]).partition("?")
            path = dataset + (("?" + query) if query else "")
            separator = "&" if query else "?"
            url = BASE_URL.format(path=path)
            if "format=" not in query:
                url += f"{separator}format=JSON"
                separator = "&"
            if "lang=" not in query:
                url += f"{separator}lang=EN"
            try:
                payload = self.client.get(url).json()
                parsed, meta = parse_eurostat_json(payload)
            except Exception as exc:  # noqa: BLE001 - provider boundary
                errors.append(f"Eurostat {spec.get('series')}: {type(exc).__name__}: {exc}")
                notes.append(FetchNote("series_failed", "error",
                                       f"Eurostat {spec['id']} request/parse failed: {exc}", spec["id"]))
                continue
            if parsed.empty:
                notes.append(FetchNote("series_empty", "warning",
                                       f"Eurostat {spec['id']}: no usable observations", spec["id"]))
                continue
            fetched_any = True
            if start:
                parsed = parsed[parsed["date"] >= pd.Timestamp(start)]
            if parsed.empty:
                continue
            if meta.get("updated"):
                notes.append(FetchNote(
                    "dataset_updated", "info",
                    f"Eurostat dataset last updated {meta['updated']} ({meta.get('label') or dataset})",
                    spec["id"],
                ))
            parsed = parsed.copy()
            parsed["series_id"] = spec["id"]
            parsed["unit"] = "percent"
            frames.append(parsed[["series_id", "date", "value", "unit"]])

        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
            columns=["series_id", "date", "value", "unit"]
        )
        if not frame.empty:
            keep = frame["value"].notna() & frame["value"].between(-50, 100)
            n_bad = int((~keep).sum())
            if n_bad:
                notes.append(FetchNote("validation_dropped", "warning",
                                       f"eurostat dropped {n_bad} rows outside (-50, 100) percent",
                                       "eurostat"))
                frame = frame[keep]
        if frame.empty:
            if fetched_any:
                notes.append(FetchNote("no_new_observations", "info",
                                       f"eurostat: source data ends before requested start {start}", "eurostat"))
                return FetchResult(frame=normalize_indicators(pd.DataFrame(), self.provider_id, fetched_at),
                                   source_id=self.provider_id, fetched_at=fetched_at,
                                   notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)
            raise ProviderError(f"{self.provider_id}: no Eurostat rows fetched ({'; '.join(errors[:3])})")
        frame = normalize_indicators(frame, self.provider_id, fetched_at)
        return FetchResult(frame=frame, source_id=self.provider_id, fetched_at=fetched_at,
                           notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)
