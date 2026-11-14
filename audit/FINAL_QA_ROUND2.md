# ROUND 2 — 独立最终 QA 复审（FINAL QA ROUND 2）

- 审计对象：`HEAD 7c5df4c` + 未提交 round-2 修复；工作树 `git status` 30 个修改 + 4 个新增审计文件。
- 数据/产物：`data/goe.db` 最终扫描 `scan-20261114T063140Z-315449`（as_of 2026-11-13，success，1,511 异常，11 候选，5 机制=2 mixed/3 unsupported，0 deep_research）；只读解析 `/tmp/cases_final_r2/validation_cases_20261114T063037Z.json`、`exports/ia_runs/OPP-0001/20261114T061751Z.../report.json`。
- 方法：`pytest` 全量离线；`sqlite3` 只读 SQL；把 DB `backup` 到 `/tmp/qa2` 后做删除/截断注入；源码阅读；评分/盲评/前瞻指标独立复算。**未改代码/配置/测试/生产数据/git**；唯一写入本文件。生产库未做任何写操作。
- 时间：2026-11-14 14:33–14:52 HKT。受 5 分钟时限约束，标“未独立验证”的项不冒充已验证。

## 1. 判决

**PASS WITH ISSUES。** round-2 声称的核心修复大多可复现：全量离线测试 **135 passed / 9 deselected**；readiness 对 UK/CN 整体失效、未发布宏观、wall-clock 隐式扫描、全曲线失效均按预期拦截；事务/失败扫描的 DB 回滚有测试覆盖；gap 当前行已到 2026-11-12；过去事件 catalyst=0.1；最终扫描 1,511/11 与代码产物一致；handoff parser 把 `out_of_scope` 判为 `refused`。

但仍有 **2 个 P1**（readiness 过阻/静默漏检）和一组 P2（小市场不可见、盲评方法-事实不对称、文档数字过期、7/7 仍是弱口径）。因此不能判 PASS；因最终产物未发现伪造/前视/错误数值，也不判 FAIL。

## 2. 验证表

