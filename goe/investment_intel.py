"""Evidence-gated Investment Intelligence; never fabricates market expectations."""
from __future__ import annotations

from typing import Any


def analyze(finding: dict[str, Any], candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    tests = finding.get("tests") or {}
    supported = [k for k, v in (finding.get("hypothesis_updates") or {}).items()
                 if v.get("status") == "SUPPORTED_BY_AVAILABLE_EVIDENCE"]
    insufficient = [k for k, v in (finding.get("hypothesis_updates") or {}).items()
                    if v.get("status") == "INSUFFICIENT_DATA"]
    # No implied-rate/consensus/options distribution baseline is supplied by the
    # current data; price moves alone are not market expectations.
    expectation_status = "MARKET_EXPECTATIONS_NOT_ESTABLISHED"
    gap_status = "MISPRICING_NOT_ESTABLISHED"
    return {
        "research_id": finding.get("research_id"),
        "decision_as_of": finding.get("decision_as_of"),
        "event_date": finding.get("event_date"),
        "observed_fact": finding.get("observed"),
        "supported_hypotheses": supported,
        "insufficient_hypotheses": insufficient,
        "market_expectations": {
            "status": expectation_status,
            "reason": "no licensed implied-rate/consensus/options distribution baseline in this run",
        },
        "expectation_gap": {"status": gap_status, "direction": None, "magnitude": None},
        "scenarios": {
            "base": "US/global risk transmission remains the best-supported channel; local/regional channels are not distinguishable",
            "alternative": "Japan/Asia-local factor dominates after new sector/flow evidence",
            "invalidation": "a later independent window fails to reproduce the global lead or a new source shows a local driver",
        },
        "monitoring": [
            "new post-cutoff market data",
            "TOPIX/Asia sector breadth",
            "implied rate/consensus vintages",
            "FX and cross-asset correlations",
        ],
        "decision_relevance": "research priority only; no trade, target price, or mispricing claim",
        "discovery_value": "NOT VALIDATED",
    }
