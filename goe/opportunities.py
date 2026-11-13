"""Opportunity generation, scoring and lifecycle.

An "opportunity" is a *research question*, not a trade. It is created only when
several independent observations line up:

    anomaly(s)  +  a mechanism or an explicit divergence argument  +  evidence
    for and against  +  an invalidation condition

Five archetypes (mandated by the project spec):
  A. price_fundamental_divergence — price moved without fundamental confirmation
  B. expectation_overshoot        — positioning/valuation extreme vs. price action
  C. regime_repricing             — macro regime shift + historically sensitive assets
  D. event_revision               — anomaly into a scheduled event
  E. relative_value               — cross-sectional dispersion between peers

Scores rank *research value* (see config/scoring.yaml), not expected return.
Opportunity fingerprints are deterministic, so a recurring phenomenon updates the
existing record instead of creating duplicates (requirement §10.6).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .config import (
    LIQUIDITY_RANK,
    load_positioning,
    load_themes,
    load_universe,
    load_yaml_config,
)
from .db import Store
from .events import EventCalendar, Event
from .features import FeatureSet
from .transmission.evaluator import MechanismResult

def load_macro_defs():
    from .config import load_macro

    return load_macro()


REGION_CN = {
    "US": "美国", "CN": "中国", "HK": "中国香港", "JP": "日本", "EA": "欧元区", "UK": "英国",
    "DE": "德国", "FR": "法国", "IT": "意大利", "ES": "西班牙", "CH": "瑞士", "KR": "韩国",
    "TW": "中国台湾", "IN": "印度", "BR": "巴西", "CA": "加拿大", "AU": "澳大利亚",
    "MX": "墨西哥", "TR": "土耳其", "WORLD": "全球",
}
TIER_SCORE = {"official": 1.0, "exchange": 0.9, "aggregator": 0.7, "proxy": 0.5, "derived": 0.6}

ARCHETYPE_HORIZON = {
    "price_fundamental_divergence": "1-3m",
    "expectation_overshoot": "1-3m",
    "regime_repricing": "3-12m",
    "event_revision": "1w-1m",
    "relative_value": "1-3m",
}

OPEN_QUESTIONS = {
    "price_fundamental_divergence": [
        "该资产的盈利/现金流预期是否已经同步下修？本系统未接入分析师一致预期，需要在 investment-agent 中核验。",
        "下跌是风险溢价上升还是现金流预期下降？两者对后续定价含义不同。",
        "同行业/同国家其他资产是否出现一致的定价变化（行业性 vs 个股/个券性）？",
    ],
    "expectation_overshoot": [
        "当前仓位数据（CFTC）覆盖的是期货，ETF/期权仓位是否同向？需要补充资金流数据。",
        "拥挤是否来自结构性对冲需求（例如做市商、保险资金）而非方向性押注？",
        "价格延伸是否已由基本面改善（盈利上修）解释？",
    ],
    "regime_repricing": [
        "该资产对触发变量的历史敏感度是否稳定？滚动回归系数是否发生结构性变化？",
        "本次宏观变化是水平冲击还是斜率/预期变化？两者对不同久期资产影响不同。",
        "传导链条中哪一环最可能断裂（政策干预、供给约束、汇率制度）？",
    ],
    "event_revision": [
        "市场对事件的预期分布是什么（而非仅仅事件时间）？本系统缺少期权隐含分布。",
        "事件前是否已出现抢跑定价（价格/仓位提前移动）？",
        "若事件结果符合预期，是否仍存在二阶影响（指引、点阵图、政策路径）？",
    ],
    "relative_value": [
        "两者的相对强弱分化由盈利差异、估值差异还是资金流差异驱动？",
        "配对的基本面可比性如何（行业结构、汇率暴露、政策敏感度）？",
        "分化是否已超过历史极值并开始收敛？需要有触发收敛的催化。",
    ],
}


# --------------------------------------------------------------------- helpers
def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(min(hi, max(lo, x)))


def _f(v: Any) -> float:
    try:
        x = float(v)
        return x if np.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


PCT_KEYS = {"drawdown_252d", "return_1m", "return_1d", "rel_strength_vs_benchmark",
            "breadth_above_ma200", "hy_minus_treasury_1m", "return_5d"}


def _fmt_raw(raw: Any) -> str:
    """Human-readable evidence values (percent for returns, signed decimals else)."""
    if not isinstance(raw, dict):
        return str(raw)
    parts = []
    for k, v in raw.items():
        if isinstance(v, bool):
            parts.append(f"{k}={v}")
        elif isinstance(v, (int, float)) and np.isfinite(float(v)):
            fv = float(v)
            parts.append(f"{k}={fv:+.1%}" if k in PCT_KEYS else f"{k}={fv:+.3f}")
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


def fingerprint(archetype: str, primary_ids: Iterable[str], mechanism_id: str | None = None) -> str:
    key = "|".join(sorted(primary_ids)) + "|" + (mechanism_id or "")
    return "FP-" + hashlib.sha1(f"{archetype}|{key}".encode()).hexdigest()[:16]


@dataclass
class Draft:
    archetype: str
    title: str
    market: str
    asset_class: str
    instruments: list[dict[str, Any]]
    horizon: str
    discovery: dict[str, Any]
    mechanism: dict[str, Any]
    evidence_for: list[dict[str, Any]]
    evidence_against: list[dict[str, Any]]
    catalysts: list[dict[str, Any]]
    open_questions: list[str]
    invalidation: str
    invalidation_checks: list[dict[str, Any]]
    data_quality: dict[str, Any]
    anomaly_ids: list[str] = field(default_factory=list)
    mechanism_id: str | None = None
    score_components: dict[str, float] = field(default_factory=dict)
    score: float = 0.0
    status: str = "new"
    status_reason: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def primary_ids(self) -> list[str]:
        return [i["id"] for i in self.instruments if i.get("role") == "primary"]

    def fingerprint(self) -> str:
        return fingerprint(self.archetype, self.primary_ids(), self.mechanism_id)


class OpportunityEngine:
    def __init__(self, fs: FeatureSet, anomalies: pd.DataFrame,
                 transmissions: list[MechanismResult] | None = None,
                 events: EventCalendar | None = None,
                 scoring: dict[str, Any] | None = None,
                 max_candidates: int = 25):
        self.fs = fs
        self.anoms = anomalies
        self.as_of = fs.as_of
        # Different exchanges close on different calendar dates, and weekly
        # macro/positioning series lag by design. "Current" therefore means the
        # most recent observation per detector+entity within a 7-day window, not
        # a single global date. Each anomaly keeps its own true observation date.
        if anomalies is None or anomalies.empty:
            self.current = pd.DataFrame() if anomalies is None else anomalies
        else:
            _dates = pd.to_datetime(anomalies["date"])
            _cut = _dates.max() - pd.Timedelta(days=7)
            _recent = anomalies[_dates >= _cut].copy()
            _recent["_d"] = pd.to_datetime(_recent["date"])
            _recent = _recent.sort_values("_d").groupby(["entity_id", "detector"], as_index=False).tail(1)
            self.current = _recent.drop(columns=["_d"]).reset_index(drop=True)
        self.transmissions = transmissions or []
        self.events = events or EventCalendar.load()
        self.scoring = scoring or load_yaml_config("scoring.yaml")
        self.universe = load_universe()
        self.themes = load_themes()
        self.positioning = load_positioning()
        self.max_candidates = max_candidates

    # --------------------------------------------------------------- accessors
    def anoms_for(self, entity_id: str) -> pd.DataFrame:
        if self.current is None or self.current.empty:
            return pd.DataFrame()
        return self.current[self.current.entity_id == entity_id]

    def anoms_since(self, entity_id: str, days: int = 30) -> pd.DataFrame:
        """Anomalies for one entity within the last `days` calendar days.

        Mechanism windows are 1-3 months, so a 7-day freshness rule is too strict
        for slow-moving variables (e.g. a volatility-regime shift).
        """
        if self.anoms is None or self.anoms.empty:
            return pd.DataFrame()
        cutoff = pd.Timestamp(self.as_of) - pd.Timedelta(days=days)
        m = (self.anoms.entity_id == entity_id) & (pd.to_datetime(self.anoms.date) >= cutoff) \
            & (pd.to_datetime(self.anoms.date) <= pd.Timestamp(self.as_of))
        return self.anoms[m]

    def fv(self, entity_id: str, feature: str, window: str = "", kind: str | None = None) -> float:
        return self.fs.value(entity_id, feature, window) if kind is None else self.fs.value(entity_id, feature, window)

    def instrument_meta(self, iid: str) -> dict[str, Any]:
        spec = self.universe.instruments.get(iid)
        if not spec:
            return {"id": iid, "name": iid, "role": "primary", "asset_class": "unknown", "region": "WORLD"}
        return {"id": iid, "name": spec.name, "symbol": spec.symbol, "asset_class": spec.asset_class,
                "region": spec.region, "role": "primary", "importance": spec.importance,
                "liquidity": spec.liquidity}

    def _events_for(self, ids: list[str], within: int = 45) -> list[dict[str, Any]]:
        # Only officially verified dates may raise the catalyst component; an
        # unverified (convention-derived) date is shown in the calendar tooling
        # but must not influence scoring.
        evs = [e for e in self.events.for_entities(ids, self.as_of, within_days=within) if e.verified]
        return self.events.to_dicts(evs)

    def _tier_score(self, anomalies: pd.DataFrame) -> float:
        tiers = []
        for row in anomalies.itertuples(index=False):
            ev = row.evidence if isinstance(row.evidence, dict) else json.loads(row.evidence or "{}")
            tier = (ev.get("source") or {}).get("tier", "derived")
            tiers.append(TIER_SCORE.get(tier, 0.6))
        return float(np.mean(tiers)) if tiers else 0.5

    # ------------------------------------------------------------------ rules
    def generate(self) -> list[Draft]:
        drafts: list[Draft] = []
        drafts.extend(self._price_fundamental_divergence())
        drafts.extend(self._expectation_overshoot())
        drafts.extend(self._regime_repricing())
        drafts.extend(self._event_revision())
        drafts.extend(self._relative_value())
        for d in drafts:
            self._score(d)

        # 1) identical phenomenon: same archetype + same primary instruments + mechanism
        best: dict[str, Draft] = {}
        for d in drafts:
            fp = d.fingerprint()
            if fp not in best or d.score > best[fp].score:
                best[fp] = d
        # 2) same exposure theme (futures vs ETF vs index): keep the strongest,
        #    so one macro phenomenon cannot fill the pipeline with wrappers.
        theme_best: dict[tuple[str, str, str], Draft] = {}
        for d in best.values():
            prim = d.primary_ids()
            theme = self.theme_of(prim[0]) if prim else "unknown"
            key = (d.archetype, theme, d.mechanism_id or "") if d.archetype == "regime_repricing" \
                else (d.archetype, theme, "")
            if key not in theme_best or d.score > theme_best[key].score:
                theme_best[key] = d
        # Expose the pre-cap scored set for validation/audit: "did the engine form
        # the hypothesis?" is a different question from "did it make the top 25?".
        self.all_scored: list[Draft] = sorted(theme_best.values(), key=lambda x: x.score, reverse=True)
        # 3) per-archetype and per-region caps to keep the pipeline diverse
        caps = {"price_fundamental_divergence": 8, "expectation_overshoot": 6,
                "regime_repricing": 6, "event_revision": 4, "relative_value": 3}
        region_caps = {"price_fundamental_divergence": 3}
        kept: list[Draft] = []
        by_arch: dict[str, int] = {}
        by_region: dict[tuple[str, str], int] = {}
        for d in sorted(theme_best.values(), key=lambda x: x.score, reverse=True):
            if by_arch.get(d.archetype, 0) >= caps.get(d.archetype, 5):
                continue
            rkey = (d.archetype, d.market)
            if by_region.get(rkey, 0) >= region_caps.get(d.archetype, 99):
                continue
            by_arch[d.archetype] = by_arch.get(d.archetype, 0) + 1
            by_region[rkey] = by_region.get(rkey, 0) + 1
            kept.append(d)
        kept.sort(key=lambda x: x.score, reverse=True)
        return kept[: self.max_candidates]

    def theme_of(self, entity_id: str) -> str:
        return self.themes.get(entity_id, entity_id)

    # ------------------------------------------------------- A. divergence
    def _price_fundamental_divergence(self) -> list[Draft]:
        out: list[Draft] = []
        price_anoms = self.current[self.current.family == "price"] if not self.current.empty else pd.DataFrame()
        if price_anoms.empty:
            return out
        credit_underperf = False
        macro_soft = False
        has_macro = not self.fs.macro.empty
        if not self.current.empty:
            credit = self.current[self.current.detector == "credit_stress"]
            credit_underperf = bool((credit.direction == "hy_underperform").any())
            macro = self.current[self.current.detector == "macro_shift"]
            macro_soft = bool((macro.direction == "below_norm").any())
        has_credit = bool((self.fs.long.entity_id == "CREDIT_RISK").any()) if not self.fs.long.empty else False
        for entity, group in price_anoms.groupby("entity_id"):
            spec = self.universe.instruments.get(entity)
            if spec is None:
                continue
            theme = self.theme_of(entity)
            # FX is a relative price without a fundamental anchor in this data set;
            # agricultural commodities lack inventory/supply data. Both are handled
            # by other archetypes or explicitly left to deeper research.
            # A divergence claim needs a fundamental anchor in the data set:
            # equities (credit/rates/breadth) and precious metals (USD/real rates).
            # Energy, industrial metals, agriculture and FX lack inventory/supply
            # or rate-differential data, so they are handled by mechanisms instead.
            anchored = spec.is_equity or (spec.asset_class == "commodity" and theme in ("gold", "silver", "platinum"))
            if not anchored:
                continue
            has_drawdown = (group.detector == "drawdown_extreme").any() and \
                           (group[group.detector == "drawdown_extreme"].direction == "deep_drawdown").any()
            down_shock = bool(((group.detector == "price_return_shock") & (group.direction == "down")).any())
            if not (has_drawdown or down_shock):
                continue
            if spec.is_equity and credit_underperf and macro_soft:
                continue
            cape_pct = self.fv("US_CAPE", "cape_pctile_10y") if spec.region == "US" else float("nan")
            erp_pct = self.fv("equity_risk_premium", "level")
            dd = self.fv(entity, "drawdown_252d")
            ret1m = self.fv(entity, "return", "1m")
            vol_pct = self.fv(entity, "vol_pctile_5y", "3m")
            if not (np.isfinite(dd) and dd <= -0.08) and not (np.isfinite(ret1m) and ret1m <= -0.05):
                continue
            # Is the decline already explained by the standard macro drivers?
            # If yes, this is not a divergence case and must not enter the pool.
            verdict, verdict_note = self._context_verdict(
                spec,
                dxy=self.fv("US_FX_DXY", "return", "1m"),
                y10=self.fv("UST:10Y", "change_21d", "10Y"),
                credit_z=self.fv("CREDIT_RISK", "hy_minus_treasury_z_3y"),
                cny=self.fv("CN_FX_USDCNY", "return", "1m"),
                cn10=self.fv("CN:10Y", "change_21d", "10Y"),
            )
            if verdict == "explained":
                continue
            anoms = list(group.itertuples(index=False))
            chain, context_ev = self._divergence_context(spec)
            ev_for = []
            for a in anoms:
                ev = a.evidence if isinstance(a.evidence, dict) else {}
                ev_for.append({
                    "claim": f"{a.detector} 触发（{a.direction}）",
                    "evidence": f"度量 {a.measure}={_f(a.magnitude):.3f}，异常强度 {a.score:.2f}；"
                                f"{_fmt_raw(ev.get('raw', {}))}",
                    "source": (ev.get("source") or {}).get("source", ""),
                    "tier": (ev.get("source") or {}).get("tier", ""),
                    "as_of": a.date, "strength": "strong" if a.score >= 0.7 else "moderate",
                })
            if np.isfinite(dd):
                ev_for.append({"claim": "价格已显著回撤", "evidence": f"距 1 年高点回撤 {dd:.1%}",
                               "source": "yahoo", "tier": "aggregator", "as_of": self.as_of,
                               "strength": "moderate"})
            ev_for.extend(context_ev)
            ev_against = [{
                "claim": "价格下跌可能反映基本面恶化而非错误定价",
                "evidence": "本系统未接入盈利一致预期与修正数据；若 EPS 预期同步下修，'超跌'假设不成立。",
                "source": "data_gap", "tier": "derived", "as_of": self.as_of, "strength": "strong",
            }]
            if credit_underperf:
                ev_against.append({"claim": "信用市场同步走弱",
                                   "evidence": "HY/国债相对表现处于 3 年负向极值，风险偏好恶化可能解释价格下跌。",
                                   "source": "yahoo_proxy", "tier": "proxy", "as_of": self.as_of,
                                   "strength": "moderate"})
            if verdict == "ambiguous":
                ev_against.append({"claim": "下跌可能与宏观驱动一致",
                                   "evidence": f"{verdict_note}；因此'超跌'判断证据不足，需先验证驱动因素。",
                                   "source": "methodology", "tier": "derived", "as_of": self.as_of,
                                   "strength": "strong"})
            if np.isfinite(vol_pct) and vol_pct > 0.9:
                ev_against.append({"claim": "波动率处于高位",
                                   "evidence": f"波动率 5 年分位 {vol_pct:.0%}，高波动期价格信号噪声更大。",
                                   "source": "yahoo", "tier": "aggregator", "as_of": self.as_of,
                                   "strength": "moderate"})
            region = spec.region
            if spec.asset_class == "commodity":
                factor_label = "美元/实际利率/供需信号"
            elif spec.is_equity and region in ("US",):
                factor_label = "估值/信用/风险溢价信号"
            elif spec.is_equity and region in ("CN", "HK"):
                factor_label = "政策/利率/信用信号"
            elif spec.is_equity:
                factor_label = "全球信用/风险偏好/广度信号"
            else:
                factor_label = "利差/政策信号"
            title = f"{REGION_CN.get(region, region)} {spec.name}：价格下行与{factor_label}不一致（待检验的超跌假设）"
            gaps = ["分析师盈利预期与修正数据未接入", "信用利差使用 HYG/IEF 代理，非 OAS 直接数据"]
            if not has_macro:
                gaps.append("宏观序列在当前数据快照中不可用")
            out.append(Draft(
                archetype="price_fundamental_divergence", title=title, market=region,
                asset_class=spec.asset_class, instruments=[self.instrument_meta(entity)],
                horizon=ARCHETYPE_HORIZON["price_fundamental_divergence"],
                discovery={
                    "what": f"{spec.name} 出现价格异常下跌（1 个月收益 {ret1m:.1%}，回撤 {dd:.1%}）；"
                            + ("信用代理与宏观序列未显示同等程度的恶化。" if (has_macro and has_credit)
                               else ("信用代理（HYG/IEF）未显示同等恶化，但宏观序列当前"
                                     + ("不可用" if not has_macro else "部分可用")
                                     + "，因此'基本面未恶化'只能视为待验证假设。" if has_credit
                                     else "宏观与信用数据当前不完整，'基本面未恶化'只能视为待验证假设。")),
                    "why_now": (lambda: (
                        f"1 个月收益 {ret1m:+.1%}、距 1 年高点 {dd:+.1%}"
                        + (f"（5 年分位 {self.fv(entity, 'drawdown_pctile_5y'):.0%}）"
                           if np.isfinite(self.fv(entity, 'drawdown_pctile_5y')) else "")
                        + (f"；信用代理 z={self.fv('CREDIT_RISK', 'hy_minus_treasury_z_3y'):+.2f}"
                           if np.isfinite(self.fv('CREDIT_RISK', 'hy_minus_treasury_z_3y')) else "")
                        + f"；宏观解释判定：{verdict_note}。"))(),
                    "hypothesis": "价格已计入悲观情形，而基本面与信用条件尚未验证该悲观程度；若后续数据不恶化，存在重新定价空间。",
                    "anomalies": [{"id": a.anomaly_id, "detector": a.detector, "direction": a.direction,
                                   "score": float(a.score)} for a in anoms],
                    "cape_pctile": cape_pct, "erp_level": erp_pct,
                    "context_verdict": verdict, "context_note": verdict_note,
                    "theme": self.theme_of(entity),
                },
                mechanism={"id": None, "chain": chain, "confidence": round(0.3 + 0.03 * len(context_ev), 2),
                           "causal_status": "hypothesis",
                           "conditions": ["信用利差未持续走阔", "宏观增长数据未显著下修", "无重大资产特有负面事件"],
                           "identification": "该链条是待检验假设；价格与基本面代理之间的相关性不等于因果。"},
                evidence_for=ev_for, evidence_against=ev_against,
                catalysts=self._events_for([entity], within=45),
                open_questions=list(OPEN_QUESTIONS["price_fundamental_divergence"]),
                invalidation=f"若 {spec.name} 相对基准再下跌 8% 以上，或 HY/国债相对表现跌至 -2σ（约 -3%），"
                             f"或出现明确的盈利下修/信用事件，则'超跌'假设失效。",
                invalidation_checks=[
                    {"entity": entity, "feature": "rel_strength_vs_benchmark", "window": "1m", "op": "<",
                     "value": -0.08, "note": "相对基准继续大幅跑输"},
                    {"entity": "CREDIT_RISK", "feature": "hy_minus_treasury_z_3y", "op": "<", "value": -2.0,
                     "note": "信用利差代理恶化"},
                ],
                data_quality={"score": self._tier_score(group) * (1.0 if has_credit else 0.8), "gaps": gaps},
                anomaly_ids=[a.anomaly_id for a in anoms],
            ))
        return out

    def _context_verdict(self, spec, *, dxy: float, y10: float, credit_z: float,
                         cny: float, cn10: float) -> tuple[str, str]:
        """Classify whether the decline is already explained by macro drivers.

        Returns (verdict, note) where verdict is:
          explained  — standard drivers account for the move; not a divergence
          ambiguous  — mixed evidence; candidate allowed only with a strong
                       evidence-against entry
          conflict   — drivers point the other way or are neutral; divergence
                       case is internally consistent
        """
        if spec.asset_class == "commodity" and self.theme_of(spec.id) in ("gold", "silver", "platinum"):
            # A large move needs a comparably large driver to be "explained":
            # a 1% dollar move does not explain a 12% crash.
            if (np.isfinite(dxy) and dxy > 0.02) or (np.isfinite(y10) and y10 > 0.25):
                return "explained", "美元走强/名义利率上行是贵金属下跌的标准解释"
            if (np.isfinite(dxy) and dxy > 0.008) or (np.isfinite(y10) and y10 > 0.08):
                return "ambiguous", "美元或利率小幅上行，部分解释下跌"
            return "conflict", "美元与利率未提供下跌解释"
        if spec.is_equity:
            if spec.region in ("CN", "HK"):
                if np.isfinite(cny) and cny > 0.02:
                    return "explained", "人民币贬值与资本外流风险可解释下跌"
                if np.isfinite(cn10) and cn10 < -0.15:
                    return "conflict", "中国国债收益率明显下行（宽松），价格下跌未反映政策方向"
                if np.isfinite(credit_z) and credit_z < -1.5:
                    return "explained", "全球信用风险代理显示风险厌恶上升"
                if np.isfinite(credit_z) and credit_z > -0.5:
                    return "conflict", "全球信用市场未确认风险厌恶（美国 HY 代理）"
                return "ambiguous", "全球信用代理信号中性，本地增长/政策驱动需进一步验证"
            if np.isfinite(credit_z) and credit_z < -1.5:
                return "explained", "信用利差代理显示风险厌恶上升"
            if np.isfinite(credit_z) and credit_z > -0.5:
                return "conflict", "信用市场未确认风险厌恶"
            return "ambiguous", "信用信号中性，宏观驱动不明确"
        if spec.asset_class == "fx":
            return "ambiguous", "汇率是相对价格，需同时检验两国利差与政策"
        if spec.asset_class in ("fixed_income", "credit"):
            return "ambiguous", "利率/信用资产需结合久期与利差分解"
        return "ambiguous", "缺少该资产类别的宏观解释框架"

    def _divergence_context(self, spec) -> tuple[list[str], list[dict[str, Any]]]:
        """Asset-class specific transmission chain and current regime evidence."""
        dxy = self.fv("US_FX_DXY", "return", "1m")
        y10 = self.fv("UST:10Y", "change_21d", "10Y")
        credit_z = self.fv("CREDIT_RISK", "hy_minus_treasury_z_3y")
        ev: list[dict[str, Any]] = []
        if np.isfinite(dxy):
            ev.append({"claim": "美元 1 个月变化", "evidence": f"DXY {dxy:+.1%}", "source": "yahoo",
                       "tier": "aggregator", "as_of": self.as_of, "strength": "weak"})
        if np.isfinite(y10):
            ev.append({"claim": "美国 10Y 收益率 1 个月变化", "evidence": f"{y10*100:+.0f}bp",
                       "source": "treasury_us", "tier": "official", "as_of": self.as_of, "strength": "weak"})
        if np.isfinite(credit_z):
            ev.append({"claim": "信用代理未确认风险厌恶", "evidence": f"HY/国债相对表现 z={credit_z:+.2f}",
                       "source": "yahoo_proxy", "tier": "proxy", "as_of": self.as_of,
                       "strength": "moderate" if abs(credit_z) < 1 else "weak"})
        if spec.region == "CN":
            cn10 = self.fv("CN:10Y", "change_21d", "10Y")
            cn_credit = self.fv("CN_CREDIT", "value", "quarterly")
            cny = self.fv("CN_FX_USDCNY", "return", "1m")
            if np.isfinite(cn10):
                ev.append({"claim": "中国 10Y 国债收益率变化", "evidence": f"{cn10*100:+.0f}bp",
                           "source": "akshare_cn_bond", "tier": "aggregator", "as_of": self.as_of, "strength": "weak"})
            if np.isfinite(cn_credit):
                ev.append({"claim": "中国私人部门信贷同比", "evidence": f"{cn_credit:+.1f}%",
                           "source": "bis", "tier": "official", "as_of": self.as_of, "strength": "moderate"})
            if np.isfinite(cny):
                ev.append({"claim": "人民币汇率 1 个月变化", "evidence": f"USD/CNY {cny:+.1%}",
                           "source": "yahoo", "tier": "aggregator", "as_of": self.as_of, "strength": "weak"})
        if spec.asset_class == "commodity":
            chain = ["供需与库存预期", "持有成本/实际利率", "商品价格", "相关权益与通胀预期"]
            pos_theme = self._positioning_for_theme(spec.id)
            if pos_theme is not None:
                ev.append({"claim": "期货仓位", "evidence": f"{pos_theme[0]} 净头寸分位 {pos_theme[1]:.0%}",
                           "source": "cftc", "tier": "official", "as_of": self.as_of, "strength": "moderate"})
        elif spec.is_equity:
            chain = ["增长/流动性预期", "风险溢价与盈利预期", "估值", "价格"]
            breadth = self.fv(spec.region, "breadth_z_3y")
            if np.isfinite(breadth):
                ev.append({"claim": "市场广度", "evidence": f"{REGION_CN.get(spec.region, spec.region)} 广度 z={breadth:+.2f}",
                           "source": "derived", "tier": "derived", "as_of": self.as_of, "strength": "moderate"})
        elif spec.asset_class in ("fixed_income", "credit"):
            chain = ["政策利率与信用风险", "久期/利差定价", "价格"]
        else:
            chain = ["利差与政策路径", "跨境资本流动", "汇率"]
        return chain, ev

    def _positioning_for_theme(self, instrument_id: str) -> tuple[str, float] | None:
        for pid, pdef in self.positioning.items():
            if pdef.maps_to == instrument_id:
                val = self.fv(pid, "net_pctile_5y")
                if np.isfinite(val):
                    return pid, val
        return None

    # ------------------------------------------------------ B. overshoot
    def _expectation_overshoot(self) -> list[Draft]:
        """Four cases: crowded long into strength, crowded short into weakness,
        crowded long into losses (unwind risk) and crowded short into a squeeze."""
        out: list[Draft] = []
        pos_anoms = self.current[self.current.detector == "positioning_extreme"] if not self.current.empty else pd.DataFrame()
        if pos_anoms.empty:
            return out
        for _, row in pos_anoms.iterrows():
            pid = row.entity_id
            pdef = self.positioning.get(pid)
            if pdef is None or not pdef.maps_to:
                continue
            iid = pdef.maps_to
            spec = self.universe.instruments.get(iid)
            if spec is None or not np.isfinite(_f(row.percentile)):
                continue
            price_anoms = self.anoms_for(iid)
            pct = _f(row.percentile)
            crowded_long = row.direction == "crowded_long" and pct >= 0.9
            crowded_short = row.direction == "crowded_short" and pct <= 0.1
            if not (crowded_long or crowded_short):
                continue
            up_move = (not price_anoms.empty) and bool(
                price_anoms.direction.isin(["up", "outperform", "near_high"]).any())
            down_move = (not price_anoms.empty) and bool(
                price_anoms.direction.isin(["down", "underperform", "deep_drawdown"]).any())
            if crowded_long and up_move:
                case, side = "optimism", "过度乐观"
            elif crowded_short and down_move:
                case, side = "pessimism", "过度悲观"
            elif crowded_long and down_move:
                case, side = "long_unwind", "多头拥挤且已出现浮亏（去杠杆风险）"
            elif crowded_short and up_move:
                case, side = "short_squeeze", "空头拥挤且价格上行（逼空风险）"
            else:
                continue
            ret1m = self.fv(iid, "return", "1m")
            rel_z = self.fv(iid, "rel_strength_z_3y", "1m")
            ev_for = [{
                "claim": f"仓位处于 5 年极值：{row.direction}（分位 {pct:.0%}）",
                "evidence": f"{pdef.name} 净头寸 5 年分位 {pct:.0%}；COT 为周二数据，已按 4 日发布滞后处理；"
                            f"以未平仓量标准化（net/OI）。",
                "source": "cftc", "tier": "official", "as_of": row.date, "strength": "strong",
            }]
            if np.isfinite(ret1m):
                ev_for.append({"claim": "价格与仓位同向/反向的验证",
                               "evidence": f"1 个月收益 {ret1m:+.1%}，相对基准 z={rel_z:+.2f}，"
                                           f"价格异常方向：{'；'.join(sorted(set(price_anoms.direction))) or '无'}",
                               "source": "yahoo", "tier": "aggregator", "as_of": self.as_of, "strength": "moderate"})
            ev_against = [{
                "claim": "仓位极端不等于方向错误",
                "evidence": "拥挤交易可以持续；COT 只覆盖期货且为周度，无法反映期权与场外头寸，也可能来自套保需求。",
                "source": "methodology", "tier": "derived", "as_of": self.as_of, "strength": "strong",
            }, {
                "claim": "净头寸未按波动率或风险预算标准化",
                "evidence": "以合约张数/未平仓量衡量，未转换为风险当量；不同合约规模差异需在深度研究中校正。",
                "source": "methodology", "tier": "derived", "as_of": self.as_of, "strength": "moderate",
            }]
            chains = {
                "optimism": ["仓位拥挤", "边际买盘减弱", "预期修正", "价格反向"],
                "pessimism": ["空头拥挤", "边际卖压减弱", "预期修复", "价格反弹"],
                "long_unwind": ["多头拥挤", "浮亏与止损", "被动减仓", "价格加速下行"],
                "short_squeeze": ["空头拥挤", "浮亏与回补", "被动买入", "价格加速上行"],
            }
            out.append(Draft(
                archetype="expectation_overshoot",
                title=f"{spec.name}：{side} — 仓位极值 + 价格异常（待检验的预期差）",
                market=spec.region, asset_class=spec.asset_class,
                instruments=[self.instrument_meta(iid),
                             {"id": pid, "name": pdef.name, "role": "context",
                              "asset_class": "positioning", "region": "WORLD"}],
                horizon=ARCHETYPE_HORIZON["expectation_overshoot"],
                discovery={
                    "what": f"{pdef.name} 净头寸处于 5 年 {pct:.0%} 分位（{row.direction}），"
                            f"同时 {spec.name} 价格出现反向异常（1 个月 {ret1m:+.1%}）。",
                    "why_now": f"{self.as_of} 前后同时出现仓位极值与价格异常，构成'{case}'组合。",
                    "hypothesis": f"市场预期可能已{side}；若基本面或政策不及当前定价，存在反向修正风险。",
                    "anomalies": [{"id": a.anomaly_id, "detector": a.detector, "direction": a.direction,
                                   "score": float(a.score)} for a in price_anoms.itertuples(index=False)],
                    "positioning_percentile": pct, "case": case, "theme": self.theme_of(iid),
                },
                mechanism={"id": None, "chain": chains[case], "confidence": 0.4,
                           "causal_status": "hypothesis",
                           "conditions": ["无新增基本面催化剂继续支持原方向", "流动性未进一步宽松/收紧"],
                           "identification": "仓位极值与反转的关系在文献中存在争议，属于待检验假设。"},
                evidence_for=ev_for, evidence_against=ev_against,
                catalysts=self._events_for([iid], within=45),
                open_questions=list(OPEN_QUESTIONS["expectation_overshoot"]),
                invalidation="若仓位回落至 5 年 40%-60% 分位，或基本面出现明确改善并伴随价格突破区间，则拥挤假设失效。",
                invalidation_checks=[
                    {"entity": pid, "feature": "net_pctile_5y", "op": "between", "value": [0.4, 0.6],
                     "note": "拥挤度回归中性"},
                ],
                data_quality={"score": 0.85, "gaps": ["ETF/期权资金流未接入", "COT 为周度且滞后"]},
                anomaly_ids=[row.anomaly_id],
            ))
        return out

    # --------------------------------------------------- C. regime repricing
    def _regime_repricing(self) -> list[Draft]:
        out: list[Draft] = []
        for tx in self.transmissions:
            if tx.status not in ("supported", "mixed", "weak"):
                continue
            for asset in tx.assets:
                aid = asset.get("id")
                if not aid:
                    continue
                spec = self.universe.instruments.get(aid)
                if spec is None:
                    continue
                asset_anoms = self.anoms_since(aid, days=30)
                # A candidate needs either a strong mechanism, or a live anomaly
                # on the affected asset plus a mechanism that is at least mixed
                # (a weak-but-live mechanism with a genuinely anomalous asset is
                # a legitimate research lead; both signals are recorded).
                if asset_anoms.empty and tx.confidence < 0.6:
                    continue
                if tx.status == "weak" and asset_anoms.empty:
                    continue
                ev_for = [{
                    "claim": f"传导机制 {tx.mechanism_id} 被激活：{tx.title}",
                    "evidence": "；".join(e.get("statement", "") for e in tx.evidence_for[:3]) or tx.title,
                    "source": "mechanism", "tier": "derived", "as_of": tx.as_of,
                    "strength": "strong" if tx.confidence >= 0.6 else "moderate",
                }]
                for e in tx.evidence_for[:3]:
                    ev_for.append({"claim": f"{e.get('test_type')} 检验通过",
                                   "evidence": e.get("statement", ""), "source": "mechanism_stats",
                                   "tier": "derived", "as_of": tx.as_of,
                                   "strength": "moderate" if tx.confidence < 0.65 else "strong"})
                ev_against = [{
                    "claim": f"机制 {tx.mechanism_id} 的检验存在失败/不稳定项",
                    "evidence": e.get("statement", "") + f"（{e.get('reason', '')}）",
                    "source": "mechanism_stats", "tier": "derived", "as_of": tx.as_of, "strength": "moderate",
                } for e in tx.evidence_against[:3]]
                ev_against.append({
                    "claim": "相关关系不等于因果关系",
                    "evidence": "滚动相关与条件统计只能说明历史共动，无法识别因果；机制成立依赖所列条件。",
                    "source": "methodology", "tier": "derived", "as_of": tx.as_of, "strength": "strong",
                })
                ret1m = self.fv(aid, "return", "1m")
                out.append(Draft(
                    archetype="regime_repricing",
                    title=f"{tx.title}：{spec.name} 可能处于重定价窗口",
                    market=spec.region, asset_class=spec.asset_class,
                    instruments=[self.instrument_meta(aid)],
                    horizon=ARCHETYPE_HORIZON["regime_repricing"],
                    discovery={
                        "what": f"宏观机制 {tx.mechanism_id}（{tx.title}）的触发变量出现异常，"
                                f"{spec.name} 是被机制映射的受影响资产。",
                        "why_now": f"机制置信度 {tx.confidence:.2f}，状态 {tx.status}；资产 1 个月收益 {ret1m:.1%}。",
                        "hypothesis": f"{tx.title} 若继续演进，{spec.name} 的定价假设需要重新检验。",
                        "anomalies": (
                            [{"id": a.anomaly_id, "detector": a.detector, "direction": a.direction,
                              "score": float(a.score), "role": "asset"}
                             for a in asset_anoms.itertuples(index=False)]
                            + [{"id": tr.get("anomaly_id"), "detector": tr.get("detector"),
                                "direction": tr.get("direction"), "score": float(tr.get("score", 0)),
                                "role": "trigger"}
                               for tr in tx.triggers[:4]]
                        ),
                    },
                    mechanism={"id": tx.mechanism_id, "chain": self._mechanism_chain(tx.mechanism_id),
                               "confidence": tx.confidence, "causal_status": "hypothesis",
                               "conditions": tx.conditions,
                               "identification": "correlation_only; 因果链条需条件成立，且可能被政策/结构因素打断。"},
                    evidence_for=ev_for, evidence_against=ev_against,
                    catalysts=self._events_for([aid], within=90),
                    open_questions=list(OPEN_QUESTIONS["regime_repricing"]),
                    invalidation=f"若机制触发变量回到常态（|z|<1），或 {spec.name} 对触发变量的滚动敏感度符号翻转，"
                                 f"则重定价假设失效。反证条件：{'; '.join(tx.falsifiers[:2])}",
                    invalidation_checks=self._trigger_invalidation_checks(tx),
                    data_quality={"score": 0.8 if tx.confidence >= 0.6 else 0.65,
                                  "gaps": ["机制统计基于历史共动，无法识别因果", "月度宏观数据存在发布滞后"]},
                    anomaly_ids=[a.anomaly_id for a in asset_anoms.itertuples(index=False)],
                    mechanism_id=tx.mechanism_id,
                ))
        return out

    def _trigger_invalidation_checks(self, tx) -> list[dict[str, Any]]:
        """Automatic invalidation: the trigger variable returning to normal (|z|<1)."""
        checks: list[dict[str, Any]] = []
        for trig in tx.triggers[:1]:
            eid = trig.get("entity_id", "")
            if not eid:
                continue
            if eid in self.universe.instruments:
                checks.append({"entity": eid, "feature": "return_z_3y", "window": "1m",
                               "op": "between", "value": [-1.0, 1.0],
                               "note": "触发变量的异常已消退（|z|<1）"})
            else:
                spec = load_macro_defs().get(eid)
                win = spec.frequency if spec else "monthly"
                checks.append({"entity": eid, "feature": "z_3y", "window": win,
                               "op": "between", "value": [-1.0, 1.0],
                               "note": "触发变量的异常已消退（|z|<1）"})
        return checks

    def _mechanism_chain(self, mechanism_id: str) -> list[str]:
        try:
            cfg = load_yaml_config("mechanisms.yaml")
            m = (cfg.get("mechanisms") or {}).get(mechanism_id, {})
            chain = m.get("mechanism_chain") or []
            return [str(x) for x in chain][:6] or ["（机制链条未在配置中提供）"]
        except Exception:
            return []

    # ----------------------------------------------------- D. event revision
    def _event_revision(self) -> list[Draft]:
        out: list[Draft] = []
        if not self.events.events or self.current.empty:
            return out
        instrument_ids = set(self.current[self.current.entity_kind == "instrument"].entity_id)
        for ev in self.events.upcoming(self.as_of, within_days=45):
            if not ev.verified:
                # convention-derived / unverified dates must not create candidates
                continue
            affected = [i for i in ev.affects if i in instrument_ids]
            for iid in affected:
                group = self.anoms_for(iid)
                if group.empty:
                    continue
                spec = self.universe.instruments.get(iid)
                if spec is None:
                    continue
                ev_for = [{
                    "claim": f"事件临近：{ev.title}（{ev.date}）",
                    "evidence": f"事件类型 {ev.type}，影响资产包含 {iid}；来源 {'已核验' if ev.verified else '未核验'}。",
                    "source": ev.source or "events.yaml", "tier": "official" if ev.verified else "derived",
                    "as_of": self.as_of, "strength": "moderate",
                }]
                for a in group.itertuples(index=False):
                    ev_for.append({"claim": f"事件前已出现 {a.detector} 异常",
                                   "evidence": f"{a.direction}，强度 {a.score:.2f}，发生于 {a.date}",
                                   "source": ((a.evidence or {}).get("source") or {}).get("source", ""),
                                   "tier": ((a.evidence or {}).get("source") or {}).get("tier", ""),
                                   "as_of": a.date, "strength": "moderate"})
                out.append(Draft(
                    archetype="event_revision",
                    title=f"{spec.name}：临近「{ev.title}」，已出现异常变化（事件驱动的预期修正线索）",
                    market=spec.region, asset_class=spec.asset_class,
                    instruments=[self.instrument_meta(iid)],
                    horizon=ARCHETYPE_HORIZON["event_revision"],
                    discovery={
                        "what": f"{spec.name} 在事件「{ev.title}」（{ev.date}）前出现 {len(group)} 项异常。",
                        "why_now": "事件可能迫使市场重新评估政策路径或数据结果，从而修正预期。",
                        "hypothesis": "若事件结果与当前定价隐含预期不一致，可能出现快速重定价；事件前异常是关注线索而非方向判断。",
                        "anomalies": [{"id": a.anomaly_id, "detector": a.detector, "direction": a.direction,
                                       "score": float(a.score)} for a in group.itertuples(index=False)],
                    },
                    mechanism={"id": None, "chain": ["事件结果", "预期修正", "资产重定价"],
                               "confidence": 0.3, "causal_status": "hypothesis",
                               "conditions": ["事件结果存在不确定性", "市场已提前定价部分结果"],
                               "identification": "事件研究法的标准识别问题：无法区分事件效应与其他同时发生的冲击。"},
                    evidence_for=ev_for,
                    evidence_against=[{"claim": "事件可能已被充分定价", "evidence": "缺少期权隐含分布与一致预期数据，无法判断预期差大小。",
                                       "source": "data_gap", "tier": "derived", "as_of": self.as_of, "strength": "strong"}],
                    catalysts=self.events.to_dicts([ev]),
                    open_questions=list(OPEN_QUESTIONS["event_revision"]),
                    invalidation=f"若事件日期已过且无显著价格/波动反应，或事件被取消/推迟，则线索失效。",
                    invalidation_checks=[],
                    data_quality={"score": 0.6, "gaps": ["缺少期权隐含分布与事件一致预期"]},
                    anomaly_ids=[a.anomaly_id for a in group.itertuples(index=False)],
                ))
        return out

    # -------------------------------------------------------- E. relative value
    def _relative_value(self) -> list[Draft]:
        out: list[Draft] = []
        rel = self.current[self.current.detector == "relative_strength_extreme"] if not self.current.empty else pd.DataFrame()
        if rel.empty:
            return out
        rel = rel[rel.window == "3m"]
        groups: dict[tuple[str, str], list[pd.Series]] = {}
        for _, row in rel.iterrows():
            spec = self.universe.instruments.get(row.entity_id)
            if spec is None:
                continue
            groups.setdefault((spec.asset_class, spec.region), []).append(row)
        for (ac, region), rows in groups.items():
            strong = [r for r in rows if r.direction == "outperform"]
            weak = [r for r in rows if r.direction == "underperform"]
            if not strong or not weak:
                continue
            a, b = strong[0], weak[0]
            out.append(Draft(
                archetype="relative_value",
                title=f"{self.universe.instruments[b.entity_id].name} vs {self.universe.instruments[a.entity_id].name}："
                      f"相对强弱分化处于 3 年极值",
                market=region, asset_class=ac,
                instruments=[self.instrument_meta(a.entity_id), self.instrument_meta(b.entity_id)],
                horizon=ARCHETYPE_HORIZON["relative_value"],
                discovery={
                    "what": f"{self.universe.instruments[a.entity_id].name} 3 个月相对强弱 z={_f(a.magnitude):.2f}，"
                            f"{self.universe.instruments[b.entity_id].name} z={_f(b.magnitude):.2f}，方向相反且均超过 2σ。",
                    "why_now": "横截面分化达到极值，若驱动因素（盈利、政策、资金）不具有持续性，可能出现收敛。",
                    "hypothesis": "两条相对强弱曲线可能均值回归；但分化也可能反映基本面差异，需先验证驱动。",
                    "anomalies": [{"id": a.anomaly_id, "detector": a.detector, "direction": a.direction, "score": float(a.score)},
                                  {"id": b.anomaly_id, "detector": b.detector, "direction": b.direction, "score": float(b.score)}],
                },
                mechanism={"id": None, "chain": ["相对强弱分化", "驱动因素检验", "收敛或持续"],
                           "confidence": 0.3, "causal_status": "hypothesis",
                           "conditions": ["两者基本面可比", "无政策性分割"],
                           "identification": "横截面极值本身不构成机会；需要识别分化驱动。"},
                evidence_for=[{"claim": "相对强弱处于 3 年极值",
                               "evidence": f"{a.entity_id} z={_f(a.magnitude):.2f}；{b.entity_id} z={_f(b.magnitude):.2f}",
                               "source": "derived", "tier": "derived", "as_of": self.as_of, "strength": "moderate"}],
                evidence_against=[{"claim": "分化可能由基本面差异驱动并持续",
                                   "evidence": f"{a.entity_id} 与 {b.entity_id} 的行业结构、盈利周期与政策敏感度不同；未做配对协整检验。",
                                   "source": "methodology", "tier": "derived", "as_of": self.as_of, "strength": "strong"}],
                catalysts=[],
                open_questions=list(OPEN_QUESTIONS["relative_value"]),
                invalidation="若相对强弱 z 值继续扩大至 3σ 以上且伴随基本面分化，则均值回归假设失效；"
                             "若相对强弱回到 1.5σ 以内，则收敛已发生、线索失效。",
                invalidation_checks=[
                    {"entity": a.entity_id, "feature": "rel_strength_z_3y", "window": "3m",
                     "op": "<", "value": 1.5, "note": "相对强弱已收敛至 1.5σ 以内"},
                ],
                data_quality={"score": 0.6, "gaps": ["缺少套利可行性与借券成本数据"]},
                anomaly_ids=[a.anomaly_id, b.anomaly_id],
            ))
            if len(out) >= 5:
                return out
        return out

    # ------------------------------------------------------------------ score
    def _score(self, d: Draft) -> None:
        w = self.scoring.get("weights", {})
        anoms = d.discovery.get("anomalies", [])
        strength = max([_f(a.get("score")) for a in anoms if _f(a.get("score")) == _f(a.get("score"))] or [0.0])
        prim = d.instruments[0] if d.instruments else {}
        imp = _f(prim.get("importance")) if np.isfinite(_f(prim.get("importance"))) else 0.4
        n_links = len([e for e in d.evidence_for if e.get("claim", "").startswith("传导机制")]) or 1
        economic_impact = _clip(0.6 * imp + 0.4 * min(1.0, n_links / 3))

        valuation_dev = 0.0
        cape_pct = _f(d.discovery.get("cape_pctile"))
        if np.isfinite(cape_pct):
            valuation_dev = _clip(abs(cape_pct - 0.5) * 2)
        pos_pct = _f(d.discovery.get("positioning_percentile"))
        positioning_dev = _clip(abs(pos_pct - 0.5) * 2) if np.isfinite(pos_pct) else 0.0
        if d.archetype == "price_fundamental_divergence":
            divergence = 0.7
        elif d.archetype == "regime_repricing":
            # A supported macro mechanism is itself evidence that the market may
            # not have priced the regime shift yet; the confidence of that
            # mechanism is used as a partial expectation-gap signal (0-0.6).
            divergence = 0.6 * _clip(_f(d.mechanism.get("confidence", 0.0)))
        else:
            divergence = 0.0
        expectation_gap = _clip(max(valuation_dev, positioning_dev, divergence))

        prim_id = prim.get("id", "")
        ma_gap = abs(_f(self.fv(prim_id, "ma_gap_200d")))
        dd = abs(_f(self.fv(prim_id, "drawdown_252d")))
        repricing = _clip(0.6 * _clip(ma_gap / 0.15) + 0.4 * _clip(dd / 0.20))

        cat = 0.1
        if d.catalysts:
            days = min((datetime.strptime(c["date"], "%Y-%m-%d") - datetime.strptime(self.as_of, "%Y-%m-%d")).days
                       for c in d.catalysts)
            cat = 1.0 if days <= 10 else (0.6 if days <= 30 else 0.2)
        timing = 1.0 if ARCHETYPE_HORIZON.get(d.archetype) == d.horizon else 0.5
        liq_rank = LIQUIDITY_RANK.get(prim.get("liquidity", "medium"), 2) if prim else 2
        risk_liquidity = 0.1 + 0.9 * (liq_rank / 4)
        tier = self.scoring.get("weights", {}) and _clip(d.data_quality.get("score", 0.6))
        independent = min(1.0, len(d.evidence_for) / 3)
        mech_support = _clip(d.mechanism.get("confidence", 0.3) / 0.85) if d.mechanism else 0.0
        evidence_quality = _clip(0.5 * tier + 0.3 * independent + 0.2 * mech_support)

        comp = {
            "anomaly_strength": strength,
            "economic_impact": economic_impact,
            "expectation_gap": expectation_gap,
            "repricing_potential": repricing,
            "catalyst": cat,
            "timing_window": timing,
            "risk_liquidity": risk_liquidity,
            "evidence_quality": evidence_quality,
        }
        d.score_components = {k: round(v, 4) for k, v in comp.items()}
        d.score = round(sum(float(w.get(k, 0.0)) * v for k, v in comp.items()), 4)

        # gates
        thresholds = self.scoring.get("status_thresholds", {})
        gates = self.scoring.get("gates", {})
        if len(d.evidence_for) < int(gates.get("min_evidence_items", 2)):
            d.status, d.status_reason = "excluded", "证据项不足（gates.min_evidence_items）"
        elif d.data_quality.get("score", 0) < float(gates.get("min_data_quality", 0.3)):
            d.status, d.status_reason = "excluded", "数据质量不满足最低要求"
        elif d.score >= float(thresholds.get("deep_research", 0.68)):
            d.status = "deep_research"
        elif d.score >= float(thresholds.get("watch", 0.52)):
            d.status = "watch"
        elif d.score >= float(thresholds.get("low_priority", 0.38)):
            d.status = "low_priority"
        else:
            d.status = "excluded"
            d.status_reason = "综合研究价值低于门槛"

    # --------------------------------------------------------------- to record
    def to_record(self, d: Draft) -> dict[str, Any]:
        return {
            "fingerprint": d.fingerprint(),
            "as_of": self.as_of,
            "archetype": d.archetype,
            "title": d.title,
            "market": d.market,
            "asset_class": d.asset_class,
            "instruments": d.instruments,
            "horizon": d.horizon,
            "status": d.status,
            "status_reason": d.status_reason,
            "score": d.score,
            "score_breakdown": d.score_components,
            "discovery": {**d.discovery, "invalidation_checks": d.invalidation_checks},
            "mechanism": d.mechanism,
            "evidence_for": d.evidence_for,
            "evidence_against": d.evidence_against,
            "catalysts": d.catalysts,
            "open_questions": d.open_questions,
            "invalidation": d.invalidation,
            "invalidation_checks": d.invalidation_checks,
            "data_quality": d.data_quality,
            "lifecycle": [],
        }


# ------------------------------------------------------------------ persistence
def persist_drafts(store: Store, engine: OpportunityEngine, drafts: list[Draft],
                   run_id: str | None = None) -> dict[str, Any]:
    created, refreshed = 0, 0
    by_fp: dict[str, Draft] = {}
    for d in drafts:
        rec = engine.to_record(d)
        by_fp[rec["fingerprint"]] = d
        existing = store.find_opportunity(rec["fingerprint"])
        store.upsert_opportunity(rec, run_id=run_id)
        if existing is None:
            created += 1
        else:
            refreshed += 1
            # status follows the score unless a human set a terminal status
            if existing["status"] not in ("deep_research", "excluded", "expired", "invalidated"):
                if existing["status"] != rec["status"]:
                    store.set_opportunity_status(existing["opportunity_id"], rec["status"],
                                                 f"评分更新至 {rec['score']:.2f}", run_id)
    lifecycle = apply_lifecycle(store, engine, by_fp, run_id)
    return {"created": created, "refreshed": refreshed, **lifecycle}


def apply_lifecycle(store: Store, engine: OpportunityEngine, current: dict[str, Draft],
                    run_id: str | None = None, expire_days: int = 45) -> dict[str, Any]:
    """Expire stale records and evaluate automated invalidation checks."""
    as_of_dt = datetime.strptime(engine.as_of, "%Y-%m-%d")
    df = store.opportunities(limit=1000)
    expired = invalidated = 0
    if df.empty:
        return {"expired": 0, "invalidated": 0}
    for row in df.itertuples(index=False):
        if row.status in ("expired", "invalidated", "excluded"):
            continue
        if row.fingerprint in current:
            continue
        last_seen = datetime.strptime(row.last_seen, "%Y-%m-%d")
        age = (as_of_dt - last_seen).days
        # evaluate invalidation checks stored with the discovery payload
        if _checks_breached(store, engine, row.opportunity_id):
            store.set_opportunity_status(row.opportunity_id, "invalidated",
                                         "自动失效条件被触发（invalidation_checks）", run_id)
            invalidated += 1
            continue
        if age > expire_days:
            store.set_opportunity_status(row.opportunity_id, "expired",
                                         f"超过 {expire_days} 天未被重新检测（最后出现 {row.last_seen}）", run_id)
            expired += 1
    return {"expired": expired, "invalidated": invalidated}


def _checks_breached(store: Store, engine: OpportunityEngine, opportunity_id: str) -> bool:
    """Read invalidation checks from the run record and evaluate against features.

    Checks are stored inside the opportunity's ``discovery`` payload
    (``invalidation_checks``) to keep the schema stable. They are evaluated
    against the current feature set only; this is a coarse, auditable rule, not
    a trading stop.
    """
    row = store.conn.execute(
        "SELECT discovery_json FROM opportunities WHERE opportunity_id=?", (opportunity_id,)
    ).fetchone()
    if not row:
        return False
    try:
        checks = json.loads(row["discovery_json"] or "{}").get("invalidation_checks") or []
    except Exception:
        return False
    for chk in checks:
        if not isinstance(chk, dict):
            continue
        entity = chk.get("entity", "")
        feature = chk.get("feature", "")
        window = chk.get("window", "")
        op = chk.get("op", "")
        target = chk.get("value")
        val = engine.fv(entity, feature, window)
        if not np.isfinite(val) or target is None:
            continue
        if op == "<" and isinstance(target, (int, float)) and val < float(target):
            return True
        if op == ">" and isinstance(target, (int, float)) and val > float(target):
            return True
        if op == "between" and isinstance(target, list) and len(target) == 2:
            if float(target[0]) <= val <= float(target[1]):
                return True
    return False
