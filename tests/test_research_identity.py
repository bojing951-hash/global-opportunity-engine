from __future__ import annotations

import pytest

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


def _cand(rid, as_of="2026-11-13", iid="JP_EQ_N225", theme="RT-1"):
    return {"research_id": rid, "research_theme_id": theme, "as_of": as_of,
            "market": "JP", "asset_class": "equity_index", "instruments": [iid],
            "observed_phenomenon": "x", "priority_tier": "intelligence",
            "competing_hypotheses": [], "evidence": []}


def test_immutable_identity_rejects_asset_and_date_retarget(store):
    c = _cand(rid())
    store.upsert_research_candidate(c)
    for bad in (_cand(rid(), iid="US_EQ_SPY"), _cand(rid(), as_of="2026-11-14")):
        with pytest.raises(ValueError, match="immutable research identity"):
            store.upsert_research_candidate(bad)
    row = store.research_candidate(c["research_id"])
    assert row["as_of"] == "2026-11-13" and "JP_EQ_N225" in row["instruments_json"]


def test_completed_status_is_not_silently_reopened(store):
    c = _cand(rid())
    store.upsert_research_candidate(c)
    store.set_research_status(c["research_id"], "research_complete", "done")
    store.upsert_research_candidate({**c, "observed_phenomenon": "updated"})
    assert store.research_candidate(c["research_id"])["status"] == "research_complete"
    with pytest.raises(ValueError, match="cannot be reopened"):
        store.set_research_status(c["research_id"], "active")


def test_theme_is_stable_across_dates_event_is_not():
    from goe.research_identity import research_theme_id
    t1 = research_theme_id(instrument_id="JP_EQ_N225", detector="drawdown_extreme",
                           direction="deep_drawdown", window="1d")
    t2 = research_theme_id(instrument_id="JP_EQ_N225", detector="drawdown_extreme",
                           direction="deep_drawdown", window="1d")
    assert t1 == t2 and t1.startswith("RT-")
    assert rid("2026-11-13") != rid("2026-11-14")
    assert rid("2026-11-13") != rid(det="vol_regime_shift")


def test_rescan_preserves_research_hypotheses_evidence_and_findings(store):
    c = _cand(rid())
    c["competing_hypotheses"] = [
        {"id": "H-LOCAL", "status": "open", "type": "local"},
        {"id": "H-GLOBAL", "status": "open", "type": "global"}]
    c["evidence"] = [{"claim": "base", "source": "prices", "available_at": "2026-11-13",
                      "class": "observed_fact"}]
    store.upsert_research_candidate(c)
    store.update_research_hypotheses(c["research_id"], {
        "H-LOCAL": {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE", "label": "local", "type": "local"},
        "H-NEW": {"status": "INSUFFICIENT_DATA", "label": "new", "type": "new"}})
    store.add_research_finding("F1", c["research_id"], "INCONCLUSIVE", {"v": 1}, "f.json")
    # A later scan sends the original open hypotheses; it must not reset anything.
    store.upsert_research_candidate(c)
    statuses = dict(store.conn.execute(
        "SELECT hypothesis_key,status FROM research_v2_hypotheses WHERE research_id=?",
        (c["research_id"],)).fetchall())
    assert statuses["H-LOCAL"] == "SUPPORTED_BY_AVAILABLE_EVIDENCE"
    assert statuses["H-NEW"] == "INSUFFICIENT_DATA"
    assert store.conn.execute("SELECT COUNT(*) FROM research_v2_evidence WHERE research_id=?",
                              (c["research_id"],)).fetchone()[0] == 1
    assert store.conn.execute("SELECT COUNT(*) FROM research_v2_hypothesis_revisions WHERE research_id=?",
                              (c["research_id"],)).fetchone()[0] >= 3
    # Findings are append-only.
    store.add_research_finding("F1", c["research_id"], "COMPLETED", {"v": 2}, "f2.json")
    assert store.conn.execute("SELECT status FROM research_v2_findings WHERE finding_id='F1'").fetchone()[0] == "INCONCLUSIVE"
