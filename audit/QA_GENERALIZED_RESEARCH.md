# QA — 广义多案例研究系统（Research V2）

- 审计对象：`architecture/research-v2` @ `4fa6086`（父提交 `4d94eba`）
- 审计范围：`goe/research_engine.py`、`goe/research_orchestrator.py`、`goe/db.py`（research v2 段）、`goe/cli.py`（`research` 子命令）、`research_results/2026-11-13/{JP_EQ_N225,US_FX_DXY,CM_ETF_SLV}`、相关测试
- 方式：只读代码/产物 + 定向测试（`tests/test_research_orchestrator.py tests/test_research_v2.py`，11 passed）
- 时限：约 6 分钟，未重跑 243 全量测试

## 结论（Verdict）

**有条件接受（CONDITIONAL ACCEPT）**：三案例确实跑在同一执行器上，PIT 对齐正确，状态均 `INCONCLUSIVE`，记忆层为追加式；但“按资产类别的测试注册表”名不副实，测试模板仍按 `case_kind` 硬编码具体标的与假设 ID，新增同类异市场案例会错跑或崩溃；编排器对 BLOCKED 案例无重试上限。上述问题不推翻三案例证据，但限制“广义化”主张，需在文档措辞与编排器上修正后方可称通用引擎。

## P0

无。三案例产物齐全、可读、PIT 无穿越、状态诚实，未发现会推翻当前结论的阻断级缺陷。

## P1

### P1-1 “资产类别测试注册表”并非真正注册表，模板硬编码日本/美国标的
- `execute_spec` 实际是 `if spec.case_kind == "equity_event" / "fx_level" / "commodity_event"` 三个分支（`research_engine.py:121,188,221`），不存在按 `asset_class` 查表的 registry。
- 分支内部把 peer 写死：`JP_EQ_TOPIX/TW_EQ_TAIEX/KR_EQ_KOSPI/GX_FX_USDJPY`（`:122-124`）、`US_EQ_SPY/CM_MET_GC/...`（`:222`），假设 ID 也写死为 `H-EQJP-*`、`H-FX-*`、`H-CMD-*`。
- `learned` 用 `f"{topix:+.2%}"` 等直接格式化（`:180-185`），一旦 peer 缺失（`rv()` 返回 `None`）即 `TypeError`；即一条“equity_index”新案例（如 SP500）若缺 TOPIX/TAIEX/KOSPI 会直接崩溃，而不是降级为 `INSUFFICIENT_DATA`。
- 因此：**无 per-ticker executor = 真**；**测试按资产类别泛化 = 仅名义成立**。三案例能跑是因为 spec 的 peer 集与分支硬编码恰好匹配。

### P1-2 BLOCKED 案例可被无限重选，无尝试计数/退避
- `next_case()` 只检查 `research_v2_findings` 是否存在（`research_orchestrator.py:56-59`），不检查 workflow 是否 `BLOCKED`。
- `run()` 异常时置 `BLOCKED`（`:45-47`），但失败不产生 finding，故下次 `research next` 仍选中同一案例，可无限重试；无 attempt 计数、无 quarantine、无退避。
- 固定顺序 `nikkei → dxy → silver`，不按优先级/证据就绪度选择；“自动选择”实为“首个未跑”。

### P1-3 三案例新产物未入版本控制，HEAD 内证据与工作树不一致
- `git status` 显示 `research_results/2026-11-13/{JP_EQ_N225,US_FX_DXY,CM_ETF_SLV}/` 均为 untracked；HEAD 提交只含旧 `N225/`。
- 旧 `N225/finding.json`（`RC-20261113-JP_EQ_N225-455ff8e1a32f`）与新 `JP_EQ_N225` 同事件 2026-11-06，但 peer 集不同（旧含 HSI/CSI300/IEF/HYG），且未标注“取代/历史版本”。
- 影响：以 commit 为准的复现/验收拿不到三案例证据；同一案例存在两条未标注关系的证据链。建议提交产物并加 `supersedes` 说明。

## 关键核验（证据）

### 1. 三案例确实不同、同一引擎
| 项 | JP_EQ_N225 | US_FX_DXY | CM_ETF_SLV |
|---|---|---|---|
| asset_class / case_kind | equity_index / equity_event | fx / fx_level | commodity / commodity_event |
| 事件日 | 2026-11-06 | 2026-11-11 | 2026-06-09 |
| 问题 | 本地/北亚/全球/日元/政策/基本面 | 利率/风险/宽美元/数据伪影 | 美元/实际利率/风险/供给 |
| 测试数 | 6 | 4 | 5 |
| finding 状态 | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE |
| 假设结果 | 3 supported / 1 weakened / 2 insufficient | 2 supported / 1 weakened / 1 insufficient | 1 supported / 3 inconclusive / 1 insufficient |

