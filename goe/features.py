"""Feature engineering: the measurable state of every market and macro series.

Design principles
-----------------
* **Point in time.** ``FeatureBuilder(store, as_of=...)`` only sees rows with
  ``date <= as_of``. Macro releases additionally respect a conservative
  publication lag (``RELEASE_LAG_DAYS``), so a replay never uses a CPI print
  before it was published.
* **No imputation of market data.** A window shorter than the required minimum
  yields ``NaN``, never a shorter-window substitute.
* **Explicit, versioned methods.** ``FEATURE_VERSION`` is stored with every
  computation so a scan result can be reproduced later.
* **The feature layer is descriptive.** No feature says "cheap" or "opportunity";
  detectors (``goe.anomalies``) apply thresholds and the opportunity layer
  interprets them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

import numpy as np
import pandas as pd

from .config import MacroSeries, load_curves, load_macro, load_positioning, load_universe
from .db import Store

FEATURE_VERSION = "v1"

# Conservative publication lags (calendar days) used only when replaying history.
# Values are deliberately longer than typical release calendars; the cost is a
# small delay in recognizing a macro print, the benefit is no lookahead.
RELEASE_LAG_DAYS = {"daily": 0, "weekly": 4, "monthly": 45, "quarterly": 120, "annual": 180}

TRADING_WINDOWS = {"1w": 5, "1m": 21, "3m": 63, "6m": 126, "12m": 252}

# A series whose latest observation is older than this is treated as unavailable
# at the as-of date instead of being forward-filled. This prevents a stale
# print (e.g. a discontinued workbook) from being presented as current evidence.
STALE_AFTER_DAYS = {"daily": 20, "weekly": 45, "monthly": 110, "quarterly": 280, "annual": 400}
RETURN_WINDOWS = {"1d": 1, "1w": 5, "1m": 21, "3m": 63, "6m": 126, "12m": 252}
VOL_WINDOWS = {"1m": 21, "3m": 63, "12m": 252}


# ------------------------------------------------------------------------- utils
def _sliding(x: pd.Series, window: int) -> np.ndarray:
    from numpy.lib.stride_tricks import sliding_window_view

    arr = x.to_numpy(dtype=float)
    if len(arr) < window:
        return np.empty((0, window))
    return sliding_window_view(arr, window)


def robust_z(x: pd.Series, window: int, min_periods: int | None = None) -> pd.Series:
    """Robust z-score against a trailing window: (x - median) / (1.4826 * MAD).

    Exactly matches the documented definition: median and MAD are computed inside
    each trailing window (not a median of rolling medians). Implemented with a
    vectorised sliding window; a std-based scale is used only when MAD collapses
    (constant stretches), which is recorded by construction rather than hidden.
    """
    from numpy.lib.stride_tricks import sliding_window_view

    min_periods = min_periods or max(6, window // 5)
    min_periods = min(min_periods, max(2, window))
    arr = x.to_numpy(dtype=float)
    n = len(arr)
    out = np.full(n, np.nan)
    if n < min_periods:
        return pd.Series(out, index=x.index, name=x.name)
    win = _sliding(x, window)
    if win.size:
        med = np.nanmedian(win, axis=1)
        mad = np.nanmedian(np.abs(win - med[:, None]), axis=1)
        valid = np.isfinite(win).sum(axis=1) >= min_periods
        scale = 1.4826 * mad
        std = np.nanstd(win, axis=1, ddof=1)
        scale = np.where((scale <= 0) | ~np.isfinite(scale), std, scale)
        last = win[:, -1]
        with np.errstate(invalid="ignore", divide="ignore"):
            z = (last - med) / scale
        z[~valid | ~np.isfinite(z)] = np.nan
        start = window - 1
        out[start:start + len(z)] = z
    # Rows before the first full window use *expanding* windows from
    # min_periods upwards (documented: min_periods is the minimum number of
    # observations required, not a requirement to have a full window).
    for i in range(min_periods - 1, min(window - 1, n)):
        seg = arr[: i + 1]
        seg = seg[np.isfinite(seg)]
        if len(seg) < 2:
            continue
        m = float(np.median(seg))
        mad = float(np.median(np.abs(seg - m)))
        scale = 1.4826 * mad if mad > 0 else float(np.std(seg, ddof=1))
        if scale and np.isfinite(scale):
            out[i] = (arr[i] - m) / scale
    return pd.Series(out, index=x.index, name=x.name)


def rolling_percentile(x: pd.Series, window: int, min_periods: int | None = None) -> pd.Series:
    """Percentile of the latest value within up to `window` trailing observations.

    Uses the rank of the current value: ``(rank - 1) / (n - 1)`` where ``n`` is
    the number of observations in the window. For distinct values this equals
    "share of the window strictly below the latest value" and lies in [0, 1].
    Partial windows are supported (``min_periods``), so instruments with shorter
    history still get a percentile once ``min_periods`` observations exist.
    """
    min_periods = min_periods or max(6, window // 5)
    min_periods = min(min_periods, max(2, window))
    roll = x.rolling(window, min_periods=min_periods)
    rank = roll.rank(pct=False)
    count = roll.count()
    pct = (rank - 1) / (count - 1).replace(0, np.nan)
    pct[count < 2] = np.nan
    return pct


def ann_vol(rets: pd.Series, window: int) -> pd.Series:
    return rets.rolling(window, min_periods=max(10, window // 3)).std() * math.sqrt(252)


def drawdown_from_high(px: pd.Series, window: int) -> pd.Series:
    high = px.rolling(window, min_periods=max(20, window // 4)).max()
    return px / high - 1.0


def safe_pct_change(s: pd.Series, periods: int) -> pd.Series:
    return s.pct_change(periods, fill_method=None)


def _last_valid(s: pd.Series) -> float:
    s = s.dropna()
    return float(s.iloc[-1]) if len(s) else float("nan")


# ----------------------------------------------------------------- price cleaning
_SPLIT_FACTORS = (2.0, 3.0, 4.0, 5.0, 10.0, 20.0, 0.5, 1 / 3, 0.25, 0.2, 0.1, 0.05)
_MAX_MOVE = {"volatility": 2.0, "crypto": 0.8, "fx": 0.25, "commodity": 0.5}


def clean_price_panel(px: pd.DataFrame, universe) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Remove non-positive prices and repair/quarantine data glitches.

    Operates on the sequence of *valid* observations (weekends/holidays are not
    rows), so a gap cannot hide a jump. Rules:

    * price <= 0 -> NaN (e.g. WTI 2020-04-20; percentage returns are undefined).
    * a move beyond the asset-class threshold is suspicious:
        - split-like ratio AND immediate continuity afterwards -> rebase prior
          observations (corporate action);
        - otherwise the whole anomalous window (jump plus any compensating
          reversal until the price returns near the pre-jump level) is
          quarantined, so the series is never left on two price bases.
    * every action is returned as a data-quality record.
    """
    out = px.copy()
    issues: list[dict[str, Any]] = []
    for iid in out.columns:
        spec = universe.instruments.get(iid) if universe is not None else None
        asset_class = spec.asset_class if spec else "equity_etf"
        threshold = _MAX_MOVE.get(asset_class, 0.40)

        s = out[iid]
        nonpos = s.index[s <= 0]
        if len(nonpos):
            out.loc[nonpos, iid] = np.nan
            issues.append({"instrument_id": iid, "kind": "nonpositive_price",
                           "dates": [d.strftime("%Y-%m-%d") for d in nonpos[:10]],
                           "count": int(len(nonpos))})

        guard = 0
        while guard < 200:
            guard += 1
            valid = out[iid].dropna()
            if len(valid) < 3:
                break
            rets = valid.pct_change(fill_method=None)
            hits = rets[rets.abs() > threshold]
            if hits.empty:
                break
            dt = hits.index[0]
            pos = int(valid.index.get_loc(dt))
            prev, cur = float(valid.iloc[pos - 1]), float(valid.iloc[pos])
            ratio = cur / prev
            matched = None
            if asset_class in ("equity_etf", "sector_equity"):
                matched = next((f for f in _SPLIT_FACTORS if abs(ratio / f - 1.0) <= 0.02), None)
            continuous = False
            if matched is not None and pos + 1 < len(valid):
                # A genuine split preserves continuity over the following
                # observations too; a glitch pair (drop then recovery) does not.
                window = valid.iloc[pos:pos + 6].to_numpy(dtype=float)
                hops = np.abs(window[1:] / window[:-1] - 1.0) if len(window) > 1 else np.array([])
                continuous = bool(len(hops) and np.nanmax(hops) <= threshold)
            if matched is not None and continuous:
                out.loc[valid.index[:pos], iid] = valid.iloc[:pos].to_numpy() * ratio
                issues.append({"instrument_id": iid, "kind": "split_adjusted",
                               "date": dt.strftime("%Y-%m-%d"), "ratio": round(float(ratio), 6)})
                continue
            # quarantine: from the jump until price is back near the pre-jump level
            reference = prev
            bad_dates = [valid.index[pos]]
            j = pos + 1
            while j < len(valid):
                v = float(valid.iloc[j])
                if abs(v / reference - 1.0) <= threshold:
                    break
                bad_dates.append(valid.index[j])
                j += 1
            out.loc[bad_dates, iid] = np.nan
            issues.append({"instrument_id": iid, "kind": "extreme_move_quarantined",
                           "date": dt.strftime("%Y-%m-%d"),
                           "dates": [d.strftime("%Y-%m-%d") for d in bad_dates],
                           "move": round(float(rets.loc[dt]), 4), "threshold": threshold})
    return out, issues


