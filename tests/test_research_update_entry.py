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
