# QA_SCAN_FINAL_H — 冻结 HEAD e6853ca / scan v5 独立终审（H 角度）

- 对象：`e6853ca`（业务代码 `9d51769`，branch `architecture/research-v2`），v5 proof 219，scan `scan-20261115T044634Z-b68802`
- 方法：独立复算 + 真实 DB/artifacts 副本（`sqlite3 .backup` → `/tmp/qa_h/`，`GOE_ROOT=/tmp/qa_h`），全部篡改只在 /tmp；仓库只写本文件
- 时限：约 6 分钟；未改代码/数据，未触碰 main / V1

**结论：PASS WITH ISSUES（有条件通过）。P0=0，新增 P1=0。P1-C1（输出字段指纹）已闭环；剩余为已接受/应显式接受的 P2（信任边界、可移植性、文档）。Phase 1 工程可冻结，但须先提交工作区中的 v5 残余文档并修正错误引用（当前工作树 dirty）。DISCOVERY: NOT VALIDATED。**

---

## 1. 真实 scan + 全列输出指纹 + artifact 冻结哈希

真实副本 `verify_scan_evidence(require_artifacts=True)`：

```
BASE ACCEPTED scan-20261115T044634Z-b68802  11 opp / 1506 anomalies
mode=offline status=success started=2026-11-15T04:46:34Z
counts prices=358310 indicators=159508 anomalies=1506 transmissions=5 opportunities=11
stats.output_fingerprint == 现场重算 True；manifest scan_counts 全等
report / scan_json / pipeline 三文件 sha256 == manifest.artifacts == stats.artifact_sha256（True×3）
reports/report_2026-11-13.md 7ac34255… / reports/scan_2026-11-13.json cd0bc502… / exports/pipeline_2026-11-13.json 9e6bd81a…
```

`goe/db.py:scan_output_fingerprint()` 现按 `PRAGMA table_info` 枚举三张输出表全部列（anomalies 15 列 / transmissions 14 列 / opportunities 28 列）。独立逐列篡改（不改 stats/artifacts）：

| 篡改列（此前未哈希） | 结果 |
|---|---|
| opportunities.catalysts_json | **REJECTED** `scan output content changed after the scan` |
| transmissions.notes | **REJECTED**（同上） |
| anomalies.created_at | **REJECTED**（同上） |
| opportunities.title（E/F 的 P1-C1 原攻击） | **REJECTED**（同上） |

→ **P1-C1（输出表全列指纹）确认闭环**，v5 声明在此口径成立。

## 2. 空/假/过期/部分/缺失/不匹配用例

| 场景 | 结果 |
|---|---|
| 空 DB（无 scan_runs） | REJECTED `no scan_runs evidence` |
| 伪造 scan_runs.config_hash | REJECTED `config_hash does not match current config` |
| 伪造 scan_runs.data_hash | REJECTED `data_hash does not match recomputed DB content` |
| stats.artifact_sha256 改假 | REJECTED `report content does not match the scan-time artifact hash` |
| 篡改 report 正文 | REJECTED（同上） |
| reference_date=2026-11-21（8 天） | REJECTED stale；11-20（7 天）ACCEPTED，边界正确 |
| stats.ingest.status=partial | REJECTED `ingest status is partial` |
| 删除 report（require_reports=True） | REJECTED `required artifact missing` |
| 删除 report + require_reports=False | **ACCEPTED**（P2，发布路径 `build_manifest` 默认 True，不阻断） |

JUnit 独立解析：219 testcase、219 unique、skipped/failure/error=0；scan 专项 11 条；proof `required.count=executed.count=219`、`required_sha256==executed_sha256=e0ce8c31…`，manifest `rerun 219/219/0`；log/junit 现场 sha256 与 proof 记录一致（`c18b1fd5…` / `29d80524…`）。

## 3. 信任边界（P2，非新增）

- 自洽改写实测：改 DB 机会 title + 重算 `stats.output_fingerprint` + 同步 scan_json `meta.output_fingerprint` + 同步 `stats.artifact_sha256[scan_json]` → **ACCEPTED**。即“artifact 与 DB 内容不交叉对账”的信任边界确实存在；只改 DB/指纹/scan_json 任一项仍会被拒。
- `indicators.unit` 篡改 → **ACCEPTED**（`data_fingerprint` 仍不含 unit/fetched_at）；`opportunity_events.note`（本 scan 11 行）篡改 → **ACCEPTED**（指纹只覆盖三张输出表）。二者不进入已冻结 report/scan-json（`"unit"` 在 scan-json 出现 0 次），属 DB 侧静默分叉/下游复用风险，归 **P2**；建议在冻结文档显式列为 accepted P2，不计为新增 P1。
- 附注：改 `stats_json.data_hash` 不被校验（校验用 `scan_runs.data_hash` 列），为无效字段，P3。

