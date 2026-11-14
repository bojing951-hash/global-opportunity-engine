"""Descriptive forward-return study for the selected research objects.

This is NOT a backtest of a portfolio and NOT proof of investment edge. It answers
a narrower question: at historical as-of dates, did the objects each method selected
subsequently move more than the cross-section, and in which direction? Selection is
point-in-time (the mapping was produced from PIT features); forward returns use only
prices after the as-of date.

Caveats printed in the report: no costs/sizing/direction, small n, survivorship of
the current universe, and no claim that a research candidate is a trade.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import load_universe
from .db import Store

METHODS = ("A_price_move", "B_anomaly_score", "C_engine")
HORIZONS = {"1m": 21, "3m": 63}


def _forward_return(series: pd.Series, as_of: str, days: int) -> float | None:
    s = series.dropna()
    s = s[s.index >= pd.Timestamp(as_of)]
    if len(s) < days + 1:
        return None
    return float(s.iloc[days] / s.iloc[0] - 1.0)


def build_forward_study(store: Store, mapping_path: str | Path = "audit/research_quality_mapping.json",
                        spy: str = "US_EQ_SPY") -> dict[str, Any]:
    mapping = json.load(open(mapping_path, encoding="utf-8"))["mapping"]
    universe = load_universe()
    dates = sorted({m["as_of"] for m in mapping.values()})
    close = store.load_prices(list(universe.instruments), start=min(dates), end=None)
    rows: list[dict[str, Any]] = []
    for token, meta in mapping.items():
        iid = meta["entity_id"]
        if iid not in close.columns:
            continue
        r1 = _forward_return(close[iid], meta["as_of"], HORIZONS["1m"])
        r3 = _forward_return(close[iid], meta["as_of"], HORIZONS["3m"])
        b3 = _forward_return(close[spy], meta["as_of"], HORIZONS["3m"]) if spy in close.columns else None
        rows.append({**meta, "object_id": token, "fwd_1m": r1, "fwd_3m": r3,
                     "excess_3m_vs_spy": (r3 - b3) if (r3 is not None and b3 is not None) else None})
    df = pd.DataFrame(rows)
    # per-date cross-sectional median |3m| across the investable universe
    med: dict[str, float] = {}
    for d in dates:
        vals = [_forward_return(close[i], d, HORIZONS["3m"]) for i in universe.instruments if i in close.columns]
        vals = [abs(v) for v in vals if v is not None]
        med[d] = float(np.median(vals)) if vals else float("nan")
    df["abs_fwd_3m"] = df["fwd_3m"].abs()
    df["median_abs_3m"] = df["as_of"].map(med)
    df["material_move"] = df["abs_fwd_3m"] >= 1.5 * df["median_abs_3m"]
    # Asset-class-relative excess: comparing an EM equity with SPY is not a
    # like-for-like benchmark (audit R2).
    cls_median: dict[tuple[str, str], float] = {}
    for d in dates:
        for cls in sorted({spec.asset_class for spec in universe.instruments.values()}):
            vals = []
            for iid, spec in universe.instruments.items():
                if spec.asset_class != cls or iid not in close.columns:
                    continue
                r = _forward_return(close[iid], d, HORIZONS["3m"])
                if r is not None:
                    vals.append(r)
            cls_median[(d, cls)] = float(np.median(vals)) if vals else float("nan")
    def _cls_excess(row):
        cls = universe.instruments.get(row["entity_id"]).asset_class if row["entity_id"] in universe.instruments else ""
        b = cls_median.get((row["as_of"], cls))
        if row["fwd_3m"] is None or b is None or not np.isfinite(b):
            return None
        return row["fwd_3m"] - b
    df["excess_3m_vs_class"] = df.apply(_cls_excess, axis=1)
    summary = {}
    for method in METHODS:
        sub = df[df.method == method]
        summary[method] = {
            "n": int(len(sub)),
            "mean_fwd_1m": _round(sub["fwd_1m"].mean()),
            "mean_fwd_3m": _round(sub["fwd_3m"].mean()),
            "mean_abs_fwd_3m": _round(sub["abs_fwd_3m"].mean()),
            "material_move_rate": _round(sub["material_move"].mean()),
            "mean_excess_3m_vs_spy": _round(sub["excess_3m_vs_spy"].mean()),
            "beat_spy_rate": _round((sub["excess_3m_vs_spy"] > 0).mean()),
            "mean_excess_3m_vs_class": _round(sub["excess_3m_vs_class"].mean()),
            "beat_class_rate": _round((sub["excess_3m_vs_class"] > 0).mean()),
        }
    per_date = []
    for d in dates:
        row = {"as_of": d, "median_abs_3m": _round(med[d])}
        for method in METHODS:
            sub = df[(df.method == method) & (df.as_of == d)]
            row[method] = _round(sub["fwd_3m"].mean())
        per_date.append(row)
    return {"summary": summary, "per_date": per_date, "objects": df.to_dict("records")}


def _round(v: Any, n: int = 4) -> float | None:
    try:
        if v is None or not np.isfinite(float(v)):
            return None
        return round(float(v), n)
    except Exception:
        return None


def write_forward_report(store: Store, out_path: str | Path = "audit/FORWARD_RETURNS.md",
                         mapping_path: str | Path = "audit/research_quality_mapping.json") -> dict[str, Any]:
    res = build_forward_study(store, mapping_path)
    lines = ["# FORWARD RETURNS — descriptive, not a backtest", "",
             "Selection is point-in-time (PIT mapping produced by `goe.evaluation`). Forward returns use",
             "only prices after each as-of date. No costs, no position sizing, no direction adjustment;",
             "the engine is a research-priority tool, not a portfolio. Small n (12 objects/method).", "",
             "| method | n | mean fwd 1m | mean fwd 3m | mean abs fwd 3m | material move rate | mean excess 3m vs SPY | beat SPY rate | mean excess 3m vs class | beat class rate |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m in METHODS:
        s = res["summary"][m]
        lines.append(f"| {m} | {s['n']} | {s['mean_fwd_1m']} | {s['mean_fwd_3m']} | "
                     f"{s['mean_abs_fwd_3m']} | {s['material_move_rate']} | {s['mean_excess_3m_vs_spy']} | "
                     f"{s['beat_spy_rate']} | {s['mean_excess_3m_vs_class']} | {s['beat_class_rate']} |")
    lines += ["", "Per as-of date (mean forward 3m return):", "",
              "| as_of | median abs 3m (universe) | A | B | C |", "|---|---:|---:|---:|---:|"]
    for r in res["per_date"]:
        lines.append(f"| {r['as_of']} | {r['median_abs_3m']} | {r['A_price_move']} | "
                     f"{r['B_anomaly_score']} | {r['C_engine']} |")
    lines += ["", "Interpretation rules:",
              "- `material_move_rate` measures whether the selected objects subsequently moved ≥1.5× the",
              "  cross-sectional median |3m| move; it is an attention/activity check, not a profit claim.",
              "- Positive/negative mean returns are descriptive; a single date or a few objects can dominate.",
              "- This does not repair the missing human/forward validation of the research process; it adds",
              "  one historical, falsifiable check and must be read with the blind LLM evaluation.",
              ""]
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    return res
