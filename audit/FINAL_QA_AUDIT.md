# FINAL QA AUDIT — 独立红队复核（round 1）

- 快照：`1ea537d`（含 audit 文档提交），工作区 clean；DB `data/goe.db`（scan `scan-20261114T030134Z-f03d5b`，as_of 2026-11-13）；复核时间 2026-11-14 11:21 HKT。
- 方法：只读代码/DB/报告；用仓库 `.venv` 重算 FeatureBuilder、SQL、pytest；未启动完整 `goe scan` / `goe replay`。唯一写入本文件。
- 结论：**PASS WITH ISSUES**。所有 8 个原报告 P1 均可独立复验通过；但新审计的 N-02（原标 P0）只修了一半，且 docs 的最终数字与 DB/报告不一致。

## 1. 判决

**PASS WITH ISSUES**，不是 PASS，也不是 FAIL。

支持 PASS 的证据：离线 121 passed（9 deselected），新增 48 项定向测试通过；P1-03/04 的前视/归一化、P1-05 的逐日切片、P1-06 的下游语义、P1-07 的就绪门禁、P1-08 的状态来源均有代码 + 数据/测试证据；当前 18 个候选的 gap 已无 0.7/0.6×机制置信度常量。

不判 FAIL 的理由：N-02 残留的 45 条 `trend_break` 伪异常全部落在 2026-04-27..05-14，当前 18 个候选没有引用其中任何一条，当前 30 天窗口和 top-3 不受影响；原 8 个 P1 没有未解决项。

最强反证（不能判 PASS 的原因）：
1. `trend_break` 134 条中 **45 条（33.6%）** 是 `detect_anomalies(since=...)` 先截断特征、再做 `sign.shift(10)` 产生的窗口起点伪突破；N-02 的“134 条已修好”不成立。
2. 文档最终数字与 DB 不符：DB/`reports/scan_2026-11-13.json` 是 **1,659** 条异常，`TEST_RESULTS.md`、`audit/VALIDATION_RESULTS.md`、`audit/FINAL_ACCEPTANCE.md` 均写 **1,651**；`PROJECT_SPEC.md` 仍写 2,935 条、6 条机制（2 supported），实际 1,659 条、5 条机制（3 mixed / 2 unsupported）。
3. “真实筛选能力”只有 LLM 盲评：引擎均值 1.2917 vs 最大异常分 1.2708（+1.6%），Precision@3 0.50 vs 0.25；无前瞻收益检验，且 2025-06-30 引擎 0.67 明显输给异常分 1.50。

## 2. 验证表

