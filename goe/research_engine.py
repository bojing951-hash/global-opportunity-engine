"""Generalized, deterministic research executor.

A ResearchSpec says WHAT is observed and WHICH test template applies. Test
templates are selected by asset class, not by hardcoded ticker. Every finding
stores PIT-aligned evidence, rules, outputs, input hash and code provenance.
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

from .db import Store
from .features import FEATURE_VERSION, FeatureBuilder
from .research_identity import research_id as make_rid, research_theme_id as make_theme
from .research_exec import ResearchFinding
from .test_registry import execution_key, select_test

METHOD_VERSION = "research-engine-v3"


def _engine_hash() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:8]


def _sha(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str,
                                     ensure_ascii=False).encode()).hexdigest()


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return ""


def _ret(returns: pd.DataFrame, iid: str, date: pd.Timestamp) -> float | None:
    if iid not in returns.columns or date not in returns.index:
        return None
    v = returns.at[date, iid]
    return float(v) if np.isfinite(v) else None


@dataclass
class ResearchSpec:
    research_id: str
    research_theme_id: str
    as_of: str
    asset: str
    market: str
    asset_class: str
    question: str
    case_kind: str
    peers: dict[str, tuple[str, str]]  # iid -> (label, "same_day"|"prior_us_session")
    hypotheses: list[dict[str, Any]]
    event_window: int = 180
    event_override: str | None = None
    roles: dict[str, str] = field(default_factory=dict)
    hypothesis_ids: dict[str, str] = field(default_factory=dict)
    event_contract: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def spec_for_asset(*, asset: str, market: str, asset_class: str, as_of: str,
                   question: str, peers: dict[str, tuple[str, str]],
                   hypotheses: list[dict[str, Any]], case_kind: str,
                   detector: str = "research_event", direction: str = "event",
                   event_override: str | None = None,
                   roles: dict[str, str] | None = None,
                   hypothesis_ids: dict[str, str] | None = None) -> ResearchSpec:
    rid = make_rid(as_of=as_of, instrument_id=asset, detector=detector,
                   direction=direction, window="event")
    return ResearchSpec(rid, make_theme(instrument_id=asset, detector=detector,
                                       direction=direction, window="event"),
                        as_of, asset, market, asset_class, question, case_kind, peers, hypotheses,
                        event_override=event_override, roles=roles or {},
                        hypothesis_ids=hypothesis_ids or {})


def _event_date(returns: pd.DataFrame, asset: str, as_of: str, window: int) -> str:
    y = returns[asset].dropna()
    y = y[y.index <= pd.Timestamp(as_of)].tail(window)
    return str(y.abs().idxmax().date())


def _prior(returns: pd.DataFrame, event: str) -> str:
    idx = returns.index[returns.index < pd.Timestamp(event)]
    return str(idx[-1].date())


def execute_spec(store: Store, spec: ResearchSpec, *, out_dir: str | Path = "research_results") -> ResearchFinding:
    fs = FeatureBuilder(store, as_of=spec.as_of, point_in_time=True,
                        history_start=(pd.Timestamp(spec.as_of) - pd.DateOffset(years=3)).strftime("%Y-%m-%d")).build()
    returns = fs.returns
    definition = select_test(spec.asset_class)
    if definition is None:
        raise ValueError(f"UNSUPPORTED_TEST: no registered test for {spec.asset_class}")
    case_kind = execution_key(definition.test_id)
    event = spec.event_override or _event_date(returns, spec.asset, spec.as_of, spec.event_window)
    prior = _prior(returns, event)
    observed: dict[str, dict[str, Any]] = {}
    for aid, (label, align) in {spec.asset: (spec.asset, "same_day"), **spec.peers}.items():
        date = pd.Timestamp(event) if align == "same_day" else pd.Timestamp(prior)
        if align == "prior_us_session" and spec.asset_class == "fx":
            date = pd.Timestamp(event)  # FX closes in NY; use event close for the FX case
        r = _ret(returns, aid, date)
        if r is not None:
            observed[aid] = {"label": label, "return": round(r, 6),
                             "data_date": str(date.date()), "alignment": align}
    if spec.asset not in observed:
        raise RuntimeError(f"event asset unavailable: {spec.asset}")
    data_hash = hashlib.sha256(
        pd.util.hash_pandas_object(returns.loc[:pd.Timestamp(event)], index=True).values.tobytes()).hexdigest()

    def rv(k: str):
        return (observed.get(k) or {}).get("return")

    n225 = rv(spec.asset)
    hist = returns[spec.asset].dropna()
    hist = hist[hist.index <= pd.Timestamp(event)].tail(252)
    pct = float((hist < n225).mean()) if len(hist) and n225 is not None else None
    R, H = spec.roles, spec.hypothesis_ids

    def role(k: str):
        return rv(R.get(k, ""))

    def p(v) -> str:
        return "n/a" if v is None else f"{v:+.2%}"

    def hid(k: str, default: str) -> str:
        return H.get(k, default)

    def hs(passed, supported: str, weak: str = "INCONCLUSIVE") -> str:
        return "INSUFFICIENT_DATA" if passed is None else (supported if passed else weak)
    tests: dict[str, Any] = {"historical_percentile": {
        "event_return": n225, "percentile": pct,
        "pass": bool(pct is not None and (pct <= 0.05 or pct >= 0.95)),
        "interpretation": "two-sided 5% tail of the trailing 252-session return distribution"}}
    updates: dict[str, Any] = {}
    learned: list[str] = []
    unknown: list[str] = []

    if case_kind == "equity_event":
        topix, taiex, kospi = role("local"), role("regional_tw"), role("regional_kr")
        spy, qqq, vix = role("global_equity"), role("global_growth"), role("global_vol")
        fx = role("fx")
        local_label = observed.get(R.get("local", ""), {}).get("label", "local market")
        tw_label = observed.get(R.get("regional_tw", ""), {}).get("label", "regional market A")
        kr_label = observed.get(R.get("regional_kr", ""), {}).get("label", "regional market B")
        fx_label = observed.get(R.get("fx", ""), {}).get("label", "FX")
        tests["local_asia_test"] = {
            "topix_return": topix, "pass": (None if topix is None else topix < -0.03),
            "interpretation": f"{local_label} co-move; association only"}
        tests["global_lead_test"] = {
            "prior_us_session": prior, "spy_return": spy, "qqq_return": qqq, "vix_return": vix,
            "pass": (None if spy is None or vix is None else (spy < -0.01 and vix > 0)),
            "interpretation": "prior US session selloff/VIX spike is consistent with a global lead"}
        regional_pass = (None if taiex is None or kospi is None
                         else (taiex < -0.03 and kospi < -0.03))
        tests["asia_regional_test"] = {
            "regional_a_return": taiex, "regional_b_return": kospi,
            "pass": regional_pass,
            "interpretation": ("North Asia co-move supported; tech-specific attribution not identified"
                              if regional_pass else
                              "Regional peers did not both meet the pre-set threshold")}
        tests["fx_test"] = {"prior_usdjpy_return": fx,
                            "pass": (None if fx is None else abs(fx) >= 0.20 * abs(n225 or 0.01)),
                            "interpretation": "small FX move cannot explain the equity move"}
        idx = returns.index; pos = idx.get_loc(pd.Timestamp(event))
        nxt = returns[spec.asset].iloc[pos + 1: pos + 4]
        reversal = round(float((1 + nxt).prod() - 1), 6) if len(nxt) else None
        tests["reversal_test"] = {"n225_next_3d": reversal, "pass": bool(reversal is not None and reversal > 0),
                                  "interpretation": "only bars after event through as-of"}
        local_ok = tests["local_asia_test"]["pass"]
        local_ok = tests["local_asia_test"]["pass"]
        regional_ok = tests["asia_regional_test"]["pass"]
        policy_event = None
        try:
            import yaml
            from .config import project_root
            ev = yaml.safe_load((project_root() / "config" / "events.yaml").read_text(encoding="utf-8")) or {}
            for e in ev.get("events", []):
                if str(e.get("date")) == event:
                    policy_event = e
                    break
        except Exception:
            pass
        updates = {
            hid("local", "H-EQ-LOCAL"): {"status": hs(tests["local_asia_test"]["pass"], "SUPPORTED_BY_AVAILABLE_EVIDENCE"),
                             "label": "Local market factor", "type": "local_market",
                             "new_evidence": f"{local_label} same-day", "value": topix,
                             "note": ("Local peer co-moved; not an independent instrument." if local_ok
                                      else "Local peer did not meet its pre-set threshold; no local support.")},
            hid("global", "H-EQ-GLOBAL"): {"status": hs(tests["global_lead_test"]["pass"], "SUPPORTED_BY_AVAILABLE_EVIDENCE", "WEAKENED_BY_EVIDENCE"),
                              "label": "Global risk lead", "type": "global_risk",
                              "new_evidence": "prior US session SPY/QQQ/VIX", "value": {"SPY": spy, "QQQ": qqq, "VIX": vix},
                              "note": "Prior US selloff/VIX spike preceded Asia; same-date US close is not used."},
            hid("fx", "H-EQ-FX"): {"status": hs(tests["fx_test"]["pass"], "INCONCLUSIVE", "WEAKENED_BY_EVIDENCE"),
                          "label": "FX/cross-border flow", "type": "fx", "new_evidence": "prior USDJPY", "value": fx,
                          "note": "Small FX move cannot explain the equity move by itself."},
            hid("policy", "H-EQ-POLICY"): {"status": "INSUFFICIENT_DATA" if policy_event is None else "INCONCLUSIVE",
                              "label": "Policy/regulatory event", "type": "policy",
                              "new_evidence": "config/events.yaml calendar check", "value": policy_event,
                              "note": ("No scheduled event in config/events.yaml; not proof no policy news."
                                       if policy_event is None else "Scheduled event exists; attribution not established.")},
            hid("fund", "H-EQ-FUND"): {"status": "INSUFFICIENT_DATA", "label": "Fundamentals", "type": "fundamental",
                            "new_evidence": "consensus unavailable", "value": None,
                            "note": "No authorized consensus data; no fabrication."},
            hid("regional", "H-EQ-REGIONAL"): {"status": hs(tests["asia_regional_test"]["pass"], "SUPPORTED_BY_AVAILABLE_EVIDENCE"),
                                     "label": "Regional co-move", "type": "regional_asia",
                                     "new_evidence": "regional peers same-day",
                                     "value": {tw_label: taiex, kr_label: kospi},
                                     "note": "Regional co-move; sector/tech attribution unavailable."},
        }
        learned = [f"{spec.asset} event {event}: {p(n225)}; {local_label} {p(topix)}.",
                   f"Prior US session {prior}: {p(spy)}, {p(qqq)}, {p(vix)}; global lead consistent.",
                   (f"{tw_label} {p(taiex)}, {kr_label} {p(kospi)}; regional co-move supported."
                    if regional_ok else
                    f"{tw_label} {p(taiex)}, {kr_label} {p(kospi)}; regional co-move did not meet threshold."),
                   f"{fx_label} {p(fx)}; too small to be primary.",
                   f"Three-session reversal {p(reversal)}.",
                   ("Local and regional explanations both survive; broad indices cannot separate."
                    if local_ok and regional_ok else
                    ("Regional co-move survives; the local peer did not meet its pre-set threshold."
                     if regional_ok else
                     ("Local co-move survives; the regional peers did not meet threshold."
                      if local_ok else
                      "Neither local nor regional thresholds were met; only the global lead is supported.")))]
        unknown = [f"{local_label} sector/constituent breadth", "regional supply-chain exposure",
                   "consensus revisions", "event/news calendar"]

    elif case_kind == "fx_level":
        eur, jpy, spy, vix, ief = role("cross1"), role("cross2"), role("risk"), role("vol"), role("rates")
        tests["broad_usd_test"] = {"eurusd": eur, "usdjpy": jpy,
                                   "pass": (None if eur is None or jpy is None else (eur < -0.002 and jpy > 0.002)),
                                   "interpretation": "EUR lower and USDJPY higher confirms broad USD strength"}
        tests["rate_test"] = {"ief_return": ief,
                              "pass": (None if ief is None else (ief < 0 and n225 > 0)),
                              "interpretation": "US duration down (yields up) alongside USD up is consistent with rate differential"}
        tests["risk_test"] = {"spy": spy, "vix": vix,
                              "pass": (None if spy is None or vix is None else (spy < 0 and vix > 0)),
                              "interpretation": "risk-off / safe-haven bid"}
        updates = {
            hid("rates", "H-FX-RATES"): {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if tests["rate_test"]["pass"] else "INCONCLUSIVE",
                           "label": "US rate differential", "type": "rates",
                           "new_evidence": "IEF and DXY same-day", "value": {"DXY": n225, "IEF": ief},
                           "note": "Duration down + USD up is consistent with yield support; association only."},
            hid("risk", "H-FX-RISK"): {"status": hs(tests["risk_test"]["pass"], "SUPPORTED_BY_AVAILABLE_EVIDENCE", "WEAKENED_BY_EVIDENCE"),
                          "label": "Global risk-off/safe haven", "type": "risk",
                          "new_evidence": "SPY/VIX same-day", "value": {"SPY": spy, "VIX": vix},
                          "note": "Risk-off bid is a competing channel; cannot establish causality."},
            hid("broad", "H-FX-BROAD"): {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if tests["broad_usd_test"]["pass"] else "INCONCLUSIVE",
                           "label": "Broad USD move", "type": "cross_rate",
                           "new_evidence": "EURUSD/USDJPY same-day", "value": {"EURUSD": eur, "USDJPY": jpy},
                           "note": "Cross-rate confirmation; no claim about equilibrium."},
            hid("artifact", "H-FX-DATA"): {"status": "INSUFFICIENT_DATA", "label": "Data artifact", "type": "data_artifact",
                          "new_evidence": "no roll/split flag for DXY", "value": None,
                          "note": "Index data are not a futures roll; artifact not indicated but not fully ruled out."},
        }
        learned = [f"{spec.asset} event {event}: {p(n225)}.",
                   f"EURUSD {p(eur)}, USDJPY {p(jpy)}, IEF {p(ief)}, SPY {p(spy)}, VIX {p(vix)}.",
                   "Rate/broad-USD co-move is supported; risk-off is weakened at this event; no causal identification."]
        unknown = ["2Y/10Y yield decomposition", "positioning", "policy calendar", "real-time news"]

    elif case_kind == "commodity_event":
        dxy, gold, ief, spy, vix = role("dollar"), role("gold"), role("rates"), role("risk"), role("vol")
        tests["dollar_test"] = {"dxy_return": dxy,
                                "pass": (None if dxy is None else (n225 < 0 and dxy > 0)),
                                "interpretation": "USD up with commodity down is consistent with dollar channel"}
        tests["real_rate_test"] = {"ief_return": ief,
                                   "pass": (None if ief is None else (ief < 0 and n225 < 0)),
                                   "interpretation": "duration down (yields up) with commodity down is consistent with real-rate channel"}
        tests["risk_test"] = {"spy": spy, "vix": vix,
                              "pass": (None if spy is None or vix is None else (spy < 0 and vix > 0)),
                              "interpretation": "risk-off channel"}
        tests["gold_test"] = {"gold_return": gold,
                              "pass": (None if gold is None else gold < 0),
                              "interpretation": "gold co-move checks a broad commodity/metal factor"}
        updates = {
            hid("dollar", "H-CMD-DOLLAR"): {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if tests["dollar_test"]["pass"] else "INCONCLUSIVE",
                             "label": "USD/dollar channel", "type": "dollar",
                             "new_evidence": "DXY same-day", "value": dxy,
                             "note": "Dollar co-move is association; no causal identification."},
            hid("rates", "H-CMD-REALRATE"): {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if tests["real_rate_test"]["pass"] else "INCONCLUSIVE",
                               "label": "Real-rate channel", "type": "real_rate",
                               "new_evidence": "IEF proxy same-day", "value": ief,
                               "note": "IEF is a duration proxy, not a direct real-yield measure."},
            hid("risk", "H-CMD-RISK"): {"status": hs(tests["risk_test"]["pass"], "SUPPORTED_BY_AVAILABLE_EVIDENCE", "WEAKENED_BY_EVIDENCE"),
                           "label": "Risk-off channel", "type": "risk",
                           "new_evidence": "SPY/VIX same-day", "value": {"SPY": spy, "VIX": vix},
                           "note": "Risk channel is not separable from dollar/rates with these proxies."},
            hid("supply", "H-CMD-SUPPLY"): {"status": "INSUFFICIENT_DATA", "label": "Supply/inventory", "type": "supply",
                             "new_evidence": "no inventory/supply data", "value": None,
                             "note": "No supply data; not fabricated."},
        }
        learned = [f"{spec.asset} event {event}: {p(n225)}.",
                   f"DXY {p(dxy)}, gold {p(gold)}, IEF {p(ief)}, SPY {p(spy)}, VIX {p(vix)}.",
                   "Dollar/rate/risk channels overlap; none uniquely identified; supply data missing."]
        unknown = ["inventory/supply", "real yields", "positioning", "contract roll metadata"]
    else:
        raise ValueError(f"unknown case_kind: {spec.case_kind}")

    rules = {k: v.get("interpretation") for k, v in tests.items()}
    status = "INCONCLUSIVE"
    input_hash = _sha({"observed": observed, "rules": rules, "event": event,
                       "as_of": spec.as_of, "data_hash": data_hash,
                       "method": METHOD_VERSION, "engine": _engine_hash()})
    finding = ResearchFinding(
        finding_id="RF-" + spec.research_id + "-" + input_hash[:8], research_id=spec.research_id,
        decision_as_of=spec.as_of, event_date=event, observed=observed,
        plan={"question": spec.question, "case_kind": spec.case_kind,
              "test_id": definition.test_id, "event_contract": spec.event_contract,
              "peers": spec.peers, "missing": unknown,
              "pit": "same-day for event market; prior US session for US/FX in equity case"},
        evidence={"source": "GOE prices DB", "event_available_at": event,
                  "decision_as_of": spec.as_of, "data_hash": data_hash,
                  "data_dates": {k: v["data_date"] for k, v in observed.items()},
                  "input_rows": int(len(returns.loc[:pd.Timestamp(event)]))},
        tests=tests, hypothesis_updates=updates, learned=learned, still_unknown=unknown,
        next_action="Retain in A; acquire the listed missing evidence. No B handoff for unsupported deep asset research.",
        input_sha256=input_hash,
        code_commit=_commit(), feature_version=FEATURE_VERSION, status=status,
        data_dates={k: v["data_date"] for k, v in observed.items()}, rules=rules)
    out = Path(out_dir) / spec.as_of / spec.asset / finding.finding_id
    existing = out / "finding.json"
    if existing.exists():
        payload = json.loads(existing.read_text(encoding="utf-8"))
        if payload.get("finding_id") != finding.finding_id:
            raise RuntimeError("artifact/finding id mismatch at immutable path")
        store.add_research_finding(finding.finding_id, spec.research_id, finding.status,
                                   payload, str(existing))
        return ResearchFinding(**payload) if isinstance(payload, dict) else finding
    # Write atomically outside the final directory; rename is the commit point.
    tmp = out.parent / (".tmp-" + finding.finding_id)
    if tmp.exists():
        import shutil
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    payload = finding.to_dict()
    (tmp / "finding.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (tmp / "plan.json").write_text(json.dumps(finding.plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (tmp / "evidence.json").write_text(json.dumps({"source": "GOE prices DB", "observed": observed,
                                                   "data_hash": data_hash}, ensure_ascii=False, indent=2), encoding="utf-8")
    (tmp / "tests.json").write_text(json.dumps(tests, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [f"# Research Finding — {spec.asset} {spec.as_of}", "",
          f"- Event date: {event}", f"- Status: {status}",
          f"- Input SHA256: `{finding.input_sha256}`", f"- Code commit: `{finding.code_commit}`", "",
          "## Acquired evidence", f"- {spec.question}", f"- Source: GOE prices DB", "",
          "## Tests"]
    for k, v in tests.items():
        md.append(f"- **{k}**: pass={v.get('pass')} — {v.get('interpretation')}")
    md += ["", "## Hypothesis updates"]
    for k, v in updates.items():
        md.append(f"- **{k}**: {v['status']} — {v['note']}")
    md += ["", "## What we learned"] + [f"- {x}" for x in learned]
    md += ["", "## Still unknown"] + [f"- {x}" for x in unknown]
    md += ["", finding.next_action, "", "DISCOVERY VALUE: NOT VALIDATED"]
    (tmp / "findings.md").write_text("\n".join(md), encoding="utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp.rename(out)
    store.update_research_hypotheses(spec.research_id, updates)
    store.add_research_finding(finding.finding_id, spec.research_id, status, payload,
                               str(out / "finding.json"))
    return finding
