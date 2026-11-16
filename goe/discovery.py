"""Research Opportunity Qualification: separate anomaly from research opportunity."""
from __future__ import annotations

from typing import Any


def _artifact(c: dict[str, Any]) -> bool:
    m = c.get("materiality") or {}
    dq = (c.get("data_quality") or {})
    text = str(c.get("observed_phenomenon") or "").lower()
    return bool(m.get("near_month_end") or m.get("is_continuous_futures")
                or dq.get("artifact") or "roll" in text or "换月" in text)


def _distinct(hs: list[dict[str, Any]]) -> tuple[int, bool]:
    preds = []
    for h in hs:
        p = str(h.get("implications") or h.get("label") or "").strip()
        if p and p not in preds:
            preds.append(p)
    return len(preds), len(preds) >= 2


def qualify(c: dict[str, Any]) -> dict[str, Any]:
    m = c.get("materiality") or {}
    gap = float(m.get("gap_score") or 0.0)
    worth = str(c.get("research_worthiness") or "low")
    ready = str(c.get("evidence_readiness") or "missing")
    n_preds, distinct = _distinct(c.get("competing_hypotheses") or [])
    if _artifact(c):
        cls = "DATA_ARTIFACT"
    elif gap <= 0.05 or worth == "low" and ready != "ready":
        cls = "INTELLIGENCE_ONLY"
    elif worth in ("high", "medium") and ready == "ready" and distinct:
        cls = "RESEARCH_READY"
    elif worth in ("high", "medium"):
        cls = "EVIDENCE_TO_COLLECT"
    else:
        cls = "INTELLIGENCE_ONLY"
    reasons = {
        "DATA_ARTIFACT": "possible roll/split/stale or month-end construction issue; no economic claim",
        "INTELLIGENCE_ONLY": "materiality/decision relevance or explanatory gap too small for research",
        "RESEARCH_READY": "material gap, two distinct predictions, evidence ready",
        "EVIDENCE_TO_COLLECT": "worth researching, but evidence readiness incomplete",
    }
    return {"research_id": c.get("research_id"), "asset": (c.get("instruments") or [None])[0],
            "materiality": m.get("importance"), "explanatory_gap": gap,
            "distinct_predictions": n_preds, "distinct_ok": distinct,
            "research_worthiness": worth, "evidence_readiness": ready,
            "decision_relevance": c.get("decision_impact"),
            "research_queue": c.get("research_queue"),
            "classification": cls, "reason": reasons[cls],
            "next_best_evidence": c.get("next_best_evidence") or (
                "collect missing evidence before promoting" if cls == "EVIDENCE_TO_COLLECT" else
                "none; retain as intelligence" if cls == "INTELLIGENCE_ONLY" else
                "verify raw contract/roll metadata" if cls == "DATA_ARTIFACT" else
                "execute selected test")}
