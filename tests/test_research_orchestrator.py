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


def test_unresolved_high_priority_candidate_does_not_block_valid_one(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    bad = {"research_id": "A-BAD", "research_theme_id": "T", "as_of": "2026-11-13",
           "market": "TW", "asset_class": "equity_index", "instruments": ["NO_SUCH"],
           "observed_phenomenon": "price_return_shock down", "priority_tier": "intelligence",
           "research_worthiness": "high", "evidence_readiness": "ready",
           "research_queue": "watch", "competing_hypotheses": []}
    good = {**bad, "research_id": "B-GOOD", "instruments": ["TW_EQ_TAIEX"],
            "observed_phenomenon": "price_return_shock down", "research_worthiness": "medium",
            "detector_id": "price_return_shock", "direction": "down", "event_date": "2026-11-06"}
    store.upsert_research_candidate(bad)
    store.upsert_research_candidate(good)
    store.conn.execute("""INSERT INTO anomalies(anomaly_id,as_of,detector,family,instrument_id,
        direction,magnitude,score,percentile,window,evidence_json,fingerprint,run_id,created_at)
        VALUES('A1','2026-11-06','price_return_shock','price','TW_EQ_TAIEX','down',0.04,0.8,0.0,
               '1d','{}','f','r','x')""")
    store.conn.commit()
    spec = ResearchOrchestrator(store).next_case()
    assert spec is not None and spec.research_id == "B-GOOD"
    assert store.research_workflow_state("A-BAD") == "WAITING_FOR_DATA"


def test_register_preserves_screening_fields(tmp_path):
    from goe.research_engine import spec_for_asset
    store = Store(str(tmp_path / "t.db"))
    c = {"research_id": "R-SCREEN", "research_theme_id": "T", "as_of": "2026-11-13",
         "market": "TW", "asset_class": "equity_index", "instruments": ["TW_EQ_TAIEX"],
         "observed_phenomenon": "price_return_shock down", "priority_tier": "intelligence",
         "research_worthiness": "high", "evidence_readiness": "ready", "research_queue": "research",
         "handoff_eligibility": "eligible", "materiality": {"importance": .9, "gap_score": .8},
         "research_cost": {"hours": 3}, "evidence": [{"claim": "screening"}]}
    store.upsert_research_candidate(c)
    spec = spec_for_asset(asset="TW_EQ_TAIEX", market="TW", asset_class="equity_index",
                          as_of="2026-11-13", question="q", peers={}, hypotheses=[],
                          case_kind="equity_event")
    spec.research_id = "R-SCREEN"
    ResearchOrchestrator(store).register(spec)
    row = store.research_candidate("R-SCREEN")
    import json
    p = json.loads(row["payload_json"])
    assert p["research_worthiness"] == "high"
    assert p["evidence_readiness"] == "ready"
    assert p["research_queue"] == "research"
    assert p["handoff_eligibility"] == "eligible"
    assert p["research_cost"] == {"hours": 3}
    assert p["evidence"] == [{"claim": "screening"}]


def test_finding_can_reenter_after_evidence_update(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    c = {"research_id": "R-REENTRY", "research_theme_id": "T", "as_of": "2026-11-13",
         "market": "TW", "asset_class": "equity_index", "instruments": ["TW_EQ_TAIEX"],
         "observed_phenomenon": "price_return_shock down", "detector_id": "price_return_shock",
         "direction": "down", "event_date": "2026-11-06",
         "priority_tier": "intelligence", "research_worthiness": "high",
         "evidence_readiness": "partial", "research_queue": "watch",
         "competing_hypotheses": [{"id": "H-EQTW-LOCAL", "label": "local", "type": "local"}]}
    store.upsert_research_candidate(c)
    store.conn.execute("""INSERT INTO anomalies(anomaly_id,as_of,detector,family,instrument_id,
        direction,magnitude,score,percentile,window,evidence_json,fingerprint,run_id,created_at)
        VALUES('A1','2026-11-06','price_return_shock','price','TW_EQ_TAIEX','down',0.04,0.8,0.0,
               '1d','{}','f','r','x')""")
    store.conn.commit()
    store.add_research_finding("F1", "R-REENTRY", "INCONCLUSIVE", {"v": 1}, "f.json")
    orch = ResearchOrchestrator(store)
    assert orch.next_case() is None  # no new evidence -> no empty rerun
    orch.reopen("R-REENTRY", "new evidence arrived")
    spec = orch.next_case()
    assert spec is not None and spec.research_id == "R-REENTRY"


def test_no_change_reopen_is_consumed_and_does_not_loop(tmp_path, monkeypatch):
    import time, types
    from goe.research_updates import notify_price_changes
    store = Store(str(tmp_path / "t.db"))
    c = {"research_id": "R-CONSUME", "research_theme_id": "T", "as_of": "2026-11-13",
         "market": "TW", "asset_class": "equity_index", "instruments": ["TW_EQ_TAIEX"],
         "observed_phenomenon": "price_return_shock down", "detector_id": "price_return_shock",
         "direction": "down", "event_date": "2026-11-06",
         "priority_tier": "intelligence", "research_worthiness": "high",
         "evidence_readiness": "partial", "research_queue": "watch",
         "competing_hypotheses": [{"id": "H-EQTW-LOCAL", "label": "local", "type": "local"}]}
    store.upsert_research_candidate(c)
    store.conn.execute("""INSERT INTO anomalies(anomaly_id,as_of,detector,family,instrument_id,
        direction,magnitude,score,percentile,window,evidence_json,fingerprint,run_id,created_at)
        VALUES('A1','2026-11-06','price_return_shock','price','TW_EQ_TAIEX','down',0.04,0.8,0.0,
               '1d','{}','f','r','x')""")
    store.conn.commit()
    store.add_research_finding("F1", "R-CONSUME", "INCONCLUSIVE", {"v": 1}, "f.json")
    orch = ResearchOrchestrator(store)
    t0 = store.conn.execute("SELECT created_at FROM research_v2_findings WHERE finding_id='F1'").fetchone()[0]
    # Same second as the Finding: must still be consumed.
    orch.reopen("R-CONSUME", "manual check")
    spec = orch.next_case()
    assert spec is not None
    fake = types.SimpleNamespace(finding_id="F1", status="INCONCLUSIVE", research_id="R-CONSUME",
                                 learned=[], event_date="2026-11-06",
                                 hypothesis_updates={"H": {"status": "INSUFFICIENT_DATA"}})
    monkeypatch.setattr("goe.research_orchestrator.execute_spec", lambda store, spec: fake)
    orch.run(spec)
    assert orch.next_case() is None
    assert store.open_research_update_count("R-CONSUME") == 0
    assert store.conn.execute("SELECT created_at FROM research_v2_findings WHERE finding_id='F1'").fetchone()[0] == t0
    # A second data update can be queued after the first was processed.
    notify_price_changes(store, {"R-CONSUME": {"TW_EQ_TAIEX": "old"}},
                         {"R-CONSUME": {"TW_EQ_TAIEX": "new"}}, batch=1)
    assert store.open_research_update_count("R-CONSUME") >= 1
    # Same occurrence delivered twice with the same batch is idempotent.
    notify_price_changes(store, {"R-CONSUME": {"TW_EQ_TAIEX": "old"}},
                         {"R-CONSUME": {"TW_EQ_TAIEX": "new"}}, batch=1)
    assert store.open_research_update_count("R-CONSUME") == 1


def test_failed_update_is_not_marked_processed_and_can_recover(tmp_path, monkeypatch):
    import types
    store = Store(str(tmp_path / "t.db"))
    c = {"research_id": "R-FAIL", "research_theme_id": "T", "as_of": "2026-11-13",
         "market": "TW", "asset_class": "equity_index", "instruments": ["TW_EQ_TAIEX"],
         "observed_phenomenon": "price_return_shock down", "detector_id": "price_return_shock",
         "direction": "down", "event_date": "2026-11-06", "priority_tier": "intelligence",
         "research_worthiness": "high", "evidence_readiness": "partial",
         "research_queue": "watch", "competing_hypotheses": []}
    store.upsert_research_candidate(c)
    store.conn.execute("""INSERT INTO anomalies(anomaly_id,as_of,detector,family,instrument_id,
        direction,magnitude,score,percentile,window,evidence_json,fingerprint,run_id,created_at)
        VALUES('A1','2026-11-06','price_return_shock','price','TW_EQ_TAIEX','down',0.04,0.8,0.0,
               '1d','{}','f','r','x')""")
    store.conn.commit()
    store.add_research_finding("F1", "R-FAIL", "INCONCLUSIVE", {}, "f.json")
    orch = ResearchOrchestrator(store)
    orch.reopen("R-FAIL", "trigger")
    spec = orch.next_case()
    assert spec
    def boom(store, spec): raise RuntimeError("controlled failure")
    monkeypatch.setattr("goe.research_orchestrator.execute_spec", boom)
    try:
        orch.run(spec)
    except RuntimeError:
        pass
    row = store.conn.execute("SELECT status FROM research_v2_update_requests WHERE research_id='R-FAIL'").fetchone()
    assert row["status"] == "FAILED"
    assert store.research_workflow_state("R-FAIL") == "BLOCKED"
    orch.retry("R-FAIL")
    pending = store.pending_research_update("R-FAIL")
    assert pending and pending["status"] == "PENDING"


def test_planner_failure_does_not_leave_processing_stuck(tmp_path, monkeypatch):
    import types
    store = Store(str(tmp_path / "t.db"))
    c = {"research_id": "R-PLANFAIL", "research_theme_id": "T", "as_of": "2026-11-13",
         "market": "TW", "asset_class": "equity_index", "instruments": ["TW_EQ_TAIEX"],
         "observed_phenomenon": "price_return_shock down", "detector_id": "price_return_shock",
         "direction": "down", "event_date": "2026-11-06", "priority_tier": "intelligence",
         "research_worthiness": "high", "evidence_readiness": "partial",
         "research_queue": "watch", "competing_hypotheses": []}
    store.upsert_research_candidate(c)
    store.conn.execute("""INSERT INTO anomalies(anomaly_id,as_of,detector,family,instrument_id,
        direction,magnitude,score,percentile,window,evidence_json,fingerprint,run_id,created_at)
        VALUES('A1','2026-11-06','price_return_shock','price','TW_EQ_TAIEX','down',0.04,0.8,0.0,
               '1d','{}','f','r','x')""")
    store.conn.commit()
    store.add_research_finding("F1", "R-PLANFAIL", "INCONCLUSIVE", {}, "f.json")
    orch = ResearchOrchestrator(store)
    orch.reopen("R-PLANFAIL", "plan failure")
    spec = orch.next_case()
    assert spec
    def boom(spec): raise RuntimeError("planner boom")
    monkeypatch.setattr("goe.research_orchestrator.plan_evidence", boom)
    try:
        orch.run(spec)
    except RuntimeError:
        pass
    row = store.conn.execute("SELECT status FROM research_v2_update_requests WHERE research_id='R-PLANFAIL'").fetchone()
    assert row["status"] == "FAILED"
    orch.retry("R-PLANFAIL")
    assert store.pending_research_update("R-PLANFAIL") is not None
    # Successful recovery consumes the request.
    fake = types.SimpleNamespace(finding_id="F1", status="INCONCLUSIVE",
                                 research_id="R-PLANFAIL", learned=[], event_date="2026-11-06",
                                 hypothesis_updates={"H": {"status": "INCONCLUSIVE"}})
    monkeypatch.setattr("goe.research_orchestrator.plan_evidence",
                        lambda spec: types.SimpleNamespace(target_claim="q", to_dict=lambda: {}))
    monkeypatch.setattr("goe.research_orchestrator.execute_spec", lambda store, spec: fake)
    orch.run(spec)
    assert store.open_research_update_count("R-PLANFAIL") == 0
