# 四项 P1 独立最终 QA（2026-11-16）

- 审计基线：`HEAD 343d3c0`（代码 `e315f33`），工作树干净（`git status` 无输出）。
- 方式：只读审计，唯一写入本文件。独立复跑命令与测试，不修改代码。

## 结论

**总体：PASS。** F1–F4 四项全部通过；未发现 P0 或 P1。发现 3 项 P2（覆盖缺口，不阻塞发布）。

| 项 | 状态 | 结论 |
|---|---|---|
| F1 CLI 回归 | **PASS** | doctor / events --check / replay 实跑 rc=0，无 NameError/undefined |
| F2 依赖感知 ingest | **PASS（P2 注）** | IEF→QQQ 触发、无关资产不触发、as-of 截断；cmd_ingest 实测 |
| F3 失败/恢复 | **PASS（P2 注）** | planner/execute 异常→FAILED+BLOCKED；retry 复位；只处理一次 |
| F4 B→C→B | **PASS（P2 注）** | 三个 revision 均入队；同 transition 幂等；历史不覆盖 |

## 证据

### 测试总量与 CI

- 独立收集：`pytest tests -m "not network and not realdata" --collect-only` → **266**。
- 独立全量离线运行退出码 **0**；仓库证据 `audit/test_evidence/20261116T072802Z_e315f33248.proof.json`：`passed 266 / failed 0 / errors 0`，commit `e315f33`，`git_dirty=false`，JUnit 计数与 sha256 一致（`860b94…`）。
- CI run58：本次会话无法访问 GitHub Actions，仓库内 `audit/CI_SUCCESS_2026-11-15.md` 只记录到 run34（243 tests）；run58 绿为上游提供的外部证据，本地可复现的是 266 离线测试。此项不构成代码缺陷，但属证据链外部依赖。

### F1 — CLI（实际运行）

```bash
.venv/bin/python -m goe.cli doctor --json                      # rc=0
.venv/bin/python -m goe.cli events --check --json              # rc=0, ok=true
.venv/bin/python -m goe.cli replay --start 2026-06-01 --end 2026-06-30 --step 21 --json  # rc=0
```

- doctor：Python 3.12.13 / DB 检查正常，无异常。
- events --check：`events=35, verified=34, problems=[], ok=true`；唯一 unverified 为 `CN_LPR_2026_11_20`，是数据源告警而非程序错误。
- replay：`n_dates=3, n_ok=3`，anomalies 370/408/386，opps 3/6/6；stderr 仅有 numpy 全 NaN 切片 RuntimeWarning，不影响 rc。
- 未出现 NameError、未定义变量或 ingest 代码误插入。

### F2 — 依赖感知 ingest

- 实现：`research_snapshots()` 对每个候选按其 `as_of` 计算依赖指纹；`research_dependencies()` = 候选资产 ∪ 最新 Finding 的 peers ∪ event_contract.asset_id；`instrument_price_fingerprint(iid, cutoff)` 只取 `date <= cutoff`。
- `cmd_ingest`：ingest 前/后各取快照，`notify_price_changes()` 仅对指纹变化的依赖入队。实跑测试 `test_ingest_peer_revision_reactivates_qqq`：仅改 IEF，经真实 `cmd_ingest` 路径后 QQQ 得到 1 条更新，`trigger_key` 含 `US_FI_IEF`。
- 无关资产：`test_peer_dependency_revision_triggers_only_related_research` 中断言无变化时 `notify_price_changes == []`，且只有 IEF 变化才产生更新。
- 截止日：截断逻辑在 `date<=as_of`，代码级确认；未发现把 as-of 后 bar 计入指纹的路径。
- **P2**：没有一条端到端测试在 cmd_ingest 中显式插入“as-of 之后的 bar”并断言不触发；当前为代码审查 + 指纹 SQL 证据。

### F3 — planner/execute 失败与恢复

- `ResearchOrchestrator.run()` 先将请求置 PROCESSING；`plan_evidence` 与 `execute_spec` 同在 try 内。任一异常：请求置 `FAILED`（带错误），workflow 置 `BLOCKED`，再抛出。
- `retry()` 调用 `retry_failed_research_updates()`，把 `FAILED` **和 `PROCESSING`** 复位为 `PENDING`，并把 `BLOCKED/WAITING_FOR_DATA` 恢复为 `PLANNED`。
- `pending_research_update()` 查询包含 `PENDING','PROCESSING`，因此崩溃遗留的 PROCESSING 可被再次领取。
- 测试通过：`test_failed_update_is_not_marked_processed_and_can_recover`（执行器异常→FAILED/BLOCKED→retry→PENDING）、`test_planner_failure_does_not_leave_processing_stuck`（planner 异常→FAILED；成功恢复后 open_update=0，不重复处理）。
- **P2**：没有专门构造“进程崩溃留下 PROCESSING”的测试；stale PROCESSING 恢复为代码级证据（查询 + retry 的 IN 列表），行为正确但缺故障注入用例。

### F4 — B→C→B 与幂等/历史

- trigger_key 含新旧内容前缀：`price:<instrument>:<old12>-><new12>`；A→B、B→C、C→B 生成三个不同 key，测试 `test_b_to_c_to_b_transitions_are_not_swallowed` 断言 3 条 pending。
- 表约束 `UNIQUE(research_id, trigger_key)` + `INSERT OR IGNORE`：同一 transition 重复通知返回 None，open 计数保持 1（`test_no_change_reopen_is_consumed_and_does_not_loop` 中显式断言）。
- 历史：Finding/event 均追加写入，identity 不可变（`test_immutable_identity_rejects_asset_and_date_retarget`、`test_completed_status_is_not_silently_reopened`），重复 upsert 保留 candidate 字段与 task（`test_duplicate_upsert_keeps_identity_and_task`）。
- **P2**：F4 测试只断言“三个 revision 入队”，未真正驱动三次 `run()` 断言“最终 B 被 PROCESSED”；处理逻辑按 update_id 顺序消费 3 条，代码路径成立，但缺少端到端断言。

### 其他指定点

- 无变化 reopen 被消费、同一秒、第二次更新可入队、重复同 transition 幂等：`test_no_change_reopen_is_consumed_and_does_not_loop` 全通过（含 Finding `created_at` 不变、open 计数 0→1→1）。
- 队列继续：`test_ingest_entry_queues_update_for_related_research`；`test_next_case_selects_real_candidate_queue_not_fixed_cases` 通过。
- 候选字段 / 事件身份：`test_research_identity.py`、`test_contracts.py::test_research_candidate_contract` 通过。
- 聚焦复跑：`test_research_update_entry.py + test_research_orchestrator.py + test_research_identity.py + test_research_v2.py` → 29 passed。

## P0 / P1

- **P0：无。**
- **P1：无。**
- P2（3 项）：F2 as-of 后 bar 缺 e2e；F3 崩溃遗留 PROCESSING 缺故障注入测试；F4 最终 B 的 PROCESSED 缺端到端断言。

## 判定

四项 P1 修复在 `e315f33` 上可复现通过，266 项离线测试与 CLI 实跑一致，**准予通过**；CI run58 以外部证据为准，三项 P2 建议后续补测，不影响本次结论。
