# QA — 广义研究系统最终验收（Generalized Research Final QA）

- 审计对象：`architecture/research-v2` @ `d5f48c9`（code `ad203d9`，proof `bb6c2b7`）
- 方式：只读代码/产物 + 定向测试（`tests/test_research_identity.py tests/test_research_orchestrator.py`，8 passed）+ 只读 DB 查询 + CLI 试跑
- 时限：约 4 分钟；未重跑 243 全量测试（发布清单声明 243 passed，见 `audit/releases/release_bb6c2b7b05.json`）

## 结论（Verdict）

**有条件接受（CONDITIONAL ACCEPT）**：三案例确实由同一 `research_engine.execute_spec` 执行，PIT 对齐正确，状态均为 `INCONCLUSIVE`，无 alpha/因果过度声明，`research run/status/next` 可用，BLOCKED 重试已被跳过；但“findings 不可变/追加式证据”在**文件产物层不成立**，且“按资产类别的测试注册表”仍只是 `case_kind` 三分支加角色参数，泛化主张仍被高估。三案例证据可接受，但不能无条件接受“不可变记忆 + 通用资产类别引擎”的完整主张。

**Status：CONDITIONAL ACCEPT（P1-1 必须修复后才可称 findings 不可变；P1-2 修复/降级措辞后才可称资产类别通用引擎）。**

## P0

无。未发现会推翻三案例结论、伪造数据或把 INCONCLUSIVE 写成成功的阻断级缺陷。

## P1

### P1-1 `findings` 文件产物会被覆盖，DB 中的历史 finding 指向被替换的 artifact

- `goe/research_engine.py:293` 每次固定写 `out_dir/as_of/asset`，`:296-314` 对 `finding.json/plan.json/evidence.json/tests.json/findings.md` 无条件 `write_text`。
- DB 侧仅 `INSERT OR IGNORE`（`goe/db.py:997`），同一 `finding_id` 不覆盖；但新数据会生成新 finding id，却写回**同一路径**。
- 实际只读 DB 证据：`RF-RC-...-a715b958` 的 `artifact_path` 指向 `research_results/2026-11-13/JP_EQ_N225/finding.json`，该文件现在的内容却是 `RF-RC-...-d23f1f99`（由 13:45 的重跑覆盖）。即 DB 保留了旧 payload，但 artifact 已漂移，旧 finding 的外部证据链接不再自洽。
- 另：仓库内三份 artifact 的 `code_commit` 均为 `ad203d9`，而当前 HEAD 为 `d5f48c9`；`git diff ad203d9..HEAD -- goe/research_engine.py` 为空，数值可信，但“当前 HEAD 可复现的 artifact”这一层 provenance 已不精确。
- 影响：违反“findings immutable / append-only”的对外承诺；重跑同目录会静默替换历史证据文件。建议按 `finding_id` 分目录或写一次即拒绝覆盖。

### P1-2 泛化仍为按 `case_kind` 的三条硬编码模板，不是资产类别注册表

- `execute_spec` 仍是 `if spec.case_kind == "equity_event" / "fx_level" / "commodity_event"` 三个分支（`research_engine.py:136/203/236`），没有 `asset_class -> test template` 注册表。
- `roles` / `hypothesis_ids` 已可由 spec 注入（较上一轮有实质改进），但测试语义和文案仍写死日本/美国标的：`TOPIX`、`Taiwan`、`Korea`、`Japan`、`prior USDJPY`（`:137-153`, `:195-201`），默认 hypothesis id 也写死 `H-EQ-LOCAL` 等（`:171-193`）。
- 直接后果：新增一个非日本 `equity_index` 案例复用 `equity_event` 时，会得到“TOPIX/Taiwan/Korea”语义的测试解释和默认假设，而不是该市场的测试模板；三案例能通过是因为 spec 与分支恰好匹配。
- 这是上一轮 P1-1 的**部分修复、未闭环**；若继续宣称“按资产类别泛化的研究引擎”，应改注册表或把主张降级为“三种 case-kind 模板 + 可配置 peers/roles”。

## P2

