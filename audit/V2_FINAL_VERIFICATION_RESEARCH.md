# V2 最终研究复核（独立，只读）

- 对象：`global-opportunity-engine`，分支 `architecture/research-v2`，冻结提交 `a31f545`（tag/发布产物 `audit/releases/release_a31f545dbc.json`，其中 `git_dirty=false`、`test_count=166`）。
- 复核时间：2026-11-14 21:08–21:2x HKT。范围：只读代码/契约/评估 artifact/DB/文档；仅写本文件。未改代码、配置、测试、数据、git。
- 方法：`git show a31f545:<file>` 核对提交内容 + 只读 SQLite（`immutable=1`）+ 读取提交内导出 artifact。未重跑 scan/triage/评估。
- **重要环境事实**：复核期间工作区出现未提交修改（`audit/V2_FINAL_ACCEPTANCE.md`、`evaluation/V2_EVALUATION_RESULTS.md`、`goe/research_evaluation.py`、`audit/EXECUTION_STATE.md`，`git status` 显示 4 个 M）。本报告一律以**提交 a31f545** 为准；工作区改动另见 §5，不能当作冻结提交已修复。

## 结论：FAIL（P1 未全部关闭）

- 无 P0。研究结论本身诚实：`DISCOVERY VALUE: NOT VALIDATED` 未被升级，第 3、6 项实质通过。
- 但冻结提交上第 2、5 项失败，第 4 项“文档写实际状态”失败：验收文档仍自称“no P0/P1”并引用不存在的文件，结果文档仍把 2021-12-31 写成 “test; held out”。因此不能判 PASS 或 PASS WITH ISSUES。

## 1. 逐项结论

