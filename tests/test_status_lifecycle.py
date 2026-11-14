"""Opportunity status model (P1-08): auto scoring may demote; human decisions hold."""

from __future__ import annotations

import pytest

from conftest import make_draft
from goe.opportunities import apply_lifecycle, persist_drafts


class StubEngine:
    as_of = "2024-12-31"

    def __init__(self, draft):
        self.draft = draft

    def to_record(self, d):
        return {
            "fingerprint": d.fingerprint(), "as_of": self.as_of, "archetype": d.archetype,
            "title": d.title, "market": d.market, "asset_class": d.asset_class,
            "instruments": d.instruments, "horizon": d.horizon, "status": d.status,
            "status_reason": d.status_reason, "score": d.score,
            "score_breakdown": d.score_components,
            "discovery": {**d.discovery, "invalidation_checks": d.invalidation_checks},
            "mechanism": d.mechanism, "evidence_for": d.evidence_for,
            "evidence_against": d.evidence_against, "catalysts": d.catalysts,
            "open_questions": d.open_questions, "invalidation": d.invalidation,
            "invalidation_checks": d.invalidation_checks, "data_quality": d.data_quality,
        }

    def fv(self, *a, **k):
        return float("nan")


class BreachedEngine(StubEngine):
    def fv(self, *a, **k):
        return 1.0  # every >0 invalidation check fires


def _draft(status: str, score: float):
    d = make_draft()
    d.status = status
    d.score = score
    d.score_components = {"anomaly_strength": score}
    return d


def test_auto_score_can_demote_deep_research(store):
    d = _draft("deep_research", 0.71)
    persist_drafts(store, StubEngine(d), [d])
    row = store.conn.execute("SELECT status,status_source FROM opportunities").fetchone()
    assert row["status"] == "deep_research" and row["status_source"] == "auto"

    d2 = _draft("watch", 0.51)
    persist_drafts(store, StubEngine(d2), [d2])
    row = store.conn.execute("SELECT status,status_source,score FROM opportunities").fetchone()
    assert row["status"] == "watch", "自动评分下降必须降级状态"
    assert row["status_source"] == "auto"
    events = store.opportunity_events().to_dict("records")
    assert any(e["event_type"] == "status_change" and e["to_status"] == "watch" for e in events)


def test_manual_status_is_protected(store):
    d = _draft("deep_research", 0.70)
    persist_drafts(store, StubEngine(d), [d])
    oid = store.conn.execute("SELECT opportunity_id FROM opportunities").fetchone()[0]
    store.set_opportunity_status(oid, "watch", "PM: 需要观察催化", source="manual")

    d2 = _draft("deep_research", 0.80)   # auto would promote again
    persist_drafts(store, StubEngine(d2), [d2])
    row = store.conn.execute("SELECT status,status_source FROM opportunities").fetchone()
    assert row["status"] == "watch" and row["status_source"] == "manual"
    events = store.opportunity_events(oid).to_dict("records")
    assert any(e["event_type"] == "auto_status_held" for e in events)


def test_terminal_status_is_not_resurrected(store):
    d = _draft("watch", 0.55)
    persist_drafts(store, StubEngine(d), [d])
    oid = store.conn.execute("SELECT opportunity_id FROM opportunities").fetchone()[0]
    store.set_opportunity_status(oid, "invalidated", "条件触发", source="lifecycle")
    persist_drafts(store, StubEngine(_draft("deep_research", 0.75)), [_draft("deep_research", 0.75)])
    row = store.conn.execute("SELECT status FROM opportunities").fetchone()
    assert row["status"] == "invalidated"


def test_current_candidate_is_invalidated_when_its_own_check_fires(store):
    d = _draft("watch", 0.55)
    d.invalidation_checks = [{"entity": "X", "feature": "f", "op": ">", "value": 0.0}]
    persist_drafts(store, BreachedEngine(d), [d])
    row = store.conn.execute("SELECT opportunity_id,status FROM opportunities").fetchone()
    assert row["status"] == "invalidated", "a re-detected candidate must still respect invalidation_checks"
    assert store.conn.execute("SELECT COUNT(*) FROM opportunities WHERE status='watch'").fetchone()[0] == 0


def test_excluded_candidate_can_be_re_armed(store):
    d = _draft("excluded", 0.30)
    persist_drafts(store, StubEngine(d), [d])
    row = store.conn.execute("SELECT opportunity_id,status FROM opportunities").fetchone()
    assert row["status"] == "excluded"
    d2 = _draft("watch", 0.60)
    persist_drafts(store, StubEngine(d2), [d2])
    row = store.conn.execute("SELECT status,status_source FROM opportunities").fetchone()
    assert row["status"] == "watch", "excluded was treated as terminal and could never recover"
