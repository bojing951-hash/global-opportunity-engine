"""Point-in-time historical validation.

Two instruments of validation are provided:

``run_case_validation``
    Seven pre-registered episodes (COVID crash, 2022 rate shock, UK gilt crisis,
    SVB, yen carry unwind, China policy rally, gold vs real rates). Each case
    asks: *given only the data visible at ``as_of``, did the engine flag the
    phenomenon?* It measures **detection**, not returns. Case definitions live in
    ``config/cases.yaml`` and are checked against detectors, anomaly families and
    transmission mechanisms.

``run_replay``
    A grid of as-of dates with a fixed step. For each date the full detection /
    transmission / opportunity logic is executed without persisting anything, so
    the live pipeline is never polluted by synthetic history. Output: detection
    frequency, archetype mix, score distribution and stability of recurring
    candidates.

Look-ahead control
------------------
* ``FeatureBuilder(point_in_time=True)`` truncates prices at ``as_of`` and shifts
  macro observations by their publication lag.
* ``no_lookahead_diff`` compares feature values computed at two different as-of
  dates over their common history; a non-zero difference indicates leakage.
* Nothing in the replay writes to the live opportunity tables.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from . import project_root
from .anomalies import detect_anomalies
from .config import load_themes, load_yaml_config
from .db import Store
from .events import EventCalendar
from .features import FeatureBuilder, FeatureSet
from .opportunities import OpportunityEngine
from .transmission.evaluator import MechanismEvaluator, evaluate_transmissions


def _out_dir(out_dir: str | Path | None) -> Path:
    p = Path(out_dir) if out_dir else project_root() / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _build(store: Store, as_of: str, history_start: str) -> FeatureSet:
    return FeatureBuilder(store, as_of=as_of, point_in_time=True, history_start=history_start).build()


def run_case_validation(store: Store, out_dir: str | Path | None = None,
                        cases: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cases if cases is not None else load_yaml_config("cases.yaml")
    case_defs = cfg.get("cases", {})
    mech_cfg = load_yaml_config("mechanisms.yaml")
    scoring = load_yaml_config("scoring.yaml")
    events = EventCalendar.load()
    results = []
    for cid, c in case_defs.items():
        print(f"[case] {cid} starting", flush=True)
        win = c.get("window", [])
        as_of = c.get("as_of") or (win[-1] if win else "")
        start, end = (win + [as_of, as_of])[:2] if win else (as_of, as_of)
        hist = (pd.Timestamp(start) - pd.DateOffset(years=3)).strftime("%Y-%m-%d")
        try:
            fs = _build(store, as_of, hist)
            anomalies = detect_anomalies(fs, since=start)
            window_anoms = anomalies[(anomalies.date >= start) & (anomalies.date <= end)] \
                if not anomalies.empty else anomalies
            entities = set(c.get("entities", []) or [])
            if entities:
                ent_anoms = window_anoms[window_anoms.entity_id.isin(entities)]
            else:
                ent_anoms = window_anoms
            # Detectors are evaluated globally within the window: several detectors
            # attach to synthetic entities (CREDIT_RISK, gold_dollar, policy series),
            # so restricting to instrument ids would make them invisible.
            found_detectors = sorted(set(window_anoms.detector)) if not window_anoms.empty else []
            # anomaly families are evaluated over the whole window: pair-level
            # anomalies (e.g. cross_asset divergence) are not attached to a
            # single instrument, so restricting families to case entities would
            # make them unobservable by construction.
            found_families = sorted(set(window_anoms.family)) if not window_anoms.empty else []
            earliest = {}
            if not ent_anoms.empty:
                for det, g in ent_anoms.groupby("detector"):
                    earliest[det] = min(g.date)
            # Mechanisms are evaluated at several points inside the window (a
            # transmission can be activated and decay before as_of); the union of
            # statuses is reported, with the earliest activation date.
            # Evaluate at up to six points in the window with ONE evaluator, so that
            # resolved series are cached across evaluations (an episode can be
            # activated and decay before as_of).
            n_eval = 8
            eval_dates = [d.strftime("%Y-%m-%d") for d in
                          pd.date_range(start, end, periods=n_eval)] if end > str(start) else [as_of]
            if eval_dates[-1] != as_of:
                eval_dates.append(as_of)
            def _avail_dates(frame: pd.DataFrame) -> pd.Series:
                if frame is None or frame.empty:
                    return pd.Series(dtype="datetime64[ns]")
                col = "available_date" if "available_date" in frame.columns else "date"
                return pd.to_datetime(frame[col])

            mech_union: dict[str, list[dict[str, Any]]] = {}
            episode_drafts: list[Any] = []
            for ed in eval_dates:
                # Each evaluation date gets its own point-in-time view: prices,
                # macro and positioning truncated to what was known at ed, and
                # anomalies filtered by AVAILABILITY (not observation date).
                fs_ed = fs.slice_as_of(ed)
                _avail = _avail_dates(anomalies)
                _recent = anomalies[(_avail >= pd.Timestamp(ed) - pd.Timedelta(days=10))
                                   & (_avail <= pd.Timestamp(ed))] if not anomalies.empty else anomalies
                try:
                    _mechs = MechanismEvaluator(fs_ed, mech_cfg).evaluate(_recent)
                except Exception:
                    _mechs = []
                for m in _mechs:
                    mech_union.setdefault(m.mechanism_id, []).append(
                        {"as_of": ed, "status": m.status, "confidence": round(m.confidence, 2)})
                # Opportunities are generated at each evaluation point so the case
                # measures whether the phenomenon surfaced DURING the episode, not
                # only on the final as-of date after the anomaly had decayed.
                try:
                    _eng = OpportunityEngine(fs_ed, _recent, _mechs, events, scoring, max_candidates=25)
                    _eng.generate()
                    episode_drafts.extend(getattr(_eng, "all_scored", []))
                except Exception:
                    pass
            expected_mechs = c.get("expect_mechanisms", []) or []
            mech_checks = {}
            for mid in expected_mechs:
                hist = mech_union.get(mid, [])
                statuses = [h["status"] for h in hist]
                if not hist:
                    mech_checks[mid] = "not_activated"
                elif "supported" in statuses:
                    mech_checks[mid] = "supported"
                elif "mixed" in statuses:
                    mech_checks[mid] = "mixed"
                elif "weak" in statuses:
                    mech_checks[mid] = "weak"
                elif "insufficient_data" in statuses:
                    mech_checks[mid] = "insufficient_data"
                else:
                    mech_checks[mid] = statuses[-1]
            _avail_all = _avail_dates(anomalies)
            last_recent = anomalies[(_avail_all >= pd.Timestamp(as_of) - pd.Timedelta(days=10))
                                    & (_avail_all <= pd.Timestamp(as_of))] if not anomalies.empty else anomalies
            fs_end = fs.slice_as_of(as_of)
            mech_results = MechanismEvaluator(fs_end, mech_cfg).evaluate(last_recent)
            # opportunity generation (not persisted)
            engine = OpportunityEngine(fs_end, anomalies[(_avail_all <= pd.Timestamp(as_of))]
                                       if not anomalies.empty else anomalies,
                                       mech_results, events, scoring, max_candidates=25)
            drafts = engine.generate()
            # union of the as-of drafts and all episode drafts, best score per fingerprint
            _by_fp: dict[str, Any] = {}
            for _d in list(drafts) + episode_drafts + list(getattr(engine, "all_scored", [])):
                fp = _d.fingerprint()
                if fp not in _by_fp or _d.score > _by_fp[fp].score:
                    _by_fp[fp] = _d
            episode_best = sorted(_by_fp.values(), key=lambda x: x.score, reverse=True)
            top = [{"title": d.title, "archetype": d.archetype, "score": d.score, "status": d.status,
                    "primary": d.primary_ids()} for d in episode_best[:5]]
            case_themes = {load_themes().get(x, x) for x in entities} if entities else set()
            relevant = [d for d in episode_best
                        if d.status != "excluded" and (
                            bool(set(d.primary_ids()) & entities)
                            or (bool(entities) and d.primary_ids()
                                and load_themes().get(d.primary_ids()[0], "") in case_themes)
                        )]
            relevant_candidate = len(relevant) > 0
            relevant_summary = [{"title": d.title, "status": d.status, "score": round(d.score, 3),
                                 "primary": d.primary_ids()} for d in relevant[:3]]
            exp_det = set(c.get("expect_detectors", []) or [])
            exp_fam = set(c.get("expect_families", []) or [])
            checks = {
                "detectors_expected": sorted(exp_det),
                "detectors_found": found_detectors,
                "detectors_hit": sorted(exp_det & set(found_detectors)),
                "families_expected": sorted(exp_fam),
                "families_found": found_families,
                "mechanisms": mech_checks,
            }
            det_hit = len(exp_det & set(found_detectors))
            fam_hit = len(exp_fam & set(found_families))
            detection_ok = (det_hit > 0) or (fam_hit > 0)
            mech_ok = any(v in ("supported", "mixed") for v in mech_checks.values()) if mech_checks else True
            mech_evaluated = all(v not in ("not_activated",) for v in mech_checks.values()) if mech_checks else True
            # A case passes when the phenomenon was detected AND at least one of
            # the affected assets actually produced a candidate. Mechanism status
            # is reported separately: a refuted mechanism is a valid research
            # finding, not a detection failure.
            passed = bool(detection_ok and relevant_candidate)
            print(f"[case] {cid} done: detectors={len(found_detectors)} mechs_eval={len(mech_checks)} "
                  f"opps={len(drafts)}", flush=True)
            results.append({
                "case_id": cid, "title": c.get("title", cid), "window": [start, end], "as_of": as_of,
                "passed": passed,
                "detection_ok": bool(detection_ok), "mechanism_ok": bool(mech_ok),
                "mechanism_evaluated": bool(mech_evaluated),
                "relevant_candidate": bool(relevant_candidate),
                "relevant_candidates": relevant_summary,
                "checks": checks,
                "n_anomalies_in_window": int(len(window_anoms)),
                "n_anomalies_on_case_entities": int(len(ent_anoms)),
                "earliest_detection": earliest,
                "mechanisms": [{"id": m.mechanism_id, "status": m.status, "confidence": round(m.confidence, 2)}
                               for m in mech_results],
                "top_opportunities": top,
                "note": c.get("note", ""), "data_note": _data_note(fs),
            })
        except Exception as exc:  # noqa: BLE001 - one case must not kill the run
            results.append({"case_id": cid, "title": c.get("title", cid), "window": [start, end],
                            "as_of": as_of, "passed": False,
                            "error": f"{type(exc).__name__}: {exc}"})
    summary = {
        "n_cases": len(results),
        "n_passed": sum(1 for r in results if r.get("passed")),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "point-in-time feature build; macro release lag applied; detection not profitability",
    }
    payload = {"summary": summary, "cases": results}
    out = _out_dir(out_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (out / f"validation_cases_{stamp}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out / f"validation_cases_{stamp}.md").write_text(_cases_markdown(payload), encoding="utf-8")
    return payload


def _data_note(fs: FeatureSet) -> dict[str, Any]:
    return {
        "n_instruments": fs.meta.get("n_instruments"),
        "n_curves": fs.meta.get("n_curve_systems"),
        "n_macro": fs.meta.get("n_macro_series"),
        "stale_macro_series": fs.meta.get("stale_macro_series", {}),
    }


def _cases_markdown(payload: dict[str, Any]) -> str:
    lines = ["# 历史案例验证（时点回放）", "",
             f"- 生成时间：{payload['summary']['generated_at']}",
             f"- 方法：{payload['summary']['method']}",
             f"- 通过：{payload['summary']['n_passed']} / {payload['summary']['n_cases']}", "",
             "| 案例 | 结果 | 命中检测器 | 相关候选 | 机制状态 | 窗口异常数 |",
             "|---|---|---|---|---|---|"]
    for r in payload["cases"]:
        if "error" in r:
            lines.append(f"| {r['title']} | ERROR | {r['error'][:80]} | - | - | - |")
            continue
        det = "、".join(r["checks"]["detectors_hit"]) or "—"
        mech = "；".join(f"{k}={v}" for k, v in r["checks"]["mechanisms"].items()) or "—"
        rel = r.get("relevant_candidates") or []
        rel_txt = ("；".join(f"{(x.get('title') or '')[:40]}({x.get('status')})" for x in rel) if rel
                   else ("未生成候选" if not r.get("relevant_candidate") else "—"))
        lines.append(f"| {r['title']} | {'✅ PASS' if r['passed'] else '❌ FAIL'} | {det} | {rel_txt} | {mech} | "
                     f"{r['n_anomalies_in_window']} |")
    lines += ["", "> 通过标准：窗口内至少命中一个预期检测器（或异常家族），**且**受影响资产在该时点生成了候选机会。"
                  "机制状态单列报告：机制被证伪（unsupported）是有效的负面研究结论，不计为检测失败。"
                  "该验证衡量“能否发现值得研究的现象”，不衡量投资收益。", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------- replay
def run_replay(store: Store, start: str | None = None, end: str | None = None,
               step: int = 21, out_dir: str | Path | None = None) -> dict[str, Any]:
    last = store.scalar("SELECT MAX(date) FROM prices")
    end = end or last
    start = start or (pd.Timestamp(end) - pd.DateOffset(years=3)).strftime("%Y-%m-%d")
    dates = [d.strftime("%Y-%m-%d") for d in pd.date_range(start, end, freq=f"{int(step)}D")]
    if not dates or dates[-1] != end:
        dates.append(end)
    scoring = load_yaml_config("scoring.yaml")
    mech_cfg = load_yaml_config("mechanisms.yaml")
    events = EventCalendar.load()
    rows = []
    for i, d in enumerate(dates):
        hist = (pd.Timestamp(d) - pd.DateOffset(years=3)).strftime("%Y-%m-%d")
        try:
            fs = _build(store, d, hist)
            anomalies = detect_anomalies(fs, since=(pd.Timestamp(d) - pd.Timedelta(days=45)).strftime("%Y-%m-%d"))
            recent = anomalies[pd.to_datetime(anomalies.date) >= (
                pd.Timestamp(d) - pd.Timedelta(days=10))] if not anomalies.empty else anomalies
            _, mechs = evaluate_transmissions(fs, recent, mech_cfg)
            engine = OpportunityEngine(fs, anomalies, mechs, events, scoring, max_candidates=25)
            drafts = engine.generate()
            rows.append({
                "as_of": d,
                "n_anomalies": int(len(anomalies)),
                "by_family": anomalies.family.value_counts().to_dict() if not anomalies.empty else {},
                "n_transmissions": len(mechs),
                "mechanisms_supported": [m.mechanism_id for m in mechs if m.status == "supported"],
                "n_opportunities": len(drafts),
                "by_archetype": pd.Series([x.archetype for x in drafts]).value_counts().to_dict() if drafts else {},
                "by_status": pd.Series([x.status for x in drafts]).value_counts().to_dict() if drafts else {},
                "top": [{"fingerprint": x.fingerprint(), "title": x.title, "score": round(x.score, 3),
                         "status": x.status, "archetype": x.archetype} for x in drafts[:5]],
                "coverage": {"n_instruments": fs.meta.get("n_instruments"),
                             "n_macro": fs.meta.get("n_macro_series"),
                             "n_curves": fs.meta.get("n_curve_systems")},
            })
        except Exception as exc:  # noqa: BLE001
            rows.append({"as_of": d, "error": f"{type(exc).__name__}: {exc}"})
        print(f"replay {i + 1}/{len(dates)} {d} "
              f"anoms={rows[-1].get('n_anomalies')} opps={rows[-1].get('n_opportunities')}", flush=True)
    ok = [r for r in rows if "error" not in r]
    summary = {
        "start": start, "end": end, "step_days": step, "n_dates": len(dates), "n_ok": len(ok),
        "avg_anomalies": round(float(np.mean([r["n_anomalies"] for r in ok])), 1) if ok else 0,
        "avg_transmissions": round(float(np.mean([r["n_transmissions"] for r in ok])), 2) if ok else 0,
        "avg_opportunities": round(float(np.mean([r["n_opportunities"] for r in ok])), 2) if ok else 0,
        "archetype_totals": _sum_dicts([r["by_archetype"] for r in ok]),
        "status_totals": _sum_dicts([r["by_status"] for r in ok]),
        "recurring_fingerprints": _recurring(ok),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    payload = {"summary": summary, "replay": rows}
    out = _out_dir(out_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (out / f"replay_{start}_{end}_{stamp}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out / f"replay_{start}_{end}_{stamp}.md").write_text(_replay_markdown(payload), encoding="utf-8")
    return payload


def _sum_dicts(dicts: Iterable[dict[str, int]]) -> dict[str, int]:
    total: dict[str, int] = {}
    for d in dicts:
        for k, v in (d or {}).items():
            total[k] = total.get(k, 0) + int(v)
    return dict(sorted(total.items(), key=lambda kv: -kv[1]))


def _recurring(rows: list[dict[str, Any]], min_count: int = 3) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for r in rows:
        for t in r.get("top", []):
            c = counts.setdefault(t["fingerprint"], {"title": t["title"], "n": 0, "archetype": t["archetype"]})
            c["n"] += 1
    return [{"fingerprint": k, **v} for k, v in sorted(counts.items(), key=lambda kv: -kv[1]["n"])
            if v["n"] >= min_count][:20]


def _replay_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = ["# 时点回放验证", "",
             f"- 区间：{s['start']} → {s['end']}，步长 {s['step_days']} 天，{s['n_ok']}/{s['n_dates']} 个时点成功",
             f"- 平均异常数：{s['avg_anomalies']}；平均激活机制：{s['avg_transmissions']}；平均候选机会：{s['avg_opportunities']}",
             f"- 机会类型累计：{s['archetype_totals']}",
             f"- 状态累计：{s['status_totals']}", "",
             "| 时点 | 异常数 | 机制数 | 候选数 | 主要类型 |", "|---|---|---|---|---|"]
    for r in payload["replay"]:
        if "error" in r:
            lines.append(f"| {r['as_of']} | ERROR | - | - | {r['error'][:60]} |")
            continue
        arch = "、".join(f"{k}:{v}" for k, v in r["by_archetype"].items()) or "—"
        lines.append(f"| {r['as_of']} | {r['n_anomalies']} | {r['n_transmissions']} | "
                     f"{r['n_opportunities']} | {arch} |")
    if s["recurring_fingerprints"]:
        lines += ["", "## 反复出现的候选（跨时点稳定）", ""]
        for f in s["recurring_fingerprints"]:
            lines.append(f"- `{f['fingerprint']}` ×{f['n']}：{f['title']}")
    lines += ["", "> 回放只做检测与机会生成，不写入正式机会库；分数衡量研究优先级，不代表收益。", ""]
    return "\n".join(lines)


# -------------------------------------------------------------- lookahead help
def no_lookahead_diff(store: Store, date_a: str, date_b: str,
                      entities: Iterable[str] | None = None, features: Iterable[str] | None = None) -> dict[str, Any]:
    """Compare features computed at two as-of dates over their common history.

    A non-zero maximum absolute difference means a feature at an earlier date
    depends on data from later dates (look-ahead leakage). Macro series are
    expected to differ only through the publication-lag filter, which is applied
    identically in both builds.
    """
    hist_a = (pd.Timestamp(store.scalar("SELECT MIN(date) FROM prices"))).strftime("%Y-%m-%d")
    fs_a = FeatureBuilder(store, as_of=date_a, point_in_time=True, history_start=hist_a).build()
    fs_b = FeatureBuilder(store, as_of=date_b, point_in_time=True, history_start=hist_a).build()
    fset = set(features or ["return", "ann_vol", "drawdown_252d", "ma_gap_200d", "return_z_3y",
                            "slope_2s10s", "value", "net_pctile_5y"])
    a = fs_a.long[fs_a.long.entity_kind != "macro"] if "value" not in fset else fs_a.long
    a = a[a.feature.isin(fset)]
    b = fs_b.long[fs_b.long.entity_kind != "macro"] if "value" not in fset else fs_b.long
    b = b[b.feature.isin(fset)]
    if entities:
        ids = set(entities)
        a = a[a.entity_id.isin(ids)]
        b = b[b.entity_id.isin(ids)]
    keys = ["entity_kind", "entity_id", "feature", "window", "date"]
    merged = a.merge(b, on=keys, suffixes=("_a", "_b"))
    merged = merged[merged.date <= date_a]
    if merged.empty:
        return {"n_compared": 0, "max_abs_diff": None, "status": "no_overlap"}
    diff = (merged["value_a"] - merged["value_b"]).abs()
    # tolerate float noise only
    worst = merged.loc[diff.idxmax(), keys + ["value_a", "value_b"]].to_dict()
    return {
        "n_compared": int(len(merged)),
        "max_abs_diff": float(diff.max()),
        "mean_abs_diff": float(diff.mean()),
        "worst": {k: (str(v) if not isinstance(v, (int, float)) else v) for k, v in worst.items()},
        "leakage_detected": bool(diff.max() > 1e-5),
    }
