from __future__ import annotations

import types

import pandas as pd

from goe.cli import cmd_ingest
from goe.db import Store


def test_ingest_entry_queues_update_for_related_research(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    store = Store(str(db))
    c = {"research_id": "R-AUTO", "research_theme_id": "T", "as_of": "2026-11-13",
         "market": "TW", "asset_class": "equity_index", "instruments": ["TW_EQ_TAIEX"],
         "observed_phenomenon": "price_return_shock down", "priority_tier": "intelligence",
         "research_worthiness": "high", "evidence_readiness": "partial",
         "research_queue": "watch", "competing_hypotheses": [], "evidence": []}
    store.upsert_research_candidate(c)
    store.upsert_prices(pd.DataFrame([{"instrument_id": "TW_EQ_TAIEX", "date": "2026-11-12",
                                       "close": 100.0, "adj_close": 100.0,
                                       "source_id": "test", "fetched_at": "2026-11-12T00:00:00Z"}]))
    store.add_research_finding("F-AUTO", "R-AUTO", "INCONCLUSIVE", {}, "f.json")
    store.close()

    class FakeIngestor:
        def __init__(self, store): self.store = store
        def register_metadata(self): pass
        def ingest_prices(self, mode="incremental", instruments=None):
            self.store.upsert_prices(pd.DataFrame([{"instrument_id": "TW_EQ_TAIEX",
                "date": "2026-11-13", "close": 101.0, "adj_close": 101.0,
                "source_id": "test", "fetched_at": "2026-11-13T00:00:00Z"}]))
            return types.SimpleNamespace(to_dict=lambda: {"rows": 1})

    monkeypatch.setattr("goe.ingest.Ingestor", FakeIngestor)
    args = types.SimpleNamespace(db=str(db), prices_only=True, indicators_only=False,
                                 mode="incremental", json=True)
    assert cmd_ingest(args) == 0
    store2 = Store(str(db))
    try:
        assert store2.open_research_update_count("R-AUTO") == 1
        update = store2.pending_research_update("R-AUTO")
        assert update["trigger_type"] == "price_revision"
    finally:
        store2.close()


def test_peer_dependency_revision_triggers_only_related_research(tmp_path):
    from goe.research_updates import notify_price_changes
    store = Store(str(tmp_path / "d.db"))
    c = {"research_id": "R-DEP", "research_theme_id": "T", "as_of": "2026-11-13",
         "market": "US", "asset_class": "equity_etf", "instruments": ["US_EQ_QQQ"],
         "observed_phenomenon": "relative underperform", "priority_tier": "intelligence",
         "research_worthiness": "high", "evidence_readiness": "partial",
         "research_queue": "watch", "competing_hypotheses": [], "evidence": []}
    store.upsert_research_candidate(c)
    store.add_research_finding("F1", "R-DEP", "INCONCLUSIVE",
                               {"plan": {"peers": {"US_EQ_SPY": "US", "US_VOL_VIX": "VIX",
                                                   "US_FI_IEF": "rates", "US_FX_DXY": "USD",
                                                   "CM_MET_GC": "gold"}}}, "f.json")
    deps = store.research_dependencies("R-DEP", "2026-11-13")
    assert {"US_EQ_QQQ", "US_EQ_SPY", "US_VOL_VIX", "US_FI_IEF", "US_FX_DXY", "CM_MET_GC"} <= set(deps)
    before = {"R-DEP": {d: "old" for d in deps}}
    after = {"R-DEP": {d: ("new" if d == "US_FI_IEF" else "old") for d in deps}}
    created = notify_price_changes(store, before, after)
    assert len(created) == 1 and created[0]["instrument"] == "US_FI_IEF"
    assert store.open_research_update_count("R-DEP") == 1
    # Unrelated asset change does not create an update.
    before2 = {"R-DEP": {d: "old" for d in deps}}
    after2 = {"R-DEP": {d: "old" for d in deps}}
    assert notify_price_changes(store, before2, after2) == []


def test_b_to_c_to_b_transitions_are_not_swallowed(tmp_path):
    from goe.research_updates import notify_price_changes
    store = Store(str(tmp_path / "b.db"))
    c = {"research_id": "R-BCB", "research_theme_id": "T", "as_of": "2026-11-13",
         "market": "US", "asset_class": "equity_etf", "instruments": ["US_EQ_QQQ"],
         "observed_phenomenon": "x", "priority_tier": "intelligence",
         "research_worthiness": "high", "evidence_readiness": "partial",
         "research_queue": "watch", "competing_hypotheses": []}
    store.upsert_research_candidate(c)
    store.add_research_finding("F1", "R-BCB", "INCONCLUSIVE", {"plan": {"peers": {}}}, "f.json")
    for old, new in [("A", "B"), ("B", "C"), ("C", "B"), ("B", "C")]:
        notify_price_changes(store, {"R-BCB": {"US_EQ_QQQ": old}},
                             {"R-BCB": {"US_EQ_QQQ": new}})
    assert store.open_research_update_count("R-BCB") == 4
    # Same occurrence delivered twice with the same batch is idempotent.
    n = store.open_research_update_count("R-BCB")
    notify_price_changes(store, {"R-BCB": {"US_EQ_QQQ": "B"}},
                         {"R-BCB": {"US_EQ_QQQ": "C"}}, batch="same")
    notify_price_changes(store, {"R-BCB": {"US_EQ_QQQ": "B"}},
                         {"R-BCB": {"US_EQ_QQQ": "C"}}, batch="same")
    assert store.open_research_update_count("R-BCB") == n + 1


def test_ingest_peer_revision_reactivates_qqq(tmp_path, monkeypatch):
    import types
    db = tmp_path / "q.db"
    store = Store(str(db))
    c = {"research_id": "R-QQQ", "research_theme_id": "T", "as_of": "2026-11-13",
         "market": "US", "asset_class": "equity_etf", "instruments": ["US_EQ_QQQ"],
         "observed_phenomenon": "relative underperform", "priority_tier": "intelligence",
         "research_worthiness": "high", "evidence_readiness": "partial",
         "research_queue": "watch", "competing_hypotheses": [], "evidence": []}
    store.upsert_research_candidate(c)
    store.add_research_finding("F1", "R-QQQ", "INCONCLUSIVE",
                               {"plan": {"peers": {"US_EQ_SPY": "x", "US_VOL_VIX": "x",
                                                   "US_FI_IEF": "x", "US_FX_DXY": "x",
                                                   "CM_MET_GC": "x"}}}, "f.json")
    for iid in ["US_EQ_QQQ", "US_EQ_SPY", "US_VOL_VIX", "US_FI_IEF", "US_FX_DXY", "CM_MET_GC"]:
        store.upsert_prices(pd.DataFrame([{"instrument_id": iid, "date": "2026-11-12",
                                           "close": 100.0, "adj_close": 100.0,
                                           "source_id": "test", "fetched_at": "2026-11-12T00:00:00Z"}]))
    store.close()

    class FakeIngestor:
        def __init__(self, store): self.store = store
        def register_metadata(self): pass
        def ingest_prices(self, mode="incremental", instruments=None):
            self.store.upsert_prices(pd.DataFrame([{"instrument_id": "US_FI_IEF",
                "date": "2026-11-13", "close": 100.5, "adj_close": 100.5,
                "source_id": "test", "fetched_at": "2026-11-13T00:00:00Z"}]))
            return types.SimpleNamespace(to_dict=lambda: {"rows": 1})

    monkeypatch.setattr("goe.ingest.Ingestor", FakeIngestor)
    args = types.SimpleNamespace(db=str(db), prices_only=True, indicators_only=False,
                                 mode="incremental", json=True)
    assert cmd_ingest(args) == 0
    store2 = Store(str(db))
    try:
        u = store2.pending_research_update("R-QQQ")
        assert u and "US_FI_IEF" in u["trigger_key"]
    finally:
        store2.close()