| # | 检查 | 命令 / 方法 | 观察值 | 判定 |
|---|---|---|---|---|
| 1 | 离线测试 | `.venv/bin/python -m pytest tests -m "not network" -q -p no:warnings`；加 `-o addopts=""` 取摘要 | exit 0；**121 passed, 9 deselected, 35.19s** | PASS |
| 2 | 新增定向测试 | `pytest tests/test_readiness_handoff.py tests/test_status_lifecycle.py tests/test_time_semantics.py tests/test_data_integrity.py tests/test_features.py tests/test_scoring.py tests/test_pipeline_e2e.py` | **48 passed, 33.47s** | PASS |
| 3 | P1-03 CFTC 前视 / P1-04 归一化 | `FeatureBuilder(as_of="2026-11-04").build()` | 10,036,093 行；positioning 最大 **2026-10-31**；> as_of 行 **0**；32 列（16 net + 16 `:oi`）；`POS_SP500_LEV.net_to_oi=**-0.204838**`，net=-400,604（ratio×OI 复算一致） | PASS |
| 4 | P1-05 逐日切片 | `FeatureBuilder(as_of="2024-09-15").build()` → `slice_as_of("2024-08-05")` | 8,067,231 行；Nikkei 1m **-23.1102%**、252d 回撤 **-25.4964%**；SPY 1m **-6.7179%**；VIX 1m **+209.0545%**；slice macro 最大 **2024-07-16**（未带入 7/1、8/1 印数） | PASS |
| 5 | N-01 周一收益 | 真实 DB/特征层，SPY 2026-11-09；97 个周一 | 11-09 收益 **+2.3664%**，**1d z=3.3497**（N-01 指标；1m z=-1.7996 也存在）；97 个周一仅 8 个 NaN，全部为美国假日（01-20、02-17、05-26、09-01、2026-01-19、02-16、05-25、09-07）；11-02、10-26、09-08、07-06、2025-12-26 均有收益 | PASS（任务写作“1m z”，实际 N-01 是 1d z） |
| 6 | N-02 trend_break 占比 | SQL + 独立复算（特征面板按 `since` 截断 vs 全窗） | DB **134/1,659=8.08%**（远低于 40%）；但 **45/134** 在截断帧中位置 <10（无 10 个有效观测回看），全部在 2026-04-27..05-14；全窗 vs 截断的原始 flag 数为 **876 vs 2,094**；当前 18 个候选引用这些早期异常 **0** 条 | **PARTIAL**：占比通过，N-02 修复不完整 |
| 7 | N-03 breadth | `FeatureBuilder(2026-11-13)`，US 区域 | 2,984 个观测、**48 个不同值**、0..1、最新 0.75；`breadth_extreme` 异常 **10** 条；`breadth_z` 非常量 | PASS |
| 8 | N-04 最新 US bar | 特征面板 vs 原始 prices | 特征层 SPY 最后有效 **2026-11-12**；原始 DB 仍有 2026-11-13 盘中 753.11（fetched 15:05Z），被 `_drop_incomplete_bars` 丢弃；US/CA/BR/MX 股票 38 个最后为 11-12，仅 4 个 FX 有 11-13；readiness 仍报 last_price_date=11-13 | PASS（特征层）；原始库/readiness 口径见问题表 |
| 9 | CFTC / CPI / NEWEN | SQL + 独立计算 | CFTC 原始最大 **2026-11-03**，特征层 11-13 时最大 11-07、11-04 时最大 10-31；CPI YoY 2026-09=**3.737685%**，2026-10=NaN（2025-10 基期为 NULL）；NEWEN **1,399** 行、`level_rebased` ratio **3.21328**、2024-09-18 收益 0、无缺失/尾部隔离 | PASS |
| 10 | P1-02 宏观可用日 / 机制窗口 | DB `evidence_json.entity_kind=="macro"` 的 14 条异常；`recency_days` | 宏观异常 **14/14** `as_of==available_date`，`available_date>as_of` **0**；窗口 **daily 7 / weekly 21 / monthly 75 / quarterly 150**；M05 `trigger_json` 含 `US_CPI`（available 2026-10-16），M14 含 `JP_POLICY_RATE` | PASS |
| 11 | P1-01 预期差 | 3 个机会 `discovery_json` + `grep` + 单测 | OPP-0001 gap **0.3176**（residual 0.7941，conf 0.4）；OPP-0002 **0.1392**（positioning 0.3977，residual 0，conf 0.75）；OPP-0003 **0.4000**（residual 1.0，conf 0.4）；均有 named component/evidence；无 0.7 / 0.6×机制置信度常量；`test_missing_expectation_gap_caps_at_watch` 通过；OPP-0010 gap=None 仅 watch | PASS（但见问题 3 的自变量 bug） |
| 12 | 机制统计 / FDR / lead_lag | DB `transmissions` + `config/mechanisms.yaml` + evaluator | 5 条机制；每条 test 均有 `p_value`/`p_adjusted`；M01 4 个失败全在 `evidence_against`，confidence 0.05；M12 3 通过 1 失败，confidence 0.63；配置 **7** 个 lead_lag，DB 5 个机制各 1 个 | **PARTIAL**：p/FDR 存在，但 n_eff 有下限 10、lag 搜索未校正（见问题 2） |
| 13 | P1-08 status_source | DB schema/值 + 3 个测试 + 代码 | `opportunities.status_source` 列存在，18/18 为 `auto`、0 NULL；降级/人工保护/terminal 不复活 3 测试通过；`persist_drafts` 区分 auto/manual/terminal | PASS |
| 14 | P1-06 下游语义 | 真实 `exports/ia_runs/OPP-0001/.../report.json` + 单测 | `run_ok=true`、17 evidence、13 steps 中 1 个 `semantic_ok=false` → parser **partial**；`research_tasks` RT-20261113-0001=`not_completed:partial`，事件 `ia_research_not_completed`；测试覆盖 ok/rejected/insufficient/partial/missing/stdout-ok:false | PASS（语义）；CLI 仍 exit 0（问题 5） |
| 15 | P1-07 就绪门禁 | 单测 + 内存 `Store(":memory:")` 强制 readiness 失败 | readiness stale/coverage 测试通过；强制失败后 `scan_runs` 写入 `mode=blocked,status=blocked_data` 且含 readiness；CLI `ScanBlockedError` 返回 **2** | PASS（代码）；生产 DB 无 blocked 行，见“无法验证” |
| 16 | 回滚 | `test_failed_scan_rolls_back_partial_records` | 报告阶段注入失败后 anomalies=0、opportunities=0；`rollback_scan` 删除 anomalies/transmissions/created opp | PASS（该失败点）；覆盖不足见问题 4 |
| 17 | 仓库卫生 | `git status/diff --stat e5da620..HEAD`、`check_secrets.sh`、`git grep` | 无删除测试；`config/thresholds.yaml` 无 diff（未降阈值）；无 tracked DB/.env/密钥；`/Users/...` 仅 `.env.example` 的 `/Users/you` 示例；4 个 shell 语法通过 | PASS（卫生）；docs 数字见问题 6 |
| 18 | 真实筛选能力 | 独立 1m 基准 + `audit/research_quality_*` 复算 | QQQ/SPY/XLP 的 1m 绝对收益排名 **32/84/41**（120 个可算标的）；盲评均值 A **1.1667**、B **1.2708**、C **1.2917**，Precision@3 **0 / 0.25 / 0.50**；2025-06-30 C **0.67** vs B **1.50**；无前瞻收益 | **PARTIAL** |
| 19 | 历史案例 7/7 | `reports/validation_cases_20261114T030757Z.json` + `validation.py` | 7/7 `passed=true`；但 **5/7 `mechanism_ok=false`**（UK、SVB、Japan、China、Gold）；pass 条件仅为 `detection_ok & relevant_candidate` | **PARTIAL**（通过但口径弱） |
| 20 | docs vs DB | `grep` 关键数字 | DB/报告 **1,659**；`TEST_RESULTS`/`VALIDATION_RESULTS`/`FINAL_ACCEPTANCE` 写 **1,651**；`PROJECT_SPEC:78-79` 写 2,935 / 6 条（2 supported）；`DATA_SOURCES:36` 写 127；`SCORING:36` 写 ≥38 而代码 `RESIDUAL_MIN_OBS=36` | **PARTIAL/FAIL（文档）** |

