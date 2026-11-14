# V2 研究最终复验 — QA_V2_RESEARCH_CLOSURE

- 复验对象：冻结提交 `9f98e1c`（代码 `08dd069`），2026-11-15（Asia/Hong_Kong）
- 范围：`audit/QA_V2_FINAL_RESEARCH.md` 所列 P1、`evaluation/v2_candidates_20_2026-11-13.json`、评估文档、A→B 文档/DB、新缺陷
- 方式：只读静态检查 + 已跟踪 JSON + 只读 DB（`immutable=1`）；未重跑评估、未改代码；仅写本文件
- 限制：单次、短时复验；DB 是共享工作副本且与本次 artifact 不同步（见 P2-1）；审计开始时工作树已有 4 个未提交文档改动（`TEST_RESULTS.md`、`audit/EXECUTION_STATE.md`、`audit/V2_FINAL_ACCEPTANCE.md`、`audit/V2_ISSUES.md`）；回复前工作树又出现未提交的 release 文件修复（`goe/release.py`、`tests/test_contracts.py`）及 `audit/QA_V2_RELEASE_CLOSURE.md`，属工程范围，不在本文件研究判定内。研究对象（`08dd069` 的 hypotheses/artifact）未变。

## 总判定

**PASS WITH ISSUES（不可作纯净 PASS；严格按“原审计 P1 全闭”口径则仍不可签署）**

- 本次清单中的 4 项检查通过；发现 **1 项新的窄口径 P1**：20 条 artifact 的 `RC-20261113-04` 含非法 hypothesis status `obtainable`，且其证据进入候选 supporting evidence。
- 另发现原 `P1-C-3` 的“可用性高估”部分未随 `08dd069` 修复（CN sector 的 UST `available` 等，见 P1-R1）；该项不在本次 5 项清单的字面范围内，但按 `QA_V2_FINAL_RESEARCH.md` 的完整 P1 口径仍存在。
- **P0：无。**
- **DISCOVERY VALUE：NOT VALIDATED**（结论未变，见末节）。

## 逐项复验

### 1. untestable 假设的 evidence_for / supporting evidence — PASS

- 20 条 artifact、104 个假设，其中 **57 个 `untestable`**；逐条检查 `evidence_for` 全部为空，0 违例。
- 候选级聚合 `evidence` / `evidence_for` 中没有任何 `hypothesis_id` 属于本轮 `untestable` 假设（0 条泄漏）；`untestable` 假设也没有 falsifier。
- 代码路径已按资产类别收口：FX `H-INT`、commodity `H-SUPPLY`/`H-ART`、crypto `H-REG`/`H-FLOW` 均只在可检验时才带证据（`goe/hypotheses.py:239-245, 263-288, 297-313`）。
- 新测试 `test_all_untestable_hypotheses_have_no_supporting_evidence` 覆盖 equity/FX/rates/commodity（含 SLV）/crypto 共 8 个 case；本次实跑 `tests/test_hypotheses.py -k "untestable or self_benchmark"` 为 **4 passed**。
- 残留（P3）：`goe/hypotheses.py:263` 用 `if False else []` 硬置空，属死代码；`goe/contracts.py` 仍只依赖测试、未把“`untestable ⇒ evidence_for 为空`”写成 validator 不变量。当前数据干净，但回归保护是测试级而非 schema 级。

### 2. 结构性差异 / SLV / benchmark — PASS（有 P2 残留）

- 104 个假设、89 个不同 `(id,type,status)` 三元组；按每个候选的 `(id,type,status)` 集合计，**18 种结构签名**（falsifier 签名也是 18 种），满足 ≥10；每个候选 4–7 个假设，无 `H1`–`H5` 旧五模板，ID 已按现象命名空间化（17 个前缀）。
- 仍有 2 组重复结构签名（US equity、agriculture 内部），但整体差异度已满足本次阈值。
- SLV（`RC-20261113-05`）：`H-SILV-ART` 已为 `untestable`、`evidence_for=[]`、无 falsifier，artifact 中不再有 `futures`/换月作为支撑证据；futures-only 的 artifact 层面已实质修复。
  - 残留（P2）：该假设的 label 仍为“换月/连续合约数据伪影”，implications 仍写“换月日附近跳变；原始合约与连续合约不一致”，`critical_unknowns` 仍有“换月因子”。对白银 ETF 属措辞残留，但已不影响证据/测试/tier。
