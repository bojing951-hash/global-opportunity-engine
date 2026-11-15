# QA_RESEARCH_FINAL2 — 独立研究终验（只读）

- 时间：2026-11-15（Asia/Hong_Kong），timebox 6 分钟
- 仓库：`global-opportunity-engine`
- Branch：`architecture/research-v2`
- HEAD：`1a32b1f`（仅 release proof 文档提交）；产品代码：`9f7e54e`
- 范围：只读复核；除本文件外未改代码/DB/artifact；未重跑全量 230 测试（引用 `9f7e54e` 的 release proof/JUnit/log，并独立运行 23 个相关测试）
- **结论：PASS WITH ISSUES（仅 P2）；无新的 P0/P1 研究缺陷。**
- **DISCOVERY VALUE: NOT VALIDATED。**

## 1. 四维与当前 20 条候选 — PASS（P2）

官方 artifact：`evaluation/v2_candidates_20_2026-11-13.json`（as_of 2026-11-13）。
`goe.contracts.validate_research_candidate` 逐条校验：**20/20 PASS，0 ContractError**。

| 维度 | 当前分布 |
|---|---|
| `research_queue` | **research 0 / watch 4 / archive 16** |
| `research_worthiness` | high 1 / medium 3 / low 16 |
| `evidence_readiness` | ready 0 / partial 4 / missing 16 |
| `handoff_eligibility` | **eligible 0 / a_retained 20** |
| `priority_tier` | intelligence 20 |

- 20 个唯一 `research_id`，20 个唯一 `research_theme_id`；artifact 与 `data/goe.db` 的 20 条 payload **逐字段 0 diff**，DB `status` 全部 `intelligence`。
- N225：`RC-20261113-JP_EQ_N225-455ff8e1a32f` = **high worthiness / partial readiness / watch / a_retained / intelligence**；quality audit 显示 1 条 measured discriminator、coverage 0.25、`decision_value_flag=True`，但未达到 2 条 measured 的 research 门槛。
- 4 条 watch：N225（high/partial）、TAIEX（medium/missing）、QQQ（medium/missing）、XLV（medium/missing）。
- worthiness 与 readiness 计算相互独立（`goe/research_triage.py:240-251`）：存在 high+partial→watch、medium+missing→watch、low+partial→archive 等组合。
- **P2（已知，不阻断）**：`handoff_eligibility` 由 `priority_tier` 决定（`research_triage.py:295`），`research_queue == "research"` 同样由 tier A/B/C 决定（`:296`），因此当前实现中 `eligible ⟺ research_queue=="research"`；四字段是独立 schema/取值域，但 queue 与 eligibility 在本版共线，不能表达“进入研究队列但暂不移交”的中间态。

## 2. A→B 守卫 — PASS

- `eligible_for_handoff`（`goe/integration/research_handoff.py:95-107`）要求**显式** `handoff_eligibility == "eligible"` **且** `priority_tier in (A,B,C)` **且** `research_readiness == "evidence_ok"`；仅 tier/readiness 不够。
- 当前对 artifact 运行 `eligible_for_handoff` 返回 **[]**。
- CLI `triage --handoff`（`goe/cli.py:321-325`）在 `eligible == []` 时直接打印说明并 **return 3**，发生在 adapter 构造、`handoff_v2`、`persist_v2_result` 之前，**不创建 task、不写 result**。
- DB 实测：`research_v2_tasks = 0`、`research_v2_results = 0`；20 条候选（含 4 条 watch/intelligence）全部保留，未删除、未改写为 success。
- 既有拒绝语义（历史 QA `audit/FINAL_RESEARCH_QA.md`：`RC-20261113-12` 的 `not_completed:refused`、`run_ok=0`，候选保留为 `handoff_failed`）与当前 `persist_v2_result`（`research_handoff.py:62-92`）一致：仅 `status=="ok" and semantic_status=="ok_valid"` 才可能 `research_complete`；refused/rejected/timeout 只记录 `not_completed:<sem>`、保留候选、标记 `handoff_failed`。相关测试 `tests/test_research_v2.py:39-54,183-196`、`tests/test_research_identity.py` 通过。
- **P2（历史证据缺口，本轮无影响）**：当前 DB 已是干净快照（tasks/results=0），先前 refused task 只存在于历史审计与测试中，不能从当前 DB 直接复现；但当前 0 eligible 路径已由代码顺序和无 task 的 DB 状态验证。

## 3. Research quality audit — PASS

- 用当前 artifact 重跑 `goe.research_quality.evaluate_candidates`，与 `evaluation/research_quality_audit.json` **完全相等（含 20 行明细与全部汇总字段，0 diff）**。
- `evaluation/RESEARCH_QUALITY_AUDIT.md` 与 JSON 一致；数字：n=20，research 0，watch 4，eligible 0，measured≥2 为 0，decision-value flags 4，mean measured coverage **0.075**，mean question structure **0.988**，duplicate claims 0。
- 该审计是**描述性**的（`goe/research_quality.py:1-12` 明确 “NOT a valuation / NOT an independent performance label”，“no independent human labels”）；`discovery_value` 硬编码为 `NOT VALIDATED`，note 明确不得当作投资价值或已验证分数。
- **无 synthetic validation**：quality audit 基于真实 20 条候选 artifact，不用合成市场/合成标签证明发现价值；合成数据仅用于单元测试的道具（`tests`），不进入 DISCOVERY 结论。
- **无 test/date overfitting**：评测协议预先固定 split，2021-12-31 因复用被降级为 exploratory，2025-12-31 明确“非未来窗口/非独立”，D 1.000 < C 1.500，结论保持 NOT VALIDATED；产品代码未发现按候选 ID/特定 as_of 调参的硬编码（仅有 universe 名单与数据源日期注释）。
- **DISCOVERY VALUE: NOT VALIDATED** 在代码、JSON、MD、`PROJECT_STATE.md`、`FINAL_ACCEPTANCE_CURRENT.md`、`EVALUATION_PROTOCOL_V3.md` 中口径一致。

