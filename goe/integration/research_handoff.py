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
    out_dir = Path(out_dir).resolve()
    res = adapter.run_task(question, out_dir / str(candidate.get("research_id", "RC")),
                           timeout=timeout)
    res["question"] = question
    return res


def persist_v2_result(store, candidate: dict[str, Any], res: dict[str, Any],
                      target: str | Path) -> dict[str, Any]:
    """Persist the V2 research object lifecycle without touching V1 tables.

    The candidate is always retained. A refused/rejected/timeout run creates a
    task + result + event and marks the candidate handoff_failed; only a genuine
    ok_valid run may mark it research_complete.
    """
    import json
    from datetime import datetime, timezone

    sem = res.get("semantic_status") or res.get("status") or "unknown"
    if sem == "unknown" and res.get("status") == "timeout":
        sem = "timeout"
    run_ok = res.get("status") == "ok" and sem == "ok_valid"
    rid = str(candidate.get("research_id"))
    task_id = rid if rid.startswith("RC-") else f"RC-{rid}"
    store.upsert_research_candidate(candidate, status="handoff_pending")
    store.upsert_research_task_v2({
        "task_id": task_id, "research_id": rid, "target_system": "investment-agent",
        "payload": {"candidate": candidate, "result": res, "target": str(target)},
        "status": "completed" if run_ok else f"not_completed:{sem}",
    })
    store.add_research_result(rid, task_id, sem, run_ok, {"result": res})
    store.add_research_event(rid, "ia_research_run" if run_ok else "ia_research_not_completed",
                             f"V2 handoff: {sem} ({res.get('semantic_reason', '')})",
                             task_id=task_id, payload={"semantic": sem})
    store.set_research_status(rid, "research_complete" if run_ok else "handoff_failed",
                              note=f"V2 handoff {sem}", task_id=task_id)
    return {"task_id": task_id, "status": "completed" if run_ok else f"not_completed:{sem}",
            "semantic_status": sem}


def eligible_for_handoff(rows) -> list:
    """Only evidence_ok research tiers may leave A; intelligence stays local."""
    out = []
    for r in rows or []:
        tier = r.get("priority_tier") if isinstance(r, dict) else getattr(r, "priority_tier", None)
        readiness = (r.get("research_readiness") if isinstance(r, dict)
                     else getattr(r, "research_readiness", None))
        eligible = (r.get("handoff_eligibility") if isinstance(r, dict)
                    else getattr(r, "handoff_eligibility", None))
        if (eligible == "eligible" and tier in ("A", "B", "C")
                and readiness == "evidence_ok"):
            out.append(r)
    return out