# ------------------------------------------------------------------- containers
@dataclass
class FeatureSet:
    as_of: str
    long: pd.DataFrame                      # entity_kind, entity_id, feature, window, value
    prices: pd.DataFrame                    # wide adj close (truncated)
    returns: pd.DataFrame                   # wide daily simple returns
    curve: dict[str, pd.DataFrame]          # curve_id -> wide tenor matrix
    macro: pd.DataFrame                     # wide macro levels as published
    positioning: pd.DataFrame               # wide net positions
    meta: dict[str, Any] = field(default_factory=dict)

    _index: dict | None = field(default=None, repr=False)

    def _indexed(self) -> dict:
        """Lazy (entity, feature, window) -> (dates, values) index.

        The long frame has millions of rows; calling ``value`` hundreds of times
        per scan must not re-filter it. The index is built once per FeatureSet.
        """
        if getattr(self, "_index", None) is None:
            idx: dict = {}
            grp = self.long.groupby(["entity_id", "feature", "window"], sort=False)
            for (entity, feature, window), sub in grp:
                sub = sub.sort_values("date")
                idx[(entity, feature, window)] = (sub["date"].to_numpy(), sub["value"].to_numpy())
            self._index = idx
        return self._index

    def frame(self) -> pd.DataFrame:
        return self.long

    def value(self, entity_id: str, feature: str, window: str = "") -> float:
        d = self._indexed().get((entity_id, feature, window))
        if not d:
            return float("nan")
        _, vals = d
        return float(vals[-1]) if len(vals) else float("nan")

    def series(self, entity_id: str, feature: str, window: str = "") -> pd.Series:
        d = self._indexed().get((entity_id, feature, window))
        if not d:
            return pd.Series(dtype=float)
        dates, vals = d
        return pd.Series(vals, index=pd.to_datetime(dates))

    def entities(self, kind: str) -> list[str]:
        return sorted(self.long.loc[self.long.entity_kind == kind, "entity_id"].unique())

    def save(self, directory: str) -> str:
        from pathlib import Path

        p = Path(directory)
        p.mkdir(parents=True, exist_ok=True)
        target = p / f"features_{self.as_of}_{FEATURE_VERSION}.parquet"
        self.long.to_parquet(target, index=False)
        return str(target)


