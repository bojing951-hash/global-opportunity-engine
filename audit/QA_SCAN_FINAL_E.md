# QA_SCAN_FINAL_E — 冻结 HEAD 独立红队复核（v4 / artifact hashes）

- 复核对象：`a1f3082`（code `f2b9d9e`，branch `architecture/research-v2`），`goe/scan_evidence.py`、`goe/pipeline.py`、`goe/db.py`、`goe/release.py`、`audit/releases/release_f2b9d9eaf0.json`
- 环境：macOS，`.venv` Python 3.12；仓库只读，所有篡改实验在 `/tmp/qa_scan_e/`（`real.db.bak` 为真实 `data/goe.db` 的 sqlite backup，真实 artifacts 副本）
- 规则：未改任何代码/数据；除本文件外无仓库写入；未触碰 `main` / V1
- 时限：6 分钟

**结论：PASS WITH ISSUES（条件通过）。C/D 的 artifact 内容篡改 P1 已修复并独立复现拒绝；但 task 2 的 output fingerprint 覆盖面并未在 v4 落地，C 的 P1-C1 原样残留（opportunity title/status_reason/invalidation、transmission title/trigger/conditions 改后仍 ACCEPTED）。无新增 P0；无新增 P1（除该 carry-over）。**

---

## 1. P1 修复验证（真实 DB 副本，同一连接内 UPDATE 后立即 verify）

| # | 场景 | 结果 | 判定 |
|---|---|---|---|
| E0 | 真实 DB + 真实 artifacts，`require_artifacts=True` | ACCEPTED（prices=358310, anomalies=1506, opp=11） | ✅ |
| E1 | 改 report 正文，manifest/artifacts 哈希不变（stats 冻结哈希为准） | REJECTED `report content does not match the scan-time artifact hash` | ✅ P1 已修 |
| E2 | 改 scan-json 中 anomaly 内容 | REJECTED（scan_json 哈希不符） | ✅ P1 已修 |
| E3 | 改 pipeline 中 opportunity title | REJECTED（pipeline 哈希不符） | ✅ P1 已修 |
| E11 | 改 `stats.artifact_sha256` 中 report 哈希 | REJECTED（同上） | ✅ |
| E12 | `stats.artifact_sha256` 缺失（v3 旧扫描） | REJECTED `no frozen artifact hashes` | ✅ |
| S9 | 删除 report（默认 `require_reports=True`） | REJECTED `required artifact missing` | ✅ |
| S10 | 删除 report 且 `require_reports=False` | ACCEPTED | P2（`build_manifest` 用默认 True，发布路径不受影响） |

**关键判断**：artifact 哈希在 scan 结束时写入 `scan_runs.stats_json`，`build_manifest` 以 `require_artifacts=True` 重新校验；manifest 自身的哈希不参与校验，故“先改文件再改 manifest”不再有效。D4/D8 场景闭环。

## 2. Output fingerprint 覆盖面（task 2）— **未修复（残留 P1）**

`Store.scan_output_fingerprint()`（`goe/db.py:921`）仍只哈希：

- anomalies：全部列；transmissions：`transmission_id,as_of,mechanism_id,confidence,status,evidence_for_json,evidence_against_json`；opportunities：`opportunity_id,fingerprint,status,score,score_json,discovery_json,evidence_for_json,evidence_against_json`

真实 DB 副本实测：

| # | SQL 篡改（不改 stats） | 结果 | 备注 |
|---|---|---|---|
| E4 | 11 条 opportunity 的 `title/status_reason/invalidation` 全部改 `INJECTED` | **ACCEPTED** | 指纹未变 |
| E5 | 同上，并重算 `stats.output_fingerprint` | **ACCEPTED** | 重算值与旧值相同（字段不在哈希内） |
| E6 | transmission `title/trigger_json/conditions_json` 改为注入值 + 重算指纹 | **ACCEPTED** | 重算值不变 |

影响：DB 中进入报告/研究流程的标题、状态理由、失效条件、传导触发条件可在 scan 后替换而不被门禁发现；scan-json/report 因冻结哈希保持不变，故表现为 **DB 与冻结 artifacts 静默分叉**，下游读 DB 的结论被污染。此即 C 报告 P1-C1，v4 未修（`git show 16d1695` 无 `goe/db.py` 变更，测试也无对应字段用例）。若验收标准为“所有进入报告的派生输出字段不可事后改写”，本项阻断冻结。

