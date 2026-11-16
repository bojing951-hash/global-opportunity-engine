# QA V4 Closure — Independent Verification

- 审计对象：`architecture/research-v2`，声明基线 HEAD `97424fa`（code `8a2efba`），251 tests
- 审计执行：2026-11-16 10:53–11:00 (+08:00)，只读；仅写本文件
- 环境：macOS / `.venv` Python 3.12 / 离线 suite（`-m "not network"`）

## 结论

**PASS —— V4 closure 成立，无 P0、无 P1。**

五项验收中 4 项直接复验通过，CI 项通过公开 HTML 复核（Run 46 → `97424fa` → success）。发现 3 个 P2 级可追溯性/发布卫生问题，不阻断交付（见文末）。审计期间 HEAD 被并发推进（`97424fa` → `0384598` → `4eacf46`），因此“冻结 HEAD”这一点需发布方确认，详见 P2-1。

## 逐项验证

### 1. Event contract 持久化与不可重绑 — PASS

| 检查 | 证据 | 结果 |
|---|---|---|
| DB 表落盘 | `goe/db.py:162` `CREATE TABLE research_v2_event_contracts(research_id PK, contract_hash, anomaly_id, contract_json, created_at)` | PASS |
| 写入不可变 | `goe/db.py:946-956` `save_event_contract` 使用 `ON CONFLICT(research_id) DO NOTHING`；`resolve_event` 同样 `INSERT OR IGNORE`（`goe/research_contract.py:113-118`） | PASS |
| 重开/重扫不换事件 | `tests/test_research_contract.py:115-141`：关闭并重开 `Store` 后 `ev2.event_start == ev1.event_start == 2026-11-06`，`contract_hash` 相同 | PASS（本机 suite 通过） |
| 缺事件报错 | `goe/research_contract.py:80,96` 抛 `EventNotResolved`；`tests/test_research_contract.py:25-32` 断言不会静默替换 | PASS |
| 身份冲突报错 | `goe/research_contract.py:67-73`：asset/as_of/event_date/detector 任一漂移抛 `EventIdentityConflict`；测试 139 行覆盖 event rebind | PASS |
| TAIEX 合同 | `research_results/2026-11-13/TW_EQ_TAIEX/...-4dece725/plan.json`：`event_start=event_end=2026-11-06`、`event_contract` 持久化、`research_id=RC-20261113-TW_EQ_TAIEX-d1be6bcd3313` | PASS |
| KOSPI 合同 | `research_results/2026-11-13/KR_EQ_KOSPI/...-cc491d3f/plan.json`（V1）与 `...-d756fb85/plan.json`（V2）：均为 `2026-10-15`、`drawdown_extreme/deep_drawdown` | PASS |

代码修复 `e61bd58`（persist actual anomaly_id）已在当前 HEAD 中：`contract_json` 的 `anomaly_id` 来自 `anomalies.anomaly_id`，不再落空串。

### 2. 队列隔离 / 显式重试 / 决策语义 — PASS

| 检查 | 证据 | 结果 |
|---|---|---|
| 未解析高优先级不阻塞有效候选 | `tests/test_research_orchestrator.py:54-79`：高分候选 `A-BAD` 无事件 → `WAITING_FOR_DATA`，`next_case()` 继续并返回 `B-GOOD`；实现见 `goe/research_orchestrator.py:100-109`（`except EventNotResolved: ... continue`） | PASS |
| 失败隔离为显式状态 | `EventNotResolved` → `WAITING_FOR_DATA`；其他合同错误 → `BLOCKED`；`next_case` 的 SELECT 后续过滤 `BLOCKED/WAITING_FOR_DATA` | PASS |
| 显式重试 | `goe/research_orchestrator.py:44-49` `retry()` 仅对 `BLOCKED`/`WAITING_FOR_DATA` 生效，重置为 `PLANNED` 并写 `research:retry` 事件 | PASS |
| INSUFFICIENT_DATA 决策 | `goe/research_orchestrator.py:60-65`：任一 hypothesis `INSUFFICIENT_DATA` → `ACQUIRE_MORE_EVIDENCE`；`STOP_LOW_VALUE_RESEARCH` 仅在无数据缺口且 `INCONCLUSIVE` 时出现 | PASS |
| 缺失数据语义 | `tests/test_research_contract.py:35-103`：缺 SPY/VIX、缺 FX/商品风险序列均为 `INSUFFICIENT_DATA`，不误判为“证伪” | PASS |

### 3. KOSPI V1/V2 保留与诚实 CASE_C — PASS（附 1 个 P2 观察）