1. **旧 N225 证据链未标注取代**：`research_results/2026-11-13/N225` 仍 tracked，code commit `8266fa6`，无 `superseded_by`/历史版本说明；CLI 仍保留仅支持 nikkei 的 `research-case`（`goe/cli.py:392-403`, `goe/research_exec.py:108`）。同一 N225 事件存在两条未标注关系的证据链，易误用。
2. **finding 级 status 恒为 `INCONCLUSIVE`**（`research_engine.py:275`），与假设级 `SUPPORTED_BY_AVAILABLE_EVIDENCE` 并存，`COMPLETED` 分支实际不可达；状态字段不承载信息。
3. **BLOCKED 只跳过、无解除/尝试计数**：`next_case` 跳过 BLOCKED（`research_orchestrator.py:56`），可避免无限重试，但瞬时失败会永久隔离；无 attempts/last_error/人工 unblock 路径。
4. **DXY percentile 的解释力偏弱**：事件是“接近 5 年高位”（水平事件），却用 252 日**日收益**尾部检验（0.67%，97.6% 分位，pass=True）；统计上成立，但与“水平高位”问题不是同一维度，容易过度解读。
5. `research status` 会列出大量未执行 candidate（state=None/findings=0），噪声大；`next_case` 每次先 `register`，重复追加 `candidate_scan/research:planned` 事件（不重置状态）。
6. `research run` 对 INCONCLUSIVE 仍返回 0；不是 fake success（状态会打印），但自动化调用方可能误判为“研究成功”。

## 关键核验（证据）

### 1. 同一引擎、三案例不同测试

| 项 | JP_EQ_N225 | US_FX_DXY | CM_ETF_SLV |
|---|---|---|---|
| asset_class / case_kind | equity_index / equity_event | fx / fx_level | commodity / commodity_event |
| event | 2026-11-06 | 2026-11-11 | 2026-06-09 |
| tests 数 | 6 | 4 | 5 |
| finding status | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE |
| research_id | `RC-20261113-JP_EQ_N225-e4953e300c07` | `RC-20261113-US_FX_DXY-66e350e808c5` | `RC-20261113-CM_ETF_SLV-4da1f0cfcde7` |

- 三份 artifact 均由 `execute_spec` 的 finding 结构产出（`plan.case_kind` 不同、`input_sha256` 不同、`code_commit=ad203d9`）。
- `goe/research_engine.py` 内无按 ticker 的执行分支；`grep` 仅见 `spec.asset` 的取值/存在性检查（`:98`, `:107`）。ticker 定义集中在 `research_orchestrator.py` 的 case factories，属“案例配置”，不是执行器分支。

### 2. PIT、诚实性与 percentile

- N225 data dates：N225/TOPIX/TAIEX/KOSPI `2026-11-06`；SPY/QQQ/VIX/USDJPY `2026-11-05`（前一美股交易日，非同日未来收盘）。正确。
- DXY：所有 peer `2026-11-11` 同日，as_of `2026-11-13` 可见。正确。
- SLV：所有 peer `2026-06-09` 同日。正确。
- 三份 findings 末尾均有 `DISCOVERY VALUE: NOT VALIDATED`；notes 明确 `association only`、`no causal identification`、`cannot establish causality`；缺失数据标 `INSUFFICIENT_DATA`，无 alpha/因果宣称。
- `historical_percentile` 三案例均存在：N225 `-5.96%`，0.40% 分位，pass=True；DXY `+0.67%`，97.6% 分位，pass=True；SLV `-4.17%`，7.5% 分位，pass=False。检验为 trailing 252-session、双侧 5% 尾部，规则明确。

### 3. 追加式记忆 / rescan

- 定向测试 8 passed：`test_rescan_preserves_research_hypotheses_evidence_and_findings`、`test_orchestrator_runs_and_records_workflow` 等覆盖 rescan 后状态/证据/finding 不被重置。
- DB 只读查询：`research_v2_hypothesis_revisions=51`，`research_v2_events=78`；假设状态、workflow 均在；workflow 状态为 INCONCLUSIVE。
- `upsert_research_candidate` 不更新 `status`，completed/archived 不可被 scan 重开（`db.py:832+`）；`add_research_finding` 使用 `INSERT OR IGNORE`（`:997`）。
- **但文件 artifact 可被覆盖（P1-1）**，因此“append-only/immutable”只能在 DB 行层成立，不能在对外证据文件层成立。

### 4. Orchestrator / CLI

- `goe/cli.py:620-627` 注册 `research run|next|status`；实测 `research status` 正确显示三案例 `state=INCONCLUSIVE findings=3 latest=INCONCLUSIVE`。
- 实测 `research next`：`no research case available`，rc=1，无无限重试。
- `next_case` 跳过 `BLOCKED`（`research_orchestrator.py:56`），修复了上一轮“失败案例无限重选”的 P1；但无尝试计数/解除路径（P2）。
- `run()` 异常置 BLOCKED 并 re-raise；未发现内部死循环。

## 最终判定

- **可接受**：三案例同引擎、不同测试、PIT 正确、状态 INCONCLUSIVE、无因果/alpha 过度声明、percentile 与 rescan/workflow/CLI 主路径通过。
- **不可无条件接受**：findings 文件产物可被重跑覆盖（P1-1）；泛化仍是三分支 + 角色参数，不是资产类别注册表（P1-2）。修复 P1-1 并按 P1-2 修正实现或文档措辞后，可升级为无条件接受。
