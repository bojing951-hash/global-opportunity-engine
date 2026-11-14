# V2 FINAL QA — 研究/评估独立复核（只读）

- 仓库/分支/冻结点：`global-opportunity-engine`，`architecture/research-v2`，`44b9572`（前一提交 `7ead637`，初始 V2 `4e3f40d`）。
- 范围：只读代码/配置/契约/评估 artifact/DB；仅写本文件。未修改代码、配置、测试、数据、git。
- 方法：静态核对 + 重算 `evaluation/*.json` + 一次只读 V2 triage（as_of 2026-11-13，输出到 `/tmp`，未写仓库）+ 只读 DB 查询。未跑全量构建/网络测试。
- 结论先行：**`DISCOVERY VALUE: NOT VALIDATED` 的结论正确、方向诚实、无夸大优势；但验收文档与真实 V2 产出存在新的 P1 级不一致，且“held-out test 只用一次”的表述与其提交时序不符。没有发现 P0，也没有任何证据可把结论升级为 VALIDATED。**

## 1. 逐项验证

| # | 项目 | 结果 | 证据 |
|---|---|---|---|
| 1 | 评估 split 与评分/映射 | **PASS（有保留）** | `goe/research_evaluation.py:28-30`：dev `2022-10-31/2024-09-30`、validation `2023-03-31`、test `2021-12-31`；`v2_eval_mapping.json.splits` 同。48 objects，48/48 有评分；盲卡仅 `as_of/object_id/facts`，序列化后无 method/tier/hypothesis 字样（仅对象 ID 含 “V2x”，非泄漏）。每个 method/date 恰 3 个对象；test 每个 method n=3（D=3，满足 n>=3）。 |
| 2 | 最终数值与决策规则 | **PASS** | 重算均值/P@3 与文档逐位一致：A .875/0，B .9167/.0833，C .9792/.1667，D .8333/0；test A .833、B .583、C .583、D .750，P@3 全 0。`v2_eval_results.json` 的 `D beats B and C on test (mean and P@3) = [False, False]` 与“mean 胜、P@3 平（0=0，非严格胜）”的规则一致；`V2_FINAL_ACCEPTANCE.md`、`RESEARCH_V2_RESULTS.md`、`V2_EVALUATION_RESULTS.md` 均写 NOT VALIDATED，无“优于 V1/基准”的表述。 |
| 3 | 第二评分者不稳定 / 构念不匹配的披露 | **PARTIAL** | 两处均明写：D 1.350 → 0.833（`RESEARCH_V2_RESULTS.md:32-33`、`V2_FINAL_ACCEPTANCE.md:17,25`）；盲卡测“资产选择”而非 V2 research brief、D 预筛而 A/B/C 不预筛（`:36-43`、acceptance `:26`）。**但“second rater”并非同一样本**：旧评 46 objects、D n=10；新评 48 objects、D n=12；D 只有 6 个 (date,entity) 重叠。见 P2-2。 |
| 4 | V2 triage 前五与字段完整性 | **FAIL（文档）/ PARTIAL（数据）** | 实跑（冻结 commit）：N225(A)、QQQ(B)、TAIEX(B)、XLV(B)、DXY(B)；**不是**验收文档写的 “N225, DXY, BRL, USDJPY, TAIEX”（BRL/USDJPY 不在前五，QQQ/XLV 未提）。每个候选 5 hypotheses、4–5 evidence、4–5 unknowns、1–4 falsifiers。但真实输出中 25 条 hypotheses **`evidence_for/evidence_against` 全为空**，falsifiers **无 `hypothesis_id`**，TAIEX 仅 1 条 falsifier；DXY `gap=0.0` 仍因 `mechanism_conflict` 进 tier B。见 P1-1/P1-3。 |
| 5 | A→B V2 交接 | **PASS（有保留）** | `build_v2_question` 含“事实核对/关键未知/证伪”，测试断言禁用词（建议/仓位/买卖/多空/赔率等）不出现（`tests/test_research_v2.py:27-35`）；`persist_v2_result` 只在 `status=="ok" 且 semantic=="ok_valid"` 时写 completed，否则 `not_completed:<sem>`；payload 保留候选（`research_handoff.py:70-84`）。DB 实存 `RC-RC-20261113-08` → `not_completed:rejected`，无 V2 成功事件。**但**验收称 N225 为 `no_registry_identity`，DB 可复核记录是 `rejected`；该 N225 具体记录/事件未能从 artifact 复核（P2-5）。 |
| 6 | test 日期隐藏调参 | **PARTIAL** | 代码/配置中无 test 日期专用常量，日期只出现在 `goe/research_evaluation.py` 的预注册 split 列表。ordinal 阈值在 `contracts/RESEARCH_CONTRACT.md` 中写明，且在**最终**评估（`44b9572`）之前（`7ead637`）已提交。**但**同一次 `7ead637` 也改了 `goe/research_triage.py` 的 gate 逻辑，并在其 message 中记录“test n=1”；随后 `44b9572` 用同一 test 日期重跑出 n=3。见 P1-2。 |