## 4. Manifest / 可移植性 / CI / V1-main

- manifest `release_9d51769823.json`：`git_commit=9d51769`（HEAD `e6853ca` 的祖先，证据-only 子提交）、`git_dirty=false`；三 artifact 哈希与现场逐一相等；`by_status` 4+2+3+2=11；全为相对路径，无绝对路径。
- 可移植性：`git ls-files reports exports data` = **0**；101 MB DB 与 artifacts 未入库，fresh clone 无法复验 scan evidence（只能复验 219 test proof）。manifest 本身可移植（JSON+相对路径），但 scan 证据不可从 clone 重建 → 沿用 **P2（accepted residual）**。
- CI：`.github/workflows/verify-release.yml` 仅 `ubuntu-latest`，仅 `goe.cli verify-release --proof`；无 scan evidence/DB 校验、无 macOS runner → **P2（未执行跨 OS/scan 校验）**。
- V1/main：`main=origin/main=e5da620`（3 个 docs/initial 提交，未动）；annotated tag `v1-frozen-1f2b341 → 1f2b341`（V1 冻结提交，pre-existing；不在 main 上，main 未新增 V1 变更）。工作区仅有 3 个**未提交 docs 修改**（PROJECT_STATE/RELEASE_GATE_ACCEPTANCE/TEST_EVIDENCE），无代码/数据/evidence 改动。

## 5. Accepted P2 文档状态（关键缺口）

在 **e6853ca 提交态**，v5 的 accepted-residual 清单尚未落地：`RELEASE_GATE_ACCEPTANCE.md` 最新提交版止于 v3；v5 addendum 只存在于**未提交工作区**，且仅覆盖 5 项中的 3 项（local DB 不可移植、CI 只 replay proof、self-consistent synthetic DB、no licensed consensus/term-OIS），**未显式记录**“伪造 ingest_runs 可过 live 校验”“artifact-vs-DB 无交叉对账”。另有未提交文档错误：

- `PROJECT_STATE.md` 写“latest release `release_5bcaa5de06` (219, v3)”——v3 实为 217，219 是 `release_9d51769823`（v5）；
- `audit/TEST_EVIDENCE.md` 写“219 passed at commit `c0caf384`”——219 对应 `9d51769`，`c0caf384` 非该 proof 提交。

→ **P2（文档/冻结证据）**：冻结前必须把 v5 addendum 提交，补齐 5 项 P2（fabricated ingest run、synthetic-DB trust boundary、artifact-vs-DB cross-check、CI unexecuted、no consensus/term-OIS），并修正上述引用；否则“accepted P2 已文档化”不成立。

## 6. 判定 / 冻结建议 / DISCOVERY

- **P0：0**（真实 scan/manifest/proof 均可独立复算；空/假/过期/部分/缺失/篡改 artifact 均拒绝）。
- **新增 P1：0**。P1-C1 输出字段指纹已闭环；`data_fingerprint`（unit/fetched_at）与 `opportunity_events` 为既有/延伸 **P2**，不改变已发布 artifacts。
- **Verdict：PASS WITH ISSUES（CONDITIONAL PASS）**。
- **Phase 1 冻结建议：有条件推荐冻结**（工程门禁达到冻结标准）。条件：① 提交工作区 3 个文档修改并把 5 项 accepted P2 写全、修正 v3/219 引用；② 冻结 tag/记录指向 clean HEAD（当前 `git status` dirty，仅 docs）；③ 不把“scan evidence 全可移植/全字段不可篡改”写成已验证。满足①后即可标记 Phase 1 ENGINEERING ACCEPTED，CI 跨 OS 与 scan 证据可移植性留 Phase 2 前补丁，不阻断冻结。
- **DISCOVERY：NOT VALIDATED**（20 candidates → 0 research / 20 intelligence，`evidence_gap`；无 consensus/term-OIS 许可源）。
