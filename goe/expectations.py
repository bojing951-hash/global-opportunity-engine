"""Expectation-gap measurement.

P1-01: the previous implementation used constants (`divergence = 0.7`, then
`0.6 * mechanism_confidence`) as a stand-in for "the market expectation is too
optimistic/pessimistic". A mechanism's confidence says nothing about what the
market has priced; a constant is not a measurement. This module replaces that
with three *observable* proxies, each with an explicit data requirement, and an
explicit "unavailable" state:

1. ``positioning`` — CFTC net/OI percentile distance from neutral. Measures how
   one-sided speculative positioning is (a crowding/expectation proxy). Requires
   a mapped COT market and a fresh weekly report.
2. ``valuation`` — distance of a valuation percentile from neutral. Requires a
   fresh, asset-relevant valuation series (currently only Shiller CAPE for broad
   US equity; stale data -> unavailable, never forward-filled).
3. ``residual_divergence`` — the part of the asset's recent return that is NOT
   explained by its standard drivers (market, dollar, rates, real-rate proxy),
   estimated on a trailing non-overlapping monthly sample and expressed as a
   robust z-score of the residual. High |z| with sign consistency means price
   moved further than drivers justify; low R² means drivers explain too little
   and the proxy is reported unavailable rather than as a discovery.

The combined value is the reliability-weighted mean of the available components
multiplied by the available-weight share. Missing data therefore *reduces* the
score and can never manufacture an opportunity: ``value=None`` means "cannot be
measured", and the opportunity layer caps such candidates below deep research.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .config import load_macro, load_positioning, load_universe

COMPONENT_WEIGHTS = {"positioning": 0.35, "valuation": 0.25, "residual_divergence": 0.40}
RESIDUAL_MIN_OBS = 36
RESIDUAL_MIN_R2 = 0.10
RESIDUAL_Z_THRESHOLD = 1.5


@dataclass
class GapComponent:
    name: str
    value: float | None
    weight: float
    source: str
    evidence: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": None if self.value is None else round(float(self.value), 4),
                "weight": self.weight, "source": self.source,
                "reason": self.reason, "evidence": self.evidence}


@dataclass
class ExpectationGap:
    value: float | None
    confidence: float
    components: dict[str, GapComponent]

    def available_components(self) -> list[str]:
        return [k for k, v in self.components.items() if v.value is not None]

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": None if self.value is None else round(float(self.value), 4),
            "confidence": round(float(self.confidence), 4),
            "available": self.available_components(),
            "definition": "reliability-weighted mean of observable expectation proxies; "
                          "None means insufficient evidence",
            "components": {k: v.to_dict() for k, v in self.components.items()},
        }


# ------------------------------------------------------------------ components
def _fresh(series: pd.Series, as_of: pd.Timestamp, max_age_days: int) -> bool:
    return len(series) > 0 and (as_of - pd.Timestamp(series.index.max())).days <= max_age_days


def _positioning_component(fs, instrument_id: str, as_of: pd.Timestamp,
                           max_age_days: int = 21) -> GapComponent:
    for pid, pdef in load_positioning().items():
        if pdef.maps_to != instrument_id:
            continue
        s = fs.series(pid, "net_pctile_5y")
        if s.empty or not _fresh(s, as_of, max_age_days):
            return GapComponent("positioning", None, COMPONENT_WEIGHTS["positioning"], "cftc",
                                {"positioning_series": pid}, "无新鲜 CFTC 持仓数据")
        pct = float(s.iloc[-1])
        if not np.isfinite(pct):
            return GapComponent("positioning", None, COMPONENT_WEIGHTS["positioning"], "cftc",
                                {"positioning_series": pid}, "持仓分位不可用")
        value = float(np.clip(abs(pct - 0.5) * 2.0, 0.0, 1.0))
        return GapComponent("positioning", value, COMPONENT_WEIGHTS["positioning"], "cftc",
                            {"positioning_series": pid, "net_pctile_5y": round(pct, 4),
                             "as_of_report": str(pd.Timestamp(s.index.max()).date()),
                             "meaning": "净头寸相对 5 年分布的单边程度"})
    return GapComponent("positioning", None, COMPONENT_WEIGHTS["positioning"], "cftc", {},
                        "该资产无映射的 CFTC 持仓市场")


def _valuation_component(fs, instrument_id: str, as_of: pd.Timestamp,
                         max_age_days: int = 120) -> GapComponent:
    spec = load_universe().instruments.get(instrument_id)
    theme_map = {}
    try:
        from .config import load_themes

        theme_map = load_themes()
    except Exception:
        pass
    theme = theme_map.get(instrument_id, "")
    if not spec or theme not in ("us_equity_broad", "us_equity_growth"):
        return GapComponent("valuation", None, COMPONENT_WEIGHTS["valuation"], "shiller",
                            {"theme": theme}, "该资产没有可比的估值序列（仅覆盖美国宽基）")
    s = fs.series("US_CAPE", "cape_pctile_10y")
    if s.empty or not _fresh(s, as_of, max_age_days):
        return GapComponent("valuation", None, COMPONENT_WEIGHTS["valuation"], "shiller",
                            {}, "CAPE 数据过期或不可用（不向前填充）")
    pct = float(s.iloc[-1])
    if not np.isfinite(pct):
        return GapComponent("valuation", None, COMPONENT_WEIGHTS["valuation"], "shiller", {},
                            "CAPE 分位不可用")
    value = float(np.clip(abs(pct - 0.5) * 2.0, 0.0, 1.0))
    return GapComponent("valuation", value, COMPONENT_WEIGHTS["valuation"], "shiller",
                        {"cape_pctile_10y": round(pct, 4), "as_of_value": str(pd.Timestamp(s.index.max()).date()),
                         "meaning": "估值相对 10 年分布的两端程度（仅标普 500 口径）"})


def _period_return(s: pd.Series, periods: int = 21) -> pd.Series:
    return s.pct_change(periods, fill_method=None)


def _period_change(s: pd.Series, periods: int = 21) -> pd.Series:
    return s.diff(periods)


def _driver_returns(fs, instrument_id: str) -> tuple[dict[str, pd.Series], str]:
    spec = load_universe().instruments.get(instrument_id)
    if spec is None:
        return {}, "unknown"
    prices = fs.prices
    region = spec.region
    drivers: dict[str, pd.Series] = {}
    try:
        bench = load_universe().resolve_benchmark(spec)
    except Exception:
        bench = None
    # Local market first; never use the asset itself as its own "market driver"
    # (that produced R²=1 and a meaningless zero residual for SPY).
    region_market = {
        "CN": ["CN_EQ_CSI300", "CN_EQ_SSE", "CN_EQ_CSI500"],
        "HK": ["HK_EQ_HSI", "HK_EQ_HSCEI", "HK_EQ_2800"],
        "JP": ["JP_EQ_N225", "JP_EQ_TOPIX"],
        "EA": ["EA_EQ_SX5E"],
        "DE": ["DE_EQ_DAX"],
        "UK": ["UK_EQ_FTSE"],
        "FR": ["FR_EQ_CAC"],
        "US": ["US_EQ_SPY", "US_EQ_RSP", "US_EQ_QQQ"],
    }
    local_fx = {"JP": ("jpy", "GX_FX_USDJPY"), "EA": ("eur", "GX_FX_EURUSD"),
                "UK": ("gbp", "GX_FX_GBPUSD"), "CH": ("chf", "GX_FX_USDCHF"),
                "AU": ("aud", "GX_FX_AUDUSD"), "KR": ("krw", "GX_FX_USDKRW"),
                "BR": ("brl", "GX_FX_USDBRL"), "MX": ("mxn", "GX_FX_USDMXN")}
    if spec.is_equity:
        cands = ([bench] if bench else []) + region_market.get(region, []) + ["US_EQ_SPY"]
        market_id = None
        for cand in cands:
            if cand and cand != instrument_id and cand in prices.columns:
                market_id = cand
                break
        if market_id:
            drivers["market"] = _period_return(prices[market_id])
        if "US_FX_DXY" in prices.columns:
            drivers["dollar"] = _period_return(prices["US_FX_DXY"])
        if "UST" in fs.curve and "10Y" in fs.curve["UST"].columns:
            drivers["rates"] = _period_change(fs.curve["UST"]["10Y"])
        if region in ("CN", "HK") and "CN_FX_USDCNY" in prices.columns:
            drivers["cny"] = _period_return(prices["CN_FX_USDCNY"])
        fx = local_fx.get(region)
        if fx and fx[1] in prices.columns:
            drivers[fx[0]] = _period_return(prices[fx[1]])
        kind = "equity"
    elif spec.asset_class == "commodity":
        if "US_FX_DXY" in prices.columns:
            drivers["dollar"] = _period_return(prices["US_FX_DXY"])
        if "UST" in fs.curve and "10Y" in fs.curve["UST"].columns:
            drivers["rates"] = _period_change(fs.curve["UST"]["10Y"])
        if "US_FI_TIP" in prices.columns:
            drivers["real_rates_proxy"] = _period_return(prices["US_FI_TIP"])
        kind = "commodity"
    else:
        return {}, "unsupported"
    return drivers, kind


def _residual_component(fs, instrument_id: str, as_of: pd.Timestamp) -> GapComponent:
    name = "residual_divergence"
    weight = COMPONENT_WEIGHTS[name]
    if instrument_id not in fs.prices.columns:
        return GapComponent(name, None, weight, "derived", {}, "资产价格不可用")
    drivers, kind = _driver_returns(fs, instrument_id)
    if not drivers:
        return GapComponent(name, None, weight, "derived", {"kind": kind}, "没有可用的解释变量")
    y = _period_return(fs.prices[instrument_id])
    sample = pd.DataFrame({"y": y, **drivers}).dropna()
    if len(sample) < RESIDUAL_MIN_OBS + 5:
        return GapComponent(name, None, weight, "derived",
                            {"kind": kind, "n_obs": int(len(sample))},
                            f"样本不足（{len(sample)} < {RESIDUAL_MIN_OBS + 5} 个月度观测）")
    # Current observation = the latest date on which the asset AND drivers are
    # all available. The old `sample.iloc[::21]` silently locked "current" to an
    # earlier grid date (e.g. 10-30 while prices ran to 11-12).
    current = sample.iloc[-1]
    lag_days = int((pd.Timestamp(as_of) - pd.Timestamp(current.name)).days)
    if lag_days > 10:
        return GapComponent(name, None, weight, "derived",
                            {"kind": kind, "as_of_return_date": str(pd.Timestamp(current.name).date()),
                             "lag_days": lag_days},
                            f"残差观测滞后 as_of {lag_days} 天（驱动数据不新鲜）")
    # Non-overlapping monthly observations for the regression, excluding current.
    history = sample[sample.index < current.name].iloc[::21]
    if len(history) < RESIDUAL_MIN_OBS:
        return GapComponent(name, None, weight, "derived",
                            {"kind": kind, "n_obs": int(len(history)), "lag_days": lag_days},
                            f"非重叠月度样本不足（{len(history)} < {RESIDUAL_MIN_OBS}）")
    fit = history
    X = np.column_stack([np.ones(len(fit)), fit[list(drivers)].to_numpy(dtype=float)])
    beta, *_ = np.linalg.lstsq(X, fit["y"].to_numpy(dtype=float), rcond=None)
    fitted = X @ beta
    resid = fit["y"].to_numpy(dtype=float) - fitted
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((fit["y"] - fit["y"].mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    resid_std = float(np.std(resid, ddof=1))
    if not np.isfinite(resid_std) or resid_std <= 0:
        return GapComponent(name, None, weight, "derived", {"kind": kind}, "残差波动为零")
    if r2 < RESIDUAL_MIN_R2:
        return GapComponent(name, None, weight, "derived",
                            {"kind": kind, "r2": round(r2, 4), "n_obs": int(len(fit))},
                            f"解释变量只解释了 {r2:.1%} 的变动，残差背离不可识别")
    x_cur = np.r_[1.0, current[list(drivers)].to_numpy(dtype=float)]
    pred_cur = float(x_cur @ beta)
    resid_cur = float(current["y"] - pred_cur)
    z = resid_cur / resid_std
    sign_consistent = bool(np.sign(resid_cur) == np.sign(current["y"]))
    if abs(z) < RESIDUAL_Z_THRESHOLD or not sign_consistent:
        value = 0.0
    else:
        value = float(np.clip((abs(z) - RESIDUAL_Z_THRESHOLD) / 1.5, 0.0, 1.0))
    return GapComponent(name, value, weight, "derived", {
        "kind": kind, "drivers": list(drivers), "r2": round(r2, 4), "n_obs": int(len(fit)),
        "residual_z": round(float(z), 3), "residual": round(resid_cur, 4),
        "actual_return": round(float(current["y"]), 4), "predicted_return": round(pred_cur, 4),
        "sign_consistent": sign_consistent,
        "as_of_return_date": str(pd.Timestamp(current.name).date()),
        "lag_days": lag_days,
        "history_start": str(pd.Timestamp(fit.index.min()).date()),
        "n_obs": int(len(fit)),
        "meaning": "1 个月实际收益中无法由市场/美元/利率解释的部分（同向且 |z|>=1.5 才计分）",
    })


# --------------------------------------------------------------------- public
def compute_expectation_gap(fs, instrument_id: str) -> ExpectationGap:
    as_of = pd.Timestamp(fs.as_of)
    components = {
        "positioning": _positioning_component(fs, instrument_id, as_of),
        "valuation": _valuation_component(fs, instrument_id, as_of),
        "residual_divergence": _residual_component(fs, instrument_id, as_of),
    }
    spec = load_universe().instruments.get(instrument_id)
    applicable = set(components)
    if spec is not None and spec.asset_class == "commodity":
        applicable.discard("valuation")       # CAPE is not applicable to commodities
    if spec is not None and not spec.is_equity:
        applicable.discard("valuation")
    available = {k: v for k, v in components.items() if v.value is not None and k in applicable}
    total_w = sum(components[k].weight for k in applicable) or 1.0
    avail_w = sum(v.weight for v in available.values())
    if not available or avail_w <= 0:
        return ExpectationGap(value=None, confidence=0.0, components=components)
    weighted = sum((v.value or 0.0) * v.weight for v in available.values()) / avail_w
    confidence = avail_w / total_w
    value = float(np.clip(weighted * confidence, 0.0, 1.0))
    return ExpectationGap(value=value, confidence=float(confidence), components=components)