## 2. NEW issues（按严重度）

### P1（影响结论表述/可复现性；不改变 NOT VALIDATED）

1. **验收文档的 V2 triage 前五不可复现（文档事实错误）**
   - `audit/V2_FINAL_ACCEPTANCE.md:6`：“top N225 tier A/B, then DXY/BRL/USDJPY/TAIEX”。
   - 冻结 commit 实跑结果：`RC-20261113-14 N225 A`、`RC-20261113-17 QQQ B`、`RC-20261113-16 TAIEX B`、`RC-20261113-22 XLV B`、`RC-20261113-19 DXY B`（limit=10 时第 6–10 为 EEM/XLP/SMI/IPC/MTUM，仍无 BRL、USDJPY）。BRL/USDJPY 的“前五”说法无 artifact 支撑，疑似与 V1 候选清单或旧审计混淆。
   - 性质：文档/验收证据错误（code fix 可修，不需要改研究结论）。

2. **“test held out、只用一次”的表述与提交时序冲突**
   - `RESEARCH_EVALUATION_PROTOCOL.md:13-16`：“used once for the final claim”“No date may move from test to development after seeing results”；`:15` 要求若 test 被用于改规则则 relabel。
   - 时序：`4e3f40d` 初始评估 test D **n=1**（D=1.5，P@3=1.0，点估计）；`7ead637` 同时（a）修改 triage gate/排序，（b）在 protocol 追加“test n=1”限制；`44b9572` 在**未 relabel** 的情况下用同一 `2021-12-31` 重跑，test D 变 n=3，得 D=.75。
   - 因此最终文档仍称 test “held out / used once”不准确；`RESEARCH_V2_RESULTS.md:34` 的“No weights were tuned after seeing either result”字面成立（没调权重），但**规则（gates）在看见首次 test 结果后改过，test 日期被复用**。结论仍是 NOT VALIDATED，故无误导性正向声明；但这是评估协议完整性的 P1 缺陷。

3. **真实 V2 产出不满足 RESEARCH CONTRACT 的 hypothesis 证据字段**
   - 契约：`contracts/RESEARCH_CONTRACT.md:6-7` 要求每个 hypothesis 带 `evidence_for`、`evidence_against`；`V2_ISSUES.md` V2-05 标“FIXED”。
   - 实际：实跑 5 个候选 × 5 hypotheses，`evidence_for`/`evidence_against` **全为空数组**；falsification 只有 `test/threshold/data`，无 `hypothesis_id`，无法绑定到假设；TAIEX 仅 1 条 falsifier（信用利差代理），与其“gap=0.782 + 无可检验机制”并列时信息量偏低。
   - 另：DXY `gap=0.0`（标准驱动已完全解释）仍以 `mechanism_conflict` 进 tier B，和契约 gate 2 “standard drivers do not fully explain”冲突；这与方法审查 P0-2 的旧模式同类，属 triage 规则未真正修好。
   - 性质：**code/contract fix**（可修）；但它也说明“结构化假设/证据”目前是模板骨架，不是已实现的研究深度。

4. **验收文档自相矛盾：声称无已知 P0/P1，但 issue ledger 有 OPEN P1 且引用文件不存在**
   - `V2_FINAL_ACCEPTANCE.md:15`：“no P0/P1 known after final QA (see `V2_FINAL_QA.md`)”；`audit/V2_FINAL_QA.md` **不存在**；同表 RESEARCH METHODOLOGY = PARTIAL。
   - `audit/V2_ISSUES.md` 仍列 V2-08 OPEN（P1，评估测资产卡/预筛/短样本）、V2-09 PARTIAL（P1，CLI handoff）、V2-10 OPEN（P2，单评分者/无 CI）。
   - 性质：文档/验收表述错误（code fix 可修），不改变研究结论。

### P2（清理/披露精度）