| # | 检查组 | 结论 | 证据（a31f545） |
|---|---|---|---|
| 1 | triage 前五 / 无 DXY、BRL、USDJPY 旧说法 | **PASS（文档）/ 不可复算（artifact）** | `audit/V2_FINAL_ACCEPTANCE.md:6` 已改为 “N225 (A), QQQ (B), TAIEX (B), XLV (B), EEM (B)”；V2 文档中已无 “DXY/BRL/USDJPY 前五”表述（仅 V1 的 `docs/examples/report_2026-11-13.md`、`docs/id_reference.md` 正常提及这些资产）。但提交内唯一 5-candidate 运行产物缺失：`exports/research_candidates_2026-11-13.json`（21:05）只有 1 条 `RC-20261113-12 N225`，是 `triage --handoff --limit 1` 的导出；QA 在 44b9572 的 limit=10 实跑第五是 DXY、EEM 第六。a31f545 的 gate 改动（drawdown_extreme+near_high 需 |1m|≥5% 或 dd≤5%）足以解释 DXY 掉出、EEM 递补，但**没有保留可复算的 5 条输出**，EEM 入前五无法从提交产物独立验证。 |
| 2 | 2021-12-31 标为 exploratory/reused；protocol/results/acceptance 一致；NOT VALIDATED | **FAIL（一致性）** | acceptance 已改：`:7` “no independent test split”、`:21` “2021-12-31 (exploratory/reused)”；protocol split 表已改（`RESEARCH_EVALUATION_PROTOCOL.md:13`）。**但**提交的 `evaluation/V2_EVALUATION_RESULTS.md` 仍写 `## Test split (2021-12-31; held out)`、空表、`- D beats B and C on test (mean and P@3): [False, False]`、`do not tune ... on this test date`；生成器 `goe/research_evaluation.py`（a31f545 版本）仍输出该 test 段；protocol `:55` 决策规则仍 “On the **test** split”、`:70` Known limits 仍 “Test split (2021-12-31) yielded D n=1”。结果/协议与 acceptance 自相矛盾。 |
| 3 | D 0.833 vs C 0.979/B 0.917/A 0.875；second rater 1.350 披露；无 VALIDATED | **PASS** | `V2_FINAL_ACCEPTANCE.md:17,23-25`；`evaluation/V2_EVALUATION_RESULTS.md` 全样本表 A .875 / B .9167 / C .9792 / D .8333；`V2_FINAL_ACCEPTANCE.md:25` “earlier exploratory rating gave D 1.350; it did not replicate (0.833)”。全仓相关文档 grep 只有 “NOT VALIDATED” 与 “not an empirically validated ranking”，无正向 VALIDATED 声明。 |
| 4 | 真实交接记录 not_completed:rejected/refused、非成功、候选保留；文档写实际状态 | **PARTIAL（记录 PASS / 文档 FAIL）** | DB 实存 `research_tasks`：`RC-20261113-12`，`created_at=2026-11-14T13:05:35Z`，`status=not_completed:rejected`；`opportunity_events` 同日 `ia_research_not_completed`，note “V2 handoff: rejected (下游研究明确返回失败/拒绝（run_ok=false）)”；payload 保留 candidate 与 result（`status=not_ok`、`semantic_status=rejected`、`run_ok=false`）。**但**提交的 acceptance `:18` 仍写 B 返回 `unmapped/no_registry_identity`、`:29-30` 仍写 “run_ok=true but S8 no_registry_identity”；`EXECUTION_STATE.md` 写 “unmapped/refused”。三项都不是实际的 `rejected`。 |
| 5 | acceptance 无虚假 no P0/P1、无悬空 QA 引用；V2-08/V2-09 状态准确 | **FAIL** | 提交的 `V2_FINAL_ACCEPTANCE.md:15` 仍为 “no P0/P1 known after final QA (see `V2_FINAL_QA.md`)”；`audit/V2_FINAL_QA.md` **不存在**（只有 `V2_FINAL_QA_ENGINEERING.md`、`V2_FINAL_QA_RESEARCH.md`）。`audit/V2_ISSUES.md:12` V2-08 仍是 **OPEN P1**，故 “no P0/P1” 自相矛盾。另：V2-08 描述 “test n=1” 已过期（现无 test；2021 复用后 n=3）；V2-09 描述 “CLI integration remains a V3 item”，但 a31f545 已加 `goe triage --handoff`（`goe/cli.py`），状态描述不准。 |
| 6 | 无 test-date 调参；阈值评估前已文档化 | **PASS（有保留）** | `goe/research_evaluation.py`：`TEST_DATES=[]`，2021-12-31 移入 `DEV_DATES`；2021 复用与 gate 变更已在 acceptance/protocol 披露。阈值 |1m|≥5%、dd≤0.05 写在 `contracts/RESEARCH_CONTRACT.md:34`（M2，早于最终评估），非 test 专用常量。保留：a31f545 的 gate 改动发生在 44b9572 评估之后，`v2_eval_mapping.json` 只改 split 标签、D 的 12 个对象未变，提交未说明是否受该 gate 影响/是否重算；若受影响，D 数值仍是旧 gate 产物。 |

## 2. 剩余 P0/P1

**P0：无。**

**P1（未关闭）：**
1. **验收文档虚假 “no P0/P1” + 悬空引用**（`V2_FINAL_ACCEPTANCE.md:15` → 不存在的 `audit/V2_FINAL_QA.md`；同文件 V2-08 仍 OPEN P1）。这正是 QA P1-4，冻结提交未修。
2. **2021-12-31 仍被结果文档/生成器称为 “test; held out”**（`evaluation/V2_EVALUATION_RESULTS.md` 的 test 段与 “D beats B and C on test”；`goe/research_evaluation.py` 仍生成该段；protocol `:55/:70` 仍 test/n=1）。与 acceptance “no independent test split” 直接冲突，是第 2 项失败的核心。

