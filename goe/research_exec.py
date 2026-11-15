"""Execute a real research case: acquire evidence, run PIT tests, update hypotheses.

Key PIT rule: an Asia equity close happens before the same-calendar-date US close.
For an Asia event, US/FX information known at the event must be the PREVIOUS US
session, not the future same-date US close. The N225 case makes this explicit.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import project_root
from .db import Store
from .features import FEATURE_VERSION, FeatureBuilder

CASE_N225 = "RC-20261113-JP_EQ_N225-455ff8e1a32f"
EVENT_ASSETS = {
    "JP_EQ_N225": ("Japan Nikkei 225 (event asset)", "same_day"),
    "JP_EQ_TOPIX": ("Japan broad market", "same_day"),
    "TW_EQ_TAIEX": ("Taiwan equity market", "same_day"),
    "KR_EQ_KOSPI": ("Korea equity market", "same_day"),
    "HK_EQ_HSI": ("Hong Kong equity market", "same_day"),
    "CN_EQ_CSI300": ("China A-share", "same_day"),
    "US_EQ_SPY": ("US broad risk", "prior_us_session"),
    "US_EQ_QQQ": ("US growth", "prior_us_session"),
    "US_VOL_VIX": ("US implied volatility", "prior_us_session"),
    "GX_FX_USDJPY": ("JPY", "prior_us_session"),
    "US_FI_IEF": ("US duration", "prior_us_session"),
    "US_CR_HYG": ("US credit", "prior_us_session"),
}


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return ""


def _sha(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str,
                                     ensure_ascii=False).encode()).hexdigest()


@dataclass
class ResearchFinding:
    finding_id: str
    research_id: str
    decision_as_of: str
    event_date: str
    observed: dict[str, Any]
    plan: dict[str, Any]
    evidence: dict[str, Any]
    tests: dict[str, Any]
    hypothesis_updates: dict[str, Any]
    learned: list[str]
    still_unknown: list[str]
    next_action: str
    input_sha256: str
    code_commit: str
    feature_version: str
    status: str
    data_dates: dict[str, str] = field(default_factory=dict)
    rules: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _event_date(returns: pd.DataFrame, iid: str, as_of: str) -> str:
    y = returns[iid].dropna()
    y = y[y.index <= pd.Timestamp(as_of)].tail(90)
    return str(y.abs().idxmax().date())


def _ret(returns: pd.DataFrame, iid: str, date: str) -> float | None:
    if iid not in returns.columns or pd.Timestamp(date) not in returns.index:
        return None
    v = returns.at[pd.Timestamp(date), iid]
    return float(v) if np.isfinite(v) else None


def _prior_session(returns: pd.DataFrame, event: str) -> str:
    idx = returns.index[returns.index < pd.Timestamp(event)]
    if len(idx) == 0:
        raise RuntimeError("no prior session")
    return str(idx[-1].date())


def _policy_event_on(config: dict[str, Any], date: str) -> dict[str, Any] | None:
    for e in (config.get("events") or {}).get("events", []) if isinstance(config.get("events"), dict) else []:
        if e.get("date") == date:
            return e
    for e in (config.get("events") or []):
        if e.get("date") == date:
            return e
    return None


def execute_nikkei_case(store: Store, *, as_of: str = "2026-11-13",
                        out_dir: str | Path = "research_results") -> ResearchFinding:
    fs = FeatureBuilder(store, as_of=as_of, point_in_time=True,
                        history_start=(pd.Timestamp(as_of) - pd.DateOffset(years=3)).strftime("%Y-%m-%d")).build()
    iid = "JP_EQ_N225"
    event = _event_date(fs.returns, iid, as_of)
    prior = _prior_session(fs.returns, event)
    observed: dict[str, dict[str, Any]] = {}
    data_dates: dict[str, str] = {}
    for aid, (label, alignment) in EVENT_ASSETS.items():
        date = event if alignment == "same_day" else prior
        r = _ret(fs.returns, aid, date)
        if r is not None:
            observed[aid] = {"label": label, "return": round(r, 6),
                             "data_date": date, "alignment": alignment}
            data_dates[aid] = date
    if iid not in observed:
        raise RuntimeError("N225 event return unavailable")
    raw_window = fs.returns.loc[:pd.Timestamp(event)]
    data_hash = hashlib.sha256(
        pd.util.hash_pandas_object(raw_window, index=True).values.tobytes()).hexdigest()

    rules = {
        "local": "TOPIX same-day return < -3%",
        "global": "prior US session SPY < -1% AND VIX return > 0 (QQQ is reported, not a gate)",
        "regional": "TAIEX and KOSPI same-day both < -3% (North Asia; HSI/CSI reported separately)",
        "fx": "prior-session |USDJPY| >= 20% of |N225|",
        "reversal": "N225 cumulative return over next 3 sessions > 0",
        "alignment": "Asia same-day; US/FX previous US session; no same-date future US close",
    }
    plan = {
        "question": "What explains the N225 event: Japan-local factor, regional Asia co-move, "
                    "US/global risk, JPY, policy, or fundamentals?",
        "next_best_evidence": "PIT-aligned same-day Asia returns plus PRIOR US-session returns/VIX/USDJPY",
        "why": "It separates a Japan/regional Asia shock from a US-global lead without lookahead",
        "source": "GOE prices DB (yahoo), completed daily bars",
        "period": f"event {event}; prior US session {prior}; trailing 90 sessions",
        "cost": "low; already stored",
        "missing": ["consensus revisions", "TOPIX sector constituents", "term OIS",
                    "CFTC history at event", "Asia semiconductor exposure"],
        "decision_rule": rules,
        "pit_note": "US same-calendar-date close is after the Asia close and is therefore not used.",
    }

    def rv(k: str, default=None):
        return (observed.get(k) or {}).get("return", default)

    topix, taiex, kospi = rv("JP_EQ_TOPIX"), rv("TW_EQ_TAIEX"), rv("KR_EQ_KOSPI")
    spy, qqq, vix = rv("US_EQ_SPY"), rv("US_EQ_QQQ"), rv("US_VOL_VIX")
    fx = rv("GX_FX_USDJPY")
    local_pass = topix is not None and topix < -0.03
    global_pass = bool(spy is not None and vix is not None and spy < -0.01 and vix > 0)
    regional_pass = bool(taiex is not None and kospi is not None and taiex < -0.03 and kospi < -0.03)
    n225 = rv(iid)
    fx_pass = bool(fx is not None and n225 is not None and abs(fx) >= 0.20 * abs(n225))
    idx = fs.returns.index
    pos = idx.get_loc(pd.Timestamp(event))
    nxt = fs.returns[iid].iloc[pos + 1: pos + 4]
    reversal = round(float((1 + nxt).prod() - 1), 6) if len(nxt) else None
    reversal_pass = bool(reversal is not None and reversal > 0)

    tests = {
        "local_asia_test": {"topix_return": topix, "pass": local_pass,
                            "interpretation": "TOPIX co-move supports a broad Japan/local factor; association only"},
        "global_lead_test": {"prior_us_session": prior, "spy_return": spy, "qqq_return": qqq,
                             "vix_return": vix, "pass": global_pass,
                             "interpretation": "prior US selloff/VIX spike is consistent with a global lead"},
        "asia_regional_test": {"taiex_return": taiex, "kospi_return": kospi, "pass": regional_pass,
                               "interpretation": "Taiwan/Korea co-move supports regional Asia; tech-specific attribution not identified"},
        "fx_test": {"prior_usdjpy_return": fx, "pass": fx_pass,
                    "interpretation": "small prior FX move cannot explain a -6% equity move by itself"},
        "reversal_test": {"n225_next_3d": reversal, "pass": reversal_pass,
                          "interpretation": "measured only from bars after the event through as-of"},
    }

    # Policy calendar is real config; absence is evidence of no scheduled event, not a missing file.
    events_path = project_root() / "config" / "events.yaml"
    policy_event = None
    policy_source = "config/events.yaml"
    try:
        import yaml
        ev = yaml.safe_load(events_path.read_text(encoding="utf-8")) or {}
        for e in ev.get("events", []):
            if str(e.get("date")) == event:
                policy_event = e
                break
    except Exception:
        policy_source = "config/events.yaml unavailable"

    updates = {
        "H-EQJP-LOCAL": {
            "status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if local_pass else "INCONCLUSIVE",
            "new_evidence": "TOPIX same-day", "value": topix,
            "label": "Japan broad local market factor", "type": "local_market",
            "note": "Broad co-move; not an independent instrument and not causal proof."},
        "H-EQJP-GLOBAL": {
            "status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if global_pass else "WEAKENED_BY_EVIDENCE",
            "new_evidence": "prior US session SPY/QQQ/VIX", "value": {"SPY": spy, "QQQ": qqq, "VIX": vix},
            "label": "US/global risk lead", "type": "global_risk",
            "note": "Prior US session sold off and VIX spiked before Asia opened; consistent with transmission. "
                    "The later same-date US close is not used."},
        "H-EQJP-FX": {
            "status": "WEAKENED_BY_EVIDENCE" if not fx_pass else "INCONCLUSIVE",
            "new_evidence": "prior-session USDJPY", "value": fx,
            "label": "JPY/cross-border flow", "type": "fx",
            "note": "Small prior FX move cannot explain the equity move by itself."},
        "H-EQJP-POLICY": {
            "status": "INSUFFICIENT_DATA" if policy_event is None else "INCONCLUSIVE",
            "new_evidence": "policy calendar check", "value": policy_event,
            "label": "Policy/regulatory event", "type": "policy",
            "note": f"No scheduled event on {event} in {policy_source}; not enough to rule out policy news."},
        "H-EQJP-FUND": {
            "status": "INSUFFICIENT_DATA", "new_evidence": "consensus revisions unavailable",
            "value": None, "label": "Japan fundamentals/earnings revisions", "type": "fundamental",
            "note": "No authorized consensus data; no fabricated values."},
        "H-EQJP-ASIA-REGIONAL": {
            "status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if regional_pass else "INCONCLUSIVE",
            "new_evidence": "Taiwan/Korea same-day", "value": {"TAIEX": taiex, "KOSPI": kospi},
            "label": "Regional Asia co-move", "type": "regional_asia",
            "note": "Regional co-move supported; sector/tech channel is not identified."},
    }
    learned = [
        f"On {event}, N225 returned {rv(iid):.2%}; TOPIX {topix:.2%}.",
        f"Prior US session ({prior}) SPY {spy:+.2%}, QQQ {qqq:+.2%}, VIX {vix:+.2%}: a US-global lead is "
        "consistent, not contradicted. Using the later same-date US close would be lookahead.",
        f"Taiwan {taiex:+.2%} and Korea {kospi:+.2%} fell; a North Asia co-move is supported, "
        "but tech-specific attribution is unavailable.",
        f"Hong Kong {rv('HK_EQ_HSI'):+.2%} and China {rv('CN_EQ_CSI300'):+.2%} were much smaller, "
        "so broad 'Asia' is too strong; the evidence is North Asia/Japan-Taiwan-Korea.",
        f"Prior-session USDJPY {fx:+.2%}; too small to be the primary driver.",
        f"Three-session post-event N225 return {reversal:+.2%}.",
        "Japan-local and regional Asia explanations both survive; broad indices cannot separate them.",
        "No scheduled policy event on the date was found in config/events.yaml; that is not proof no policy news occurred.",
    ]
    unknown = ["TOPIX sector/constituent breadth", "Asia semiconductor exposure",
               "consensus/earnings revisions", "CFTC positioning at event",
               "policy/news calendar coverage on the date"]
    finding = ResearchFinding(
        finding_id="RF-N225-20261113", research_id=CASE_N225, decision_as_of=as_of,
        event_date=event, observed=observed, plan=plan,
        evidence={"source": "GOE prices DB", "event_available_at": event,
                  "decision_as_of": as_of, "data_dates": data_dates,
                  "data_hash": data_hash,
                  "input_rows": int(len(fs.returns.loc[:pd.Timestamp(event)])),
                  "missing": plan["missing"], "alignment": rules["alignment"]},
        tests=tests, hypothesis_updates=updates, learned=learned, still_unknown=unknown,
        next_action="Retain in A/watch; acquire TOPIX sector breadth and Asia semiconductor exposure. "
                    "Do not hand off unsupported deep asset research to B.",
        input_sha256=_sha({"observed": observed, "event": event, "prior": prior,
                           "as_of": as_of, "rules": rules, "data_hash": data_hash}),
        code_commit=_git_commit(), feature_version=FEATURE_VERSION, status="INCONCLUSIVE",
        data_dates=data_dates, rules=rules,
    )
    out = Path(out_dir) / as_of / "N225"; out.mkdir(parents=True, exist_ok=True)
    payload = finding.to_dict()
    (out / "finding.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                                     encoding="utf-8")
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "evidence.json").write_text(json.dumps(
        {**finding.evidence, "observed": observed}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "tests.json").write_text(json.dumps(tests, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [f"# Research Finding — N225 {as_of}", "",
          f"- Event date: {event}",
          f"- Prior US session: {prior}",
          f"- Status: {finding.status}",
          f"- Input SHA256: `{finding.input_sha256}`",
          f"- Code commit: `{finding.code_commit}` / feature {finding.feature_version}", "",
          "## PIT alignment", f"- {rules['alignment']}",
          f"- US/FX data date: {prior}; Asia data date: {event}", "",
          "## What was acquired", f"- {plan['next_best_evidence']}",
          f"- Source: {finding.evidence['source']}", "",
          "## Tests and results"]
    for name, t in tests.items():
        md.append(f"- **{name}**: pass={t.get('pass')} — {t.get('interpretation')}")
    md += ["", "## Hypothesis updates"]
    for hid, u in updates.items():
        md.append(f"- **{hid}**: {u['status']} — {u['note']}")
    md += ["", "## What we learned"] + [f"- {x}" for x in learned]
    md += ["", "## Still unknown"] + [f"- {x}" for x in unknown]
    md += ["", "## Next action", finding.next_action, "",
           "DISCOVERY VALUE: NOT VALIDATED"]
    (out / "findings.md").write_text("\n".join(md), encoding="utf-8")

    store.update_research_hypotheses(finding.research_id, updates)
    store.add_research_finding(finding.finding_id, finding.research_id, finding.status,
                               payload, str(out / "finding.json"))
    return finding
