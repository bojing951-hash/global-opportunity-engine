from __future__ import annotations

from goe.research_engine import spec_for_asset
from goe.research_planner import plan


def test_us_relative_plan_does_not_use_commodity_inventory_template():
    spec = spec_for_asset(asset="US_EQ_QQQ", market="US", asset_class="equity_etf",
                          as_of="2026-11-13", question="q", peers={}, hypotheses=[],
                          case_kind="us_equity_relative")
    task = plan(spec)
    joined = " ".join(task.required_data).lower()
    assert "inventory" not in joined and "supply" not in joined
    assert "iEF".lower() in joined
    assert "us" in task.method.lower() or "relative" in task.method.lower()


def test_unknown_case_kind_is_explicitly_unsupported():
    spec = spec_for_asset(asset="X", market="X", asset_class="equity_index",
                          as_of="2026-11-13", question="q", peers={}, hypotheses=[],
                          case_kind="unknown_template")
    task = plan(spec)
    assert task.availability_status.startswith("UNSUPPORTED_TEST")
