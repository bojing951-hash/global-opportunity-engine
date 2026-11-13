"""Deterministic synthetic fixtures for the GOE test suite.

Everything here is generated from fixed seeds and lives in ``tmp_path``. No
test may touch ``data/goe.db``, ``exports/`` or the network.

The synthetic market deliberately contains:

* eight real instrument ids from ``config/universe.yaml`` with 1400 business days
  (enough for 3y robust-z windows and 5y percentile windows)
  of OHLCV + ``adj_close`` rows (source ``yahoo``, explicit ``fetched_at``);
* a one-day crash on gold and a volatility spike on the Nasdaq/VIX pair so the
  anomaly detectors have something to find;
* a US Treasury 2Y/10Y curve, monthly US CPI (released with the 45-day lag),
  weekly CFTC gold positioning (with open interest) and an old quarterly credit
  series used to test stale-series exclusion.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
import pytest

from goe.config import load_universe
from goe.db import Store
from goe.features import FeatureSet, FeatureBuilder

END_DATE = "2024-12-31"
N_BUSINESS_DAYS = 1400
FETCHED_AT = "2024-12-31T22:00:00Z"

INSTRUMENT_IDS = [
    "US_EQ_SPY",
    "US_EQ_QQQ",
    "CN_EQ_CSI300",
    "CM_MET_GC",
    "US_FI_IEF",
    "US_FX_DXY",
    "US_CR_HYG",
    "US_VOL_VIX",
]

# Real config ids referenced by the synthetic curve/macro/positioning data.
CURVE_SERIES = ["UST:2Y", "UST:10Y"]
MACRO_SERIES = ["US_CPI"]
STALE_MACRO_SERIES = "US_CREDIT"          # quarterly, deliberately out of date
POSITIONING_SERIES = ["POS_GOLD_MM", "POS_GOLD_MM:oi"]

FEATURE_COLUMNS = [
    "entity_kind", "entity_id", "asset_class", "region",
    "feature", "window", "date", "value",
]


# ----------------------------------------------------------------- data builders
def build_prices() -> pd.DataFrame:
    """~700 business days of OHLCV for eight real universe instruments."""
    dates = pd.bdate_range(end=END_DATE, periods=N_BUSINESS_DAYS)
    rng = np.random.default_rng(20240501)
    frames: list[pd.DataFrame] = []
    for i, iid in enumerate(INSTRUMENT_IDS):
        sigma = [0.009, 0.011, 0.013, 0.008, 0.005, 0.004, 0.006, 0.050][i]
        drift = [0.00040, 0.00055, 0.00020, 0.00030, 0.00010, 0.00002, 0.00018, 0.0][i]
        rets = rng.normal(drift, sigma, N_BUSINESS_DAYS)
        if iid == "US_EQ_QQQ":
            # late-sample volatility expansion (vol_regime_shift candidate)
            rets[-30:] = rng.normal(0.001, 0.030, 30)
        if iid == "CM_MET_GC":
            # deliberate one-day crash (price_return_shock / drawdown candidate)
            rets[-3] = -0.12
        if iid == "US_VOL_VIX":
            rets[-20:] = rng.normal(0.02, 0.09, 20)
        close = 100.0 * np.exp(np.cumsum(rets))
        open_ = np.r_[close[0], close[:-1]] * (1.0 + rng.normal(0.0, 0.001, N_BUSINESS_DAYS))
        high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0.004, 0.002, N_BUSINESS_DAYS)))
        low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0.004, 0.002, N_BUSINESS_DAYS)))
        volume = rng.integers(500_000, 5_000_000, N_BUSINESS_DAYS).astype(float)
        frames.append(pd.DataFrame({
            "instrument_id": iid,
            "date": dates.strftime("%Y-%m-%d"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "adj_close": close,          # no corporate actions in the fixture
            "volume": volume,
            "source_id": "yahoo",
            "fetched_at": FETCHED_AT,
        }))
    return pd.concat(frames, ignore_index=True)


def build_indicators() -> pd.DataFrame:
    """Curve + macro + positioning series (~4 years)."""
    dates = pd.bdate_range(end=END_DATE, periods=N_BUSINESS_DAYS)
    t = np.arange(N_BUSINESS_DAYS)
    frames: list[pd.DataFrame] = []

    two_y = 4.0 + 0.5 * np.sin(t / 80.0) + 0.0005 * t
    ten_y = two_y + 0.6 + 0.4 * np.sin(t / 110.0 + 1.3)
    for sid, values in (("UST:2Y", two_y), ("UST:10Y", ten_y)):
        frames.append(pd.DataFrame({
            "series_id": sid, "date": dates.strftime("%Y-%m-%d"), "value": values,
            "unit": "percent", "source_id": "treasury_us", "fetched_at": FETCHED_AT,
        }))

    # Monthly CPI index with a clear trend; the last observation (2024-12-01) is
    # published *after* as_of under the 45-day release lag.
    monthly = pd.date_range("2021-01-01", END_DATE, freq="MS")
    cpi = 260.0 * np.exp(0.0025 * np.arange(len(monthly)))
    frames.append(pd.DataFrame({
        "series_id": "US_CPI", "date": monthly.strftime("%Y-%m-%d"), "value": cpi,
        "unit": "index", "source_id": "bls", "fetched_at": FETCHED_AT,
    }))

    # Quarterly credit series whose last obs is > STALE_AFTER_DAYS old.
    quarterly = pd.date_range("2020-06-30", "2023-06-30", freq="QE")
    frames.append(pd.DataFrame({
        "series_id": STALE_MACRO_SERIES, "date": quarterly.strftime("%Y-%m-%d"),
        "value": 100.0 + 2.0 * np.arange(len(quarterly)), "unit": "USD_bn",
        "source_id": "bis", "fetched_at": FETCHED_AT,
    }))

    weekly = pd.date_range("2021-01-01", "2024-12-27", freq="W-FRI")
    w = np.arange(len(weekly))
    frames.append(pd.DataFrame({
        "series_id": "POS_GOLD_MM", "date": weekly.strftime("%Y-%m-%d"),
        "value": 120_000.0 + 50_000.0 * np.sin(w / 20.0), "unit": "contracts",
        "source_id": "cftc", "fetched_at": FETCHED_AT,
    }))
    frames.append(pd.DataFrame({
        "series_id": "POS_GOLD_MM:oi", "date": weekly.strftime("%Y-%m-%d"),
        "value": 400_000.0 + 1_000.0 * w, "unit": "contracts",
        "source_id": "cftc", "fetched_at": FETCHED_AT,
    }))
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------- seeding
def seed_store(path, market: dict[str, Any] | None = None) -> Store:
    """Create a Store at ``path`` and populate it with the synthetic data."""
    data = market or {"prices": build_prices(), "indicators": build_indicators()}
    store = Store(path)
    universe = load_universe()
    store.upsert_instruments([universe.instruments[iid] for iid in INSTRUMENT_IDS])
    store.upsert_prices(data["prices"])
    store.upsert_indicators(data["indicators"])
    return store


# -------------------------------------------------------------------- fixtures
@pytest.fixture(scope="session")
def synthetic_market() -> dict[str, Any]:
    prices = build_prices()
    return {
        "prices": prices,
        "indicators": build_indicators(),
        "instrument_ids": list(INSTRUMENT_IDS),
        "as_of": END_DATE,
        "dates": pd.to_datetime(sorted(prices["date"].unique())),
    }


@pytest.fixture()
def store(tmp_path, synthetic_market) -> Store:
    """Fresh, isolated store for tests that write to the database."""
    s = seed_store(tmp_path / "goe_test.db", synthetic_market)
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(scope="session")
def shared_store(tmp_path_factory, synthetic_market) -> Store:
    """Read-only-by-convention store reused by feature/report tests."""
    path = tmp_path_factory.mktemp("shared_market") / "goe_shared.db"
    s = seed_store(path, synthetic_market)
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(scope="session")
def feature_set(shared_store) -> FeatureSet:
    return FeatureBuilder(shared_store, as_of=END_DATE, point_in_time=True).build()


# ------------------------------------------------------------ object factories
def make_feature_set(
    as_of: str = END_DATE,
    rows: list[tuple] | None = None,
    *,
    prices: pd.DataFrame | None = None,
    returns: pd.DataFrame | None = None,
    macro: pd.DataFrame | None = None,
    positioning: pd.DataFrame | None = None,
    curve: dict[str, pd.DataFrame] | None = None,
) -> FeatureSet:
    """Minimal FeatureSet for detector / scoring / transmission unit tests."""
    long = pd.DataFrame(rows or [], columns=FEATURE_COLUMNS)
    return FeatureSet(
        as_of=as_of,
        long=long,
        prices=prices if prices is not None else pd.DataFrame(),
        returns=returns if returns is not None else pd.DataFrame(),
        curve=curve if curve is not None else {},
        macro=macro if macro is not None else pd.DataFrame(),
        positioning=positioning if positioning is not None else pd.DataFrame(),
    )


def instrument_dict(iid: str = "US_EQ_SPY") -> dict[str, Any]:
    spec = load_universe().instruments[iid]
    return {
        "id": spec.id, "name": spec.name, "symbol": spec.symbol,
        "asset_class": spec.asset_class, "region": spec.region, "role": "primary",
        "importance": spec.importance, "liquidity": spec.liquidity,
    }


def make_draft(**overrides: Any):
    """A structurally valid Draft with sensible defaults for scoring tests."""
    from goe.opportunities import Draft

    base: dict[str, Any] = {
        "archetype": "price_fundamental_divergence",
        "title": "测试机会：价格下行与基本面信号不一致",
        "market": "US",
        "asset_class": "equity_etf",
        "instruments": [instrument_dict("US_EQ_SPY")],
        "horizon": "1-3m",
        "discovery": {
            "what": "SPY 出现价格异常下跌",
            "why_now": "异常在扫描日前后被触发",
            "hypothesis": "价格已计入悲观情形，基本面尚未验证该悲观程度",
            "anomalies": [{"score": 0.8}],
        },
        "mechanism": {"id": None, "chain": ["风险溢价", "价格"], "confidence": 0.5,
                      "conditions": ["信用利差未持续走阔"]},
        "evidence_for": [
            {"claim": "价格已显著回撤", "evidence": "距 1 年高点回撤 12%"},
            {"claim": "波动率处于高位", "evidence": "波动率 5 年分位 92%"},
        ],
        "evidence_against": [
            {"claim": "下跌可能反映基本面恶化", "evidence": "未接入盈利一致预期"},
        ],
        "catalysts": [],
        "open_questions": ["盈利预期是否同步下修？"],
        "invalidation": "若相对基准再跌 8%，则超跌假设失效。",
        "invalidation_checks": [],
        "data_quality": {"score": 0.8, "gaps": []},
    }
    base.update(overrides)
    return Draft(**base)


def make_mechanism(
    mechanism_id: str = "M_TEST",
    *,
    triggers: list[dict[str, Any]] | None = None,
    tests: list[dict[str, Any]] | None = None,
    assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Small mechanisms catalogue (1-2 mechanisms) for transmission tests."""
    return {
        "mechanisms": {
            mechanism_id: {
                "title": f"测试机制 {mechanism_id}",
                "family": "test_family",
                "triggers": triggers if triggers is not None else [{"series": "UST:10Y", "direction": "up"}],
                "affected_assets": assets if assets is not None else [{"id": "CM_MET_GC", "role": "primary"}],
                "evidence_tests": tests or [],
                "conditions": ["测试条件"],
                "falsifiers": ["测试反证条件"],
                "limitations": "仅用于测试。",
            }
        }
    }


