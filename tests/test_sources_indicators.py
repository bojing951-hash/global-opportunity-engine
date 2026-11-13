"""Offline parsing tests + live smoke tests for the indicator adapters.

Offline tests use tiny inline fixtures and never touch the network. The live
tests are marked ``network`` (deselect with ``-m "not network"``); they skip
when the endpoint is genuinely unreachable but **fail** when a reachable
endpoint is parsed to zero rows.
"""

from __future__ import annotations

import io
import json

import pandas as pd
import pytest

from goe.sources.base import FetchResult, ProviderError
from goe.sources.bis import parse_bis_csv, period_to_date
from goe.sources.bls import parse_bls_json
from goe.sources.cftc import extract_positions, match_market
from goe.sources.ecb import parse_ecb_csv
from goe.sources.eurostat import parse_eurostat_json
from goe.sources.mof_japan import parse_mof_csv
from goe.sources.shiller import decimal_year_to_month, parse_shiller_xls
from goe.sources.treasury import COLUMN_TO_TENOR, parse_treasury_csv

# --------------------------------------------------------------------------- fixtures

TREASURY_CSV = """Date,"1 Mo","1.5 Month","2 Mo","3 Mo","4 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"
01/02/2024,5.54,5.55,5.52,5.40,5.35,5.20,4.82,4.35,4.12,3.95,3.98,4.02,4.35,4.20
01/03/2024,5.55,5.56,5.53,5.41,5.36,5.21,4.83,4.36,4.13,3.96,3.99,4.03,4.36,4.21
"""

TREASURY_ZERO_CSV = """Date,"1 Mo","2 Mo","3 Mo","4 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"
01/02/2024,0.00,0.01,0.02,0.03,0.05,0.10,0.25,0.40,1.00,1.50,2.00,2.50,3.00
"""

BIS_CPI = """FREQ,REF_AREA,UNIT_MEASURE,UNIT_MULT,TIME_PERIOD,OBS_VALUE
M,JP,628,0,2024-01,105.0
M,JP,771,0,2024-01,3.0
M,JP,771,0,2024-02,3.5
"""

BIS_TC = """FREQ,REF_AREA,UNIT_TYPE,TC_ADJUST,UNIT_MEASURE,UNIT_MULT,TIME_PERIOD,OBS_VALUE
Q,US,XDC,U,USD,9,2024-Q1,41000.0
Q,US,XDC,A,USD,9,2024-Q1,41000.0
Q,US,USD,A,USD,9,2024-Q1,41000.0
Q,US,770,A,367,0,2024-Q1,140.0
Q,US,XDC,U,USD,9,2024-Q2,42000.0
"""

CFTC_FIN = """Market_and_Exchange_Names,Report_Date_as_YYYY-MM-DD,Open_Interest_All,Asset_Mgr_Positions_Long_All,Asset_Mgr_Positions_Short_All,Lev_Money_Positions_Long_All,Lev_Money_Positions_Short_All
E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE,2024-01-02,2000000,900000,100000,500000,800000
E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE,2024-01-09,2010000,910000,110000,510000,810000
SOME OTHER MARKET,2024-01-09,10,1,1,1,1
"""

CFTC_FIN_OLD = """Market_and_Exchange_Names,Report_Date_as_YYYY-MM-DD,Open_Interest_All,Asset_Mgr_Positions_Long_All,Asset_Mgr_Positions_Short_All,Lev_Money_Positions_Long_All,Lev_Money_Positions_Short_All
E-MINI S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE,2019-01-08,1500000,700000,100000,400000,600000
"""

CFTC_FIN_TRANSITION = """Market_and_Exchange_Names,Report_Date_as_YYYY-MM-DD,Open_Interest_All,Asset_Mgr_Positions_Long_All,Asset_Mgr_Positions_Short_All,Lev_Money_Positions_Long_All,Lev_Money_Positions_Short_All
E-MINI S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE,2022-01-04,2000000,900000,100000,500000,800000
E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE,2022-02-08,2100000,910000,110000,510000,810000
"""

CFTC_DISAGG = """Market_and_Exchange_Names,Report_Date_as_YYYY-MM-DD,Open_Interest_All,M_Money_Positions_Long_All,M_Money_Positions_Short_All
GOLD - COMMODITY EXCHANGE INC.,2024-01-02,400000,200000,50000
"""