# -------------------------------------------------------------------- builder
class FeatureBuilder:
    """Compute the descriptive feature layer for a single as-of date."""

    def __init__(self, store: Store, as_of: str | None = None, *, point_in_time: bool = True,
                 min_history_days: int = 504, history_start: str | None = None):
        self.store = store
        self.universe = load_universe()
        self.curves = load_curves()
        self.macro_defs: dict[str, MacroSeries] = load_macro()
        self.positioning_defs = load_positioning()
        self.point_in_time = point_in_time
        self.min_history = min_history_days
        self.history_start = history_start

        last_date = store.scalar("SELECT MAX(date) FROM prices")
        if as_of is None:
            if not last_date:
                raise RuntimeError("no price data in store; run `goe ingest` first")
            as_of = last_date
        self.as_of = str(as_of)
        if last_date and self.as_of > last_date:
            # scanning a future date would silently use stale data; clamp instead
            self.as_of = last_date

    # ------------------------------------------------------------------ loaders
    def _load_prices(self) -> pd.DataFrame:
        ids = list(self.universe.instruments)
        px = self.store.load_prices(ids, end=self.as_of)
        if px.empty:
            raise RuntimeError("price panel empty for as-of date")
        # keep instruments with at least the minimum useful history
        px = px.loc[:, px.notna().sum() >= min(self.min_history, 120)]
        if self.history_start:
            px = px.loc[px.index >= pd.Timestamp(self.history_start)]
        return px

    def _load_curves(self) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        for cid, cdef in self.curves.items():
            series_ids = [f"{cid}:{t}" for t in cdef.tenors]
            wide = self.store.load_indicators_wide(series_ids, end=self.as_of)
            if wide.empty:
                continue
            wide.columns = [c.split(":", 1)[1] for c in wide.columns]
            out[cid] = wide.dropna(how="all")
        return out

    def _load_macro(self) -> pd.DataFrame:
        ids = list(self.macro_defs)
        wide = self.store.load_indicators_wide(ids, end=self.as_of)
        if wide.empty:
            return wide
        as_of_dt = pd.Timestamp(self.as_of)
        kept: dict[str, pd.Series] = {}
        stale: dict[str, int] = {}
        for sid in wide.columns:
            s = wide[sid].dropna()
            if s.empty:
                continue
            freq = self.macro_defs[sid].frequency if sid in self.macro_defs else "monthly"
            age = int((as_of_dt - pd.Timestamp(s.index.max())).days)
            if age > STALE_AFTER_DAYS.get(freq, 110):
                stale[sid] = age
                continue
            kept[sid] = wide[sid]
        self.stale_macro = stale
        wide = pd.DataFrame(kept) if kept else pd.DataFrame()
        if wide.empty:
            return wide
        if not self.point_in_time:
            return wide
        # Point-in-time filter: an observation is visible only after its
        # publication lag. The observation date itself is preserved so that
        # monthly series keep a monthly index (important for rolling windows).
        adjusted: dict[str, pd.Series] = {}
        as_of_dt = pd.Timestamp(self.as_of)
        for sid in wide.columns:
            freq = self.macro_defs[sid].frequency if sid in self.macro_defs else "monthly"
            lag = RELEASE_LAG_DAYS.get(freq, 45)
            s = wide[sid].dropna()
            if s.empty:
                continue
            obs_dates = pd.to_datetime(s.index)
            available = obs_dates + pd.Timedelta(days=lag)
            visible = available <= as_of_dt
            if not visible.any():
                continue
            adjusted[sid] = pd.Series(s.values[visible], index=obs_dates[visible])
        return pd.DataFrame(adjusted) if adjusted else pd.DataFrame()

    def _load_positioning(self) -> pd.DataFrame:
        ids = [f"{pid}" for pid in self.positioning_defs]
        wide = self.store.load_indicators_wide(ids, end=self.as_of)
        if wide.empty:
            return wide
        if self.point_in_time:
            # COT is as-of Tuesday, published Friday: 4 calendar day lag
            wide.index = pd.to_datetime(wide.index) + pd.Timedelta(days=4)
        return wide

    # -------------------------------------------------------------------- build
    def build(self) -> FeatureSet:
        px = self._load_prices()
        px, self.price_issues = clean_price_panel(px, self.universe)
        rets = px.pct_change(fill_method=None)
        curves = self._load_curves()
        macro = self._load_macro()
        pos = self._load_positioning()

        rows: list[pd.DataFrame] = []
        rows.append(self._price_features(px, rets))
        rows.append(self._relative_strength(px, rets))
        rows.append(self._breadth(px))
        rows.append(self._curve_features(curves))
        rows.append(self._indicator_features(curves, macro, pos))
        rows.append(self._cross_asset_features(px, rets, curves))
        rows.append(self._valuation_features(macro))
        rows.append(self._positioning_features(pos))
        rows.append(self._macro_features(macro))
        rows.append(self._risk_features(px, rets))

        long = pd.concat([r for r in rows if r is not None and not r.empty], ignore_index=True)
        long = long.replace([np.inf, -np.inf], np.nan).dropna(subset=["value"])
        long["date"] = pd.to_datetime(long["date"]).dt.strftime("%Y-%m-%d")
        long["method_version"] = FEATURE_VERSION
        long = long.sort_values(["entity_kind", "entity_id", "feature", "date"]).reset_index(drop=True)

        return FeatureSet(
            as_of=self.as_of, long=long, prices=px, returns=rets, curve=curves,
            macro=macro, positioning=pos,
            meta={
                "as_of": self.as_of,
                "point_in_time": self.point_in_time,
                "n_instruments": int(px.shape[1]),
                "n_curve_systems": len(curves),
                "n_macro_series": int(macro.shape[1]) if not macro.empty else 0,
                "n_positioning_series": int(pos.shape[1]) if not pos.empty else 0,
                "feature_version": FEATURE_VERSION,
                "stale_macro_series": getattr(self, "stale_macro", {}),
                "price_data_issues": getattr(self, "price_issues", []),
            },
        )

    # ------------------------------------------------------------ price features
    def _price_features(self, px: pd.DataFrame, rets: pd.DataFrame) -> pd.DataFrame:
        out = []
        for iid in px.columns:
            spec = self.universe.instruments.get(iid)
            if spec is None:
                continue
            p = px[iid].dropna()
            if len(p) < 60:
                continue
            r = rets[iid].dropna()

            def add(feature: str, series: pd.Series, window: str = ""):
                s = series.dropna()
                if s.empty:
                    return
                out.append(pd.DataFrame({
                    "entity_kind": "instrument", "entity_id": iid, "asset_class": spec.asset_class,
                    "region": spec.region, "feature": feature, "window": window,
                    "date": s.index, "value": s.values,
                }))

            for wname, w in RETURN_WINDOWS.items():
                add("return", safe_pct_change(p, w), wname)
            for wname, w in VOL_WINDOWS.items():
                add("ann_vol", ann_vol(r, w), wname)
            add("drawdown_252d", drawdown_from_high(p, 252))
            add("drawdown_5y", drawdown_from_high(p, 1260))
            ma50 = p.rolling(50, min_periods=40).mean()
            ma200 = p.rolling(200, min_periods=150).mean()
            add("ma_gap_50d", p / ma50 - 1.0)
            add("ma_gap_200d", p / ma200 - 1.0)
            add("ma_cross_50_200", (ma50 - ma200) / ma200)

            # 12-1 momentum (skip the most recent month): standard factor definition
            add("momentum_12_1", p.shift(21) / p.shift(252) - 1.0)

            # robust z-scores & percentiles of returns, computed on trailing windows
            r1m = safe_pct_change(p, 21)
            add("return_z_3y", robust_z(r1m, 756), "1m")
            add("return_pctile_5y", rolling_percentile(r1m, 1260), "1m")
            r1d = r
            add("return_z_1d_3y", robust_z(r1d, 756), "1d")
            vol63 = ann_vol(r, 63)
            add("vol_z_3y", robust_z(vol63, 756), "3m")
            add("vol_pctile_5y", rolling_percentile(vol63, 1260), "3m")
            add("drawdown_pctile_5y", rolling_percentile(drawdown_from_high(p, 252), 1260))
            # realized vol relative to its own long-run median = regime gauge
            add("vol_ratio_1m_12m", ann_vol(r, 21) / ann_vol(r, 252).replace(0, np.nan))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

    def _relative_strength(self, px: pd.DataFrame, rets: pd.DataFrame) -> pd.DataFrame:
        out = []
        for iid, spec in self.universe.instruments.items():
            if iid not in px.columns:
                continue
            bench = self.universe.resolve_benchmark(spec)
            if not bench or bench not in px.columns or bench == iid:
                continue
            for wname, w in (("1m", 21), ("3m", 63), ("6m", 126)):
                rel = safe_pct_change(px[iid], w) - safe_pct_change(px[bench], w)
                rel = rel.dropna()
                if rel.empty:
                    continue
                out.append(pd.DataFrame({
                    "entity_kind": "instrument", "entity_id": iid, "asset_class": spec.asset_class,
                    "region": spec.region, "feature": "rel_strength_vs_benchmark", "window": wname,
                    "date": rel.index, "value": rel.values,
                }))
                z = robust_z(rel, 756).dropna()
                out.append(pd.DataFrame({
                    "entity_kind": "instrument", "entity_id": iid, "asset_class": spec.asset_class,
                    "region": spec.region, "feature": "rel_strength_z_3y", "window": wname,
                    "date": z.index, "value": z.values,
                }))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

    def _breadth(self, px: pd.DataFrame) -> pd.DataFrame:
        """Cross-sectional breadth by region: share of instruments above MA200."""
        out = []
        groups: dict[str, list[str]] = {}
        for iid, spec in self.universe.instruments.items():
            if iid not in px.columns:
                continue
            if spec.asset_class not in {"equity_index", "equity_etf", "sector_equity"}:
                continue
            groups.setdefault(spec.region, []).append(iid)
        for region, ids in groups.items():
            if len(ids) < 4:
                continue
            ma200 = px[ids].rolling(200, min_periods=150).mean()
            above = (px[ids] > ma200).astype(float)
            above = above.where(px[ids].notna())
            breadth = above.mean(axis=1).dropna()
            out.append(pd.DataFrame({
                "entity_kind": "region", "entity_id": region, "asset_class": "equity_etf",
                "region": region, "feature": "breadth_above_ma200", "window": "",
                "date": breadth.index, "value": breadth.values,
            }))
            breadth_z = robust_z(breadth, 756).dropna()
            out.append(pd.DataFrame({
                "entity_kind": "region", "entity_id": region, "asset_class": "equity_etf",
                "region": region, "feature": "breadth_z_3y", "window": "",
                "date": breadth_z.index, "value": breadth_z.values,
            }))
        # US sector breadth & dispersion
        us_sectors = [i.id for i in self.universe.by_asset_class("sector_equity") if i.region == "US" and i.id in px.columns]
        if len(us_sectors) >= 6:
            r21 = px[us_sectors].pct_change(21, fill_method=None)
            pos_share = (r21 > 0).astype(float).where(r21.notna()).mean(axis=1).dropna()
            disp = r21.std(axis=1).dropna()
            for feat, s in (("us_sector_breadth_1m", pos_share), ("us_sector_dispersion_1m", disp)):
                out.append(pd.DataFrame({
                    "entity_kind": "region", "entity_id": "US", "asset_class": "sector_equity",
                    "region": "US", "feature": feat, "window": "1m",
                    "date": s.index, "value": s.values,
                }))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

    # ------------------------------------------------------------ curve features
    def _curve_features(self, curves: dict[str, pd.DataFrame]) -> pd.DataFrame:
        out = []
        for cid, wide in curves.items():
            cols = list(wide.columns)

            def add(feature: str, series: pd.Series, window: str = ""):
                s = series.dropna()
                if s.empty:
                    return
                out.append(pd.DataFrame({
                    "entity_kind": "curve", "entity_id": cid, "asset_class": "fixed_income",
                    "region": self.curves[cid].region, "feature": feature, "window": window,
                    "date": s.index, "value": s.values,
                }))

            def col(t: str) -> pd.Series | None:
                return wide[t] if t in cols else None

            # Individual benchmark yields are emitted at series level by
            # _indicator_features() (entity "UST:10Y" etc.) so that a feature is
            # uniquely keyed by (entity, feature, window). Curve-level features
            # below are only the combinations (slope/curvature/state).

            t2, t10 = col("2Y"), col("10Y")
            if t2 is not None and t10 is not None:
                slope = t10 - t2
                add("slope_2s10s", slope)
                add("slope_2s10s_change_1m", slope.diff(21), "1m")
                add("slope_2s10s_z_3y", robust_z(slope, 756))
                add("slope_2s10s_pctile_5y", rolling_percentile(slope, 1260))
                add("curve_inverted", (slope < 0).astype(float))
            t3m = col("3M")
            if t3m is not None and t10 is not None:
                add("slope_3m10y", t10 - t3m)
            t5 = col("5Y")
            if t5 is not None and t2 is not None and t10 is not None:
                add("curvature_2_5_10", 2 * t5 - t2 - t10)
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

    # -------------------------------------------------------- indicator features
    def _indicator_features(self, curves: dict[str, pd.DataFrame], macro: pd.DataFrame,
                            pos: pd.DataFrame) -> pd.DataFrame:
        """Level/change/z features for every stored indicator series (curves included)."""
        out = []
        for cid, wide in curves.items():
            for tenor in wide.columns:
                s = wide[tenor].dropna()
                if len(s) < 30:
                    continue
                sid = f"{cid}:{tenor}"
                for feat, series, win in (
                    ("level", s, tenor),
                    ("change_21d", s.diff(21), tenor),
                    ("change_63d", s.diff(63), tenor),
                    ("change_252d", s.diff(252), tenor),
                    ("z_level_3y", robust_z(s, 756), tenor),
                ):
                    out.append(pd.DataFrame({
                        "entity_kind": "series", "entity_id": sid, "asset_class": "fixed_income",
                        "region": self.curves[cid].region, "feature": feat, "window": win,
                        "date": series.dropna().index, "value": series.dropna().values,
                    }))
        del macro, pos  # macro/positioning handled below with transforms
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

    # ------------------------------------------------------ cross-asset features
    def _cross_asset_features(self, px: pd.DataFrame, rets: pd.DataFrame,
                              curves: dict[str, pd.DataFrame]) -> pd.DataFrame:
        out = []

        def add(entity_id: str, feature: str, series: pd.Series, window: str = "", region: str = "WORLD"):
            s = series.replace([np.inf, -np.inf], np.nan).dropna()
            if s.empty:
                return
            out.append(pd.DataFrame({
                "entity_kind": "cross_asset", "entity_id": entity_id, "asset_class": "cross_asset",
                "region": region, "feature": feature, "window": window,
                "date": s.index, "value": s.values,
            }))

        def rolling_corr(a: pd.Series, b: pd.Series, w: int) -> pd.Series:
            df = pd.concat([a, b], axis=1).dropna()
            if df.shape[1] < 2:
                return pd.Series(dtype=float)
            return df.iloc[:, 0].rolling(w, min_periods=max(20, w // 3)).corr(df.iloc[:, 1])

        def ret(iid: str) -> pd.Series | None:
            return rets[iid].dropna() if iid in rets.columns else None

        pairs = [
            ("US_EQ_SPY", "UST:10Y", "stock_bond", 1),
            ("US_EQ_SPY", "US_CR_HYG", "equity_credit", 1),
            ("CM_MET_GC", "US_FX_DXY", "gold_dollar", -1),
            ("CM_MET_HG", "CM_MET_GC", "copper_gold", 1),
            ("US_EQ_SPY", "CM_ENE_CL", "equity_oil", 1),
            ("US_EQ_SPY", "US_VOL_VIX", "equity_vix", -1),
        ]
        ust = curves.get("UST")
        for a, b, label, _sign in pairs:
            ra = ret(a)
            if ra is None:
                continue
            if b.startswith("UST:") and ust is not None:
                tenor = b.split(":")[1]
                if tenor not in ust.columns:
                    continue
                rb = ust[tenor].diff().dropna()
            else:
                rb = ret(b)
            if rb is None or rb.empty:
                continue
            corr = rolling_corr(ra, rb, 63)
            add(label, "corr_63d", corr)
            add(label, "corr_z_3y", robust_z(corr, 756))

        # copper/gold ratio as a growth proxy
        if "CM_MET_HG" in px.columns and "CM_MET_GC" in px.columns:
            ratio = (px["CM_MET_HG"] / px["CM_MET_GC"]).dropna()
            add("copper_gold_ratio", "ratio", ratio)
            add("copper_gold_ratio", "ma_gap_200d", ratio / ratio.rolling(200, min_periods=150).mean() - 1)
            add("copper_gold_ratio", "z_3y", robust_z(ratio, 756))

        # equity risk premium: S&P earnings yield minus 10y (using trailing P/E proxy)
        pe = self.store.load_indicator("VALUATION:SP500_PE", end=self.as_of)
        if pe.empty:
            pe = self.store.load_indicator("US_CAPE", end=self.as_of)
        if not pe.empty and ust is not None and "10Y" in ust.columns:
            ey = (100.0 / pe).dropna()
            y10 = ust["10Y"].dropna()
            joined = pd.concat([ey.rename("ey"), y10.rename("y10")], axis=1).dropna()
            if not joined.empty:
                joined = joined.resample("ME").last()
                erp = joined["ey"] - joined["y10"]
                add("equity_risk_premium", "level", erp)
                add("equity_risk_premium", "z_5y", robust_z(erp, 60))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

    # ------------------------------------------------------- valuation features
    def _valuation_features(self, macro: pd.DataFrame) -> pd.DataFrame:
        out = []
        if "US_CAPE" not in macro.columns:
            return pd.DataFrame()
        cape = macro["US_CAPE"].dropna()
        if cape.empty:
            return pd.DataFrame()
        for feat, series, win in (
            ("cape_level", cape, ""),
            ("cape_pctile_10y", rolling_percentile(cape, 120), ""),
            ("cape_z_10y", robust_z(cape, 120), ""),
            ("cape_yoy", cape.pct_change(12, fill_method=None) * 100, ""),
        ):
            s = series.dropna()
            out.append(pd.DataFrame({
                "entity_kind": "valuation", "entity_id": "US_CAPE", "asset_class": "equity_etf",
                "region": "US", "feature": feat, "window": win, "date": s.index, "value": s.values,
            }))
        # earnings yield from CAPE for ERP cross-check
        ey = (100.0 / cape).dropna()
        out.append(pd.DataFrame({
            "entity_kind": "valuation", "entity_id": "US_CAPE", "asset_class": "equity_etf",
            "region": "US", "feature": "earnings_yield", "window": "", "date": ey.index, "value": ey.values,
        }))
        return pd.concat(out, ignore_index=True)

    # ------------------------------------------------------ positioning features
    def _positioning_features(self, pos: pd.DataFrame) -> pd.DataFrame:
        out = []
        for pid in pos.columns:
            s = pos[pid].dropna()
            if len(s) < 30:
                continue
            oi_series = pos.get(f"{pid}:oi")
            norm = s / oi_series.replace(0, np.nan) if oi_series is not None else s
            for feat, series in (
                ("net_position", s),
                ("net_to_oi", norm),
                ("net_z_3y", robust_z(norm, 156)),
                ("net_pctile_5y", rolling_percentile(norm, 260)),
                ("net_change_4w", norm.diff(4)),
            ):
                x = series.dropna()
                if x.empty:
                    continue
                out.append(pd.DataFrame({
                    "entity_kind": "positioning", "entity_id": pid, "asset_class": "positioning",
                    "region": "WORLD", "feature": feat, "window": "",
                    "date": x.index, "value": x.values,
                }))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

    # ------------------------------------------------------------ macro features
    def _macro_features(self, macro: pd.DataFrame) -> pd.DataFrame:
        out = []
        if macro.empty:
            return pd.DataFrame()
        for sid in macro.columns:
            if sid not in self.macro_defs:
                continue
            spec = self.macro_defs[sid]
            raw = macro[sid].dropna()
            if raw.empty:
                continue
            value = self._transform(raw, spec)
            if value.dropna().empty:
                continue
            freq_days = {"monthly": 21, "quarterly": 63, "annual": 252, "weekly": 5, "daily": 1}.get(spec.frequency, 21)
            win = {"monthly": 36, "quarterly": 16, "annual": 10, "weekly": 156, "daily": 756}.get(spec.frequency, 36)
            pct_win = {"monthly": 60, "quarterly": 20, "annual": 10, "weekly": 260, "daily": 1260}.get(spec.frequency, 60)
            features = {
                "value": value,
                "change_1p": value.diff(1),
                "change_3p": value.diff(3),
                "change_12p": value.diff(12),
                "z_3y": robust_z(value, win),
                "pctile_5y": rolling_percentile(value, pct_win),
            }
            for feat, series in features.items():
                x = series.replace([np.inf, -np.inf], np.nan).dropna()
                if x.empty:
                    continue
                out.append(pd.DataFrame({
                    "entity_kind": "macro", "entity_id": sid, "asset_class": "macro",
                    "region": spec.region, "feature": feat, "window": spec.frequency,
                    "date": x.index, "value": x.values,
                }))
            del freq_days
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

    @staticmethod
    def _transform(raw: pd.Series, spec: MacroSeries) -> pd.Series:
        """Apply a transform on a CALENDAR-aligned series.

        ``pct_change(12)`` shifts by *rows*, which is wrong when a month is
        missing (the BLS gap in 2025-10 produced a fake +4% CPI YoY and a false
        macro anomaly). Resampling to the calendar frequency first inserts NaN
        placeholders so the lag is in months/quarters, not observations.
        """
        s = raw.sort_index()
        freq = {"monthly": "MS", "quarterly": "QS", "annual": "YS"}.get(spec.frequency)
        if freq and len(s) > 1:
            s = s.resample(freq).last()
        if spec.transform == "yoy":
            return s.pct_change(spec.transform_lags, fill_method=None) * 100.0
        if spec.transform == "diff":
            return s.diff()
        if spec.transform == "pct":
            return s.pct_change(fill_method=None) * 100.0
        return s

    # ------------------------------------------------------------- risk features
    def _risk_features(self, px: pd.DataFrame, rets: pd.DataFrame) -> pd.DataFrame:
        out = []

        def add(entity_id: str, feature: str, series: pd.Series, window: str = ""):
            s = series.replace([np.inf, -np.inf], np.nan).dropna()
            if s.empty:
                return
            out.append(pd.DataFrame({
                "entity_kind": "risk", "entity_id": entity_id, "asset_class": "volatility",
                "region": "US", "feature": feature, "window": window,
                "date": s.index, "value": s.values,
            }))

        vix = px.get("US_VOL_VIX")
        vix3m = px.get("US_VOL_VIX3M")
        if vix is not None:
            add("VIX", "level", vix)
            add("VIX", "z_3y", robust_z(vix, 756))
            add("VIX", "pctile_5y", rolling_percentile(vix, 1260))
            if vix3m is not None:
                ratio = (vix / vix3m).dropna()
                add("VIX_TERM", "vix_over_vix3m", ratio)
                add("VIX_TERM", "z_3y", robust_z(ratio, 756))
                add("VIX_TERM", "inverted", (ratio > 1).astype(float))
        move = px.get("US_VOL_MOVE")
        if move is not None:
            add("MOVE", "level", move)
            add("MOVE", "z_3y", robust_z(move, 756))
        # cross-sectional risk appetite: high-yield minus treasuries over 1m
        if "US_CR_HYG" in px.columns and "US_FI_IEF" in px.columns:
            spread_proxy = (px["US_CR_HYG"].pct_change(21, fill_method=None)
                            - px["US_FI_IEF"].pct_change(21, fill_method=None)).dropna()
            add("CREDIT_RISK", "hy_minus_treasury_1m", spread_proxy)
            add("CREDIT_RISK", "hy_minus_treasury_z_3y", robust_z(spread_proxy, 756))
            ratio = (px["US_CR_HYG"] / px["US_FI_IEF"]).dropna()
            add("CREDIT_RISK", "hy_over_treasury", ratio)
            add("CREDIT_RISK", "hy_over_treasury_z_3y", robust_z(ratio, 756))
        del rets
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def build_features(store: Store, as_of: str | None = None, *, point_in_time: bool = True) -> FeatureSet:
    return FeatureBuilder(store, as_of=as_of, point_in_time=point_in_time).build()


def save_feature_snapshot(fs: FeatureSet, directory: str) -> str:
    return fs.save(directory)
