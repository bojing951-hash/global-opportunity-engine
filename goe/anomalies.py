"""Anomaly detection.

An anomaly is a *descriptive* statement: "this measurement is unusual relative
to its own recent history, with a reproducible formula". It is explicitly NOT a
claim of mispricing. Several anomalies must combine, and a mechanism or a
divergence argument must connect them, before the opportunity layer creates a
candidate (see ``goe.opportunities``).

Every detector:
  * uses trailing-only statistics (robust z / trailing percentile) supplied by
    the feature layer, so replaying a past date never sees the future;
  * states its threshold, its score formula and the raw supporting numbers in
    the evidence payload;
  * is bounded by flood control so a market-wide shock does not generate
    hundreds of near-duplicate flags.

Output frame columns
--------------------
date, anomaly_id, detector, family, entity_id, entity_kind, asset_class, region,
direction, window, measure, magnitude, score, percentile, evidence (dict)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd

from .config import load_curves, load_macro, load_sources, load_universe, load_yaml_config
from .features import FeatureSet


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def _safe_float(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def anomaly_id(detector: str, entity_id: str, date: str, direction: str, window: str = "") -> str:
    raw = f"{detector}|{entity_id}|{date}|{direction}|{window}"
    return "AN-" + hashlib.sha1(raw.encode()).hexdigest()[:14]


@dataclass
class SourceIndex:
    """Maps entity -> (provider, tier) for evidence provenance."""

    instruments: dict[str, tuple[str, str]]
    series: dict[str, tuple[str, str, str]]  # id -> (provider, tier, label)

    @classmethod
    def build(cls) -> "SourceIndex":
        universe = load_universe()
        sources = load_sources()
        inst = {
            iid: (spec.source, sources.get(spec.source, {}).get("tier", "unknown"))
            for iid, spec in universe.instruments.items()
        }
        series: dict[str, tuple[str, str, str]] = {}
        for cid, cdef in load_curves().items():
            for t in cdef.tenors:
                series[f"{cid}:{t}"] = (cdef.provider, cdef.tier, f"{cdef.name} {t}")
        for mid, m in load_macro().items():
            series[mid] = (m.provider, m.tier, m.name)
        for pid, p in load_positioning_items().items():
            series[pid] = (p.provider, "official", p.name)
            series[f"{pid}:oi"] = (p.provider, "official", p.name + " (open interest)")
        return cls(instruments=inst, series=series)

    def lookup(self, entity_id: str, entity_kind: str) -> dict[str, str]:
        if entity_kind == "instrument" and entity_id in self.instruments:
            provider, tier = self.instruments[entity_id]
            return {"source": provider, "tier": tier}
        if entity_id in self.series:
            provider, tier, label = self.series[entity_id]
            return {"source": provider, "tier": tier}
        return {"source": "derived", "tier": "derived"}


def load_positioning_items():
    from .config import load_positioning

    return load_positioning()


# ------------------------------------------------------------------------- base
class Detector:
    name: str = ""
    family: str = ""
    description: str = ""

    def __init__(self, ctx: "DetectorContext"):
        self.ctx = ctx

    def detect(self) -> pd.DataFrame:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError


class DetectorContext:
    def __init__(self, fs: FeatureSet, thresholds: dict[str, Any] | None = None):
        self.fs = fs
        self.thresholds = thresholds or load_yaml_config("thresholds.yaml")
        self.sources = SourceIndex.build()
        self.global_cfg = self.thresholds.get("global", {})
        self._cache: dict[tuple[str, str, str | None], pd.DataFrame] = {}

    def cfg(self, detector: str) -> dict[str, Any]:
        return self.thresholds.get("detectors", {}).get(detector, {})

    def wide(self, entity_kind: str, feature: str, window: str | None = None) -> pd.DataFrame:
        key = (entity_kind, feature, window)
        if key in self._cache:
            return self._cache[key]
        df = self.fs.long
        m = (df.entity_kind == entity_kind) & (df.feature == feature)
        if window is not None:
            m &= df.window == window
        sub = df[m]
        if sub.empty:
            out = pd.DataFrame()
        else:
            sub = sub.copy()
            sub["date"] = pd.to_datetime(sub["date"])
            out = sub.pivot_table(index="date", columns="entity_id", values="value", aggfunc="last").sort_index()
        self._cache[key] = out
        return out

    def availability(self, entity_kind: str, entity_id: str, date: pd.Timestamp) -> str:
        """Date on which the observation could actually be known.

        Macro observations are dated by reference period and only published after
        a lag; the anomaly must be screened against its *availability* date, or a
        fresh release can never enter the recent-window opportunity logic (P1-02).
        Market prices, curves and positioning (already publication-dated) are
        available on their own date.
        """
        from .features import RELEASE_LAG_DAYS

        if getattr(self.fs, "meta", {}).get("macro_dates_are_availability"):
            return pd.Timestamp(date).strftime("%Y-%m-%d")
        lag = 0
        try:
            macro = load_macro()
            if entity_id in macro:
                lag = RELEASE_LAG_DAYS.get(macro[entity_id].frequency, 0)
            elif entity_kind == "valuation" and entity_id == "US_CAPE":
                lag = RELEASE_LAG_DAYS["monthly"]
        except Exception:
            lag = 0
        return (pd.Timestamp(date) + pd.Timedelta(days=lag)).strftime("%Y-%m-%d")

    def observation_date(self, entity_kind: str, entity_id: str, date: pd.Timestamp) -> str:
        """Reference-period date for macro observations (date minus release lag)."""
        from .features import RELEASE_LAG_DAYS

        lag = 0
        try:
            macro = load_macro()
            if entity_id in macro:
                lag = RELEASE_LAG_DAYS.get(macro[entity_id].frequency, 0)
        except Exception:
            lag = 0
        return (pd.Timestamp(date) - pd.Timedelta(days=lag)).strftime("%Y-%m-%d")

    def value_at(self, kind: str, feature: str, entity_id: str, date: pd.Timestamp,
                 window: str | None = None) -> float:
        """Latest-cached lookup into the wide feature matrix (avoids O(n^2) scans)."""
        w = self.wide(kind, feature, window)
        if w.empty or entity_id not in w.columns:
            return float("nan")
        try:
            return _safe_float(w.at[date, entity_id])
        except KeyError:
            return float("nan")

    def meta_for(self, entity_id: str) -> dict[str, Any]:
        universe = load_universe()
        spec = universe.instruments.get(entity_id)
        if spec:
            return {"asset_class": spec.asset_class, "region": spec.region, "importance": spec.importance,
                    "liquidity": spec.liquidity}
        for cid, cdef in load_curves().items():
            if entity_id.startswith(cid + ":"):
                return {"asset_class": "fixed_income", "region": cdef.region, "importance": 0.7,
                        "liquidity": "very_high"}
        macro = load_macro()
        if entity_id in macro:
            m = macro[entity_id]
            return {"asset_class": "macro", "region": m.region, "importance": m.importance,
                    "liquidity": "none"}
        pos = load_positioning_items()
        if entity_id in pos:
            return {"asset_class": "positioning", "region": "WORLD", "importance": pos[entity_id].importance,
                    "liquidity": "none"}
        return {"asset_class": "unknown", "region": "WORLD", "importance": 0.3, "liquidity": "none"}


# ------------------------------------------------------------------- utilities
def emit_rows(
    ctx: DetectorContext,
    values: pd.DataFrame,
    mask: pd.DataFrame,
    *,
    detector: str,
    family: str,
    entity_kind: str,
    window: str,
    direction: str | Callable[[float], str],
    score_fn: Callable[[float], float],
    evidence_fn: Callable[[str, pd.Timestamp, float], dict[str, Any]],
    percentile: pd.DataFrame | None = None,
    measure_name: str = "",
) -> pd.DataFrame:
    if values is None or values.empty or mask is None or mask.empty:
        return pd.DataFrame()
    mask = mask.reindex_like(values).fillna(False)
    stacked = mask.stack()
    idx = stacked[stacked.astype(bool)].index
    if len(idx) == 0:
        return pd.DataFrame()
    records = []
    for date, entity_id in idx:          # stack order is (row_index=date, column=entity)
        val = values.at[date, entity_id]
        if pd.isna(val):
            continue
        direction_value = direction(val) if callable(direction) else direction
        meta = ctx.meta_for(entity_id)
        src = ctx.sources.lookup(entity_id, entity_kind)
        pct_val = np.nan
        if percentile is not None and not percentile.empty and date in percentile.index:
            if entity_id in percentile.columns:
                pct_val = _safe_float(percentile.at[date, entity_id])
        avail = ctx.availability(entity_kind, entity_id, pd.Timestamp(date))
        evidence = evidence_fn(entity_id, date, _safe_float(val))
        _tier = (src or {}).get("tier", "derived")
        _dq = {"official": 1.0, "exchange": 0.9, "aggregator": 0.7, "proxy": 0.5}.get(_tier, 0.6)
        evidence.update({
            "detector": detector,
            "measure": measure_name,
            "measure_value": _safe_float(val),
            "entity_kind": entity_kind,
            "available_date": avail,
            "asset_class": meta.get("asset_class"),
            "region": meta.get("region"),
            "source": src,
            "data_quality": _dq,
        })
        records.append({
            "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
            "available_date": avail,
            "detector": detector,
            "family": family,
            "entity_id": entity_id,
            "entity_kind": entity_kind,
            "asset_class": meta.get("asset_class"),
            "region": meta.get("region"),
            "direction": direction_value,
            "window": window,
            "measure": measure_name,
            "magnitude": _safe_float(val),
            "score": _clip01(score_fn(float(val))),
            "percentile": pct_val,
            "evidence": evidence,
        })
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df["anomaly_id"] = [anomaly_id(detector, e, d, di, window)
                        for e, d, di in zip(df.entity_id, df.date, df.direction)]
    return df


# -------------------------------------------------------------------- detectors
class PriceReturnShock(Detector):
    name = "price_return_shock"
    family = "price"

    def detect(self) -> pd.DataFrame:
        cfg = self.ctx.cfg(self.name)
        out = []
        # 1-day shock
        w1 = self.ctx.wide("instrument", "return_z_1d_3y", "1d")
        if not w1.empty:
            p = cfg.get("windows", {}).get("1d", {"min": 3.0, "cap": 7.0})
            mask = w1.abs() >= p["min"]
            out.append(emit_rows(
                self.ctx, w1, mask, detector=self.name, family=self.family,
                entity_kind="instrument", window="1d",
                direction=lambda v: "up" if v > 0 else "down",
                score_fn=lambda v: (abs(v) - p["min"]) / (p["cap"] - p["min"]),
                evidence_fn=lambda e, d, v: {
                    "threshold": p["min"],
                    "formula": f"score=clip((|z_1d|-{p['min']})/({p['cap']}-{p['min']}),0,1)",
                    "raw": {"return_1d": self.ctx.value_at("instrument", "return", e, d, "1d")},
                },
                measure_name="return_z_1d_3y",
            ))
        # 1-month shock, additionally requiring a trailing-percentile extreme
        wm = self.ctx.wide("instrument", "return_z_3y", "1m")
        pct = self.ctx.wide("instrument", "return_pctile_5y", "1m")
        if not wm.empty and not pct.empty:
            p = cfg.get("windows", {}).get("1m", {"min": 2.0, "cap": 5.0})
            pct_ok = (pct <= (1 - cfg.get("min_percentile", 0.97))) | (pct >= cfg.get("min_percentile", 0.97))
            mask = (wm.abs() >= p["min"]) & pct_ok.reindex_like(wm).fillna(False)
            out.append(emit_rows(
                self.ctx, wm, mask, detector=self.name, family=self.family,
                entity_kind="instrument", window="1m",
                direction=lambda v: "up" if v > 0 else "down",
                score_fn=lambda v: (abs(v) - p["min"]) / (p["cap"] - p["min"]),
                evidence_fn=lambda e, d, v: {
                    "threshold": p["min"],
                    "formula": f"score=clip((|z_1m|-{p['min']})/({p['cap']}-{p['min']}),0,1)",
                    "raw": {"return_1m": self.ctx.value_at("instrument", "return", e, d, "1m"),
                            "return_pctile_5y": _safe_float(pct.at[d, e]) if e in pct.columns and d in pct.index else np.nan},
                },
                percentile=pct, measure_name="return_z_3y",
            ))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


class VolRegimeShift(Detector):
    name = "vol_regime_shift"
    family = "price"

    def detect(self) -> pd.DataFrame:
        cfg = self.ctx.cfg(self.name)
        w = self.ctx.wide("instrument", "vol_z_3y", "3m")
        if w.empty:
            return pd.DataFrame()
        mask = w.abs() >= cfg["min"]
        pct = self.ctx.wide("instrument", "vol_pctile_5y", "3m")
        return emit_rows(
            self.ctx, w, mask, detector=self.name, family=self.family, entity_kind="instrument",
            window="3m", direction=lambda v: "expansion" if v > 0 else "compression",
            score_fn=lambda v: (abs(v) - cfg["min"]) / (cfg["cap"] - cfg["min"]),
            evidence_fn=lambda e, d, v: {
                "threshold": cfg["min"],
                "formula": f"score=clip((|z_vol|-{cfg['min']})/({cfg['cap']}-{cfg['min']}),0,1)",
                "raw": {"vol_pctile_5y": _safe_float(pct.at[d, e]) if e in pct.columns and d in pct.index else np.nan},
            },
            percentile=pct, measure_name="vol_z_3y",
        )


class DrawdownExtreme(Detector):
    name = "drawdown_extreme"
    family = "price"

    def detect(self) -> pd.DataFrame:
        cfg = self.ctx.cfg(self.name)
        pct = self.ctx.wide("instrument", "drawdown_pctile_5y")
        dd = self.ctx.wide("instrument", "drawdown_252d")
        if pct.empty or dd.empty:
            return pd.DataFrame()
        # deep end requires an economically meaningful drawdown; near-high end does not
        mask = ((pct <= cfg["low"]) & (dd.reindex_like(pct).fillna(0.0) <= -0.10)) | (pct >= cfg["high"])
        return emit_rows(
            self.ctx, pct, mask, detector=self.name, family=self.family, entity_kind="instrument",
            window="252d", direction=lambda v: "deep_drawdown" if v <= 0.5 else "near_high",
            score_fn=lambda v: _clip01(1 - min(v, 1 - v) / 0.20),
            evidence_fn=lambda e, d, v: {
                "threshold": {"low": cfg["low"], "high": cfg["high"]},
                "formula": "score=clip(1-min(pct,1-pct)/0.20,0,1)",
                "raw": {"drawdown_252d": _safe_float(dd.at[d, e]) if e in dd.columns and d in dd.index else np.nan},
            },
            percentile=pct, measure_name="drawdown_pctile_5y",
        )


class TrendBreak(Detector):
    name = "trend_break"
    family = "price"

    def detect(self) -> pd.DataFrame:
        cfg = self.ctx.cfg(self.name)
        cross = self.ctx.wide("instrument", "ma_cross_50_200")
        gap = self.ctx.wide("instrument", "ma_gap_200d")
        if cross.empty:
            return pd.DataFrame()
        lookback = int(cfg.get("lookback_days", 10))
        # Evaluate each instrument on its own valid observations: a global row
        # shift(10) turns "market was closed 10 rows ago" into a fake cross.
        mask = pd.DataFrame(False, index=cross.index, columns=cross.columns)
        gap_aligned = gap.reindex_like(cross)
        for col in cross.columns:
            s = cross[col].dropna()
            if len(s) < lookback + 2:
                continue
            sign = np.sign(s)
            flipped = (sign != sign.shift(lookback)) & (sign != 0)
            for dt in s.index[flipped.fillna(False)]:
                g = gap_aligned.at[dt, col] if col in gap_aligned.columns else np.nan
                if np.isfinite(g) and abs(g) >= cfg.get("min_abs_gap", 0.01):
                    mask.at[dt, col] = True
        return emit_rows(
            self.ctx, cross, mask, detector=self.name, family=self.family, entity_kind="instrument",
            window=f"{lookback}d", direction=lambda v: "golden_cross" if v > 0 else "death_cross",
            score_fn=lambda v: 0.5,
            evidence_fn=lambda e, d, v: {
                "threshold": cfg.get("min_abs_gap", 0.01),
                "formula": "score=0.5 (binary trend-regime change)",
                "raw": {"ma_cross_50_200": v,
                        "ma_gap_200d": _safe_float(gap.at[d, e]) if e in gap.columns and d in gap.index else np.nan},
            },
            measure_name="ma_cross_50_200",
        )


class RelativeStrengthExtreme(Detector):
    name = "relative_strength_extreme"
    family = "industry"

    def detect(self) -> pd.DataFrame:
        cfg = self.ctx.cfg(self.name)
        out = []
        for wname in cfg.get("windows", ["1m", "3m"]):
            w = self.ctx.wide("instrument", "rel_strength_z_3y", wname)
            if w.empty:
                continue
            mask = w.abs() >= cfg["min_z"]
            out.append(emit_rows(
                self.ctx, w, mask, detector=self.name, family=self.family, entity_kind="instrument",
                window=wname, direction=lambda v: "outperform" if v > 0 else "underperform",
                score_fn=lambda v: (abs(v) - cfg["min_z"]) / (cfg["cap_z"] - cfg["min_z"]),
                evidence_fn=lambda e, d, v, wname=wname: {
                    "threshold": cfg["min_z"],
                    "formula": f"score=clip((|z|-{cfg['min_z']})/({cfg['cap_z']}-{cfg['min_z']}),0,1)",
                    "raw": {"rel_strength_vs_benchmark": self.ctx.value_at(
                        "instrument", "rel_strength_vs_benchmark", e, d, wname)},
                    "benchmark": _benchmark_of(e),
                },
                measure_name="rel_strength_z_3y",
            ))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


class BreadthExtreme(Detector):
    name = "breadth_extreme"
    family = "industry"

    def detect(self) -> pd.DataFrame:
        cfg = self.ctx.cfg(self.name)
        w = self.ctx.wide("region", "breadth_z_3y")
        out = []
        if not w.empty:
            mask = w.abs() >= cfg["min_abs_z"]
            out.append(emit_rows(
                self.ctx, w, mask, detector=self.name, family=self.family, entity_kind="region",
                window="", direction=lambda v: "broad_strength" if v > 0 else "broad_weakness",
                score_fn=lambda v: (abs(v) - cfg["min_abs_z"]) / (cfg["cap_abs_z"] - cfg["min_abs_z"]),
                evidence_fn=lambda e, d, v: {
                    "threshold": cfg["min_abs_z"],
                    "formula": f"score=clip((|z|-{cfg['min_abs_z']})/({cfg['cap_abs_z']}-{cfg['min_abs_z']}),0,1)",
                    "raw": {"breadth_above_ma200": self.ctx.value_at("region", "breadth_above_ma200", e, d)},
                },
                measure_name="breadth_z_3y",
            ))
        disp = self.ctx.wide("region", "us_sector_dispersion_1m")
        if not disp.empty and "US" in disp.columns:
            s = disp["US"].dropna()
            if len(s) > 260:
                med = s.rolling(260, min_periods=100).median()
                mad = (s - med).abs().rolling(260, min_periods=100).median() * 1.4826
                z = (s - med) / mad.replace(0, np.nan)
                zdf = z.to_frame("US")
                mask = zdf.abs() >= cfg.get("sector_dispersion_z", 2.0)
                out.append(emit_rows(
                    self.ctx, zdf, mask, detector=self.name + "_dispersion", family=self.family,
                    entity_kind="region", window="1m",
                    direction=lambda v: "high_dispersion" if v > 0 else "low_dispersion",
                    score_fn=lambda v: (abs(v) - 2.0) / 2.0,
                    evidence_fn=lambda e, d, v: {
                        "threshold": cfg.get("sector_dispersion_z", 2.0),
                        "formula": "score=clip((|z|-2)/2,0,1)",
                        "raw": {"us_sector_dispersion_1m": _safe_float(s.get(d, np.nan))},
                    },
                    measure_name="us_sector_dispersion_z",
                ))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


class ValuationExtreme(Detector):
    name = "valuation_extreme"
    family = "valuation"

    def detect(self) -> pd.DataFrame:
        cfg = self.ctx.cfg(self.name)
        out = []
        cape_pct = self.ctx.wide("valuation", "cape_pctile_10y")
        cape = self.ctx.wide("valuation", "cape_level")
        if not cape_pct.empty:
            mask = (cape_pct >= cfg["cape_pctile_high"]) | (cape_pct <= cfg["cape_pctile_low"])
            out.append(emit_rows(
                self.ctx, cape_pct, mask, detector=self.name, family=self.family, entity_kind="valuation",
                window="10y",
                direction=lambda v: "expensive" if v >= 0.5 else "cheap",
                score_fn=lambda v: (v - cfg["cape_pctile_high"]) / (1 - cfg["cape_pctile_high"])
                if v >= 0.5 else (cfg["cape_pctile_low"] - v) / cfg["cape_pctile_low"],
                evidence_fn=lambda e, d, v: {
                    "threshold": {"high": cfg["cape_pctile_high"], "low": cfg["cape_pctile_low"]},
                    "formula": "score=distance beyond 10y percentile band, normalised",
                    "raw": {"cape_level": _safe_float(cape.at[d, e]) if e in cape.columns and d in cape.index else np.nan},
                    "caveat": "CAPE is a slow-moving valuation gauge; extremes are not timing signals.",
                },
                percentile=cape_pct, measure_name="cape_pctile_10y",
            ))
        erp = self.ctx.wide("cross_asset", "equity_risk_premium", "level")
        if not erp.empty:
            pct = erp.rolling(60, min_periods=24).apply(lambda a: (a[:-1] < a[-1]).mean(), raw=True)
            mask = (pct <= cfg["erp_pctile_low"]) | (pct >= cfg["erp_pctile_high"])
            out.append(emit_rows(
                self.ctx, pct, mask, detector=self.name + "_erp", family=self.family,
                entity_kind="cross_asset", window="5y",
                direction=lambda v: "erp_tight" if v <= 0.5 else "erp_wide",
                score_fn=lambda v: (0.1 - v) / 0.1 if v <= 0.5 else (v - 0.9) / 0.1,
                evidence_fn=lambda e, d, v: {
                    "threshold": {"low": cfg["erp_pctile_low"], "high": cfg["erp_pctile_high"]},
                    "formula": "score=distance beyond 5y percentile band, normalised",
                    "raw": {"equity_risk_premium": _safe_float(erp.at[d, e]) if e in erp.columns and d in erp.index else np.nan},
                },
                percentile=pct, measure_name="erp_pctile_5y",
            ))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


class CurveChange(Detector):
    name = "curve_change"
    family = "macro"

    def detect(self) -> pd.DataFrame:
        """Benchmark yield moves (series level) plus slope/inversion (curve level)."""
        cfg = self.ctx.cfg(self.name)
        out = []
        z = self.ctx.wide("series", "z_level_3y")
        chg = self.ctx.wide("series", "change_21d")
        if not z.empty and not chg.empty:
            chg = chg.reindex(columns=[c for c in chg.columns if c in z.columns])
            # focus on government curve benchmark tenors
            bench = [c for c in z.columns if any(c.endswith(t) for t in (":2Y", ":5Y", ":10Y", ":30Y"))]
            z10 = z[bench] if bench else z
            chg21 = chg.reindex(columns=list(z10.columns))
            mask = (z10.abs() >= cfg["min_abs_z"]) & (
                chg21.abs().reindex_like(z10).fillna(0) >= cfg["slope_change_min_bp"] / 100
            )
            out.append(emit_rows(
                self.ctx, z10, mask, detector=self.name, family=self.family, entity_kind="series",
                window="1m", direction=lambda v: "yields_up" if v > 0 else "yields_down",
                score_fn=lambda v: (abs(v) - cfg["min_abs_z"]) / (cfg["cap_abs_z"] - cfg["min_abs_z"]),
                evidence_fn=lambda e, d, v: {
                    "threshold": {"z": cfg["min_abs_z"], "min_move_pp": cfg["slope_change_min_bp"] / 100},
                    "formula": f"score=clip((|z|-{cfg['min_abs_z']})/({cfg['cap_abs_z']}-{cfg['min_abs_z']}),0,1)",
                    "raw": {"yield_change_1m_pp": _safe_float(chg21.at[d, e])
                            if e in chg21.columns and d in chg21.index else np.nan},
                },
                measure_name="z_level_3y",
            ))
        slope_z = self.ctx.wide("curve", "slope_2s10s_z_3y")
        slope_chg = self.ctx.wide("curve", "slope_2s10s_change_1m", "1m")
        if not slope_z.empty and not slope_chg.empty:
            mask = (slope_z.abs() >= cfg["min_abs_z"]) & (
                slope_chg.abs().reindex_like(slope_z).fillna(0) >= cfg["slope_change_min_bp"] / 100
            )
            out.append(emit_rows(
                self.ctx, slope_z, mask, detector=self.name + "_slope", family=self.family,
                entity_kind="curve", window="1m",
                direction=lambda v: "steepening" if v > 0 else "flattening",
                score_fn=lambda v: (abs(v) - cfg["min_abs_z"]) / (cfg["cap_abs_z"] - cfg["min_abs_z"]),
                evidence_fn=lambda e, d, v: {
                    "threshold": {"z": cfg["min_abs_z"], "min_move_pp": cfg["slope_change_min_bp"] / 100},
                    "formula": f"score=clip((|z|-{cfg['min_abs_z']})/({cfg['cap_abs_z']}-{cfg['min_abs_z']}),0,1)",
                    "raw": {"slope_2s10s_change_1m_pp": _safe_float(slope_chg.at[d, e])
                            if e in slope_chg.columns and d in slope_chg.index else np.nan,
                            "slope_2s10s": self.ctx.value_at("curve", "slope_2s10s", e, d)},
                },
                measure_name="slope_2s10s_z_3y",
            ))
        inv = self.ctx.wide("curve", "curve_inverted")
        if not inv.empty:
            flipped = (inv != inv.shift(1)) & inv.notna() & inv.shift(1).notna()
            recent = flipped.rolling(int(cfg.get("inversion_flip_lookback", 20)), min_periods=1).max().astype(bool)
            out.append(emit_rows(
                self.ctx, inv, recent, detector=self.name + "_inversion", family=self.family,
                entity_kind="curve", window="state_change",
                direction=lambda v: "inverted" if v > 0 else "re_normalised",
                score_fn=lambda v: 0.9,
                evidence_fn=lambda e, d, v: {
                    "threshold": "state change within lookback window",
                    "formula": "score=0.9 (regime state change)",
                    "raw": {"curve_inverted": v},
                },
                measure_name="curve_inverted",
            ))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


class CreditStress(Detector):
    name = "credit_stress"
    family = "macro"

    def detect(self) -> pd.DataFrame:
        cfg = self.ctx.cfg(self.name)
        z = self.ctx.wide("risk", "hy_minus_treasury_z_3y")
        if z.empty:
            return pd.DataFrame()
        mask = z.abs() >= cfg["min_abs_z"]
        return emit_rows(
            self.ctx, z, mask, detector=self.name, family=self.family, entity_kind="risk",
            window="3y", direction=lambda v: "hy_outperform" if v > 0 else "hy_underperform",
            score_fn=lambda v: (abs(v) - cfg["min_abs_z"]) / (cfg["cap_abs_z"] - cfg["min_abs_z"]),
            evidence_fn=lambda e, d, v: {
                "threshold": cfg["min_abs_z"],
                "formula": f"score=clip((|z|-{cfg['min_abs_z']})/({cfg['cap_abs_z']}-{cfg['min_abs_z']}),0,1)",
                "raw": {"hy_minus_treasury_1m": _feature_at(self.ctx.fs, "risk", "hy_minus_treasury_1m", e, d),
                        "note": "Proxy: HYG vs IEF total return. Not a direct OAS spread."},
            },
            measure_name="hy_minus_treasury_z_3y",
        )


class CrossAssetDivergence(Detector):
    name = "cross_asset_divergence"
    family = "cross_asset"

    def detect(self) -> pd.DataFrame:
        cfg = self.ctx.cfg(self.name)
        z = self.ctx.wide("cross_asset", "corr_z_3y")
        if z.empty:
            return pd.DataFrame()
        mask = z.abs() >= cfg["min_abs_z"]
        corr = self.ctx.wide("cross_asset", "corr_63d")
        return emit_rows(
            self.ctx, z, mask, detector=self.name, family=self.family, entity_kind="cross_asset",
            window="63d", direction=lambda v: "corr_break_up" if v > 0 else "corr_break_down",
            score_fn=lambda v: (abs(v) - cfg["min_abs_z"]) / (cfg["cap_abs_z"] - cfg["min_abs_z"]),
            evidence_fn=lambda e, d, v: {
                "threshold": cfg["min_abs_z"],
                "formula": f"score=clip((|z|-{cfg['min_abs_z']})/({cfg['cap_abs_z']}-{cfg['min_abs_z']}),0,1)",
                "raw": {"corr_63d": _safe_float(corr.at[d, e]) if e in corr.columns and d in corr.index else np.nan},
                "pair": e,
            },
            measure_name="corr_z_3y",
        )


class MacroShift(Detector):
    name = "macro_shift"
    family = "macro"

    def detect(self) -> pd.DataFrame:
        cfg = self.ctx.cfg(self.name)
        z = self.ctx.wide("macro", "z_3y")
        chg = self.ctx.wide("macro", "change_3p")
        if z.empty:
            return pd.DataFrame()
        exclude = set(cfg.get("exclude_series", []))
        cols = [c for c in z.columns if c not in exclude]
        if not cols:
            return pd.DataFrame()
        z = z[cols]
        chg = chg.reindex(columns=[c for c in chg.columns if c in cols])
        mask = (z.abs() >= cfg["min_abs_z"]) & (chg.abs().reindex_like(z).fillna(0) >= cfg["min_abs_change_3p"])
        return emit_rows(
            self.ctx, z, mask, detector=self.name, family=self.family, entity_kind="macro",
            window="3p", direction=lambda v: "above_norm" if v > 0 else "below_norm",
            score_fn=lambda v: (abs(v) - cfg["min_abs_z"]) / (cfg["cap_abs_z"] - cfg["min_abs_z"]),
            evidence_fn=lambda e, d, v: {
                "threshold": {"z": cfg["min_abs_z"], "min_change": cfg["min_abs_change_3p"]},
                "formula": f"score=clip((|z|-{cfg['min_abs_z']})/({cfg['cap_abs_z']}-{cfg['min_abs_z']}),0,1)",
                "raw": {"change_3p": _safe_float(chg.at[d, e]) if e in chg.columns and d in chg.index else np.nan,
                        "value": self.ctx.value_at("macro", "value", e, d)},
            },
            measure_name="z_3y",
        )


class PositioningExtreme(Detector):
    name = "positioning_extreme"
    family = "positioning"

    def detect(self) -> pd.DataFrame:
        cfg = self.ctx.cfg(self.name)
        pct = self.ctx.wide("positioning", "net_pctile_5y")
        if pct.empty:
            return pd.DataFrame()
        mask = (pct <= cfg["pctile_low"]) | (pct >= cfg["pctile_high"])
        net = self.ctx.wide("positioning", "net_position")
        return emit_rows(
            self.ctx, pct, mask, detector=self.name, family=self.family, entity_kind="positioning",
            window="5y", direction=lambda v: "crowded_long" if v >= 0.5 else "crowded_short",
            score_fn=lambda v: (cfg["pctile_high"] - v) / cfg["pctile_high"] if v <= 0.5
            else (v - cfg["pctile_high"]) / (1 - cfg["pctile_high"]),
            evidence_fn=lambda e, d, v: {
                "threshold": {"low": cfg["pctile_low"], "high": cfg["pctile_high"]},
                "formula": "score=distance beyond 5y percentile band, normalised",
                "raw": {"net_position": _safe_float(net.at[d, e]) if e in net.columns and d in net.index else np.nan},
                "note": "COT report as of Tuesday, published Friday; a 4-day lag is applied upstream.",
            },
            percentile=pct, measure_name="net_pctile_5y",
        )


class RiskAppetiteShift(Detector):
    name = "risk_appetite_shift"
    family = "cross_asset"

    def detect(self) -> pd.DataFrame:
        cfg = self.ctx.cfg(self.name)
        out = []
        term = self.ctx.wide("risk", "vix_over_vix3m")
        pct = self.ctx.wide("risk", "pctile_5y")
        z_all = self.ctx.wide("risk", "z_3y")
        if not term.empty:
            z = z_all.reindex(columns=[c for c in term.columns if c in z_all.columns])
            mask = (z.abs() >= cfg["vix_term_min_abs_z"]) & (term > 1.0)
            out.append(emit_rows(
                self.ctx, z, mask, detector=self.name, family=self.family, entity_kind="risk",
                window="63d", direction=lambda v: "term_inverted",
                score_fn=lambda v: (abs(v) - cfg["vix_term_min_abs_z"]) / (4.0 - cfg["vix_term_min_abs_z"]),
                evidence_fn=lambda e, d, v: {
                    "threshold": cfg["vix_term_min_abs_z"],
                    "formula": "score=clip((|z|-1.5)/(4-1.5),0,1)",
                    "raw": {"vix_over_vix3m": _safe_float(term.at[d, e]) if e in term.columns and d in term.index else np.nan},
                },
                measure_name="vix_term_z_3y",
            ))
        if not pct.empty:
            vix_cols = [c for c in pct.columns if c in ("VIX",)]
            if vix_cols:
                sub = pct[vix_cols]
                mask = sub >= cfg["vix_pctile_high"]
                out.append(emit_rows(
                    self.ctx, sub, mask, detector=self.name + "_vix", family=self.family,
                    entity_kind="risk", window="5y", direction=lambda v: "stress",
                    score_fn=lambda v: (v - cfg["vix_pctile_high"]) / (1 - cfg["vix_pctile_high"]),
                    evidence_fn=lambda e, d, v: {
                        "threshold": cfg["vix_pctile_high"],
                        "formula": "score=(pctile-0.9)/0.1",
                        "raw": {"vix_pctile_5y": v},
                    },
                    percentile=sub, measure_name="vix_pctile_5y",
                ))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


class PolicyRateChange(Detector):
    """Actual policy-rate actions (cuts/hikes) by major central banks.

    A change of the policy rate is a *decision*, not a statistical outlier: robust
    z-scores on a step function are uninformative (the level jumps and stays).
    This detector flags changes >= 5bp over the last 45 days directly, with the
    before/after values in the evidence payload.
    """

    name = "policy_rate_change"
    family = "macro"

    def detect(self) -> pd.DataFrame:
        cfg = self.ctx.cfg(self.name) or {"min_change_pp": 0.05, "lookback_days": 45}
        macro_ids = [m for m in ("US_POLICY_RATE", "EA_POLICY_RATE", "JP_POLICY_RATE",
                                 "CN_POLICY_RATE", "UK_POLICY_RATE")]
        wide = self.ctx.wide("macro", "value")
        out = []
        for mid in macro_ids:
            if mid not in wide.columns:
                continue
            s = wide[mid].dropna()
            if s.empty:
                continue
            chg = s.diff(int(cfg.get("lookback_days", 45)) // 30 or 1)
            vals = chg.to_frame(mid)
            mask = (vals.abs() >= float(cfg.get("min_change_pp", 0.05)))
            out.append(emit_rows(
                self.ctx, vals, mask, detector=self.name, family=self.family,
                entity_kind="macro", window="policy_action",
                direction=lambda v: "cut" if v < 0 else "hike",
                score_fn=lambda v: min(1.0, abs(v) / 0.50),
                evidence_fn=lambda e, d, v: {
                    "threshold_pp": cfg.get("min_change_pp", 0.05),
                    "formula": "score=clip(|change_pp|/0.50,0,1)",
                    "raw": {"policy_rate_level": float(s.get(d, float("nan"))),
                            "change_pp": v},
                    "note": "中央行政策利率变动（BIS 政策利率序列），非统计异常。",
                },
                measure_name="policy_rate_change_pp",
            ))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


DETECTORS: list[type[Detector]] = [
    PriceReturnShock, VolRegimeShift, DrawdownExtreme, TrendBreak,
    RelativeStrengthExtreme, BreadthExtreme, ValuationExtreme, CurveChange,
    CreditStress, CrossAssetDivergence, MacroShift, PositioningExtreme,
    RiskAppetiteShift, PolicyRateChange,
]


# -------------------------------------------------------------------- helpers
def _raw_return(fs: FeatureSet, entity_id: str, date: pd.Timestamp, window: str) -> float:
    return _feature_at(fs, "instrument", "return", entity_id, date, window)


def _feature_at(fs: FeatureSet, kind: str, feature: str, entity_id: str, date: pd.Timestamp,
                window: str | None = None) -> float:
    df = fs.long
    m = (df.entity_kind == kind) & (df.feature == feature) & (df.entity_id == entity_id) & (df.date == str(date.date()))
    if window is not None:
        m &= df.window == window
    sub = df[m]
    return _safe_float(sub["value"].iloc[-1]) if len(sub) else float("nan")


def _benchmark_of(entity_id: str) -> str:
    spec = load_universe().instruments.get(entity_id)
    if not spec:
        return ""
    return load_universe().resolve_benchmark(spec) or ""


# ------------------------------------------------------------------- driver
def detect_anomalies(fs: FeatureSet, thresholds: dict[str, Any] | None = None,
                     detectors: Iterable[type[Detector]] | None = None,
                     since: str | None = None) -> pd.DataFrame:
    # IMPORTANT: do NOT truncate the long frame before detection. Windowed
    # detectors (trend_break shift(10), percentile windows, ...) need the pre-window
    # history; truncating first creates false signals at the window boundary.
    # Filter the *emitted anomalies* to the requested window, after detection.
    ctx = DetectorContext(fs, thresholds)
    frames: list[pd.DataFrame] = []
    errors: list[str] = []
    for det_cls in (detectors or DETECTORS):
        try:
            df = det_cls(ctx).detect()
            if df is not None and not df.empty:
                frames.append(df)
        except Exception as exc:  # noqa: BLE001 - one detector must not kill the scan
            errors.append(f"{det_cls.name}: {type(exc).__name__}: {exc}")
    if not frames:
        out = pd.DataFrame()
    else:
        out = pd.concat(frames, ignore_index=True)
        if since and not out.empty:
            out = out[out["date"] >= since].copy()
        out = _apply_flood_control(out, ctx)
    out.attrs["errors"] = errors
    out.attrs["n_detectors"] = len(list(detectors or DETECTORS))
    return out


def _apply_flood_control(df: pd.DataFrame, ctx: DetectorContext) -> pd.DataFrame:
    if df.empty:
        return df
    gcfg = ctx.thresholds.get("flood_control", {})
    max_family = int(gcfg.get("max_anomalies_per_family", ctx.global_cfg.get("max_anomalies_per_family", 60)))
    max_entity = int(gcfg.get("max_anomalies_per_entity", ctx.global_cfg.get("max_anomalies_per_entity", 4)))
    dedupe_days = int(gcfg.get("dedupe_within_days", 5))

    df = df.sort_values(["date", "score"], ascending=[True, False]).copy()
    kept: list[pd.DataFrame] = []
    for date, group in df.groupby("date", sort=True):
        g = group.sort_values("score", ascending=False)
        # per-entity cap
        g = g.groupby("entity_id", group_keys=False, sort=False).head(max_entity)
        # expose family separately for downstream reporting while capping
        g = g.groupby("family", group_keys=False, sort=False).head(max_family)
        kept.append(g)
    out = pd.concat(kept, ignore_index=True)
    # Cross-day dedupe: same detector+entity+direction within N days is ONE event.
    # The kept row is the highest-score observation in the run (not merely the
    # first), because the first occurrence may be a weak precursor.
    out["dedupe_date"] = pd.to_datetime(out["date"])
    out = out.sort_values(["detector", "entity_id", "direction", "dedupe_date"]).reset_index(drop=True)
    keep_rows: list[int] = []
    run_best: int | None = None
    run_last: pd.Timestamp | None = None
    run_key: tuple[str, str, str] | None = None
    for idx, row in out.iterrows():
        key = (row.detector, row.entity_id, row.direction)
        if key != run_key or run_last is None or (row.dedupe_date - run_last).days > dedupe_days:
            if run_best is not None:
                keep_rows.append(run_best)
            run_best = int(idx)
            run_key = key
        else:
            if float(row.score) > float(out.loc[run_best, "score"]):
                run_best = int(idx)
        run_last = row.dedupe_date
    if run_best is not None:
        keep_rows.append(run_best)
    out = out.loc[keep_rows].drop(columns=["dedupe_date"]).reset_index(drop=True)
    return out


def summarize(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"n": 0, "by_family": {}, "by_detector": {}, "top": []}
    latest = df[df.date == df.date.max()]
    return {
        "n": int(len(df)),
        "n_latest": int(len(latest)),
        "by_family": df.family.value_counts().to_dict(),
        "by_detector": df.detector.value_counts().to_dict(),
        "top": latest.sort_values("score", ascending=False).head(10)[
            ["date", "detector", "entity_id", "direction", "score"]
        ].to_dict("records"),
    }
