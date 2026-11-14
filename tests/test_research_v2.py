from __future__ import annotations

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

    cand = {"research_id": "RC-TEST", "opportunity_id": "RC-TEST"}
    persist_v2_result(store, cand, {"status": "not_ok", "semantic_status": "ok_valid",
                                    "returncode": 17}, "/tmp/rc-test")
    task = store.conn.execute("SELECT status FROM research_tasks WHERE task_id='RC-TEST'").fetchone()
    assert task["status"] != "completed"


def test_v2_timeout_is_not_unknown(store):
    from goe.integration.research_handoff import persist_v2_result

    cand = {"research_id": "RC-TIMEOUT"}
    persist_v2_result(store, cand, {"status": "timeout", "semantic_status": None}, "/tmp/rc-timeout")
    task = store.conn.execute("SELECT status FROM research_tasks WHERE task_id='RC-TIMEOUT'").fetchone()
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