def make_opportunity_row(**overrides: Any) -> dict[str, Any]:
    """DB-row shaped opportunity record (JSON columns stored as strings)."""
    base: dict[str, Any] = {
        "opportunity_id": "OPP-0001",
        "fingerprint": "FP-" + "a" * 16,
        "as_of": END_DATE,
        "status": "deep_research",
        "score": 0.82,
        "title": "黄金：价格下行与实际利率信号不一致（测试）",
        "archetype": "price_fundamental_divergence",
        "market": "WORLD",
        "asset_class": "commodity",
        "horizon": "1-3m",
        "instruments_json": json.dumps([instrument_dict("CM_MET_GC")], ensure_ascii=False),
        "discovery_json": json.dumps({
            "what": "黄金价格出现异常下跌，而美元与实际利率未提供解释。",
            "why_now": "异常在 2024-12-31 前后触发。",
            "hypothesis": "若实际利率回落而央行购金持续，金价存在重新定价空间。",
            "anomalies": [{"id": "AN-1", "detector": "price_return_shock", "score": 0.8}],
        }, ensure_ascii=False),
        "mechanism_json": json.dumps({
            "id": "M02_GOLD_REAL_YIELD", "chain": ["实际利率", "机会成本", "金价"],
            "confidence": 0.62, "conditions": ["实际利率是边际定价因子"],
        }, ensure_ascii=False),
        "evidence_for_json": json.dumps([
            {"claim": "价格已显著回撤", "evidence": "距 1 年高点回撤 12%", "source": "yahoo",
             "tier": "aggregator", "as_of": END_DATE},
            {"claim": "美元未走强", "evidence": "DXY 1 个月变化 -0.5%", "source": "yahoo",
             "tier": "aggregator", "as_of": END_DATE},
        ], ensure_ascii=False),
        "evidence_against_json": json.dumps([
            {"claim": "央行购金数据缺失", "evidence": "未接入央行储备明细"},
        ], ensure_ascii=False),
        "catalysts_json": json.dumps([], ensure_ascii=False),
        "open_questions_json": json.dumps(["实际利率的分解是否可靠？"], ensure_ascii=False),
        "invalidation": "若金价相对基准再跌 8%，或美元与实际利率同步走强，则假设失效。",
        "score_json": json.dumps({"anomaly_strength": 0.8, "economic_impact": 0.6},
                                 ensure_ascii=False),
        "data_quality": json.dumps({"score": 0.8, "gaps": ["央行储备数据缺失"]},
                                   ensure_ascii=False),
        "first_seen": "2024-12-20",
        "last_seen": END_DATE,
    }
    base.update(overrides)
    return base
