"""Data-readiness gate.

The engine must refuse to produce "fresh-looking" opportunities from stale or
failed data. Two distinct conditions are checked:

* **critical** — prices are missing/stale relative to the research as-of date, or
  an ingest run failed outright. The scan is blocked (no opportunities).
* **degraded** — macro/positioning coverage is incomplete. The scan may run, but
  the report and every candidate carry the degradation flag and the confidence
  gates in scoring prevent deep-research promotion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd

from .config import load_curves, load_macro, load_positioning, load_universe
from .db import Store


class ScanBlockedError(RuntimeError):
    """Raised when data is too stale/incomplete to produce a research scan."""


@dataclass
class ReadinessResult:
    ok: bool
    critical: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    as_of: str = ""
    last_price_date: str = ""
    age_days_vs_asof: int | None = None
    n_configured: int = 0
    n_fresh: int = 0
    coverage: float = 0.0
    price_rows: int = 0
    indicator_rows: int = 0
    macro_series_present: int = 0
    fresh_macro_series: int = 0
    stale_indicators: list[str] = field(default_factory=list)
    last_positioning_date: str = ""
    regions: dict[str, dict[str, Any]] = field(default_factory=dict)
    degraded: bool = False
    # A single stale optional series is a disclosure, not a reason to disable
    # deep research for every candidate. `critical_degraded` is the broad
    # macro/curve/région failure that the scoring gate may use.
    critical_degraded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok, "critical": self.critical, "warnings": self.warnings,
            "as_of": self.as_of, "last_price_date": self.last_price_date,
            "age_days_vs_asof": self.age_days_vs_asof, "n_configured": self.n_configured,
            "n_fresh": self.n_fresh, "coverage": round(self.coverage, 4),
            "price_rows": self.price_rows, "indicator_rows": self.indicator_rows,
            "macro_series_present": self.macro_series_present,
            "fresh_macro_series": self.fresh_macro_series,
            "stale_indicators": self.stale_indicators,
            "last_positioning_date": self.last_positioning_date,
            "regions": self.regions, "degraded": self.degraded,
            "critical_degraded": self.critical_degraded,
        }


def check_data_readiness(store: Store, as_of: str | None = None, *,
                         max_age_days: int = 7, min_coverage: float = 0.80,
                         today: str | None = None) -> ReadinessResult:
    universe = load_universe()
    n_configured = len(universe.instruments)
    price_rows = int(store.scalar("SELECT COUNT(*) FROM prices") or 0)
    last = store.scalar("SELECT MAX(date) FROM prices WHERE date <= ?", (as_of,)) if as_of else \
        store.scalar("SELECT MAX(date) FROM prices")
    indicator_rows = int(store.scalar("SELECT COUNT(*) FROM indicators") or 0)
    res = ReadinessResult(ok=False, as_of=as_of or "", last_price_date=last or "",
                          n_configured=n_configured, price_rows=price_rows,
                          indicator_rows=indicator_rows)
    if price_rows == 0 or not last:
        res.critical.append("价格表为空：没有可用的市场数据")
        return res

    target = as_of or last
    if as_of and last is None:
        res.critical.append(f"as-of {as_of} 之前没有任何价格数据")
        return res
    res.as_of = target
    try:
        age = (pd.Timestamp(target) - pd.Timestamp(last)).days
        res.age_days_vs_asof = int(age)
    except Exception:
        res.critical.append(f"as-of 日期无法解析: {target}")
        return res
    if abs(res.age_days_vs_asof) > max_age_days:
        res.critical.append(
            f"价格数据与 as-of 不一致：最后价格 {last}，as-of {target}，相差 {res.age_days_vs_asof} 天"
            f"（阈值 {max_age_days}）")
    if as_of is None:
        # implicit "latest" scan: also require the data to be recent in wall-clock terms
        ref = today or date.today().isoformat()
        stale_days = (pd.Timestamp(ref) - pd.Timestamp(last)).days
        if stale_days > 10:
            res.critical.append(f"最新价格距今已 {stale_days} 天（>10），拒绝生成“最新”机会")

    window_start = (pd.Timestamp(target) - pd.Timedelta(days=max_age_days)).strftime("%Y-%m-%d")
    fresh = store.conn.execute(
        "SELECT COUNT(DISTINCT instrument_id) FROM prices WHERE date >= ? AND date <= ?",
        (window_start, target)).fetchone()[0]
    res.n_fresh = int(fresh)
    res.coverage = res.n_fresh / n_configured if n_configured else 0.0
    if res.coverage < min_coverage:
        res.critical.append(
            f"近期价格覆盖率 {res.coverage:.0%} < {min_coverage:.0%}（{res.n_fresh}/{n_configured} 个标的）")

    # ---- per-market health: a global coverage ratio can hide a dead market.
    # Denominators use instruments that have ever been ingested for that market,
    # so a complete outage is caught by last-date age even when other markets are
    # fresh. Holiday gaps (e.g. China Golden Week) are tolerated to 10 days.
    region_of = {iid: spec.region for iid, spec in universe.instruments.items()}
    present_rows = store.conn.execute(
        "SELECT instrument_id, MAX(date) AS last_date FROM prices WHERE date <= ? "
        "GROUP BY instrument_id", (target,)).fetchall()
    present_last = {r["instrument_id"]: r["last_date"] for r in present_rows}
    configured_by_region: dict[str, int] = {}
    for iid in universe.instruments:
        configured_by_region[region_of[iid]] = configured_by_region.get(region_of[iid], 0) + 1
    for region in sorted(configured_by_region):
        ids = [i for i in present_last if region_of.get(i) == region]
        if not ids:
            res.regions[region] = {"n_tracked": 0, "n_fresh": 0, "coverage": 0.0,
                                   "last_date": "", "age_days": None,
                                   "n_configured": configured_by_region[region]}
            msg = f"{region} 市场完全没有价格数据（配置 {configured_by_region[region]} 个标的）"
            if configured_by_region[region] >= 3 and min_coverage > 0:
                res.critical.append(msg + "：关键市场数据失效")
            else:
                res.warnings.append(msg)
                res.degraded = True
            continue
        fresh_ids = [i for i in ids if present_last[i] is not None
                     and pd.Timestamp(present_last[i]) >= pd.Timestamp(target) - pd.Timedelta(days=10)
                     and pd.Timestamp(present_last[i]) <= pd.Timestamp(target)]
        last_region = max(present_last[i] for i in ids if present_last[i])
        age_region = (pd.Timestamp(target) - pd.Timestamp(last_region)).days
        ratio = len(fresh_ids) / len(ids)
        covered_ratio = len(ids) / configured_by_region[region]
        res.regions[region] = {"n_tracked": len(ids), "n_fresh": len(fresh_ids),
                               "coverage": round(ratio, 4), "last_date": last_region,
                               "age_days": int(age_region),
                               "n_configured": configured_by_region[region],
                               "instrument_coverage": round(covered_ratio, 4)}
        if len(ids) >= 3 and (ratio < 0.5 or age_region > 10):
            res.critical.append(
                f"{region} 市场数据失效：{len(fresh_ids)}/{len(ids)} 个标的在 10 天内有更新，"
                f"最后日期 {last_region}（距今 {age_region} 天）")
        elif min_coverage > 0 and len(ids) >= 3 and covered_ratio < 0.5:
            res.critical.append(
                f"{region} 市场覆盖流失：仅 {len(ids)}/{configured_by_region[region]} 个配置标的有数据")
        elif len(ids) >= 1 and len(fresh_ids) == 0:
            res.warnings.append(f"{region} 市场没有任何近期更新（最后 {last_region}，{age_region} 天前）")
            res.degraded = True
        elif len(ids) >= 3 and ratio < 0.8:
            res.warnings.append(f"{region} 市场仅 {len(fresh_ids)}/{len(ids)} 个标的近期有更新")
            res.degraded = True

    macro_ids = list(load_macro())
    present_macro = store.conn.execute(
        f"SELECT COUNT(DISTINCT series_id) FROM indicators WHERE series_id IN ({','.join('?' for _ in macro_ids)})",
        tuple(macro_ids)).fetchone()[0] if macro_ids else 0
    res.macro_series_present = int(present_macro)
    macro_defs = load_macro()
    lag_by_freq = {"daily": 0, "weekly": 4, "monthly": 45, "quarterly": 120, "annual": 180}
    fresh_macro = 0
    stale_macro_ids: list[str] = []
    for sid in macro_ids:
        mdef = macro_defs[sid]
        lag = lag_by_freq.get(mdef.frequency, 45)
        # pick the latest observation that is actually AVAILABLE at target;
        # rejecting the newest (unpublished) observation as "stale" was a false
        # alarm on every day before a release (audit round 2).
        cutoff_obs = (pd.Timestamp(target) - pd.Timedelta(days=lag)).strftime("%Y-%m-%d")
        last_sid = store.conn.execute(
            "SELECT MAX(date) FROM indicators WHERE series_id=? AND date <= ?",
            (sid, cutoff_obs)).fetchone()[0]
        if not last_sid:
            stale_macro_ids.append(sid)
            res.stale_indicators.append(f"macro:{sid} no_observation_available_by_asof")
            continue
        avail = pd.Timestamp(last_sid) + pd.Timedelta(days=lag)
        max_age = lag + 60
        if (pd.Timestamp(target) - avail).days <= max_age:
            fresh_macro += 1
        else:
            stale_macro_ids.append(sid)
            res.stale_indicators.append(f"macro:{sid} last_obs={last_sid} available={avail.date()}")
    res.fresh_macro_series = fresh_macro
    if indicator_rows == 0:
        res.critical.append("指标表为空：无法评估利率/宏观传导")
    elif present_macro < max(4, len(macro_ids) // 3):
        res.warnings.append(f"宏观序列仅 {present_macro}/{len(macro_ids)} 条可用，机制评估将受限")
        res.degraded = True
    if present_macro and fresh_macro < max(3, present_macro // 2):
        res.warnings.append(
            f"宏观序列新鲜度不足：仅 {fresh_macro}/{present_macro} 条在发布滞后+60 天内（停止更新？）")
        res.degraded = True
        res.critical_degraded = True
    if stale_macro_ids:
        key_stale = [sid for sid in stale_macro_ids
                     if float(getattr(macro_defs[sid], "importance", 0.5)) >= 0.8]
        shown = ", ".join(stale_macro_ids[:6])
        if key_stale:
            res.warnings.append(f"关键宏观序列过期：{', '.join(key_stale[:6])}（按发布日+60 天判断）")
        else:
            res.warnings.append(f"部分宏观序列过期/停止更新：{shown}")
        res.degraded = True
    curve_ids = [f"{cid}:{t}" for cid, cdef in load_curves().items() for t in cdef.tenors]
    present_curve, fresh_curve = 0, 0
    for cid in curve_ids:
        last_c = store.conn.execute(
            "SELECT MAX(date) FROM indicators WHERE series_id=? AND date <= ?",
            (cid, target)).fetchone()[0]
        if last_c:
            present_curve += 1
            if (pd.Timestamp(target) - pd.Timestamp(last_c)).days <= 15:
                fresh_curve += 1
            else:
                res.stale_indicators.append(f"curve:{cid} last={last_c}")
    if present_curve == 0:
        res.warnings.append(f"收益率曲线缺失：0/{len(curve_ids)} 个期限可用")
        res.degraded = True
    # Per curve SYSTEM: losing all fresh tenors of one core system (e.g. UST)
    # must be critical even when other systems are healthy.
    curve_systems = load_curves()
    for cid, cdef in curve_systems.items():
        tenors = [f"{cid}:{t}" for t in cdef.tenors]
        present_n = fresh_n = 0
        for sid in tenors:
            last_c = store.conn.execute(
                "SELECT MAX(date) FROM indicators WHERE series_id=? AND date <= ?",
                (sid, target)).fetchone()[0]
            if last_c:
                present_n += 1
                if (pd.Timestamp(target) - pd.Timestamp(last_c)).days <= 15:
                    fresh_n += 1
        if present_n and fresh_n == 0:
            res.critical.append(
                f"{cid} 曲线全部过期：0/{present_n} 个期限在 15 天内有更新（无法评估利率传导）")
            res.degraded = True
            res.critical_degraded = True
        elif present_n and fresh_n < present_n * 0.5:
            res.warnings.append(f"{cid} 曲线多数期限过期：{fresh_n}/{present_n} 个在 15 天内有更新")
            res.degraded = True
    # Per-system warnings above already cover missing/stale systems; do not add a
    # duplicate aggregate warning here (QA P3).
    pos_ids = list(load_positioning())
    present_pos = store.conn.execute(
        f"SELECT COUNT(DISTINCT series_id) FROM indicators WHERE series_id IN ({','.join('?' for _ in pos_ids)})",
        tuple(pos_ids)).fetchone()[0] if pos_ids else 0
    if pos_ids:
        last_pos = store.conn.execute(
            f"SELECT MAX(date) FROM indicators WHERE series_id IN ({','.join('?' for _ in pos_ids)}) "
            "AND date <= ?", tuple(pos_ids) + (target,)).fetchone()[0]
        res.last_positioning_date = last_pos or ""
        if present_pos == 0:
            res.warnings.append("CFTC 持仓缺失：仓位维度不可用")
            res.degraded = True
        elif last_pos and (pd.Timestamp(target) - pd.Timestamp(last_pos)).days > 30:
            res.warnings.append(f"CFTC 持仓过期：最后 {last_pos}（>30 天）")
            res.degraded = True

    res.ok = not res.critical
    return res
