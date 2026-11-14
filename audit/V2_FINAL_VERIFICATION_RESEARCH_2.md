# V2 最终研究复核 #2（独立，只读）

- 对象：`global-opportunity-engine`，分支 `architecture/research-v2`，冻结提交 `5db6e33`（代码提交 `532d819`）；manifest `audit/releases/release_532d819dcf.json`（`git_dirty=false`，`test_count=167`）。复核时 `git status --porcelain` 为空，工作树干净。
- 复核时间：2026-11-14 21:2x HKT。范围：复核 `audit/V2_FINAL_VERIFICATION_RESEARCH.md` 的 P1-A/P1-B；只读代码/文档/评估 artifact/DB，仅写本文件。
- 方法：`git show 5db6e33`/`532d819` 静态核对 + 只读 SQLite（`immutable=1`）+ 解析 `evaluation/*.json`；未重跑 scan/triage/评估，未改代码/配置/测试/数据/git。

## 结论：PASS WITH ISSUES（研究层）；无 P0；P1-A/P1-B 已关闭

- **P1-A（结果文档/生成器仍称 2021 为 test/held out）：CLOSED。** `evaluation/V2_EVALUATION_RESULTS.md:15-22` 已改为 "Independent test split — NOT AVAILABLE / exploratory, not an independent test / DISCOVERY VALUE: NOT VALIDATED"；`goe/research_evaluation.py:28-30` `TEST_DATES=[]`、2021-12-31 在 `DEV_DATES`，`:205-208` 在 `test.empty` 时输出 NOT AVAILABLE，不再生成 test 段。`evaluation/v2_eval_results.json` 为 `discovery_value=NOT VALIDATED`、`test={}`。
- **P1-B（验收文档虚假 no P0/P1 + 悬空 QA 引用）：CLOSED。** `audit/V2_FINAL_ACCEPTANCE.md:15` 已删除 "no P0/P1 known"，改引 `V2_FINAL_QA_ENGINEERING.md` 与 `V2_FINAL_VERIFICATION_ENGINEERING.md`（二者均存在于 `audit/`；`V2_FINAL_QA.md` 已无引用）；`:18,29-30` 已写实际 `not_completed:rejected`。
- **剩余全部为 P2 文档/脚本旧词，不构成新的 P0/P1，也不改变 NOT VALIDATED 结论。**

## 1. 逐项核验

| # | 检查组 | 结论 | 证据（5db6e33） |
|---|---|---|---|
| 1 | 2021 exploratory/reused；无独立 test；NOT VALIDATED 一致 | **PASS（主文档一致）** | `V2_FINAL_ACCEPTANCE.md:7,21,24`；`evaluation/V2_EVALUATION_RESULTS.md:15-22`；`evaluation/RESEARCH_EVALUATION_PROTOCOL.md:13,16-17,70-71`；生成器 `TEST_DATES=[]`。2021 在 `DEV_DATES` 而非 test。 |
| 2 | acceptance 无虚假 no P0/P1/悬空 QA 引用 | **PASS** | `V2_FINAL_ACCEPTANCE.md:15` 引用的两份 QA 文件均存在；全文件无 "no P0/P1"；`audit/V2_FINAL_QA.md` 不存在且已不被引用。 |
| 3 | V2-08 open research limitation 准确 | **PASS** | `audit/V2_ISSUES.md:12`：V2-08 = OPEN (research limitation)，明确 "the 2021 date was reused (no independent test)"，修复项为 "protocol amended as a limitation; result remains NOT VALIDATED; future ... new future test window"。与 acceptance RESEARCH METHODOLOGY/PARTIAL 一致。 |
| 4 | A→B 实际记录 `not_completed:rejected` | **PASS** | 只读 DB：`research_tasks` 中 `RC-20261113-12`，`created_at=2026-11-14T13:05:35Z`，`status=not_completed:rejected`；`opportunity_events` 同日 `ia_research_not_completed`，note "V2 handoff: rejected (... run_ok=false)"。acceptance `:18,29-30` 与之一致，且未声称 `ok_valid`。 |
| 5 | top5 N225/QQQ/TAIEX/XLV/EEM 可复算 | **PASS** | `evaluation/v2_candidates_2026-11-13.json` 5 条候选按 `priority_rank` 1..5 依次为 `JP_EQ_N225`(A)、`US_EQ_QQQ`(B)、`TW_EQ_TAIEX`(B)、`US_SEC_XLV`(B)、`WORLD_EQ_EEM`(B)，与 acceptance `:6` 完全一致。 |
| 6 | 无 VALIDATED claim；1.350 披露；无 test-date 调参 | **PASS（有 P2 保留）** | 追踪文件 grep 仅有 "NOT VALIDATED"/"not an empirically validated"；结果 JSON 为 NOT VALIDATED。`V2_FINAL_ACCEPTANCE.md:17,25` 与 `audit/RESEARCH_V2_RESULTS.md:28` 披露 D 1.350→0.833。`TEST_DATES=[]`；2021 复用与 gate 变更已披露，未在 test 上调权重。 |

## 2. 剩余 P0/P1

**P0：无。P1：无。**

P1-A/P1-B 均已在 `532d819` 关闭；研究结论仍为 `DISCOVERY VALUE: NOT VALIDATED`，无虚假成功、无 VALIDATED 声明。

## 3. 剩余 P2（文档/artifact 卫生，建议下次冻结前顺手修）

1. `audit/RESEARCH_V2_RESULTS.md:11` 仍写 "Test (held out): 2021-12-31"，`:38` 仍写 "Test split has only 3 D objects"；同文件 `:13,21-23` 已自我更正为 exploratory/no independent test，属同文前后不一致。
2. `audit/V2_FINAL_ACCEPTANCE.md:26` 仍写 "test n=3"（应改为 "reused-date n=3" 或删去 test 字样）。
3. `evaluation/RESEARCH_EVALUATION_PROTOCOL.md:54` 决策规则仍以 "On the **test** split" 开头（现已无 test split，属悬空条件）；`:60` "4 selected/method/date" 实际为 3/date。
4. `goe/research_evaluation.py:210-217` 的 `else` 分支仍保留 "## Test split" 与 "D beats B and C on test" 死代码；当前 `TEST_DATES=[]` 不可达，不会产出错误文档，但属潜在复发点（若未来加入 test 日期会重新生成 test 段并可能给出 VALIDATED）。
5. `evaluation/v2_eval_mapping.json` 的 `splits.development` 只有 3 个日期（缺 `2021-12-31`），而代码 `DEV_DATES` 含 2021；评分时 2021 行落入 "unknown"。全样本汇总与 NOT VALIDATED 不受影响，属 artifact/code 漂移。
6. `audit/EXECUTION_STATE.md:62` 仍写 A→B "returns unmapped/refused"，与 DB 实际 `rejected` 不符；`V2_FINAL_VERIFICATION_ENGINEERING.md` 仍以 `a31f545` 为对象记 anomaly-date P1-2 "PARTIAL"，而 acceptance `:34-36` 称已由 `DETECTION_CONTRACT` 语义定义解决——契约已改，但该报告未刷新，属跨文档口径差。

## 4. 结论口径

- 研究层：**PASS WITH ISSUES**。P1-A/P1-B 关闭，无 P0/P1；`DISCOVERY VALUE: NOT VALIDATED` 不可升级，结论诚实且无夸大。
- 上述 P2 不影响冻结提交的验收判断，但 "2021 relabelled everywhere" 与 "test n=3" 等旧词仍在少数文档/死代码中；若要求文档完全自洽，应在下一次冻结前修掉第 1-3、6 项并重新冻结、复核。
