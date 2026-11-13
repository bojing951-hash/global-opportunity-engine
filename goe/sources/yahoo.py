"""Yahoo Finance price adapter.

Used for liquid market prices across equities, government/credit ETF proxies,
FX, futures and crypto. Treat as an *aggregator* (see config/sources.yaml):
convenient, rate-limited, and not a primary source of record for official
statistics.

Implementation notes
--------------------
* Batch download is used (8 symbols per call) because per-symbol calls hit the
  provider's rate limiter quickly; failures are retried individually so one bad
  ticker does not lose a whole batch.
* ``auto_adjust=False`` keeps raw OHLC and the provider's own adjusted close.
  Analytics use adjusted close for total-return series and raw close for
  instrument levels; both are stored.
* A short random delay between batches plus exponential backoff on HTTP 429.
"""

from __future__ import annotations

import random
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence

import pandas as pd

from .base import FetchNote, FetchResult, PriceProvider, normalize_prices

DEFAULT_START = "2015-01-01"
BATCH_SIZE = 8
MIN_VALID_ROWS = 20   # fewer valid rows than this means the symbol is unusable


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _flatten(df: pd.DataFrame, symbols: Sequence[str]) -> dict[str, pd.DataFrame]:
    """Normalise yfinance's column layout into {symbol: OHLCV frame}."""
    out: dict[str, pd.DataFrame] = {}
    if df is None or df.empty:
        return out
    if isinstance(df.columns, pd.MultiIndex):
        lvl0 = set(df.columns.get_level_values(0))
        # Layout A: (field, ticker); Layout B: (ticker, field)
        if "Close" in lvl0:
            for sym in symbols:
                if sym not in set(df.columns.get_level_values(1)):
                    continue
                sub = df.xs(sym, axis=1, level=1, drop_level=True)
                out[sym] = _canonical(sub)
        else:
            for sym in symbols:
                if sym not in set(df.columns.get_level_values(0)):
                    continue
                sub = df.xs(sym, axis=1, level=0, drop_level=True)
                out[sym] = _canonical(sub)
    else:
        sym = symbols[0]
        out[sym] = _canonical(df)
    return out


def _canonical(sub: pd.DataFrame) -> pd.DataFrame:
    rename = {"Open": "open", "High": "high", "Low": "low", "Close": "close",
              "Adj Close": "adj_close", "Volume": "volume"}
    sub = sub.rename(columns={k: v for k, v in rename.items() if k in sub.columns})
    sub = sub[[c for c in ("open", "high", "low", "close", "adj_close", "volume") if c in sub.columns]].copy()
    sub.index = pd.to_datetime(sub.index)
    # Yahoo timestamps are exchange-local; keep calendar date only.
    sub.index = sub.index.tz_localize(None) if sub.index.tz is not None else sub.index
    sub.index = sub.index.normalize()
    sub = sub[~sub.index.duplicated(keep="last")]
    for col in ("open", "high", "low", "close", "adj_close", "volume"):
        if col not in sub.columns:
            sub[col] = pd.NA
    return sub


class YahooPriceProvider(PriceProvider):
    provider_id = "yahoo"

    def __init__(self, polite_delay: float = 1.2, max_batches: int | None = None):
        self.polite_delay = polite_delay
        self.max_batches = max_batches

    def fetch_prices(
        self,
        instruments: Sequence[dict[str, Any]],
        start: str | None = None,
        end: str | None = None,
    ) -> FetchResult:
        import yfinance as yf

        t0 = time.monotonic()
        fetched_at = _utc_now()
        start = start or DEFAULT_START
        specs = [dict(s) for s in instruments if s.get("symbol")]
        notes: list[FetchNote] = []
        errors: list[str] = []
        frames: list[pd.DataFrame] = []

        for i in range(0, len(specs), BATCH_SIZE):
            if self.max_batches is not None and i // BATCH_SIZE >= self.max_batches:
                break
            batch = specs[i : i + BATCH_SIZE]
            symbols = [s["symbol"] for s in batch]
            id_by_symbol = {s["symbol"]: s["id"] for s in batch}
            try:
                raw = self._download(yf, symbols, start, end)
            except Exception as exc:  # noqa: BLE001 - provider boundary
                errors.append(f"batch {symbols}: {type(exc).__name__}: {exc}")
                raw = pd.DataFrame()
            per_symbol = _flatten(raw, symbols)
            for sym in symbols:
                sub = per_symbol.get(sym)
                if sub is None or sub.empty:
                    # single-symbol retry, then give up on this ticker
                    sub = self._retry_single(yf, sym, start, end, errors)
                if sub is None or sub.empty:
                    notes.append(FetchNote("empty_series", "warning", f"{sym} returned no rows", id_by_symbol[sym]))
                    continue
                sub = sub.copy()
                sub = sub[sub["close"].notna() | sub["adj_close"].notna()]
                if sub.empty or len(sub) < MIN_VALID_ROWS:
                    notes.append(FetchNote("insufficient_history", "warning",
                                           f"{sym} returned only {len(sub)} valid rows", id_by_symbol[sym]))
                    continue
                sub["instrument_id"] = id_by_symbol[sym]
                sub["date"] = sub.index.strftime("%Y-%m-%d")
                frames.append(sub.reset_index(drop=True))
            if i + BATCH_SIZE < len(specs):
                time.sleep(self.polite_delay * (0.7 + random.random() * 0.6))

        if frames:
            frame = normalize_prices(pd.concat(frames, ignore_index=True), self.provider_id, fetched_at)
        else:
            frame = normalize_prices(pd.DataFrame(), self.provider_id, fetched_at)
        return FetchResult(
            frame=frame, source_id=self.provider_id, fetched_at=fetched_at,
            notes=notes, errors=errors, elapsed_s=time.monotonic() - t0,
        )

    def _download(self, yf: Any, symbols: Sequence[str], start: str, end: str | None) -> pd.DataFrame:
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                df = yf.download(
                    list(symbols), start=start, end=end, auto_adjust=False, actions=False,
                    group_by="column", threads=False, progress=False,
                )
                if df is not None and not df.empty:
                    return df
            except Exception as exc:  # noqa: BLE001
                if attempt == attempts:
                    raise
                # rate limited / transient: back off
                time.sleep(3.0 * attempt + random.random())
                del exc
            time.sleep(1.5 * attempt)
        return pd.DataFrame()

    def _retry_single(self, yf: Any, symbol: str, start: str, end: str | None,
                      errors: list[str]) -> pd.DataFrame | None:
        for attempt in range(1, 3):
            try:
                hist = yf.Ticker(symbol).history(
                    start=start, end=end or (date.today() + timedelta(days=1)).isoformat(),
                    auto_adjust=False, actions=False,
                )
                if hist is not None and not hist.empty:
                    return _canonical(hist)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{symbol} retry {attempt}: {type(exc).__name__}: {exc}")
                time.sleep(2.0 * attempt)
        return None
