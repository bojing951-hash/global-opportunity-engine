"""File-backed consensus-revision and policy-path evidence.

No public, licensed consensus/OIS history is bundled with this repository. The
adapters therefore read explicitly configured local CSV files. Missing files
leave hypotheses unknown; they never create observations or impute values.

Schemas (strict, point-in-time):
  consensus: series_id,observation_date,forecast_target,publication_time,available_at,
             vintage,value,metric,kind,source
  ois:       curve_id,currency,region,curve_type,provider,units,tenor,date,
             publication_time,available_at,vintage,value,source
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
    for c in ("date", "available_at", "publication_time", "observation_date", "forecast_target"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c])
    return df


def consensus_evidence(as_of: str, series_id: str | None = None,
                       config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    cfg = (config or _config()).get("consensus") or {}
    if not cfg.get("enabled"):
        return None
    cols = {"series_id", "observation_date", "forecast_target", "publication_time",
            "available_at", "vintage", "value", "metric", "kind", "source"}
    df = _read_csv(cfg.get("path", ""), cols)
    if df is None or df.empty:
        return None
    cutoff = pd.Timestamp(as_of)
    for c in ("observation_date", "forecast_target", "publication_time", "available_at",
              "vintage"):
        df[c] = pd.to_datetime(df[c])
    # Publication/availability/vintage must be known by the decision time; a
    # future forecast target is allowed, but its publication/vintage is not.
    avail = df[(df["available_at"] <= cutoff) & (df["publication_time"] <= cutoff)
               & (df["vintage"] <= cutoff) & (df["vintage"] <= df["available_at"])
               & (df["publication_time"] <= df["available_at"])
               & (df["observation_date"] <= cutoff)]
    if series_id:
        avail = avail[avail["series_id"] == series_id]
    if avail.empty:
        return None
    kinds = set(avail["kind"].astype(str))
    if kinds - {"actual", "forecast"}:
        return None
    # For actuals the target period must be in the past; for forecasts the
    # target may be future but the forecast itself must have been published.
    actual = avail[(avail["kind"] == "actual") & (avail["forecast_target"] <= cutoff)]
    forecast = avail[(avail["kind"] == "forecast") & (avail["forecast_target"] >= cutoff)]
    usable = pd.concat([actual, forecast]).drop_duplicates()
    if usable.empty:
        return None
    last = usable.sort_values(["available_at", "observation_date"]).iloc[-1]
    age = (cutoff - pd.Timestamp(last["available_at"])).days
    if age > int(cfg.get("max_age_days", 90)):
        return None
    return {"claim": "分析师一致预期修正（PIT）", "value": f"{last['metric']}={last['value']}",
            "class": "statistical_association", "source": str(last["source"]),
            "available_at": str(last["available_at"].date()),
            "publication_time": str(last["publication_time"].date()),
            "vintage": str(last["vintage"]), "kind": str(last["kind"]),
            "forecast_target": str(last["forecast_target"].date()),
            "discriminating": True, "series_id": str(last["series_id"])}


def ois_evidence(as_of: str, region: str | None = None,
                 currency: str | None = None, curve_type: str | None = None,
                 curve_id: str | None = None,
                 config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Slope from ONE economically comparable curve; never stitch currencies.

    Required schema: curve_id,currency,region,curve_type,tenor,date,value,
    available_at,source. All tenors must share curve/currency/region/type and
    observation date. The configured type is explicit: ``ois`` for a true OIS
    curve, or ``policy_path_proxy`` for the FRED Treasury/SOFR proxy.
    """
    cfg = (config or _config()).get("ois") or {}
    if not cfg.get("enabled"):
        return None
    cols = {"curve_id", "currency", "region", "curve_type", "provider", "units", "tenor",
            "date", "publication_time", "available_at", "vintage", "value", "source"}
    df = _read_csv(cfg.get("path", ""), cols)
    if df is None or df.empty:
        return None
    desired_currency = currency or cfg.get("currency")
    desired_region = region or cfg.get("region")
    desired_type = curve_type or cfg.get("curve_type", "ois")
    desired_curve = curve_id or cfg.get("curve_id")
    desired_provider = cfg.get("provider")
    desired_units = cfg.get("units")
    if not desired_currency or not desired_region:
        return None
    cutoff = pd.Timestamp(as_of)
    for c in ("date", "publication_time", "available_at", "vintage"):
        df[c] = pd.to_datetime(df[c])
    avail = df[(df["date"] <= cutoff) & (df["available_at"] <= cutoff)
               & (df["publication_time"] <= cutoff) & (df["vintage"] <= cutoff)
               & (df["publication_time"] <= df["available_at"])
               & (df["vintage"] <= df["available_at"])
               & (df["currency"] == desired_currency)
               & (df["region"] == desired_region)
               & (df["curve_type"] == desired_type)].copy()
    if desired_provider:
        avail = avail[avail["provider"] == desired_provider]
    if desired_units:
        avail = avail[avail["units"] == desired_units]
    if desired_curve:
        avail = avail[avail["curve_id"] == desired_curve]
    if avail.empty:
        return None
    curve_ids = avail["curve_id"].unique()
    if len(curve_ids) != 1:
        return None  # ambiguous curve identity: refuse rather than stitch
    cid = str(curve_ids[0])
    if avail["provider"].nunique() != 1:
        return None
    if avail["units"].nunique() != 1:
        return None
    latest = avail.sort_values("available_at").groupby("tenor", as_index=False).tail(1)
    tenors = set(latest["tenor"].astype(str))
    if not {"2Y", "10Y"}.issubset(tenors):
        return None
    short_row = latest[latest["tenor"].astype(str) == "2Y"].iloc[-1]
    long_row = latest[latest["tenor"].astype(str) == "10Y"].iloc[-1]
    if str(short_row["date"]) != str(long_row["date"]):
        return None
    if str(short_row["available_at"]) != str(long_row["available_at"]):
        return None
    try:
        short = float(short_row["value"]); long = float(long_row["value"])
    except (TypeError, ValueError):
        return None
    if pd.isna(short) or pd.isna(long):
        return None
    age = (cutoff - pd.Timestamp(short_row["available_at"])).days
    if age > int(cfg.get("max_age_days", 10)):
        return None
    is_ois = desired_type == "ois"
    return {"claim": "OIS 曲线 2s10s" if is_ois else "政策路径代理 2s10s（非 OIS）",
            "value": f"2s10s={long - short:.2f}pp",
            "class": "statistical_association", "source": str(short_row["source"]),
            "available_at": str(short_row["available_at"]), "discriminating": True,
            "publication_time": str(short_row["publication_time"].date()),
            "vintage": str(short_row["vintage"]),
            "curve": {"curve_id": cid, "currency": desired_currency,
                      "region": desired_region, "curve_type": desired_type,
                      "provider": str(short_row["provider"]), "units": str(short_row["units"]),
                      "date": str(short_row["date"].date()), "2Y": short, "10Y": long}}



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
