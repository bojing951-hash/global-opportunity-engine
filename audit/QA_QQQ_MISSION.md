# QA — Research Mission 01（QQQ 相对弱势，2026-11-05）

- 审计对象：`HEAD 553b0f9`（研究代码 `73ef6cb`，254 tests，CI run #51）
- 审计时间：2026-11-16（Asia/Hong_Kong）
- 审计范围：只读核验；除本文件外未修改任何代码/数据/artifact
- 最终状态：**有条件通过（CONDITIONAL PASS）**
- **P0 = 0；P1 = 2；P2 = 4**

---

## 1. 事件真实性、数据、合约与 PIT

### 1.1 数据复核（GOE prices DB，同日收盘）

| Series | 2026-11-04 close | 2026-11-05 close | 计算收益 | 任务声明 | 结论 |
|---|---:|---:|---:|---:|---|
| QQQ | 691.9500 | 647.0500 | **-6.4908%** | -6.49% | 一致 |
| SPY | 766.8100 | 733.0000 | **-4.4091%** | -4.41% | 一致 |
| VIX | 16.6100 | 28.1800 | **+69.657%** | +69.66% | 一致 |
| IEF | 91.6600 | 91.9700 | **+0.3382%** | +0.34% | 一致 |
| DXY | 101.5100 | 101.5500 | **+0.0394%** | +0.04% | 一致 |
| Gold | 4073.00 | 4113.50 | **+0.9944%** | +0.99% | 一致 |

- QQQ−SPY 相对差：`-6.4908% − (-4.4091%) = -2.0817pp`，与 artifact `-0.020797` 一致。
- 3 日反转：647.05 → 674.76（2026-11-10 收盘）= **+4.2825%**，与 `next_3d=0.042825` 一致。
- **事件为真实数据事件**：不是空值、不是重复行、不是跨越收盘对齐造成的假事件。

### 1.2 Event Contract 持久化与漂移

- `research_v2_event_contracts` 中存在 QQQ 行：
  - `research_id = RC-20261113-US_EQ_QQQ-c6b8c38dbf91`
  - `contract_hash = f31e7f43f8be67b64c0c9f7362258839b3173c10a574f68f91bc332e6e1499f8`
  - `anomaly_id = AN-1821b60c31ae31`
  - `created_at = 2026-11-16 04:37:33`
- 该 hash 与 finding `plan.event_contract.contract_hash` **完全相同**；`event_start/event_end = 2026-11-05`、`direction=underperform`、`detector_id=relative_strength_extreme`、`decision_as_of=2026-11-13` 均一致。
- **无 event drift**：合约是持久化的，DB 行与 finding 内嵌合约一致。

### 1.3 决策时点 / 未来数据

- `decision_as_of = 2026-11-13`；六条同日序列 `data_date` 全部为 `2026-11-05`。
- 反转检验使用 2026-11-06/09/10 收盘，仍 **早于** as-of 2026-11-13。
- DB 中相关序列最新到 2026-11-13；未发现用 as-of 之后数据反推结论。
- 结论：**PIT 合规，无 future data 泄漏**。

---

## 2. 竞争假设、信息增益与过度声称

### 2.1 假设判定（canonical finding：`...-2ca1fb5a`）

| 假设 | artifact 状态 | QA 判断 |
|---|---|---|
| H-RISK（risk-off/flight-to-quality） | `SUPPORTED_BY_AVAILABLE_EVIDENCE` | **成立**：SPY 下跌 + VIX 飙升，且 IEF 上涨，联合 pattern 支持风险规避；不是因果证明 |
| H-RATE（rate/duration shock） | `WEAKENED_BY_EVIDENCE` | **成立**：IEF +0.34%（收益率下行）与“简单利率上行冲击”方向相反；但 IEF 只是久期代理，不能排除盘中/实际利率/信用渠道，用“weakened”准确 |
| H-TECH（成长/科技特异性 de-rating） | `SUPPORTED_BY_AVAILABLE_EVIDENCE` | **观察成立、机制未分离**：QQQ 相对弱势是事实；但没有行业/成分/盘中数据，不能把“相对弱势”升级为“科技特异性 de-rating”的机制证据。finding 的 note 已限定，但 intel 摘要丢失限定（见 P2-1） |
| H-DATA（数据/指数构造 artifact） | `INSUFFICIENT_DATA` | **成立**：没有发现 roll/价格异常，但“没发现”不等于“证明干净”，标为数据不足而非排除，正确 |

