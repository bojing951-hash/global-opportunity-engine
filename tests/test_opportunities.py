"""Opportunity identity, persistence, theme de-duplication and lifecycle rules."""

from __future__ import annotations

import json

import pandas as pd

from conftest import END_DATE, instrument_dict, make_draft, make_feature_set
from goe.opportunities import (
    OpportunityEngine,
    _checks_breached,
    apply_lifecycle,
    fingerprint,
    persist_drafts,
)


def _engine(as_of: str = END_DATE, rows=None) -> OpportunityEngine:
    fs = make_feature_set(as_of=as_of, rows=rows)
    return OpportunityEngine(fs, pd.DataFrame())


def _draft_for(iid: str, *, archetype: str = "relative_value", score: float = 0.5,
               mechanism_id: str | None = None):
    draft = make_draft(archetype=archetype, instruments=[instrument_dict(iid)],
                       mechanism_id=mechanism_id)
    draft.score = score
    return draft


# ------------------------------------------------------------------ identity
def test_fingerprint_is_stable_regardless_of_date_and_id_order():
    ids = ["CM_MET_GC", "CM_ETF_GLD"]
    assert fingerprint("relative_value", ids, "M1") == fingerprint(
        "relative_value", list(reversed(ids)), "M1")
    assert fingerprint("relative_value", ids, "M1") == fingerprint(
        "relative_value", ids, "M1")

    first = make_draft(archetype="relative_value",
                       instruments=[instrument_dict("CM_MET_GC"), instrument_dict("CM_ETF_GLD")],
                       mechanism_id="M1")
    later = make_draft(archetype="relative_value",
                       instruments=[instrument_dict("CM_ETF_GLD"), instrument_dict("CM_MET_GC")],
                       mechanism_id="M1", title="另一天再次检测到的同一现象")
    assert first.fingerprint() == later.fingerprint()

    # Different primary instruments, mechanism or archetype -> different id.
    other_instrument = make_draft(archetype="relative_value",
                                  instruments=[instrument_dict("CM_MET_GC")], mechanism_id="M1")
    other_mechanism = make_draft(archetype="relative_value",
                                 instruments=[instrument_dict("CM_MET_GC"), instrument_dict("CM_ETF_GLD")],
                                 mechanism_id="M2")
    other_archetype = make_draft(archetype="expectation_overshoot",
                                 instruments=[instrument_dict("CM_MET_GC"), instrument_dict("CM_ETF_GLD")],
                                 mechanism_id="M1")
    assert len({first.fingerprint(), other_instrument.fingerprint(),
                other_mechanism.fingerprint(), other_archetype.fingerprint()}) == 4


def test_persist_drafts_is_idempotent_and_counts_refreshes(store):
    engine = _engine()
    draft = make_draft()

    first = persist_drafts(store, engine, [draft])
    assert first["created"] == 1
    assert first["refreshed"] == 0
    assert store.scalar("SELECT COUNT(*) FROM opportunities") == 1
    oid = store.find_opportunity(draft.fingerprint())["opportunity_id"]

    second = persist_drafts(store, engine, [draft])
    assert second["created"] == 0
    assert second["refreshed"] == 1
    assert store.scalar("SELECT COUNT(*) FROM opportunities") == 1
    row = store.find_opportunity(draft.fingerprint())
    assert row["opportunity_id"] == oid
    assert row["last_seen"] == END_DATE

    event_types = [r[0] for r in store.conn.execute(
        "SELECT event_type FROM opportunity_events WHERE opportunity_id=? ORDER BY event_id", (oid,))]
    assert event_types == ["created", "refreshed"]


# -------------------------------------------------------------- theme dedupe
def _stub_generate(engine, drafts):
    """Replace every archetype rule with fixtures (dedupe logic stays intact)."""
    engine._score = lambda _draft: None
    for name in ("_price_fundamental_divergence", "_expectation_overshoot",
                 "_regime_repricing", "_event_revision", "_relative_value"):
        setattr(engine, name, lambda: [])
    engine._relative_value = lambda: drafts


