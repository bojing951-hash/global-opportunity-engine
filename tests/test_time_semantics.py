"""Publication-time semantics: observation date vs availability date vs as-of.

P1-02/P1-03/P1-05 regression guards. A macro observation dated 2026-09-01 is not
knowable until its release date; the anomaly must carry both dates and screening
must use the availability date. Historical replay must slice each evaluation date
independently instead of reusing an end-of-window feature set.
"""

from __future__ import annotations

import pandas as pd
import pytest

from conftest import END_DATE, FEATURE_COLUMNS, make_feature_set
from goe.anomalies import DetectorContext, MacroShift, detect_anomalies
from goe.features import FeatureBuilder


THRESHOLDS = {
    "global": {},
    "detectors": {"macro_shift": {"min_abs_z": 1.5, "cap_abs_z": 3.5, "min_abs_change_3p": 0.1,
                                  "exclude_series": []}},
    "flood_control": {"max_anomalies_per_family": 50, "max_anomalies_per_entity": 5,
                      "dedupe_within_days": 5},
}


def _row(entity: str, feature: str, window: str, date: str, value: float) -> tuple:
    return ("macro", entity, "macro", "US", feature, window, date, value)


def test_macro_anomaly_carries_observation_and_availability_dates():
    dates = pd.date_range("2021-01-01", "2026-09-01", freq="MS")
    rows = []
    for i, d in enumerate(dates):
        z = 2.2 if i == len(dates) - 1 else 0.1
        rows.append(_row("US_CPI", "z_3y", "monthly", d.strftime("%Y-%m-%d"), z))
        rows.append(_row("US_CPI", "change_3p", "monthly", d.strftime("%Y-%m-%d"), 0.4))
        rows.append(_row("US_CPI", "value", "monthly", d.strftime("%Y-%m-%d"), 330.0 + i))
    fs = make_feature_set(as_of="2026-09-01", rows=rows)
    out = detect_anomalies(fs, thresholds=THRESHOLDS, detectors=[MacroShift])
    assert len(out) == 1
    rec = out.iloc[0]
    assert rec["date"] == "2026-09-01"                    # observation date
    assert rec["available_date"] == "2026-10-16"          # +45 day publication lag
    assert rec["evidence"]["available_date"] == "2026-10-16"


def test_opportunity_recency_uses_availability_not_observation(shared_store):
    """A macro print observed weeks ago but published inside the window counts."""
    from goe.opportunities import OpportunityEngine
    from goe.events import EventCalendar
    from goe.config import load_yaml_config

    fs = FeatureBuilder(shared_store, as_of=END_DATE, point_in_time=True).build()
    anomalies = pd.DataFrame([{
        "date": "2024-11-01", "available_date": END_DATE, "anomaly_id": "AN-LATE",
        "detector": "macro_shift", "family": "macro", "entity_id": "US_CPI",
        "entity_kind": "macro", "asset_class": "macro", "region": "US",
        "direction": "above_norm", "window": "3p", "measure": "z_3y",
        "magnitude": 2.5, "score": 0.8, "percentile": float("nan"), "evidence": {},
    }])
    eng = OpportunityEngine(fs, anomalies, transmissions=[], events=EventCalendar([]),
                            scoring=load_yaml_config("scoring.yaml"))
    assert len(eng.current) == 1, "availability date must drive the recent window"


def test_slice_as_of_removes_future_macro_and_positioning(shared_store):
    fs = FeatureBuilder(shared_store, as_of=END_DATE, point_in_time=True).build()
    cut = "2024-06-28"
    sliced = fs.slice_as_of(cut)
    assert sliced.as_of == cut
    assert pd.to_datetime(sliced.long["date"]).max() <= pd.Timestamp(cut)
    if not sliced.macro.empty:
        assert sliced.macro.index.max() <= pd.Timestamp(cut)
    if not sliced.positioning.empty:
        assert sliced.positioning.index.max() <= pd.Timestamp(cut)
    assert len(sliced.long) < len(fs.long)