三者资产类别、事件日、问题、测试集、结果结构均不同，**不重复**。DXY 与 SLV 共用美元/利率/风险代理与 SPY/IEF/VIX peer，属模板部分重叠，但问题与结论不同；N225 证据最强，SLV 为弱信号/负结果案例（percentile=False），仍有保留价值。唯一弱点是 SLV 事件日（06-09）距决策日（11-13）约 5 个月，是历史问题而非当前异常，新鲜度不足。

### 2. PIT 与诚实性
- N225：N225/TOPIX/TAIEX/KOSPI 均为 `2026-11-06`；SPY/QQQ/VIX/USDJPY 均为 `2026-11-05`（前一美股交易日），**prior US 而非同日，正确**。
- DXY：全部 `2026-11-11` 同日；FX 收盘语义特殊处理（`research_engine.py:95-96`）对本案无副作用（peers 全 same_day）。
- SLV：全部 `2026-06-09` 同日。
- 所有 observed 日期 ≤ as_of `2026-11-13`；`data_hash` 只取 `returns.loc[:event]`；`hist` 截断到 event。未见未来数据。
- 注意：N225 的 `reversal_test` 使用 event 后 3 根 bar（`2026-11-09..11`），在 as_of 视角合法且注明“only bars after event through as-of”，但相对事件本身是事后信息，不应计为独立解释证据。
- 诚实性：三案例均 `INCONCLUSIVE`；`findings.md` 末尾 `DISCOVERY VALUE: NOT VALIDATED`；notes 明确 “association only”“no causal identification”“cannot establish causality”；缺失数据标 `INSUFFICIENT_DATA`（政策日历：“not proof no policy news”）。无因果/alpha 过度声明。未发现“支持”被写成因果结论。
- 小瑕疵：finding 级 `status` 恒为 `INCONCLUSIVE`（`:260`），与假设级 `SUPPORTED_BY_AVAILABLE_EVIDENCE` 并存，导致状态字段不承载信息，也使编排器 `COMPLETED` 分支不可达。

### 3. 持久记忆（追加式）
- 候选：`upsert_research_candidate` 对已有 id 校验 as_of/instruments/theme 不变；status 插入式，后续只能走 `set_research_status`，completed/archived 不可被重开（`db.py:832-934`）。
- 假设：首次插入，后续 `UPDATE` 当前快照但每次写 `research_v2_hypothesis_revisions`（`INSERT OR IGNORE`，hash 去重，source=`candidate_scan`/`research_execution`），历史可追（`:956-988`）。
- 证据：`research_v2_evidence` 以内容 hash 为主键 `INSERT OR IGNORE`（`:900-909`）。
- Finding：`INSERT OR IGNORE`，`finding_id = RF-{rid}-{input_hash[:8]}`，重跑同数据不覆盖、不同数据生成新 id（`:990-1001`）；无 UPDATE/DELETE API。注：物理层无触发器，不可变性靠 API 约定。
- 工作流：`register` 仅在状态为空时置 `PLANNED`，重扫不重置（`:35-37`）；测试 `test_orchestrator_runs_and_records_workflow` 明确断言 rescan 后仍为 `INCONCLUSIVE`，已通过。
- 测试证据：测试级 evidence 落在 finding payload 与 `tests.json`，未单独写入 `research_v2_evidence` 表；可接受但检索性弱。

### 4. 编排器与 CLI
- 状态集 `STATES` 11 个（`:11-13`），实际只用 `PLANNED/EVIDENCE_PENDING/TESTING/INCONCLUSIVE/COMPLETED/BLOCKED`；`DETECTED/EVALUATED/REVIEW_PENDING/ARCHIVED` 未用。
- CLI：`research run|next|status` 已实现（`cli.py:353-390`），`status` 输出 workflow/findings/latest；`next` 无案例时返回码 1。`run --case all` 串行三案例。
- 无内部无限循环；但见 P1-2，BLOCKED 无隔离；`next_case` 每次对三个 spec 调 `register`，会重复追加 `research:planned` 事件（事件噪音，不重置状态）。

## 建议（按优先级）
1. P1-1：把 `case_kind` 分支改为显式 `TEST_REGISTRY[asset_class]`，测试函数接收 spec/peer 映射，缺数据返回 `None` 并降级而不是格式化崩溃；假设 ID 由 spec 提供，不在模板写死。
2. P1-2：`next_case` 跳过 `BLOCKED` 或加 `attempts`/`last_error` 与最大重试；优先级排序替代固定顺序。
3. P1-3：提交三案例产物；旧 `N225` 标注 `superseded_by`。
4. P2：finding 状态由测试结果映射（如 `INCONCLUSIVE`/`PARTIALLY_SUPPORTED`），或明确其为“发现等级”而非证据等级；为 findings 表加禁改触发器；补一个非日本 equity spec 的回放测试，证明泛化。

**最终：三案例可作为“同一引擎、三种资产类别”的证据接受；广义“资产类别注册表”主张暂不接受，需修正 P1-1/P1-2 后再复核。**
