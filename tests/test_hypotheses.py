from __future__ import annotations

from types import SimpleNamespace

from goe.hypotheses import build_hypotheses


def spec(asset_class, name, region, is_futures=False):
    return SimpleNamespace(asset_class=asset_class, name=name, region=region, is_futures=is_futures)


def build(s, **kw):
    base = dict(detector="price_return_shock", direction="down", ret1m=-0.08,
                ddpct=0.03, gap_value=0.2, positioning_value=None,
                mechanism_statuses=[], has_price_issue=False, as_of="2026-01-01",
                available={"cross_asset": True, "fx": True, "benchmark": False,
                           "policy_calendar": False})
    base.update(kw)
    return build_hypotheses(s, **base)


def test_hypotheses_differ_by_phenomenon():
    cases = {
        "japan_equity": build(spec("equity_index", "Nikkei 225", "JP")),
        "us_equity_etf": build(spec("equity_etf", "QQQ", "US")),
        "sector_etf": build(spec("sector_equity", "XLV", "US")),
        "fx": build(spec("fx", "DXY", "US")),
        "rates": build(spec("fixed_income", "IEF", "US")),
        "commodity": build(spec("commodity", "Gold", "WORLD", True)),
    }
    label_sets = {k: frozenset(h["label"] for h in v["hypotheses"]) for k, v in cases.items()}
    # at least four genuinely different structures, not one template
    assert len(set(label_sets.values())) >= 4
    assert label_sets["japan_equity"] != label_sets["us_equity_etf"]
    assert label_sets["us_equity_etf"] != label_sets["sector_etf"]
    assert label_sets["fx"] != label_sets["rates"]
    for name, b in cases.items():
        assert b["open_count"] >= 2, name
        assert b["discriminating"], name
        assert len({t["hypothesis_id"] for t in b["tests"]}) >= 2, name
        assert b["decision_impact"]["if_true"] != b["decision_impact"]["if_false"]


def test_decision_impact_is_not_a_global_boilerplate():
    a = build(spec("equity_index", "Nikkei 225", "JP"))["decision_impact"]
    b = build(spec("fixed_income", "IEF", "US"))["decision_impact"]
    c = build(spec("commodity", "Gold", "WORLD", True))["decision_impact"]
    assert len({a["if_true"], b["if_true"], c["if_true"]}) == 3


def test_untestable_hypotheses_do_not_count_as_open():
    b = build(spec("fx", "DXY", "US"), positioning_value=None)
    pos = [h for h in b["hypotheses"] if h["id"].endswith("-POS")][0]
    assert pos["status"] == "untestable"
    assert all(t["hypothesis_id"] != pos["id"] for t in b["tests"])


def test_untestable_does_not_support_and_tests_declare_data_status():
    b = build(spec("equity_index", "Nikkei 225", "JP"))
    for h in b["hypotheses"]:
        if h["status"] == "untestable":
            assert h["evidence_for"] == [], h["id"]
    for t in b["tests"]:
        assert t["data_status"] in ("available", "obtainable")


def test_no_self_benchmark_available():
    # benchmark flag is passed by triage; this only verifies tests can be obtainable
    b = build(spec("equity_index", "Nikkei 225", "JP"),
              available={"cross_asset": True, "fx": True, "benchmark": False,
                         "policy_calendar": False})
    local = [t for t in b["tests"] if t["hypothesis_id"].endswith("-LOCAL")][0]
    assert local["data_status"] == "obtainable"


def test_all_untestable_hypotheses_have_no_supporting_evidence():
    cases = [
        ("equity_index", "Nikkei 225", "JP", False),
        ("equity_etf", "QQQ", "US", False),
        ("sector_equity", "Health Care Select Sector SPDR", "US", False),
        ("fx", "USD/BRL", "BR", False),
        ("fixed_income", "Bund", "DE", False),
        ("commodity", "COMEX Gold", "WORLD", True),
        ("commodity", "iShares Silver Trust", "US", False),
        ("crypto", "Bitcoin", "WORLD", False),
    ]
    for ac, name, region, fut in cases:
        b = build(spec(ac, name, region, fut))
        for h in b["hypotheses"]:
            if h["status"] == "untestable":
                assert h["evidence_for"] == [], (ac, h["id"])