- finding `status = INCONCLUSIVE`，`still_unknown` 含 4 项（盘中领导/行业宽度、隐含利率/期权分布、盈利修正、仓位）。**满足“INCONCLUSIVE + learned/unknowns”要求**。

### 2.2 相对简单 anomaly screen 的信息增益

**判断：有真实但“温和/方法层”的信息增益，不构成经验发现或 alpha。**

- 简单 screen 只能给出“QQQ -6.49% 是尾部事件”（percentile 约 0.4%）。
- GOE 额外做了三件事：用 SPY/VIX 支持风险规避、用 IEF 否定“简单利率上行”、把“成长/久期归因未分离”显式留作 unknown。这是**结构化的假设判别**，比单指标 screen 多一层推理。
- 但六条价格任何分析师都能取得，分解本身不是新数据、不是新事实、不是可交易 edge；mission 文档自己写明“not proof of investment alpha”“DISCOVERY VALUE: NOT VALIDATED”，**这一点没有过度声称**。
- 唯一措辞偏强处：mission 文档写“rejects a simple rates-up explanation”，finding 写的是 `WEAKENED`。基于单日 IEF 代理，建议改为“does not support / weakens”，不要用“reject”（P2-2）。

### 2.3 因果/过度声称检查

- **H-RISK**：只声称“supported by available evidence”，并注明“not a causal proof”，合格。
- **H-RATE**：`WEAKENED` 而非 `REJECTED`，合格；mission 正文的“rejects”偏强。
- **H-TECH**：finding 的 note 已说“not separable”，但 `investment_intelligence_qqq.json` 的 `supported_hypotheses` 直接列入 `H-TECH`，且没有携带“机制未分离”限定。对投资读者而言，这容易被读成“科技特异性 de-rating 已被支持”，属于**轻度因果过度声称**（P2-1）。
- **H-DATA**：没有把“无 flag”说成“无 artifact”，合格。

---

## 3. 复现（percentile / tests / 状态）

### 3.1 Percentile

- artifact：`percentile = 0.003968253968253968`（= 1/252），`event_return = -0.064889`，`pass = true`。
- 用 DB 最近 253 个收盘（252 个收益，截至 2026-11-05）复算：事件收益为**最小值**，`n<=event = 1`，`1/252 = 0.3968%`，与 artifact 一致。
- 用 254 个收盘（253 个收益）做稳健性 sanity check：`1/253 = 0.3953%`，仍是尾部最小。**percentile 可复现，尾部结论稳健**。
- 说明：0.3968% 落在双侧 5% 尾部内；“two-sided 5% tail”规则与实现一致。

### 3.2 Tests

- `historical_percentile`：pass（最小值，1/252）。
- `relative_underperform_test`：spread -2.0797pp，pass。
- `risk_test`：SPY<0 且 VIX>0，pass。
- `rate_test`：IEF +0.3382%，**fail**（正确地把“利率上行冲击”判为不成立）。
- `dollar_test`：DXY +0.0394%、Gold +0.9944%，**fail**（经典美元/黄金双重避险未确认；注意黄金单独上涨并不否定 risk-off，规则要求的是经典组合）。
- `reversal_test`：+4.2825%，pass。
- 本地 targeted 复跑：`tests/test_archetypes.py tests/test_research_exec.py tests/test_hypotheses.py` 全部通过（16 passed）。