1. **protocol “Known limits” 已过期**：`:69` 仍写 “test split yielded D n=1, below n>=3”，与最终 n=3、48 objects 冲突；`:59` “4 selected/method/date”、`:42` “12 selected objects” 与实际 3/date、12/method 混用。
2. **“second rater” 比较不是同一样本**：旧 46/D n=10 vs 新 48/D n=12；6 个重叠 D 对象在新评中**全部恰好下降 0.5**（USDJPY 1.5→1.25、CSI300 1.5→1.0、BTC 1.5→1.0、USDJPY 1.75→1.25、XLK .75→.5、CSI300 1.5→1.0）。这更像评分尺度系统性下移（rater/尺度层）+ 候选集更换，不宜简单写成“同一对象的 inter-rater instability”；应报告重叠子集与新增对象。
3. **test D 卡片质量**：3 个 test D 对象为 USDJPY 1.25、USMV 0.50、XLP 0.50；后两者 note 明写“仅价格数据/仅价格弱机制”，data_sufficiency=0。D 的 test 均值 .75 由单条撑起，2/3 是低信息卡；这与“D 选品未验证”一致，也说明 test 对 D 不公平/不具代表性（两方向都削弱任何强结论）。
4. **指标实现与决策规则未完全对齐**：`precision_at_3` 实为 “mean>=1.5 的 share”，非 top-3 precision；决策规则只比较 mean/P@3，未按 protocol 检查 evidence sufficiency/falsifiability 的“no material regression”（本样本 0.25/1.5 vs C 0.50/1.5 其实有回归，未被规则捕捉）。
5. **A→B 记录不一致**：验收写 N225 `no_registry_identity`，DB 唯一 RC 记录为 `not_completed:rejected`；无法从 artifact 追溯 N225 的那次运行/事件。
6. **test 日期为不完整交易日**：2021-12-31 有 9 个市场休市（DAX/SMI/SX5E/IBEX/FTSEMIB/N225/TOPIX/KOSPI/TAIEX），横截面与 dev/validation 不同；此限制只写在方法审查，未进最终结果文档。2026 年 LLM 评分对 2021 卡片的“后见知识”同样只在方法审查披露。

## 3. 最强反证（对“V2 更差”的反证）

1. **test 均值 D 并不输**：D .750 > B/C .583（A .833 最高）。否定只来自“P@3 0=0 的平局不算胜”+ 严格 both-metric 规则；全样本 C .979 才明显领先。因此正确表述是“test 无可判定的 P@3 优势、全样本劣于 C”，不是“D 在 test 上更差”。
2. **P@3 分母与粒度**：test 每方法 n=3，P@3 只能是 0/1/3 粒度；三者全 0 说明该指标在 test 上无区分力，不能支持“B/C 优于 D”。
3. **评分尺度漂移**：6 个重叠 D 卡全部 -0.5，且 A/B/C 全样本也整体下移（A -0.29、B -0.27、C -0.31），说明第二次评分整体更严；跨方法比较受评分尺度影响，单次 D 0.833 不能独立证明“V2 选品差”。
4. **无隐藏优势证据**：全部文档/结果均写 NOT VALIDATED；代码无 test 日期常量；最终评估前阈值已写入 contract。故反证只能把结论从“D 更差”拉回“不可判定/未验证”，**不能**拉到 VALIDATED。

## 4. 代码可修 vs 研究未验证

| 类别 | 事项 |
|---|---|
| 代码/文档可修（不改变结论） | 验收 top-5 清单错误；`V2_FINAL_QA.md` 悬空引用与“无 P0/P1”自相矛盾；hypothesis `evidence_for/against` 空、falsifier 无 `hypothesis_id`；protocol 过期 n=1/4-per-date 文字；A→B 记录不一致；`precision_at_3` 命名/实现；决策规则缺 evidence/falsifiability 非回归检查。 |
| 研究层面未验证（不能靠修代码/调阈值解决） | 盲卡测“资产选择”而非 D 的 research brief（构念/效标不匹配）；D 预筛、A/B/C 不预筛（选择≠排序）；单一 LLM、无人类标签、无 IRR；test n=3 且日期不完整、被复用；低信息 test 卡片；第二评分非同样本。这些只能通过新的预注册协议（共同候选池、D-filter-only/random 基线、research-brief 模板、多评审、冻结未来窗口）重做。 |

## 5. 结论

- **V2 文档对自身失败的表述总体诚实**：48 对象全覆盖、方法盲化、test n=3、D 全样本低于 C/B、test P@3 全零、D 未同时在 mean 与 P@3 上胜 B/C，均与 artifact 重算一致；无“V2 优于基准”的隐藏声明。
- **但验收包不能作为“干净 held-out 验证”**：test 在首次 n=1 结果后被改规则并重跑，protocol 未按其自身规则 relabel；且真实 triage 前五与验收文字不符。
- **DISCOVERY VALUE: NOT VALIDATED**（维持；不可升级）。若需正式签收：研究层 NO-GO for VALIDATED，工程层可保留“结构化研究问题生成器/探索性”定位；先修 P1 文档与契约字段，再按新协议开独立 test window，禁止在本 test 上调参。
