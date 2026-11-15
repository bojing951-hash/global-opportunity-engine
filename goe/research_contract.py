"""Immutable Research Question & Event Contract (V4)."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


class EventNotResolved(ValueError):
    pass


def _phenomenon(c: dict[str, Any]) -> tuple[str, str, str]:
    text = str(c.get("observed_phenomenon") or "").lower()
    if "drawdown" in text:
        det = "drawdown_extreme"
        direction = "deep_drawdown" if ("deep" in text or "回撤" in text) else "near_high"
    elif "price_return_shock" in text or "收益" in text:
        det = "price_return_shock"
        direction = "down" if ("down" in text or "-" in text or "下跌" in text) else "up"
    elif "vol_regime" in text:
        det, direction = "vol_regime_shift", "expansion"
    else:
        det, direction = "", ""
    return det, direction, "1d"


@dataclass(frozen=True)
class EventContract:
    research_id: str
    research_theme_id: str
    asset_id: str
    market: str
    asset_class: str
    phenomenon_id: str
    detector_id: str
    direction: str
    detection_window: str
    event_start: str
    event_end: str
    event_timestamp: str
    event_timezone: str
    decision_as_of: str
    observed_facts: tuple[str, ...]
    research_question: str
    source_snapshot: str
    data_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_event(candidate: dict[str, Any], conn) -> EventContract:
    """Bind a candidate to one stored anomaly; never silently pick another event."""
    asset = str((candidate.get("instruments") or [""])[0])
    inferred_det, inferred_dir, window = _phenomenon(candidate)
    detector = str(candidate.get("detector_id") or inferred_det)
    direction = str(candidate.get("direction") or inferred_dir)
    if not detector:
        raise EventNotResolved(f"EVENT_NOT_RESOLVED: no phenomenon detector for {candidate.get('research_id')}")
    hint = candidate.get("event_date")
    if hint:
        row = conn.execute(
            """SELECT as_of,detector,direction,evidence_json FROM anomalies
               WHERE instrument_id=? AND detector=? AND as_of=?""",
            (asset, detector, str(hint))).fetchone()
    else:
        row = conn.execute(
            """SELECT as_of,detector,direction,evidence_json FROM anomalies
               WHERE instrument_id=? AND detector=? AND as_of<=?
                 AND (?='' OR direction LIKE ?)
               ORDER BY as_of DESC, score DESC LIMIT 1""",
            (asset, detector, candidate.get("as_of"), direction,
             "%" + direction + "%" if direction else "%")).fetchone()
    if not row:
        raise EventNotResolved(f"EVENT_NOT_RESOLVED: no matching anomaly for {asset} {detector} {direction}")
    date = str(row["as_of"])
    return EventContract(
        research_id=str(candidate["research_id"]),
        research_theme_id=str(candidate.get("research_theme_id") or ""),
        asset_id=asset, market=str(candidate.get("market") or ""),
        asset_class=str(candidate.get("asset_class") or ""),
        phenomenon_id=f"{detector}|{asset}|{row['direction']}|{date}",
        detector_id=detector, direction=str(row["direction"]), detection_window=window,
        event_start=date, event_end=date, event_timestamp=date + "T23:59:59Z",
        event_timezone="exchange_local", decision_as_of=str(candidate.get("as_of")),
        observed_facts=(str(candidate.get("observed_phenomenon") or ""),),
        research_question=str(candidate.get("observed_phenomenon") or ""),
        source_snapshot="goe.db:prices+anomalies", data_version="scan-20261115T044634Z-b68802")
