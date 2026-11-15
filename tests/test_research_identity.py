from __future__ import annotations

from goe.research_identity import research_id
from goe.db import Store


def rid(as_of="2026-11-13", iid="JP_EQ_N225", det="drawdown_extreme",
        direction="deep_drawdown", window="1d"):
    return research_id(as_of=as_of, instrument_id=iid, detector=det,
                       direction=direction, window=window)


def test_identity_is_order_independent_and_content_specific():
    ids = [rid(), rid("2026-11-13", "US_EQ_SPY"), rid(det="vol_regime_shift"),
           rid(direction="near_high"), rid("2026-11-14")]
    assert len(ids) == len(set(ids))
    assert rid() == rid()                       # repeat scan
    assert rid() != rid(det="vol_regime_shift") # different anomaly
    assert rid() != rid(iid="US_EQ_SPY")        # different asset
    # list order does not enter the function
    assert sorted(ids) == sorted(reversed(ids))


def test_legacy_alias_preserves_old_task_link(store):
    old = "RC-20261113-12"
    new = rid()
    store.upsert_research_candidate({
        "research_id": old, "as_of": "2026-11-13", "market": "JP",
        "asset_class": "equity_index", "instruments": ["JP_EQ_N225"],
        "observed_phenomenon": "legacy", "priority_tier": "intelligence",
        "competing_hypotheses": [], "evidence": []})
    store.upsert_research_task_v2({"task_id": "T-LEGACY", "research_id": old,
                                   "status": "not_completed:refused"})
    store.record_identity_alias(old, new, "order-dependent legacy id")
    assert store.identity_lookup(old) == new
    assert store.conn.execute("SELECT research_id FROM research_v2_tasks WHERE task_id='T-LEGACY'").fetchone()[0] == old
    assert store.research_integrity()["orphan_tasks"] == 0


def test_duplicate_upsert_keeps_identity_and_task(store):
    c = {"research_id": rid(), "as_of": "2026-11-13", "market": "JP",
         "asset_class": "equity_index", "instruments": ["JP_EQ_N225"],
         "observed_phenomenon": "x", "priority_tier": "intelligence",
         "competing_hypotheses": [], "evidence": []}
    store.upsert_research_candidate(c)
    store.upsert_research_task_v2({"task_id": "T1", "research_id": c["research_id"],
                                   "status": "not_completed:refused"})
    store.upsert_research_candidate({**c, "observed_phenomenon": "updated"})
    assert store.research_candidate(c["research_id"])["phenomenon"] == "updated"
    assert store.conn.execute("SELECT COUNT(*) FROM research_v2_tasks WHERE research_id=?",
                              (c["research_id"],)).fetchone()[0] == 1
