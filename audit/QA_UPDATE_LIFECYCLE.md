# QA — 更新生命周期 / 自动重激活 / 评估材料（最终独立验收）

- 时间：2026-11-16（Asia/Hong_Kong）
- 基线：HEAD `b27090b`（code `c1e848b`），工作树干净；分支 `architecture/research-v2`
- 方式：只读审计；除本文件外未改代码、未改数据、未改仓库状态
- 结论：**UPDATE_LIFECYCLE = PASS；AUTO_REACTIVATION = PASS；EVALUATION_MATERIALS = PASS；SUPERVISED_READY = YES**
- 严重度：**P0 = 0；P1 = 0**（P2 见文末，均不阻断受监督使用）

## 1. 更新账本（UPDATE_LIFECYCLE = PASS）

| 验收项 | 结果 | 证据 |
|---|---|---|
| reopen 产生 PENDING | PASS | `ResearchOrchestrator.reopen` 调 `Store.enqueue_research_update`，插入 `status='PENDING'`；候选不存在时抛错 |
| next_case 选择待处理项 | PASS | `next_case` 以 `open_research_update_count`（PENDING/PROCESSING）判重，不再依赖秒级 `created_at` 比较；有 finding 但无 pending 才跳过 |
| 空跑也消费通知 | PASS | `run` 无论 finding 是否被复用都标记该 update `PROCESSED`，注释明确不得让同一 trigger 永久 pending |
| 重复 next 不循环 | PASS | `test_no_change_reopen_is_consumed_and_does_not_loop`：run 后 `next_case() is None`、open count = 0；旧 finding `created_at` 不变 |
| 重复 key 幂等 | PASS | 表级 `UNIQUE(research_id, trigger_key)` + `INSERT OR IGNORE`；同 fingerprint 二次通知后 open count 仍为 1 |
| 同秒不 sleep | PASS | 上述测试无 `sleep`，finding 与 reopen 同秒仍被消费（修复了 `QA_FIVE_FIXES.md` 记录的 P2 同秒竞态） |
| 失败 → FAILED/BLOCKED、可重试 | PASS | `run` 捕获 `execute_spec` 异常：update 置 `FAILED`、workflow 置 `BLOCKED`；`retry` 将 FAILED 重置 PENDING、BLOCKED 重置 PLANNED；测试 `test_failed_update_is_not_marked_processed_and_can_recover` |
| 运行中到达的更新不被吞 | PASS（独立复核） | 审计时用临时 DB 注入“run 执行中到达第二条不同 fingerprint”场景：运行前 update = PROCESSED，运行中 update 保持 PENDING，open=1；未写入仓库测试（见 P2-1） |

账本状态机为 PENDING/PROCESSING/PROCESSED/FAILED；`mark_research_update` 对非法状态抛错，失败 update 不会误标 PROCESSED。

## 2. 实际 `goe ingest` 入口（AUTO_REACTIVATION = PASS）

- `goe/cli.py::cmd_ingest` 在 ingest 前后分别取 `candidate_price_fingerprints`，调用 `notify_price_changes`；入口层而非仅 orchestrator 层接线。
- 只有候选 instruments 集合的价格 fingerprint 变化才触发；`notify_price_changes` 仅遍历 `before` 中发生变化的 instrument，并只对该 instrument 关联的 research_id 入队，不会因无关标的变化而全局重跑。
- `tests/test_research_update_entry.py` 直接调用 `cmd_ingest`，用受控 provider 新增价格 bar，断言关联候选产生 `price_revision` 的 PENDING update。
- 无未来数据：`execute_spec` 使用 `FeatureBuilder(as_of=..., point_in_time=True)`（只取 `date <= as_of`）；`_event_date` 过滤 `index <= as_of`；`_ret` 对未来/缺失日期返回 None（`tests/test_research_exec.py::test_ret_returns_none_for_future_or_missing_date`）；finding 的 `data_hash` 只覆盖 `returns.loc[:as_of]`。
- 边界：真实 DB 止于 2026-11-13，入口测试使用受控价格变更；不宣称真实跨日 ingest 已发生。

