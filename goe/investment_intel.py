"""Evidence-gated Investment Intelligence; never fabricates market expectations."""
from __future__ import annotations

from typing import Any


def analyze(finding: dict[str, Any], candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    tests = finding.get("tests") or {}
    updates = finding.get("hypothesis_updates") or {}
    supported = [k for k, v in updates.items()
                 if v.get("status") == "SUPPORTED_BY_AVAILABLE_EVIDENCE"]
    insufficient = [k for k, v in updates.items()
                    if v.get("status") == "INSUFFICIENT_DATA"]
    unresolved = [k for k, v in updates.items()
                  if v.get("status") in ("INCONCLUSIVE", "WEAKENED_BY_EVIDENCE")]
    observed = finding.get("observed") or {}
    asset = next(iter(observed.keys()), "asset")
    if "QQQ" in asset:
        monitoring = ["US 2Y/10Y decomposition", "QQQ vs SPY breadth", "implied rates/options distribution", "post-event reversal"]
    elif "KOSPI" in asset:
        monitoring = ["Korea sector/foreign flow", "USDKRW", "US 2Y/10Y", "post-event reversal"]
    elif "TAIEX" in asset:
        monitoring = ["Taiwan sector/semiconductor breadth", "USDCNY/TWD", "US/Asia risk", "post-event reversal"]
    else:
        monitoring = ["new post-cutoff market data", "sector/breadth evidence", "implied rate/consensus vintages"]
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
        "asset": asset,
        "unresolved_hypotheses": unresolved,
        "scenarios": {
            "base": f"Best-supported channels: {', '.join(supported) or 'none'}; unresolved: {', '.join(unresolved) or 'none'}",
            "alternative": "A competing mechanism remains possible where hypotheses are WEAKENED/INCONCLUSIVE; see hypothesis updates",
            "invalidation": "new independent-window evidence fails to reproduce the supported channel or identifies a specific omitted driver",
        },
        "monitoring": monitoring,
        "decision_relevance": "research priority only; no trade, target price, or mispricing claim",
        "discovery_value": "NOT VALIDATED",
    }
