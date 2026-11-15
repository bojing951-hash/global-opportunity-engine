"""B capability router — only route factual research B actually supports.

B is a global-macro fact/relationship workbench (macro overview, yield curve,
rates, FX levels/trends, correlations, archived views). It is not a general
equity/sector/commodity valuation or mispricing engine. This router never
modifies B; unsupported tasks stay in A as research dossiers/evidence plans.
"""
from __future__ import annotations

from typing import Any


def route_candidate(candidate: dict[str, Any] | Any) -> dict[str, Any]:
    get = (lambda k, d=None: candidate.get(k, d)) if isinstance(candidate, dict) else (
        lambda k, d=None: getattr(candidate, k, d))
    instruments = [str(x) for x in (get("instruments") or [])]
    asset = str(get("asset_class") or "")
    market = str(get("market") or "")
    joined = " ".join(instruments)
    # Asset class wins over instrument-name heuristics (an equity portfolio can
    # contain a UST proxy and must not become a rates handoff).
    if asset in ("equity_index", "equity_etf", "sector_equity", "commodity", "crypto", "volatility"):
        return {"supported": False, "kind": "deep_asset_research_unsupported",
                "reason": ("B is a macro fact workbench, not a general equity/sector/commodity "
                           "valuation or mispricing engine; keep in A"),
                "B": "investment-agent"}
    if asset in ("fx",) or any(x.startswith("GX_FX") or x.startswith("US_FX") for x in instruments):
        return {"supported": True, "kind": "fx_fact",
                "reason": "B exposes FX level/trend and macro facts", "B": "investment-agent"}
    if asset in ("fixed_income", "credit") or "UST" in joined or "JGB" in joined:
        return {"supported": True, "kind": "rates_fact",
                "reason": "B exposes yield levels, curve and macro facts", "B": "investment-agent"}
    return {"supported": False, "kind": "unknown_asset_class",
            "reason": f"no B capability mapping for {asset!r}", "B": "investment-agent"}


def handoff_eligibility(candidate: dict[str, Any] | Any, *, tier: str,
                        evidence_readiness: str) -> str:
    if tier not in ("A", "B", "C") or evidence_readiness != "ready":
        return "a_retained"
    return "eligible" if route_candidate(candidate).get("supported") else "capability_gap"
