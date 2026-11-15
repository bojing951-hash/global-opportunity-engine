# QA — 研究产物修复独立复核（HEAD a63bd1b / code bbde58d）

- 审查对象：`architecture/research-v2` @ `a63bd1b`（代码 `bbde58d`，243 tests 证明）
- 方式：只读 Git、DB（`mode=ro&immutable=1`）、artifact JSON 规范化比对、`git diff bbde58d^..bbde58d`；未改代码，仅新增本报告。
- 时限约 3 分钟；未重跑 243 全量，复用 release proof + junit。CI 按任务说明仍 pending，未核验为绿色。

## 结论（Verdict）

**不通过（FAIL / FUNCTIONAL NOT VALIDATED）**：10 条 DB finding 的 `artifact_path` 已全部指向唯一、存在、版本化的 `RF-*/finding.json`，且 payload 与 DB 一致；4 个 legacy root 均已标注，memory/DB 未删除历史行。但 **“不覆盖当前 3 份 artifact”不成立**：修复提交 `bbde58d` 无条件重写了 3 份当前案例 artifact 的 `finding.json` 与 `findings.md`，导致当前报告被截短、JP 泛化标签被回退、`code_commit` 变成旧值。属 P1，不能签署“无覆盖 / 可追溯”的完整结论。

- **P0：无。**
- **P1：1 项（P1-1，见下）。**
- **最终状态：FAIL（P1 未关闭前不接受）。**

## P1-1 当前 3 份 artifact 被修复脚本覆盖

`git diff --name-status bbde58d^ bbde58d` 明确显示以下 3 组当前版本化 artifact 的 `finding.json` 与 `findings.md` 均为 **M（modified）**：

- `research_results/2026-11-13/CM_ETF_SLV/RF-RC-20261113-CM_ETF_SLV-4da1f0cfcde7-4039396d/`
- `research_results/2026-11-13/JP_EQ_N225/RF-RC-20261113-JP_EQ_N225-e4953e300c07-d23f1f99/`
- `research_results/2026-11-13/US_FX_DXY/RF-RC-20261113-US_FX_DXY-66e350e808c5-03588083/`

具体回归：

1. **`findings.md` 被截短，丢失证据章节**：
   - CM：37 行 → 11 行；JP：43 行 → 14 行；US：36 行 → 11 行。
   - 原有 `Acquired evidence`、`Tests`、`Hypothesis updates`、`Still unknown`、`next action` 全部消失，只剩 finding/research/status 与 `What we learned`。当前案例的人工可读证据链被降级。
2. **JP 当前 `finding.json` 的泛化标签被回退**：
   - `Local market factor` → `Japan broad local market factor`；
   - `Global risk lead` → `US/global risk lead`；
   - `FX/cross-border flow` → `JPY/cross-border flow`；
   - `Fundamentals` → `Japan fundamentals`；
   - `Regional co-move` → `Regional North Asia co-move`。
   - 即撤销了 `8406799` “remove Japan-specific labels from generic templates” 的修复效果。
3. **3 份当前 `finding.json` 的 `code_commit` 均被改为旧值**：
   - `b93d5e66920ed95347568fe2e8c1f4c61570df84` → `4fa60862cc168b532bcb2e11871e2c5bf8cda9f1`。
   - 当前 artifact 的 `finding.json` 因此与其同目录 `evidence.json/plan.json/tests.json`（`aa2b4da`、`b93d5e6` 生成）及 release code `bbde58d` 的 provenance 不再一致。
4. **根因**：`scripts/repair_research_artifacts.py:37-39` 对 DB 中全部 10 条 finding 无条件 `write_text` 写入 `<asset>/<finding_id>/finding.json` 和 `findings.md`，没有“已存在当前 artifact 则跳过/拒绝覆盖”的保护；aa2b4da 已生成的 3 份当前 artifact 被当成待修复对象重写。
5. **影响**：任务验收项“no overwritten current 3 artifacts”直接失败；“当前 artifact 不可变 / 历史证据可追溯”的对外承诺仍不成立，只是从“DB 指向旧 root”变成了“当前 artifact 被旧 DB payload 回填”。因 10 条 finding 仍全部为 `INCONCLUSIVE`、数据与结论未变、未发生跨 finding 串写，定级 P1 而非 P0。

