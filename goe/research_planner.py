"""Evidence Planner: choose the next discriminating, actually available evidence."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from .research_engine import ResearchSpec


@dataclass
class EvidenceTask:
    research_id: str
    hypothesis_ids: list[str]
    target_claim: str
    required_data: list[str]
    source: str
    observation_window: str
    point_in_time_cutoff: str
    discriminating_predictions: dict[str, str]
    method: str
    estimated_cost: str
    availability_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan(spec: ResearchSpec) -> EvidenceTask:
    """Use already-stored daily cross-asset data first; mark unavailable gaps explicitly."""
    ids = list(spec.hypothesis_ids.values()) or [h[0] for h in spec.hypotheses]
    if spec.case_kind == "equity_event":
        required = ["same-day regional equity returns", "prior-US-session global/VIX",
                    "prior-session FX", "sector/constituent breadth"]
        pred = {"local/regional": "same-sign co-move",
                "global": "prior US down + VIX up",
                "fx": "prior FX move explains a material share"}
        method = "event_cross_section + historical_percentile"
        avail = "available for market/global series; sector breadth unavailable"
    elif spec.case_kind == "fx_level":
        required = ["cross FX returns", "US duration proxy", "risk/VIX", "2Y/10Y decomposition"]
        pred = {"rate": "duration down + USD up", "risk": "SPY down + VIX up",
                "broad": "EUR down + USDJPY up"}
        method = "fx_rate_risk_cross_section + percentile"
        avail = "available for proxies; 2Y/10Y decomposition unavailable"
    else:
        required = ["DXY", "gold", "duration proxy", "risk/VIX", "inventory/supply"]
        pred = {"dollar": "DXY up + commodity down", "real_rate": "duration down + commodity down",
                "risk": "SPY down + VIX up", "supply": "inventory shock precedes price"}
        method = "commodity_cross_section + percentile"
        avail = "available for proxies; inventory unavailable"
    return EvidenceTask(
        research_id=spec.research_id, hypothesis_ids=ids,
        target_claim=spec.question, required_data=required, source="GOE prices DB",
        observation_window="event day + trailing 252 sessions",
        point_in_time_cutoff=spec.as_of,
        discriminating_predictions=pred, method=method,
        estimated_cost="low (already stored)" if "available" in avail else "medium",
        availability_status=avail)
