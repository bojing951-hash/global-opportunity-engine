# QA — 广义研究系统最终独立验收（HEAD f9a482c）

- 分支/对象：`architecture/research-v2` @ `f9a482c`（代码 `b93d5e6`，证明 `aa2b4da`）
- 方式：只读代码、Git、DB（`mode=ro&immutable=1`）、产物、证明与 GitHub Actions 公开页面；未改任何代码。仅新增本报告。
- 时限约 4 分钟；未重跑 243 全量，重放采用 release proof + junit/log 哈希 + 本地 `verify-release --no-rerun` + CI 实际 run 四重交叉核验。

## 结论（Verdict）

**有条件接受（CONDITIONAL ACCEPT）**：三条发布案例确实由同一泛化执行器 `execute_spec` 产出，roles/hypotheses 由 spec 注入，三份 versioned 产物与 DB 当前指针一致，243 tests 与 CI run #35 均绿；但“DB artifact_path 全部匹配 / 旧 root 产物已有 legacy 状态”不成立——10 条 finding 中 6 条仍指向被覆盖的 root 产物，且 3 组 root 产物无 legacy/superseded 标注。该问题不影响三案例结论，但破坏历史证据溯源，属 P1，不能无条件签署“append-only / 可追溯”的完整主张。

**P0：无。**
**P1：2 项（P1-1、P1-2，见下）。**
**最终状态：FUNCTIONAL NOT VALIDATED。**

## P1

### P1-1 六条历史 finding 的 DB `artifact_path` 与文件内容不匹配

只读 DB 全量比对（10 条 finding，逐条读取 `artifact_path` 文件的 `finding_id`）：

- **MATCH 4/10**：
  - `RF-N225-20261113` → `research_results/2026-11-13/N225/finding.json`（旧 N225，匹配）
  - `RF-RC-20261113-JP_EQ_N225-e4953e300c07-d23f1f99` → `.../JP_EQ_N225/<finding_id>/finding.json`
  - `RF-RC-20261113-US_FX_DXY-66e350e808c5-03588083` → `.../US_FX_DXY/<finding_id>/finding.json`
  - `RF-RC-20261113-CM_ETF_SLV-4da1f0cfcde7-4039396d` → `.../CM_ETF_SLV/<finding_id>/finding.json`
- **MISMATCH 6/10**：`RF-RC-...-e4953e300c07`、`RF-RC-...-66e350e808c5`、`RF-RC-...-4da1f0cfcde7` 及其 `-a715b958` / `-d9eebf25` / `-d1df303f` 三条，`artifact_path` 全部指向
  `research_results/2026-11-13/{JP_EQ_N225,US_FX_DXY,CM_ETF_SLV}/finding.json`；这些 root 文件现存内容的 `finding_id` 已分别变为
  `...-d23f1f99` / `...-03588083` / `...-4039396d`，与 DB 行不一致（即旧证据链接指向已经被覆盖的 artifact）。
- 根因：`goe/db.py:997-1003` 的 `ON CONFLICT(finding_id)` 只对“同一 finding_id 重新写入”重链 `artifact_path`；历史行 finding_id 不同，重跑时不会被迁移/重链，也无一次性 repair 迁移。
- 影响：DB 行层 append-only 仍保留，但对外证据链（DB→artifact）对 6 条历史 finding 已断；违反“版本化后 DB artifact_path 全部匹配”的验收项。

### P1-2 旧 root 产物未标注 legacy/superseded，且仍被 tracked / 被引用

- `git ls-files` 显示 root 产物（如 `research_results/2026-11-13/JP_EQ_N225/finding.json`、`US_FX_DXY/finding.json`、`CM_ETF_SLV/finding.json`）仍被仓库跟踪；其 `code_commit` 为 `ad203d9`，而当前三份 versioned 产物为 `b93d5e6`，工作树 clean。
- 旧 `N225` root 有 `ACCEPTANCE.md`，legacy 身份可识别；但上述三组 root 产物没有任何 `superseded_by`、legacy 或历史版本说明，且部分 finding 行的 `artifact_path` 仍指向它们（P1-1），易被当作当前证据误用。
- 结论：旧 root 产物仅“事实存在”，未达到“known legacy status”。

## P2（非阻断，建议后续处理）

1. **同 finding_id 重跑仍会原位覆盖**：`goe/research_engine.py:297-318` 对 versioned 目录内 5 个文件仍无条件 `write_text`。目录只按 `finding_id` 版本化；同一输入重跑（尤其代码版本变化时 `code_commit` 进入 payload）会重写同一目录，没有 write-once/拒绝覆盖保护。“不同 finding 不再互相覆盖”成立，但“artifact 不可变”仍未强制。
2. **equity 模板仍残留日本语义**：`research_engine.py:142/173/180/192/205` 仍有 `TOPIX`、`broad Japan/local`、`Taiwan/Korea`、`Asia semiconductor`。当前 DXY/SLV 产物 grep 无 Japan/TOPIX/Taiwan/Korea，故“其他案例无日本标签”通过；但新增非日本 equity 案例仍会继承这些文案。
3. **遗留 per-ticker 路径**：`goe/research_exec.py:108` 的 `execute_nikkei_case` 和 `goe/cli.py:394-404` 的 `research-case --case nikkei` 仍在，且打印旧 root 路径 `2026-11-13/N225/findings.md`；它不是泛化引擎执行路径，但“无 per-ticker executor”只在 `execute_spec` 内成立。
4. `audit/CI_SUCCESS_2026-11-15.md` 只补录到 run #34，未补 run #35（文档滞后）。