| # | 检查项 | 结果 | 独立证据 |
|---|---|---|---|
| 1 | 离线测试 | **PASS** | `.venv/bin/python -m pytest tests -m "not network" -q` → **135 passed, 9 deselected, 46.36s**；`git diff` 的测试改动生效 |
| 2 | 历史 as_of 不被阻塞 | **PASS** | `/tmp` 副本 `as_of=2024-06-03`：`ok=True, critical=[], fresh_macro=15/16`；`regions` 末日期均 ≤ as_of |
| 3 | 最新未发布宏观不误判 | **PASS** | `as_of=2026-11-13`：`fresh_macro=14/16`；`US_CPI` 不在 `stale_indicators`；仅 `US_CAPE`（2023-09-01）与 `EA_HICP`（2025-12-01）真实过期 |
| 4 | 死亡 UK/CN 市场 | **PASS** | 删 UK 3 标的：`ok=False`，critical=`UK 市场完全没有价格数据…关键市场数据失效`；删 CN 23 标的：`ok=False`，critical=`CN …`（全局 coverage 仍 0.816/0.976） |
| 5 | wall-clock 隐式扫描 | **PASS** | 价格截到 2024-12-31：`check(as_of=None,today=2026-11-14)` critical=`最新价格距今已 683 天（>10）`；`run_scan(as_of=None)` 抛 `ScanBlockedError`，`scan_runs` 记 `blocked_data` |
| 6 | stale curve critical | **部分 PASS** | 四个曲线系统全删近期：critical=`收益率曲线全部过期：0/43`；但**仅 UST 全曲线死亡**：`ok=True`、无 critical、warnings 只有 EA_HICP（见 NEW P1-2） |
| 7 | 事务/失败扫描 | **测试级 PASS，未独立注入** | `tests/test_pipeline_e2e.py:108/125` 覆盖 `write_reports` 失败与 `VolRegimeShift.detect` 失败，135 项全过；源码确认 `store.transaction()` SAVEPOINT 嵌套 + `run_scan` 单事务包裹 anomalies/transmissions/opportunities/events；**未按 round-2 审计方式独立 monkeypatch 复跑**（时限） |
| 8 | gap 当前行 | **PASS（3/4 可核）** | `OPP-0001` residual evidence `as_of_return_date=2026-11-12, lag_days=1`；QQQ（`OPP-0008`）gap **0.0131**（与 round-2 “最新行”复算 0.0131 一致）；EEM（`OPP-0006`）0.1228（round-2 0.1227）；XLP 不在最终候选中，未独立复算 |
| 9 | self-driver 排除 | **PASS** | SPY residual `drivers=["market","dollar","rates"]`、`r2=0.7394`（非 1.0），未用自身作 market driver |
| 10 | 无 10–30 天采样相位 | **PASS（代码+产物）** | `expectations.py` 已删 `sample.iloc[::21]` 对 current 的使用；最终 11 个候选的 residual 日期全部为 2026-11-12 |
| 11 | 排名复算 | **PASS** | 按 `score_json` 重算：OPP-0001 **0.605618**（存 0.6056）、OPP-0002 0.592756、OPP-0003 0.54771；权重和 1.0 |
| 12 | 过去事件不再催化 | **PASS** | OPP-0001/0003 的 catalyst 日期 2026-10-16（as_of 前 28 天），`catalyst=0.1`；无负天数命中 1.0 |
| 13 | 重复 primary / 主题 | **PASS** | 11 个候选 primary 均不同（SPY/DXY/N225/DAX/USDJPY/EEM/TAIEX/QQQ/XLY/CHINEXT/XLK）；主题除 2 个 `None` 外均不同，None 的 dedup key 是 entity id，实际唯一 |
| 14 | invalidation / expected_direction | **部分 PASS** | OPP-0006 `invalidation_checks`（VIX3M 1m z∈[-1,1]）在主扫描内触发，事件 `status_change low_priority→invalidated` 已落库；`direction_conflict` 代码存在，但最终候选中无 XLP/冲突案例，**未能用产物复验方向矛盾被剔除** |
| 15 | 验证 7/7 | **PASS（弱口径）** | `/tmp/cases_final_r2/validation_cases_20261114T063037Z.json`：`n_passed=7/7`；`detectors_hit` 改为 case 实体（SVB 仅 `credit_stress`，来自 HYG/IEF 派生）；**7/7 全部 `mechanism_ok=false`**，SVB 相关候选仍是 TLT VIX / XLF 政策 |
| 16 | handoff 语义 | **PASS（端到端状态未核）** | 最新 `report.json` 解析：`semantic_status=refused`、`s8_status=out_of_scope`、`run_ok=True`、`n_l1_rows=0`、`n_l2_views=17`；`cmd_handoff` 对非 `ok_valid` 返回 2。**DB `research_tasks` 5 行均被最终扫描重导出为 `exported`，未保留 handoff 的 `not_completed:refused`；任务状态未独立确认** |
| 17 | 文档 vs DB | **部分 FAIL** | 1,511/11/5 机制与 125 标的、358,310 价格、159,508 指标一致；但 README/TEST_RESULTS 仍写 **121** 测试；VALIDATION/FINAL_ACCEPTANCE 仍写 top-3 **0.670/0.662/0.653**（实际 0.6056/0.5927/0.5477）和 **1,649 异常/18 候选**；TEST_RESULTS 仍写 handoff rc=0 产出报告 |
| 18 | 盲评 | **部分 PASS** | 重算 A **1.0625**、B **1.2292**、C **1.2500**；P@3 0.083/0.333/0.417，与文档一致；ID 已全局混排（无 X01-03 分块）；仍有 3 对重复实体（有效 n=33）；**事实卡机制数 C 9/12、B 3/12、A 1/12**（未修） |
| 19 | 前瞻收益 | **PASS（诚实披露）** | FORWARD_RETURNS：C 3m **+7.12%**、excess vs SPY **+0.56%**、beat SPY 25%、excess vs 同类 **+2.99%**、beat 同类 **42%**（低于 B 58%）；文档明确写“未跑赢简单异常排序/不用于调参” |
| 20 | mechanism_breakdown 洪水 | **未发生** | 最终仅 1 个（OPP-0005 USDJPY，low_priority，conf 0.05），cap=2；未观察到 flooding |

## 3. NEW 问题表（本轮独立发现）

