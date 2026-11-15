"""Machine-checkable module contracts.

The markdown contracts in ``contracts/`` are the normative definitions; this
module provides the executable subset used by tests and the release gate.
"""
from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

FEATURE_COLUMNS = ["entity_kind", "entity_id", "asset_class", "region",
                   "feature", "window", "date", "value"]
ANOMALY_REQUIRED = ["anomaly_id", "date", "available_date", "detector", "family",
                    "entity_id", "entity_kind", "direction", "window", "measure",
                    "magnitude", "score", "evidence"]
EVIDENCE_REQUIRED = ["threshold", "formula", "raw", "source", "data_quality"]
EVIDENCE_CLASSES = {"observed_fact", "statistical_association", "causal_hypothesis",
                    "unknown", "judgement_pending"}
HYPOTHESIS_TYPES = {"risk_premium", "fundamental", "positioning_flow", "global_risk",
                    "data_artifact", "policy"}
HYPOTHESIS_STATUS = {"open", "supported", "contradicted", "untestable"}
RESEARCH_REQUIRED = ["research_id", "as_of", "market", "asset_class", "instruments",
                     "observed_phenomenon", "materiality", "competing_hypotheses",
                     "evidence", "critical_unknowns", "falsification_conditions",
                     "required_data", "research_cost", "decision_impact",
                     "priority_tier", "priority_rank", "rationale", "data_quality",
                     "evidence_gaps", "evidence_for", "evidence_against", "evaluation_id", "method",
                     "research_readiness", "research_worthiness", "evidence_readiness",
                     "handoff_eligibility", "research_queue"]
V1_WEIGHTS = {"anomaly_strength", "economic_impact", "expectation_gap",
              "repricing_potential", "catalyst", "timing_window",
              "risk_liquidity", "evidence_quality"}


class ContractError(ValueError):
    pass


def validate_feature_frame(df) -> None:
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise ContractError(f"FeatureSet.long missing columns: {missing}")
    if df.empty:
        return
    if df["value"].isna().all():
        raise ContractError("FeatureSet.long has no values")
    if df.duplicated(["entity_kind", "entity_id", "feature", "window", "date"]).any():
        raise ContractError("FeatureSet.long has duplicate keys")


def validate_anomaly_records(records: Iterable[dict[str, Any]]) -> None:
    for r in records:
        missing = [c for c in ANOMALY_REQUIRED if c not in r]
        if missing:
            raise ContractError(f"anomaly missing fields: {missing}")
        ev = r.get("evidence") or {}
        if not isinstance(ev, dict):
            raise ContractError("anomaly evidence must be a dict")
        miss_ev = [c for c in EVIDENCE_REQUIRED if c not in ev]
        if miss_ev:
            raise ContractError(f"anomaly evidence missing: {miss_ev}")
        if not (0.0 <= float(r["score"]) <= 1.0):
            raise ContractError(f"anomaly score outside [0,1]: {r['score']}")