- benchmark：`goe/research_triage.py:192` 以 `i in fs.prices.columns and i != iid` 排除自身；当前 20 条候选未发现以自身作 benchmark 的 `available` 标记（N225 用 TOPIX、CN1000 用 CSI300 等均非自身）。
  - 残留（P3）：`test_no_self_benchmark_available` 只验证传入 `benchmark=False` 时 test 为 `obtainable`，没有直接覆盖 triage 的 `i != iid` 路径；测试名强于实际。

### 3. P1-F 2025-12-31 独立性 — PASS

- `evaluation/new_window/V2_EVALUATION_RESULTS.md` 标题已改为 `## Exploratory window (not independent)`，正文明确“2025-12-31 is not an independent test (used in a V1 case)”；D 1.000 vs C 1.500，P@3 0.00 vs 0.67；`DISCOVERY VALUE: NOT VALIDATED`。
- `evaluation/V2_EVALUATION_RESULTS.md`、`evaluation/new_window/RESULTS.md`、`audit/V2_FINAL_ACCEPTANCE.md` 均保持 exploratory/not independent 与 NOT VALIDATED。
- 全仓检索 `Test split` / `held out` / `held-out` / `on test` 已无陈旧表述（仅“no independent test split”类否定句）。
- 残留（P2）：`evaluation/RESEARCH_EVALUATION_PROTOCOL.md:64-68` 的 2025 段写“new frozen window / not a future window / selection-quality check only”，未直接写“exploratory/not independent”（结论与 NOT VALIDATED 已写明）；`audit/V2_FINAL_ACCEPTANCE.md:3` 仍写“166 offline passed”，同文件 engineering 行写 178；`:6` 仍写“15 distinct hypothesis signatures”，与当前 18 不一致。

### 4. A→B 真实 refused / 无成功 / 候选保留 — PASS

- `audit/V2_FINAL_ACCEPTANCE.md`：latest run `refused`（S8 `no_registry_identity`），A persisted `not_completed:refused`，`never success`；earlier run 为 process-level error，不再表述为 B 拒答。
- DB（只读）：task `not_completed:refused`；result 2 `semantic_status=refused`、`run_ok` 列为 0；`RC-20261113-12` 仍存在（status `handoff_failed`、tier A、rank 1）；无 `ok_valid`/`research_complete` 成功记录。
- 残留（P2）：历史 result 1 仍为 `rejected`（当时 env error），未回填为 `error`；`A→B` 文档的“earlier run now mapped to error”只描述当前 adapter 映射，不是历史行状态。

### 5. 新 P0/P1

#### P1-N1（新，窄口径）：`RC-20261113-04` 使用非法 hypothesis status `obtainable`

- 位置：`evaluation/v2_candidates_20_2026-11-13.json:3920-3923`（`H-ENER-CRACK`，`"status": "obtainable"`）；根因在 `goe/hypotheses.py:370`（把 test 的 `data_status="obtainable"` 误写进 hypothesis status）。
- `goe/contracts.py:22` 允许的 status 只有 `open/supported/contradicted/untestable`；`validate_research_candidate` 在 `goe/contracts.py:81-82` 会抛 `bad hypothesis status obtainable`。本次用 validator 检查 20 条，**1/20 失败**（`RC-20261113-04`）；5 条生产 artifact 全部通过。
- 影响：该 hypothesis 的 1 条 `evidence_for`（“能源价格可观察”）被 `research_triage` 聚合成候选 `evidence`/`evidence_for`（RC-04 各 3 条，含该条）；同时因 `open_ids` 只收 `open`，`H-ENER-CRACK` 没有 falsifier，形成“有支撑证据、无检验、非 open/非 untestable”的自相矛盾状态。rationale 的 `open_hypotheses=2` 与 5 个假设中 2 个 open、2 个 untestable、1 个非法 status 对应。
- 严重度判断：仅 1 条 intelligence tier 候选（tier/rank 未受影响），但它是 20 条验收 artifact 中唯一无法通过自身 RESEARCH CONTRACT 的候选；且生成/测试路径未调用 `validate_research_candidate`，所以 178 tests 全绿仍可漏过。建议一行修复（`obtainable` → `open`，并补上对应 falsifier；或改 `untestable` 并清空 evidence）并加“所有生成假设 status 必须在允许集合”的测试。