| 检查 | 证据 | 结果 |
|---|---|---|
| V1/V2 独立目录共存 | `research_results/2026-11-13/KR_EQ_KOSPI/` 下 8 个 finding dir；V1=`...-cc491d3f`、V2=`...-d756fb85`，各自含 `plan.json/evidence.json/tests.json/finding.json/findings.md` | PASS |
| 同一事件 | 两目录 `finding.json` 均为 `"event_date": "2026-10-15"`；CASE_C 文档写明同一 research ID、同一 locked event | PASS |
| V2 使用 USDKRW | V2 `finding.json` 唯一 FX 序列为 `GX_FX_USDKRW`；`goe/research_orchestrator.py:126` 对 `KR_EQ_KOSPI` 选择 `GX_FX_USDKRW`（V1 用 CNY，非本币对） | PASS |
| 无覆盖 | V1/V2 目录名由 input hash 区分，文件集合与内容并存；CASE_C 明示 “V1 directory was not overwritten” | PASS |
| 诚实性 | `research_results/CASE_C_MULTI_ROUND.md`：明确 V2 是 `EXISTING_DATA_NEWLY_ANALYZED`，非“新到达数据”；结论 `INCONCLUSIVE` + `ACQUIRE_MORE_EVIDENCE`；承认真正的 post-cutoff Case C 仍 `OBJECTIVELY_BLOCKED` | PASS |

补充观察（P2）：同 research ID 下另有历史目录 `...-f0604d67`，`event_date=2026-06-17`，属早期未引入持久合同前的旧 artifact，被保留未删除。它不参与当前合同（当前锁定 2026-10-15），但说明历史扫描确实产生过同 ID 不同事件，建议在 release note 中注明其为 pre-contract 历史件。

### 4. 测试证明 251 / artifact / 无未来数据 / 无 P0-P1 — PASS

| 检查 | 证据 | 结果 |
|---|---|---|
| 251 tests | `audit/releases/release_8a2efba96b.json`：`test_evidence.passed=251, skipped=0`，`git_commit=8a2efba96b…`，`git_dirty=false`；`audit/releases/release_0384598018.json` 亦为 251/0 | PASS |
| 本地复跑 | `.venv/bin/python -m pytest tests -q -m "not network"` 退出码 0（审计时段内复跑，无失败） | PASS |
| Proof 文件路径 | `audit/test_evidence/20261116T024712Z_8a2efba96b.proof.json`、对应 `.junit.xml`/`.log`；`audit/releases/release_8a2efba96b.json` | PASS |
| Artifact 路径 | `reports/report_2026-11-13.md`（sha256 `7ac34255…`）、`reports/scan_2026-11-13.json`（`cd0bc502…`）、`exports/pipeline_2026-11-13.json`（`9e6bd81a…`）；scan `scan-20261115T044634Z-b68802`，as_of `2026-11-13` | PASS |
| 无未来数据 | 唯一 decision cutoff `2026-11-13`；事件日 TAIEX `2026-11-06`、KOSPI `2026-10-15`，均早于 cutoff；CASE_C 明示 DB 无 cutoff 后观测；`tests/test_time_semantics.py` 通过 | PASS |
| 无 P0/P1 | 本审计未发现阻断级缺陷；测试与 queue/event 语义均闭环 | PASS |

### 5. CI Run 46 — PASS（公开 HTML）

- 公开仓库页面 `https://github.com/bojing951-hash/global-opportunity-engine/actions` 返回 200。
- 页面内 **Run 46** 段落对应提交 `97424fa`，标题 `chore(release): V4 event/multi-round proof at 8a2efba (251 tests)`，状态 `success`（HTML 同时含 `8a2efba` 与 success 标记）。
- 结论：CI run46 在声明基线 `97424fa` 上为绿；与 251 tests proof 一致。

## P2（不阻断）

1. **审计期间 HEAD 漂移**：开始时 `97424fa`，随后 `0384598`（TAIEX contract revision）、`4eacf46`（10:59:08 新增）。`4eacf46` 尚无对应 release proof。若最终交付以 `4eacf46` 为准，应在该 commit 重新生成 251-test proof 并重跑 CI；若以 `97424fa`/`0384598` 为准，应冻结分支并注明 `4eacf46` 为审计期外新增。这不是代码缺陷，是发布冻结卫生问题。
2. **合同 data_version 硬编码**：`goe/research_contract.py:105` `data_version="scan-20261115T044634Z-b68802"` 为固定串而非按 scan 注入。当前 artifact 与该 scan 一致，但换 scan 后合同 provenance 会失真，建议后续从 scan metadata 派生。
3. **历史同 ID 不同事件 artifact**：`...-f0604d67`（2026-06-17）为 pre-contract 旧件，保留正确，但建议在文档中显式标注，避免被误读为当前合同漂移。

## 最终状态

**V4 CLOSURE: PASS（P0=0 / P1=0 / P2=3，发布冻结待确认）。**

事件合同持久化、拒绝重绑、缺事件显式报错、队列隔离与显式重试、`INSUFFICIENT_DATA → ACQUIRE_MORE_EVIDENCE`、KOSPI V1/V2 保留与 USDKRW 第二轮、251-test proof、artifact 路径与无未来数据、CI Run 46 绿——均已独立复核。唯一需发布方动作的是确认最终冻结 HEAD 并为其留存 proof（P2-1）。