### 3.3 Finding 状态

- `status = INCONCLUSIVE`；`learned` 5 条、`still_unknown` 4 条、`next_action` 明确“Retain in A；no B handoff”。
- 结论：**INCONCLUSIVE + learned/unknowns 成立**，没有把 INCONCLUSIVE 包装成 confirmed。

---

## 4. 投资情报与 A→B 验证

### 4.1 Investment intelligence 标志位

- `MARKET_EXPECTATIONS_NOT_ESTABLISHED`：**正确**。没有 implied rate / consensus / options 分布基线。
- `MISPRICING_NOT_ESTABLISHED`：**正确**；`direction/magnitude = null`。
- `decision_relevance`：research priority only；no trade/target/alpha claim。**合格**。
- `discovery_value = NOT VALIDATED`：与 mission 文档一致。

### 4.2 A→B 实际利率差证据

- `evaluation/a_to_b_validation.json`：`semantic_status = ok_valid`、`run_ok = true`、`n_evidence_rows = 63`、`s8_status = answered`。
- 数值复核：
  - UST_2Y = 4.56 @2026-11-09
  - UST_10Y = 4.88 @2026-11-09
  - CURVE_2S10S = 0.25 @2026-11-10
  - JGB10Y = 2.748 @2026-11-10
  - OP-1：2.748 − 4.88 = **-2.132** ✓
  - OP-2：4.88 − 4.56 = **0.32**，与注册值 0.25 的差异已如实披露 ✓
- 用下游 `/tmp/goe_ia_adapter2/.../report.json` 复核：`evidence_index` 长度 = **63**，`run_ok=true`，13 steps、0 failed，S8 `answered`。**63 rows 准确**。
- `l1_rows` 在 summary 中为空，但 S8 有 4 个事实值，`ok_valid` 判定符合 adapter 规则（`n_l1_rows>0 or n_s8_values>0`）。
- **B unchanged**：`a_to_b_validation.json` 只在 `0e005b7` 引入，`9c56364..HEAD` 无 diff；未发现 A 修改 B 的证据。

---

## 5. Proof / CI

- GitHub Actions `verify-release` **run #51**：`head_sha=553b0f9`、`status=completed`、`conclusion=success`、run id `43806016836`（2026-11-16T04:45:43Z）。
- 本地证明：`audit/releases/release_73ef6cb6ab.json`，`git_dirty=false`，`passed=254, skipped=0`；junit `tests=254, failures=0, errors=0`；日志 `254 passed, 10 deselected`。
- 本地 targeted 复跑通过；`git status` 干净（仅本 QA 文件新增）。
- 证明链结构完整：scan hash、data hash、artifact sha256、test proof sha256 均有记录。
- **P0：无**。未发现伪造证据、未来数据、合约漂移、测试/证明失效。

---

## 6. 问题清单（P0/P1/P2）