MOF_CSV = """Interest Rate (January 2024),,,,,,,,,,,,,,,(Unit : %)
Date,1Y,2Y,3Y,4Y,5Y,6Y,7Y,8Y,9Y,10Y,15Y,20Y,25Y,30Y,40Y
2024/1/4,-0.1,0.05,0.1,0.15,0.2,0.25,0.3,0.35,0.4,0.5,0.9,1.2,1.5,1.7,2.0
2024/1/5,,0.05,0.1,0.15,0.2,0.25,0.3,0.35,0.4,0.5,0.9,1.2,1.5,1.7,2.0
2024/1/8,-,-,0.1,0.15,0.2,0.25,0.3,0.35,0.4,0.5,0.9,1.2,1.5,1.7,2.0
"  note",,,,,,,,,,,,,,,
"""

ECB_CSV = """KEY,FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y,D,EUR,2024-01-02,2.5
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y,D,EUR,2024-01-03,2.6
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y,D,EUR,2024-01-04,
"""

EUROSTAT_JSON = {
    "version": "2.0",
    "class": "dataset",
    "label": "HICP - monthly data",
    "updated": "2026-02-06T23:00:00+0100",
    "id": ["freq", "unit", "coicop", "geo", "time"],
    "size": [1, 1, 1, 1, 3],
    "dimension": {
        "freq": {"category": {"index": {"M": 0}}},
        "unit": {"category": {"index": {"RCH_A": 0}}},
        "coicop": {"category": {"index": {"CP00": 0}}},
        "geo": {"category": {"index": {"EA": 0}}},
        "time": {"category": {"index": {"2025-11": 0, "2025-12": 1, "2026-01": 2}}},
    },
    "value": {"0": 2.1, "1": 2.0, "2": None},
}


def _shiller_workbook_xlsx() -> bytes:
    rows = [[None] * 22 for _ in range(12)]
    rows[5][12] = "Ratio"
    rows[6][12] = "P/E10 or"
    rows[7][0] = "Date"
    rows[7][1] = "P"
    rows[7][12] = "CAPE"
    rows[7][16] = "Yield"
    rows[6][16] = "CAPE"  # part of "Excess CAPE Yield": must not be selected
    rows[8][0], rows[8][12] = 2022.09, 30.1
    rows[9][0], rows[9][12] = 2022.1, 28.2   # October, not January
    rows[10][0], rows[10][12] = 2022.11, 29.0
    rows[11][0], rows[11][1] = None, "note row"
    frame = pd.DataFrame(rows, dtype=object)
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False, header=False, engine="openpyxl")
    return buffer.getvalue()


# --------------------------------------------------------------------------- treasury


def test_treasury_parse_maps_known_tenors_and_ignores_extra_columns():
    frame = parse_treasury_csv(TREASURY_CSV)
    assert set(frame["tenor"]) == set(COLUMN_TO_TENOR.values())
    assert len(frame) == 2 * len(COLUMN_TO_TENOR)
    assert frame["date"].min() == pd.Timestamp("2024-01-02")
    ten_y = frame[(frame["tenor"] == "10Y") & (frame["date"] == pd.Timestamp("2024-01-02"))]
    assert ten_y["value"].iloc[0] == pytest.approx(4.02)


def test_treasury_provider_keeps_zero_yields_and_normalises(monkeypatch):
    from goe.sources.treasury import TreasuryUSProvider

    provider = TreasuryUSProvider()
    monkeypatch.setattr(provider, "_year_text", lambda year, current: TREASURY_ZERO_CSV)
    result = provider.fetch_indicators(
        [{"id": "UST", "kind": "curve", "tenors": ["1M", "10Y"], "start_year": 2024}],
        start="2024-01-01",
    )
    assert isinstance(result, FetchResult)
    assert result.rows > 0
    assert (result.frame["value"] == 0.0).any()  # 0.00 is a real bill yield
    assert set(result.frame["unit"]) == {"percent"}
    assert set(result.frame["series_id"]) == {"UST:1M", "UST:10Y"}
    assert result.fetched_at.endswith("Z")


# --------------------------------------------------------------------------- bis


