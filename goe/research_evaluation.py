"""Four-method evaluation harness for Research Discovery V2.

Methods A/B/C/D share one FeatureSet/anomaly/mechanism snapshot per date. Fact cards
are method-blind (no V1/V2 scores, hypotheses or tier). Test-split labels are not
imputed from returns.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .anomalies import detect_anomalies
from .config import load_macro, load_positioning, load_themes, load_universe, load_yaml_config
from .db import Store
from .evaluation import _instrument_facts, _theme_dedupe, EvalObject
from .features import FeatureBuilder
from .opportunities import OpportunityEngine
from .research_triage import build_candidates
from .timesemantics import filter_recent
from .transmission.evaluator import MechanismEvaluator

METHODS = ("A_price_move", "B_anomaly_score", "C_v1_score", "D_v2_triage")
DEV_DATES = ["2022-10-31", "2024-09-30"]
VALIDATION_DATES = ["2023-03-31"]
TEST_DATES = ["2021-12-31"]


def _v2_fact_sheet(fs, iid, positioning, mech_by_asset, recent) -> dict[str, Any]:
    # identical schema/facts to A/B/C; deliberately no hypotheses/tier/score
    return _instrument_facts(fs, iid, positioning, mech_by_asset, recent)


def build_methods(store: Store, as_of: str) -> tuple[dict[str, list[EvalObject]], dict[str, Any]]:
    universe = load_universe()
    themes = load_themes()
    positioning = load_positioning()
    fs = FeatureBuilder(store, as_of=as_of, point_in_time=True,
                        history_start=(pd.Timestamp(as_of) - pd.DateOffset(years=8)).strftime("%Y-%m-%d")).build()
    anomalies = detect_anomalies(fs, since=(pd.Timestamp(as_of) - pd.Timedelta(days=200)).strftime("%Y-%m-%d"))
    if anomalies.attrs.get("errors"):
        raise RuntimeError("detector errors: " + "; ".join(anomalies.attrs["errors"]))
    recent = filter_recent(anomalies, pd.Timestamp(as_of))
    mechs = MechanismEvaluator(fs, load_yaml_config("mechanisms.yaml")).evaluate(recent)
    mech_by_asset: dict[str, list[dict]] = {}
    for m in mechs:
        for a in m.assets:
            if a.get("id"):
                mech_by_asset.setdefault(a["id"], []).append(
                    {"id": m.mechanism_id, "status": m.status, "confidence": round(m.confidence, 2),
                     "role": a.get("role")})
    v1 = OpportunityEngine(fs, anomalies, mechs, None, load_yaml_config("scoring.yaml"),
                           max_candidates=25, store=store)
    v1.generate()
    v1_candidates = getattr(v1, "all_scored", [])

    def facts(iid):
        return _v2_fact_sheet(fs, iid, positioning, mech_by_asset, recent)

    # A: max |1m|
    movers = []
    for iid in universe.instruments:
        if iid in fs.prices.columns:
            r = fs.value(iid, "return", "1m")
            if np.isfinite(r):
                movers.append((abs(float(r)), iid))
    movers.sort(reverse=True)
    a = [EvalObject(iid, METHODS[0], themes.get(iid, iid), facts(iid)) for _, iid in movers]
    # B: max recent anomaly
    scores: dict[str, float] = {}
    for row in recent.sort_values("score", ascending=False).itertuples(index=False):
        if row.entity_id in universe.instruments:
            scores[row.entity_id] = max(scores.get(row.entity_id, 0.0), float(row.score))
    b = [EvalObject(iid, METHODS[1], themes.get(iid, iid), facts(iid))
         for iid, _ in sorted(scores.items(), key=lambda kv: -kv[1])]
    # C: V1
    c = []
    for d in v1_candidates:
        ids = d.primary_ids()
        if ids:
            c.append(EvalObject(ids[0], METHODS[2], themes.get(ids[0], ids[0]), facts(ids[0])))
    # D: V2 triage (same fs/anomalies/mechs; no V1 ranking)
    d_objs = []
    for cand in build_candidates(fs, anomalies, mechs, max_candidates=10):
        if cand.priority_tier == "intelligence" or not cand.instruments:
            continue
        iid = cand.instruments[0]
        if iid not in universe.instruments:
            continue
        d_objs.append(EvalObject(iid, METHODS[3], themes.get(iid, iid), facts(iid)))
    diag = {"as_of": as_of, "n_anomalies": int(len(anomalies)),
            "n_recent": int(len(recent)), "n_mechanisms": len(mechs),
            "v1_candidates": len(v1_candidates),
            "v2_candidates": len([x for x in build_candidates(fs, anomalies, mechs, max_candidates=10)
                                  if x.priority_tier != "intelligence"])}
    return {"A_price_move": _theme_dedupe(a), "B_anomaly_score": _theme_dedupe(b),
            "C_v1_score": _theme_dedupe(c), "D_v2_triage": _theme_dedupe(d_objs)}, diag


def write_blind_input(store: Store, dates: list[str], out_dir: str | Path = "evaluation") -> dict[str, Any]:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261114)
    pending, diag = [], {}
    for as_of in dates:
        methods, d = build_methods(store, as_of)
        diag[as_of] = d
        for method, objs in methods.items():
            for rank, obj in enumerate(objs, start=1):
                pending.append((as_of, method, rank, obj))
    rng.shuffle(pending)
    records, mapping = [], {}
    for i, (as_of, method, rank, obj) in enumerate(pending, start=1):
        token = f"V{i:02d}"
        mapping[token] = {"as_of": as_of, "method": method, "rank": rank,
                          "entity_id": obj.entity_id, "theme": obj.theme}
        sheet = obj.fact_sheet(); sheet["object_id"] = token
        records.append({"as_of": as_of, "object_id": token, "facts": sheet})
    payload = {"instructions": "Independent research-value rating; methods hidden; "
                              "score four criteria 0-2 from the facts only.",
               "criteria": ["real_market_change", "beyond_price", "falsifiable", "data_sufficiency"],
               "objects": records}
    (out / "v2_eval_input.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                                            encoding="utf-8")
    (out / "v2_eval_mapping.json").write_text(json.dumps(
        {"mapping": mapping, "diagnostics": diag, "splits": {
            "development": DEV_DATES, "validation": VALIDATION_DATES, "test": TEST_DATES}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return {"n_objects": len(records), "n_dates": len(dates), "path": str(out / "v2_eval_input.json")}


def score_ratings(ratings: list[dict[str, Any]], mapping: dict[str, Any],
                  out_dir: str | Path = "evaluation") -> dict[str, Any]:
    import numpy as np
    by_token = {r["object_id"]: r for r in ratings}
    rows = []
    for token, meta in mapping["mapping"].items():
        r = by_token.get(token)
        if not r:
            continue
        scores = {k: float(v) for k, v in r["scores"].items()}
        rows.append({**meta, "mean": sum(scores.values()) / len(scores), **scores})
    if not rows:
        raise ValueError("no ratings matched mapping")
    df = pd.DataFrame(rows)
    splits = mapping.get("splits", {})
    def split_of(d):
        for name, dates in splits.items():
            if d in dates:
                return name
        return "unknown"
    df["split"] = df["as_of"].map(split_of)
    summary = {}
    for method in METHODS:
        sub = df[df.method == method]
        if sub.empty:
            continue
        summary[method] = {
            "n": int(len(sub)), "mean": round(float(sub["mean"].mean()), 4),
            "precision_at_3": round(float((sub["mean"] >= 1.5).mean()), 4),
            "evidence_sufficiency": round(float(sub["data_sufficiency"].mean()), 4),
            "falsifiability": round(float(sub["falsifiable"].mean()), 4),
            "duplicate_rate": int(sub.groupby(["as_of", "theme"]).size().gt(1).sum()),
        }
    test = df[df.split == "test"]
    test_summary = {}
    for method in METHODS:
        sub = test[test.method == method]
        if not sub.empty:
            test_summary[method] = {"n": int(len(sub)),
                                    "mean": round(float(sub["mean"].mean()), 4),
                                    "precision_at_3": round(float((sub["mean"] >= 1.5).mean()), 4)}
    # decision rule: D must beat B and C on both mean and P@3 on test
    dt = test_summary.get("D_v2_triage", {})
    wins = []
    for base in ("B_anomaly_score", "C_v1_score"):
        bs = test_summary.get(base, {})
        wins.append(bool(dt and bs and dt.get("mean", -1) > bs.get("mean", 1)
                         and dt.get("precision_at_3", -1) > bs.get("precision_at_3", 1)))
    validated = bool(dt and all(wins) and dt.get("n", 0) >= 3)
    result = {"summary": summary, "test": test_summary,
              "d_beats_b_and_c_on_test": wins,
              "discovery_value": "VALIDATED" if validated else "NOT VALIDATED",
              "n_rated": int(len(df)),
              "limitations": ["single LLM rater; no human labels; small n; fact-card asymmetry; "
                              "research value is not return prediction"]}
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    (out / "v2_eval_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                                         default=str), encoding="utf-8")
    lines = ["# RESEARCH DISCOVERY V2 — four-method blind evaluation", "",
             f"- rated objects: {len(df)}",
             "- methods: A max move, B max anomaly, C V1 score, D V2 triage",
             "- rater: independent LLM, labels hidden; 4 criteria 0–2",
             "- limitation: no human labels; small n; fact-card asymmetry; not a return test", "",
             "| method | n | mean worthiness | P@3 | evidence sufficiency | falsifiability | duplicate themes |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for m in METHODS:
        s = summary.get(m)
        if s:
            lines.append(f"| {m} | {s['n']} | {s['mean']} | {s['precision_at_3']} | "
                         f"{s['evidence_sufficiency']} | {s['falsifiability']} | {s['duplicate_rate']} |")
    lines += ["", "## Test split (2021-12-31; held out)", "",
              "| method | n | mean | P@3 |", "|---|---:|---:|---:|"]
    for m in METHODS:
        s = test_summary.get(m)
        if s:
            lines.append(f"| {m} | {s['n']} | {s['mean']} | {s['precision_at_3']} |")
    lines += ["", f"**DISCOVERY VALUE: {result['discovery_value']}**",
              f"- D beats B and C on test (mean and P@3): {wins}",
              "- If NOT VALIDATED: do not tune V2 weights on this test date; report failure.",
              ""]
    (out / "V2_EVALUATION_RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    return result
