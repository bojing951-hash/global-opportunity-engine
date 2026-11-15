#!/usr/bin/env python3
"""Reproduce the real Case D dossier from the stored cotton anomaly."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from goe.dossier import build_dossier, write_dossier  # noqa: E402


def main() -> int:
    conn = sqlite3.connect(ROOT / "data" / "goe.db")
    conn.row_factory = sqlite3.Row
    r = conn.execute(
        "SELECT * FROM anomalies WHERE instrument_id='CM_AGR_CT' AND as_of='2026-04-30' "
        "ORDER BY score DESC LIMIT 1").fetchone()
    if not r:
        print("cotton anomaly not found")
        return 1
    meta = json.loads((ROOT / "reports" / "scan_2026-11-13.json").read_text())["meta"]
    cand = {
        "research_id": "CASE-D-CM_AGR_CT-20260430",
        "research_theme_id": "RT-DATA-ROLL-CM_AGR_CT",
        "as_of": "2026-04-30", "market": "WORLD", "asset_class": "commodity",
        "instruments": ["CM_AGR_CT"],
        "observed_phenomenon": "Cotton continuous futures near 5y high at month-end "
                               "(drawdown score 0.90; 5y percentile 0.98).",
        "materiality": {"importance": 0.2, "gap_score": 0.0, "near_month_end": True,
                        "is_continuous_futures": True},
        "priority_tier": "intelligence", "research_worthiness": "low",
        "evidence_readiness": "partial", "research_queue": "archive",
        "handoff_eligibility": "a_retained", "research_readiness": "evidence_gap",
        "competing_hypotheses": [
            {"id": "H-ART", "label": "Continuous-futures roll / month-end data artifact",
             "type": "data_artifact", "status": "open",
             "implications": "If roll artifact, raw contract ratio/roll date explains the jump and no economic question remains.",
             "evidence_for": [{"claim": "near month end on continuous futures", "value": "2026-04-30",
                               "class": "observed_fact", "source": "anomaly evidence",
                               "available_at": "2026-04-30", "discriminating": True}],
             "evidence_against": [{"claim": "roll metadata unavailable", "value": "unknown",
                                   "class": "unknown", "source": "provider", "available_at": "2026-04-30"}]},
            {"id": "H-SUPPLY", "label": "Cotton supply/demand shock", "type": "fundamental",
             "status": "untestable",
             "implications": "Cotton inventories/China demand should move before price; not available in current dataset.",
             "evidence_for": [], "evidence_against": [{"claim": "no cotton inventory/China demand data",
                                                      "value": "unknown", "class": "unknown",
                                                      "source": "data_gap", "available_at": "2026-04-30"}]}],
        "evidence": [{"claim": "drawdown detector", "value": "score 0.90; percentile 0.98",
                      "class": "observed_fact", "source": "anomaly", "available_at": "2026-04-30"},
                     {"claim": "continuous futures / month end", "value": "True / True",
                      "class": "observed_fact", "source": "anomaly evidence", "available_at": "2026-04-30"}],
        "critical_unknowns": ["raw cotton contract price and roll date", "CFTC cotton positioning",
                              "USDA cotton inventory/China demand"],
        "falsification_conditions": [
            {"hypothesis_id": "H-ART", "test": "compare raw front/next cotton contract around roll",
             "threshold": "ratio jumps at roll", "data": "raw futures"},
            {"hypothesis_id": "H-SUPPLY", "test": "cotton inventory/China demand change",
             "threshold": "supply/demand shock precedes price", "data": "USDA/customs"}],
        "research_cost": {"hours": 3, "data_access": "low"},
        "decision_impact": {"if_true": "No further research; mark data artifact.",
                            "if_false": "Could investigate cotton fundamentals if raw data validates move."},
        "rationale": "Case D: cotton continuous futures near month end; likely roll artifact, no economic research claim.",
    }
    d = build_dossier(cand, artifact_path="scripts/build_case_d_dossier.py", scan_meta=meta,
                      case_label="CASE_D_DATA_ARTIFACT")
    print(write_dossier(d, "research_dossiers"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