def test_bis_long_cpi_selects_the_spec_unit_variant():
    frame, meta = parse_bis_csv(
        BIS_CPI,
        {"id": "JP_CPI", "kind": "macro", "series": "WS_LONG_CPI/M.JP",
         "unit": "percent", "frequency": "monthly"},
    )
    assert frame["value"].tolist() == [3.0, 3.5]
    assert set(frame["unit"]) == {"percent_yoy"}
    assert meta["unit_measure"] == "771"
    assert frame["date"].tolist() == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")]


def test_bis_credit_selects_domestic_currency_unadjusted_and_flags_unit_mult():
    frame, meta = parse_bis_csv(
        BIS_TC,
        {"id": "US_CREDIT", "kind": "macro", "series": "WS_TC/Q.US.P.A.M",
         "unit": "USD_mn", "frequency": "quarterly"},
    )
    assert frame["value"].tolist() == [41000.0, 42000.0]
    assert frame["date"].tolist() == [pd.Timestamp("2024-03-01"), pd.Timestamp("2024-06-01")]
    assert meta["unit_mult"] == "9"
    assert meta["unit"] == "USD_mn"


@pytest.mark.parametrize(
    "period,expected",
    [
        ("2026-08", "2026-08-01"),
        ("2025-Q4", "2025-12-01"),
        ("2025", "2025-12-01"),
        ("2026-08-13", "2026-08-13"),
    ],
)
def test_bis_period_to_date(period, expected):
    assert period_to_date(period) == pd.Timestamp(expected)


# --------------------------------------------------------------------------- eurostat


def test_eurostat_jsonstat_linear_index_decode():
    frame, meta = parse_eurostat_json(EUROSTAT_JSON)
    assert frame["value"].tolist() == [2.1, 2.0]  # null cell skipped, not filled
    assert frame["date"].tolist() == [pd.Timestamp("2025-11-01"), pd.Timestamp("2025-12-01")]
    assert meta["updated"].startswith("2026-02-06")


def test_eurostat_rejects_ambiguous_multi_dimension_response():
    payload = json.loads(json.dumps(EUROSTAT_JSON))
    payload["size"] = [1, 1, 1, 2, 3]
    payload["dimension"]["geo"]["category"]["index"] = {"EA": 0, "DE": 1}
    with pytest.raises(ValueError, match="non-time dimensions"):
        parse_eurostat_json(payload)


# --------------------------------------------------------------------------- cftc


def test_cftc_fin_metric_mapping_and_open_interest():
    frame = pd.read_csv(io.StringIO(CFTC_FIN))
    part, info = extract_positions(
        frame,
        {"id": "POS_SP500_LEV", "kind": "positioning", "report": "fin",
         "market": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
         "metric": "net_lev_money", "unit": "contracts"},
    )
    net = part[part["series_id"] == "POS_SP500_LEV"].sort_values("date")
    oi = part[part["series_id"] == "POS_SP500_LEV:oi"].sort_values("date")
    assert net["value"].tolist() == [-300000.0, -300000.0]
    assert oi["value"].tolist() == [2000000.0, 2010000.0]
    assert not info["used_alias"]


def test_cftc_same_year_rename_keeps_both_names():
    frame = pd.read_csv(io.StringIO(CFTC_FIN_TRANSITION))
    part, info = extract_positions(
        frame,
        {"id": "POS_SP500_LEV", "kind": "positioning", "report": "fin",
         "market": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
         "metric": "net_lev_money", "unit": "contracts"},
    )
    net = part[part["series_id"] == "POS_SP500_LEV"].sort_values("date")
    assert net["date"].tolist() == [pd.Timestamp("2022-01-04"), pd.Timestamp("2022-02-08")]
    assert net["value"].tolist() == [-300000.0, -300000.0]
    assert info["used_alias"] is True
    assert len(info["matched_markets"]) == 2


def test_cftc_disagg_managed_money():
    frame = pd.read_csv(io.StringIO(CFTC_DISAGG))
    part, _ = extract_positions(
        frame,
        {"id": "POS_GOLD_MM", "kind": "positioning", "report": "disagg",
         "market": "GOLD - COMMODITY EXCHANGE INC.", "metric": "net_managed_money",
         "unit": "contracts"},
    )
    assert part[part["series_id"] == "POS_GOLD_MM"]["value"].iloc[0] == 150000
    assert part[part["series_id"] == "POS_GOLD_MM:oi"]["value"].iloc[0] == 400000


