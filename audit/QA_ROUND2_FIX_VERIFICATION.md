# QA Round 2 修复独立复核

- 仓库：`global-opportunity-engine`，HEAD `69a267a`，工作树干净。
- 方式：只读代码 / 测试 / `data/goe.db`；对抗性用例在 `mktemp` 临时库副本上构造，未改仓库库、代码、配置、测试、git。
- 时间：2026-11-14（HKT）。
- 唯一写入：本文件。

## 结论

**PASS WITH ISSUES（两个 P1 均实际修复，未发现新 P0/P1；残留 P2/P3 见文末）。**

## 检查表

| # | 检查 | 实测 | 判定 |
|---|---|---|---|
| A1 | `ReadinessResult` 含 `degraded` / `critical_degraded` | `goe/readiness.py:47,51`，`to_dict()` 输出两个字段（:64-65） | PASS |
| A2 | `critical_degraded` 只在“广谱宏观失败”或“整条曲线系统全过期”置位 | 宏观仅 `fresh_macro < max(3, present//2)` 时置位（:204-208）；曲线仅 `present_n>0 and fresh_n==0` 时置位（:247-251）；单条过期只进 `warnings`+`degraded`（:209-217） | PASS |
| A3 | 单条过期 macro 不再全局封禁深研 | 真实库：14/16 fresh、`degraded=True`、`critical_degraded=False`；临时库强制 `US_PAYROLLS` 过期（13/16 fresh）同样 False | PASS |
| A4 | pipeline 把 `critical_degraded` 传给引擎 | `goe/pipeline.py:130` → `goe/opportunities.py:179,201,1416`（仅该标志进入 deep_research 门禁） | PASS |
| A5 | 定向测试 | `pytest tests/test_readiness_handoff.py tests/test_pipeline_e2e.py -q` → 23 passed，exit 0 | PASS |
| A6 | 声称 137 tests | `-m "not network"` 收集 137；`-m network` 9；全量 146 收集并全部通过（exit 0） | PASS（137 指离线） |
| B1 | 对抗：UST 各期限有历史、as_of 前无 fresh | 临时库删除 `UST:* AND date > 2026-10-28` 后 `check_data_readiness(as_of=2026-11-13, min_coverage=0)`：`ok=False`，critical=`UST 曲线全部过期：0/13 个期限在 15 天内有更新`，`degraded=True` | PASS |
| B2 | 对抗：单条过期可选 macro + ≥6 fresh | 真实库已满足（14 fresh/2 stale）→ `critical_degraded=False`；临时库再制造 1 条过期仍 False | PASS |
| B3 | 引擎/管线映射 | 见 A4；`data_degraded` 只在 `d.status=="deep_research"` 分支降为 `watch`（:1416-1417） | PASS |
| C1 | 真实库 readiness（as_of=2026-11-13） | `ok=True`，`degraded=True`，`critical_degraded=False`；125/125 fresh；macro 14/16；warnings=`关键宏观序列过期：EA_HICP…`；stale 另含 `US_CAPE`（非关键） | PASS |
| C2 | 扫描 meta | `reports/scan_2026-11-13.json`：`data_readiness.degraded=True`、`critical_degraded=False`；11 个机会 | PASS |
| D1 | 文档数字一致性 | README/TEST_RESULTS/`audit/VALIDATION_RESULTS.md`/`audit/FINAL_ACCEPTANCE.md`：1,511 异常、11 候选、top 0.606、137 离线+9 联网，全部一致 | PASS |
| D2 | 旧数字残留 | 1,649 / 18 个 / 0.6702 仅出现在历史审计快照（`audit/ROUND2_RESEARCH_AUDIT.md`、`ROUND2_DATA_AUDIT.md`、`ROUND2_FIX_SUMMARY.md` 的“修复前→后”），未出现在当前验收文档；`121` 仅作“round 1 test count”历史对照 | PASS（历史审计文档保留旧值属正常） |
| D3 | top 分与分布复核 | 扫描 JSON 最高 0.6056（OPP-0001 watch），第 2 0.5927；状态 3 watch/2 low_priority/5 excluded/1 invalidated = 11 | PASS |
| E1 | OPP-0001 任务状态 | `research_tasks` 仅 `RT-20261113-0001`，status=`exported`（非 `not_completed:refused`） | 部分不符 |
| E2 | 实际交接产物 S8 | 最新 `exports/ia_runs/OPP-0001/20261114T064204Z_…/report.json`：`S8_grounded_qa.semantic_ok=false`，`envelope.data.status="out_of_scope"`，`gate_a="DEGRADED"` → 对端拒绝研究问题 | PASS（拒绝有产物证据） |
| E3 | “handoff refused / exit 2” | 产物只证明语义拒绝；task 被最终扫描/导出流程重写为 `exported`，库内无 refused 状态、无 exit code 记录 | 不可完全复核 |
| F1 | 新 P0/P1 回归 | 未发现：无死锁（事务未改）；`min_coverage=0` 下缺失市场仅 warning（实测删全部 CN 价格：`ok=True`，`critical` 无 CN，warning=`CN 市场完全没有价格数据`）；无全局过度封禁（真实扫描正常 success） | PASS |
| F2 | “7/7 archived” | 最新 `reports/validation_cases_20261114T063037Z.md`：`通过：7 / 7` | PASS |

## 残留问题（均非 P1）

1. **P2 — handoff 状态语义**：`research_tasks.status` 为 `exported`，未记录 `not_completed:refused`。拒绝事实只存在于 IA run `report.json` 的 S8 envelope。若下游按 task.status 判断，会误以为研究已完成。建议导出时把 `semantic_status`/refused 写回 task.status，或另存 handoff 结果。
2. **P2 — 回归测试偏弱**：`test_single_stale_series_is_disclosure_not_global_deep_cap` 先为 7 条序列写入 `2024-09-01`，再把最后一条写 `2023-01-01`；后者被更新的行遮蔽，并未真正制造“过期序列”，`degraded=True` 也可由缺失市场/曲线告警满足。本次行为已由独立临时库用例证实，但该测试本身防回归能力不足。
3. **P3 — 重复代码块**：`readiness.py:230-232` 与 `255-257` 重复 `if present_curve == 0` 告警，曲线全缺时会重复 warning。
4. **设计提示（非缺陷）**：整条曲线系统全过期会写入 `critical`（`ok=False`），即封禁整次扫描；这与 P1-2 声称的“critical”一致，但意味着任一有历史数据的次要曲线系统（如 CN/JGB）长期停更即可永久阻塞全部扫描，且不受 `min_coverage` 调节。建议后续按核心系统/严重度分级。

## 两个 P1 是否真的修复

- **P1-1（单条过期宏观封禁全部深研）：是。** `critical_degraded` 与 `degraded` 分离，只有广谱宏观新鲜度不足才置位；真实扫描 `EA_HICP` 过期但 `critical_degraded=False`，管线仅据此门禁。
- **P1-2（按曲线系统判 stale）：是。** 新增逐系统 `present_n>0 && fresh_n==0 → critical`；对抗用例 UST 0/13 fresh 正确触发 critical。残留的“次要系统可全量阻塞”属设计取舍，不是该修复失效。
