"""Research Discovery V2 — phenomena, competing hypotheses, evidence gaps.

This module is deliberately separate from ``goe.opportunities`` (V1 scoring).
V1 remains the frozen baseline. V2 does NOT output a mispricing conclusion or a
trade; it outputs a structured research question for B (investment-agent).

Prioritisation is rule-based/lexicographic, not a weighted sum (contracts/
RESEARCH_CONTRACT.md), because no validated weights exist yet.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np
import pandas as pd

from .config import load_themes, load_universe
from .expectations import compute_expectation_gap
from .timesemantics import filter_recent

MISSING_DATA = ["分析师一致预期/修正", "期权隐含分布", "ETF 资金流", "信用 OAS（仅有 HYG/IEF 代理）"]
OPEN_DATA = ["价格/成交量", "CFTC 持仓（周度）", "收益率曲线", "宏观序列（按发布滞后）"]


@dataclass
class ResearchCandidate:
    research_id: str
    as_of: str
    market: str
    asset_class: str
    instruments: list[str]
    observed_phenomenon: str
    materiality: dict[str, Any]
    competing_hypotheses: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    critical_unknowns: list[str] = field(default_factory=list)
    falsification_conditions: list[dict[str, Any]] = field(default_factory=list)
    required_data: list[str] = field(default_factory=list)
    research_cost: dict[str, Any] = field(default_factory=dict)
    decision_impact: dict[str, str] = field(default_factory=dict)
    priority_tier: str = "intelligence"
    priority_rank: int = 0
    rationale: str = ""
    data_quality: dict[str, Any] = field(default_factory=dict)
    evidence_gaps: list[str] = field(default_factory=list)
    evidence_for: list[dict[str, Any]] = field(default_factory=list)
    evidence_against: list[dict[str, Any]] = field(default_factory=list)
    evaluation_id: str = ""
    method: str = "D_v2_triage"
    v1_score: float | None = None
    v1_status: str | None = None
    theme: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def card(self) -> dict[str, Any]:
        """Anonymisable card for independent research-value evaluation."""
        return {
            "research_id": self.research_id, "as_of": self.as_of,
            "market": self.market, "asset_class": self.asset_class,
            "instruments": self.instruments,
            "observed_phenomenon": self.observed_phenomenon,
            "materiality": self.materiality,
            "competing_hypotheses": self.competing_hypotheses,
            "evidence": self.evidence, "critical_unknowns": self.critical_unknowns,
            "falsification_conditions": self.falsification_conditions,
            "required_data": self.required_data, "research_cost": self.research_cost,
            "decision_impact": self.decision_impact,
            "data_quality": self.data_quality, "evidence_gaps": self.evidence_gaps,
        }


def _ev(claim: str, value: str, eclass: str, source: str, as_of: str) -> dict[str, Any]:
    return {"claim": claim, "value": value, "class": eclass, "source": source, "available_at": as_of}


def _materiality(fs, iid: str, score: float) -> dict[str, Any]:
    """Ordinal materiality (not a weighted score): near-high alone is level 0."""
    spec = load_universe().instruments.get(iid)
    if spec is None:
        return {"level": 0, "importance": 0.0, "score": 0.0}
    ret1m = fs.value(iid, "return", "1m")
    ddpct = fs.value(iid, "drawdown_pctile_5y")
    volz = fs.value(iid, "vol_z_3y", "3m")
    has_change = (np.isfinite(ret1m) and abs(float(ret1m)) >= 0.05) or \
                 (np.isfinite(ddpct) and float(ddpct) <= 0.05) or \
                 (np.isfinite(volz) and abs(float(volz)) >= 2) or score >= 0.70
    if not has_change:
        level = 0
    elif float(score) >= 0.90 or (np.isfinite(ret1m) and abs(float(ret1m)) >= 0.12) \
            or (np.isfinite(ddpct) and float(ddpct) <= 0.02):
        level = 3
    elif float(score) >= 0.70 or (np.isfinite(ret1m) and abs(float(ret1m)) >= 0.05):
        level = 2
    else:
        level = 1
    if float(spec.importance) < 0.5:
        level = min(level, 1)
    return {"level": int(level), "importance": float(spec.importance),
            "score": float(score), "return_1m": float(ret1m) if np.isfinite(ret1m) else None,
            "has_change": bool(has_change)}


def build_candidates(fs, anomalies: pd.DataFrame, mechanisms: list[Any] | None = None,
                     v1_rows: list[dict[str, Any]] | None = None, max_candidates: int = 5) -> list[ResearchCandidate]:
    universe = load_universe()
    themes = load_themes()
    as_of = str(fs.as_of)
    if anomalies is None or anomalies.empty:
        return []
    recent = filter_recent(anomalies, pd.Timestamp(as_of))
    if recent.empty:
        return []
    # one row per entity, strongest recent anomaly; entities must be investable instruments
    by_entity = (recent[recent.entity_id.isin(universe.instruments)]
                 .sort_values("score", ascending=False)
                 .groupby("entity_id", as_index=False).first())
    mech_by_asset: dict[str, list[Any]] = {}
    for m in mechanisms or []:
        for a in getattr(m, "assets", []):
            if a.get("id"):
                mech_by_asset.setdefault(a["id"], []).append(m)
    v1_by_theme = {}
    for row in v1_rows or []:
        import json as _json
        disc = row.get("discovery") or {}
        if isinstance(row.get("discovery_json"), str):
            try:
                disc = _json.loads(row["discovery_json"])
            except Exception:
                disc = {}
        instruments = row.get("instruments") or []
        if isinstance(row.get("instruments_json"), str):
            try:
                instruments = _json.loads(row["instruments_json"])
            except Exception:
                pass
        theme = (disc.get("theme") or
                 (instruments[0].get("id") if instruments else ""))
        if theme:
            v1_by_theme[theme] = row

    out: list[ResearchCandidate] = []
    seen_theme: set[str] = set()
    for r in by_entity.itertuples(index=False):
        iid = r.entity_id
        spec = universe.instruments.get(iid)
        if spec is None:
            continue
        theme = themes.get(iid, iid)
        if theme in seen_theme:
            continue
        score = float(r.score)
        ret1m = fs.value(iid, "return", "1m")
        ddpct = fs.value(iid, "drawdown_pctile_5y")
        mat_meta = _materiality(fs, iid, score)
        mat_level = int(mat_meta["level"])
        if mat_level < 1:
            # near-high/trend alone is market intelligence, not a research candidate
            continue
        has_change = bool(mat_meta["has_change"])
        gap = compute_expectation_gap(fs, iid)
        residual = gap.components.get("residual_divergence")
        gap_open = bool(residual is not None and residual.value is not None and residual.value > 0)
        mechs = mech_by_asset.get(iid, [])
        mech_conflict = any(getattr(m, "status", "") in ("mixed", "unsupported", "weak") for m in mechs)
        gap_score = float(residual.value) if (residual and residual.value is not None) else 0.0

        hypotheses = [
            {"id": "H1", "label": "风险溢价/风险厌恶变化", "type": "risk_premium",
             "status": "open" if mech_conflict or gap_open else "untestable",
             "implications": "信用/波动率与风险资产应同向；不需盈利下修。"},
            {"id": "H2", "label": "基本面/盈利预期变化", "type": "fundamental",
             "status": "untestable" if "分析师一致预期/修正" in MISSING_DATA else "open",
             "implications": "盈利修正应领先或同步；本系统无一致预期，需外部验证。"},
            {"id": "H3", "label": "仓位/资金流驱动的技术性移动", "type": "positioning_flow",
             "status": "open" if (gap.components.get("positioning") is not None
                                  and gap.components["positioning"].value is not None)
             else "untestable",
             "implications": "CFTC 极端仓位、随后反转；ETF/期权资金流需补充。"},
            {"id": "H4", "label": "全球共同风险冲击（跨资产同日）", "type": "global_risk",
             "status": "open" if abs(float(ret1m or 0)) >= 0.03 else "untestable",
             "implications": "同日多资产同向下跌/上涨，beta 解释而非本地故事。"},
            {"id": "H5", "label": "数据伪影（换月/拆股/盘中/陈旧）", "type": "data_artifact",
             "status": "open" if spec.asset_class in ("commodity", "crypto") else "untestable",
             "implications": "换月/拆股/数据修订可解释；需核对原始合约与抓取时间。"},
        ]
        evidence = [
            _ev("近期异常", f"{r.detector} {r.direction} 分数 {score:.2f}", "observed_fact",
                "engine/anomalies", str(r.available_date)),
            _ev("1 个月收益", f"{float(ret1m):+.1%}" if np.isfinite(ret1m) else "unknown",
                "observed_fact", "prices", as_of),
        ]
        evidence_for = [
            _ev("可观察异常", f"{r.detector} {r.direction} score={score:.2f}", "observed_fact",
                "engine/anomalies", str(r.available_date)),
            _ev("价格变化", f"1m={float(ret1m):+.1%}" if np.isfinite(ret1m) else "unknown",
                "observed_fact", "prices", as_of),
        ]
        evidence_against = []
        if mech_conflict:
            evidence_against.append(_ev("机制检验失败/不稳定", "mechanism status mixed/unsupported/weak",
                                        "statistical_association", "mechanism_stats", as_of))
        if not np.isfinite(ret1m) or abs(float(ret1m)) < 0.03:
            evidence_against.append(_ev("价格变动幅度不足以支持重大重定价", f"1m={ret1m}",
                                        "observed_fact", "prices", as_of))
        if spec.asset_class == "commodity":
            evidence_against.append(_ev("连续合约换月/拆股伪影风险", "未调整换月",
                                        "unknown", "data_quality", as_of))
        # distinguishability: at least two independent observable test families
        test_families = 0
        if gap.components.get("residual_divergence") is not None and gap.components["residual_divergence"].value is not None:
            test_families += 1
        if gap.components.get("positioning") is not None and gap.components["positioning"].value is not None:
            test_families += 1
        if mech_conflict:
            test_families += 1
        distinguishability = float(min(1.0, test_families / 2.0))
        decision_impact = float(min(1.0, 0.5 * float(spec.importance) + (0.5 if gap_open or mech_conflict else 0.0)))
        if residual is not None and residual.value is not None:
            evidence.append(_ev("驱动残差背离", f"z={residual.evidence.get('residual_z')}, "
                                               f"R²={residual.evidence.get('r2')}",
                                "statistical_association", "derived/residual", as_of))
        for m in mechs[:2]:
            evidence.append(_ev(f"机制 {m.mechanism_id} 状态 {m.status}",
                                f"confidence={m.confidence:.2f}", "statistical_association",
                                "mechanism_stats", str(m.as_of)))
        evidence.append(_ev("盈利预期/期权分布缺失", "无法区分基本面与风险溢价",
                            "unknown", "data_gap", as_of))

        unknowns = list(MISSING_DATA)
        if gap.value is None:
            unknowns.append("预期差代理不可测量（仓位/估值/残差均不可用）")
        if not mechs:
            unknowns.append("该资产没有可检验的宏观传导机制")
        falsification = []
        credit_z = fs.value("CREDIT_RISK", "hy_minus_treasury_z_3y")
        if np.isfinite(credit_z):
            falsification.append({"test": "信用利差代理回升（风险溢价解释被削弱）",
                                  "threshold": f"z > -1 (current {credit_z:.2f})", "data": "CREDIT_RISK"})
        rel_z = fs.value(iid, "rel_strength_z_3y", "1m")
        if np.isfinite(rel_z):
            falsification.append({"test": "相对强弱 z 回归 0（本地冲击论点被削弱）",
                                  "threshold": f"z crosses 0 (current {rel_z:.2f})", "data": "prices"})
        pos_comp = gap.components.get("positioning")
        if pos_comp is not None and pos_comp.value is not None:
            falsification.append({"test": "CFTC 净头寸分位回到中性",
                                  "threshold": "40%-60%", "data": "CFTC"})
        if mechs:
            falsification.append({"test": f"机制 {mechs[0].mechanism_id} 的滚动相关恢复原符号",
                                  "threshold": "sign stable 60d", "data": "mechanism"})
        if spec.asset_class in ("commodity", "crypto"):
            falsification.append({"test": "核对原始合约/交易日，排除换月或坏价",
                                  "threshold": "raw contract data", "data": "exchange/provider"})
        if not falsification:
            falsification = [{"test": "后续价格/仓位/宏观证据与当前解释相反",
                              "threshold": "documented review", "data": "open"}]
        # observed/testable facts belong in the candidate provenance

        cost_hours = 4 + 2 * len([g for g in unknowns if g != "分析师一致预期/修正"]) + (
            2 if spec.asset_class == "commodity" else 0)
        cost = {"hours": int(min(20, cost_hours)),
                "data_access": "high" if spec.asset_class == "commodity" else "medium"}
        decision = {
            "if_true": "若风险溢价/数据伪影解释成立，下调该线索的研究优先级，不改变仓位判断。",
            "if_false": "若基本面或仓位假设获得支持，交给 B 做估值/情景研究。",
        }
        # hard gate: materiality; explanatory gap; distinguishability; decision impact
        gap_level = 2 if gap_score >= 0.3 else (1 if (gap_open or mech_conflict) else 0)
        dist_level = 2 if test_families >= 2 else (1 if test_families == 1 else 0)
        impact_level = 2 if (float(spec.importance) >= 0.8 and gap_level > 0) else \
            (1 if float(spec.importance) >= 0.5 else 0)
        if mat_level < 1 or gap_level == 0:
            tier = "intelligence"
        elif mat_level >= 3 and gap_level >= 2 and dist_level >= 2 and impact_level >= 2:
            tier = "A"
        elif mat_level >= 2 and gap_level >= 1 and dist_level >= 1:
            tier = "B"
        elif mat_level >= 1 and dist_level >= 1:
            tier = "C"
        else:
            tier = "intelligence"
        v1 = v1_by_theme.get(theme)
        cand = ResearchCandidate(
            research_id=f"RC-{as_of.replace('-', '')}-{len(out)+1:02d}",
            as_of=as_of, market=spec.region, asset_class=spec.asset_class,
            instruments=[iid], observed_phenomenon=(
                f"{spec.name} 近期 {r.detector}（{r.direction}，分数 {score:.2f}）；"
                f"1 个月收益 {float(ret1m):+.1%}；回撤分位 {float(ddpct):.2f}。"),
            materiality={"level": mat_level, "importance": spec.importance,
                         "anomaly_score": score, "return_1m": float(ret1m) if np.isfinite(ret1m) else None,
                         "gap_score": round(gap_score, 3), "gap_level": gap_level,
                         "mechanism_conflict": mech_conflict,
                         "distinguishability_level": dist_level,
                         "decision_impact_level": impact_level, "has_change": has_change},
            competing_hypotheses=hypotheses, evidence=evidence,
            critical_unknowns=unknowns, falsification_conditions=falsification,
            required_data=OPEN_DATA + MISSING_DATA,
            research_cost=cost, decision_impact=decision,
            priority_tier=tier, priority_rank=0,
            rationale=f"tier {tier}: materiality L{mat_level}, gap L{gap_level}, "
                      f"distinguishability L{dist_level}, impact L{impact_level}, "
                      f"mechanism_conflict={mech_conflict}, cost={cost['hours']}h",
            data_quality={"score": float(gap.confidence), "gaps": unknowns},
            evidence_gaps=unknowns, theme=theme,
            evidence_for=evidence_for, evidence_against=evidence_against,
            evaluation_id=f"D:{as_of}:{iid}",
            v1_score=float(v1["score"]) if v1 and v1.get("score") is not None else None,
            v1_status=v1.get("status") if v1 else None,
        )
        out.append(cand)
        seen_theme.add(theme)

    # rank only researchable tiers; intelligence items are recorded but not prioritized
    # lexicographic: tier, materiality, explanatory gap, distinguishability,
    # decision impact, inverse cost. No hidden weighted sum.
    ranked = sorted([c for c in out if c.priority_tier != "intelligence"],
                    key=lambda c: (c.priority_tier, -int(c.materiality.get("level", 0)),
                                   -int(c.materiality.get("gap_level", 0)),
                                   -int(c.materiality.get("distinguishability_level", 0)),
                                   -int(c.materiality.get("decision_impact_level", 0)),
                                   c.research_cost["hours"], c.research_id))
    for i, c in enumerate(ranked, start=1):
        c.priority_rank = i
    intelligence = [c for c in out if c.priority_tier == "intelligence"]
    return (ranked + intelligence)[: max_candidates]


def run_triage(store, as_of: str | None = None, history_start: str | None = None,
               max_candidates: int = 5) -> list[ResearchCandidate]:
    from .anomalies import detect_anomalies
    from .config import load_yaml_config
    from .features import FeatureBuilder
    from .transmission.evaluator import MechanismEvaluator

    as_of = as_of or store.scalar("SELECT MAX(date) FROM prices")
    fs = FeatureBuilder(store, as_of=as_of, point_in_time=True,
                        history_start=history_start).build()
    start = (pd.Timestamp(fs.as_of) - pd.Timedelta(days=200)).strftime("%Y-%m-%d")
    anomalies = detect_anomalies(fs, since=start)
    if anomalies.attrs.get("errors"):
        raise RuntimeError("detector failed in triage: " + "; ".join(anomalies.attrs["errors"]))
    recent = filter_recent(anomalies, pd.Timestamp(fs.as_of))
    mechs = MechanismEvaluator(fs, load_yaml_config("mechanisms.yaml")).evaluate(recent)
    v1_rows = []
    try:
        v1_rows = store.opportunities(limit=100).to_dict("records")
    except Exception:
        v1_rows = []
    return build_candidates(fs, anomalies, mechs, v1_rows, max_candidates=max_candidates)