## 3. 评估材料（EVALUATION_MATERIALS = PASS）

- 中性卡片 `evaluation/triage_cards.json`：20 张，字段仅 `card_id/asset/observed_phenomenon/return_1m/anomaly_score/materiality/decision_relevance`；不含 GOE class/rating/queue/worthiness，未见方法标签泄漏。
- 空白评分表 `evaluation/triage_scores_template.csv`：20 行 C01–C20，四项 0–3 分与 comments 均空。
- 方法映射 `evaluation/triage_method_mapping.json` 单独存放（simple_baseline / goe_selection / method_mapping），与卡片分离，可对评分者隐藏。
- `evaluation/TRIAGE_VALUE_REVIEW.md` 明确 **TRIAGE VALUE: NOT VALIDATED**；无用户/独立评分，不能据此声称节省审阅时间或选出更优问题。
- 口径一致：评估是“停止 16 项 + 为 4 项提出具体缺失证据”，不是“更多机会”。

## 4. 候选筛查、QQQ H-TECH、262 证明与 CI

- 候选筛查保留：`register` 仅在候选不存在时写入默认 payload；`test_register_preserves_screening_fields` 覆盖 worthiness/readiness/queue/handoff/materiality/research_cost/evidence 不被覆盖。真实 QQQ 候选复核：`research_worthiness=high`、`evidence_readiness=partial`、`research_queue=watch`、`handoff_eligibility=a_retained`，`updated_at=2026-11-16T04:37:32Z` 未因 register 变化。
- QQQ H-TECH：canonical finding `RF-…c6b8…-e357c75d` 中 `H-TECH = INCONCLUSIVE`，new_evidence 标注 “observation, not independent support”；`evaluation/investment_intelligence_qqq.json` 仅 `H-RISK` 为 supported，`H-RATE/H-TECH` 为 unresolved；H-RISK supported、H-RATE weakened 与 finding 一致。
- 262 测试：`audit/releases/release_c1e848b964.json` 的 proof 为 `passed=262 / failed=0 / skipped=0`，required 与 executed SHA256 一致；`audit/test_evidence/20261116T063508Z_c1e848b964.proof.json` 同步记录 262，rerun 262。审计本地复跑 `pytest tests -m "not network"` 退出码 0（100% 完成）。
- CI run 56：GitHub Actions `verify-release` #56，commit `b27090b`，状态 `COMPLETED / SUCCESS`，耗时 1m17s，创建于 2026-11-16T06:36:51Z（run URL: `actions/runs/43817951768`）。与任务给定 “run56 success” 一致。

## 5. P2 残余（不阻断）

1. `audit/UPDATE_LIFECYCLE_EVIDENCE.md` 场景 G 称“test coverage in orchestrator”，但仓库中无“运行中到达更新”的回归测试；本次仅以临时 DB 独立复核。建议补一条回归测试，避免文档高估覆盖。
2. `run()` 在 `plan_evidence(spec)` 之前就把 update 置 PROCESSING，而该调用在 try 之外；若 planner 抛异常，update 会停在 PROCESSING、workflow 停在 EVIDENCE_PENDING，不会走 FAILED/BLOCKED。当前 planner 为确定性映射，未触发；建议把 plan 纳入同一异常处理。
3. 幂等键 `price:<instrument>:<new_fingerprint>` 是生命周期唯一：价格 A→B 被消费后，若数据回退到 A 再变回 B，第二次 B 会因旧键已存在而被吞。无真实跨日 ingest 场景，当前不可达；建议键加入 revision 序号/时间。
4. `reopen` 在重复 key（`enqueue` 返回 None）时仍把 workflow 置 PLANNED 并追加事件，但无 PENDING，队列不会重选；属状态/队列轻微不一致，建议仅在拿到 update_id 时改状态。

**最终：P0=0，P1=0；受监督使用可继续。** 更新生命周期与自动重激活在当前受控/历史数据范围内成立；真实跨日连续运行与更新价值仍未验证。