**P2（精度/证据卫生）：**
- 交接文档语义错误：acceptance/EXECUTION_STATE 写 `no_registry_identity`/`run_ok=true`，DB 实际 `rejected`/`run_ok=false`（记录本身正确，仅文档未同步）。
- protocol 旧文字：“4 selected/method/date”（`:60`，实际 3/date）、“Test split ... n=1”（`:70`）；决策规则仍绑定 test。
- V2-08 “test n=1”、V2-09 “CLI remains V3” 描述过期；acceptance A→B 行未提已存在的 `goe triage --handoff`。
- 前五名单无可复算 artifact（只有 --limit 1 导出）；EEM 递补仅能靠 gate 逻辑推断。
- 评估未在 a31f545 gate 改动后重跑/说明无影响；`release_a31f545dbc.json` test_count=166 与 acceptance “165 offline passed” 不一致（工作区已改 166）。
- 第二评分者样本不同（旧 46/D n=10，新 48/D n=12；D 仅 6 个 (date,entity) 重叠，6 个全部 -0.5），写成 “inter-rater instability” 偏强，应报重叠子集与尺度漂移。

## 3. 最强反证（对“V2 更差/已验证”两侧）

1. **复用日 D 并不输**：2021-12-31 上 D .750 > B/C .583（A .833 最高）；全样本 D .833 < C .979/B .917/A .875 主要由开发期日期驱动。正确表述是“无可判定的优势”，不是“test 上更差”。
2. **P@3 在 n=3 上无区分力**：分母 3，取值只能是 0/1/3；全零不能支持任何方法优劣。
3. **评分尺度漂移**：6 个重叠 D 卡全部 -0.5；A/B/C 全样本也整体下移（约 -0.27~-0.31），第二次评分整体更严，跨方法比较受尺度影响。
4. **构念不匹配**：盲卡测“资产选择”，非 V2 research brief；D 预筛、A/B/C 不预筛。故这套评估既不能证明 V2 更好，也不能可靠证明 V2 更差；只能维持 NOT VALIDATED。
5. 上述反证**不能**把结论升级为 VALIDATED；且第 2/5 项是文档一致性缺陷，不会因这些反证而消失。

## 4. 结论口径

- 研究层：**维持 `DISCOVERY VALUE: NOT VALIDATED`，不可升级**；无 P0，无虚假成功声明。
- 验收层：**FAIL**。冻结提交 `a31f545` 仍不能作为“P1 已关闭/干净验收”的签收版本；修完第 2/5 项（结果文档与生成器统一改 exploratory、删除 test 段；acceptance 删除 “no P0/P1” 并引用真实 QA 文件/更新 V2-08、V2-09）后需重新冻结、重新独立复核。

## 5. 复核期间观察到的未提交改动（不属于 a31f545）

`git status`：`M audit/EXECUTION_STATE.md`、`M audit/V2_FINAL_ACCEPTANCE.md`、`M evaluation/V2_EVALUATION_RESULTS.md`、`M goe/research_evaluation.py`；`?? audit/releases/release_a31f545dbc.json`（发布产物本身）。
- 工作区 acceptance 已改为 “latest real run B returned `rejected` ... `not_completed:rejected` ... V2 CLI entry exists”，并删除 “no P0/P1”，改引 `V2_FINAL_QA_ENGINEERING.md`/`V2_FINAL_VERIFICATION_ENGINEERING.md`。
- 工作区 `V2_EVALUATION_RESULTS.md` 与 `research_evaluation.py` 已改为 “Independent test split — NOT AVAILABLE”，不再输出 test 表。
- 这些改动若提交，可关闭本报告 P1-2 与 P1-1 的文档部分；但 `V2_FINAL_VERIFICATION_ENGINEERING.md` 是否真实存在、V2-08 仍 OPEN P1 时 acceptance 能否声称 “P1s fixed”、protocol `:55/:70` 旧文字是否同步，仍需复核。且 `release_a31f545dbc.json` 记录 `git_dirty=false`，与当前脏工作区不符，需重跑 release gate 后重新冻结。
