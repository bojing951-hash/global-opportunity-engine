# Research Dossier RD-RC-20261113-US_VOL_VIX-c1092d4e5bea

- Research ID: `RC-20261113-US_VOL_VIX-c1092d4e5bea`
- Research Theme: `RT-bfb7d7f74d4ea817`
- Decision as-of: `2026-11-13`
- Market / Assets: US / US_VOL_VIX
- Case: CASE_B_EXPLAINED

## 1. Observed Facts

- **同日跨资产全球因子回归**: R²=0.47, beta=-11.20, residual_z=-0.34, n=252 _(source: derived/cross_asset)_
- **波动率指数出现变化**: 1m=10.8% _(source: prices)_
- **仓位分位**: 0.07335907335907343 _(source: CFTC)_

## 2. Why This Matters

- **materiality**: `{"level": 2, "importance": 0.9, "anomaly_score": 0.2494478558529104, "return_1m": 0.10847657573615233, "gap_score": 0.0, "gap_level": 0, "mechanism_conflict": false, "distinguishability_level": 0, "decision_impact_level": 1, "has_change": true}`
- **decision_relevance**: `{"if_true": "若波动率状态解释成立，研究波动率风险溢价与期限结构。", "if_false": "若无稳定关系，保留为市场情报，不宣称错误定价。"}`
- **observed_phenomenon**: CBOE Volatility Index 近期 price_return_shock（down，分数 0.25）；1 个月收益 +10.8%；回撤分位 0.74。

## 3. Research Question

What explains: CBOE Volatility Index 近期 price_return_shock（down，分数 0.25）；1 个月收益 +10.8%；回撤分位 0.74。

## 4. Competing Hypotheses

- **全球共同风险/美元流动性冲击**: 同日股票、信用、商品和美元应同向；控制全球因子后本地残差消失。
- **波动率/风险溢价状态变化**: 波动率应均值回归；期限结构/实现波动与隐含波动的关系应可检验。
- **仓位/波动率交易拥挤**: VIX 期货/期权仓位极端应预示反转；需要持仓与期权数据。
- **数据伪影（换月/拆股/盘中/陈旧）**: 原始合约/拆分调整/抓取时点应能解释跳变；清洗后异常应消失。

## 5. Different Predictions

- 同日股票、信用、商品和美元应同向；控制全球因子后本地残差消失。
- 波动率应均值回归；期限结构/实现波动与隐含波动的关系应可检验。
- VIX 期货/期权仓位极端应预示反转；需要持仓与期权数据。
- 原始合约/拆分调整/抓取时点应能解释跳变；清洗后异常应消失。

## 6. Supporting Evidence

- **同日跨资产全球因子回归**: R²=0.47, beta=-11.20, residual_z=-0.34, n=252 _(source: derived/cross_asset)_
- **波动率指数出现变化**: 1m=10.8% _(source: prices)_
- **仓位分位**: 0.07335907335907343 _(source: CFTC)_

## 7. Contradicting Evidence

- **缺少 VIX 期限结构与期权隐含分布**: term structure missing _(source: data_gap)_
- **VIX 仓位/期权数据缺失**: vix positioning missing _(source: data_gap)_
- **未记录价格清洗问题**: no price_data_issue _(source: data_quality)_

## 8. Critical Unknowns

- VIX 期限结构
- 期权隐含分布
- 波动率仓位
- 无法形成两个可区分且可检验的竞争解释

## 9. Evidence Acquisition Plan

- 明确数据源、发布日期与可得时点：VIX 期限结构
- 取得历史期权隐含分布；否则保留为 unknown
- 使用 CFTC/ETF 资金流并检查发布日期
- 明确数据源、发布日期与可得时点：无法形成两个可区分且可检验的竞争解释

## 10. Falsification Conditions

- **VIX 均值回归/期限结构**: term structure sign consistent
- **VIX 期货/期权仓位反转**: >90% or <10%

## 11. Research Worthiness

- **rating**: low
- **rationale**: tier intelligence: case=volatility, materiality L2, gap L0, distinguishability L0, impact L1, open_hypotheses=2, discriminating=0, worthiness=low, evidence=missing, cost=12h

## 12. Evidence Readiness

- **rating**: missing
- **research_readiness**: evidence_gap
- **measured_note**: Only measured, discriminating evidence counts; availability notes do not.

## 13. Research Cost

- **hours**: 12
- **data_access**: medium

## 14. Next Research Action

No further research allocation; retain as market intelligence

## 15. B Capability / Handoff

- **supported**: False
- **kind**: deep_asset_research_unsupported
- **reason**: B is a macro fact workbench, not a general equity/sector/commodity valuation or mispricing engine; keep in A
- **eligibility**: a_retained
- **research_queue**: archive
- **tier**: intelligence

## 16. Result / Open Questions

- **result**: NOT_EXECUTED
- **open_questions**: `["VIX 期限结构", "期权隐含分布", "波动率仓位", "无法形成两个可区分且可检验的竞争解释"]`
- **learned**: No research result is claimed; unresolved unknowns remain explicit.

## 17. Independent Quality Review

- **status**: NOT_INDEPENDENTLY_REVIEWED
- **note**: No human/expert review was performed for this dossier. Do not treat the dossier as validated research value.

## 18. Source & Version References

- **artifact_path**: evaluation/v2_candidates_20_2026-11-13.json
- **scan_id**: scan-20261115T044634Z-b68802
- **config_hash**: 7d4d8ae1a7ca110204f522359f57e8c627c89cdec753eea29b51af4a486fc187
- **data_hash**: 9350b109d05e0131412fc8631a6620eae73072ba17c208271b43b1d384c04054
- **theme_id**: RT-bfb7d7f74d4ea817
- **evidence_count**: 3
- **source_note**: All evidence retains source and available_at; unavailable facts are unknown.

---
Content SHA-256: `3b62b0e21d7992e82d2d2cb4fd449691ec06686f892888a13cb0da63bf2375d5`
DISCOVERY VALUE: NOT VALIDATED
