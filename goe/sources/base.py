"""Provider protocols and canonical frames.

Two provider families exist:

``PriceProvider``
    Given instrument definitions (``id``, ``symbol``, ``currency`` ...), return
    a long frame with columns
    ``instrument_id, date, open, high, low, close, adj_close, volume``.
    ``date`` is a ``datetime.date``/ISO string in the exchange calendar.

``IndicatorProvider``
    Given series definitions (curve tenor / macro series / positioning market),
    return a long frame with columns ``series_id, date, value, unit``.

Providers must:
  * never invent, interpolate or forward-fill observations;
  * attach the observation date reported by the source ("as of"), not the
    download date;
  * return ``FetchResult.errors`` instead of raising for per-symbol failures, so
    one dead ticker cannot abort a full scan (but must raise if nothing at all
    could be fetched);
  * be idempotent: fetching the same window twice returns the same values.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Sequence

import pandas as pd

PRICE_COLUMNS = ["instrument_id", "date", "open", "high", "low", "close", "adj_close", "volume"]
INDICATOR_COLUMNS = ["series_id", "date", "value", "unit"]


class ProviderError(RuntimeError):
    pass


@dataclass
class FetchNote:
    code: str
    severity: str          # info | warning | error
    detail: str
    target: str = ""


@dataclass
class FetchResult:
    frame: pd.DataFrame
    source_id: str
    fetched_at: str
    notes: list[FetchNote] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    rows: int = 0
    elapsed_s: float = 0.0

    def __post_init__(self) -> None:
        self.rows = 0 if self.frame is None else len(self.frame)

    def require_nonempty(self) -> "FetchResult":
        if self.frame is None or self.frame.empty:
            raise ProviderError(
                f"{self.source_id}: no rows fetched" + (f" ({'; '.join(self.errors[:3])})" if self.errors else "")
            )
        return self


class Provider(abc.ABC):
    provider_id: str = ""
    kind: str = ""

    @property
    def source_id(self) -> str:
        return self.provider_id


class PriceProvider(Provider):
    kind = "price"

    @abc.abstractmethod
    def fetch_prices(
        self,
        instruments: Sequence[dict[str, Any]],
        start: str | None = None,
        end: str | None = None,
    ) -> FetchResult:
        ...


class IndicatorProvider(Provider):
    kind = "indicator"

    @abc.abstractmethod
    def fetch_indicators(
        self,
        specs: Sequence[dict[str, Any]],
        start: str | None = None,
    ) -> FetchResult:
        ...


class Timer:
    def __enter__(self) -> "Timer":
        self.t0 = time.monotonic()
        return self

    def __exit__(self, *exc: object) -> None:
        self.elapsed = time.monotonic() - self.t0


def normalize_prices(df: pd.DataFrame, source_id: str, fetched_at: str) -> pd.DataFrame:
    """Enforce canonical dtypes/labels on a provider price frame."""
    if df is None or df.empty:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    out = df.copy()
    for col in PRICE_COLUMNS:
        if col not in out.columns:
            out[col] = None
    out = out[PRICE_COLUMNS]
    out["date"] = pd.to_datetime(out["date"]).dt.date.astype(str)
    for col in ("open", "high", "low", "close", "adj_close", "volume"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["instrument_id", "date"])
    # A row with no close at all is not an observation; Yahoo returns such rows
    # for unavailable symbols and they must never be stored as data.
    out = out[out["close"].notna() | out["adj_close"].notna()]
    out = out.drop_duplicates(subset=["instrument_id", "date"], keep="last")
    out["source_id"] = source_id
    out["fetched_at"] = fetched_at
    return out.reset_index(drop=True)


def normalize_indicators(df: pd.DataFrame, source_id: str, fetched_at: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=INDICATOR_COLUMNS)
    out = df.copy()
    for col in INDICATOR_COLUMNS:
        if col not in out.columns:
            out[col] = None
    out = out[INDICATOR_COLUMNS]
    out["date"] = pd.to_datetime(out["date"]).dt.date.astype(str)
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["series_id", "date", "value"])
    out = out.drop_duplicates(subset=["series_id", "date"], keep="last")
    out["source_id"] = source_id
    out["fetched_at"] = fetched_at
    return out.reset_index(drop=True)


def parse_date(x: Any) -> date:
    if isinstance(x, date):
        return x
    return pd.Timestamp(x).date()
