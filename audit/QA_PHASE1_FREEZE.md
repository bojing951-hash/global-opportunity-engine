# Phase-1 冻结独立最终 QA（2026-11-16）

- 审计基线：`HEAD f9aeee5`（代码 `b8e9e15`，HEAD 仅新增 release/proof 产物）；审计开始时 `git status --short` 为空。
- 方式：只读审计；除本文件外未修改工作树。独立全量复跑 + 定点复跑 + 独立临时库探针（`/tmp/qa_freeze`，不写入仓库）。
- 外部输入：CI run60 success 为上游提供；本会话无 `gh`，GitHub API 限流，无法独立复取。

## 结论

**总体：PASS，准予冻结（FREEZE CANDIDATE）。P0 = 0，P1 = 0。** 发现 3 项 P2（证据/覆盖缺口，不阻塞冻结）。

| 状态项 | 结果 |
|---|---|
| `F4_A_UPDATE_OCCURRENCES` | **PASS** |
| `F4_B_CURRENT_STATE_SYNC` | **PASS** |
| `REGRESSION_CHECK` | **PASS** |
| `USER_OPERATING_GUIDE` | **PASS** |
| `FREEZE_CANDIDATE` | **PASS（准予冻结）** |

## 证据

### F4_A_UPDATE_OCCURRENCES — PASS

- 代码：`goe/research_updates.py` 的 key 为 `price:{iid}:{old12}->{new12}:b{batch}`；`batch` 缺省时由 `Store.next_update_batch()` 从 `counters` 表单调递增分配（`goe/db.py:958`），key 内无 `utc_now`/时间戳，不依赖墙钟。
- 独立探针：B→C→B→C 四次通知得到 4 条 update、4 个不同 key（`b1/b2/b3/b4`），counter=4；随后以显式 `batch="dup"` 重复投递同一 B→C：第一次新增 1 条（4→5），第二次新增 0 条（仍 5），`UNIQUE(research_id,trigger_key)`+`INSERT OR IGNORE` 保证同批次幂等。
- 仓库测试 `test_b_to_c_to_b_transitions_are_not_swallowed` 复跑通过，断言 open 计数 4 与同批重复幂等。
- **P2**：该测试只断言 4 条入队，未驱动 4 次 `run()` 断言全部 PROCESSED；按 update_id 顺序每次消费 1 条的代码路径成立，但缺端到端用例。

### F4_B_CURRENT_STATE_SYNC — PASS

- 代码：`execute_spec` cache-hit 分支在 `add_research_finding` 前调用 `update_research_hypotheses(spec.research_id, payload["hypothesis_updates"])`，把缓存 Finding 的 hypothesis_updates 重新落库；`add_research_finding` 冲突时只更新 `artifact_path`（`goe/db.py:1129-1136`），不改 status/payload/created_at。
- 独立探针（经 `ResearchOrchestrator.run` + 真实 `execute_spec` 缓存命中）：第二次调用返回同一 finding_id；返回值 hypothesis 状态、DB 状态一致；2 条 update 全部 `PROCESSED`、open=0；旧 finding 的 `created_at`、`payload_json`、`artifact_path` 及 `finding.json` 字节均未变化；workflow=`INCONCLUSIVE`。
- **P2**：仓库测试 `test_generic_execution_is_idempotent_and_keeps_artifact` 未经过 orchestrator/update ledger，故“update processed 一致”仅由本次未提交探针验证；代码路径明确。

### REGRESSION_CHECK — PASS

- 独立全量离线复跑：`pytest tests -o addopts= -q -m "not network and not realdata"` → **266 passed，0 failed，0 skipped，10 deselected**，exit 0（约 82s），与仓库 proof 的 266 一致。
- 定点复跑 `test_research_update_entry + test_research_orchestrator + test_research_exec + test_research_identity + test_research_v2` → **35 passed**。
- F1：`goe.cli doctor --json` rc=0；`events --check --json` rc=0（events=35/verified=34/ok=true，唯一 unverified 为数据源告警 `CN_LPR_2026_11_20`）。`replay` 本轮启动后超时未返回，未作为本轮通过证据；前次 QA 记录 rc=0。
- F2：依赖感知 ingest（IEF→QQQ 触发、无关资产不触发、as-of 截断）测试通过；F3：失败→FAILED+BLOCKED、retry→PENDING、成功恢复→PROCESSED 不重复，测试通过。
- 候选字段/事件身份：`test_research_identity.py`、`test_research_v2.py` 及 `test_register_preserves_screening_fields` 均通过。

### USER_OPERATING_GUIDE — PASS

- `docs/USER_GUIDE_PHASE1.md`、`docs/ROLLBACK_PHASE1.md`、`docs/RELEASE_NOTES_PHASE1.md` 均存在且已随 `b8e9e15` 提交；内容与实现一致（先 ingest 后 scan、更新状态机、失败重试、数据库备份与无破坏性迁移、B→C→B→C occurrence batches、cache-hit 状态重放）。
- **P2**：release JSON 的 `test_evidence.rerun.log_sha256=650944…` 在 `audit/test_evidence/` 无对应 rerun 日志文件（主日志 sha256=`16c46…` 可核）；CI 台账只记录到 run34，run60 无仓库内记录，属外部证据依赖。

### 冻结证明

- 全量 266/266，`required.sha256 = executed.sha256 = 860b9403…`；`git_commit=b8e9e15`，`git_dirty=false`；JUnit/log sha256 与仓库文件逐一匹配。
- HEAD `f9aeee5` 相对 `b8e9e15` 仅新增 release JSON、proof、JUnit、log 四个文件，无代码改动。
- CI run60：上游声明 success；本会话无法从仓库或 GitHub API 独立复核（P2，非代码缺陷）。

## P0 / P1

- **P0：无。**
- **P1：无。**
- P2（3 项）：F4-a 缺 4 次处理端到端断言；F4-b 的 update-processed 一致性仅由未提交探针覆盖；CI run60 与 rerun 日志哈希缺仓库内可核证据。

## 判定

F4-a、F4-b、F1–F3 回归、依赖更新、候选字段/事件身份及三份运维文档均在 `b8e9e15` 上成立；266 项离线测试独立复跑全绿，工作树干净，未发现 P0/P1。**准予作为 Phase-1 冻结候选，状态 FREEZE_CANDIDATE = PASS。**
