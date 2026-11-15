from __future__ import annotations

import types

from goe.db import Store
from goe.research_engine import spec_for_asset
from goe.research_orchestrator import ResearchOrchestrator


def test_orchestrator_runs_and_records_workflow(tmp_path, monkeypatch):
    store = Store(str(tmp_path / "t.db"))
    spec = spec_for_asset(
        asset="US_FX_DXY", market="US", asset_class="fx", as_of="2026-11-13",
        question="q", peers={"GX_FX_EURUSD": ("EURUSD", "same_day")},
        hypotheses=[("H-FX-RATES", {"label": "rates", "type": "rates"})],
        case_kind="fx_level")
    fake = types.SimpleNamespace(finding_id="F", status="INCONCLUSIVE",
                                 research_id=spec.research_id, learned=["x"], event_date="2026-11-11",
                                 hypothesis_updates={"H-FX-RATES": {"status": "INCONCLUSIVE"}})
    calls = []
    monkeypatch.setattr("goe.research_orchestrator.execute_spec",
                        lambda store, spec: calls.append(spec) or fake)
    orch = ResearchOrchestrator(store)
    orch.register(spec)
    assert store.research_workflow_state(spec.research_id) == "PLANNED"
    assert orch.run(spec) is fake
    orch.register(spec)  # rescan must not reset completed workflow
    assert store.research_workflow_state(spec.research_id) == "INCONCLUSIVE"
    assert calls[0].research_id == spec.research_id
    assert store.research_workflow_state(spec.research_id) == "INCONCLUSIVE"
    assert any(r["workflow"] == "INCONCLUSIVE" for r in orch.status())


def test_next_case_selects_real_candidate_queue_not_fixed_cases(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    cand = {
        "research_id": "RC-TEST-TW-1", "research_theme_id": "RT-TEST-TW",
        "as_of": "2026-11-13", "market": "TW", "asset_class": "equity_index",
        "instruments": ["TW_EQ_TAIEX"], "observed_phenomenon": "price_return_shock down",
        "priority_tier": "intelligence", "research_worthiness": "medium",
        "evidence_readiness": "partial", "research_queue": "watch",
        "handoff_eligibility": "a_retained",
        "competing_hypotheses": [{"id": "H-EQTW-LOCAL", "label": "local", "type": "local"}],
    }
    store.upsert_research_candidate(cand)
    store.conn.execute("""INSERT INTO anomalies(anomaly_id,as_of,detector,family,instrument_id,
        direction,magnitude,score,percentile,window,evidence_json,fingerprint,run_id,created_at)
        VALUES('A1','2026-11-06','price_return_shock','price','TW_EQ_TAIEX','down',0.04,0.8,0.0,
               '1d','{}','f','r','x')""")
    store.conn.commit()
    orch = ResearchOrchestrator(store)
    spec = orch.next_case()
    assert spec is not None
    assert spec.research_id == "RC-TEST-TW-1"
