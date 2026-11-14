"""Frequency-aware recency windows.

Daily market anomalies are "current" for a few days; a monthly macro release is
published every ~30 days and must remain eligible for screening for a longer
window, otherwise the 7-day opportunity/trigger window can never contain a
monthly macro observation (audit P1-02).

Windows are anchored on the anomaly's AVAILABILITY date, not its observation
date. Values are deliberately conservative and documented here:

    daily / curve / cross-asset : 7 days
    weekly (CFTC)               : 21 days
    monthly macro / valuation   : 75 days
    quarterly macro             : 150 days
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .config import load_macro, load_positioning

_BASE = {"daily": 7, "weekly": 21, "monthly": 75, "quarterly": 150, "annual": 365}


@lru_cache(maxsize=1)
def _macro_freq() -> dict[str, str]:
    return {sid: m.frequency for sid, m in load_macro().items()}


@lru_cache(maxsize=1)
def _positioning_ids() -> frozenset[str]:
    return frozenset(load_positioning())


def recency_days(entity_kind: str, entity_id: str) -> int:
    freq = _macro_freq().get(entity_id)
    if freq:
        return _BASE.get(freq, 30)
    if entity_kind == "valuation":
        return _BASE["monthly"]
    if entity_kind == "positioning" or entity_id in _positioning_ids() or entity_id.endswith(":oi"):
        return _BASE["weekly"]
    if entity_kind == "region":
        return _BASE["daily"]
    return _BASE["daily"]


def recent_mask(available: pd.Series, entity_ids: pd.Series, kinds: pd.Series,
                as_of: pd.Timestamp) -> pd.Series:
    """Vectorised 'is this anomaly recent for its own data frequency?'."""
    window = pd.Series(
        [recency_days(k, e) for k, e in zip(kinds.tolist(), entity_ids.tolist())],
        index=available.index, dtype="float64")
    return available >= (as_of - pd.to_timedelta(window, unit="D"))


def filter_recent(frame: pd.DataFrame, as_of: pd.Timestamp, *, window_days: int | None = None) -> pd.DataFrame:
    """Filter an anomaly frame by availability date with frequency-aware windows.

    ``window_days`` forces a fixed window (e.g. the historical replay's 10-day
    event window) when the caller needs one.
    """
    if frame is None or frame.empty:
        return frame if frame is not None else pd.DataFrame()
    avail = pd.to_datetime(frame["available_date"]) if "available_date" in frame.columns \
        else pd.to_datetime(frame["date"])
    if window_days is not None:
        mask = (avail >= as_of - pd.Timedelta(days=window_days)) & (avail <= as_of)
    else:
        kinds = frame["entity_kind"] if "entity_kind" in frame.columns else pd.Series("instrument", index=frame.index)
        ids = frame["entity_id"]
        mask = recent_mask(avail, ids, kinds, as_of) & (avail <= as_of)
    return frame[mask]
