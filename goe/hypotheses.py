"""Phenomenon-specific competing hypotheses (P1-C).

The same five labels for every asset is not research. This module builds a
hypothesis set from the *asset class, region, detector and available evidence*.
Hypotheses that cannot be tested with available/obtainable data are explicitly
marked untestable and never counted as supporting evidence. A candidate with
fewer than two open, discriminating hypotheses is demoted to Market Intelligence.
"""
from __future__ import annotations

from typing import Any

import numpy as np

POLICY_REGIONS = {"US", "CN", "JP", "EA", "UK"}


def _ev(claim: str, value: str, eclass: str, source: str, as_of: str,
        hypothesis_id: str | None = None) -> dict[str, Any]:
    out = {"claim": claim, "value": value, "class": eclass, "source": source,
           "available_at": as_of}
    if hypothesis_id:
        out["hypothesis_id"] = hypothesis_id
    return out


def _h(hid: str, label: str, typ: str, status: str, implications: str,
       for_ev: list[dict], against: list[dict]) -> dict[str, Any]:
    return {"id": hid, "label": label, "type": typ, "status": status,
            "implications": implications, "evidence_for": for_ev,
            "evidence_against": against}


def _test(hid: str, test: str, threshold: str, data: str,
          data_status: str = "obtainable") -> dict[str, Any]:
    return {"hypothesis_id": hid, "test": test, "threshold": threshold, "data": data,
            "data_status": data_status}