| 级别 | 编号 | 问题 | 证据 | 影响 | 建议 |
|---|---|---|---|---|---|
| **P1** | P1-1 | QQQ 投资情报含**日本/亚洲模板残留**：`alternative = "Japan/Asia-local factor dominates..."`，`monitoring` 含 `"TOPIX/Asia sector breadth"`，base 谈 “local/regional channels” | `evaluation/investment_intelligence_qqq.json`；根因 `goe/investment_intel.py:31,36` 为硬编码，任意 finding 都套同一段 | 投资读者会看到与美股 QQQ 无关的监测/替代情景，误导后续跟踪；与 `research/MISSION_01_QQQ.md` 的 monitoring（2Y/10Y、sector breadth、post-event reversal、positioning）不一致 | 按 finding/market 生成 scenario/monitoring；至少删除 JP/Asia 文案并以 mission 的 monitoring 为准 |
| **P1** | P1-2 | 同一 `research_id` 下存在**陈旧/错误模板 artifact** `...-e96d8477`：`test_id=equity_event_cross_section`（亚洲模板），`local_asia_test/global_lead_test/asia_regional_test/fx_test` 全为 null，反转字段名为 `n225_next_3d`，learned 写“local market n/a / prior US session n/a” | `research_results/2026-11-13/US_EQ_QQQ/RF-RC-...-e96d8477/finding.json`（在 73ef6cb 中提交） | 与 canonical `...-2ca1fb5a` 同 research_id 但测试/叙事冲突；按目录扫描的下游可能取到错误 artifact；对美股事件写“local/regional n/a”是事实错误 | 删除或明确标记 superseded；同一 research_id 只保留 canonical finding；增加“同一 research_id 多 finding”一致性测试 |
| P2 | P2-1 | intel `supported_hypotheses` 含 `H-TECH`，丢失“机制未分离”限定，易被读成因果支持 | `investment_intelligence_qqq.json`；finding note 已写“not separable from duration/risk-off” | 轻度过度声称；无 trade/alpha claim，故不升 P1 | 将 H-TECH 改为 `OBSERVED_NOT_SEPARABLE`，或在 intel 中带 caveat |
| P2 | P2-2 | 文档“rejects a simple rates-up explanation”强于 artifact 的 `WEAKENED`；单日 IEF 只是久期代理 | `research/MISSION_01_QQQ.md` vs finding `H-RATE.status` | 措辞层面的过度断言 | 改为“does not support / weakens”；保留 IEF 代理局限 |
| P2 | P2-3 | finding `code_commit = 9c56364`，实际发布/证明在 `73ef6cb`；artifact 由含未提交任务代码的工作区生成 | `...-2ca1fb5a/finding.json`；`created_at 04:37:33` 早于 73ef6cb 提交 04:40:52 | provenance 字段不能精确指向生成代码；但不影响内容复现（73ef6cb 已含 `us_equity_relative`） | 生成时记录 dirty-tree hash 或提交后再生成 artifact |
| P2 | P2-4 | `a_to_b_validation.json` 的 `l1_rows` 为空，63 行证据不能仅凭该 JSON 自证 | 该文件；`/tmp/.../report.json` 的 `evidence_index` 长度 63 可复核 | 审计可追溯性弱；本次已用下游 report 验证 | 在 summary 中保留 evidence_index 的 hash/样本，或注明 63 的来源 |

---

## 7. 最终判定

- **事件真实**：是。DB 收盘价复算与六条序列全部一致。
- **合约持久化/无漂移**：是。DB contract hash 与 finding 内嵌 contract 一致。
- **决策 as-of / 无未来数据**：是。2026-11-13，事件与反转数据均不晚于 as-of。
- **假设结论**：H-RISK 支持、H-RATE 弱化、H-TECH 观察成立但机制未分离、H-DATA 数据不足——**与任务描述一致**；但 intel 摘要的 H-TECH 标签有轻度过度声称。
- **信息增益**：真实但温和，属方法层假设判别，不是经验发现或 alpha；mission 文档对此诚实。
- **测试/percentile**：可复现；INCONCLUSIVE + learned/unknowns 成立。
- **投资情报标志位**：两个 NOT_ESTABLISHED 正确；A→B 63 行/ok_valid/数值准确；B 未变。
- **Proof/CI**：run #51 success，254 tests，0 failures；**P0 = 0**。

### 状态

**CONDITIONAL PASS（有条件通过）**：核心事件、PIT、合约、假设结论、A→B 与 proof/CI 均可接受；但存在 **2 个 P1**（QQQ 情报的日本/亚洲模板残留；同 research_id 的陈旧错误 artifact），需在对外把该 mission 作为投资情报交付前修复。P1 不影响“事件真实/无未来数据/254 tests/CI success”这些基础事实，故不判 FAIL。

> 本文件是唯一写入；未修改任何代码、数据、finding 或 proof。