def validate_research_candidate(c: dict[str, Any]) -> None:
    missing = [k for k in RESEARCH_REQUIRED if k not in c]
    if missing:
        raise ContractError(f"research candidate missing: {missing}")
    hyps = c["competing_hypotheses"]
    is_intel = c.get("priority_tier") == "intelligence"
    minimum = 1 if is_intel else 2
    if not isinstance(hyps, list) or len(hyps) < minimum:
        raise ContractError(f"research candidate needs >={minimum} competing hypotheses")
    for h in hyps:
        for k in ("id", "label", "type", "status", "implications",
                  "evidence_for", "evidence_against"):
            if k not in h:
                raise ContractError(f"hypothesis missing {k}")
        if h["type"] not in HYPOTHESIS_TYPES:
            raise ContractError(f"bad hypothesis type {h['type']}")
        if h["status"] not in HYPOTHESIS_STATUS:
            raise ContractError(f"bad hypothesis status {h['status']}")
    ev = c["evidence"]
    if not isinstance(ev, list) or not ev:
        raise ContractError("research candidate needs evidence")
    for e in ev:
        for k in ("claim", "class", "source", "available_at"):
            if k not in e:
                raise ContractError(f"evidence missing {k}")
        if e["class"] not in EVIDENCE_CLASSES:
            raise ContractError(f"bad evidence class {e['class']}")
    if not is_intel and (not c.get("evidence_for") or not c.get("evidence_against")):
        raise ContractError("research candidate needs evidence_for and evidence_against")
    ids = [h["id"] for h in hyps]
    if len(ids) != len(set(ids)):
        raise ContractError("hypothesis ids must be unique")
    if c.get("method") not in (None, "D_v2_triage"):
        raise ContractError("research candidate method must be D_v2_triage")
    if not str(c.get("evaluation_id") or "").startswith("D:"):
        raise ContractError("evaluation_id must start with D:")
    if float(c["research_cost"]["hours"]) <= 0:
        raise ContractError("research_cost.hours must be positive")
    as_of = pd.Timestamp(c["as_of"])
    for item in list(c["evidence"]) + list(c.get("evidence_for") or []) + list(c.get("evidence_against") or []):
        if not item.get("source"):
            raise ContractError("evidence source is required")
        if item.get("available_at") and pd.Timestamp(item["available_at"]) > as_of:
            raise ContractError("evidence available_at is after as_of")
    if not c["critical_unknowns"]:
        raise ContractError("research candidate needs critical_unknowns")
    if not c["falsification_conditions"]:
        raise ContractError("research candidate needs falsification conditions")
    hyp_ids = {h["id"] for h in hyps}
    if not is_intel:
        if len(c["falsification_conditions"]) < 2:
            raise ContractError("research candidate needs >=2 falsification conditions")
        if len({f.get("hypothesis_id") for f in c["falsification_conditions"]}) < 2:
            raise ContractError("falsification tests must discriminate >=2 hypotheses")
    for f in c["falsification_conditions"]:
        if not isinstance(f, dict) or not all(k in f for k in ("test", "threshold", "data", "hypothesis_id")):
            raise ContractError("falsification condition must have test/threshold/data/hypothesis_id")
        if f["hypothesis_id"] not in hyp_ids:
            raise ContractError("falsification points to unknown hypothesis")
    for k in ("hours", "data_access"):
        if k not in c["research_cost"]:
            raise ContractError(f"research_cost missing {k}")
    if not {"if_true", "if_false"} <= set(c["decision_impact"]):
        raise ContractError("decision_impact needs if_true/if_false")
    if c["priority_tier"] not in {"A", "B", "C", "intelligence"}:
        raise ContractError("priority_tier must be A/B/C/intelligence")
    if c["research_worthiness"] not in {"high", "medium", "low"}:
        raise ContractError("bad research_worthiness")
    if c["evidence_readiness"] not in {"ready", "partial", "missing"}:
        raise ContractError("bad evidence_readiness")
    if c["research_queue"] not in {"research", "watch", "archive"}:
        raise ContractError("bad research_queue")
    if c["handoff_eligibility"] not in {"eligible", "a_retained"}:
        raise ContractError("bad handoff_eligibility")
    if c["handoff_eligibility"] == "eligible" and (
            c["priority_tier"] == "intelligence" or c["evidence_readiness"] != "ready"):
        raise ContractError("handoff eligible requires research tier + evidence ready")
    if c["priority_tier"] != "intelligence":
        discriminating = sum(
            1 for h in hyps if h.get("status") == "open" and any(
                e.get("discriminating") and e.get("class") != "unknown"
                for e in h.get("evidence_for", [])))
        if c.get("research_readiness") != "evidence_ok" or discriminating < 2:
            raise ContractError("research tier requires >=2 hypotheses with discriminating evidence")


def validate_v1_weights(weights: dict[str, float]) -> None:
    if set(weights) != V1_WEIGHTS:
        raise ContractError(f"V1 weights keys changed: {set(weights) ^ V1_WEIGHTS}")
    total = sum(float(v) for v in weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ContractError(f"V1 weights must sum to 1.0, got {total}")


def validate_handoff_result(res: dict[str, Any]) -> None:
    sem = res.get("semantic_status")
    status = res.get("status")
    valid = {"ok_valid", "refused", "rejected", "insufficient_data", "partial", "unknown"}
    if sem is not None and sem not in valid:
        raise ContractError(f"unknown semantic status {sem}")
    if status == "ok" and sem != "ok_valid":
        raise ContractError("handoff status=ok requires semantic ok_valid")
    if status == "ok" and res.get("returncode") not in (0, None):
        raise ContractError("handoff status=ok requires rc=0")
