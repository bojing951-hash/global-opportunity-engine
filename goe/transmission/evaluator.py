"""Transmission mechanism evaluation.

The mechanism catalogue lives in ``config/mechanisms.yaml``. Each mechanism is a
*conditional hypothesis*: "when X moves, Y is expected to move because Z". This
module does four things for every activated mechanism:

1. **Activation** — the mechanism's trigger variables must show a detected
   anomaly at the as-of date (direction-aware). No anomaly, no transmission.
2. **Evidence for** — statistical tests declared in the config: rolling
   correlation sign/magnitude/stability, lead-lag cross-correlation, and
   descriptive conditional forward returns of the affected asset after similar
   macro states.
3. **Evidence against** — failed tests, unstable/insignificant relationships,
   contradictions across tests, and data gaps. A mechanism is never reported as
   "supported" without at least one passing test and no contradiction.
4. **Conditions & falsifiers** — carried from the catalogue so the research
   consumer knows when the hypothesis stops applying.

Statistical honesty rules implemented here:
* correlations are computed on the *transform* declared by the test (changes by
  default for non-stationary series), never on raw levels unless requested;
* rolling windows are trailing-only, so the as-of evaluation is point-in-time;
* conditional forward statistics are explicitly labelled descriptive and are
  never used as a forecast or a return estimate;
* "correlation != causation" is encoded in ``identification`` on every row.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

import numpy as np
import pandas as pd

from ..config import load_yaml_config
from ..features import FeatureSet
from ..timesemantics import filter_recent

# direction wording -> sign  (used to align anomalies with trigger directions)
_NEG = ("down", "underperform", "below_norm", "flattening", "compression", "deep_drawdown",
        "death_cross", "crowded_short", "yields_down", "hy_underperform", "corr_break_down",
        "risk_off", "stress", "term_inverted")
_POS = ("up", "outperform", "above_norm", "steepening", "expansion", "near_high",
        "golden_cross", "crowded_long", "yields_up", "hy_outperform", "corr_break_up",
        "risk_on", "high_dispersion")


def _normal_two_sided_p(t: float) -> float:
    """Two-sided p-value from a normal approximation (no scipy dependency)."""
    import math

    if not np.isfinite(t):
        return 1.0
    return float(max(0.0, min(1.0, math.erfc(abs(t) / math.sqrt(2.0)))))


def _fisher_p(corr: float, n_eff: float) -> float:
    if not np.isfinite(corr) or n_eff <= 3:
        return 1.0
    if abs(corr) >= 0.9999:
        return 0.0
    z = np.arctanh(corr) * np.sqrt(max(1.0, n_eff - 3))
    return _normal_two_sided_p(float(z))


def bh_fdr(pvalues: list[float], q: float = 0.10) -> list[float]:
    """Benjamini-Hochberg adjusted p-values (monotone)."""
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvalues[i])
    adj = [1.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        val = min(prev, pvalues[idx] * m / rank)
        adj[idx] = val
        prev = val
    return adj


def direction_sign(direction: str) -> int:
    d = (direction or "").lower()
    if any(k in d for k in _NEG):
        return -1
    if any(k in d for k in _POS):
        return 1
    return 0


@dataclass
class TestResult:
    test_type: str
    passed: bool
    stats: dict[str, Any]
    statement: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"test_type": self.test_type, "passed": self.passed, "stats": self.stats,
                "statement": self.statement, "reason": self.reason}


@dataclass
class MechanismResult:
    mechanism_id: str
    title: str
    family: str
    as_of: str
    transmission_id: str
    triggers: list[dict[str, Any]]
    assets: list[dict[str, Any]]
    evidence_for: list[dict[str, Any]]
    evidence_against: list[dict[str, Any]]
    conditions: list[str]
    falsifiers: list[str]
    confidence: float
    status: str
    notes: str
    identification: str = "correlation_only; causal claim is a hypothesis under conditions"

    def to_row(self) -> dict[str, Any]:
        return {
            "transmission_id": self.transmission_id, "as_of": self.as_of,
            "mechanism_id": self.mechanism_id, "title": self.title,
            "triggers": self.triggers, "assets": self.assets,
            "evidence_for": self.evidence_for, "evidence_against": self.evidence_against,
            "conditions": self.conditions, "confidence": self.confidence,
            "status": self.status, "notes": self.notes,
        }


class MechanismEvaluator:
    def __init__(self, fs: FeatureSet, mechanisms: dict[str, Any] | None = None):
        self.fs = fs
        if mechanisms is not None:
            cfg = mechanisms
        else:
            try:
                cfg = load_yaml_config("mechanisms.yaml")
            except Exception:
                cfg = {}          # mechanism catalogue not installed yet: no transmissions
        self.raw = cfg.get("mechanisms", {}) if isinstance(cfg, dict) else {}
        self.as_of = fs.as_of
        self._series_cache: dict[str, pd.Series] = {}

    # ------------------------------------------------------------------ helpers
    def resolve(self, sid: str) -> pd.Series:
        if sid in self._series_cache:
            return self._series_cache[sid]
        s = pd.Series(dtype=float)
        fs = self.fs
        if sid in fs.prices.columns:
            s = fs.prices[sid].dropna()
            kind = "instrument"
        elif ":" in sid and sid.split(":")[0] in fs.curve:
            cid, tenor = sid.split(":", 1)
            if tenor in fs.curve[cid].columns:
                s = fs.curve[cid][tenor].dropna()
                kind = "rate"
            else:
                kind = ""
        elif sid in fs.macro.columns:
            # transformed macro value from the indexed feature layer (fast; the
            # long-frame filter was O(rows) per test and dominated replay runtime)
            from ..config import load_macro

            spec = load_macro().get(sid)
            s = fs.series(sid, "value", spec.frequency if spec else "monthly")
            if s.empty:
                s = fs.macro[sid].dropna()
            kind = "macro"
        elif sid in fs.positioning.columns:
            s = fs.positioning[sid].dropna()
            kind = "positioning"
        else:
            kind = ""
        self._series_cache[sid] = s if len(s) else s
        self._series_cache[f"__kind__{sid}"] = kind  # type: ignore[assignment]
        return s

    def kind_of(self, sid: str) -> str:
        if f"__kind__{sid}" not in self._series_cache:
            self.resolve(sid)
        return str(self._series_cache.get(f"__kind__{sid}", ""))  # type: ignore[arg-type]

    def _transform(self, s: pd.Series, kind: str, transform: str | None) -> pd.Series:
        if s.empty:
            return s
        if transform is None:
            if kind == "instrument":
                transform = "pct"
            elif kind == "positioning":
                transform = "diff"
            elif kind == "rate":
                transform = "diff"
            else:
                transform = "level"
        if transform == "pct":
            return s.pct_change(fill_method=None) * 100.0
        if transform == "diff":
            return s.diff()
        if transform == "log":
            return np.log(s.replace(0, np.nan)).diff()
        return s

    def _align(self, a: pd.Series, b: pd.Series) -> pd.DataFrame:
        df = pd.concat([a.rename("a"), b.rename("b")], axis=1).sort_index()
        # forward-fill low-frequency series onto the higher-frequency calendar
        df["a"] = df["a"].ffill(limit=6)
        df["b"] = df["b"].ffill(limit=6)
        return df.dropna()

    # ------------------------------------------------------------------- tests
    def corr_test(self, spec: dict[str, Any]) -> TestResult:
        a_id, b_id = spec.get("a", ""), spec.get("b", "")
        window = int(spec.get("window", 250))
        expected = int(spec.get("expected_sign", 1))
        min_abs = float(spec.get("min_abs", 0.15))
        a_raw, b_raw = self.resolve(a_id), self.resolve(b_id)
        empty = TestResult("corr", False, {"a": a_id, "b": b_id}, "数据不足", "missing_series")
        if a_raw.empty or b_raw.empty:
            empty.reason = f"missing series: {[s for s, v in ((a_id, a_raw), (b_id, b_raw)) if v.empty]}"
            return empty
        # `window` in the config is expressed in TRADING DAYS. Convert it to the
        # observation frequency of the inputs (monthly/weekly series are
        # resampled), never the other way round.
        a_raw, b_raw, scale = _normalise_frequency(a_raw, b_raw)
        a = self._transform(a_raw, self.kind_of(a_id), spec.get("transform"))
        b = self._transform(b_raw, self.kind_of(b_id), spec.get("transform"))
        df = self._align(a, b)
        eff_window = max(8, int(round(window / scale)))
        if len(df) < eff_window + 10:
            return TestResult("corr", False, {"a": a_id, "b": b_id, "n": len(df), "window": eff_window},
                              "样本不足，无法评估滚动相关", "insufficient_data")
        rolling = df["a"].rolling(eff_window, min_periods=max(8, eff_window // 3)).corr(df["b"])
        rolling = rolling.dropna()
        if rolling.empty:
            return TestResult("corr", False, {"a": a_id, "b": b_id}, "滚动相关为空", "empty_rolling")
        latest = float(rolling.iloc[-1])
        recent = rolling.iloc[-min(len(rolling), max(60, 3 * eff_window)):]
        stable_share = float((np.sign(recent) == expected).mean())
        # Overlapping windows are not independent observations: effective n is the
        # number of non-overlapping windows in the sample.
        n_eff = max(4.0, len(df) / max(1, eff_window))
        p_value = _fisher_p(latest, n_eff)
        alpha = float(spec.get("alpha", 0.10))
        passed = bool(np.sign(latest) == expected and abs(latest) >= min_abs
                      and stable_share >= 0.55 and p_value <= alpha)
        stats = {
            "a": a_id, "b": b_id, "corr": round(latest, 4), "expected_sign": expected,
            "min_abs": min_abs, "stable_share": round(stable_share, 3),
            "window": eff_window, "n_obs": int(len(df)),
            "n_effective": round(float(n_eff), 2), "p_value": round(float(p_value), 6),
            "alpha": alpha,
            "transform": spec.get("transform") or ("pct" if self.kind_of(a_id) == "instrument" else "diff"),
        }
        statement = (
            f"{a_id} 与 {b_id} 的滚动相关为 {latest:+.2f}（期望符号 {expected:+d}），"
            f"近端窗口符号一致率 {stable_share:.0%}，样本 {len(df)}。"
        )
        reason = "" if passed else ("符号不符" if np.sign(latest) != expected else
                                    ("相关性过弱" if abs(latest) < min_abs else
                                     ("符号不稳定" if stable_share < 0.55 else "不显著")))
        return TestResult("corr", passed, stats, statement, reason)

    def lead_lag_test(self, spec: dict[str, Any]) -> TestResult:
        leader, follower = spec.get("leader", ""), spec.get("follower", "")
        max_lag = int(spec.get("max_lag", 20))
        expected = int(spec.get("expected_sign", 1))
        a, b = self.resolve(leader), self.resolve(follower)
        if a.empty or b.empty:
            return TestResult("lead_lag", False, {"leader": leader, "follower": follower},
                              "数据不足", "missing_series")
        a = self._transform(a, self.kind_of(leader), spec.get("transform"))
        b = self._transform(b, self.kind_of(follower), spec.get("transform"))
        df = self._align(a, b)
        if len(df) < 80:
            return TestResult("lead_lag", False, {"leader": leader, "follower": follower},
                              "样本不足", "insufficient_data")
        window = int(spec.get("window", 250))
        best_lag, best_corr = 0, 0.0
        for lag in range(-max_lag, max_lag + 1):
            # positive lag: leader leads follower by `lag` observations
            c = df["a"].shift(lag).corr(df["b"])
            if pd.notna(c) and abs(c) > abs(best_corr):
                best_lag, best_corr = lag, float(c)
        n_eff = max(4.0, len(df) / max(1, 2 * max_lag + 1))
        # the best lag was chosen out of 2*max_lag+1 candidates: Bonferroni-correct
        # the p-value for the lag search (conservative).
        p_value = min(1.0, _fisher_p(best_corr, n_eff) * (2 * max_lag + 1))
        alpha = float(spec.get("alpha", 0.10))
        passed = bool(np.sign(best_corr) == expected and abs(best_corr) >= float(spec.get("min_abs", 0.10))
                      and best_lag >= 0 and p_value <= alpha)
        stats = {"leader": leader, "follower": follower, "best_lag": best_lag,
                 "best_corr": round(best_corr, 4), "expected_sign": expected, "n_obs": int(len(df)),
                 "window": window, "n_effective": round(float(n_eff), 2),
                 "p_value": round(float(p_value), 6), "alpha": alpha}
        statement = (f"最大互相关出现在滞后 {best_lag} 期（{best_corr:+.2f}，p={p_value:.3f}），"
                     f"领先关系" + ("与假设一致" if passed else "不明显、不显著或方向相反") + "。")
        return TestResult("lead_lag", passed, stats, statement,
                          "" if passed else ("lead_lag_weak" if best_lag < 0 or np.sign(best_corr) != expected
                                             else "不显著"))

    def conditional_return_test(self, spec: dict[str, Any]) -> TestResult:
        cond_id = spec.get("condition_series", "")
        target_id = spec.get("target", "")
        operator = spec.get("operator", ">")
        threshold = float(spec.get("threshold", 0.0))
        horizon = int(spec.get("horizon_days", 63))
        expected = int(spec.get("expected_sign", 1))
        min_obs = int(spec.get("min_observations", 15))
        cond = self.resolve(cond_id)
        target_px = self.resolve(target_id)
        if cond.empty or target_px.empty:
            return TestResult("conditional_return", False, {"condition": cond_id, "target": target_id},
                              "数据不足", "missing_series")
        cond = cond.dropna()
        target_px = target_px.dropna()
        # The condition observation is only KNOWN after its publication lag. Entry
        # must therefore be the first target price on/after (observation + lag),
        # otherwise the conditional statistics use information from the future.
        # Macro feature dates are ALREADY availability dates; adding the release
        # lag again double-counts it (audit R2). No extra lag here.
        cond_lag = 0
        target_index = target_px.index
        events = []
        min_gap_days = max(1, int(horizon * 1.45))
        for ts, value in cond.items():
            if not _cmp(value, operator, threshold):
                continue
            entry_ts = ts + pd.Timedelta(days=cond_lag)
            if events and (entry_ts - pd.Timestamp(events[-1]["date"])).days < min_gap_days:
                continue  # non-overlapping forward windows only
            pos = target_index.searchsorted(entry_ts, side="left")
            if pos == 0 or pos >= len(target_index):
                continue
            start_ts = target_index[pos]
            end_ts_est = start_ts + pd.Timedelta(days=int(horizon * 1.45))
            end_pos = target_index.searchsorted(end_ts_est, side="left")
            if end_pos >= len(target_index):
                continue
            start_px = target_px.iloc[pos]
            end_px = target_px.iloc[min(end_pos, len(target_index) - 1)]
            if start_px <= 0:
                continue
            events.append({"date": start_ts.strftime("%Y-%m-%d"), "ret": end_px / start_px - 1.0})
        if len(events) < min_obs:
            return TestResult("conditional_return", False,
                              {"condition": cond_id, "target": target_id, "n": len(events)},
                              f"历史样本仅 {len(events)} 个，不足 {min_obs}，不做条件统计", "insufficient_data")
        rets = pd.Series([e["ret"] for e in events])
        hit = float((np.sign(rets) == expected).mean())
        mean_ret = float(rets.mean())
        sd = float(rets.std(ddof=1)) if len(rets) > 1 else float("nan")
        t_stat = mean_ret / (sd / np.sqrt(len(rets))) if np.isfinite(sd) and sd > 0 else float("nan")
        p_value = _normal_two_sided_p(t_stat) if np.isfinite(t_stat) else 1.0
        alpha = float(spec.get("alpha", 0.10))
        passed = bool(hit >= 0.55 and np.sign(mean_ret) == expected and p_value <= alpha)
        stats = {"condition": cond_id, "operator": operator, "threshold": threshold,
                 "target": target_id, "horizon_days": horizon, "n": int(len(events)),
                 "publication_lag_days": cond_lag,
                 "first_entry": events[0]["date"] if events else None,
                 "mean_return": round(mean_ret, 4), "median_return": round(float(rets.median()), 4),
                 "hit_rate": round(hit, 3), "expected_sign": expected,
                 "t_stat": None if not np.isfinite(t_stat) else round(float(t_stat), 3),
                 "p_value": round(float(p_value), 6), "alpha": alpha,
                 "n_effective": int(len(rets)), "non_overlapping": True,
                 "note": "描述性历史统计，不是预测或收益承诺；样本已去除重叠，p 值为正态近似。"}
        statement = (f"历史上 {cond_id} {operator} {threshold} 的 {len(events)} 个样本中，"
                     f"{target_id} 其后约 {horizon} 个交易日平均收益 {mean_ret:+.1%}，"
                     f"符号命中率 {hit:.0%}。")
        reason = "" if passed else ("conditional_weak" if hit < 0.55 or np.sign(mean_ret) != expected else "不显著")
        return TestResult("conditional_return", passed, stats, statement, reason)

    def run_tests(self, mechanism: dict[str, Any]) -> list[TestResult]:
        out = []
        for spec in mechanism.get("evidence_tests", []) or []:
            ttype = spec.get("type")
            try:
                if ttype == "corr":
                    out.append(self.corr_test(spec))
                elif ttype == "lead_lag":
                    out.append(self.lead_lag_test(spec))
                elif ttype == "conditional_return":
                    out.append(self.conditional_return_test(spec))
            except Exception as exc:  # noqa: BLE001 - one test must not kill a mechanism
                out.append(TestResult(str(ttype), False, {"error": str(exc)},
                                      "测试执行失败", f"{type(exc).__name__}"))
        return out

    # -------------------------------------------------------------- activation
    @staticmethod
    def _trigger_matches(trigger: dict[str, Any], anomalies: pd.DataFrame) -> list[dict[str, Any]]:
        sid = trigger.get("series", "")
        if not sid:
            return []
        want = (trigger.get("direction") or "any").lower()
        want_sign = {"up": 1, "down": -1}.get(want, 0)
        sub = anomalies[anomalies.entity_id == sid]
        if sub.empty:
            return []
        matches = []
        for row in sub.itertuples(index=False):
            sign = direction_sign(row.direction)
            if want_sign != 0 and sign != want_sign:
                continue
            matches.append({"entity_id": sid, "direction": row.direction, "detector": row.detector,
                            "score": float(row.score), "anomaly_id": row.anomaly_id})
        return matches

    def evaluate(self, anomalies: pd.DataFrame, min_triggers: int = 1) -> list[MechanismResult]:
        if anomalies.empty:
            return []
        _dates = pd.to_datetime(anomalies["available_date"]) \
            if "available_date" in anomalies.columns else pd.to_datetime(anomalies["date"])
        # anchor the activation window on the newest AVAILABLE observation in the
        # supplied frame (the caller already restricts it to the research as-of)
        as_of = _dates.max()
        current = filter_recent(anomalies, pd.Timestamp(as_of)).copy()
        current["_d"] = pd.to_datetime(current["date"])
        current = current.sort_values("_d").groupby(["entity_id", "detector"], as_index=False).tail(1)
        results: list[MechanismResult] = []
        for mid, mech in self.raw.items():
            triggers_cfg = mech.get("triggers", []) or []
            matched: list[dict[str, Any]] = []
            for trig in triggers_cfg:
                matched.extend(self._trigger_matches(trig, current))
            if len(matched) < min_triggers:
                continue
            tests = self.run_tests(mech)
            # Benjamini-Hochberg across the tests of THIS mechanism: with 4-5
            # tests per mechanism, an uncorrected p<0.10 is not evidence.
            pvals = [t.stats.get("p_value") for t in tests if t.stats.get("p_value") is not None]
            adj = bh_fdr([float(p) for p in pvals], q=float(mech.get("fdr_q", 0.10)))
            adj_iter = iter(adj)
            for t in tests:
                if t.stats.get("p_value") is not None:
                    t.stats["p_adjusted"] = round(float(next(adj_iter)), 6)
                    if t.passed and t.stats["p_adjusted"] > float(mech.get("fdr_q", 0.10)):
                        t.passed = False
                        t.reason = t.reason or "不显著"
            supported = [t for t in tests if t.passed]
            failed = [t for t in tests if not t.passed]
            insufficient = [t for t in failed if t.reason == "insufficient_data"]
            # every failed test with data lowers confidence; previously "correlation
            # too weak" was free, so a failing gold test did not reduce support.
            contradicting = [t for t in failed if t.reason != "insufficient_data"]
            n_passed = len(supported)
            # Collinear tests on the same left-hand series are one piece of
            # evidence, not three: count distinct `a` series (+1 for a passing
            # conditional test) so a mechanism cannot inflate confidence by
            # repeating the same pair with different right-hand assets.
            corr_leads = {t.stats.get("a") for t in supported if t.test_type == "corr"}
            n_distinct = (len(corr_leads)
                          + (1 if any(t.test_type == "conditional_return" for t in supported) else 0)
                          + (1 if any(t.test_type == "lead_lag" for t in supported) else 0))
            confidence = 0.25 + 0.18 * min(n_distinct, 3)
            if any(t.test_type == "corr" and t.passed for t in tests):
                confidence += 0.10
            if any(t.test_type == "conditional_return" and t.passed for t in tests):
                confidence += 0.08
            confidence -= 0.08 * min(len(contradicting), 3)
            confidence -= 0.05 * len(insufficient)
            confidence = float(max(0.05, min(0.85, confidence)))
            if n_passed == 0:
                status = "unsupported" if contradicting else "insufficient_data"
            elif contradicting:
                status = "mixed"
            elif confidence >= 0.55:
                status = "supported"
            else:
                status = "weak"
            assets = []
            for a in mech.get("affected_assets", []) or []:
                aid = a.get("id")
                asset_anoms = current[current.entity_id == aid]
                assets.append({
                    "id": aid, "role": a.get("role", "secondary"),
                    "expected_direction": a.get("expected_direction", "ambiguous"),
                    "horizon": a.get("horizon", ""),
                    "current_anomalies": asset_anoms[["detector", "direction", "score"]].to_dict("records"),
                })
            tid = "TX-" + hashlib.sha1(f"{mid}|{as_of}".encode()).hexdigest()[:12]
            notes = mech.get("limitations", "")
            results.append(MechanismResult(
                mechanism_id=mid, title=mech.get("title", mid), family=mech.get("family", ""),
                as_of=pd.Timestamp(as_of).strftime("%Y-%m-%d"), transmission_id=tid, triggers=matched, assets=assets,
                evidence_for=[t.to_dict() for t in supported],
                evidence_against=[t.to_dict() for t in failed],
                conditions=list(mech.get("conditions", []) or []),
                falsifiers=list(mech.get("falsifiers", []) or []),
                confidence=confidence, status=status, notes=notes,
            ))
        return results


# --------------------------------------------------------------------- helpers
def _obs_scale(s: pd.Series) -> int:
    """Approximate number of trading days represented by one observation."""
    if len(s) < 8:
        return 1
    diffs = pd.Series(s.index).diff().dropna().dt.days
    med = float(diffs.median())
    if med <= 3:
        return 1          # daily
    if med <= 10:
        return 5          # weekly
    if med <= 40:
        return 21         # monthly
    return 63             # quarterly


def _is_monthly(s: pd.Series) -> bool:
    return _obs_scale(s) == 21


def _normalise_frequency(a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series, int]:
    """Resample both inputs to the coarser observation frequency when needed."""
    scale = max(_obs_scale(a), _obs_scale(b))
    if scale >= 21:
        a = a.resample("ME").last()
        b = b.resample("ME").last()
    elif scale >= 5:
        a = a.resample("W-FRI").last()
        b = b.resample("W-FRI").last()
    return a, b, scale


def _cmp(value: float, operator: str, threshold: float) -> bool:
    if pd.isna(value):
        return False
    if operator == ">":
        return value > threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    return False


def evaluate_transmissions(fs: FeatureSet, anomalies: pd.DataFrame,
                           mechanisms: dict[str, Any] | None = None) -> tuple[pd.DataFrame, list[MechanismResult]]:
    ev = MechanismEvaluator(fs, mechanisms)
    results = ev.evaluate(anomalies)
    if not results:
        return pd.DataFrame(), []
    rows = pd.DataFrame([r.to_row() for r in results])
    return rows, results


def activation_summary(results: Iterable[MechanismResult]) -> dict[str, Any]:
    rs = list(results)
    return {
        "n_activated": len(rs),
        "by_status": pd.Series([r.status for r in rs]).value_counts().to_dict() if rs else {},
        "supported": [{"id": r.mechanism_id, "title": r.title, "confidence": round(r.confidence, 3),
                       "assets": [a["id"] for a in r.assets][:6]} for r in rs if r.status == "supported"],
    }
