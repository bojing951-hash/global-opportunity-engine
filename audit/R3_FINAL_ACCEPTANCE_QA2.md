# R3 FINAL ACCEPTANCE QA — pass 2 (second acceptance pass)

- 审计对象：`global-opportunity-engine`，HEAD `6755d34` + 未提交 worktree
- 审计时间：2026-11-14 17:30–17:38 HKT
- 权限：只读；唯一写入为本文件。未改代码/配置/DB/git
- 范围：P1-R1、P1-R2、最终 replay、盲评/前瞻一致性、离线测试

## 0. 判决

**PASS WITH ISSUES**。上一轮两个验收级 P1 在当前状态下均已关闭：
P1-R1 当前 DB 已有真实 `not_completed:refused` 记录且无 IA 成功事件；
P1-R2 用户可见文档已改为 refused / exit 2 / unmapped，不再把 `ok rc=0` 写成成功。
未发现新的 P0/P1。剩余问题均为 P2/P3 文档一致性（worktree 声明、历史计数），不影响工程签收；
研究能力仍未验证，六门整包仍是 NO-GO for research。

## 1. 逐项验证

| # | 检查项 | 观测证据 | 判定 |
|---|---|---|---|
| 1 | P1-R1 当前 DB 的 handoff 结果 | `research_tasks`：`RT-20261113-0002` / `OPP-0002` → `not_completed:refused`，`exported_at=2026-11-14T09:26:13Z`；`payload.result={status:not_ok, semantic_status:refused, semantic_reason:"下游明确拒答/越界（status=unmapped）", run_ok:true, n_evidence_rows:18}`；`opportunity_events` #519 `ia_research_not_completed`（watch→watch, 09:26:13Z） | **PASS** |
| 2 | 最新 watch 候选 | 队列 `research_queue_2026-11-13.json`：OPP-0002 priority 1 / score 0.5927（watch），OPP-0003 priority 2 / 0.5577；handoff 取 top-1 = OPP-0002 | **PASS** |
| 3 | CLI exit 2 | `goe/cli.py:290-293`：`res.status != "ok" or res.semantic_status != "ok_valid"` → `exit_code=2`；DB 记录正是 `not_ok` + `refused`，故该次真实 handoff 退出码为 2。注：DB 只持久化语义结果，未单列进程退出码字段 | **PASS（代码+记录可闭合）** |
| 4 | 无 `ia_research_run` 成功事件 | `opportunity_events` 全表仅 11 `created`、2 `status_change`、1 `ia_research_not_completed`；无 `ia_research_run` / `ia_research_completed` / 任何成功事件 | **PASS** |
| 5 | 最新 IA 导出未被覆盖 | 最新导出目录 `exports/ia_runs/OPP-0002/20261114T092613Z_.../`（17:26）；`report.json` S8 `status=unmapped`、`semantic_ok=false`、`ok=true, exit_code=0`（下游进程 0，语义拒绝）；其后无新导出 | **PASS** |
| 6 | P1-R2 README/INTEGRATION | `README.md:153`：`OPP-0002: not_ok rc=0 semantic=refused` + 注释“任务 not_completed:refused，CLI exit 2”；`docs/INTEGRATION_INVESTMENT_AGENT.md:108` 同；`PROJECT_SPEC.md:83` 同。全仓无 “ok rc=0” 成功表述；未检出 `0.606`、`DAX 0.514`、`1511`、`89 passed` 陈旧计数 | **PASS** |
| 7 | 最终扫描/队列/测试口径 | DB：anomalies **1,506**；opportunities **11** = watch **2** / low_priority **3** / invalidated **2** / excluded **4**；prices 358,310；indicators 159,508；queue **2**；`TEST_RESULTS.md`/`FINAL_ACCEPTANCE.md`/`EXECUTION_STATE.md` 均为 157 tests | **PASS** |
| 8 | 最终 replay artifact | `reports/validation_cases_20261114T092812Z.md/.json`：`n_cases=7, n_passed=7`，`generated_at=2026-11-14T09:28:12Z`；文件 mtime 17:29:27，晚于最新 `goe/*.py`（pipeline 17:15、features 16:33），即晚于本轮 feature 变更 | **PASS** |
| 9 | 盲评/前瞻诚实性 | `audit/RESEARCH_QUALITY.md`：引擎 C **1.188** < B 异常 **1.521**（亦 < A 1.312），P@3 0.417 vs 0.750；前瞻 C +7.12% 但 ex-top **+2.45%**、beat-class 42%，B +5.09%/ex-top +1.05%/58%；结论“没有稳健优势”。`FORWARD_RETURNS.md`、`FINAL_ACCEPTANCE.md` Gate 5 一致 | **PASS** |
| 10 | 离线测试 | `.venv/bin/python -m pytest tests -m "not network" -q` → **157 passed / 0 failed**，exit 0（72+72+13 点） | **PASS** |
| 11 | 新 P0/P1 | 未发现代码级 P0/P1、伪造数据、前视或扫描阻断回归；R1/R2 已关闭 | **PASS** |

