"""Autonomous research orchestrator: select, execute, persist, decide next."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .db import Store
from .research_engine import ResearchSpec, execute_spec, spec_for_asset
from .research_planner import plan as plan_evidence
from .research_contract import EventNotResolved, resolve_event
from .research_identity import research_theme_id

STATES = ("DETECTED", "PLANNED", "EVIDENCE_PENDING", "EVIDENCE_ACQUIRED",
          "TESTING", "EVALUATED", "REVIEW_PENDING", "COMPLETED", "INCONCLUSIVE",
          "BLOCKED", "ARCHIVED")


def _candidate(spec: ResearchSpec, hypotheses: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "research_id": spec.research_id, "research_theme_id": spec.research_theme_id,
        "as_of": spec.as_of, "market": spec.market, "asset_class": spec.asset_class,
        "instruments": [spec.asset], "observed_phenomenon": spec.question,
        "priority_tier": "intelligence", "research_worthiness": "medium",
        "evidence_readiness": "partial", "research_queue": "watch",
        "handoff_eligibility": "a_retained", "competing_hypotheses": hypotheses,
        "evidence": [],
    }


class ResearchOrchestrator:
    def __init__(self, store: Store):
        self.store = store

    def register(self, spec: ResearchSpec) -> None:
        hyps = [{"id": k, **v} for k, v in spec.hypotheses]
        self.store.upsert_research_candidate(_candidate(spec, hyps))
        if self.store.research_workflow_state(spec.research_id) is None:
            self.store.set_research_workflow_state(spec.research_id, "PLANNED")
        self.store.add_research_event(spec.research_id, "research:planned", spec.question)

    def retry(self, research_id: str) -> None:
        if self.store.research_workflow_state(research_id) == "BLOCKED":
            self.store.set_research_workflow_state(research_id, "PLANNED")
            self.store.add_research_event(research_id, "research:retry", "manual/unblocked retry")

    def run(self, spec: ResearchSpec) -> Any:
        self.store.set_research_workflow_state(spec.research_id, "EVIDENCE_PENDING")
        task = plan_evidence(spec)
        self.store.add_research_event(spec.research_id, "research:evidence_plan",
                                      task.target_claim, payload=task.to_dict())
        try:
            self.store.set_research_workflow_state(spec.research_id, "TESTING")
            finding = execute_spec(self.store, spec)
        except Exception:
            self.store.set_research_workflow_state(spec.research_id, "BLOCKED")
            raise
        self.store.set_research_workflow_state(spec.research_id, "INCONCLUSIVE"
                                                if finding.status == "INCONCLUSIVE" else "COMPLETED")
        action = ("ACQUIRE_MORE_EVIDENCE" if any(
                    str(v.get("status")) == "INSUFFICIENT_DATA"
                    for v in finding.hypothesis_updates.values())
                  else ("STOP_LOW_VALUE_RESEARCH" if finding.status == "INCONCLUSIVE"
                        else "COMPLETE_RESEARCH"))
        self.store.add_research_event(spec.research_id, "research:evaluated", finding.status,
                                      payload={"next_action": action})
        return finding

    def next_case(self) -> ResearchSpec | None:
        """Select from the real candidate queue; never from a hardcoded case list."""
        rows = self.store.conn.execute(
            """SELECT c.research_id,c.payload_json,c.status
               FROM research_v2_candidates c
               WHERE NOT EXISTS (SELECT 1 FROM research_v2_findings f
                                 WHERE f.research_id=c.research_id)
               ORDER BY c.research_id""").fetchall()
        ranked = []
        for r in rows:
            c = json.loads(r["payload_json"] or "{}")
            if c.get("research_queue") not in ("watch", "research"):
                continue
            # The equity template's lead/lag peers are calibrated for non-US events;
            # a US-event template is not yet registered, so do not misapply it.
            if (c.get("asset_class") in ("equity_index", "equity_etf", "sector_equity")
                    and c.get("market") == "US"):
                continue
            if c.get("research_worthiness") not in ("high", "medium"):
                continue
            state = self.store.research_workflow_state(r["research_id"])
            if state in ("BLOCKED", "COMPLETED", "WAITING_FOR_DATA"):
                continue
            score = {"high": 2, "medium": 1}.get(c.get("research_worthiness"), 0)
            score += {"ready": 2, "partial": 1}.get(c.get("evidence_readiness"), 0)
            ranked.append((score, r["research_id"], c))
        if not ranked:
            return None
        ranked.sort(key=lambda x: (-x[0], x[1]))
        for _, rid, c in ranked:
            try:
                spec = self._spec_from_candidate(c)
            except EventNotResolved as exc:
                self.store.set_research_workflow_state(rid, "WAITING_FOR_DATA")
                self.store.add_research_event(rid, "research:event_not_resolved", str(exc))
                continue  # one unresolved high-priority task must not block the queue
            except Exception as exc:  # identity conflict / malformed contract
                self.store.set_research_workflow_state(rid, "BLOCKED")
                self.store.add_research_event(rid, "research:blocked", str(exc))
                continue
            self.register(spec)
            return spec
        return None

    def _spec_from_candidate(self, c: dict[str, Any]) -> ResearchSpec:
        asset = str((c.get("instruments") or ["unknown"])[0])
        ac = str(c.get("asset_class"))
        if ac in ("equity_index", "equity_etf", "sector_equity"):
            # Build peers dynamically and never let the event asset be a peer.
            pool = ["HK_EQ_HSI", "CN_EQ_CSI300", "JP_EQ_N225", "TW_EQ_TAIEX", "KR_EQ_KOSPI"]
            pool = [x for x in pool if x != asset]
            local = next((x for x in pool if x in ("HK_EQ_HSI", "CN_EQ_CSI300")), pool[0])
            rest = [x for x in pool if x != local]
            regional_a = rest[0]
            regional_b = rest[1] if len(rest) > 1 else rest[0]
            fx_asset = "GX_FX_USDKRW" if asset == "KR_EQ_KOSPI" else "CN_FX_USDCNY"
            peers = {local: ("local", "same_day"),
                     regional_a: ("regional A", "same_day"),
                     regional_b: ("regional B", "same_day"),
                     "US_EQ_SPY": ("US broad", "prior_us_session"),
                     "US_EQ_QQQ": ("US growth", "prior_us_session"),
                     "US_VOL_VIX": ("VIX", "prior_us_session"),
                     fx_asset: ("FX", "prior_us_session")}
            roles = {"local": local, "regional_tw": regional_a,
                     "regional_kr": regional_b, "global_equity": "US_EQ_SPY",
                     "global_growth": "US_EQ_QQQ", "global_vol": "US_VOL_VIX",
                     "fx": fx_asset}
            kind = "equity_event"
        elif ac == "fx":
            peers = {"GX_FX_EURUSD": ("EURUSD", "same_day"),
                     "GX_FX_USDJPY": ("USDJPY", "same_day"),
                     "US_EQ_SPY": ("SPY", "same_day"), "US_VOL_VIX": ("VIX", "same_day"),
                     "US_FI_IEF": ("IEF", "same_day")}
            roles = {"cross1": "GX_FX_EURUSD", "cross2": "GX_FX_USDJPY",
                     "risk": "US_EQ_SPY", "vol": "US_VOL_VIX", "rates": "US_FI_IEF"}
            kind = "fx_level"
        else:
            peers = {"US_FX_DXY": ("DXY", "same_day"), "CM_MET_GC": ("Gold", "same_day"),
                     "US_FI_IEF": ("IEF", "same_day"), "US_EQ_SPY": ("SPY", "same_day"),
                     "US_VOL_VIX": ("VIX", "same_day")}
            roles = {"dollar": "US_FX_DXY", "gold": "CM_MET_GC", "rates": "US_FI_IEF",
                     "risk": "US_EQ_SPY", "vol": "US_VOL_VIX"}
            kind = "commodity_event"
        hyps = []
        hmap = {}
        for h in c.get("competing_hypotheses") or []:
            hid = str(h.get("id")); key = hid.rsplit("-", 1)[-1].lower()
            hyps.append((hid, {"label": h.get("label", hid), "type": h.get("type", "research")}))
            hmap[key] = hid
        if not hyps:
            hyps = [("H-UNKNOWN", {"label": "unresolved", "type": "research"})]
            hmap["unknown"] = "H-UNKNOWN"
        contract = resolve_event(c, self.store.conn)
        event_override = contract.event_end
        return ResearchSpec(
            event_override=event_override,
            research_id=str(c["research_id"]),
            research_theme_id=str(c.get("research_theme_id") or research_theme_id(
                instrument_id=asset, detector="dynamic", direction=kind, window="event")),
            as_of=str(c.get("as_of")), asset=asset, market=str(c.get("market") or ""),
            asset_class=ac, question=str(c.get("observed_phenomenon") or "unexplained move"),
            case_kind=kind, peers=peers, hypotheses=hyps, roles=roles,
            event_contract=contract.to_dict(),
            hypothesis_ids={"local": hmap.get("local", "H-EQ-LOCAL"),
                            "global": hmap.get("global", "H-EQ-GLOBAL"),
                            "fx": hmap.get("fx", "H-EQ-FX"),
                            "policy": hmap.get("policy", "H-EQ-POLICY"),
                            "fund": hmap.get("fund", "H-EQ-FUND"),
                            "regional": hmap.get("regional", "H-EQ-REGIONAL"),
                            "rates": hmap.get("rates", "H-FX-RATES"),
                            "risk": hmap.get("risk", "H-FX-RISK"),
                            "broad": hmap.get("broad", "H-FX-BROAD"),
                            "artifact": hmap.get("art", "H-FX-DATA"),
                            "dollar": hmap.get("dollar", "H-CMD-DOLLAR"),
                            "supply": hmap.get("supply", "H-CMD-SUPPLY")})

    def status(self) -> list[dict[str, Any]]:
        rows = self.store.conn.execute(
            """SELECT c.research_id,c.asset_class,c.status,
                      (SELECT state FROM research_v2_workflow w WHERE w.research_id=c.research_id) workflow,
                      (SELECT COUNT(*) FROM research_v2_findings f WHERE f.research_id=c.research_id) findings,
                      (SELECT status FROM research_v2_findings f WHERE f.research_id=c.research_id
                       ORDER BY created_at DESC LIMIT 1) latest_finding
               FROM research_v2_candidates c ORDER BY c.research_id""").fetchall()
        return [dict(r) for r in rows]


def case_nikkei(as_of: str = "2026-11-13") -> ResearchSpec:
    return spec_for_asset(
        asset="JP_EQ_N225", market="JP", asset_class="equity_index", as_of=as_of,
        question="What explains the N225 2026-11-06 selloff: Japan-local, regional North Asia, US/global, JPY, policy, or fundamentals?",
        peers={"JP_EQ_TOPIX": ("TOPIX", "same_day"), "TW_EQ_TAIEX": ("TAIEX", "same_day"),
               "KR_EQ_KOSPI": ("KOSPI", "same_day"), "US_EQ_SPY": ("SPY", "prior_us_session"),
               "US_EQ_QQQ": ("QQQ", "prior_us_session"), "US_VOL_VIX": ("VIX", "prior_us_session"),
               "GX_FX_USDJPY": ("USDJPY", "prior_us_session")},
        hypotheses=[("H-EQJP-LOCAL", {"label": "Japan local", "type": "local_market"}),
                    ("H-EQJP-GLOBAL", {"label": "US/global risk", "type": "global_risk"}),
                    ("H-EQJP-FX", {"label": "JPY", "type": "fx"}),
                    ("H-EQJP-POLICY", {"label": "Policy", "type": "policy"}),
                    ("H-EQJP-FUND", {"label": "Fundamentals", "type": "fundamental"}),
                    ("H-EQJP-ASIA-REGIONAL", {"label": "North Asia", "type": "regional_asia"})],
        case_kind="equity_event", detector="drawdown_extreme", direction="deep_drawdown",
        event_override="2026-11-06",
        roles={"local": "JP_EQ_TOPIX", "regional_tw": "TW_EQ_TAIEX", "regional_kr": "KR_EQ_KOSPI",
               "global_equity": "US_EQ_SPY", "global_growth": "US_EQ_QQQ",
               "global_vol": "US_VOL_VIX", "fx": "GX_FX_USDJPY"},
        hypothesis_ids={"local": "H-EQJP-LOCAL", "global": "H-EQJP-GLOBAL", "fx": "H-EQJP-FX",
                        "policy": "H-EQJP-POLICY", "fund": "H-EQJP-FUND", "regional": "H-EQJP-ASIA-REGIONAL"})


def case_dxy(as_of: str = "2026-11-13") -> ResearchSpec:
    return spec_for_asset(
        asset="US_FX_DXY", market="US", asset_class="fx", as_of=as_of,
        question="What explains the US dollar index near its 5y high on 2026-11-11: rate differential, risk-off, broad USD, or data artifact?",
        peers={"GX_FX_EURUSD": ("EURUSD", "same_day"), "GX_FX_USDJPY": ("USDJPY", "same_day"),
               "US_EQ_SPY": ("SPY", "same_day"), "US_VOL_VIX": ("VIX", "same_day"),
               "US_FI_IEF": ("IEF duration", "same_day")},
        hypotheses=[("H-FX-RATES", {"label": "US rate differential", "type": "rates"}),
                    ("H-FX-RISK", {"label": "Global risk-off/safe haven", "type": "risk"}),
                    ("H-FX-BROAD", {"label": "Broad USD move", "type": "cross_rate"}),
                    ("H-FX-DATA", {"label": "Data artifact", "type": "data_artifact"})],
        case_kind="fx_level", detector="dxy_high", direction="near_high",
        event_override="2026-11-11",
        roles={"cross1": "GX_FX_EURUSD", "cross2": "GX_FX_USDJPY", "risk": "US_EQ_SPY",
               "vol": "US_VOL_VIX", "rates": "US_FI_IEF"},
        hypothesis_ids={"rates": "H-FX-RATES", "risk": "H-FX-RISK", "broad": "H-FX-BROAD",
                        "artifact": "H-FX-DATA"})


def case_silver(as_of: str = "2026-11-13") -> ResearchSpec:
    return spec_for_asset(
        asset="CM_ETF_SLV", market="US", asset_class="commodity", as_of=as_of,
        question="What explains the silver drawdown on 2026-06-09: dollar, real rates, risk-off, or data artifact?",
        peers={"US_FX_DXY": ("DXY", "same_day"), "CM_MET_GC": ("Gold", "same_day"),
               "US_FI_IEF": ("IEF duration", "same_day"), "US_EQ_SPY": ("SPY", "same_day"),
               "US_VOL_VIX": ("VIX", "same_day")},
        hypotheses=[("H-CMD-DOLLAR", {"label": "USD/dollar channel", "type": "dollar"}),
                    ("H-CMD-REALRATE", {"label": "Real-rate channel", "type": "real_rate"}),
                    ("H-CMD-RISK", {"label": "Risk-off channel", "type": "risk"}),
                    ("H-CMD-SUPPLY", {"label": "Supply/inventory", "type": "supply"})],
        case_kind="commodity_event", detector="silver_drawdown", direction="deep_drawdown",
        event_override="2026-06-09",
        roles={"dollar": "US_FX_DXY", "gold": "CM_MET_GC", "rates": "US_FI_IEF",
               "risk": "US_EQ_SPY", "vol": "US_VOL_VIX"},
        hypothesis_ids={"dollar": "H-CMD-DOLLAR", "rates": "H-CMD-REALRATE",
                        "risk": "H-CMD-RISK", "supply": "H-CMD-SUPPLY"})
