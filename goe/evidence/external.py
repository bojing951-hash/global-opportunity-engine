"""File-backed consensus-revision and policy-path evidence.

No public, licensed consensus/OIS history is bundled with this repository. The
adapters therefore read explicitly configured local CSV files. Missing files
leave hypotheses unknown; they never create observations or impute values.

Schemas (strict):
  consensus: series_id,date,value,available_at,metric
  ois:       series_id,tenor,date,value,available_at
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..config import project_root


def _config() -> dict[str, Any]:
    import yaml

    p = project_root() / "config" / "evidence_sources.yaml"
    if not p.exists():
        return {}
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {})


def _read_csv(path: str | Path, required: set[str]) -> pd.DataFrame | None:
    p = Path(path)
    if not p.is_absolute():
        p = project_root() / p
    if not p.exists() or p.stat().st_size == 0:
        return None
    try:
        df = pd.read_csv(p)
    except Exception:
        return None
    if not required.issubset(df.columns):
        return None
    for c in ("date", "available_at"):
        df[c] = pd.to_datetime(df[c]).dt.date.astype(str)
    return df


def consensus_evidence(as_of: str, series_id: str | None = None,
                       config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    cfg = (config or _config()).get("consensus") or {}
    if not cfg.get("enabled"):
        return None
    df = _read_csv(cfg.get("path", ""), {"series_id", "date", "value", "available_at", "metric"})
    if df is None or df.empty:
        return None
    cutoff = pd.Timestamp(as_of)
    avail = df[pd.to_datetime(df["available_at"]) <= cutoff]
    if series_id:
        avail = avail[avail["series_id"] == series_id]
    if avail.empty:
        return None
    last = avail.sort_values(["available_at", "date"]).iloc[-1]
    age = (cutoff - pd.Timestamp(last["available_at"])).days
    if age > int(cfg.get("max_age_days", 90)):
        return None
    return {"claim": "分析师一致预期修正", "value": f"{last['metric']}={last['value']}",
            "class": "statistical_association", "source": "consensus_revisions",
            "available_at": str(last["available_at"]), "discriminating": True,
            "series_id": str(last["series_id"])}


def ois_evidence(as_of: str, region: str | None = None,
                 config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    cfg = (config or _config()).get("ois") or {}
    if not cfg.get("enabled"):
        return None
    df = _read_csv(cfg.get("path", ""), {"series_id", "tenor", "date", "value", "available_at"})
    if df is None or df.empty:
        return None
    cutoff = pd.Timestamp(as_of)
    avail = df[pd.to_datetime(df["available_at"]) <= cutoff].copy()
    if avail.empty:
        return None
    latest = avail.sort_values("available_at").groupby("tenor", as_index=False).tail(1)
    if latest["tenor"].nunique() < 2:
        return None
    values = dict(zip(latest["tenor"].astype(str), pd.to_numeric(latest["value"], errors="coerce")))
    short = values.get("2Y", values.get("1Y"))
    long = values.get("10Y", values.get("5Y"))
    if short is None or long is None or pd.isna(short) or pd.isna(long):
        return None
    age = (cutoff - pd.Timestamp(latest["available_at"].max())).days
    if age > int(cfg.get("max_age_days", 10)):
        return None
    return {"claim": "政策路径/曲线斜率", "value": f"2s10s={float(long) - float(short):.2f}pp",
            "class": "statistical_association", "source": "ois_curve",
            "available_at": str(latest["available_at"].max()), "discriminating": True,
            "curve": {"2Y": short, "10Y": long}}


def attach_external(bundle: dict[str, Any], spec, iid: str, as_of: str) -> dict[str, Any]:
    """Attach only measured external evidence; never turn missing data into support."""
    by_suffix = lambda suf: next((h for h in bundle["hypotheses"]
                                 if h["id"].endswith(suf)), None)
    if getattr(spec, "asset_class", "") in ("equity_index", "equity_etf", "sector_equity"):
        ev = consensus_evidence(as_of, iid)
        if ev:
            h = by_suffix("-FUND")
            if h:
                h["status"] = "open"
                h["evidence_for"] = [ev]
    if getattr(spec, "asset_class", "") in ("fixed_income", "credit", "volatility"):
        ev = ois_evidence(as_of, getattr(spec, "region", None))
        if ev:
            h = by_suffix("-POL") or by_suffix("-TERM")
            if h:
                h["status"] = "open"
                h["evidence_for"] = [ev]
    return bundle
