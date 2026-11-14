"""V2 A→B handoff: fact-only research brief for the existing investment-agent.

B's current public surface is a grounded factual research runner. It is not a
general investment-advice engine and rejects asset-specific/advice questions as
`out_of_scope`/`unmapped`. A therefore sends only observable facts, critical
unknowns and falsification tests, never a recommendation or a claim of mispricing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .ia_adapter import IAAdapter

_BANNED = ("投资建议", "仓位", "买入", "卖出", "做多", "做空", "开仓", "平仓",
           "加仓", "减仓", "保证收益", "赔率")


def _clean(text: str) -> str:
    text = str(text)
    for bad in _BANNED:
        text = text.replace(bad, "净头寸" if bad == "仓位" else "研究判断")
    return text


def build_v2_question(candidate: dict[str, Any]) -> str:
    """Self-contained factual brief; includes unknowns/falsification tests."""
    instruments = candidate.get("instruments") or []
    facts = []
    for e in candidate.get("evidence", [])[:6]:
        if e.get("class") in ("observed_fact", "statistical_association", "unknown"):
            facts.append(f"- [{e.get('class')}] {e.get('claim')}: {e.get('value')} "
                         f"（来源 {e.get('source')}，可用 {e.get('available_at')}）")
    tests = []
    for f in candidate.get("falsification_conditions", [])[:4]:
        tests.append(f"- 检验 {f.get('test')}，阈值 {f.get('threshold')}（数据 {f.get('data')}）")
    unknowns = candidate.get("critical_unknowns") or []
    lines = [
        f"【研究事实核对】{candidate.get('research_id')}；as_of {candidate.get('as_of')}",
        f"研究对象：{', '.join(str(i) for i in instruments)}（{candidate.get('market')} / "
        f"{candidate.get('asset_class')}）",
        f"已观察现象：{candidate.get('observed_phenomenon')}",
        "可核验事实：", *facts,
        "仍需补充的关键未知：" + "；".join(str(u) for u in unknowns[:5]),
        "可证伪检验：", *tests,
        "任务性质：仅做事实核对、证据分类（事实/关联/假设/未知）与数据缺口说明；"
        "不提供研究结论或交易指令。证据不足请直接说明，不要补全缺失数据。",
    ]
    return _clean("\n".join(lines))


def handoff_v2(adapter: IAAdapter, candidate: dict[str, Any], out_dir: str | Path,
               timeout: int = 300) -> dict[str, Any]:
    question = build_v2_question(candidate)
    res = adapter.run_task(question, Path(out_dir) / str(candidate.get("research_id", "RC")),
                           timeout=timeout)
    res["question"] = question
    return res


def persist_v2_result(store, candidate: dict[str, Any], res: dict[str, Any],
                      target: str | Path) -> None:
    """Persist the handoff without pretending a refused/partial run is success."""
    import json
    from datetime import datetime, timezone

    sem = res.get("semantic_status") or res.get("status") or "unknown"
    if sem == "unknown" and res.get("status") == "timeout":
        sem = "timeout"
    run_ok = res.get("status") == "ok" and sem == "ok_valid"
    rid = str(candidate.get("research_id"))
    task_id = rid if rid.startswith("RC-") else f"RC-{rid}"
    store.add_opportunity_event(rid, "ia_research_run" if run_ok else "ia_research_not_completed",
                                None, None,
                                f"V2 handoff: {sem} ({res.get('semantic_reason', '')})")
    store.upsert_research_task({
        "task_id": task_id, "opportunity_id": rid,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_system": "investment-agent",
        "payload": {"candidate": candidate, "result": res},
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "export_path": str(target),
        "status": "completed" if run_ok else f"not_completed:{sem}",
    })
