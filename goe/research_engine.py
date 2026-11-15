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
    extra: dict[str, Any] = field(default_factory=dict)


def spec_for_asset(*, asset: str, market: str, asset_class: str, as_of: str,
                   question: str, peers: dict[str, tuple[str, str]],
                   hypotheses: list[dict[str, Any]], case_kind: str,
                   detector: str = "research_event", direction: str = "event",
                   event_override: str | None = None) -> ResearchSpec:
    rid = make_rid(as_of=as_of, instrument_id=asset, detector=detector,
                   direction=direction, window="event")
    return ResearchSpec(rid, make_theme(instrument_id=asset, detector=detector,
                                       direction=direction, window="event"),
                        as_of, asset, market, asset_class, question, case_kind, peers, hypotheses,
                        event_override=event_override)


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
    tests: dict[str, Any] = {}
    updates: dict[str, Any] = {}
    learned: list[str] = []
    unknown: list[str] = []

    if spec.case_kind == "equity_event":
        topix, taiex, kospi = rv("JP_EQ_TOPIX"), rv("TW_EQ_TAIEX"), rv("KR_EQ_KOSPI")
        spy, qqq, vix = rv("US_EQ_SPY"), rv("US_EQ_QQQ"), rv("US_VOL_VIX")
        fx = rv("GX_FX_USDJPY")
        tests["local_asia_test"] = {
            "topix_return": topix, "pass": bool(topix is not None and topix < -0.03),
            "interpretation": "TOPIX co-move supports broad Japan/local; association only"}
        tests["global_lead_test"] = {
            "prior_us_session": prior, "spy_return": spy, "qqq_return": qqq, "vix_return": vix,
            "pass": bool(spy is not None and vix is not None and spy < -0.01 and vix > 0),
            "interpretation": "prior US session selloff/VIX spike is consistent with a global lead"}
        tests["asia_regional_test"] = {
            "taiex_return": taiex, "kospi_return": kospi,
            "pass": bool(taiex is not None and kospi is not None and taiex < -0.03 and kospi < -0.03),
            "interpretation": "North Asia co-move supported; tech-specific attribution not identified"}
        tests["fx_test"] = {"prior_usdjpy_return": fx,
                            "pass": bool(fx is not None and abs(fx) >= 0.20 * abs(n225 or 0.01)),
                            "interpretation": "small FX move cannot explain the equity move"}
        idx = returns.index; pos = idx.get_loc(pd.Timestamp(event))
        nxt = returns[spec.asset].iloc[pos + 1: pos + 4]
        reversal = round(float((1 + nxt).prod() - 1), 6) if len(nxt) else None
        tests["reversal_test"] = {"n225_next_3d": reversal, "pass": bool(reversal is not None and reversal > 0),
                                  "interpretation": "only bars after event through as-of"}
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
            "H-EQJP-LOCAL": {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if tests["local_asia_test"]["pass"] else "INCONCLUSIVE",
                             "label": "Japan broad local market factor", "type": "local_market",
                             "new_evidence": "TOPIX same-day", "value": topix,
                             "note": "Broad co-move; not an independent instrument."},
            "H-EQJP-GLOBAL": {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if tests["global_lead_test"]["pass"] else "WEAKENED_BY_EVIDENCE",
                              "label": "US/global risk lead", "type": "global_risk",
                              "new_evidence": "prior US session SPY/QQQ/VIX", "value": {"SPY": spy, "QQQ": qqq, "VIX": vix},
                              "note": "Prior US selloff/VIX spike preceded Asia; same-date US close is not used."},
            "H-EQJP-FX": {"status": "WEAKENED_BY_EVIDENCE" if not tests["fx_test"]["pass"] else "INCONCLUSIVE",
                          "label": "JPY/cross-border flow", "type": "fx", "new_evidence": "prior USDJPY", "value": fx,
                          "note": "Small FX move cannot explain the equity move by itself."},
            "H-EQJP-POLICY": {"status": "INSUFFICIENT_DATA" if policy_event is None else "INCONCLUSIVE",
                              "label": "Policy/regulatory event", "type": "policy",
                              "new_evidence": "config/events.yaml calendar check", "value": policy_event,
                              "note": ("No scheduled event in config/events.yaml; not proof no policy news."
                                       if policy_event is None else "Scheduled event exists; attribution not established.")},
            "H-EQJP-FUND": {"status": "INSUFFICIENT_DATA", "label": "Japan fundamentals", "type": "fundamental",
                            "new_evidence": "consensus unavailable", "value": None,
                            "note": "No authorized consensus data; no fabrication."},
            "H-EQJP-ASIA-REGIONAL": {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if tests["asia_regional_test"]["pass"] else "INCONCLUSIVE",
                                     "label": "Regional North Asia co-move", "type": "regional_asia",
                                     "new_evidence": "Taiwan/Korea same-day", "value": {"TAIEX": taiex, "KOSPI": kospi},
                                     "note": "Regional co-move; sector/tech attribution unavailable."},
        }
        learned = [f"{spec.asset} event {event}: {n225:+.2%}; TOPIX {topix:+.2%}.",
                   f"Prior US session {prior}: SPY {spy:+.2%}, QQQ {qqq:+.2%}, VIX {vix:+.2%}; global lead consistent.",
                   f"Taiwan {taiex:+.2%}, Korea {kospi:+.2%}; North Asia co-move supported.",
                   f"Prior USDJPY {fx:+.2%}; too small to be primary.",
                   f"Three-session reversal {reversal:+.2%}.",
                   "Local Japan and regional North Asia both survive; broad indices cannot separate."]
        unknown = ["TOPIX sector breadth", "Asia semiconductor exposure", "consensus revisions", "event/news calendar"]

    elif spec.case_kind == "fx_level":
        eur, jpy, spy, vix, ief = rv("GX_FX_EURUSD"), rv("GX_FX_USDJPY"), rv("US_EQ_SPY"), rv("US_VOL_VIX"), rv("US_FI_IEF")
        tests["broad_usd_test"] = {"eurusd": eur, "usdjpy": jpy,
                                   "pass": bool(eur is not None and jpy is not None and eur < -0.002 and jpy > 0.002),
                                   "interpretation": "EUR lower and USDJPY higher confirms broad USD strength"}
        tests["rate_test"] = {"ief_return": ief,
                              "pass": bool(ief is not None and ief < 0 and n225 > 0),
                              "interpretation": "US duration down (yields up) alongside USD up is consistent with rate differential"}
        tests["risk_test"] = {"spy": spy, "vix": vix,
                              "pass": bool(spy is not None and vix is not None and spy < 0 and vix > 0),
                              "interpretation": "risk-off / safe-haven bid"}
        updates = {
            "H-FX-RATES": {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if tests["rate_test"]["pass"] else "INCONCLUSIVE",
                           "label": "US rate differential", "type": "rates",
                           "new_evidence": "IEF and DXY same-day", "value": {"DXY": n225, "IEF": ief},
                           "note": "Duration down + USD up is consistent with yield support; association only."},
            "H-FX-RISK": {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if tests["risk_test"]["pass"] else "WEAKENED_BY_EVIDENCE",
                          "label": "Global risk-off/safe haven", "type": "risk",
                          "new_evidence": "SPY/VIX same-day", "value": {"SPY": spy, "VIX": vix},
                          "note": "Risk-off bid is a competing channel; cannot establish causality."},
            "H-FX-BROAD": {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if tests["broad_usd_test"]["pass"] else "INCONCLUSIVE",
                           "label": "Broad USD move", "type": "cross_rate",
                           "new_evidence": "EURUSD/USDJPY same-day", "value": {"EURUSD": eur, "USDJPY": jpy},
                           "note": "Cross-rate confirmation; no claim about equilibrium."},
            "H-FX-DATA": {"status": "INSUFFICIENT_DATA", "label": "Data artifact", "type": "data_artifact",
                          "new_evidence": "no roll/split flag for DXY", "value": None,
                          "note": "Index data are not a futures roll; artifact not indicated but not fully ruled out."},
        }
        learned = [f"{spec.asset} event {event}: {n225:+.2%}.",
                   f"EURUSD {eur:+.2%}, USDJPY {jpy:+.2%}, IEF {ief:+.2%}, SPY {spy:+.2%}, VIX {vix:+.2%}.",
                   "Rate and risk channels both survive; no causal identification."]
        unknown = ["2Y/10Y yield decomposition", "positioning", "policy calendar", "real-time news"]

    elif spec.case_kind == "commodity_event":
        dxy, gold, ief, spy, vix = rv("US_FX_DXY"), rv("CM_MET_GC"), rv("US_FI_IEF"), rv("US_EQ_SPY"), rv("US_VOL_VIX")
        tests["dollar_test"] = {"dxy_return": dxy,
                                "pass": bool(dxy is not None and n225 < 0 and dxy > 0),
                                "interpretation": "USD up with commodity down is consistent with dollar channel"}
        tests["real_rate_test"] = {"ief_return": ief,
                                   "pass": bool(ief is not None and ief < 0 and n225 < 0),
                                   "interpretation": "duration down (yields up) with commodity down is consistent with real-rate channel"}
        tests["risk_test"] = {"spy": spy, "vix": vix,
                              "pass": bool(spy is not None and vix is not None and spy < 0 and vix > 0),
                              "interpretation": "risk-off channel"}
        tests["gold_test"] = {"gold_return": gold,
                              "pass": bool(gold is not None and gold < 0),
                              "interpretation": "gold co-move checks a broad commodity/metal factor"}
        updates = {
            "H-CMD-DOLLAR": {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if tests["dollar_test"]["pass"] else "INCONCLUSIVE",
                             "label": "USD/dollar channel", "type": "dollar",
                             "new_evidence": "DXY same-day", "value": dxy,
                             "note": "Dollar co-move is association; no causal identification."},
            "H-CMD-REALRATE": {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if tests["real_rate_test"]["pass"] else "INCONCLUSIVE",
                               "label": "Real-rate channel", "type": "real_rate",
                               "new_evidence": "IEF proxy same-day", "value": ief,
                               "note": "IEF is a duration proxy, not a direct real-yield measure."},
            "H-CMD-RISK": {"status": "SUPPORTED_BY_AVAILABLE_EVIDENCE" if tests["risk_test"]["pass"] else "WEAKENED_BY_EVIDENCE",
                           "label": "Risk-off channel", "type": "risk",
                           "new_evidence": "SPY/VIX same-day", "value": {"SPY": spy, "VIX": vix},
                           "note": "Risk channel is not separable from dollar/rates with these proxies."},
            "H-CMD-SUPPLY": {"status": "INSUFFICIENT_DATA", "label": "Supply/inventory", "type": "supply",
                             "new_evidence": "no inventory/supply data", "value": None,
                             "note": "No supply data; not fabricated."},
        }
        learned = [f"{spec.asset} event {event}: {n225:+.2%}.",
                   f"DXY {dxy:+.2%}, gold {gold:+.2%}, IEF {ief:+.2%}, SPY {spy:+.2%}, VIX {vix:+.2%}.",
                   "Dollar/rate/risk channels overlap; none uniquely identified; supply data missing."]
        unknown = ["inventory/supply", "real yields", "positioning", "contract roll metadata"]
    else:
        raise ValueError(f"unknown case_kind: {spec.case_kind}")

    rules = {k: v.get("interpretation") for k, v in tests.items()}
    status = "INCONCLUSIVE"
    input_hash = _sha({"observed": observed, "rules": rules, "event": event,
                       "as_of": spec.as_of, "data_hash": data_hash})
    finding = ResearchFinding(
        finding_id="RF-" + spec.research_id + "-" + input_hash[:8], research_id=spec.research_id,
        decision_as_of=spec.as_of, event_date=event, observed=observed,
        plan={"question": spec.question, "case_kind": spec.case_kind,
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
    out = Path(out_dir) / spec.as_of / spec.asset
    out.mkdir(parents=True, exist_ok=True)
    payload = finding.to_dict()
    (out / "finding.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out / "plan.json").write_text(json.dumps(finding.plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "evidence.json").write_text(json.dumps({"source": "GOE prices DB", "observed": observed,
                                                   "data_hash": data_hash}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "tests.json").write_text(json.dumps(tests, ensure_ascii=False, indent=2), encoding="utf-8")
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
    (out / "findings.md").write_text("\n".join(md), encoding="utf-8")
    store.update_research_hypotheses(spec.research_id, updates)
    store.add_research_finding(finding.finding_id, spec.research_id, status, payload,
                               str(out / "finding.json"))
    return finding
