# 历史案例验证（时点回放）

- 生成时间：2026-11-13T15:28:49Z
- 方法：point-in-time feature build; macro release lag applied; detection not profitability
- 通过：7 / 7

| 案例 | 结果 | 命中检测器 | 相关候选 | 机制状态 | 窗口异常数 |
|---|---|---|---|---|---|
| 2020 年 3 月全球风险资产崩跌 | ✅ PASS | drawdown_extreme、price_return_shock、vol_regime_shift | SPDR S&P 500 ETF：多头拥挤且已出现浮亏（去杠杆风险） — 仓位极(deep_research)；黄金与实际利率 Gold versus real yields：COMEX Go(watch)；信用利差与股票风险溢价 Credit spreads versus equity(watch) | M10_CREDIT_SPREADS_EQUITY_RISK=mixed；M12_VIX_TERM_STRUCTURE=mixed | 1168 |
| 2022 年美联储加息与股债双杀 | ✅ PASS | curve_change、drawdown_extreme、vol_regime_shift | SPDR S&P 500 ETF：过度悲观 — 仓位极值 + 价格异常（待检验的(deep_research)；美国 SPDR S&P 500 ETF：价格下行与估值/信用/风险溢价信号不一致(deep_research)；能源—通胀—利润率—股债 Energy to inflation to marg(deep_research) | M01_REAL_RATES_USD_ALLOCATION=supported；M11_CURVE_BANK_PROFITABILITY=weak | 3074 |
| 2022 年 9 月英国国债/养老金 LDI 冲击 | ✅ PASS | price_return_shock、vol_regime_shift | 实际利率—美元—全球配置 Real rates, the dollar and (watch)；实际利率—美元—全球配置 Real rates, the dollar and (watch)；信用利差与股票风险溢价 Credit spreads versus equity(watch) | M01_REAL_RATES_USD_ALLOCATION=supported | 562 |
| 2023 年 3 月美国区域银行事件 | ✅ PASS | credit_stress、drawdown_extreme、vol_regime_shift | VIX 期限结构与波动状态 VIX term structure and vol(watch)；美国 Financial Select Sector SPDR：价格下行与估值/(watch)；实际利率—美元—全球配置 Real rates, the dollar and (low_priority) | M10_CREDIT_SPREADS_EQUITY_RISK=mixed | 582 |
| 2024 年 8 月日元套息交易平仓 | ✅ PASS | price_return_shock、relative_strength_extreme、vol_regime_shift | 日本 Nikkei 225：价格下行与全球信用/风险偏好/广度信号不一致（待检验(watch)；CBOE Volatility Index：过度乐观 — 仓位极值 + 价格异常(watch)；VIX 期限结构与波动状态 VIX term structure and vol(watch) | M14_JAPAN_CARRY_UNWIND=unsupported | 837 |
| 2024 年 9 月中国政策转向与股市急涨 | ✅ PASS | price_return_shock、relative_strength_extreme | 中国香港 Hang Seng Index：价格下行与政策/利率/信用信号不一致（(deep_research)；中国 Huatai-PB CSI300 ETF：价格下行与政策/利率/信用信号不(watch)；中国香港 CSOP Hang Seng TECH ETF：价格下行与政策/利率/(watch) | M04_CHINA_POLICY_HK_TECH=unsupported | 849 |
| 2025 年黄金与实际利率/美元的关系变化 | ✅ PASS | cross_asset_divergence、price_return_shock | 能源—通胀—利润率—股债 Energy to inflation to marg(low_priority) | M02_GOLD_REAL_YIELD=mixed | 4847 |

> 通过标准：窗口内至少命中一个预期检测器（或异常家族），**且**受影响资产在该时点生成了候选机会。机制状态单列报告：机制被证伪（unsupported）是有效的负面研究结论，不计为检测失败。该验证衡量“能否发现值得研究的现象”，不衡量投资收益。