**建议修复方向（本次未改代码）**：恢复 3 份当前 artifact 到 `aa2b4da` 的内容（含完整 `findings.md` 与泛化标签）；若必须让 DB payload 与文件一致，应显式记录“当前 artifact 被 DB 回填”的 provenance/哈希，而不是静默覆盖；修复脚本增加 skip-if-exists 或显式 `--force`，并对已存在文件做哈希/内容校验。

## 通过项（PASS）

### 1. 10/10 DB finding 的 artifact_path 唯一、存在、版本化，payload 与 DB 一致

只读查询 `research_v2_findings`（10 行），逐条打开 `artifact_path`：

- **路径唯一性**：10 条路径互不相同（10/10 unique）。
- **文件存在**：10/10 存在。
- **版本化路径**：10/10 匹配 `research_results/<as_of>/<asset>/RF-*/finding.json`。
- **finding_id 一致**：10/10 文件内 `finding_id` == DB 行 `finding_id`。
- **payload 一致**：10/10 文件 JSON 与 DB `payload_json` 规范化（canonical JSON）相等；非仅 finding_id 匹配。

分布：JP_EQ_N225 4 条、CM_ETF_SLV 3 条、US_FX_DXY 3 条（含 `RF-N225-20261113` 历史 finding）。此前 P1 的”6 条历史 finding 指向被覆盖 root 文件“已消除。

### 2. legacy root 标记

- `research_results/2026-11-13/` 下 4 个含 `finding.json` 的 root 目录：`CM_ETF_SLV`、`JP_EQ_N225`、`N225`、`US_FX_DXY`。
- 4/4 均有 `LEGACY_ROOT.md`，且均已被 Git track；内容明确写“Legacy root artifact，权威 finding 在 relink 的 `RF-*` 版本化子目录”。
- 4/4 root `finding.json` 仍存在，但已被标记为 legacy，未再作为 DB 当前指针。

### 3. memory / DB append-only

- `research_v2_findings=10`、`research_v2_hypothesis_revisions=56`、`research_v2_evidence=126`、`research_v2_events=120`、`research_v2_hypotheses=117`、`research_v2_workflow=3`；`PRAGMA integrity_check=ok`。
- 10 条 finding 状态全部 `INCONCLUSIVE`；无删除行、无新增/替换 finding。
- `scripts/repair_research_artifacts.py` 对 DB 只有 `UPDATE research_v2_findings SET artifact_path=...`，未改 `payload_json`，无 DELETE/INSERT。
- `research_results/RESEARCH_MEMORY.md` 在 `bbde58d` 中未变；其 Git 历史无删除行（仅新增契约文本）。

### 4. 测试证明（243）

- `audit/releases/release_bbde58d42c.json`：`passed=243`、`skipped=0`、`git_dirty=false`，rerun 243。
- `audit/test_evidence/20261115T141822Z_bbde58d42c.proof.json`：exit_code=0、passed=243、failed=0、errors=0、skipped=0。
- junit XML：243 个 `<testcase>`。
- 说明：仅核验离线 proof 与 junit；CI 仍 pending，不作为已绿证据。

## 附注（P2，不阻断本次判定）

- P1 的次生问题：当前 3 份 `finding.json` 的 `code_commit=4fa6086`，早于同目录其他产物的生成代码 `b93d5e6`，也不同于 release code `bbde58d`；即使接受“用 DB 回填”，也应避免这种 provenance 混淆。
- 历史 7 条 finding 的 `findings.md` 为脚本生成的极简版（仅 learned），无 tests/hypotheses 章节；这是 DB payload 不含这些字段的已知限制，建议在报告中标注“由 DB payload 重建”，避免与完整案例报告混淆。
