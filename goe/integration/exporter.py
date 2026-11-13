"""Handoff export: opportunity pipeline -> investment-agent research tasks.

The interchange format is a small, versioned JSON envelope (``HANDOFF_SCHEMA``).
It is intentionally independent of the investment-agent's internal code: the
existing system receives a *research question plus structured context*, not a
patched code path.

Files written to ``exports/``:
  pipeline_<date>.json        full opportunity pipeline for the scan
  research_tasks/RT-*.json    one self-contained research task per opportunity
  research_queue_<date>.json  ordered queue with priority and suggested command
  HANDOFF_SCHEMA.json         machine-readable schema of the envelope (once)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..db import Store

HANDOFF_SCHEMA_VERSION = "1.0"

HANDOFF_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Global Opportunity Engine handoff envelope",
    "version": HANDOFF_SCHEMA_VERSION,
    "type": "object",
    "required": ["schema_version", "engine", "provenance", "opportunity"],
    "properties": {
        "schema_version": {"type": "string", "const": HANDOFF_SCHEMA_VERSION},
        "engine": {
            "type": "object",
            "required": ["name", "version", "scan_id", "as_of", "generated_at"],
            "properties": {
                "name": {"const": "global-opportunity-engine"},
                "version": {"type": "string"},
                "scan_id": {"type": "string"},
                "as_of": {"type": "string", "format": "date"},
                "generated_at": {"type": "string"},
            },
        },
        "provenance": {
            "type": "object",
            "properties": {
                "config_hash": {"type": "string"},
                "data_hash": {"type": "string"},
                "db_path": {"type": "string"},
                "disclaimer": {"type": "string"},
            },
        },
        "opportunity": {
            "type": "object",
            "required": ["opportunity_id", "fingerprint", "status", "score", "title",
                         "instruments", "discovery", "evidence_for", "evidence_against",
                         "open_questions", "invalidation", "research_question"],
            "properties": {
                "opportunity_id": {"type": "string"},
                "fingerprint": {"type": "string"},
                "status": {"enum": ["new", "watch", "deep_research", "low_priority",
                                    "excluded", "expired", "invalidated", "archived"]},
                "score": {"type": "number", "minimum": 0, "maximum": 1},
                "score_breakdown": {"type": "object"},
                "archetype": {"type": "string"},
                "title": {"type": "string"},
                "market": {"type": "string"},
                "asset_class": {"type": "string"},
                "horizon": {"type": "string"},
                "instruments": {"type": "array"},
                "discovery": {"type": "object"},
                "mechanism": {"type": "object"},
                "evidence_for": {"type": "array"},
                "evidence_against": {"type": "array"},
                "catalysts": {"type": "array"},
                "open_questions": {"type": "array"},
                "invalidation": {"type": "string"},
                "data_quality": {"type": "object"},
                "research_question": {"type": "string"},
            },
        },
    },
}


def _json_field(row: dict[str, Any], key: str, default: Any) -> Any:
    raw = row.get(key)
    if raw is None:
        return default
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return default
    return raw


def build_research_question(row: dict[str, Any]) -> str:
    """A self-contained question for the deep-research system.

    It must stand alone: the consumer sees only the question text (``ia_cli
    research-run --question "..."``), so the numbers, evidence and invalidation
    conditions are embedded.
    """
    disc = _json_field(row, "discovery_json", {})
    instruments = _json_field(row, "instruments_json", [])
    mech = _json_field(row, "mechanism_json", {})
    ev_for = _json_field(row, "evidence_for_json", [])
    ev_against = _json_field(row, "evidence_against_json", [])
    oq = _json_field(row, "open_questions_json", [])
    names = "；".join(f"{i.get('name', '')}({i.get('symbol') or i.get('id')})" for i in instruments)
    lines = [
        f"【全球机会引擎研究任务】{row['opportunity_id']}（{row.get('archetype', '')}，"
        f"{row.get('market', '')}，{row.get('asset_class', '')}，研究周期 {row.get('horizon', '')}）",
        f"研究对象：{names}",
        f"现象：{disc.get('what', '')}",
        f"待检验假设：{disc.get('hypothesis', '')}",
        f"初步传导逻辑：{' → '.join(mech.get('chain', []))}（置信度 {mech.get('confidence', 0):.2f}，"
        f"条件：{'；'.join(mech.get('conditions', [])) or '未列明'}）",
        "支持证据：" + ("；".join(f"{e.get('claim')}: {e.get('evidence')}" for e in ev_for[:4]) or "见引擎记录"),
        "反对证据：" + ("；".join(f"{e.get('claim')}: {e.get('evidence')}" for e in ev_against[:3]) or "见引擎记录"),
        f"失效条件：{row.get('invalidation', '')}",
        "需要回答：" + "；".join(oq[:5]),
        "请完成：宏观与政策背景 → 行业/中观结构 → 公司或资产微观证据 → 情景分析 → 估值与赔率 → "
        "明确列出支持与反对证据、关键数据缺口，以及使结论失效的条件。若证据不足，请直接说明，不要补全缺失数据。",
    ]
    return "\n".join(lines)


def opportunity_envelope(store: Store, row: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "engine": {
            "name": "global-opportunity-engine",
            "version": meta.get("engine_version", ""),
            "scan_id": meta.get("scan_id", ""),
            "as_of": meta.get("as_of", ""),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "provenance": {
            "config_hash": meta.get("config_hash", ""),
            "data_hash": meta.get("data_hash", ""),
            "db_path": str(store.path),
            "disclaimer": "Opportunity discovery output for research prioritisation. Not investment advice; "
                          "scores rank research value, not expected return.",
        },
        "opportunity": {
            "opportunity_id": row["opportunity_id"],
            "fingerprint": row["fingerprint"],
            "status": row["status"],
            "score": row["score"],
            "score_breakdown": _json_field(row, "score_json", {}),
            "archetype": row.get("archetype"),
            "title": row.get("title"),
            "market": row.get("market"),
            "asset_class": row.get("asset_class"),
            "horizon": row.get("horizon"),
            "instruments": _json_field(row, "instruments_json", []),
            "discovery": _json_field(row, "discovery_json", {}),
            "mechanism": _json_field(row, "mechanism_json", {}),
            "evidence_for": _json_field(row, "evidence_for_json", []),
            "evidence_against": _json_field(row, "evidence_against_json", []),
            "catalysts": _json_field(row, "catalysts_json", []),
            "open_questions": _json_field(row, "open_questions_json", []),
            "invalidation": row.get("invalidation", ""),
            "data_quality": _json_field(row, "data_quality", {}),
            "research_question": build_research_question(row),
        },
    }


def build_task(store: Store, row: dict[str, Any], meta: dict[str, Any], priority: int) -> dict[str, Any]:
    env = opportunity_envelope(store, row, meta)
    return {
        "task_id": f"RT-{meta.get('as_of', '').replace('-', '')}-{row['opportunity_id'].split('-')[-1]}",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_system": "investment-agent",
        "priority": priority,
        "opportunity_id": row["opportunity_id"],
        "research_question": env["opportunity"]["research_question"],
        "context": env,
        "expected_outputs": [
            "宏观与政策背景", "行业中观结构", "微观/资产层面证据", "情景分析",
            "估值与赔率", "支持与反对证据清单", "数据缺口与失效条件",
        ],
        "callback": {
            "opportunity_id": row["opportunity_id"],
            "fingerprint": row["fingerprint"],
            "store": "goe.db:opportunities",
            "status_map": {"accepted": "deep_research", "deferred": "watch", "rejected": "excluded"},
        },
    }


def export_all(store: Store, records: list[dict[str, Any]], meta: dict[str, Any],
               base_dir: Path) -> dict[str, Any]:
    base_dir.mkdir(parents=True, exist_ok=True)
    as_of = meta.get("as_of", "")
    schema_path = base_dir / "HANDOFF_SCHEMA.json"
    schema_path.write_text(json.dumps(HANDOFF_SCHEMA, ensure_ascii=False, indent=2), encoding="utf-8")

    ordered = sorted(records, key=lambda r: (-(r.get("score") or 0), r["opportunity_id"]))
    envelopes = [opportunity_envelope(store, r, meta) for r in ordered]
    pipeline_path = base_dir / f"pipeline_{as_of}.json"
    pipeline_path.write_text(json.dumps({
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "engine": {"name": "global-opportunity-engine", "version": meta.get("engine_version", ""),
                   "scan_id": meta.get("scan_id", ""), "as_of": as_of,
                   "generated_at": meta.get("generated_at", "")},
        "provenance": {"config_hash": meta.get("config_hash", ""), "data_hash": meta.get("data_hash", "")},
        "summary": {
            "n_opportunities": len(ordered),
            "by_status": {s: sum(1 for r in ordered if r["status"] == s)
                          for s in sorted({r["status"] for r in ordered})},
            "by_archetype": {a: sum(1 for r in ordered if r.get("archetype") == a)
                             for a in sorted({r.get("archetype", "") for r in ordered})},
        },
        "opportunities": envelopes,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    tasks_dir = base_dir / "research_tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task_paths = []
    queue = []
    priority = 1
    for row in ordered:
        if row["status"] not in ("deep_research", "watch", "new", "low_priority"):
            continue
        task = build_task(store, row, meta, priority)
        tpath = tasks_dir / f"{task['task_id']}.json"
        tpath.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
        task_paths.append(str(tpath))
        queue.append({"task_id": task["task_id"], "opportunity_id": row["opportunity_id"],
                      "priority": priority, "status": row["status"], "score": row["score"],
                      "path": str(tpath)})
        store.upsert_research_task({"task_id": task["task_id"], "opportunity_id": row["opportunity_id"],
                                    "created_at": task["created_at"], "target_system": "investment-agent",
                                    "payload": task, "export_path": str(tpath), "status": "exported"})
        priority += 1
    queue_path = base_dir / f"research_queue_{as_of}.json"
    queue_path.write_text(json.dumps({"as_of": as_of, "generated_at": meta.get("generated_at", ""),
                                      "queue": queue}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"pipeline": str(pipeline_path), "queue": str(queue_path),
            "tasks": task_paths, "schema": str(schema_path)}
