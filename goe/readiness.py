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
    degraded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok, "critical": self.critical, "warnings": self.warnings,
            "as_of": self.as_of, "last_price_date": self.last_price_date,
            "age_days_vs_asof": self.age_days_vs_asof, "n_configured": self.n_configured,
            "n_fresh": self.n_fresh, "coverage": round(self.coverage, 4),
            "price_rows": self.price_rows, "indicator_rows": self.indicator_rows,
            "macro_series_present": self.macro_series_present, "degraded": self.degraded,
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

    macro_ids = list(load_macro())
    present_macro = store.conn.execute(
        f"SELECT COUNT(DISTINCT series_id) FROM indicators WHERE series_id IN ({','.join('?' for _ in macro_ids)})",
        tuple(macro_ids)).fetchone()[0] if macro_ids else 0
    res.macro_series_present = int(present_macro)
    if indicator_rows == 0:
        res.critical.append("指标表为空：无法评估利率/宏观传导")
    elif present_macro < max(4, len(macro_ids) // 3):
        res.warnings.append(f"宏观序列仅 {present_macro}/{len(macro_ids)} 条可用，机制评估将受限")
        res.degraded = True
    curve_ids = [f"{cid}:{t}" for cid, cdef in load_curves().items() for t in cdef.tenors]
    present_curve = store.conn.execute(
        f"SELECT COUNT(DISTINCT series_id) FROM indicators WHERE series_id IN ({','.join('?' for _ in curve_ids)})",
        tuple(curve_ids)).fetchone()[0] if curve_ids else 0
    if present_curve < len(curve_ids) * 0.5:
        res.warnings.append(f"收益率曲线仅 {present_curve}/{len(curve_ids)} 个期限可用")
        res.degraded = True
    pos_ids = list(load_positioning())
    present_pos = store.conn.execute(
        f"SELECT COUNT(DISTINCT series_id) FROM indicators WHERE series_id IN ({','.join('?' for _ in pos_ids)})",
        tuple(pos_ids)).fetchone()[0] if pos_ids else 0
    if pos_ids and present_pos == 0:
        res.warnings.append("CFTC 持仓缺失：仓位维度不可用")
        res.degraded = True

    res.ok = not res.critical
    return res