## 4. 外部证据（PIT / 单曲线 / OIS / consensus）— PASS（P2）

- `config/evidence_sources.yaml`：`consensus.enabled: false`、`ois.enabled: false`；`curve_type: policy_path_proxy`（注释明确只有 licensed term-OIS 才能用 `"ois"`）。
- PIT：`consensus_evidence` 与 `ois_evidence` 均要求 `available_at <= as_of`、`publication_time <= as_of`、`publication_time <= available_at`（`goe/evidence/external.py:65-67,124-128`）；测试覆盖 future publication、错误 actual target、stale。
- 单曲线：只允许同一 `currency+region+curve_type`，`provider`、`units` 各唯一，`curve_id` 唯一；2Y/10Y 必须同一观测日、同一可用日，拒绝跨币种/跨曲线/缺 tenor/日期不一致（`external.py:137-160`）；测试 `tests/test_external_evidence.py` 通过。
- 无 false OIS：配置为 proxy，代码仅在 `curve_type=="ois"` 时输出 “OIS 曲线 2s10s”，proxy 输出 “政策路径代理 2s10s（非 OIS）”；`data/policy_curve.csv` 的 source 也写 “not term OIS”。
- consensus 诚实：`data/consensus_revisions.csv` 不存在，adapter 关闭；20 条候选的 evidence class 仅 `observed_fact` 25 条 + `statistical_association` 7 条，external-like evidence 0 条；候选明确写“一致预期/财报修正未接入”，未伪造一致预期/OIS 值。
- **P2**：
  1. 本地 `data/policy_curve.csv` 仍是旧 schema（`series_id,tenor,date,value,available_at,source`），与新版 `ois_evidence` 要求的 curve 元数据不匹配；因 `enabled:false` 当前不被消费，但若启用会静默返回 None，属数据/文档陈旧。
  2. `PROJECT_STATE.md` 称“future publication/vintage ... rejected”，代码只严格校验 `publication_time`/`available_at`，未把 `vintage` 当日期解析；若 vintage 定义为日期字符串，这是文档精度问题（当前无 live feed，无实际影响）。

## 5. P0 / P1

- **P0：无。**
- **P1：无新增。**
- **P2（不阻断，已列明）**：
  1. queue 与 handoff_eligibility 由同一 tier 条件决定，当前共线；四维无法独立表达中间态。
  2. `exports/research_candidates_2026-11-13.json`（11:06）是旧导出，20 条四字段全为 null；正式 QA 使用 `evaluation/v2_candidates_20_2026-11-13.json` 且与 DB 0 diff。旧导出不应作为验收依据。
  3. `audit/FINAL_ACCEPTANCE_CURRENT.md` 有陈旧口径（如 “0 research / 20 intelligence” 未写成 4 watch/16 archive，Stop state 仍写 “CI CROSS-OS: BLOCKED” 而表格写 PASS）；不影响研究 gate。
  4. 本地 `data/policy_curve.csv` 旧 schema，见 §4；`vintage` 未按日期校验，见 §4。
  5. 当前 DB 无 live refused task（干净快照），历史拒绝语义靠历史审计与测试覆盖。

## 6. 验证证据

- `git diff --stat 9f7e54e..HEAD`：仅 4 个 release proof 文件；产品代码与 `9f7e54e` 相同；worktree clean。
- `audit/releases/release_9f7e54edc2.json` / `audit/test_evidence/20261115T084633Z_9f7e54edc2.{proof.json,log,junit.xml}`：commit `9f7e54e`、`git_dirty=false`、**230 passed / 0 failed / 10 deselected**、exit 0。
- 独立 focused tests：`tests/test_external_evidence.py tests/test_research_identity.py tests/test_research_quality.py tests/test_research_v2.py` → **23 passed**（只读运行，禁用 pytest cache/bytecode）。
- 独立脚本校验：contract 20/20；DB/artifact payload 0 diff；`eligible_for_handoff(artifact) == []`；DB tasks/results 0；quality audit 与 JSON 逐字段相等。

## 7. 最终允许状态（Final allowed state）

**RESEARCH GATE: PASS WITH ISSUES (P2 only) — no new P0/P1.**  
当前：**20 candidates / 0 research / 4 watch / 16 archive / 0 handoff eligible**；N225 = **high/partial/watch/retained**。  
**A→B: NO-GO**（0 eligible，0 task，20 条全部 retained；不得绕过显式 eligibility）。  
**PHASE 2: PARTIAL；DISCOVERY VALUE: NOT VALIDATED**（无人类/专家标签、无独立未来窗口；不得宣称发现有效、alpha、mispricing 或已验证的 OIS/consensus 证据）。  
**允许的表述**：研究 gate 通过（P2 only）、20/20 contract、A→B 被正确阻断、quality audit 可精确复现、外部证据 PIT/单曲线、proxy 未冒充 OIS。  
**不允许的表述**：任何 “DISCOVERY VALIDATED / 优于基线 / 可交易 / 一致预期或 term-OIS 已接入” 的声明。
