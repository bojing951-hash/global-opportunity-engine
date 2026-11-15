# QA_SCAN_FINAL_G — scan-evidence v5 全列指纹独立复验（G 角度）

- HEAD `e6853ca`（代码 `9d51769`，release 提交仅新增 proof 4 文件）；branch `architecture/research-v2`
- 复核对象：`goe/db.py::scan_output_fingerprint`（88684b2）、`goe/scan_evidence.py`、`audit/releases/release_9d51769823.json`、`audit/test_evidence/20261115T044832Z_9d51769823.*`
- 方法：真实 DB `sqlite3 .backup` → `/tmp/qa_g`，复制 `config/`、`reports/`、`exports/`；`GOE_ROOT=/tmp/qa_g` 下调真实 `verify_scan_evidence(require_artifacts=True)`；另在 `/tmp/qa_g_clone`（`git clone` 后 checkout 9d51769）做 proof 结构复验（rerun=False）。全部篡改仅发生在 `/tmp` 副本。本文件是唯一仓库写入。

**结论：PASS。P1-C1 已闭环；v5 未引入新 P0/P1。P0=0，新 P1=0。**

## 1. Q1 — 全列指纹与 DB 篡改拒绝（PASS）

`scan_output_fingerprint` 已从手选列改为 `PRAGMA table_info` 枚举 anomalies（15 列）、transmissions（14 列）、opportunities（29 列，含 `status_source`）全部持久化列，按主键排序哈希，并含 `run_id`；共 **58/58 列**。

逐列实验（每列改一行后重算）：**58 列全部 CHANGED**（`created_at`/`updated_at`/`notes`/`status_source` 等旧盲区均覆盖）。

真实 v5 scan `scan-20261115T044634Z-b68802`（as_of 2026-11-13）DB 副本上 `verify_scan_evidence(require_artifacts=True)`：

| 篡改（仅 DB，artifact 不动） | 结果 |
|---|---|
| baseline（未篡改） | **ACCEPTED** `scan-20261115T044634Z-b68802` |
| opportunities title / status_reason / invalidation | **REJECTED** `scan output content changed after the scan` |
| opportunities market / first_seen | REJECTED（同上） |
| transmissions title / trigger_json | REJECTED（同上） |
| transmissions conditions_json / assets_json | REJECTED（同上；conditions_json 为数组，需写入实际内容） |
| anomalies created_at / evidence_json | REJECTED（同上） |
| 删除 1 条 opportunity / 插入 1 条 transmission | REJECTED（计数+fingerprint） |

结论：任务指定的 6 个字段全部拒绝；“所有持久化输出列”口径成立（对照旧 F 报告 F/G 均 ACCEPTED，现已闭环）。

## 2. Q2 — artifact 哈希冻结与篡改拒绝（PASS）

`stats.artifact_sha256` 冻结 5 项，verify 对 report/scan-json/pipeline 三项按相对路径逐一比对：

| 篡改（/tmp 副本，保留计数/meta） | 结果 |
|---|---|
| report 追加正文 | **REJECTED** `report content does not match the scan-time artifact hash` |
| scan-json 改 `anomalies[0].magnitude` | **REJECTED** `scan_json content does not match ...` |
| pipeline 改 `opportunities[0].status` | **REJECTED** `pipeline content does not match ...` |
| 删除 report | **REJECTED** `required artifact missing` |
| 恢复原文件 | ACCEPTED（回归正常） |

manifest `artifacts` 三项 sha256 与现场文件逐一相等，且与 `scan_evidence.*_sha256` 一致。

## 3. Q3 — 真实 scan + manifest + proof 219（PASS）

- 真实 scan：358,310 prices / 159,508 indicators（`date<=as_of`）/ 1,506 anomalies / 5 transmissions / 11 opportunities；`config_hash=7d4d8ae1…`、`data_hash=9350b109…` 与 manifest 一致；`stats.output_fingerprint=91114997…` 可复算接受。
- manifest `release_9d51769823.json`：`git_commit=9d517698`、`git_dirty=false`，且 `git merge-base --is-ancestor 9d51769 HEAD` 成立；`by_status` 4+2+3+2=11。
- proof `20261115T044832Z_9d51769823`：schema v4、passed=219、failed=errors=skipped=0；required==executed=`e0ce8c31…`（219/219）；log/junit sha256 与文件一致；JUnit `tests=219`、failures=0、skipped=0；log 尾行 `219 passed, 10 deselected`；manifest `test_evidence.passed=219`、`rerun=219/219/0`。
- 干净 clone（9d51769 + 提交的 evidence 文件）`verify_test_proof(..., rerun=False)` → **PROOF STRUCT OK**：commit/required/executed 219 全吻合。未在时限内做完整 219 重跑（manifest rerun 已记录 219/219/0，log hash 未落盘属 P3 证据缺口，非本轮引入）。
- `pytest tests/test_scan_evidence.py` → **10 passed**（含新增 `test_output_fingerprint_covers_all_visible_columns`）。

## 4. Q4 — P0/P1 与冻结条件

- **P0：0**（无空库/假哈希/无扫描证据/伪 proof 生成 manifest 的路径；真实 v5 scan 可独立复算）。
- **新 P1：0**。P1-C1（全字段指纹）由 88684b2 修复并由本重复验；artifact 冻结 v4 起生效。
- 已知残留（非 v5 新引入，F 报告已列，维持）：扫描证据不可移植/CI 只跑 proof（`verify-release.yml` 仅 ubuntu + `verify-release --proof`，不验 scan evidence；reports/exports/data 未入库）——按“已接受 P2/CI”处理可冻结；`data_fingerprint` 仍未含 `indicators.unit/fetched_at`（P2）；`artifact_sha256` 5 项只验 3 项（P3）；verify→manifest TOCTOU（P3）；rerun stdout hash 未持久化（P3）；scan 后若有人用 `set_opportunity_status` 原地改机会状态会使指纹门禁拒绝（属设计意图，运维需知，P2 提示）。
- **Phase 1 冻结判定：可以冻结**（条件是接受上述 P2/CI 残留；本轮未发现新 P0/P1）。DISCOVERY 状态未变：NOT VALIDATED。