| # | 严重度 | 位置 | 证据 | 影响 |
|---|---|---|---|---|
| 1 | **P1** | `goe/readiness.py:198-210`；`goe/opportunities.py` `_apply_gates` 的 `elif self.data_degraded` | 最终 scan stats：`readiness.degraded=True`，`stale_indicators=['macro:US_CAPE last_obs=2023-09-01','macro:EA_HICP last_obs=2025-12-01']`；`stale_macro_series={'EA_HICP':347,'US_CAPE':1169}`；只要任一 `stale_macro_ids` 非空就 `degraded=True` | **deep_research 的全局闸门永久关闭**：US_CAPE 自 2023-09 起死亡，任何扫描都 degraded，任何候选即使 score≥0.68 也会被降为 watch “数据就绪降级”。因此“0 deep_research 是严格门槛的诚实结果”不成立（至少部分是结构性过阻）；与 round-2 审计的“健康日被误判”同源，只修了新鲜度算法，未修全局粒度 |
| 2 | **P1** | `goe/readiness.py:213-237`；`tests/test_readiness_handoff.py:test_stale_curve_is_critical_not_silent` | `/tmp` 副本删 UST 全部 13 个期限的近期行：`ok=True, critical=[], warnings=['关键宏观序列过期：EA_HICP']`，仅 `stale_indicators` 列 13 条 curve；只有把 UST/JGB/EAC/CN 四个系统全部变旧才 critical（0/43）。测试 fixture 只 seed 了 UST，故测试通过但生产不可复现 | **整个 UST 曲线系统静默死亡**：rates 驱动、曲线快照、ERP/机制全部失去输入，扫描仍 success/report 正常外观；与 detector 异常静默同类（信号覆盖无声下降） |
| 3 | P2 | `goe/readiness.py:117-150` | 5 个 1–2 标的市场全删（CA/ES/FR/IT/TW）：`ok=True`、coverage 0.952，仅 warnings；CA 唯一标的截到 2024-12-31（682 天）：`ok=True`，**无 warning**（regions 里 `age_days=682` 但未进入 warnings/critical）；CH 2 标的死 1 个：`instrument_coverage=0.5` 且无 warning | round-2 审计 #1 的 P1 只修了 ≥3 标的市场；小市场/单标的死亡仍被全局 80% 覆盖掩盖。因缺价无候选、且已 degraded，影响小于原 P1，但“per-market missing detection”承诺未完全兑现 |
| 4 | P2 | `audit/research_quality_input.json`、`audit/research_quality_mapping.json`、`audit/RESEARCH_QUALITY.md` | C 卡带 mechanisms 9/12，B 3/12，A 1/12；C 机制内容为 `{id,status,confidence,role}`（如 X08 `M03… unsupported 0.05`）；rater 的 `beyond_price` 与“有无机制”同向；C 相对 B 均值仅 **+0.0208** | “同一模板、不含引擎假设”不成立：评审在 C 自己提供的机制结构上打分，+0.02 不能作为独立选择优势；round-2 只修了 ID 分块，未修事实不对称 |
| 5 | P2 | `README.md:214`、`TEST_RESULTS.md`、`audit/VALIDATION_RESULTS.md:31-40,48-52`、`audit/FINAL_ACCEPTANCE.md` | README/TEST_RESULTS 写 121 测试；VALIDATION 写 top-3 0.670/0.662/0.653 与 “18 候选/1,649 异常”；`FINAL_ACCEPTANCE` 仍是 round-1 的 1,649/18/top-3/partial；实际 DB 0.6056/0.5927/0.5477、1,511/11；TEST_RESULTS 写 handoff rc=0 成功，实际 refused | 验收文档与最终产物不一致；审计者按文档复算会得到不同结论，削弱“可复现验收” |
| 6 | P2 | `reports/validation_cases_20261114T033334Z.json` vs `/tmp/cases_final_r2/validation_cases_20261114T063037Z.json` | 仓库内最新 case 产物是 11:33（03:33Z）版本；14:30（06:30Z）的最终 7/7 只在 `/tmp`，未落入 `reports/`/`audit/` | 最终验证证据不可由仓库复现（“/tmp artifact”不是可交付证据）；VALIDATION_RESULTS 仍引用旧 03:33 文件 |
| 7 | P2 | `goe/integration/exporter.py:187-190` | handoff task 的 `expected_outputs` 仍含 **“估值与赔率”**，而 `build_research_question` 已删该措辞并写“不构成投资建议” | 任务 envelope 与问题文本自相矛盾；若 B 读取 task JSON，仍可能触发“赔率/建议”越界拒绝；当前 B 的 `out_of_scope` 主因是意图门，不一定是此字段，但契约不一致 |
| 8 | P2 | `goe/pipeline.py:139-151`；`goe/reports.py`/`exporter.py` | `write_reports`/`export_all` 在 DB 事务内但文件写入不可回滚；round-2 审计 #9 的文件残留（report/scan JSON 指向 failed scan）未在代码中处理 | DB 行能回滚，外部 artifact 仍可能与 failed scan 不一致；本轮未独立注入复验，代码结构显示风险仍在 |
| 9 | P3 | `docs/SCORING.md` catalyst 行；`TEST_RESULTS.md` | docs 仍写 `≤10=1.0，≤30=0.6，≤90=0.2，否则0.1`；代码为 `0≤days≤10→1.0，0≤days≤30→0.6，else 0.1`（无 90 天档） | 文档公式与代码不一致（小） |
| 10 | P3 | `goe/opportunities.py` mechanism_breakdown | 新原型由 unsupported 机制（conf 0.05）生成候选，OPP-0005 仍低优先级；未在最终 11 中造成洪水，但“负检验即研究线索”的证据标准只有 ≥2 个 substantive fail + 3% 月变动 | 不是当前缺陷，但新原型的独立测试/上限解释不足（cap=2 是唯一防洪水机制） |

