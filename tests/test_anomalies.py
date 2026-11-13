"""Anomaly detector semantics: thresholds, direction mapping, flood control and
deterministic ids."""

from __future__ import annotations

import pandas as pd
import pytest

from conftest import make_feature_set
from goe.anomalies import (
    DetectorContext,
    PriceReturnShock,
    _apply_flood_control,
    anomaly_id,
    detect_anomalies,
)

THRESHOLDS = {
    "global": {"min_abs_z_floor": 1.5},
    "detectors": {
        "price_return_shock": {
            "family": "price",
            "windows": {
                "1d": {"min": 3.0, "cap": 7.0},
                "1m": {"min": 2.0, "cap": 5.0},
            },
            "min_percentile": 0.97,
        }
    },
    "flood_control": {
        "max_anomalies_per_family": 60,
        "max_anomalies_per_entity": 4,
        "dedupe_within_days": 5,
    },
}


def _row(entity_id: str, feature: str, window: str, date: str, value: float,
         kind: str = "instrument") -> tuple:
    return (kind, entity_id, "equity_etf", "US", feature, window, date, value)


def _price_shock_fs():
    """Controlled return z-scores: two crosses, two non-crosses."""
    rows = [
        _row("US_EQ_SPY", "return_z_3y", "1m", "2025-01-02", 2.5),
        _row("US_EQ_SPY", "return_pctile_5y", "1m", "2025-01-02", 0.995),
        _row("US_EQ_QQQ", "return_z_3y", "1m", "2025-01-02", -2.5),
        _row("US_EQ_QQQ", "return_pctile_5y", "1m", "2025-01-02", 0.005),
        # |z| = 1.9 < 2.0: must not fire even with an extreme percentile.
        _row("US_FI_IEF", "return_z_3y", "1m", "2025-01-02", 1.9),
        _row("US_FI_IEF", "return_pctile_5y", "1m", "2025-01-02", 0.999),
        _row("US_FX_DXY", "return_z_3y", "1m", "2025-01-02", -1.9),
        _row("US_FX_DXY", "return_pctile_5y", "1m", "2025-01-02", 0.001),
    ]
    return make_feature_set(rows=rows)


def test_price_return_shock_fires_exactly_above_threshold():
    fs = _price_shock_fs()
    out = detect_anomalies(fs, thresholds=THRESHOLDS, detectors=[PriceReturnShock])

    assert out.attrs["errors"] == []
    assert set(out["entity_id"]) == {"US_EQ_SPY", "US_EQ_QQQ"}
    assert set(out["detector"]) == {"price_return_shock"}
    assert set(out["window"]) == {"1m"}

    spy = out[out.entity_id == "US_EQ_SPY"].iloc[0]
    qqq = out[out.entity_id == "US_EQ_QQQ"].iloc[0]
    assert spy["direction"] == "up"
    assert qqq["direction"] == "down"
    assert spy["percentile"] == pytest.approx(0.995)
    assert qqq["percentile"] == pytest.approx(0.005)
    # score = clip((|z| - min) / (cap - min), 0, 1)
    assert spy["score"] == pytest.approx((2.5 - 2.0) / (5.0 - 2.0))
    assert qqq["score"] == pytest.approx((2.5 - 2.0) / (5.0 - 2.0))
    assert (out["score"] >= 0).all() and (out["score"] <= 1).all()


def test_price_return_shock_one_day_window_uses_its_own_threshold():
    rows = [
        _row("US_EQ_SPY", "return_z_1d_3y", "1d", "2025-01-03", 3.5),
        _row("US_EQ_QQQ", "return_z_1d_3y", "1d", "2025-01-03", 2.9),
    ]
    out = detect_anomalies(make_feature_set(rows=rows), thresholds=THRESHOLDS,
                           detectors=[PriceReturnShock])

    assert len(out) == 1
    row = out.iloc[0]
    assert row["entity_id"] == "US_EQ_SPY"
    assert row["window"] == "1d"
    assert row["score"] == pytest.approx((3.5 - 3.0) / (7.0 - 3.0))


def test_anomaly_ids_are_deterministic():
    fs = _price_shock_fs()
    first = detect_anomalies(fs, thresholds=THRESHOLDS, detectors=[PriceReturnShock])
    second = detect_anomalies(fs, thresholds=THRESHOLDS, detectors=[PriceReturnShock])

    assert sorted(first["anomaly_id"]) == sorted(second["anomaly_id"])
    assert first["anomaly_id"].is_unique

    direct = anomaly_id("price_return_shock", "US_EQ_SPY", "2025-01-02", "up", "1m")
    assert direct in set(first["anomaly_id"])
    assert direct != anomaly_id("price_return_shock", "US_EQ_SPY", "2025-01-02", "down", "1m")
    assert direct != anomaly_id("other_detector", "US_EQ_SPY", "2025-01-02", "up", "1m")


# ---------------------------------------------------------------- flood control
def _flood_ctx(max_family: int, max_entity: int, dedupe_days: int = 5) -> DetectorContext:
    thresholds = {
        "global": {},
        "detectors": {},
        "flood_control": {
            "max_anomalies_per_family": max_family,
            "max_anomalies_per_entity": max_entity,
            "dedupe_within_days": dedupe_days,
        },
    }
    return DetectorContext(make_feature_set(), thresholds)


def _anomaly(date: str, entity: str, detector: str, score: float,
             family: str = "price", direction: str = "down") -> dict:
    return {"date": date, "detector": detector, "family": family,
            "entity_id": entity, "direction": direction, "score": score}


def test_flood_control_caps_per_entity_and_per_family():
    crowded = pd.DataFrame([
        _anomaly("2025-01-02", entity, detector, score)
        for entity in ("US_EQ_SPY", "US_EQ_QQQ", "CN_EQ_CSI300")
        for detector, score in (("d1", 0.9), ("d2", 0.5))
    ])

    per_entity = _apply_flood_control(crowded, _flood_ctx(max_family=60, max_entity=1))
    assert len(per_entity) == 3
    assert per_entity.groupby("entity_id").size().max() == 1

    per_family = _apply_flood_control(crowded, _flood_ctx(max_family=2, max_entity=4))
    assert len(per_family) == 2
    assert per_family["family"].nunique() == 1


def test_flood_control_cross_day_dedupe_collapses_one_event():
    rows = pd.DataFrame([
        _anomaly("2025-01-02", "US_EQ_SPY", "price_return_shock", 0.2),
        _anomaly("2025-01-03", "US_EQ_SPY", "price_return_shock", 0.9),
        # well outside dedupe_within_days=5 -> a genuinely new event
        _anomaly("2025-01-20", "US_EQ_SPY", "price_return_shock", 0.5),
    ])
    out = _apply_flood_control(rows, _flood_ctx(max_family=60, max_entity=4))
    assert len(out) == 2
    assert "2025-01-20" in set(out["date"])


def test_flood_control_cross_day_dedupe_keeps_highest_score():
    """The documented rule keeps the highest-scoring observation in the window.

    Regression guard: an earlier implementation scanned in ascending date order
    and kept the *first* row, silently dropping the stronger later signal.
    """
    rows = pd.DataFrame([
        _anomaly("2025-01-02", "US_EQ_SPY", "price_return_shock", 0.20),
        _anomaly("2025-01-03", "US_EQ_SPY", "price_return_shock", 0.90),
    ])
    out = _apply_flood_control(rows, _flood_ctx(max_family=60, max_entity=4))
    assert len(out) == 1
    assert out.iloc[0]["score"] == pytest.approx(0.90)