def test_same_theme_and_archetype_collapse_to_the_strongest():
    engine = _engine()
    _stub_generate(engine, [
        _draft_for("CM_MET_GC", score=0.40),     # theme: gold
        _draft_for("CM_ETF_GLD", score=0.70),    # theme: gold (same phenomenon)
    ])
    kept = engine.generate()
    assert len(kept) == 1
    assert kept[0].score == 0.70
    assert kept[0].primary_ids() == ["CM_ETF_GLD"]

    # Different themes are distinct opportunities and both are kept.
    engine2 = _engine()
    _stub_generate(engine2, [
        _draft_for("CM_MET_GC", score=0.40),     # gold
        _draft_for("CM_ENE_CL", score=0.70),     # crude_oil
    ])
    kept2 = engine2.generate()
    assert {tuple(d.primary_ids()) for d in kept2} == {("CM_MET_GC",), ("CM_ENE_CL",)}


# ------------------------------------------------------------------ lifecycle
def test_apply_lifecycle_expires_stale_and_keeps_fresh(store):
    old_engine = _engine(as_of="2024-03-01")
    old_draft = make_draft(instruments=[instrument_dict("US_EQ_SPY")])
    store.upsert_opportunity(old_engine.to_record(old_draft))

    fresh_engine = _engine(as_of="2024-12-20")
    fresh_draft = make_draft(instruments=[instrument_dict("US_EQ_QQQ")])
    store.upsert_opportunity(fresh_engine.to_record(fresh_draft))

    now = _engine(as_of=END_DATE)
    stats = apply_lifecycle(store, now, {}, expire_days=45)

    assert stats == {"expired": 1, "invalidated": 0}
    old = store.find_opportunity(old_draft.fingerprint())
    fresh = store.find_opportunity(fresh_draft.fingerprint())
    assert old["status"] == "expired"
    assert old["last_seen"] == "2024-03-01"
    assert "45" in old["status_reason"]
    assert json.loads(old["lifecycle_json"])[-1]["to"] == "expired"

    assert fresh["status"] == "new"
    assert fresh["last_seen"] == "2024-12-20"
    assert json.loads(fresh["lifecycle_json"]) == []


def _feature_rows(value: float) -> list[tuple]:
    return [("instrument", "US_EQ_SPY", "equity_etf", "US",
             "rel_strength_vs_benchmark", "1m", END_DATE, value)]


def _checked_draft():
    checks = [{"entity": "US_EQ_SPY", "feature": "rel_strength_vs_benchmark",
               "window": "1m", "op": "<", "value": -0.08,
               "note": "相对基准继续大幅跑输"}]
    draft = make_draft(discovery={
        "what": "SPY 相对基准走弱",
        "anomalies": [{"score": 0.7}],
        "invalidation_checks": checks,
    })
    draft.invalidation_checks = checks
    return draft


def test_checks_breached_evaluates_configured_checks(store):
    breached_engine = _engine(rows=_feature_rows(-0.10))
    draft = _checked_draft()
    oid = store.upsert_opportunity(breached_engine.to_record(draft))
    assert _checks_breached(store, breached_engine, oid) is True

    safe_engine = _engine(rows=_feature_rows(-0.01))
    assert _checks_breached(store, safe_engine, oid) is False
    assert _checks_breached(store, safe_engine, "OPP-9999") is False


def test_apply_lifecycle_invalidates_when_check_is_breached(store):
    old_engine = _engine(as_of="2024-03-01", rows=_feature_rows(-0.20))
    draft = _checked_draft()
    store.upsert_opportunity(old_engine.to_record(draft))

    now = _engine(as_of=END_DATE, rows=_feature_rows(-0.20))
    stats = apply_lifecycle(store, now, {}, expire_days=45)

    assert stats == {"expired": 0, "invalidated": 1}
    row = store.find_opportunity(draft.fingerprint())
    assert row["status"] == "invalidated"
    assert "invalidation_checks" in row["status_reason"]