## 4. 五闸门评估

1. **工程（PASS，带未验证）**：135 passed；事务 SAVEPOINT、detector 异常阻断、失败扫描回滚有测试；`run_scan` 单事务包裹持久化/报告/导出。**未独立注入** `write_reports`/detector 失败（时限），也未独立验证 `scan_runs=failed` 与 0 行的组合；文件残留风险仍在（P2-8）。
2. **数据（PASS WITH ISSUES）**：历史 as_of、未发布宏观、wall-clock、UK/CN 整体失效、全曲线失效均按预期；但 **UST 单系统死亡静默**（P1-2）和 **1–2 标的小市场不可见**（P2-3）。宏观 14/16、曲线/仓位/覆盖率与 DB 一致。
3. **方法（PASS WITH ISSUES）**：gap 当前行、self-driver、历史窗口披露（`history_start`）已修；catalyst 过去事件=0.1；invalidation 对当前候选生效。**未复验 XLP 方向矛盾**；证据质量公式已纳入机制置信度/反证据，但 `expected_direction` 的产物级效果无法从最终 11 候选确认。7/7 仍是“case 实体上任一 detector + 同主题候选”的弱口径，全部 `mechanism_ok=false`。
4. **发现（PASS WITH ISSUES）**：最终 11 个候选、1,511 异常、5 机制与 DB/文档计数一致；top 分数重算一致；无重复 primary/主题；mechanism_breakdown 未洪水。但 **0 deep_research 部分由 P1-1 的全局 degraded 强制**，不是纯粹门槛结果；盲评 C 的 +0.02 仍受机制卡不对称污染（P2-4）。
5. **交接（PASS WITH ISSUES）**：parser 对最新 B 产物返回 `refused`（`s8_status=out_of_scope`，17 L2 / 0 L1），CLI 对非 ok_valid 返回 2；比 round-1 的 partial/success 正确。**但任务状态未从 DB 确认**（被扫描重导出覆盖），`expected_outputs` 仍写“估值与赔率”（P2-7），且 B 仍拒绝，实际无 `ok_valid` 交付。

## 5. 最强反证 / 不能验证

**最强反证**：`readiness.degraded=True` 在最终扫描中由永久死亡的 `US_CAPE`（1,169 天）和 `EA_HICP`（347 天）触发；`OpportunityEngine` 在 deep_research 分支用 `elif self.data_degraded` 把任何达标候选降为 watch。也就是说，**“0 deep_research”不是“门槛未被满足”的干净结论，而是被一个与多数候选无关的永久死序列全局锁死**；这与文档“0 deep 是严格门槛的诚实结果”冲突。其次是盲评：C 的 9/12 机制卡 vs B 的 3/12，使 `beyond_price` 分数与研究处理同源，+0.02 不能证明选择优势。

**未独立验证（明确列出）**：
- `write_reports`/detector 失败的独立 monkeypatch 复跑（仅有测试级证据）；
- XLP 的 gap/方向矛盾与 `expected_direction` 产物级行为（最终候选中无 XLP）；
- 完整 `run_scan(as_of='2024-06-03')` 端到端（只验证了 readiness gate 不阻塞）；
- handoff 的 `research_tasks.status = not_completed:refused`（DB 已被最终扫描覆盖）；
- B 的真实意图门/`expected_outputs` 因果；人类专家标注；CFTC/BLS 发布时刻与 vintage；期货合约级换月。

## 6. 结论

**PASS WITH ISSUES。** round-2 的绝大多数修复可验证且方向正确；最终 DB 的 1,511/11 与代码产物一致，未发现伪造、前视或算术错误。但 readiness 仍有两个 P1：全局 `data_degraded` 永久关闭 deep_research（使“0 deep”结论失真），以及单曲线系统（UST）全灭不触发 critical。加上小市场不可见、盲评事实不对称、验收文档数字过期，建议按 P1→P2 顺序修复后再做一次 pin `scan_id` 的最终验收；在 P1 未修复前，不应把“0 deep_research / 7/7 / 引擎盲评更优”作为已证实的交付结论。