def test_cftc_historical_market_alias_and_copper_yaml_truncation():
    old = pd.read_csv(io.StringIO(CFTC_FIN_OLD))
    part, info = extract_positions(
        old,
        {"id": "POS_SP500_LEV", "kind": "positioning", "report": "fin",
         "market": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
         "metric": "net_lev_money", "unit": "contracts"},
    )
    assert info["used_alias"] is True
    assert part[part["series_id"] == "POS_SP500_LEV"]["value"].iloc[0] == -200000

    matched, used = match_market({"COPPER- #1 - COMMODITY EXCHANGE INC."}, "COPPER-")
    assert matched == "COPPER- #1 - COMMODITY EXCHANGE INC."
    assert used is True


def test_cftc_unknown_metric_raises():
    frame = pd.read_csv(io.StringIO(CFTC_FIN))
    with pytest.raises(ValueError, match="unsupported"):
        extract_positions(
            frame,
            {"id": "X", "kind": "positioning", "report": "fin",
             "market": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
             "metric": "net_noncommercial", "unit": "contracts"},
        )


# --------------------------------------------------------------------------- shiller


def test_shiller_decimal_year_month_handles_dropped_trailing_zero():
    assert decimal_year_to_month(2022.1) == pd.Timestamp("2022-10-01")
    assert decimal_year_to_month(2022.10) == pd.Timestamp("2022-10-01")
    assert decimal_year_to_month(2023.01) == pd.Timestamp("2023-01-01")
    assert decimal_year_to_month(2023.13) is None
    assert decimal_year_to_month(None) is None


def test_shiller_parses_cape_column_not_excess_cape_yield():
    pytest.importorskip("openpyxl")
    frame, meta = parse_shiller_xls(_shiller_workbook_xlsx())
    assert meta["cape_column"] == 12
    assert frame["date"].tolist() == [
        pd.Timestamp("2022-09-01"),
        pd.Timestamp("2022-10-01"),
        pd.Timestamp("2022-11-01"),
    ]
    assert frame["value"].tolist() == [30.1, 28.2, 29.0]


# --------------------------------------------------------------------------- mof / ecb / bls


def test_mof_wide_layout_skips_dashes_and_keeps_negative_yields():
    frame = parse_mof_csv(MOF_CSV)
    assert set(frame["tenor"]) == {h for h in ["1Y", "2Y", "3Y", "4Y", "5Y", "6Y", "7Y",
                                               "8Y", "9Y", "10Y", "15Y", "20Y", "25Y",
                                               "30Y", "40Y"]}
    assert frame[(frame["tenor"] == "1Y") & (frame["date"] == pd.Timestamp("2024-01-04"))][
        "value"
    ].iloc[0] == pytest.approx(-0.1)
    assert len(frame) == 15 * 3 - 3  # 1Y blank/-, 2Y dash


def test_ecb_csv_parser_drops_blank_observations():
    frame = parse_ecb_csv(ECB_CSV)
    assert frame["value"].tolist() == [2.5, 2.6]
    assert frame["date"].max() == pd.Timestamp("2024-01-03")


def test_bls_parser_skips_annual_m13_and_non_numeric():
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "message": [],
        "Results": {
            "series": [
                {
                    "seriesID": "CUUR0000SA0",
                    "data": [
                        {"year": "2024", "period": "M01", "value": "308.417"},
                        {"year": "2023", "period": "M13", "value": "304.0"},
                        {"year": "2024", "period": "M02", "value": "-"},
                    ],
                }
            ]
        },
    }
    frame, status, messages = parse_bls_json(payload)
    assert status == "REQUEST_SUCCEEDED"
    assert messages == []
    assert frame["value"].tolist() == [308.417]
    assert frame["date"].tolist() == [pd.Timestamp("2024-01-01")]


# --------------------------------------------------------------------------- live smoke

_NETWORK_HINTS = (
    "connection", "timed out", "timeout", "ssl", "proxy", "name or service",
    "temporary failure", "nodename", "network", "max retries", "httperror",
    "unreachable", "certificate", "urlopen", "read timed out", "remotedisconnected",
)


