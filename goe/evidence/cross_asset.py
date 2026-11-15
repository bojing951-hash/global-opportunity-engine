"""Same-day cross-asset discriminating evidence (derived, no vendor).

For each candidate we estimate, on a trailing window ending at the decision
date, how much of its daily return is explained by a global risk factor and by
a local benchmark / FX pair. The estimates are *evidence*, not a conclusion:

* high R² and small residual z support the global/local factor explanation;
* high residual z with low R² argues against it and keeps the local hypothesis
  open.

Only observations present in the FeatureSet are used; no forward fill. If there
are too few observations the result is ``available=False`` and the caller must
keep the hypothesis untestable rather than inventing evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np
import pandas as pd

GLOBAL_ASSETS = ("US_EQ_SPY", "US_EQ_QQQ", "US_FX_DXY", "US_CR_HYG", "CM_MET_GC", "US_FI_IEF")
LOCAL_BENCHMARKS = {
    "US": ("US_EQ_SPY", "US_EQ_QQQ"),
    "CN": ("CN_EQ_CSI300", "CN_EQ_CSI1000"),
    "HK": ("HK_EQ_HSI",),
    "JP": ("JP_EQ_TOPIX",),
    "EA": ("EA_EQ_SX5E",),
    "DE": ("DE_EQ_DAX", "EA_EQ_SX5E"),
    "FR": ("FR_EQ_CAC", "EA_EQ_SX5E"),
    "UK": ("UK_EQ_FTSE",),
    "TW": ("TW_EQ_TAIEX",),
    "IN": ("IN_EQ_INDA",),
}
LOCAL_FX = {
    "JP": "GX_FX_USDJPY", "CN": "GX_FX_USDCNY", "HK": "GX_FX_USDHKD",
    "EA": "GX_FX_EURUSD", "DE": "GX_FX_EURUSD", "FR": "GX_FX_EURUSD",
    "IT": "GX_FX_EURUSD", "ES": "GX_FX_EURUSD", "UK": "GX_FX_GBPUSD",
    "TW": "GX_FX_USDTWD", "IN": "GX_FX_USDINR", "MX": "GX_FX_USDMXN",
    "BR": "GX_FX_USDBRL", "KR": "GX_FX_USDKRW",
}
MIN_OBS = 60
WINDOW = 252


@dataclass
class FactorFit:
    available: bool
    kind: str
    factor: str
    n_obs: int
    r2: float | None = None
    beta: float | None = None
    residual_z: float | None = None
    as_of: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fit(y: pd.Series, x: pd.Series, kind: str, names: str, as_of: str) -> FactorFit:
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    df = df.tail(WINDOW)
    if len(df) < MIN_OBS:
        return FactorFit(False, kind, names, len(df), as_of=as_of,
                         reason=f"insufficient common observations ({len(df)} < {MIN_OBS})")
    X = np.column_stack([np.ones(len(df)), df["x"].to_numpy(float)])
    coef, *_ = np.linalg.lstsq(X, df["y"].to_numpy(float), rcond=None)
    resid = df["y"].to_numpy(float) - X @ coef
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((df["y"] - df["y"].mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    sigma = float(np.std(resid, ddof=1)) if len(resid) > 1 else float("nan")
    rz = float(resid[-1] / sigma) if sigma and np.isfinite(sigma) else float("nan")
    return FactorFit(True, kind, names, len(df), round(r2, 4), round(float(coef[1]), 4),
                     round(rz, 4), as_of)


def compute_fits(fs, instrument_id: str, spec, as_of: str) -> dict[str, Any]:
    """Return global/local/fx factor fits for one candidate."""
    rets = fs.returns if fs is not None else pd.DataFrame()
    out: dict[str, Any] = {"available": False, "instrument": instrument_id, "as_of": as_of}
    if rets is None or rets.empty or instrument_id not in rets.columns:
        out["reason"] = "instrument returns unavailable"
        return out
    y = rets[instrument_id].dropna()
    globals_present = [i for i in GLOBAL_ASSETS if i in rets.columns and i != instrument_id]
    if len(globals_present) >= 2:
        factor = rets[globals_present].mean(axis=1).dropna()
        out["global"] = _fit(y, factor, "global", ",".join(globals_present), as_of).to_dict()
    local_ids = [i for i in LOCAL_BENCHMARKS.get(getattr(spec, "region", ""), ())
                 if i in rets.columns and i != instrument_id]
    if local_ids:
        out["local"] = _fit(y, rets[local_ids[0]], "local", local_ids[0], as_of).to_dict()
    fx_id = LOCAL_FX.get(getattr(spec, "region", ""))
    if fx_id and fx_id in rets.columns and fx_id != instrument_id:
        out["fx"] = _fit(y, rets[fx_id], "fx", fx_id, as_of).to_dict()
    out["available"] = any(k in out and out[k].get("available") for k in ("global", "local", "fx"))
    return out


def evidence_for_bundle(bundle: dict[str, Any], fits: dict[str, Any]) -> dict[str, Any]:
    """Attach actual factor estimates to matching hypotheses, with provenance.

    Items marked ``discriminating=True`` are measurements, not availability
    notes. The research-readiness gate counts only these.
    """
    def by_suffix(suf: str, typ: str | None = None):
        h = next((h for h in bundle["hypotheses"] if h["id"].endswith(suf)), None)
        if h is None and typ:
            h = next((h for h in bundle["hypotheses"]
                      if h.get("type") == typ and h.get("status") == "open"), None)
        return h
    as_of = fits.get("as_of", "")

    def item(claim: str, value: str, hid: str, source: str) -> dict[str, Any]:
        return {"claim": claim, "value": value, "class": "statistical_association",
                "source": source, "available_at": as_of, "hypothesis_id": hid,
                "discriminating": True}

    g = fits.get("global")
    if g and g.get("available"):
        h = by_suffix("-GLOBAL", "global_risk")
        if h:
            # Match the documented H-GLOBAL test: R² > 0.5 AND |residual z| < 1.5.
            support = g["r2"] > 0.50 and abs(g["residual_z"] or 0) < 1.5
            h["evidence_for"] = [item(
                "同日跨资产全球因子回归",
                f"R²={g['r2']:.2f}, beta={g['beta']:.2f}, residual_z={g['residual_z']:.2f}, n={g['n_obs']}",
                h["id"], "derived/cross_asset")] if support else []
            h["evidence_against"] = [] if support else [item(
                "全球因子解释力不足",
                f"R²={g['r2']:.2f} < 0.50; residual_z={g['residual_z']:.2f}",
                h["id"], "derived/cross_asset")]
            h["status"] = "open" if not support or abs(g["residual_z"] or 0) >= 1.5 else "supported"
    l = fits.get("local")
    if l and l.get("available"):
        # Local benchmark evidence belongs only to a hypothesis explicitly about
        # local/regional factors. Falling back by type would overwrite a GLOBAL
        # hypothesis with a local fit (observed on sector/ETF candidates).
        h = by_suffix("-LOCAL")
        if h:
            support = l["r2"] >= 0.30
            h["evidence_for"] = [item(
                "本地基准回归",
                f"R²={l['r2']:.2f}, beta={l['beta']:.2f}, residual_z={l['residual_z']:.2f}, n={l['n_obs']}",
                h["id"], "derived/cross_asset")] if support else []
            h["evidence_against"] = [] if support else [item(
                "本地基准解释力不足", f"R²={l['r2']:.2f} < 0.30", h["id"], "derived/cross_asset")]
    f = fits.get("fx")
    # A 1% R² FX fit is not evidence that FX explains the move. Only a fit that
    # meets the same explanatory threshold as global/local is marked discriminating.
    if f and f.get("available") and float(f.get("r2") or 0.0) >= 0.30:
        h = by_suffix("-FX", "global_risk") or by_suffix("-RISK", "global_risk")
        if h:
            h["evidence_for"] = [item(
                "本币汇率 beta",
                f"R²={f['r2']:.2f}, beta={f['beta']:.2f}, residual_z={f['residual_z']:.2f}, n={f['n_obs']}",
                h["id"], "derived/cross_asset")]
    return bundle


def count_discriminating(bundle: dict[str, Any]) -> int:
    """Number of open hypotheses carrying at least one measured discriminative item."""
    n = 0
    for h in bundle.get("hypotheses", []):
        if h.get("status") != "open":
            continue
        if any(e.get("discriminating") and e.get("class") != "unknown"
               for e in h.get("evidence_for", [])):
            n += 1
    return n