def build_hypotheses(spec, *, detector: str, direction: str, ret1m: float | None,
                     ddpct: float | None, gap_value: float | None,
                     positioning_value: float | None, mechanism_statuses: list[str],
                     has_price_issue: bool = False, as_of: str = "",
                     available: dict[str, bool] | None = None) -> dict[str, Any]:
    """Return hypotheses/evidence/tests/decision-impact for this phenomenon."""
    ac = spec.asset_class
    region = spec.region
    equity = ac in ("equity_index", "equity_etf", "sector_equity")
    rates = ac in ("fixed_income", "credit")
    volatility = ac == "volatility"
    fx = ac == "fx"
    commodity = ac == "commodity"
    crypto = ac == "crypto"
    chg = abs(float(ret1m)) if ret1m is not None and np.isfinite(ret1m) else 0.0
    available = available or {}
    cross_ok = bool(available.get("cross_asset"))
    fx_ok = bool(available.get("fx"))
    benchmark_ok = bool(available.get("benchmark"))
    policy_calendar_ok = bool(available.get("policy_calendar"))
    strong_mech = any(s in ("supported", "mixed") for s in mechanism_statuses)
    hyps: list[dict[str, Any]] = []
    tests: list[dict[str, Any]] = []

    def add_local():
        status = "open" if (equity and region != "WORLD") else "untestable"
        ev_for = ([_ev("机制检验支持本地/共同因子", f"mechanisms={mechanism_statuses}",
                       "statistical_association", "mechanism_stats", as_of, "H-LOCAL")]
                  if strong_mech else [])
        ev_against = [_ev("未建立可执行的本地基准对照", "regional benchmark not loaded" if not benchmark_ok
                          else "benchmark available but regression not run", "unknown", "prices",
                          as_of, "H-LOCAL")]
        hyps.append(_h("H-LOCAL", f"{region} 本地市场/区域风险因子", "global_risk", status,
                       "本地基准与全球因子应能解释大部分变动；剔除后残差应显著缩小。",
                       ev_for, ev_against))
        if status == "open":
            tests.append(_test("H-LOCAL", "对本地基准与全球因子回归后的残差", "|residual z| < 1.5",
                               "prices/regional benchmark",
                               "available" if benchmark_ok else "obtainable"))

    def add_global():
        status = "open" if (equity or fx or commodity or crypto or rates) else "untestable"
        ev_for = ([_ev("单月变动达到可检验幅度", f"1m={chg:.1%}", "observed_fact", "prices", as_of,
                       "H-GLOBAL")] if chg >= 0.03 else [])
        ev_against = [_ev("未提供同日跨资产横截面", "no same-day cross-asset sample", "unknown",
                          "cross_asset", as_of, "H-GLOBAL")]
        hyps.append(_h("H-GLOBAL", "全球共同风险/美元流动性冲击", "global_risk", status,
                       "同日股票、信用、商品和美元应同向；控制全球因子后本地残差消失。",
                       ev_for, ev_against))
        if status == "open":
            tests.append(_test("H-GLOBAL", "同日跨资产 beta 与残差", "R² > 0.5 且残差 |z|<1.5",
                               "cross_asset", "available" if cross_ok else "obtainable"))

    def add_fundamental(label: str = "基本面/盈利预期变化"):
        hyps.append(_h("H-FUND", label, "fundamental", "untestable",
                       "盈利修正/现金流预期应领先或同步；需要一致预期或财报数据。",
                       [], [_ev("一致预期/财报修正未接入", "cannot test directly", "unknown",
                                "data_gap", as_of, "H-FUND")]))

    def add_policy(label: str):
        status = "open" if region in POLICY_REGIONS else "untestable"
        hyps.append(_h("H-POLICY", label, "policy", status,
                       "政策路径/事件应改变利率或风险溢价；事件前后应出现可定位的重新定价。",
                       [_ev("区域属于政策敏感市场", region, "observed_fact", "config", as_of, "H-POLICY")]
                       if status == "open" else [],
                       [_ev("没有可核验的决议/公告时点", "event date unknown", "unknown",
                            "calendar", as_of, "H-POLICY")]))
        if status == "open":
            tests.append(_test("H-POLICY", "事件窗口前后的利率/资产反应", "event-window abnormal return > 2σ",
                               "policy calendar/rates",
                               "available" if policy_calendar_ok else "obtainable"))

    def add_positioning():
        usable = positioning_value is not None and np.isfinite(positioning_value)
        hyps.append(_h("H-POS", "仓位/资金流驱动的技术性移动", "positioning_flow",
                       "open" if usable else "untestable",
                       "CFTC/资金流极端仓位应随后均值回归；价格变动应集中在拥挤方向。",
                       [_ev("仓位分位可用", f"percentile={positioning_value}", "observed_fact", "CFTC",
                            as_of, "H-POS")] if usable else [],
                       [_ev("仓位极端程度不足或缺失", "neutral/unknown", "unknown", "CFTC", as_of,
                            "H-POS")]))
        if usable:
            tests.append(_test("H-POS", "CFTC 净头寸分位与随后 4 周反转", ">90% or <10%, reversal >1σ",
                               "CFTC", "available"))

    def add_artifact():
        status = "open" if (crypto or has_price_issue or
                            getattr(spec, "is_futures", False)) else "untestable"
        hyps.append(_h("H-ART", "数据伪影（换月/拆股/盘中/陈旧）", "data_artifact", status,
                       "原始合约/拆分调整/抓取时点应能解释跳变；清洗后异常应消失。",
                       [_ev("资产存在换月/拆股/数据质量风险", ac, "observed_fact", "data_quality",
                            as_of, "H-ART")] if status == "open" else [],
                       [_ev("未记录价格清洗问题", "no price_data_issue", "observed_fact",
                            "data_quality", as_of, "H-ART")]))
        if status == "open":
            tests.append(_test("H-ART", "核对原始合约/复权因子/抓取时点", "raw series reconciles",
                               "exchange/provider", "obtainable"))

    if equity:
        if ac == "sector_equity":
            hyps += [
                _h("H-SECTOR", f"{spec.name} 行业相对基本面/需求", "fundamental", "untestable",
                   "行业相对盈利/需求应领先；需要行业一致预期与需求数据。",
                   [], [_ev("行业盈利/需求数据未接入", "sector fundamentals missing", "unknown",
                            "data_gap", as_of, "H-SECTOR")]),
                _h("H-STYLE", "利率/风格因子驱动的相对表现", "risk_premium", "open",
                   "利率上行应压制长久期成长行业；相对基准的利率 beta 应显著。",
                   [_ev("利率与相对强弱可观察", f"1m={chg:.1%}", "observed_fact", "prices", as_of, "H-STYLE")],
                   [_ev("未估计行业利率 beta", "beta not estimated", "unknown", "derived", as_of, "H-STYLE")]),
                _h("H-GLOBAL", "全球风险/行业轮动", "global_risk", "open",
                   "同日防御/周期行业应反向；相对表现应由共同因子解释。",
                   [_ev("行业相对表现可观察", f"1m={chg:.1%}", "observed_fact", "prices", as_of, "H-GLOBAL")],
                   [_ev("没有同日行业横截面", "no sector cross-section", "unknown", "cross_asset", as_of, "H-GLOBAL")]),
                _h("H-POS", "仓位/资金流拥挤", "positioning_flow",
                   "open" if positioning_value is not None else "untestable",
                   "拥挤行业应出现反转；ETF 资金流与相对表现背离。",
                   [_ev("仓位分位", str(positioning_value), "observed_fact", "CFTC", as_of, "H-POS")]
                   if positioning_value is not None else [],
                   [_ev("行业资金流未接入", "sector flows missing", "unknown", "data_gap", as_of, "H-POS")]),
            ]
            tests += [_test("H-STYLE", "相对基准的利率 beta", "beta significant and sign consistent",
                            "local rates" if region != "US" else "UST",
                            "available" if region == "US" else "obtainable"),
                      _test("H-GLOBAL", "行业多空对全球因子回归", "residual |z|<1.5", "cross_asset",
                            "available" if cross_ok else "obtainable")]
            if positioning_value is not None:
                tests.append(_test("H-POS", "ETF/CFTC 仓位与反转", ">90% or <10%", "CFTC/flows"))
            decision = {"if_true": "若利率/风格解释成立，研究久期与行业相对价值；若全球风险解释成立，研究防御/周期切换。",
                        "if_false": "若相对表现无法由风格/风险解释，保留为待验证的行业基本面问题。"}
            unknowns = ["行业一致预期/需求", "ETF 资金流", "行业利率 beta"]
            case = "sector_equity"
        elif ac == "equity_etf" and region in ("US", "WORLD"):
            add_global()
            hyps.append(_h("H-RATES", "美国利率/估值折现率", "risk_premium", "open",
                           "实际利率上行应压制高估值成长；利率 beta 应显著。",
                           [_ev("利率与估值代理可观察", "UST", "observed_fact", "curve", as_of, "H-RATES")],
                           [_ev("未估计实时利率 beta", "beta not estimated", "unknown", "derived", as_of, "H-RATES")]))
            tests.append(_test("H-RATES", "利率 beta 与估值分位", "beta significant", "UST/valuation"))
            add_fundamental(f"{region} 盈利/估值预期变化")
            add_positioning()
            add_artifact()
            if region == "WORLD":
                hyps.append(_h("H-USD", "美元/新兴市场资金流", "global_risk", "open",
                               "美元走强应压制 EM；USD 与相对表现负相关。",
                               [_ev("DXY 可观察", "DXY", "observed_fact", "prices", as_of, "H-USD")],
                               [_ev("未做美元 beta", "not estimated", "unknown", "derived", as_of, "H-USD")]))
                tests.append(_test("H-USD", "美元 beta", "negative and significant", "DXY"))
            decision = {"if_true": "若利率/全球风险解释成立，研究久期与风格暴露；若盈利解释成立，交 B 做估值/盈利研究。",
                        "if_false": "若均被证伪，保留为市场情报，不升级为研究候选。"}
            unknowns = ["盈利修正/估值", "风格与利率 beta", "资金流"]
            case = "us_equity_etf"
        else:
            add_local()
            add_global()
            add_fundamental(f"{region} 盈利/基本面预期变化")
            add_policy("本地政策/监管冲击")
            if region in ("JP", "EA", "UK", "CN"):
                hyps.append(_h("H-FX", "本地汇率/资金流", "global_risk", "open",
                               "本币贬值应压制本地股票（外币投资者视角）；汇率与股市同向。",
                               [_ev("本地汇率可观察", "local FX", "observed_fact", "prices", as_of, "H-FX")],
                               [_ev("未做汇率 beta", "not estimated", "unknown", "derived", as_of, "H-FX")]))
                tests.append(_test("H-FX", "本币汇率 beta", "sign consistent", "local FX",
                                   "available" if fx_ok else "obtainable"))
            add_positioning()
            add_artifact()
            decision = {"if_true": "若本地/汇率/政策解释成立，研究本地风险与对冲；若全球解释成立，研究 beta。",
                        "if_false": "若竞争解释被证伪，保留为市场情报并等待新证据，不宣称错误定价。"}
            unknowns = ["本地一致预期/盈利修正", "汇率/资金流", "政策决议精确时点"]
            case = "country_equity"
    elif volatility:
        add_global()
        hyps += [
            _h("H-VOL", "波动率/风险溢价状态变化", "risk_premium", "open",
               "波动率应均值回归；期限结构/实现波动与隐含波动的关系应可检验。",
               [_ev("波动率指数出现变化", f"1m={chg:.1%}", "observed_fact", "prices", as_of, "H-VOL")],
               [_ev("缺少 VIX 期限结构与期权隐含分布", "term structure missing", "unknown",
                    "data_gap", as_of, "H-VOL")]),
            _h("H-POS", "仓位/波动率交易拥挤", "positioning_flow",
               "open" if positioning_value is not None else "untestable",
               "VIX 期货/期权仓位极端应预示反转；需要持仓与期权数据。",
               [_ev("仓位分位", str(positioning_value), "observed_fact", "CFTC", as_of, "H-POS")]
               if positioning_value is not None else [],
               [_ev("VIX 仓位/期权数据缺失", "vix positioning missing", "unknown", "data_gap", as_of, "H-POS")]),
        ]
        tests += [_test("H-VOL", "VIX 均值回归/期限结构", "term structure sign consistent", "VIX term", "obtainable")]
        if positioning_value is not None:
            tests.append(_test("H-POS", "VIX 期货/期权仓位反转", ">90% or <10%", "CFTC/options"))
        add_artifact()
        decision = {"if_true": "若波动率状态解释成立，研究波动率风险溢价与期限结构。",
                    "if_false": "若无稳定关系，保留为市场情报，不宣称错误定价。"}
        unknowns = ["VIX 期限结构", "期权隐含分布", "波动率仓位"]
        case = "volatility"
    elif rates:
        hyps += [
            _h("H-REAL", "实际利率/通胀预期变化", "fundamental", "open",
               "实际利率与盈亏平衡通胀应同向变化；名义利率分解应解释。",
               [_ev("名义利率变动可观察", f"1m={chg:.1%}", "observed_fact", "prices", as_of, "H-REAL")],
               [_ev("缺少实时盈亏平衡通胀", "local breakeven unavailable", "unknown", "data_gap", as_of, "H-REAL")]),
            _h("H-TERM", "期限溢价/财政供给冲击", "risk_premium", "open",
               "曲线斜率与拍卖/供给应共同变化；短端稳定而长端移动。",
               [_ev("本地曲线水平可观察", f"{region} curve", "observed_fact", "curve", as_of, "H-TERM")],
               [_ev("拍卖/财政供给数据未接入", "auction data missing", "unknown", "data_gap", as_of, "H-TERM")]),
            _h("H-POL", "货币政策路径重新定价", "policy", "open",
               "政策利率预期与短端应领先；事件窗口反应集中。",
               [_ev("区域政策利率序列可用", f"{region} policy rate", "observed_fact", "macro", as_of, "H-POL")],
               [_ev("市场隐含政策路径缺失", "OIS missing", "unknown", "data_gap", as_of, "H-POL")]),
        ]
        tests += [_test("H-REAL", "实际利率/通胀分解", "sign consistent 60d",
                        "local TIPS/breakeven" if region == "US" else "local inflation swaps", "obtainable"),
                  _test("H-TERM", "本地曲线斜率与长端拍卖", "2s10s move > 2σ", "local curve/auction", "available"),
                  _test("H-POL", "短端与本地政策利率预期", "short-end leads", "local policy path", "available")]
        decision = {"if_true": "若实际利率/期限溢价解释成立，研究久期与曲线交易，而非方向性信用判断。",
                    "if_false": "若政策路径解释成立，交 B 评估利率路径与久期风险。"}
        unknowns = ["实时盈亏平衡通胀", "拍卖/财政供给", "OIS 政策路径"]
        case = "rates"
    elif fx:
        hyps += [
            _h("H-CARRY", "利差/套息交易驱动", "risk_premium", "open",
               "两国利差与汇率应同向；风险厌恶上升时高息货币走弱。",
               [_ev("汇率变动可观察", f"1m={chg:.1%}", "observed_fact", "prices", as_of, "H-CARRY")],
               [_ev("缺少完整两国利率曲线", "foreign curve missing", "unknown", "data_gap", as_of, "H-CARRY")]),
            _h("H-RISK", "全球风险偏好/美元避险", "global_risk", "open",
               "VIX/信用利差与美元应同向；风险资产下跌时美元走强。",
               [_ev("VIX/信用代理可观察", "VIX/CREDIT_RISK", "observed_fact", "derived", as_of, "H-RISK")],
               [_ev("未做同日横截面", "no same-day cross-section", "unknown", "cross_asset", as_of, "H-RISK")]),
            _h("H-INT", "央行干预/政策防线", "policy", "open" if region in ("JP", "CN") else "untestable",
               "干预时点应伴随官方储备/口头指引；汇率在关口附近反转。",
               [_ev("区域有干预历史/政策敏感", region, "observed_fact", "config", as_of, "H-INT")]
               if region in ("JP", "CN") else [],
               [_ev("干预数据不可得", "intervention data missing", "unknown", "data_gap", as_of, "H-INT")]),
            _h("H-POS", "仓位/资金流的技术性反转", "positioning_flow",
               "open" if positioning_value is not None else "untestable",
               "CFTC 极端仓位应先于反转；现货与期货持仓背离。",
               [_ev("CFTC 分位", str(positioning_value), "observed_fact", "CFTC", as_of, "H-POS")]
               if positioning_value is not None else [],
               [_ev("仓位缺失/中性", "unknown", "unknown", "CFTC", as_of, "H-POS")]),
        ]
        tests += [_test("H-CARRY", "利差变化与汇率", "sign consistent", "policy rates", "obtainable"),
                  _test("H-RISK", "VIX/信用与美元", "corr > 0.4", "cross_asset",
                        "available" if cross_ok else "obtainable"),
                  _test("H-INT", "关口/储备变化", "official reserves drop", "reserves", "obtainable")]
        if positioning_value is not None:
            tests.append(_test("H-POS", "CFTC 分位反转", ">90% or <10%", "CFTC"))
        decision = {"if_true": "若利差/风险解释成立，研究 carry 或避险对冲；若干预解释成立，研究政策防线。",
                    "if_false": "若均被证伪，保留为市场情报，等待资金流/政策证据。"}
        unknowns = ["两国利率曲线", "官方干预/储备", "CFTC 分位"]
        case = "fx"
    elif commodity:
        hyps += [
            _h("H-SUPPLY", "供给冲击/库存变化", "fundamental", "untestable",
               "库存、产量或地缘供给应领先价格；曲线 backwardation 加深。",
               [_ev("价格跳变可观察", f"1m={chg:.1%}", "observed_fact", "prices", as_of, "H-SUPPLY")]
               if False else [],
               [_ev("库存/产量数据未接入", "inventory missing", "unknown", "data_gap", as_of, "H-SUPPLY")]),
            _h("H-DEMAND", "全球需求/增长预期", "global_risk", "open",
               "全球增长/工业产出应与商品同向；美元与利率同向确认。",
               [_ev("全球风险代理可观察", "global growth proxies", "observed_fact", "derived", as_of, "H-DEMAND")],
               [_ev("没有工业产出/PMI 实时数据", "PMI missing", "unknown", "data_gap", as_of, "H-DEMAND")]),
            _h("H-USD", "美元/实际利率计价效应", "risk_premium", "open",
               "美元与实际利率应负向解释黄金/商品；控制后残差下降。",
               [_ev("DXY/UST 可用", "DXY, UST", "observed_fact", "prices", as_of, "H-USD")],
               [_ev("未做实时回归", "regression not run", "unknown", "derived", as_of, "H-USD")]),
            _h("H-ART", "换月/连续合约数据伪影" if getattr(spec, "is_futures", False)
               else "拆股/盘中/陈旧数据伪影", "data_artifact",
               "open" if (getattr(spec, "is_futures", False) or crypto or has_price_issue) else "untestable",
               "换月日附近跳变；原始合约与连续合约不一致。",
               [_ev("连续合约存在换月风险", "futures", "observed_fact", "data_quality", as_of, "H-ART")]
               if (getattr(spec, "is_futures", False) or crypto or has_price_issue) else [],
               [_ev("未记录换月/清洗问题", "no issue recorded", "observed_fact", "data_quality", as_of, "H-ART")]),
        ]
        tests += [_test("H-DEMAND", "全球增长代理与商品", "corr > 0.3", "cross_asset",
                        "available" if cross_ok else "obtainable"),
                  _test("H-USD", "美元/实际利率回归", "residual |z|<1.5", "DXY/UST",
                        "available" if cross_ok else "obtainable")]
        if getattr(spec, "is_futures", False) or crypto or has_price_issue:
            tests.append(_test("H-ART", "原始合约对账", "reconciles", "exchange", "obtainable"))
        decision = {"if_true": "若供给解释成立，研究库存/地缘情景；若美元解释成立，研究计价与对冲。",
                    "if_false": "若均不成立，保留为待验证情报，不直接做方向性判断。"}
        unknowns = ["库存/产量", "工业产出/PMI", "换月因子"]
        case = "commodity"
    elif crypto:
        hyps += [
            _h("H-LIQ", "全球流动性/风险偏好", "global_risk", "open",
               "美元流动性、VIX 与加密资产应同向；风险资产同步。",
               [_ev("风险代理可用", "VIX/DXY", "observed_fact", "prices", as_of, "H-LIQ")],
               [_ev("没有稳定币/链上流动性数据", "on-chain missing", "unknown", "data_gap", as_of, "H-LIQ")]),
            _h("H-REG", "监管/政策冲击", "policy", "untestable",
               "监管公告应伴随事件窗口跳变；需要精确公告时点。",
               [], [_ev("监管事件时点未接入", "event data missing", "unknown", "calendar", as_of, "H-REG")]),
            _h("H-FLOW", "交易所/ETF 资金流", "positioning_flow", "untestable",
               "ETF 流入流出应领先价格；需要日度流量。",
               [], [_ev("ETF 流量未接入", "flow data missing", "unknown", "data_gap", as_of, "H-FLOW")]),
            _h("H-ART", "交易所/稳定币数据伪影", "data_artifact", "open",
               "交易所价差异常/稳定币脱锚；清洗后消失。",
               [_ev("24/7 市场存在交易所差异", "crypto", "observed_fact", "data_quality", as_of, "H-ART")],
               [_ev("未记录交易所价差", "no issue recorded", "unknown", "data_quality", as_of, "H-ART")]),
        ]
        tests += [_test("H-LIQ", "风险代理与加密", "corr > 0.4", "cross_asset",
                        "available" if cross_ok else "obtainable"),
                  _test("H-ART", "交易所价差/稳定币", "reconciles", "exchange", "obtainable")]
        decision = {"if_true": "若流动性解释成立，研究风险 beta；若数据伪影成立，先修数据。",
                    "if_false": "保留为情报，不升级为研究候选。"}
        unknowns = ["链上流动性", "监管时点", "ETF 流量"]
        case = "crypto"
    else:
        add_global()
        add_fundamental()
        add_positioning()
        add_artifact()
        decision = {"if_true": "若全球/基本面解释成立，交 B 进一步研究。",
                    "if_false": "证据不足，保留为市场情报。"}
        unknowns = ["一致预期", "仓位", "数据质量"]
        case = "other"

    # Give each phenomenon its own hypothesis namespace and one case-specific driver.
    if equity:
        if ac == "sector_equity":
            code = "SEC" + "".join(w[0] for w in spec.name.split()[:2]).upper()
        elif region in ("US", "WORLD"):
            code = "USEQ"
        else:
            code = "EQ" + str(region)
    elif rates:
        code = "RT" + str(region)
    elif volatility:
        code = "VOL"
    elif fx:
        code = "FX" + str(region)
    elif commodity:
        n = spec.name.lower()
        role = str(getattr(spec, "role", "") or "").lower()
        code = "GOLD" if "gold" in n else ("SILV" if "silver" in n or "slv" in n else
               ("AGRI" if (role == "agriculture" or any(x in n for x in ("wheat", "sugar", "corn", "soy", "cattle"))) else "ENER"))
    elif crypto:
        code = "CRYPTO"
    else:
        code = "OTHER"
    prefix = f"H-{code}"
    if commodity:
        n = spec.name.lower()
        if "gold" in n:
            extra = _h(prefix + "-REAL", "黄金：实际利率/美元计价", "risk_premium", "open",
                       "实际利率下行与美元走弱应支撑黄金；控制后残差下降。",
                       [_ev("实际利率/美元可观察", "UST/DXY", "observed_fact", "prices", as_of, prefix + "-REAL")],
                       [_ev("未做实时回归", "regression not run", "unknown", "derived", as_of, prefix + "-REAL")])
            extra_test = _test(prefix + "-REAL", "实际利率与美元回归", "residual |z|<1.5", "UST/DXY", "available")
        elif "silver" in n or "slv" in n:
            extra = _h(prefix + "-INDUSTRIAL", "白银：工业需求/金银比", "fundamental", "open",
                       "工业需求与金银比应解释白银；需要工业产出/ETF 流量。",
                       [_ev("金银比可观察", "gold/silver ratio", "observed_fact", "prices", as_of, prefix + "-INDUSTRIAL")],
                       [_ev("工业需求/ETF 流量缺失", "industrial/flows missing", "unknown", "data_gap", as_of, prefix + "-INDUSTRIAL")])
            extra_test = _test(prefix + "-INDUSTRIAL", "金银比与工业需求代理", "corr > 0.3", "gold/industrial", "obtainable")
        elif (str(getattr(spec, "role", "")).lower() == "agriculture"
              or any(x in n for x in ("wheat", "sugar", "corn", "soy", "cattle"))):
            extra = _h(prefix + "-WEATHER", "农产品：天气/供给冲击", "fundamental", "untestable",
                       "天气/产量数据应领先；需要产区降雨/库存。",
                       [], [_ev("天气/库存数据缺失", "weather/inventory missing", "unknown", "data_gap", as_of, prefix + "-WEATHER")])
            extra_test = None
        else:
            extra = _h(prefix + "-CRACK", "能源：炼厂利润/供给", "fundamental", "open",
                       "裂解价差与库存应解释；需要炼厂利润/库存。",
                       [_ev("能源价格可观察", f"1m={chg:.1%}", "observed_fact", "prices", as_of, prefix + "-CRACK")],
                       [_ev("裂解价差/库存缺失", "crack/inventory missing", "unknown", "data_gap", as_of, prefix + "-CRACK")])
            extra_test = _test(prefix + "-CRACK", "裂解价差与库存", "sign consistent", "crack/inventory", "obtainable")
        hyps.append(extra)
        if extra_test:
            tests.append(extra_test)
    # remap all IDs to the phenomenon namespace
    idmap = {h["id"]: f"{prefix}-{h['id'][2:]}" for h in hyps}
    for h in hyps:
        h["id"] = h["id"] if h["id"].startswith(prefix + "-") else idmap[h["id"]]
        for e in h["evidence_for"] + h["evidence_against"]:
            if e.get("hypothesis_id"):
                e["hypothesis_id"] = (e["hypothesis_id"] if e["hypothesis_id"].startswith(prefix + "-")
                                      else idmap.get(e["hypothesis_id"], e["hypothesis_id"]))
    for t in tests:
        t["hypothesis_id"] = (t["hypothesis_id"] if t["hypothesis_id"].startswith(prefix + "-")
                              else idmap.get(t["hypothesis_id"], t["hypothesis_id"]))

    open_hyps = [h for h in hyps if h["status"] == "open"]
    open_ids = {h["id"] for h in open_hyps}
    tests = [t for t in tests if t["hypothesis_id"] in open_ids]
    usable = [t for t in tests if t.get("data_status") in ("available", "obtainable")]
    available_tests = [t for t in usable if t.get("data_status") == "available"]
    # a research candidate needs >=2 explanations and >=2 distinguishable tests,
    # at least one using data available today (not only a future data request)
    discriminating = bool(len(open_ids) >= 2
                          and len({t["hypothesis_id"] for t in usable}) >= 2
                          and len(available_tests) >= 1)
    return {"case": case, "hypotheses": hyps, "tests": tests,
            "open_count": len(open_hyps), "discriminating": discriminating,
            "decision_impact": decision, "unknowns": unknowns,
            "has_untestable": any(h["status"] == "untestable" for h in hyps)}
