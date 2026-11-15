"""Autonomous research orchestrator: select, execute, persist, decide next."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .db import Store
from .research_engine import ResearchSpec, execute_spec, spec_for_asset
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
        self.store.set_research_workflow_state(spec.research_id, "PLANNED")
        self.store.add_research_event(spec.research_id, "research:planned", spec.question)

    def run(self, spec: ResearchSpec) -> Any:
        self.store.set_research_workflow_state(spec.research_id, "EVIDENCE_PENDING")
        self.store.add_research_event(spec.research_id, "research:evidence_pending", spec.question)
        try:
            self.store.set_research_workflow_state(spec.research_id, "TESTING")
            finding = execute_spec(self.store, spec)
        except Exception:
            self.store.set_research_workflow_state(spec.research_id, "BLOCKED")
            raise
        self.store.set_research_workflow_state(spec.research_id, "INCONCLUSIVE"
                                                if finding.status == "INCONCLUSIVE" else "COMPLETED")
        self.store.add_research_event(spec.research_id, "research:evaluated", finding.status)
        return finding

    def next_case(self) -> ResearchSpec | None:
        for spec in (case_nikkei(), case_dxy(), case_silver()):
            self.register(spec)
            row = self.store.conn.execute(
                "SELECT 1 FROM research_v2_findings WHERE research_id=?", (spec.research_id,)).fetchone()
            if not row:
                return spec
        return None

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
        case_kind="equity_event", detector="drawdown_extreme", direction="deep_drawdown", event_override="2026-11-06")


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
        case_kind="fx_level", detector="dxy_high", direction="near_high", event_override="2026-11-11")


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
        case_kind="commodity_event", detector="silver_drawdown", direction="deep_drawdown", event_override="2026-06-09")
