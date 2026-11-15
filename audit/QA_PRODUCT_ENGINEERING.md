# 产品工程独立 QA — 30cb2e4 / architecture/research-v2

- 时间：2026-11-15（6 分钟时限）
- 范围：只读验证；除本文件外未写入仓库，未改代码/测试/配置
- 结论：**PASS（工程验收通过）**；**新增 P0 = 0，P1 = 0**；P2 = 1（见 §6）

## 1. 核对结果

| # | 检查项 | 结果 | 证据 |
|---|---|---|---|
| 1 | Dossier CLI 生成全部 watch dossier | **PASS** | 默认命令 exit 0，生成 4/4 watch（N225、TAIEX、QQQ、XLV）；输出到临时目录；Case B VIX 用 `--id` 单独生成成功 |
| 2 | 测试 235 | **PASS** | `-m "not network and not realdata"` 收集 235/245；proof 记录 235 passed/0 failed/0 skipped；CI run 26 在 30cb2e4 重放 proof 成功 |
| 3 | proof `release_5c055cc813` accepted | **PASS** | `verify-release --no-rerun` → `status: accepted`，commit `5c055cc8130e...`，passed=235，required/executed sha256 均为 `125f6421...` |
| 4 | scan evidence 有效 | **PASS** | `verify_scan_evidence(..., require_artifacts=True)` 通过：`scan-20261115T044634Z-b68802`，as_of 2026-11-13，prices 358310 / indicators 159508 / anomalies 1506 / transmissions 5 / opportunities 11，readiness_ok=true；report/scan-json/pipeline hash 与 release manifest 完全一致 |
| 5 | 真实 dossier 存在且 18 节 | **PASS** | 2026-11-13 五个 + 2026-04-30 Case D，每个正好 18 个 `##` 节；含 `NOT_INDEPENDENTLY_REVIEWED` 与 `DISCOVERY VALUE: NOT VALIDATED` |
| 6 | 重生成并比对 content hash | **PASS（带条件）** | 用 `--artifact evaluation/v2_candidates_20_2026-11-13.json`（相对路径）重生成，4 个 watch + VIX 的 JSON/Markdown sha256 全部与已提交文件一致；用默认绝对路径则 content_sha256 变化 → 见 §6 P2 |
| 7 | GitHub Actions 30cb2e4 | **PASS** | 公共 HTML 解析：run #26（id 43701549389），title `chore(release): research-dossier proof at 5c055cc (235 tests)`，commit `30cb2e4`，branch `architecture/research-v2`，state `WORKFLOW_RUN_STATUS_COMPLETED`，conclusion `WORKFLOW_RUN_CONCLUSION_SUCCESS`，2m 5s（首次观察时为 IN_PROGRESS，复检已完成成功） |
| 8 | main / V1 / B 未触碰 | **PASS** | main = origin/main = `e5da620`（HEAD 祖先，分支外未改写）；V1 annotated tag `v1-frozen-1f2b341` 解引用 `1f2b341` = `fix/autonomous-audit-remediation` tip；B（外部 investment-agent）不在本仓库，仓库侧无写入路径，外部工作区无法从本仓库证明 |

## 2. Dossier 实测

- 命令：`python -m goe.cli dossier --out /tmp/qa_dossier` → 4 个 watch dossier，exit 0。
- 与已提交文件对比（相对 artifact 路径重生成）：
  - N225：`145989f6…` (json) / `125d4d97…` (md)
  - TAIEX：`81cbe6ea…` / `8caa0a3b…`
  - QQQ：`069df37b…` / `e33560cc…`
  - XLV：`ecab559b…` / `bbda5812…`
  - VIX（Case B，`--id` 生成）：`6149a824…` / `99df6f6f…`
- 以上 sha256 与 `research_dossiers/2026-11-13/` 中已提交文件逐一相同。
- 说明：VIX 为 archive/gap 0 的 Case B 样例，当前默认 CLI 只输出 research/watch，故不在默认 4 个之内；README 已按 Case A/B/C/D 说明，属设计而非漏生成。

## 3. 测试与 proof

- 245 collected；`not network and not realdata` → **235**。
- `audit/test_evidence/20261115T095251Z_5c055cc813.proof.json`：235 passed、0 failed、0 errors、0 skipped；rerun 235；log sha256 `ea395f7e…`，junit sha256 `995b3604…`。
- `verify-release --no-rerun` 结构校验 accepted（rerun=null）；完整 235 重放由 CI run 26 在 30cb2e4 完成并成功，避免 6 分钟时限内重复跑 2m45s 套件。
- 本地 `pytest -m "not network"` 全量实跑 exit 0。

## 4. identity / PIT / curve 回归

- `git diff --name-status 5c055cc..30cb2e4` 仅 4 个 `audit/` 证据文件（release manifest、proof、log、junit），**goe/tests/config/contracts/scripts/evaluation 零改动**；30cb2e4 的代码与已验收的 5c055cc 字节一致。
- 定向回归：`test_research_identity`、`test_time_semantics`、`test_contracts`、`test_external_evidence` → 22 passed，1 skipped（`test_contracts.py:96`，`GOE_SLOW=1` 的真实数据集成，非失败）。
- 关键约束仍在：`goe/db.py:814-840` 同 id 不可改 as_of/instruments/theme，终态保护；`goe/evidence/external.py` 拒绝未来 publication/available_at/vintage 并校验 curve/provider/units；contracts 曲线身份用例保留。
- 未发现 identity/PIT/curve/P1 修复回归。

## 5. main / V1 / B

- main `e5da620`、origin/main 同点，是 HEAD 祖先；本分支未改写 main。
- V1 tag `v1-frozen-1f2b341` → `1f2b341`，与 `fix/autonomous-audit-remediation` 同点，保持冻结基线。
- B 为外部 investment-agent，不在本仓库；仅 fact-only handoff adapter，未发现向 B 写产品或数据的路径。外部工作区状态不在本仓库可证明范围（不冒充已验证）。
- 工作区验证前 clean；唯一新增为本文件。

## 6. 新缺陷

**P0：无。P1：无。**

**P2-1（新增，不阻塞验收）— dossier content hash 依赖传入的 artifact 路径**

- 默认 `goe.cli dossier --out …` 把 `artifact` 解析为绝对路径并写入 dossier 的 `Source & Version References.artifact_path`，该字段参与 `content_sha256`（`goe/dossier.py:147`）。
- 同一 commit、同一内容，用默认绝对路径重生成得到 `206e1233…`，而 committed 为 `c1c6944f…`；改用相对 `--artifact evaluation/v2_candidates_20_2026-11-13.json` 后所有 hash 精确复现。
- 影响：跨机器/默认用法下内容 hash 不可复现，并会写入本地绝对路径；不影响数据内容、18 节完整性或本次验收结论。
- 建议（后续，不在本轮改）：入参统一归一化为仓库相对路径，或在 content hash 前剔除路径字段。

## 7. 残余风险（既有，非本轮新增）

1. scan evidence 依赖本地 gitignored DB/报告/导出产物，干净 clone 只能重放测试 proof，不能独立重算 scan（历史已接受 residual）。
2. `verify-release` 只校验测试 proof 与 commit 许可；scan artifacts 需 `verify_scan_evidence` 单独校验（本轮已单独执行并通过）。

**最终判定：工程验收 PASS；0 项 P0、0 项 P1；1 项新增 P2（dossier 路径依赖的内容 hash），建议后续修复。**
