"""Handoff exporter: schema conformance, self-contained research questions and
the files written for the investment-agent.

All exports are written under ``tmp_path`` (never the repo ``exports/``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import END_DATE, make_opportunity_row
from goe.integration.exporter import (
    HANDOFF_SCHEMA,
    HANDOFF_SCHEMA_VERSION,
    build_research_question,
    export_all,
    opportunity_envelope,
)

META = {
    "scan_id": "scan-test-1",
    "as_of": END_DATE,
    "engine_version": "0.1.0",
    "config_hash": "c" * 64,
    "data_hash": "d" * 64,
    "generated_at": "2024-12-31T22:00:00Z",
}


def test_envelope_contains_all_required_schema_fields(store):
    row = make_opportunity_row()
    env = opportunity_envelope(store, row, META)

    assert set(HANDOFF_SCHEMA["required"]) <= set(env)
    assert env["schema_version"] == HANDOFF_SCHEMA_VERSION
    assert env["engine"]["name"] == "global-opportunity-engine"
    for key in HANDOFF_SCHEMA["properties"]["engine"]["required"]:
        assert key in env["engine"], key
    assert env["engine"]["scan_id"] == "scan-test-1"
    assert env["engine"]["as_of"] == END_DATE

    provenance = env["provenance"]
    assert provenance["config_hash"] == "c" * 64
    assert provenance["data_hash"] == "d" * 64
    assert provenance["db_path"] == str(store.path)
    assert "not investment advice" in provenance["disclaimer"].lower()

    opp = env["opportunity"]
    for key in HANDOFF_SCHEMA["properties"]["opportunity"]["required"]:
        assert key in opp, key
    assert isinstance(opp["opportunity_id"], str)
    assert isinstance(opp["fingerprint"], str)
    assert isinstance(opp["title"], str)
    assert isinstance(opp["status"], str)
    assert opp["status"] in HANDOFF_SCHEMA["properties"]["opportunity"]["properties"]["status"]["enum"]
    assert isinstance(opp["score"], (int, float)) and 0.0 <= float(opp["score"]) <= 1.0
    assert isinstance(opp["instruments"], list) and opp["instruments"]
    assert isinstance(opp["discovery"], dict) and opp["discovery"]
    assert isinstance(opp["mechanism"], dict)
    assert isinstance(opp["evidence_for"], list) and opp["evidence_for"]
    assert isinstance(opp["evidence_against"], list)
    assert isinstance(opp["open_questions"], list)
    assert isinstance(opp["invalidation"], str) and opp["invalidation"]
    assert isinstance(opp["research_question"], str) and opp["research_question"]
    assert isinstance(opp["score_breakdown"], dict)
    assert opp["data_quality"]["score"] == pytest.approx(0.8)


def test_research_question_is_self_contained(store):
    row = make_opportunity_row()
    question = build_research_question(row)

    # The consumer sees only this text, so every part of the thesis must be in it.
    assert row["opportunity_id"] in question
    assert "黄金价格出现异常下跌" in question          # phenomenon
    assert "若实际利率回落" in question                # hypothesis
    assert "价格已显著回撤" in question                # supporting evidence
    assert "央行购金数据缺失" in question              # opposing evidence
    assert row["invalidation"] in question            # invalidation
    assert "请完成" in question
    assert "数据缺口" in question
    assert "不构成投资建议" in question
    assert "赔率" not in question


def test_export_all_writes_pipeline_queue_tasks_and_schema(store, tmp_path):
    records = [
        make_opportunity_row(opportunity_id="OPP-0001", fingerprint="FP-" + "1" * 16,
                             status="deep_research", score=0.90),
        make_opportunity_row(opportunity_id="OPP-0002", fingerprint="FP-" + "2" * 16,
                             status="watch", score=0.60),
        make_opportunity_row(opportunity_id="OPP-0003", fingerprint="FP-" + "3" * 16,
                             status="low_priority", score=0.40),
        make_opportunity_row(opportunity_id="OPP-0004", fingerprint="FP-" + "4" * 16,
                             status="excluded", score=0.20),
    ]
    base = tmp_path / "exports"
    paths = export_all(store, records, META, base_dir=base)

    assert Path(paths["pipeline"]) == base / f"pipeline_{END_DATE}.json"
    assert Path(paths["queue"]) == base / f"research_queue_{END_DATE}.json"
    assert Path(paths["schema"]) == base / "HANDOFF_SCHEMA.json"
    assert all(Path(p).exists() for p in paths["tasks"])
    assert len(paths["tasks"]) == 3  # excluded records do not get a task
    assert len(list((base / "research_tasks").glob("RT-*.json"))) == 3

    pipeline = json.loads(Path(paths["pipeline"]).read_text(encoding="utf-8"))
    assert pipeline["schema_version"] == HANDOFF_SCHEMA_VERSION
    assert pipeline["summary"]["n_opportunities"] == 4
    assert pipeline["summary"]["by_status"]["excluded"] == 1
    assert len(pipeline["opportunities"]) == 4
    # Ordered by score, highest first.
    assert [o["opportunity"]["score"] for o in pipeline["opportunities"]] == [0.9, 0.6, 0.4, 0.2]

    queue = json.loads(Path(paths["queue"]).read_text(encoding="utf-8"))["queue"]
    assert [entry["priority"] for entry in queue] == [1, 2, 3]
    assert [entry["score"] for entry in queue] == [0.9, 0.6, 0.4]
    assert [entry["opportunity_id"] for entry in queue] == ["OPP-0001", "OPP-0002", "OPP-0003"]

    schema = json.loads(Path(paths["schema"]).read_text(encoding="utf-8"))
    assert schema == HANDOFF_SCHEMA

    task = json.loads(Path(paths["tasks"][0]).read_text(encoding="utf-8"))
    assert task["task_id"].startswith("RT-")
    assert task["target_system"] == "investment-agent"
    assert task["priority"] == 1
    assert task["opportunity_id"] == "OPP-0001"
    assert task["context"]["opportunity"]["research_question"] == task["research_question"]
    assert "宏观与政策背景" in task["expected_outputs"]
    assert task["callback"]["fingerprint"] == "FP-" + "1" * 16


def test_exported_json_is_valid_utf8_chinese(store, tmp_path):
    base = tmp_path / "exports"
    row = make_opportunity_row(opportunity_id="OPP-0001", fingerprint="FP-" + "1" * 16)
    paths = export_all(store, [row], META, base_dir=base)

    # The queue only carries ids/scores/paths (ASCII by design); it must still be
    # valid UTF-8 JSON.
    queue_text = Path(paths["queue"]).read_bytes().decode("utf-8")
    json.loads(queue_text)

    # Pipeline and task payloads carry Chinese content and must be written as
    # UTF-8 (ensure_ascii=False), not \\uXXXX escapes.
    for path in (paths["pipeline"], paths["tasks"][0]):
        raw = Path(path).read_bytes()
        text = raw.decode("utf-8")                # must not raise
        assert any("\u4e00" <= ch <= "\u9fff" for ch in text), path
        assert "黄金" in text
        json.loads(text)                          # still valid JSON

    task = json.loads(Path(paths["tasks"][0]).read_text(encoding="utf-8"))
    assert "请完成" in task["research_question"]
    assert "黄金" in task["context"]["opportunity"]["discovery"]["what"]
