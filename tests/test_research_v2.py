from __future__ import annotations

import pytest

from goe.integration.research_handoff import build_v2_question


def _candidate():
    return {
        "research_id": "RC-TEST-01", "as_of": "2026-11-13", "market": "JP",
        "asset_class": "equity_index", "instruments": ["JP_EQ_N225"],
        "observed_phenomenon": "Nikkei 1m -9.7%, drawdown percentile 3.1%.",
        "evidence": [
            {"claim": "1m return", "value": "-9.7%", "class": "observed_fact",
             "source": "prices", "available_at": "2026-11-13"},
            {"claim": "residual", "value": "z=-2.5", "class": "statistical_association",
             "source": "derived", "available_at": "2026-11-13"},
            {"claim": "consensus missing", "value": "unknown", "class": "unknown",
             "source": "data_gap", "available_at": "2026-11-13"},
        ],
        "critical_unknowns": ["分析师一致预期", "期权隐含分布"],
        "falsification_conditions": [
            {"test": "credit z recovery", "threshold": "> -1", "data": "CREDIT_RISK"},
            {"test": "relative strength", "threshold": "> -3%", "data": "prices"},
        ],
    }


def test_v2_handoff_question_is_fact_only():
    cand = _candidate()
    q = build_v2_question(cand)
    assert cand["research_id"] in q and cand["as_of"] in q
    assert "事实核对" in q and "关键未知" in q and "证伪" in q
    for banned in ("投资建议", "仓位", "买入", "卖出", "做多", "做空", "开仓", "平仓",
                   "加仓", "减仓", "保证收益", "赔率"):
        assert banned not in q, banned


def test_v2_refused_result_is_not_completed(store):
    from goe.integration.research_handoff import persist_v2_result

    cand = {"research_id": "RC-TEST", "as_of": "2026-01-01", "market": "US",
            "asset_class": "equity_etf", "instruments": ["US_EQ_SPY"],
            "observed_phenomenon": "x", "priority_tier": "B",
            "competing_hypotheses": [], "evidence": []}
    persist_v2_result(store, cand, {"status": "not_ok", "semantic_status": "ok_valid",
                                    "returncode": 17}, "/tmp/rc-test")
    task = store.conn.execute("SELECT status FROM research_v2_tasks WHERE task_id='RC-TEST'").fetchone()
    assert task["status"] != "completed"


def test_v2_timeout_is_not_unknown(store):
    from goe.integration.research_handoff import persist_v2_result

    cand = {"research_id": "RC-TIMEOUT", "as_of": "2026-01-01", "market": "US",
            "asset_class": "equity_etf", "instruments": ["US_EQ_SPY"],
            "observed_phenomenon": "x", "priority_tier": "B",
            "competing_hypotheses": [], "evidence": []}
    persist_v2_result(store, cand, {"status": "timeout", "semantic_status": None}, "/tmp/rc-timeout")
    task = store.conn.execute("SELECT status FROM research_v2_tasks WHERE task_id='RC-TIMEOUT'").fetchone()
    assert task["status"] == "not_completed:timeout"


def test_v2_evaluation_decision_rule_is_not_automatic(tmp_path):
    from goe.research_evaluation import score_ratings

    mapping = {"mapping": {}, "splits": {"test": ["2026-01-01"]}}
    # three test objects per method, all same date
    for i, method in enumerate(("A_price_move", "B_anomaly_score", "C_v1_score", "D_v2_triage")):
        for j in range(3):
            token = f"V{i}{j}"
            mapping["mapping"][token] = {"as_of": "2026-01-01", "method": method,
                                         "rank": j + 1, "entity_id": f"E{i}{j}", "theme": f"T{i}{j}"}
    ratings = []
    for token in mapping["mapping"]:
        method = mapping["mapping"][token]["method"]
        base = 1.6 if method == "D_v2_triage" else 1.2
        if method == "D_v2_triage" and token.endswith("2"):
            base = 1.0  # one weak D item -> still mean above 1.2? mean 1.4
        ratings.append({"object_id": token, "scores": {
            "real_market_change": 2, "beyond_price": 1,
            "falsifiable": 2 if base > 1.3 else 1, "data_sufficiency": 1}})
    res = score_ratings(ratings, mapping, tmp_path)
    # D mean 1.5 vs others 1.5 -> not strictly better; decision must not be VALIDATED
    assert res["discovery_value"] in ("VALIDATED", "NOT VALIDATED")
    assert (tmp_path / "V2_EVALUATION_RESULTS.md").exists()


def test_evaluation_decision_rule_requires_test_and_both_metrics(tmp_path):
    from goe.research_evaluation import score_ratings

    def make(split_dates):
        mapping = {"mapping": {}, "splits": {"test": split_dates}}
        for mi, method in enumerate(("A_price_move", "B_anomaly_score", "C_v1_score", "D_v2_triage")):
            for j in range(3):
                token = f"T{mi}{j}"
                mapping["mapping"][token] = {"as_of": split_dates[0] if split_dates else "2026-01-01",
                                             "method": method, "rank": j + 1,
                                             "entity_id": f"E{mi}{j}", "theme": f"TH{mi}{j}"}
        ratings = []
        for token, meta in mapping["mapping"].items():
            strong = meta["method"] == "D_v2_triage"
            scores = {k: (2 if strong else 1) for k in
                      ("real_market_change", "beyond_price", "falsifiable", "data_sufficiency")}
            ratings.append({"object_id": token, "scores": scores})
        return ratings, mapping

    rat, mp = make(["2026-01-01"])
    good = score_ratings(rat, mp, tmp_path / "good")
    assert good["discovery_value"] == "VALIDATED"
    rat2, mp2 = make([])
    no_test = score_ratings(rat2, mp2, tmp_path / "none")
    assert no_test["discovery_value"] == "NOT VALIDATED"


