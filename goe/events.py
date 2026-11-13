"""Scheduled event calendar (catalysts).

Events are optional: with an empty calendar the catalyst component of the score
falls back to a low value and no event-driven opportunity is generated. Only
entries with an official, checked source should be marked ``verified: true``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from .config import load_yaml_config


@dataclass
class Event:
    id: str
    date: str
    region: str
    type: str
    title: str
    affects: list[str]
    source: str
    verified: bool

    @property
    def date_obj(self) -> date:
        return datetime.strptime(self.date, "%Y-%m-%d").date()


class EventCalendar:
    def __init__(self, events: Iterable[Event]):
        self.events = sorted(list(events), key=lambda e: e.date)

    @classmethod
    def load(cls, path: str | None = None) -> "EventCalendar":
        cfg = load_yaml_config(path or "events.yaml")
        out = []
        for raw in cfg.get("events", []) or []:
            try:
                out.append(Event(
                    id=str(raw["id"]), date=str(raw["date"]), region=str(raw.get("region", "")),
                    type=str(raw.get("type", "")), title=str(raw.get("title", "")),
                    affects=list(raw.get("affects", []) or []), source=str(raw.get("source", "")),
                    verified=bool(raw.get("verified", False)),
                ))
            except Exception:
                continue
        return cls(out)

    def upcoming(self, as_of: str, within_days: int = 45) -> list[Event]:
        start = datetime.strptime(as_of, "%Y-%m-%d").date()
        end = start + timedelta(days=within_days)
        return [e for e in self.events if start <= e.date_obj <= end]

    def for_entities(self, entity_ids: Iterable[str], as_of: str, within_days: int = 45) -> list[Event]:
        ids = set(entity_ids)
        return [e for e in self.upcoming(as_of, within_days) if ids & set(e.affects)]

    def nearest(self, entity_ids: Iterable[str], as_of: str, within_days: int = 45) -> Event | None:
        evs = self.for_entities(entity_ids, as_of, within_days)
        return evs[0] if evs else None

    def to_dicts(self, events: Iterable[Event]) -> list[dict[str, Any]]:
        return [{"id": e.id, "date": e.date, "type": e.type, "title": e.title,
                 "verified": e.verified, "source": e.source} for e in events]
