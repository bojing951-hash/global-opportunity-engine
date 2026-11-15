# QA — 研究产物恢复最终确认（HEAD 55f5540 / code 9fb6222）

- 审查对象：`architecture/research-v2` @ `55f5540`（代码 `9fb6222`，243 tests；release `9fb62229e3`）
- 方式：只读 Git、DB（`mode=ro&immutable=1`）、artifact JSON/`findings.md` 比对；未改代码，仅新增本报告。
- 时限约 2 分钟；未重跑 243 全量，复用 release proof 与 junit。

## 结论（Verdict）

**通过（PASS）**：上轮 P1（当前 3 份 artifact 被修复脚本覆盖、`findings.md` 截短、JP 泛化标签回退、`code_commit` 变旧）已关闭，本轮五项核验全部成立。

- **P0：0**
- **P1：0**
- **P2：1**（DB 历史 payload 与恢复后 artifact 的 provenance 滞后；不阻断）
- **CI run37：** 任务声明为 SUCCESS；仓库内可核证据止于 run #34/#35，run37 未能独立复核（见附注）。

## 核验结果

| # | 核验项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 3 份当前 versioned finding 恢复完整、未截短 | **PASS** | 与 `aa2b4da` 逐字节一致（`git diff --stat aa2b4da HEAD -- <3 dirs>` 为空）；`findings.md` 44/37/38 行，含 `Acquired evidence`、`Tests`、`Hypothesis updates`、`What we learned`、`Still unknown` |
| 2 | DB `artifact_path` 匹配 | **PASS** | 10/10 行唯一、存在、位于 `research_results/<as_of>/<asset>/RF-*/finding.json`；3 份当前 artifact 路径精确命中恢复文件 |
| 3 | `code_commit=b93d5e6` + 泛化标签 | **PASS** | JP/US/CM 三份 `finding.json` 均为 `b93d5e66920e…`；JP 标签为 `Local market factor` / `Global risk lead` / `FX/cross-border flow` / `Fundamentals` / `Regional co-move`，无 Japan 专有回退 |
| 4 | 修复脚本拒绝覆盖 | **PASS** | `scripts/repair_research_artifacts.py:37-38`：目标 `finding.json` 已存在即 `continue`，不写 `finding.json`/`findings.md`，也不改该行 `artifact_path` |
| 5 | legacy root 标记 | **PASS** | `CM_ETF_SLV`、`JP_EQ_N225`、`N225`、`US_FX_DXY` 4/4 均有 `LEGACY_ROOT.md`，明确指向 `RF-*` 版本化子目录 |
| 6 | 测试 243 | **PASS（复用证明）** | release `release_9fb62229e3.json`：`passed=243`、`skipped=0`、`git_dirty=false`；proof `exit_code=0`、required=executed=243；junit 243 个 `<testcase>`；log 尾 `243 passed, 10 deselected` |
| 7 | 远端 HEAD | **PASS** | `git ls-remote origin architecture/research-v2` = `55f5540b9ce4…`，与本地 HEAD、工作树 clean 一致 |

## P2-1 DB payload 仍为旧 provenance（不阻断）

3 份当前 finding 的 `research_v2_findings.payload_json` 仍是 `4fa6086` 生成的历史 payload（JP 标签仍为 `Japan broad local market factor` 等），与恢复后的 `finding.json`（`b93d5e6` + 泛化标签）**不再规范化相等**；DB 仅 `artifact_path` 指向正确文件。10 条中其余 7 条历史 finding 的 payload 与文件仍相等。

- 影响：以 DB payload 为数据源的消费者会读到旧的 `code_commit`/标签；artifact、release proof、243 tests 与结论不受影响（10 条 finding 全部 `INCONCLUSIVE`，无删除、无跨 finding 串写）。
- 定性为 P2 而非 P1：DB 未纳入版本控制（`data/` 在 `.gitignore`），release/CI 以版本化 artifact 为准；不改变研究结论与验收项。
- 建议：显式记录“当前 artifact 与 DB payload 的恢复差异”或补一次受控 payload 回填/来源哈希，避免下次重建时歧义。

## 附注

- **CI run37**：`audit/CI_SUCCESS_2026-11-15.md` 最新记录为 run #34，`audit/QA_FINAL_GENERALIZED.md` 记录 run #35；仓库内无 run37 证据，本环境网络查询未成功，故 run37 按任务声明接受，未作为独立复核结论。
- 脚本每次运行仍会重写 4 个 root 的 `LEGACY_ROOT.md`（内容幂等，不改当前 artifact），不违反“拒绝覆盖当前 3 份 artifact”。
- 本轮未改任何代码；仅新增本报告。
