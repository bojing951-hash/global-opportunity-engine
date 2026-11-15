"""Generalized test registry. Selection is by asset class/inputs, not by ticker."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TestDefinition:
    test_id: str
    supported_asset_classes: tuple[str, ...]
    required_inputs: tuple[str, ...]
    method: str
    point_in_time_rules: str
    result_schema: tuple[str, ...]
    failure_semantics: tuple[str, ...]


TESTS = {
    "equity_event_cross_section": TestDefinition(
        "equity_event_cross_section", ("equity_index", "equity_etf", "sector_equity"),
        ("event_asset", "regional_equity", "global_equity", "global_vol", "fx"),
        "same-day regional + prior-US global + percentile + reversal",
        "Asia event close uses prior US session; no same-date US future close",
        ("local_asia_test", "global_lead_test", "asia_regional_test", "fx_test",
         "reversal_test", "historical_percentile"),
        ("INSUFFICIENT_DATA", "UNSUPPORTED_TEST", "INVALID_DATA")),
    "fx_rate_risk_cross_section": TestDefinition(
        "fx_rate_risk_cross_section", ("fx",),
        ("event_asset", "cross1", "cross2", "risk", "vol", "rates"),
        "cross-rate + duration + risk/VIX + percentile",
        "event close; no future data; FX event uses event date",
        ("broad_usd_test", "rate_test", "risk_test", "historical_percentile"),
        ("INSUFFICIENT_DATA", "UNSUPPORTED_TEST", "INVALID_DATA")),
    "commodity_cross_section": TestDefinition(
        "commodity_cross_section", ("commodity", "commodity_etf", "credit"),
        ("event_asset", "dollar", "gold", "rates", "risk", "vol"),
        "dollar + duration + risk + gold co-move + percentile",
        "event close; prior data only through decision as-of",
        ("dollar_test", "real_rate_test", "risk_test", "gold_test",
         "historical_percentile"),
        ("INSUFFICIENT_DATA", "UNSUPPORTED_TEST", "INVALID_DATA")),
}


def select_test(asset_class: str) -> TestDefinition | None:
    for t in TESTS.values():
        if asset_class in t.supported_asset_classes:
            return t
    return None


def execution_key(test_id: str) -> str:
    return {"equity_event_cross_section": "equity_event",
            "fx_rate_risk_cross_section": "fx_level",
            "commodity_cross_section": "commodity_event"}[test_id]
