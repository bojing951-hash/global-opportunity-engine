# QA_SCAN_FINAL_F — v4 verified-scan gate 独立复核（F 角度）

- 冻结 HEAD：`a1f3082`（业务代码 `f2b9d9e`，branch `architecture/research-v2`）；工作树 clean（`git status --porcelain` = 0）
- 复核对象：`goe/scan_evidence.py`、`goe/pipeline.py`（artifact 冻结）、`goe/release.py`、`goe/db.py`、`audit/releases/release_f2b9d9eaf0.json`
- 方法：真实 DB `sqlite3 .backup` → `/tmp/qa_f/goe.db`；将 `reports/`、`exports/` 三个真实 artifact 与 `config/*.yaml` 复制到 `/tmp/qa_f/`；`GOE_ROOT=/tmp/qa_f` 下调用真实 `verify_scan_evidence(..., require_artifacts=True)`。全部篡改只发生在 `/tmp` 副本，仓库与 V1/main 未改。
- 本文件是唯一仓库写入。

**结论：PASS WITH ISSUES。v4 的“扫描后改 report/scan-json/pipeline”已被冻结哈希堵住；但“完整字段指纹”仍未实现（P1-C1 残留，v4 未修）。**

---

## 1. Q1 — scan 后改三个 artifact 能否被接受：已修复（ACCEPT）

真实 v4 scan `scan-20261115T043427Z-593a4f`（as_of 2026-11-13）：

```
baseline: ACCEPTED scan=scan-20261115T043427Z-593a4f 1506 anomalies / 11 opp
report=c901cb9403b892e3 scanjson=308ba379f2a57e3e pipeline=1fa671a13c43df2f
```

`stats.artifact_sha256` 与三个真实文件、manifest `artifacts`/`scan_evidence` 的 sha256 **逐一相等**。篡改实验：

| # | 操作（/tmp 副本，保留 token/计数/meta） | 结果 |
|---|---|---|
| A | 改 report 正文（保留 4 个 provenance token） | **REJECTED** `report content does not match the scan-time artifact hash` |
| B | 改 scan-json `anomalies[0].magnitude`（计数/meta 不变） | **REJECTED** `scan_json content does not match ...` |
| C | 改 pipeline `opportunities[0].status`（id 集合/数量不变） | **REJECTED** `pipeline content does not match ...` |
| D | 删除 scan-json | **REJECTED** `required artifact missing` |
| E | 恢复原文件 | ACCEPTED（回归正常） |

即 QA_SCAN_FINAL_D 的 D4（真实 DB + 伪造 artifact 内容 → ACCEPTED）在 v4 已闭环。逻辑上 `require_artifacts=True` 只在 `build_manifest` 生产路径启用；缺失 `artifact_sha256` 的旧 scan（v3 及以前）会被 `scan stats have no frozen artifact hashes` 拒绝，无法降级复用旧 scan。

**残留（P3，不阻断）**：
- scan 时实际冻结了 5 个 artifact（另有 `exports/research_queue_2026-11-13.json`、`exports/HANDOFF_SCHEMA.json`），但 verify 只核对 report/scan-json/pipeline 三项；另两项事后改写不会被门禁发现（也未进入 manifest artifacts，故无发布影响）。
- verify 与 `build_manifest` 后续取哈希之间存在毫秒级 TOCTOU 窗口（需并发写者，发布流程串行；P3）。

## 2. Q2 — 完整字段指纹：仍未覆盖全部列（P1-C1 残留，FAIL 项）

`goe/db.py`：

- `data_fingerprint`：prices 只哈希 `instrument_id,date,open,high,low,close,adj_close,volume,source_id`，**不含 `fetched_at`/`run_id`**；indicators 只哈希 `series_id,date,value,source_id`，**不含 `unit`/`fetched_at`/`run_id`**。
- `scan_output_fingerprint` 仍是 v3 的部分列选择：anomalies 不含 `created_at`；transmissions **不含 `title,trigger_json,assets_json,conditions_json,notes,created_at`**；opportunities **不含 `title,status_reason,invalidation,catalysts_json,open_questions_json,market,asset_class,instruments_json,horizon,archetype,lifecycle_json,data_quality,first_seen,last_seen,...`**。v4 提交只加了 artifact 哈希，`goe/db.py` 未改。

真实 DB 副本实测（`verify_scan_evidence(require_artifacts=True)`）：

| # | 只改 DB 字段（artifact 未动） | 结果 |
|---|---|---|
| F | `opportunities.title/status_reason/invalidation` = TAMPER | **ACCEPTED** |
| G | `transmissions.title/trigger_json` = TAMPER | **ACCEPTED** |
| H | `indicators.unit` = TAMPER | **ACCEPTED** |

