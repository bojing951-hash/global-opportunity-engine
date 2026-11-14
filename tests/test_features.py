"""Feature-layer correctness: point-in-time discipline, hand-checked formulas,
curve features, release lags and stale-series exclusion.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from conftest import END_DATE, STALE_MACRO_SERIES
from goe.features import (
    RELEASE_LAG_DAYS,
    STALE_AFTER_DAYS,
    FeatureBuilder,
    ann_vol,
    drawdown_from_high,
    robust_z,
    rolling_percentile,
    safe_pct_change,
)


# ------------------------------------------------------------------- formulas
def test_simple_returns_are_exact_on_a_tiny_series():
    px = pd.Series([100.0, 110.0, 99.0])
    rets = safe_pct_change(px, 1)
    assert math.isnan(rets.iloc[0])
    assert rets.iloc[1] == pytest.approx(0.10)
    assert rets.iloc[2] == pytest.approx(-0.10)

    two_period = safe_pct_change(px, 2)
    assert math.isnan(two_period.iloc[0])
    assert math.isnan(two_period.iloc[1])
    assert two_period.iloc[2] == pytest.approx(99.0 / 100.0 - 1.0)


def test_annualised_volatility_matches_hand_computation():
    # Alternating +/-1% returns: sample std = 1% * sqrt(n/(n-1)).
    rets = pd.Series([0.01, -0.01] * 10)
    n = 20
    expected_std = 0.01 * math.sqrt(n / (n - 1))
    expected = expected_std * math.sqrt(252)
    got = ann_vol(rets, window=20).iloc[-1]
    assert got == pytest.approx(expected, rel=1e-12)

    # A shorter history than the minimum period yields NaN, never a substitute.
    short = ann_vol(pd.Series([0.01, -0.01, 0.02]), window=252)
    assert short.isna().all()


def test_drawdown_from_high_matches_hand_computation():
    # drawdown_from_high needs min_periods=max(20, window//4); use window=40.
    px = pd.Series([100.0] * 20 + [120.0, 90.0])
    dd = drawdown_from_high(px, window=40)
    assert dd.iloc[20] == pytest.approx(0.0)          # at a new high
    assert dd.iloc[21] == pytest.approx(90.0 / 120.0 - 1.0)  # 25% below the high
    assert dd.iloc[:19].isna().all()


def test_robust_z_respects_minimum_periods():
    z = robust_z(pd.Series(np.arange(20.0)), window=8)
    # min_periods = max(6, window//5) = 6
    assert z.iloc[:5].isna().all()
    assert np.isfinite(z.iloc[5])


def test_robust_z_matches_documented_median_mad_formula():
    """features.robust_z is documented as (x - median) / (1.4826 * MAD).

    The MAD is the median absolute deviation *within the current trailing
    window*.  A linear ramp makes the expected value easy to compute by hand.

    Regression guard: an earlier implementation computed a rolling median of
    deviations from *each point's own* rolling median, which is not the window
    MAD and produced a different scale (see ``goe/features.py::robust_z``).
    """
    values = np.arange(1.0, 21.0)
    window = 8
    x = pd.Series(values)

    trailing = values[-window:]
    median = float(np.median(trailing))
    mad = float(np.median(np.abs(trailing - median)))
    expected = (values[-1] - median) / (1.4826 * mad)

    got = robust_z(x, window).iloc[-1]
    assert got == pytest.approx(expected, rel=1e-9)


def test_rolling_percentile_ranks_latest_value():
    pct = rolling_percentile(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]), window=6)
    assert pct.iloc[-1] == pytest.approx(1.0)  # latest value is the maximum
    descending = rolling_percentile(pd.Series([6.0, 5.0, 4.0, 3.0, 2.0, 1.0]), window=6)
    assert descending.iloc[-1] == pytest.approx(0.0)


# -------------------------------------------------------------- point-in-time
def test_no_lookahead_for_price_features(shared_store, feature_set, synthetic_market):
    """A value computed at t with as_of=t must equal the same t in a later build."""
    dates = synthetic_market["dates"]
    t = dates[500].strftime("%Y-%m-%d")
    fs_t = FeatureBuilder(shared_store, as_of=t).build()

    assert fs_t.as_of == t
    for feature, window in (
        ("return", "1m"),
        ("ma_gap_200d", ""),
        ("return_z_3y", "1m"),
        ("ann_vol", "3m"),
        ("drawdown_252d", ""),
    ):
        early = fs_t.value("US_EQ_SPY", feature, window)
        later = feature_set.series("US_EQ_SPY", feature, window).loc[t]
        assert np.isfinite(early), f"{feature} should be available at {t}"
        assert early == pytest.approx(float(later), rel=1e-12, abs=1e-15), feature


# --------------------------------------------------------------------- curve
def test_curve_slope_features_exist_when_2y_and_10y_present(feature_set, synthetic_market):
    assert "UST" in feature_set.curve
    assert set(feature_set.curve["UST"].columns) == {"2Y", "10Y"}
    assert "UST" in feature_set.entities("curve")

    slope = feature_set.series("UST", "slope_2s10s")
    assert not slope.empty
    assert np.isfinite(slope.iloc[-1])
    assert slope.iloc[-1] == pytest.approx(
        feature_set.value("UST:10Y", "level", "10Y")
        - feature_set.value("UST:2Y", "level", "2Y")
    )
    assert np.isfinite(feature_set.value("UST", "slope_2s10s_z_3y"))
    assert np.isfinite(feature_set.value("UST", "slope_2s10s_change_1m", "1m"))

    # Curve level features are keyed by (series, tenor).
    ten_y = synthetic_market["indicators"]
    last_10y = ten_y[(ten_y.series_id == "UST:10Y") & (ten_y.date <= END_DATE)].iloc[-1]["value"]
    assert feature_set.value("UST:10Y", "level", "10Y") == pytest.approx(last_10y)


# --------------------------------------------------------------------- macro
def test_macro_release_lag_excludes_unpublished_observations(feature_set):
    lag = RELEASE_LAG_DAYS["monthly"]

    assert not feature_set.macro.empty
    # Macro panels are indexed by AVAILABILITY date: nothing published after the
    # as-of date may appear, and a print is dated observation + lag.
    assert feature_set.macro.index.max() <= pd.Timestamp(END_DATE)
    assert pd.Timestamp("2024-11-01") + pd.Timedelta(days=lag) in feature_set.macro.index
    assert pd.Timestamp("2024-12-01") + pd.Timedelta(days=lag) not in feature_set.macro.index

    macro_rows = feature_set.long[
        (feature_set.long.entity_kind == "macro") & (feature_set.long.entity_id == "US_CPI")
    ]
    assert not macro_rows.empty
    assert pd.to_datetime(macro_rows["date"]).max() <= pd.Timestamp(END_DATE)


def test_stale_macro_series_is_excluded(feature_set):
    assert STALE_MACRO_SERIES not in feature_set.macro.columns
    stale = feature_set.meta["stale_macro_series"]
    assert STALE_MACRO_SERIES in stale
    assert stale[STALE_MACRO_SERIES] > STALE_AFTER_DAYS["quarterly"]
    # No feature row may be emitted from the stale series.
    assert feature_set.long[feature_set.long.entity_id == STALE_MACRO_SERIES].empty


def test_point_in_time_false_skips_release_lag(shared_store, feature_set, synthetic_market):
    no_pit = FeatureBuilder(shared_store, as_of=END_DATE, point_in_time=False).build()

    assert "US_CPI" in no_pit.macro.columns
    # The 2024-12-01 print is visible without the lag, but not with it.
    assert no_pit.macro.index.max() == pd.Timestamp("2024-12-01")
    assert feature_set.macro.index.max() == pd.Timestamp("2024-11-01") + pd.Timedelta(
        days=RELEASE_LAG_DAYS["monthly"])

    indicators = synthetic_market["indicators"]
    last_cpi = indicators[indicators.series_id == "US_CPI"].iloc[-1]
    assert no_pit.macro.loc[pd.Timestamp("2024-12-01"), "US_CPI"] == pytest.approx(last_cpi["value"])