## 3. 新鲜度/时序/ingest/OHLCV 边界

| # | 场景 | 结果 | 判定 |
|---|---|---|---|
| S13 | `reference_date=2026-11-21`（as_of 后 8 天） | REJECTED stale | ✅ |
| S14 | `reference_date=2026-11-20`（恰好 7 天） | ACCEPTED | ✅ 边界符合 `>7` |
| S3 | as_of 改为 2026-11-14（相对 reference 未来） | REJECTED future | ✅ |
| S4 | 一根 bar `fetched_at=2026-11-14T09:00Z`（as_of 次日、早于 scan start） | ACCEPTED | ✅ 正确允许隔夜抓取 |
| S5 | `fetched_at=2026-11-15T05:00Z`（晚于 scan started 04:34） | REJECTED `fetched_at after the scan started` | ✅ |
| S6 | 改 OHLCV close（+1） | REJECTED `data_hash` mismatch | ✅ |
| S7 | `mode=live` + `stats.ingest.status=success`，无 ingest_runs | REJECTED | ✅ |
| S8 | 同上 + 插入一条窗口内伪造 `ingest_runs(prices,success)` | **ACCEPTED** | P2（已知 P2-C1，非新 P1） |

## 4. 真实 manifest `release_f2b9d9eaf0.json`（ACCEPT）

- `git_commit=f2b9d9e…`，`git_dirty=false`；`HEAD=a1f3082` 为其 docs-only 子提交（diff 仅 4 个 `audit/` 文件），符合祖先链要求。
- `test_evidence`: `passed=218`、`skipped=0`、`required_sha256 == executed_sha256 = 4a3b56e7…`；proof `.proof.json` 存在（`git_commit` 一致）、JUnit `tests="218"`；log/junit 哈希与 proof 记录一致（本轮未重跑完整 218 条，引用 evidence 自身一致性）。
- `scan_evidence`: 现场 `verify_scan_evidence(require_artifacts=True)` ACCEPTED；counts 358310/159508/1506/5/11 与 DB、`scan_counts` 一致；`opportunities_by_status` 合计 4+2+3+2=11。
- artifact 哈希：manifest 中 report/scan-json/pipeline 三个 sha256 与现场文件逐一相等（`c901cb94…` / `308ba379…` / `1fa671a1…`），且与 `scan.stats.artifact_sha256` 冻结值一致。
- `proof_path` 为相对路径 `audit/test_evidence/…`，**无绝对路径**；scan as_of 2026-11-13 与 reference 2026-11-15 差 2 天，真实扫描有效。

## 5. 新发现与遗留

- **新增 P0：0**
- **新增 P1：0**；**残留 P1（C-P1-C1，未修）**：output fingerprint 未覆盖 opportunity `title/status_reason/invalidation`、transmission `title/trigger_json/conditions_json`（§2）。
- **P2（信任边界/CI，沿用 D）**：伪造窗口内 ingest_runs 可过 live 校验；artifact 只做“扫描时刻哈希”，未与 DB 内容交叉对账（扫描过程中生成的伪造内容会被一起冻结）；`require_reports=False` 时缺失 report 不拒绝；`by_status` 未按 scan 限定；7 天新鲜度使 manifest 事后不可复验；CI 仍仅 ubuntu + 仅 `verify-release --proof`，不校验 scan evidence/data。

## 6. 判定与 Phase 1 状态

**Verdict: PASS WITH ISSUES（条件通过）。**

- 定向 P1“artifact 冻结哈希拒篡改”**验收通过**；真实 218 proof、manifest 计数/哈希/路径均可独立复算；无新增 P0/P1。
- 但 C 的 **P1-C1（report-visible 字段指纹覆盖）未修复**，v4 代码与测试均无该字段；若验收要求“进入报告的派生输出内容全部不可事后改写”，则本项应判 **FAIL/不可冻结**。
- **Phase 1 工程状态：CONDITIONALLY ACCEPTED（未关闭）** — 需在冻结前对 P1-C1 做出“修复或明确降级 verified 措辞/接受限制”的书面决定；P2-C1/CI 不阻断但 release 文档不得宣称“输出/报告内容全量验证”。
- **DISCOVERY 状态：NOT VALIDATED**（沿用 PROJECT_STATE：20 candidates → 0 research / 20 intelligence，`evidence_gap`）。