## 关键核验证据（PASS 项）

### 1. 版本化目录与三案例

- 3 个 versioned 目录，每个仅 1 个 finding，各含 `finding.json/plan.json/evidence.json/tests.json/findings.md`：
  - `research_results/2026-11-13/JP_EQ_N225/RF-RC-20261113-JP_EQ_N225-e4953e300c07-d23f1f99/`
  - `research_results/2026-11-13/US_FX_DXY/RF-RC-20261113-US_FX_DXY-66e350e808c5-03588083/`
  - `research_results/2026-11-13/CM_ETF_SLV/RF-RC-20261113-CM_ETF_SLV-4da1f0cfcde7-4039396d/`
- 三案例 workflow state 均为 `INCONCLUSIVE`；finding status 均为 `INCONCLUSIVE`，无 alpha/因果成功声明。
- 当前 3 条 DB finding 的 `artifact_path` 与 versioned 文件内 `finding_id` 逐条 MATCH。

### 2. 泛化执行器（roles/hypotheses 注入，无 ticker 分支）

- `research_engine.py:121-134`：`R, H = spec.roles, spec.hypothesis_ids`，测试与更新通过 `role()/hid()` 取值；案例定义在 `research_orchestrator.py:78-131` 以 `roles={...}` 注入。
- `execute_spec` 仅按 `case_kind`（equity_event/fx_level/commodity_event）分支，无按 ticker 的执行分支；`grep spec.asset` 仅见资产取值/存在性检查（`:95-115`）。
- 三案例 `JP_EQ_N225` / `US_FX_DXY` / `CM_ETF_SLV` 均由 orchestrator 的 `case_nikkei/case_dxy/case_silver` 经 `run()` → `execute_spec` 执行。
- DXY/SLV 产物 grep `Japan|Japanese|TOPIX|Taiwan|Korea` 无命中。

### 3. 追加式记忆 / rescan / workflow

- 定向测试 `tests/test_research_identity.py tests/test_research_orchestrator.py`：**8 passed in 1.20s**（含 `test_rescan_preserves_research_hypotheses_evidence_and_findings`、orchestrator rescan 不重置）。
- DB：findings=10（仅追加，历史行未被删除）、`research_v2_hypothesis_revisions=56`、`research_v2_events=120`；三案例 `research_v2_workflow` state=INCONCLUSIVE。
- `next_case` 对 `BLOCKED` 直接 `continue`（`research_orchestrator.py:56`），`run()` 异常置 BLOCKED 并 re-raise（`:44-47`）；当前无 BLOCKED 行，跳过逻辑由测试覆盖。

### 4. 证明 / 测试 / CI

- `audit/releases/release_aa2b4da695.json`：`git_commit=aa2b4da...`、`git_dirty=false`、`passed=243`、`skipped=0`、required/executed sha256 同为 `ba7656d6...`。
- `audit/test_evidence/20261115T140744Z_aa2b4da695.log`：`243 passed, 10 deselected`。
- junit：**243** 个 `<testcase>`，`<failure>/<error>/<skipped>` 均为 **0**。
- 本地 `verify-release --proof ... --no-rerun` rc=0，accepted 243（rerun=null）。
- GitHub Actions run **#35**（id `43722788094`），head **`f9a482c`**，workflow `verify-release`，页面显示 `completed successfully`、`243 tests`；`git ls-remote origin architecture/research-v2` = `f9a482c`。
- 说明：proof 的 `git_commit` 是 `aa2b4da`，HEAD `f9a482c` 仅新增 `audit/` 证明/发布文件；CI 在该 HEAD 上重放 243 tests 通过，与 release 声明一致。

## 最终判定

- **PASS**：三案例同引擎、roles/hypotheses 注入、三份 versioned 产物逐一对应、PIT/INCONCLUSIVE/无过度声明、rescan/workflow/BLOCKED 主路径、243 tests、CI run #35 绿色。
- **FAIL/P1**：6/10 历史 finding 的 `artifact_path` 指向被覆盖的 root 产物；旧 root 产物无 legacy/superseded 标注。修复方式：一次性迁移按 finding_id 分目录（或为旧行写历史目录），并给 root 产物加 `LEGACY/SUPERSEDED` 标记；同 finding_id 写入增加“已存在则拒绝覆盖”保护（P2-1）。
- **Status：FUNCTIONAL NOT VALIDATED。**