def _skip_if_network_message(message: str) -> None:
    lowered = message.lower()
    if any(hint in lowered for hint in _NETWORK_HINTS):
        pytest.skip(f"network/endpoint unavailable: {message[:240]}")


def _live(provider, specs, start: str, expect_series: str) -> None:
    try:
        result = provider.fetch_indicators(specs, start=start)
    except ProviderError as exc:
        _skip_if_network_message(str(exc))
        raise
    if result.frame.empty:
        _skip_if_network_message(" ".join(result.errors))
        pytest.fail(
            f"{provider.provider_id}: endpoint reachable but parse returned zero rows "
            f"(errors={result.errors[:3]}, notes={[n.detail for n in result.notes[:3]]})"
        )
    assert isinstance(result, FetchResult)
    assert result.fetched_at.endswith("Z")
    assert set(["series_id", "date", "value", "unit"]).issubset(result.frame.columns)
    assert expect_series in set(result.frame["series_id"]), sorted(result.frame["series_id"].unique())[:10]


@pytest.mark.network
def test_live_treasury():
    from goe.sources.treasury import TreasuryUSProvider

    _live(TreasuryUSProvider(),
          [{"id": "UST", "kind": "curve", "tenors": ["10Y"], "start_year": 2026}],
          "2026-01-01", "UST:10Y")


@pytest.mark.network
def test_live_mof_japan():
    from goe.sources.mof_japan import MofJapanProvider

    _live(MofJapanProvider(),
          [{"id": "JGB", "kind": "curve", "tenors": ["10Y"], "start_year": 2026}],
          "2026-01-01", "JGB:10Y")


@pytest.mark.network
def test_live_ecb():
    from goe.sources.ecb import EcbProvider

    _live(EcbProvider(),
          [{"id": "EAC", "kind": "curve", "tenors": ["10Y"], "start_year": 2026}],
          "2026-01-01", "EAC:10Y")


@pytest.mark.network
def test_live_bls():
    from goe.sources.bls import BlsProvider

    _live(BlsProvider(),
          [{"id": "US_CPI", "kind": "macro", "series": "CUUR0000SA0", "unit": "index",
            "frequency": "monthly"}],
          "2025-01-01", "US_CPI")


@pytest.mark.network
def test_live_bis():
    from goe.sources.bis import BisProvider

    _live(BisProvider(),
          [{"id": "US_POLICY_RATE", "kind": "macro", "series": "WS_CBPOL/M.US",
            "unit": "percent", "frequency": "monthly"}],
          "2025-01-01", "US_POLICY_RATE")


@pytest.mark.network
def test_live_eurostat():
    from goe.sources.eurostat import EurostatProvider

    _live(EurostatProvider(),
          [{"id": "EA_HICP", "kind": "macro",
            "series": "prc_hicp_manr?geo=EA&coicop=CP00&unit=RCH_A",
            "unit": "percent", "frequency": "monthly"}],
          "2025-01-01", "EA_HICP")


@pytest.mark.network
def test_live_cftc():
    from goe.sources.cftc import CftcProvider

    _live(CftcProvider(),
          [{"id": "POS_GOLD_MM", "kind": "positioning", "report": "disagg",
            "market": "GOLD - COMMODITY EXCHANGE INC.", "metric": "net_managed_money",
            "unit": "contracts"}],
          "2026-01-01", "POS_GOLD_MM")


@pytest.mark.network
def test_live_akshare_cn_bond():
    from goe.sources.akshare_cn_bond import AkshareCnBondProvider

    result = AkshareCnBondProvider().fetch_indicators(
        [{"id": "CN", "kind": "curve", "tenors": ["10Y"], "start_year": 2026}], start="2026-01-01")
    if result.frame.empty:
        _skip_if_network_message(" ".join(result.errors))
        pytest.fail(f"akshare endpoint reachable but zero rows: {result.errors[:3]}")
    assert "CN:10Y" in set(result.frame["series_id"])


@pytest.mark.network
def test_live_shiller():
    from goe.sources.shiller import ShillerProvider

    _live(ShillerProvider(),
          [{"id": "US_CAPE", "kind": "macro", "series": "CAPE", "unit": "ratio",
            "frequency": "monthly"}],
          "2015-01-01", "US_CAPE")