这些字段是报告/扫描 JSON 可见的：report 第 281–287 行直接输出机会 `title`/`status_reason`，`scan_2026-11-13.json` 的 `opportunities` 是整行 dump。因此“scan output content changed after the scan”这一强断言仍不成立。**影响已被 v4 缩小**：已发布的 report/scan-json/pipeline 被哈希冻结，事后改 DB 不会改变发布物；残留风险是 DB 侧字段可与冻结 artifact 静默分叉，后续从 DB 再导出/复用得到被改内容。QA_SCAN_FINAL_C 将 P1-C1 列为需要“修复或明确接受”的 P1，v4 未修复，本 HEAD 文档中也未见显式降级为 P2 的记录。**要冻结 Phase 1，需对该项明确接受为 P2（或实现整行指纹），否则按“全字段输出不可篡改”口径不可冻结。**

## 3. Q3 — 真实 scan/manifest、218 proof、fresh clone、可移植性

| 项 | 证据 | 结果 |
|---|---|---|
| 真实 scan | `scan-20261115T043427Z-593a4f`，358,310 prices / 159,508 indicators / 1,506 anomalies / 5 transmissions / 11 opportunities；config `7d4d8ae1…`、data `9350b109…` 与 manifest 一致 | ✅ |
| manifest | `release_f2b9d9eaf0.json`：`git_commit=f2b9d9e`、`git_dirty=false`；三 artifact sha256 与现场一致；`by_status` 4+2+3+2=11 且全部属于本 scan | ✅ |
| proof 218 | proof `20261115T043650Z_f2b9d9eaf0`：passed=218、skipped=0、required==executed=`4a3b56e7cc20…`；manifest `rerun` 218/218/0；JUnit 218/0 skipped（文件内） | ✅ |
| fresh clone | `git clone` 到 `/tmp/qa_f_clone`（HEAD a1f3082），`verify_test_proof(..., rerun=False)` → **PROOF-STRUCT accepted**，commit/218/hash 全部吻合；完整 218 重跑在写本文件时仍在运行，未在时限内取得结果（不宣称已通过重跑） | ⚠️ 结构通过 |
| CI/可移植性 | `git ls-files reports exports data` = **0**；CI 只有 `ubuntu-latest`，只跑 `goe.cli verify-release --proof`，**不跑 scan evidence**，CI workflow 中 `scan` 关键词 0 次；无 manifest/artifact 校验入口 | ❌ P1（沿用 QA_SCAN_FINAL_D 的 P1-2/P1-3，v4 未闭环） |
| 文档 | `RELEASE_GATE_ACCEPTANCE.md` 无 v4 addendum；`PROJECT_STATE.md` 写“latest release_5bcaa5de06 (218 tests, v3)”（v3 实为 217、v4 为 218）；`TEST_EVIDENCE.md` 仍写 `c0caf384`/214→218 | P2/P3（不阻断） |

## 4. Q4 — V1/main 与 P0/P1 清单

- V1/main 未被本阶段改动：`main=e5da620`（docs 提交），tag `v1-frozen-1f2b341` 仍指向 `1f2b341`；当前 branch 仅 `architecture/research-v2`，工作树 clean；本复核只写本文件。
- **P0：0**（未发现空库/假哈希/无扫描证据/伪 proof 生成 manifest 的路径；真实 v4 scan 可独立复算）。
- **P1（1 项，继承 QA_SCAN_FINAL_C 的 P1-C1，非 v4 新引入）**：`scan_output_fingerprint`/`data_fingerprint` 未覆盖全部列，DB 侧报告可见字段（机会 title/status_reason/invalidation、transmission title/trigger_json 等）在 scan 后被改仍 ACCEPTED。v4 artifact 冻结使已发布文件不可改，故实际可利用面已缩小，但“完整字段指纹”验收项不通过。
- **P1（环境/证据，沿用 D，未修）**：scan evidence 不可移植（reports/exports/data 未入库、无 manifest 验证入口、CI 不验 scan）；CI 仅 Ubuntu 且仅 proof。
- **P2/P3**：stats 可缺 `opportunities` 键；`by_status` 全局未按 scan 限定；7 天新鲜度使历史 manifest 不可复验；scan `started_at/finished_at` 未来值未校验；`artifact_sha256` 5 项只验 3 项；verify→manifest 哈希 TOCTOU；文档版本/计数陈旧；`indicators.unit` 与 `fetched_at` 未入 data_hash。

## 5. 判定

**Verdict: PASS WITH ISSUES（v4 的 artifact 冻结目标达成，完整字段指纹仍未达成）。**

- 剩余 P0：**无**。
- 剩余 P1：**2 类**（P1-C1 字段指纹；scan evidence 可移植性/CI，沿用 D），均未在 v4 修复；此外 v4 未引入新 P0/P1。
- **Phase 1 能否冻结：有条件可以**。若验收口径是“发布 artifact（report/scan-json/pipeline）在 scan 后不可改 + 真实 v4 scan/manifest/proof 218 可复算”，则 v4 已满足，可冻结，但必须把 P1-C1 明确写成“已接受 P2（DB 侧字段指纹不完整，发布物不受影响）”并把可移植性/CI 作为 Phase 1 后的 P1 补丁；若验收口径是“所有报告可见字段不可事后篡改”，则 **P1-C1 未闭环，Phase 1 不可冻结**。
- DISCOVERY 状态未变：NOT VALIDATED（本轮未重开研究评估）。
