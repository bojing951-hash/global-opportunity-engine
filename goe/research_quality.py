"""Descriptive research-quality audit (selection / question / evidence / decision).

This is NOT a valuation and NOT an independent performance label. It records what
can be measured from the structured candidate without inventing human labels:
  * selection: materiality/importance and material change;
  * question structure: distinct hypothesis types and observable tests;
  * evidence: measured discriminating coverage and duplicate-claim reuse;
  * decision value: importance x available test x open gap, as a descriptive flag.

With no independent human labels the only allowed discovery verdict is
``DISCOVERY VALUE: NOT VALIDATED``.
"""
from __future__ import annotations

from typing import Any


def _hyp(h: dict) -> dict:
    return h or {}


def evaluate_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for c in candidates or []:
        hyps = [_hyp(h) for h in c.get("competing_hypotheses") or []]
        open_h = [h for h in hyps if h.get("status") == "open"]
        measured = [h for h in open_h if any(
            e.get("discriminating") and e.get("class") != "unknown"
            for e in h.get("evidence_for") or [])]
        available_tests = [t for t in c.get("falsification_conditions") or []
                           if t.get("data_status") == "available"]
        claims = [e.get("claim") for h in hyps for e in h.get("evidence_for") or []]
        duplicate_claims = len(claims) - len(set(claims))
        types = {h.get("type") for h in hyps}
        mat = c.get("materiality") or {}
        importance = float(mat.get("importance") or 0.0)
        gap = float(mat.get("gap_score") or 0.0)
        question_score = min(1.0, len(types) / 4.0)
        evidence_coverage = len(measured) / len(open_h) if open_h else 0.0
        decision_flag = bool(open_h and available_tests and importance >= 0.5 and gap > 0)
        rows.append({
            "research_id": c.get("research_id"),
            "tier": c.get("priority_tier"),
            "readiness": c.get("evidence_readiness") or c.get("research_readiness"),
            "worthiness": c.get("research_worthiness"),
            "research_queue": c.get("research_queue"),
            "handoff_eligibility": c.get("handoff_eligibility"),
            "importance": importance,
            "gap_score": gap,
            "open_hypotheses": len(open_h),
            "hypothesis_types": len(types),
            "measured_discriminating": len(measured),
            "evidence_coverage": round(evidence_coverage, 3),
            "available_tests": len(available_tests),
            "duplicate_claims": duplicate_claims,
            "question_structure": round(question_score, 3),
            "decision_value_flag": decision_flag,
        })
    n = len(rows)
    return {
        "n_candidates": n,
        "n_research_candidates": sum(1 for r in rows if r["tier"] in ("A", "B", "C")),
        "n_measured_two_or_more": sum(1 for r in rows if r["measured_discriminating"] >= 2),
        "n_decision_value": sum(1 for r in rows if r["decision_value_flag"]),
        "n_watch": sum(1 for r in rows if r["research_queue"] == "watch"),
        "n_research_queue": sum(1 for r in rows if r["research_queue"] == "research"),
        "n_handoff_eligible": sum(1 for r in rows if r["handoff_eligibility"] == "eligible"),
        "mean_evidence_coverage": round(sum(r["evidence_coverage"] for r in rows) / n, 3) if n else 0.0,
        "mean_question_structure": round(sum(r["question_structure"] for r in rows) / n, 3) if n else 0.0,
        "duplicate_claim_total": sum(r["duplicate_claims"] for r in rows),
        "candidates": rows,
        "discovery_value": "NOT VALIDATED",
        "note": "Descriptive audit only; no human/expert labels, no independent future window. "
                "Do not treat these numbers as investment value or as a validated score.",
    }
