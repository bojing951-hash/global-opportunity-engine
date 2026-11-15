# Research Dossier RD-RC-20261113-US_EQ_QQQ-ed67c9acfee9

- Research ID: `RC-20261113-US_EQ_QQQ-ed67c9acfee9`
- Research Theme: `RT-26fd92f4b393b82c`
- Decision as-of: `2026-11-13`
- Market / Assets: US / US_EQ_QQQ
- Case: CASE_C_EVIDENCE_GAP

## 1. Observed Facts

- **利率与估值代理可观察**: UST _(source: curve, available: 2026-11-13)_

## 2. Why This Matters

- **materiality**: `{"level": 2, "importance": 0.95, "anomaly_score": 0.12537393433190536, "return_1m": -0.05594351960212729, "gap_score": 0.328, "gap_level": 2, "mechanism_conflict": true, "distinguishability_level": 0, "decision_impact_level": 2, "has_change": true}`
- **decision_relevance**: `{"if_true": "若利率/全球风险解释成立，研究久期与风格暴露；若盈利解释成立，交 B 做估值/盈利研究。", "if_false": "若均被证伪，保留为市场情报，不升级为研究候选。"}`
- **observed_phenomenon**: Invesco QQQ (Nasdaq 100) 近期 price_return_shock（up，分数 0.13）；1 个月收益 -5.6%；回撤分位 0.29。

## 3. Research Question

What explains: Invesco QQQ (Nasdaq 100) 近期 price_return_shock（up，分数 0.13）；1 个月收益 -5.6%；回撤分位 0.29。

## 4. Competing Hypotheses

- **全球共同风险/美元流动性冲击**: 同日股票、信用、商品和美元应同向；控制全球因子后本地残差消失。
- **美国利率/估值折现率**: 实际利率上行应压制高估值成长；利率 beta 应显著。
- **US 盈利/估值预期变化**: 盈利修正/现金流预期应领先或同步；需要一致预期或财报数据。
- **仓位/资金流驱动的技术性移动**: CFTC/资金流极端仓位应随后均值回归；价格变动应集中在拥挤方向。
- **数据伪影（换月/拆股/盘中/陈旧）**: 原始合约/拆分调整/抓取时点应能解释跳变；清洗后异常应消失。

## 5. Different Predictions

- 同日股票、信用、商品和美元应同向；控制全球因子后本地残差消失。
- 实际利率上行应压制高估值成长；利率 beta 应显著。
- 盈利修正/现金流预期应领先或同步；需要一致预期或财报数据。
- CFTC/资金流极端仓位应随后均值回归；价格变动应集中在拥挤方向。
- 原始合约/拆分调整/抓取时点应能解释跳变；清洗后异常应消失。

## 6. Supporting Evidence

_None recorded._

## 7. Contradicting Evidence

- **全球因子解释力不足**: R²=0.38 < 0.50; residual_z=1.12 _(source: derived/cross_asset, available: 2026-11-13)_
- **一致预期/财报修正未接入**: cannot test directly _(source: data_gap, available: 2026-11-13)_
- **未记录价格清洗问题**: no price_data_issue _(source: data_quality, available: 2026-11-13)_

## 8. Critical Unknowns

- 盈利修正/估值
- 风格与利率 beta
- 资金流

## 9. Evidence Acquisition Plan

- 接入带 publication_time/vintage 的 consensus CSV；先补历史版本，不能回填
- 明确数据源、发布日期与可得时点：风格与利率 beta
- 使用 CFTC/ETF 资金流并检查发布日期

## 10. Falsification Conditions

- **同日跨资产 beta 与残差**: R² > 0.5 且残差 |z|<1.5
- **利率 beta 与估值分位**: beta significant

## 11. Research Worthiness

- **rating**: medium
- **rationale**: tier intelligence: case=us_equity_etf, materiality L2, gap L2, distinguishability L0, impact L2, open_hypotheses=2, discriminating=0, worthiness=medium, evidence=missing, cost=10h

## 12. Evidence Readiness

- **rating**: missing
- **research_readiness**: evidence_gap
- **measured_note**: Only measured, discriminating evidence counts; availability notes do not.

## 13. Research Cost

- **hours**: 10
- **data_access**: medium

## 14. Next Research Action

Collect the listed evidence / wait for the stated trigger; do not hand off yet

## 15. B Capability / Handoff

- **supported**: False
- **kind**: deep_asset_research_unsupported
- **reason**: B is a macro fact workbench, not a general equity/sector/commodity valuation or mispricing engine; keep in A
- **eligibility**: a_retained
- **research_queue**: watch
- **tier**: intelligence

## 16. Result / Open Questions

- **result**: NOT_EXECUTED
- **open_questions**: `["盈利修正/估值", "风格与利率 beta", "资金流"]`
- **learned**: No research result is claimed; unresolved unknowns remain explicit.

## 17. Independent Quality Review

- **status**: NOT_INDEPENDENTLY_REVIEWED
- **note**: No human/expert review was performed for this dossier. Do not treat the dossier as validated research value.

## 18. Source & Version References

- **artifact_path**: evaluation/v2_candidates_20_2026-11-13.json
- **scan_id**: scan-20261115T044634Z-b68802
- **config_hash**: 7d4d8ae1a7ca110204f522359f57e8c627c89cdec753eea29b51af4a486fc187
- **data_hash**: 9350b109d05e0131412fc8631a6620eae73072ba17c208271b43b1d384c04054
- **theme_id**: RT-26fd92f4b393b82c
- **evidence_count**: 1
- **source_note**: All evidence retains source and available_at; unavailable facts are unknown.

---
Content SHA-256: `febb763b21c1e642f1715f21bedec3e4b9148156cc2d7cd0d850b85b4a71dfdc`
DISCOVERY VALUE: NOT VALIDATED
