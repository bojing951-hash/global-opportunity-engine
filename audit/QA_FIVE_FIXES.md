# QA — 五项修复独立验收（HEAD f8bbfaa / code bbed80b）

- 验收时间：2026-11-16（Asia/Hong_Kong）
- 基线：HEAD `f8bbfaa1befb6a4cb312cd1f10a4ad21ef47a76b`，code `bbed80b9deffcc6e735bfa9a565aa720f062b1ce`
- 方式：只读审计 + 现有测试/证据复核；除本文件外未改代码、未改仓库状态
- 结论：**FIVE_FIXES = PASS；SUPERVISED_READY = YES；无 P0 / 无 P1**

## 测试与 CI 证明

- 本地离线套件：`.venv/bin/python -m pytest tests -q -m "not network"` → exit 0；仓库证明日志 `audit/test_evidence/20261116T055858Z_bbed80b9de.log` 明确 `259 passed, 10 deselected`。
- Proof：`audit/test_evidence/20261116T055858Z_bbed80b9de.proof.json`，commit `bbed80b9`，`passed=259 / failed=0 / skipped=0`，required/executed SHA256 一致（`25790a5f…`）。
- Release：`audit/releases/release_bbed80b9de.json`，`git_dirty=false`，test_evidence 259，rerun 259。
- CI：GitHub Actions `verify-release` **run 54**，head `f8bbfaa`，`completed / success`（2026-11-16T06:01:03Z）。

## P1-1 data_hash 覆盖 as_of（含事件后反转）— PASS

- `goe/research_engine.py:125-126`：`data_hash` 由 `returns.loc[:spec.as_of]` 计算，不再截到 event；`input_rows` 同步改为 as_of。
- 现有测试 `test_generic_execution_is_idempotent_and_keeps_artifact` 覆盖同输入幂等：finding_id 不变、artifact 字节不变、DB 仅 1 条 finding。
- `test_post_event_data_changes_input_hash_and_preserves_old_artifact` 覆盖事件后数据变化：finding_id 改变，旧 artifact 目录仍存在。
- 代码路径确认：finding_id = `RF-<research_id>-<input_hash[:8]>`，input_hash 包含 data_hash；新数据 → 新 ID → 新目录，旧目录不被覆盖；同输入重跑命中 existing 分支，幂等。
- 备注（非阻断）：现有测试改的是 as_of 当日 bar；实现按“截至 as_of 全表”哈希，事件后、as_of 前任意 bar 变化同样会改变 hash。

## P1-2 `research:evidence_update` 后候选重新入队 — PASS

- `goe/research_orchestrator.py:81-105`：`next_case` 不再无条件排除有 finding 的候选；仅当最新 finding 之后存在 `research:evidence_update` 事件才允许重入，否则 `continue`。
- `reopen()` 追加新事件并把 workflow 置回 `PLANNED`，不删除旧 finding/事件。
- 测试 `test_finding_can_reenter_after_evidence_update`：无新证据 → `next_case() is None`；reopen 后 → 同一 research_id 重新返回。
- 事件为 append-only 新行，旧 finding 保留；实际 QQQ 事件表中 `research:evidence_plan/evaluated` 均独立追加。
- 残余 P2（非 P1）：`utc_now()` 为秒级精度，finding 与 evidence_update 落在同一秒时 `at > created_at` 不成立，重入会不触发；现有测试因此 `sleep(1.1)`。正常人工/调度间隔下不触发，建议后续改为微秒或序列比较。

## P1-3 register/next_case 保留筛查字段 — PASS

- `register()` 仅在候选不存在时 `upsert_research_candidate`，已存在则完全不重写 payload；`next_case()` 只读候选并调用该 register。
- 测试 `test_register_preserves_screening_fields` 覆盖 worthiness/readiness/queue/handoff/materiality/research_cost/evidence 全字段不变。
- 真实 QQQ 候选 `RC-20261113-US_EQ_QQQ-c6b8c38dbf91` 复核：`research_worthiness=high`、`evidence_readiness=partial`、`research_queue=watch`、`handoff_eligibility=a_retained`、`evidence=[]` 均保留，未被 `_candidate()` 的 medium/partial/watch/a_retained 默认值覆盖；其 `updated_at` 仍为首次写入时间。
- 真实候选无 `research_cost/materiality` 键属原始数据本身未提供，不是被覆盖；合成测试已证明若存在会被保留。

## P2-1 H-TECH 改为 INCONCLUSIVE / 观察非支持 — PASS（intel 一致）

- `goe/research_engine.py:192-195`：H-TECH 固定 `INCONCLUSIVE`，new_evidence 明确 “observation, not independent support”，note 说明不能与 risk-off/duration 分离。
- canonical QQQ finding `RF-…c6b8…-e357c75d`（code commit 6ad3182）：status INCONCLUSIVE，H-RISK supported、H-RATE weakened、H-TECH INCONCLUSIVE、H-DATA insufficient；`tests.relative_underperform_test.pass=true` 仍保留为**事实检验**，但不再映射为假设支持。
- `evaluation/investment_intelligence_qqq.json`：`supported_hypotheses` 仅 `["H-RISK"]`；`H-TECH` 移入 unresolved；新增 `observed_relative_weakness=-0.020797` 与 “observation, not independent support” 说明；`scenarios.base` 同步为 “Best-supported channels: H-RISK; unresolved: H-RATE, H-TECH”；observed_fact 与 finding/evidence 数值一致。
- 残余 P2（文档指向，非当前情报）：旧错误模板 artifact `…-e96d8477/SUPERSEDED.md` 仍指向更早的 `…-2ca1fb5a`，而后者保留旧的 H-TECH SUPPORTED 文本；最新 canonical 应按 DB `created_at` 取 `…-e357c75d`，建议后续把 SUPERSEDED 指向最新 revision，避免读者误读历史 artifact。

## P2-2 US planner 不再使用 inventory/supply；不支持显式化 — PASS

- `goe/research_planner.py:39-48` 新增 `us_equity_relative` 分支：required 为 event asset、US market、VIX、IEF、DXY、gold、intraday leadership，**无 inventory/supply**；availability 明确 intraday/implied rates 缺失。
- 未知 case_kind 走 `else`：`method=UNSUPPORTED_TEST`、`availability_status="UNSUPPORTED_TEST: no planner for …"`；测试 `test_unknown_case_kind_is_explicitly_unsupported` 覆盖。
- 真实 QQQ finding plan 的 `case_kind=us_equity_relative`，未出现 inventory/supply 数据需求。
- 残余 P2（防御性，非当前流程）：`execute_spec` 在 case_kind 未注册时仍会按 asset_class `select_test` 回退；生产编排只生成四种已知 case_kind，故当前不可达。建议后续让“planner 判不支持”与 executor 行为一致。

## 最终判定

| 项 | 结果 |
|---|---|
| P1-1 | PASS |
| P1-2 | PASS（P2：同秒时间戳竞态） |
| P1-3 | PASS |
| P2-1 | PASS（P2：SUPERSEDED 文档指向偏旧） |
| P2-2 | PASS（P2：executor 未知 case_kind 回退，当前不可达） |
| 真实 QQQ 候选字段 | PASS（保留） |
| 259 测试 / proof | PASS |
| CI run 54 @ f8bbfaa | success |

**FIVE_FIXES: PASS**
**SUPERVISED_READY: YES**
**P0: 0；P1: 0；P2: 3（均不阻断）。**
