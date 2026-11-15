"""Research Dossier — human-readable, source-bound research problem package.

A dossier does not invent a conclusion. It separates observed facts, competing
hypotheses, distinct predictions, support/refutation, unknowns, acquisition
plan, falsification, worthiness, readiness, cost, B capability and the next
action. Independent review is left explicitly pending unless a real reviewer ran.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .integration.capabilities import route_candidate

SECTIONS = [
    "Observed Facts", "Why This Matters", "Research Question", "Competing Hypotheses",
    "Different Predictions", "Supporting Evidence", "Contradicting Evidence",
    "Critical Unknowns", "Evidence Acquisition Plan", "Falsification Conditions",
    "Research Worthiness", "Evidence Readiness", "Research Cost", "Next Research Action",
    "B Capability / Handoff", "Result / Open Questions", "Independent Quality Review",
    "Source & Version References",
]


def _dedupe(items: list[dict]) -> list[dict]:
    out, seen = [], set()
    for e in items:
        key = (e.get("claim"), e.get("value"), e.get("source"), e.get("hypothesis_id"))
        if key in seen:
            continue
        seen.add(key); out.append(e)
    return out


def _acquisition_plan(unknowns: list[str]) -> list[str]:
    plans = []
    for u in unknowns:
        text = str(u)
        if "一致预期" in text or "盈利" in text:
            plans.append("接入带 publication_time/vintage 的 consensus CSV；先补历史版本，不能回填")
        elif "OIS" in text or "政策路径" in text:
            plans.append("接入 licensed term-OIS；当前只能使用 policy-path proxy，不得冒充 OIS")
        elif "汇率" in text or "FX" in text:
            plans.append("补充本地汇率序列并执行同期 beta/残差检验")
        elif "库存" in text or "供给" in text:
            plans.append("补充库存/产量/期限结构；不可用价格替代供给数据")
        elif "期权" in text:
            plans.append("取得历史期权隐含分布；否则保留为 unknown")
        elif "资金流" in text or "仓位" in text:
            plans.append("使用 CFTC/ETF 资金流并检查发布日期")
        else:
            plans.append(f"明确数据源、发布日期与可得时点：{text}")
    return plans


def build_dossier(candidate: dict[str, Any], *, artifact_path: str = "",
                  scan_meta: dict[str, Any] | None = None,
                  case_label: str = "") -> dict[str, Any]:
    hyps = candidate.get("competing_hypotheses") or []
    evidence = _dedupe(list(candidate.get("evidence") or []))
    # Availability notes/config flags are not evidence for a hypothesis; only
    # measured/discriminating or statistical-association items count as support.
    supporting = _dedupe([e for h in hyps for e in (h.get("evidence_for") or [])
                          if e.get("discriminating") or e.get("class") == "statistical_association"])
    contradicting = _dedupe([e for h in hyps for e in (h.get("evidence_against") or [])
                             if e.get("class") != "unknown" or e.get("source") == "data_gap"])
    predictions = []
    for h in hyps:
        pred = str(h.get("implications") or "")
        if pred and pred not in predictions:
            predictions.append(pred)
    unknowns = [str(x) for x in (candidate.get("critical_unknowns") or [])]
    b = route_candidate(candidate)
    queue = candidate.get("research_queue") or "archive"
    tier = candidate.get("priority_tier") or "intelligence"
    if queue == "research":
        next_action = ("Prepare B handoff" if candidate.get("handoff_eligibility") == "eligible"
                       else "Retain in A; B capability gap or evidence incomplete")
    elif queue == "watch":
        next_action = "Collect the listed evidence / wait for the stated trigger; do not hand off yet"
    else:
        next_action = "No further research allocation; retain as market intelligence"
    dossier = {
        "dossier_id": "RD-" + str(candidate.get("research_id")),
        "research_id": candidate.get("research_id"),
        "research_theme_id": candidate.get("research_theme_id"),
        "case_label": case_label,
        "decision_as_of": candidate.get("as_of"),
        "market": candidate.get("market"),
        "asset_class": candidate.get("asset_class"),
        "instruments": candidate.get("instruments") or [],
        "sections": {
            "Observed Facts": [
                {"claim": e.get("claim"), "value": e.get("value"), "source": e.get("source"),
                 "available_at": e.get("available_at"), "class": e.get("class")}
                for e in evidence if e.get("class") in ("observed_fact", "statistical_association")],
            "Why This Matters": {
                "materiality": candidate.get("materiality"),
                "decision_relevance": candidate.get("decision_impact"),
                "observed_phenomenon": candidate.get("observed_phenomenon"),
            },
            "Research Question": f"What explains: {candidate.get('observed_phenomenon')}",
            "Competing Hypotheses": hyps,
            "Different Predictions": predictions,
            "Supporting Evidence": supporting,
            "Contradicting Evidence": contradicting,
            "Critical Unknowns": unknowns,
            "Evidence Acquisition Plan": _acquisition_plan(unknowns),
            "Falsification Conditions": candidate.get("falsification_conditions") or [],
            "Research Worthiness": {
                "rating": candidate.get("research_worthiness"),
                "rationale": candidate.get("rationale"),
            },
            "Evidence Readiness": {
                "rating": candidate.get("evidence_readiness"),
                "research_readiness": candidate.get("research_readiness"),
                "measured_note": "Only measured, discriminating evidence counts; availability notes do not.",
            },
            "Research Cost": candidate.get("research_cost") or {},
            "Next Research Action": next_action,
            "B Capability / Handoff": {
                "supported": b.get("supported"), "kind": b.get("kind"), "reason": b.get("reason"),
                "eligibility": candidate.get("handoff_eligibility"),
                "research_queue": queue, "tier": tier,
            },
            "Result / Open Questions": {
                "result": "NOT_EXECUTED" if queue != "research" else "PENDING_B_OR_A_RESEARCH",
                "open_questions": unknowns,
                "learned": "No research result is claimed; unresolved unknowns remain explicit.",
            },
            "Independent Quality Review": {
                "status": "NOT_INDEPENDENTLY_REVIEWED",
                "note": "No human/expert review was performed for this dossier. Do not treat the "
                        "dossier as validated research value.",
            },
            "Source & Version References": {
                "artifact_path": artifact_path,
                "scan_id": (scan_meta or {}).get("scan_id"),
                "config_hash": (scan_meta or {}).get("config_hash"),
                "data_hash": (scan_meta or {}).get("data_hash"),
                "theme_id": candidate.get("research_theme_id"),
                "evidence_count": len(evidence),
                "source_note": "All evidence retains source and available_at; unavailable facts are unknown.",
            },
        },
        "discovery_value": "NOT VALIDATED",
    }
    payload = json.dumps(dossier, ensure_ascii=False, sort_keys=True, default=str)
    dossier["content_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
    return dossier


def render_markdown(dossier: dict[str, Any]) -> str:
    s = dossier["sections"]
    lines = [f"# Research Dossier {dossier['dossier_id']}", "",
             f"- Research ID: `{dossier['research_id']}`",
             f"- Research Theme: `{dossier['research_theme_id']}`",
             f"- Decision as-of: `{dossier['decision_as_of']}`",
             f"- Market / Assets: {dossier['market']} / {', '.join(dossier['instruments'])}",
             f"- Case: {dossier.get('case_label', '')}", ""]
    for i, name in enumerate(SECTIONS, start=1):
        lines += [f"## {i}. {name}", ""]
        val = s.get(name)
        if isinstance(val, list):
            if not val:
                lines.append("_None recorded._")
            for item in val:
                if isinstance(item, dict):
                    label = item.get("label") or item.get("claim") or item.get("test") or item.get("id")
                    extra = item.get("value") or item.get("implications") or item.get("threshold") or ""
                    src = item.get("source", "")
                    avail = item.get("available_at", "")
                    suffix = f" _(source: {src}" + (f", available: {avail}" if avail else "") + ")_" if src else ""
                    lines.append(f"- **{label}**: {extra}" + suffix)
                else:
                    lines.append(f"- {item}")
        elif isinstance(val, dict):
            for k, v in val.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"- **{k}**: `{json.dumps(v, ensure_ascii=False, default=str)[:500]}`")
                else:
                    lines.append(f"- **{k}**: {v}")
        else:
            lines.append(str(val))
        lines.append("")
    lines += ["---", f"Content SHA-256: `{dossier['content_sha256']}`",
              "DISCOVERY VALUE: NOT VALIDATED", ""]
    return "\n".join(lines)


def write_dossier(dossier: dict[str, Any], out_dir: str | Path = "research_dossiers") -> dict[str, str]:
    out = Path(out_dir) / str(dossier["decision_as_of"])
    out.mkdir(parents=True, exist_ok=True)
    stem = str(dossier["research_id"]).replace("/", "_")
    md = out / f"{stem}.md"; js = out / f"{stem}.json"
    md.write_text(render_markdown(dossier), encoding="utf-8")
    js.write_text(json.dumps(dossier, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {"markdown": str(md), "json": str(js)}