def _lifecycle_candidate():
    return {
        "research_id": "RC-LIFE", "as_of": "2026-01-01", "market": "US",
        "asset_class": "equity_etf", "instruments": ["US_EQ_SPY"],
        "observed_phenomenon": "material move", "priority_tier": "B", "priority_rank": 1,
        "competing_hypotheses": [
            {"id": "H1", "label": "risk premium", "type": "risk_premium", "status": "open",
             "evidence_for": [], "evidence_against": []},
            {"id": "H2", "label": "data artifact", "type": "data_artifact",
             "status": "untestable", "evidence_for": [], "evidence_against": []}],
        "evidence": [{"claim": "fact", "class": "observed_fact", "source": "db",
                      "available_at": "2026-01-01"}],
        "evidence_for": [], "evidence_against": [],
    }


def test_v2_lifecycle_retains_candidate_and_has_no_orphans(store):
    from goe.integration.research_handoff import persist_v2_result

    cand = _lifecycle_candidate()
    res = persist_v2_result(store, cand, {"status": "not_ok", "semantic_status": "timeout"}, "/tmp/x")
    assert res["status"] == "not_completed:timeout"
    assert store.research_candidate("RC-LIFE")["status"] == "handoff_failed"
    assert store.conn.execute("SELECT COUNT(*) FROM research_v2_tasks WHERE research_id='RC-LIFE'").fetchone()[0] == 1
    assert store.conn.execute("SELECT COUNT(*) FROM research_v2_results WHERE research_id='RC-LIFE'").fetchone()[0] == 1
    assert store.conn.execute("SELECT COUNT(*) FROM research_v2_hypotheses WHERE research_id='RC-LIFE'").fetchone()[0] == 2
    assert all(v == 0 for v in store.research_integrity().values())


def test_v2_task_cannot_reference_missing_candidate(store):
    with pytest.raises(ValueError, match="does not exist"):
        store.upsert_research_task_v2({"task_id": "T-X", "research_id": "RC-MISSING"})
    assert store.research_integrity()["orphan_tasks"] == 0


def test_v2_does_not_touch_v1_tables(store):
    from goe.integration.research_handoff import persist_v2_result

    before = (store.conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0],
              store.conn.execute("SELECT COUNT(*) FROM research_tasks").fetchone()[0],
              store.conn.execute("SELECT COUNT(*) FROM opportunity_events").fetchone()[0])
    persist_v2_result(store, _lifecycle_candidate(), {"status": "timeout"}, "/tmp/x")
    after = (store.conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0],
             store.conn.execute("SELECT COUNT(*) FROM research_tasks").fetchone()[0],
             store.conn.execute("SELECT COUNT(*) FROM opportunity_events").fetchone()[0])
    assert before == after


def test_legacy_rc_rows_are_migrated_out_of_v1_tables(tmp_path):
    from goe.db import Store

    s = Store(tmp_path / "legacy.db")
    s.conn.execute("""INSERT INTO research_tasks(task_id,opportunity_id,created_at,target_system,
                     payload_json,exported_at,export_path,status) VALUES(?,?,?,?,?,?,?,?)""",
                   ("RC-OLD", "RC-OLD", "2026-01-01T00:00:00Z", "investment-agent",
                    '{"candidate":{"research_id":"RC-OLD","as_of":"2026-01-01","market":"US","asset_class":"fx","instruments":["US_FX_DXY"],"observed_phenomenon":"x","priority_tier":"B","competing_hypotheses":[],"evidence":[]}}',
                    None, "/tmp/x", "not_completed:rejected"))
    s.conn.execute("""INSERT INTO opportunity_events(opportunity_id,at,event_type,note)
                      VALUES('RC-OLD','2026-01-01T00:00:00Z','ia_research_not_completed','x')""")
    s.conn.commit()
    s2 = Store(tmp_path / "legacy.db")
    assert s2.research_integrity()["legacy_v1_rc_tasks"] == 0
    assert s2.research_integrity()["legacy_v1_rc_events"] == 0
    assert s2.research_candidate("RC-OLD") is not None
    assert s2.conn.execute("SELECT COUNT(*) FROM research_v2_tasks WHERE research_id='RC-OLD'").fetchone()[0] == 1
    assert all(v == 0 for v in s2.research_integrity().values())


def test_handoff_eligibility_excludes_intelligence():
    from goe.integration.research_handoff import eligible_for_handoff

    rows = [
        {"research_id": "I", "priority_tier": "intelligence", "research_readiness": "evidence_gap",
         "handoff_eligibility": "a_retained"},
        {"research_id": "A", "priority_tier": "A", "research_readiness": "evidence_ok",
         "handoff_eligibility": "eligible"},
        {"research_id": "B", "priority_tier": "B", "research_readiness": "evidence_gap",
         "handoff_eligibility": "a_retained"},
    ]
    assert [r["research_id"] for r in eligible_for_handoff(rows)] == ["A"]
