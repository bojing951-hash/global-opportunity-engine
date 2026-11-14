# 历史案例验证（时点回放）

- 生成时间：2026-11-14T06:30:37Z
- 方法：point-in-time feature build; macro release lag applied; detection not profitability
- 通过：7 / 7

| 案例 | 结果 | 命中检测器 | 相关候选 | 机制状态 | 窗口异常数 |
|---|---|---|---|---|---|
| 2020 年 3 月全球风险资产崩跌 | ✅ PASS | drawdown_extreme、price_return_shock、vol_regime_shift | 信用利差与股票风险溢价 Credit spreads versus equity(watch)；SPDR S&P 500 ETF：多头拥挤且已出现浮亏（去杠杆风险） — 仓位极(deep_research)；美国 SPDR S&P 500 ETF：价格下行与估值/信用/风险溢价信号不一致(watch) | M10_CREDIT_SPREADS_EQUITY_RISK=mixed；M12_VIX_TERM_STRUCTURE=mixed | 884 |
| 2022 年美联储加息与股债双杀 | ✅ PASS | curve_change、drawdown_extreme、vol_regime_shift | 信用利差与股票风险溢价 Credit spreads versus equity(watch)；美国 政策变化后的重定价：SPDR S&P 500 ETF（US_POLICY_(watch)；SPDR S&P 500 ETF：过度悲观 — 仓位极值 + 价格异常（待检验的(watch) | M01_REAL_RATES_USD_ALLOCATION=unsupported；M11_CURVE_BANK_PROFITABILITY=unsupported | 2172 |
| 2022 年 9 月英国国债/养老金 LDI 冲击 | ✅ PASS | price_return_shock、vol_regime_shift | 英国 政策变化后的重定价：iShares MSCI United Kingdom(low_priority) | M01_REAL_RATES_USD_ALLOCATION=unsupported | 473 |
| 2023 年 3 月美国区域银行事件 | ✅ PASS | credit_stress | VIX 期限结构与波动状态 VIX term structure and vol(low_priority)；美国 政策变化后的重定价：Financial Select Sector SPD(low_priority) | M10_CREDIT_SPREADS_EQUITY_RISK=mixed | 296 |
| 2024 年 8 月日元套息交易平仓 | ✅ PASS | price_return_shock、relative_strength_extreme、vol_regime_shift | 日本 政策变化后的重定价：Nikkei 225（JP_POLICY_RATE h(watch)；日元套息交易与全球去杠杆 Japan carry trade and globa(watch) | M14_JAPAN_CARRY_UNWIND=unsupported | 473 |
| 2024 年 9 月中国政策转向与股市急涨 | ✅ PASS | price_return_shock、relative_strength_extreme | 中国 政策变化后的重定价：CSI 300 Index（CN_POLICY_RAT(watch)；中国政策与港股科技 China policy to Hong Kong tech(watch) | M04_CHINA_POLICY_HK_TECH=unsupported | 545 |
| 2025 年黄金与实际利率/美元的关系变化 | ✅ PASS | price_return_shock | 黄金与实际利率 Gold versus real yields：历史传导关系失效(watch) | M02_GOLD_REAL_YIELD=unsupported | 2378 |

> 通过标准：窗口内至少命中一个预期检测器（或异常家族），**且**受影响资产在该时点生成了候选机会。机制状态单列报告：机制被证伪（unsupported）是有效的负面研究结论，不计为检测失败。该验证衡量“能否发现值得研究的现象”，不衡量投资收益。
