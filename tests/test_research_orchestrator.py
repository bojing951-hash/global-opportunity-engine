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
                                 research_id=spec.research_id, learned=["x"], event_date="2026-11-11")
    calls = []
    monkeypatch.setattr("goe.research_orchestrator.execute_spec",
                        lambda store, spec: calls.append(spec) or fake)
    orch = ResearchOrchestrator(store)
    orch.register(spec)
    assert store.research_workflow_state(spec.research_id) == "PLANNED"
    assert orch.run(spec) is fake
    assert calls[0].research_id == spec.research_id
    assert store.research_workflow_state(spec.research_id) == "INCONCLUSIVE"
    assert any(r["workflow"] == "INCONCLUSIVE" for r in orch.status())