## 3. 剩余问题

| 严重度 | 位置 | 证据 | 影响 |
|---|---|---|---|
| **P1（N-02 原标 P0，修复不完整）** | `goe/anomalies.py:399`、`goe/anomalies.py:835`、`goe/pipeline.py:94` | `detect_anomalies(since=...)` 先截断 `fs.long`，TrendBreak 再对截断后的 `sign.shift(10)` 求翻转；前 10 个观测 `shift` 为 NaN，`sign != NaN` 为 True。DB 134 条中 **45 条** 位于 `since` 后前 10 个有效观测（2026-04-27..05-14），如 CN_SEC_SEC 2026-05-11、HK_EQ_3033 2026-05-05。全窗/截断原始 flag **876 / 2,094** | 异常总数虚增约 2.7%，trend_break 虚增 33.6%；每个历史验证 case 的前 10 天同样会产生伪 trend_break，可能污染 7/7；文档“134 条已修好”不成立 |
| P2 | `goe/transmission/evaluator.py:250`、`:293` | `n_eff=max(10, len(df)/window)`：n_obs 1636、window 250 → 6.54，却报 **10.0**；lead_lag 在 41 个 lag 中取最大相关，p 值未对 lag 搜索做多重校正 | corr 的 p/FDR 偏乐观；M12 的 0.63、M05/M09 的 FDR 通过需打折；研究结论置信度被高估 |
| P2 | `goe/expectations.py:143-159`；OPP-0002 | SPY 的 market driver 选中 SPY 自身，回归 R²=**1.0**、residual=0；该零残差仍计为 available component，使 confidence 从 0.35 升到 **0.75** | “预期差”证据对 SPY 自洽但无信息；当前 gap 0.1392 未触发 deep，但会误导未来 SPY 候选的置信度 |
| P2 | `goe/pipeline.py:122-124,164`；`goe/db.py:649` | `_created_ids` 在 `persist_drafts` 之后才赋值；失败发生在 persist 内部时不会删除已创建机会；`rollback_scan` 也不恢复已存在机会的自动升级/降级事件。测试只注入报告阶段失败 | “失败不留部分记录”只对测试的失败点成立；DB 错误/中途失败仍可能留下部分 opportunity 或状态变更 |
| P2 | `goe/cli.py:291` | `cmd_handoff` 对 `semantic_status != ok_valid` 只打印原因，仍 `return 0`；真实 partial 运行 CLI 退出码为 0 | 任务表/事件正确记录 not_completed，但 shell/调度器仍可能把 partial 当成功 |
| P2（文档） | `PROJECT_SPEC.md:78-79`；`TEST_RESULTS.md:60`；`audit/VALIDATION_RESULTS.md` C；`audit/FINAL_ACCEPTANCE.md:39`；`docs/DATA_SOURCES.md:36`；`docs/SCORING.md:36` | DB/报告 1,659 vs 文档 1,651；2,935 vs 1,659；6 条（2 supported）vs 5 条（3 mixed/2 unsupported）；127 vs 125；≥38 vs 代码 36 | 审计证据链不可复算；对外/PR 数字不一致；属于“最终文档未随最后一次扫描更新” |
| P3 | `goe/features.py:383-417`；`goe/readiness.py:62`；报告 | 原始 prices 仍保存 SPY 2026-11-13 盘中 753.11；readiness/报告写“最后价格 2026-11-13”，但 US 特征实际用 11-12 | 只读原始 prices 的脚本/人工核对可能误用盘中 bar；“最后价格”口径需说明是原始库还是特征层 |
| P3 | `tests/test_time_semantics.py:44` | 测试断言宏观异常 `date==观测日`，live 特征/DB 的 `date` 是 **可用日**（`macro_dates_are_availability=True`） | 该回归测试没有守住 live 语义；未来改动可能不易发现 |
| P3 | `goe/validation.py:195-207` | `passed = detection_ok and relevant_candidate`；`detection_ok` 只要求窗口内任一预期 detector/family 出现；5/7 `mechanism_ok=false` 仍算 pass | “7/7”是弱口径，不能证明机制/因果成立；docs 引用时需同时给出机制状态 |

