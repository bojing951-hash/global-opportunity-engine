"""China A-share index adapter via akshare (Sina endpoint).

Yahoo's coverage of mainland indices has been unreliable (rate-limited history,
all-NaN columns). akshare's Sina-backed index endpoint provides long daily
history for the Shanghai/Shenzhen indices, so it is used as the source of record
for those five instruments.

Data notes
----------
* Values are index points reported by the exchange; no adjustment applies.
* ``adj_close`` is intentionally NULL (indices are not adjusted for dividends).
* akshare performs its own HTTP internally; failures are caught and returned as
  errors so a blocked endpoint cannot abort a scan.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

import pandas as pd

from .base import FetchNote, FetchResult, PriceProvider, normalize_prices

SINA_CODE = {
    "CN_EQ_SSE": "sh000001",       # 上证综指
    "CN_EQ_SZSE": "sz399001",      # 深证成指
    "CN_EQ_CSI300": "sh000300",    # 沪深300
    "CN_EQ_CSI500": "sh000905",    # 中证500
    "CN_EQ_CSI1000": "sh000852",   # 中证1000
}


class AkshareCnIndexProvider(PriceProvider):
    provider_id = "akshare_cn_index"

    def fetch_prices(self, instruments: Sequence[dict[str, Any]], start: str | None = None,
                     end: str | None = None) -> FetchResult:
        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        notes: list[FetchNote] = []
        errors: list[str] = []
        frames: list[pd.DataFrame] = []
        try:
            import akshare as ak
        except Exception as exc:  # noqa: BLE001
            return FetchResult(frame=normalize_prices(pd.DataFrame(), self.provider_id, fetched_at),
                              source_id=self.provider_id, fetched_at=fetched_at,
                              errors=[f"akshare unavailable: {type(exc).__name__}: {exc}"])
        for spec in instruments:
            iid, symbol = spec["id"], spec["symbol"]
            code = SINA_CODE.get(iid) or symbol
            try:
                raw = ak.stock_zh_index_daily(symbol=code)
            except Exception as exc:  # noqa: BLE001 - per-symbol isolation
                errors.append(f"{iid} ({code}): {type(exc).__name__}: {exc}")
                continue
            if raw is None or raw.empty:
                notes.append(FetchNote("empty_series", "warning", f"{code} returned no rows", iid))
                continue
            df = raw.rename(columns={"date": "date", "open": "open", "high": "high", "low": "low",
                                     "close": "close", "volume": "volume"})
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            df = df[(df["close"] > 0)]
            if start:
                df = df[df["date"] >= start]
            if end:
                df = df[df["date"] <= end]
            if df.empty:
                notes.append(FetchNote("empty_window", "warning", f"{code} no rows in window", iid))
                continue
            df = df[["date", "open", "high", "low", "close", "volume"]].copy()
            df["instrument_id"] = iid
            df["adj_close"] = None
            frames.append(df)
        frame = (normalize_prices(pd.concat(frames, ignore_index=True), self.provider_id, fetched_at)
                 if frames else normalize_prices(pd.DataFrame(), self.provider_id, fetched_at))
        return FetchResult(frame=frame, source_id=self.provider_id, fetched_at=fetched_at,
                           notes=notes, errors=errors)