#### P2（不阻断）

- **P2-1 DB 与 artifact 不同步（新可见）**：只读 DB 有 20 candidates、**204 hypotheses / 167 evidence**；当前 artifact 为 **104 hypotheses / 144 条去重 evidence**。约 100 条旧命名空间 hypothesis 行（如 `RC-04:H-ART`、`H-SUPPLY`）与约 23 条旧 evidence 仍在 DB。`08dd069` 只对 evidence 加了 `DELETE`（`goe/db.py:838-841`），hypotheses 仍按新 ID 累加；`research_integrity()` 只查 orphan/FK，查不出“FK 有效但已过时”。DB 未跟踪，且最后写入(00:05)早于修复提交(00:06)，属工作副本问题，不是 artifact 问题。
- **P2-2**：SLV `H-ART` 的 label/implications/`换月因子` 仍是期货措辞（见上）。
- **P2-3**：`V2_FINAL_ACCEPTANCE.md:3,6` 的 166 tests / 15 signatures 陈旧；PROTOCOL 2025 段未字面写 not independent。
- **P2-4**：A→B 历史 result 1 仍 `rejected`；`V2_ISSUES.md` 工作树版本称“futures-only artifact test”，但 `tests/` 中没有直接断言“SLV 不得使用期货模板”的测试（只有 untestable-empty 覆盖 SLV 的间接测试）。
- **P2-5**：`goe/hypotheses.py:263` 的 `if False` 死代码；`test_no_self_benchmark_available` 未覆盖 triage 自身排除逻辑。

## 剩余 P0/P1

- **P0：无。**
- **P1：**
  1. **P1-N1（新）**：`RC-04 / H-ENER-CRACK` 非法 status `obtainable`，artifact 无法通过自身 contract，且非 open 假设的证据进入候选 supporting evidence。
  2. **P1-R1（原 P1-C-3 的未覆盖部分，非本次清单字面项）**：可用性高估仍在——`goe/hypotheses.py:159` 对全部 sector 无条件 `_test("H-STYLE", …, "UST", "available")`，`RC-20261113-07`（CN_SEC_EV）因此获得 UST `available`；commodity 的 `cross_asset` 只要 SPY/QQQ/DXY/GC 任一存在即 `available`（`goe/research_triage.py:185-187`），`RC-04/05` 的 `DXY/UST` 也标 `available`。当前这些候选均为 intelligence tier（未抬升 tier/rank），但原审计将其列为 P1；若按原 P1 全闭口径，不能签署。

## DISCOVERY VALUE

**DISCOVERY VALUE: NOT VALIDATED.**

- 2025-12-31 已用于 V1 validation case，不是独立 test；该窗口 D 1.000 < C 1.500（A 1.083/B 0.917），P@3 D 0.00 vs C 0.67。
- 2021-12-31 在 V2 gate 改动后被复用，只能算 exploratory：全样本 D 0.833 < C 0.979；该日 D 0.750，C 0.583，A 0.833。
- 无独立 test split、无 human/expert labels、单 LLM rater 且评分不稳定；卡片测的是资产选择 worthiness，不是 V2 research question 质量。
- 未发现 test-date tuning；不得把 2025 结果表述为独立验证或 V2 优于 A/B/C。结论保持 **NOT VALIDATED**。

## 备注

- 冻结代码与 artifact 一致：`evaluation/v2_candidates_20_2026-11-13.json` 的 SHA-256 与 `git show 08dd069:...` 完全相同（`6461fb24…e5b1`）。
- 审计期间未改代码；本次唯一写入为本文件。工作树 4 个文档改动在本审计开始前已存在。
- 建议的签署前最小动作：修复 `P1-N1`（一行 status + 对应 falsifier + 生成后 validator/测试）；若沿用原审计 P1 全闭口径，同时处理 `P1-R1`。两项均不影响 DISCOVERY 的 NOT VALIDATED 结论。