## 4. 五道门

| 门 | 判定 | 证据 / 反证 |
|---|---|---|
| 工程正确性 | **PASS** | 121 离线通过、48 定向通过；P1-06 parser、P1-07 readiness、P1-08 status、rollback 测试均通过；无删除测试、无降阈值 |
| 数据可靠性 | **PARTIAL** | P1-03/04、周一收益、breadth、CPI、NEWEN、盘中 bar 均复验；但 45/134 trend_break 为窗口起点伪突破；原始库仍存 11-13 盘中 bar；CFTC/BLS vintage、期货展期不可验证；docs 数字过期 |
| 研究方法 | **PARTIAL** | 预期差已改为可测代理、无 0.7 常量；机制有 p/FDR/lead_lag、失败扣分；但 n_eff 下限 10、lag 搜索未校正、SPY 自驱动 R²=1.0、无样本外/因果识别 |
| 真实筛选能力 | **PARTIAL** | 有独立 PIT 切片验证（7/7 但 5/7 机制 unsupported）与 LLM 盲评（1.2917 vs 1.2708，+1.6%；2025 反例 0.67 vs 1.50）；**无任何前瞻收益/人类专家验证**；当前 top-3 的 1m 绝对排名仅 32/84/41，不能证明优于简单基准 |
| 交接 | **PASS（附注）** | 真实下游 run_ok=true/17 evidence/1 step failed → partial，task `not_completed:partial`，不是成功；parser 单测覆盖全部状态。残留：CLI exit 0、无真实 ok_valid 运行 |

## 5. 无法独立验证的声明

1. **7/7 全量回放未重跑**：我阅读了 `reports/validation_cases_20261114T030757Z.json` 和 `validation.py` 的 pass 逻辑，并独立复验了 P1-05 的 2024-08-05 切片；但没有逐案重跑 `goe replay --cases`（重负载，任务限制），因此 7 个 case 的分数/候选无法全部独立重算。
2. **LLM 盲评的“独立性”**：均值/Precision 可从 `research_quality_ratings.json` 复算一致，但无法验证 rater 是否真的独立、是否只看了事实卡；也无法排除 LLM 对结构化信息的偏好。
3. **真实 CFTC/BLS 发布时刻**：只能验证报告日 + 配置滞后（+4d / +45d），无法逐周验证实际发布时点；BLS/BIS 无 vintage。
4. **生产 DB 的 blocked_data 行**：生产 DB 只有 1 条 success scan，无 blocked 行；我在内存 Store 强制失败验证了 `blocked_data` 写入，但没有真实失败扫描归档。
5. **真实 ok_valid handoff**：真实 run 是 partial；没有成功的 downstream 端到端样本。
6. **9 个 network 测试**：按要求未跑。
7. **期货展期/复权 vintage**：无合约元数据，无法量化。
8. **N-02 对 7/7 的污染程度**：45 条伪 trend_break 会进入每个 case 的前 10 天，但我没有重跑 case 来量化其对 `relevant_candidate`/分数的影响。
9. **最终文档数字**：审计期间 docs/audit 文件被并发修改/提交；本文件以 11:21 HKT 的 `1ea537d` + DB/报告为准，无法保证之后不再变化。
10. **扫描 artifact 与 HEAD 的严格同源**：scan 11:01 产生，代码提交 11:13/11:20；`goe/` 无 diff（`ia_adapter` 11:09 变更不参与 scan），但我没有在 commit 后重跑完整 scan 来字节级对比。