## 2. 剩余问题（均 P2/P3，不阻塞工程）

1. **P2 文档计数残留**：`README.md:170` 仍写“97 项离线测试”（同文件 215 行已写 157）；`audit/VALIDATION_RESULTS.md:20` 仍写“137 passed (round 1: 121)”，而当前为 157。属历史/局部口径未同步，不是验收假成功。
2. **P2 执行状态自相矛盾**：`audit/EXECUTION_STATE.md:8` 写“Worktree: clean; all changes committed and pushed”，实际 `git status` 33 个修改 + 多个未跟踪审计文件；同文件第 4 行又写“commit pending”，且“strict replay pending final artifact”已被 17:28 的 7/7 artifact 取代。
3. **P3 措辞**：`docs/INTEGRATION_INVESTMENT_AGENT.md` §4.3 标题仍为“实际执行深度研究（已验证）”，正文已明确 refused/exit 2；建议改为“执行已验证（下游 refused）”。`FINAL_ACCEPTANCE.md` 称“Round-3 changes are committed separately”，与当前未提交 worktree 不符。
4. **P3 范围标注**：`VALIDATION_RESULTS.md` 标题“rounds 1–2 (final)”但正文已含 round-3 的 1,506/11/handoff 结果。

## 3. 六门状态（沿用并核对当前证据）

| Gate | 状态 | 关键证据 |
|---|---|---|
| 1 Data | PASS with residuals | 当前 scan 125/125、readiness ok/degraded；未重跑 full build 属性测试（沿用工程 QA） |
| 2 Quant | PASS with residuals | 独立复算与工程 QA 未变；HAC/同源价格等 P2 仍在 |
| 3 Engineering | **PASS** | 157 离线测试 exit 0；handoff 语义/exit 2；事务回滚 |
| 4 Methodology | PARTIAL | 本地 driver/失效条件已修；proxy 非一致预期、样本相位敏感等 P2 |
| 5 Discovery | **PARTIAL / NOT VALIDATED** | replay 7/7；盲评 C 最后；前瞻 ex-top 2.45% < B 5.09%；0 deep |
| 6 Integration & QA | **PASS（语义正确）/ 端到端 NOT ACHIEVED** | 真实 refused 已入 DB；无 ok_valid 样本；B intent gate 拒绝资产问题 |

## 4. 结论

- 工程：**ACCEPTED WITH ISSUES（PASS WITH ISSUES）**；P1-R1/P1-R2 已关闭，无新 P0/P1。
- 研究：**NOT VALIDATED**；不能宣称引擎优势，0 deep 不应被当作质量结论。
- 六门整包：工程可签收；研究能力与端到端 A→B 成功仍不可签收。

> 本报告仅新增本文件；未修改代码、配置、DB 或 git。
