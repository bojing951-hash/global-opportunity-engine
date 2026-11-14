"""Research-quality evaluation: engine ranking vs naive benchmarks.

The goal is NOT to prove return prediction. It answers a narrower, testable
question: *are the objects the engine selects more research-worthy than the ones
a naive price-move or anomaly-score screen would select?*

Design (pre-registered in audit/RESEARCH_QUALITY.md):
1. At several historical as-of dates, build one point-in-time FeatureSet.
2. Produce top-3 lists from three methods (theme-deduplicated):
   A. largest absolute 1-month return;
   B. largest recent anomaly score;
   C. the opportunity engine.
3. Build a COMMON fact sheet for every selected object (same fields regardless of
   method), shuffle and anonymise, and have an independent rater score each object
   on four criteria without knowing the method.
4. Unmask and compute Precision@3, mean research score, duplicate rate and fact
   completeness. Historical/LLM-rater labels are stated as limitations; no return
   or profitability claim is made.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .anomalies import detect_anomalies, summarize as summarize_anomalies
from .config import load_macro, load_positioning, load_universe, load_yaml_config
from .db import Store
from .events import EventCalendar
from .features import FeatureBuilder
from .opportunities import OpportunityEngine
from .timesemantics import filter_recent
from .transmission.evaluator import MechanismEvaluator

METHODS = ("A_price_move", "B_anomaly_score", "C_engine")


def _json_default(obj):
    import numpy as _np

    if isinstance(obj, (_np.bool_,)):
        return bool(obj)
    if isinstance(obj, (_np.integer,)):
        return int(obj)
    if isinstance(obj, (_np.floating,)):
        return float(obj)
    if isinstance(obj, (_np.ndarray,)):
        return obj.tolist()
    return str(obj)


@dataclass
class EvalObject:
    entity_id: str
    method: str
    theme: str
    facts: dict[str, Any] = field(default_factory=dict)

    def fact_sheet(self) -> dict[str, Any]:
        return {"object_id": self.entity_id, **self.facts}


def _theme(iid: str, themes: dict[str, str]) -> str:
    return themes.get(iid, iid)


def _instrument_facts(fs, iid: str, positioning: dict, mechanisms_by_asset: dict[str, list[dict]],
                      anomalies: pd.DataFrame) -> dict[str, Any]:
    spec = load_universe().instruments.get(iid)
    if spec is None:
        return {"name": iid, "market": "?", "asset_class": "?"}
    pos = None
    for pid, pdef in positioning.items():
        if pdef.maps_to == iid:
            v = fs.value(pid, "net_pctile_5y")
            if np.isfinite(v):
                pos = round(float(v), 4)
    recent = anomalies[anomalies.entity_id == iid] if not anomalies.empty else anomalies
    anoms = []
    for a in recent.tail(5).itertuples(index=False):
        anoms.append({"detector": a.detector, "direction": a.direction,
                      "score": round(float(a.score), 2), "available_date": a.available_date})
    return {
        "name": spec.name, "market": spec.region, "asset_class": spec.asset_class,
        "return_1m": round(float(fs.value(iid, "return", "1m")), 4) if np.isfinite(fs.value(iid, "return", "1m")) else None,
        "return_3m": round(float(fs.value(iid, "return", "3m")), 4) if np.isfinite(fs.value(iid, "return", "3m")) else None,
        "return_12m": round(float(fs.value(iid, "return", "12m")), 4) if np.isfinite(fs.value(iid, "return", "12m")) else None,
        "vol_pctile_5y": round(float(fs.value(iid, "vol_pctile_5y", "3m")), 4)
        if np.isfinite(fs.value(iid, "vol_pctile_5y", "3m")) else None,
        "drawdown_pctile_5y": round(float(fs.value(iid, "drawdown_pctile_5y")), 4)
        if np.isfinite(fs.value(iid, "drawdown_pctile_5y")) else None,
        "ma_gap_200d": round(float(fs.value(iid, "ma_gap_200d")), 4)
        if np.isfinite(fs.value(iid, "ma_gap_200d")) else None,
        "positioning_net_pctile_5y": pos,
        "recent_anomalies": anoms,
        "mechanisms": mechanisms_by_asset.get(iid, [])[:3],
        "data_gaps": ["no consensus earnings", "no options-implied distribution"],
    }


def _theme_dedupe(items: list[EvalObject], n: int = 3) -> list[EvalObject]:
    seen, out = set(), []
    for it in items:
        if it.theme in seen:
            continue
        seen.add(it.theme)
        out.append(it)
        if len(out) == n:
            break
    return out


def build_eval_objects(store: Store, as_of: str) -> tuple[list[EvalObject], list[EvalObject], list[EvalObject], dict[str, Any]]:
    """Return (method_A, method_B, method_C, diagnostics) for one as-of date."""
    from .config import load_themes

    themes = load_themes()
    positioning = load_positioning()
    universe = load_universe()
    fs = FeatureBuilder(store, as_of=as_of, point_in_time=True,
                        history_start=(pd.Timestamp(as_of) - pd.DateOffset(years=6)).strftime("%Y-%m-%d")).build()
    anomalies = detect_anomalies(fs, since=(pd.Timestamp(as_of) - pd.Timedelta(days=200)).strftime("%Y-%m-%d"))
    recent = filter_recent(anomalies, pd.Timestamp(as_of))
    mechs = MechanismEvaluator(fs, load_yaml_config("mechanisms.yaml")).evaluate(recent)
    mech_by_asset: dict[str, list[dict]] = {}
    for m in mechs:
        for a in m.assets:
            if a.get("id"):
                mech_by_asset.setdefault(a["id"], []).append(
                    {"id": m.mechanism_id, "status": m.status, "confidence": round(m.confidence, 2),
                     "role": a.get("role")})
    engine = OpportunityEngine(fs, anomalies, mechs, EventCalendar.load(), load_yaml_config("scoring.yaml"),
                               max_candidates=25, store=store)
    engine.generate()
    engine_candidates = getattr(engine, "all_scored", [])
    diag = {"as_of": as_of, "n_anomalies": int(len(anomalies)), "n_recent": int(len(recent)),
            "n_mechanisms": len(mechs), "engine_candidates": len(engine_candidates),
            "engine_statuses": pd.Series([d.status for d in engine_candidates]).value_counts().to_dict()
            if engine_candidates else {}}

    def facts(iid: str) -> dict[str, Any]:
        return _instrument_facts(fs, iid, positioning, mech_by_asset, recent)

    # A: largest absolute 1-month move
    movers = []
    for iid in universe.instruments:
        if iid not in fs.prices.columns:
            continue
        r = fs.value(iid, "return", "1m")
        if np.isfinite(r):
            movers.append((abs(r), iid))
    movers.sort(reverse=True)
    method_a = [EvalObject(iid, METHODS[0], _theme(iid, themes), facts(iid)) for _, iid in movers]
    # B: largest recent anomaly score (one object per theme)
    anom_scores: dict[str, float] = {}
    for a in recent.sort_values("score", ascending=False).itertuples(index=False):
        if a.entity_id in universe.instruments:
            anom_scores[a.entity_id] = max(anom_scores.get(a.entity_id, 0.0), float(a.score))
    ranked_b = sorted(anom_scores.items(), key=lambda kv: -kv[1])
    method_b = [EvalObject(iid, METHODS[1], _theme(iid, themes), facts(iid)) for iid, _ in ranked_b]
    # C: engine candidates (score order, all_scored already sorted)
    method_c = []
    for d in engine_candidates:
        ids = d.primary_ids()
        if not ids:
            continue
        iid = ids[0]
        # NB: no engine-specific fields are added to the fact sheet — the blind
        # rater must not be able to infer which method selected the object.
        f = facts(iid)
        method_c.append(EvalObject(iid, METHODS[2], _theme(iid, themes), f))
    return (_theme_dedupe(method_a), _theme_dedupe(method_b),
            _theme_dedupe(method_c), diag)


def write_blind_input(store: Store, dates: list[str], out_dir: str | Path = "audit") -> dict[str, Any]:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)
    records, mapping, diagnostics = [], {}, {}
    pending: list[tuple[str, str, int, Any]] = []
    for as_of in dates:
        a, b, c, diag = build_eval_objects(store, as_of)
        diagnostics[as_of] = diag
        for method, objs in ((METHODS[0], a), (METHODS[1], b), (METHODS[2], c)):
            for rank, obj in enumerate(objs, start=1):
                pending.append((as_of, method, rank, obj))
    # Assign anonymised ids AFTER a global shuffle, so X01..X36 do not reveal
    # A/B/C blocks (audit R2: the old id order leaked the method).
    rng.shuffle(pending)
    for i, (as_of, method, rank, obj) in enumerate(pending, start=1):
        token = f"X{i:02d}"
        mapping[token] = {"as_of": as_of, "method": method, "rank": rank,
                          "entity_id": obj.entity_id, "theme": obj.theme}
        sheet = obj.fact_sheet()
        sheet["object_id"] = token
        records.append({"as_of": as_of, "object_id": token, "facts": sheet})
    rng.shuffle(records)
    payload = {
        "instructions": "Independent research-value rating. Method labels are hidden. "
                        "For each object score four criteria from 0 (no) to 2 (strong), "
                        "using only the supplied facts.",
        "criteria": [
            "real_market_change: there is a genuine, material market change",
            "beyond_price: research value goes beyond a simple price move (mechanism/positioning/valuation/structure)",
            "falsifiable: a specific, falsifiable hypothesis can be formed from these facts",
            "data_sufficiency: enough data is available to start deep research, with gaps stated",
        ],
        "objects": records,
    }
    (out / "research_quality_input.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    (out / "research_quality_mapping.json").write_text(json.dumps(
        {"mapping": mapping, "diagnostics": diagnostics,
         "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return {"n_objects": len(records), "n_dates": len(dates), "path": str(out / "research_quality_input.json")}


def score_blind_ratings(ratings: list[dict[str, Any]], mapping: dict[str, Any],
                        out_path: str | Path = "audit/RESEARCH_QUALITY.md") -> dict[str, Any]:
    """Compute metrics from rater scores (0-2 per criterion)."""
    by_token = {r["object_id"]: r for r in ratings}
    per_method: dict[str, list[float]] = {m: [] for m in METHODS}
    rows = []
    for token, meta in mapping["mapping"].items():
        r = by_token.get(token)
        if not r:
            continue
        scores = [float(r["scores"][c]) for c in r["scores"]]
        mean = sum(scores) / len(scores)
        per_method[meta["method"]].append(mean)
        rows.append({**meta, "mean_score": round(mean, 3), "scores": r["scores"]})
    summary = {}
    for method, vals in per_method.items():
        vals = np.array(vals)
        summary[method] = {
            "n": int(len(vals)),
            "mean_research_score": round(float(vals.mean()), 3) if len(vals) else None,
            "precision_at_3": round(float((vals >= 1.5).mean()), 3) if len(vals) else None,
        }
    df = pd.DataFrame(rows)
    dup = {}
    for method in METHODS:
        sub = df[df.method == method]
        if sub.empty:
            dup[method] = None
            continue
        # duplicate = repeated theme within the same as-of top-3
        d = sub.groupby("as_of")["theme"].apply(lambda s: len(s) - s.nunique()).sum()
        dup[method] = int(d)
    result = {"summary": summary, "duplicate_themes": dup, "n_rated": len(rows)}
    lines = ["# RESEARCH QUALITY — blind benchmark evaluation", "",
             f"- rated objects: {len(rows)}",
             "- rater: independent LLM reviewer, method labels hidden; 4 criteria scored 0-2",
             "- limitation: historical objects, no human labels, no return/profitability claim; "
             "a single rater is not statistical proof", "",
             "| method | n | mean research score (0-2) | Precision@3 (mean≥1.5) | duplicate themes |",
             "|---|---|---|---|---|"]
    for m in METHODS:
        s = summary[m]
        lines.append(f"| {m} | {s['n']} | {s['mean_research_score']} | {s['precision_at_3']} | {dup[m]} |")
    lines += ["", "Method A = largest absolute 1m return; B = largest recent anomaly score; C = engine.", ""]
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    return result
