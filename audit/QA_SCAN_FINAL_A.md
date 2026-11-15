# QA_SCAN_FINAL_A — scan_evidence / build_manifest 独立红队复核

- 复核对象：`goe/scan_evidence.py`、`goe/release.py::build_manifest`
- 冻结基线：`94f632b`（branch `architecture/research-v2`，业务代码即 `1c57cba`；两 commit 差异仅 `audit/` 证据文件）
- 环境：macOS，`.venv` Python 3.12.13；所有实验 DB 在 `/tmp/qa_scan_a/` 下重建，仓库只写本报告
- 规则：未改任何代码；除本文件外无仓库写入
- 结论：**PASS WITH ISSUES（有条件通过）**
  - 真实 release `release_1c57cba580.json` 的证据链完整、可复验，未发现伪造通过。
  - 但 `scan_evidence` 的 “verified / rejects stale, forged” 承诺在 **stale scan** 与 **扫描后写库篡改** 两类场景不成立（P1），Phase1 只能有条件关闭。若验收标准是“必须拒绝这两类攻击”，本次应判 **FAIL**。

---

## 0. 判定说明

攻击矩阵共 22 项：21 项行为符合预期，1 项（stale）与 4 项“接受”属于本次发现的绕过面（同一结果表内已标注）。核心哈希/计数/来源/INGEST 拒绝逻辑有效；问题集中在**哈希覆盖面**与**新鲜度/证据独立性**。

| 维度 | 结果 |
|---|---|
| 空库、假 success、假 config_hash、假 data_hash、同数量改价 | 全部拒绝 ✅ |
| as_of、统计计数、报告 token、scan-json 计数、pipeline provenance/count/ids | 全部拒绝 ✅ |
| 未注册 source、未来 price fetched_at、partial ingest、live 无 ingest | 全部拒绝 ✅ |
| stale scan（as_of 2020）、扫描后改 anomaly/opportunity/OHLCV、future indicator fetched_at、伪造报告、ingest 纯声明 | **接受 ❌（P1/P2）** |
| 真实 manifest 的 scan counts、artifact hashes、215 proof | 全部一致 ✅ |

---

## 1. 真实 release 复核（`audit/releases/release_1c57cba580.json`）

复核方法：从 `data/goe.db` 做 SQLite backup 到 `/tmp/qa_scan_a/real.db`，用真实 `check_data_readiness` 调 `verify_scan_evidence`，并与 manifest 逐字段比对。

| 检查项 | 证据 | 结果 |
|---|---|---|
| scan_evidence 计数 | 358,310 prices / 159,508 indicators / 1,506 anomalies / 5 transmissions / 11 opportunities，与 `scan_counts` 完全一致 | ✅ |
| config_hash / data_hash | `7d4d8ae1…` / `9ddd93ef…`，与 DB 独立重算一致 | ✅ |
| report / scan-json / pipeline sha256 | 三个文件现场重算分别等于 manifest `artifacts` 中的 `24a50fdd…` / `391b6b06…` / `8bb95e91…` | ✅ |
| 215 accepted | 干净 clone（`94f632b`，venv Python 3.12）`verify_test_proof(..., rerun=False)` → `PROOF ACCEPTED 215 offline`；JUnit 215 tests、0 skipped；`required_sha256 == executed_sha256` | ✅ |
| manifest 生成时序 | `created_at=2026-11-15T04:06:18Z`，晚于 scan `started_at=03:15:40Z` 与 proof `ended_at=04:04:51Z`；代码顺序是先 `verify_test_proof(rerun=True)`、再 `verify_scan_evidence`、最后 `path.write_text`（`release.py:684,739`） | ✅ |
| 验证失败不落盘 | 空库 + fake proof 调 `build_manifest` → `ReleaseError: verified scan evidence failed: no scan_runs evidence`，输出目录为空 | ✅ |
| 冻结 HEAD 关系 | manifest `git_commit=1c57cba` 为 HEAD `94f632b` 的父 commit；`git diff --stat 1c57cba 94f632b` 仅 4 个 `audit/` 证据文件，`_check_commit` 允许该差异 | ✅ |

**结论：真实 release 的 scan 证据和 artifact 哈希未被伪造，manifest 确在 scan 验证之后写出。**

未做：未重跑 215 条测试（10 分钟时限）；只做 `rerun=False` 的独立接受验证，并核对 manifest 中 `rerun.passed=215/executed=215/skipped=0`。重跑结论来自证据文件本身，未独立复现其耗时段。

---

## 2. 攻击矩阵（可复现）

合成 DB harness：`/tmp/qa_scan_a/harness.py`（22 项断言，0 FAIL；“PASS”= 行为符合预期）。真实 DB 篡改用 `/tmp/qa_scan_a/real.db`、`fresh.db`，走真实 readiness，不 monkeypatch。

| # | 攻击 | 预期 | 实际 | 判定 |
|---|---|---|---|---|
| 1 | 空 DB | 拒绝 | `no scan_runs evidence` | ✅ |
| 2 | 假 success（status=success、无 prices） | 拒绝 | `no price observations at scan as_of` | ✅ |
| 3 | 假 `config_hash` | 拒绝 | `scan config_hash does not match current config` | ✅ |
| 4 | 假 `data_hash` | 拒绝 | `scan data_hash does not match recomputed DB content` | ✅ |
| 5 | 同 row count 改 close（100→101） | 拒绝 | `data_hash does not match` | ✅ |
| 6 | 错 `as_of`（2026-01-02） | 拒绝 | `no price observations at scan as_of` | ✅ |
| 7 | **stale success，as_of=2020-01-03，DB/哈希/artifact 自洽** | 拒绝 | **接受** | ❌ P1 |
| 8 | `ingest.status=partial` | 拒绝 | `release requires complete ingest` | ✅ |
| 9 | 缺 report | 拒绝 | `required artifact missing` | ✅ |
| 10 | report 无 provenance token | 拒绝 | `report does not contain provenance token` | ✅ |
| 11 | scan-json anomaly 计数不一致 | 拒绝 | `scan json anomaly count disagrees with DB` | ✅ |
| 12 | pipeline provenance 哈希不一致 | 拒绝 | `pipeline export provenance hashes disagree with DB` | ✅ |
| 13 | pipeline `n_opportunities` 不一致 | 拒绝 | `pipeline export opportunity count disagrees with DB` | ✅ |
| 14 | pipeline opportunity id 集合不一致 | 拒绝 | `pipeline export opportunity ids disagree with DB` | ✅ |
| 15 | 未注册 source | 拒绝 | `prices contain observations from unregistered sources` | ✅ |
| 16 | price `fetched_at` 在未来 | 拒绝 | `price rows have future fetched_at timestamps` | ✅ |
| 17 | **indicator `fetched_at`=2099，price 正常** | 拒绝 | **接受** | ❌ P2 |
| 18 | live mode、ingest=offline | 拒绝 | `live scan ingest status is 'offline'` | ✅ |
| 19 | **live mode、stats 里只写 ingest=success、无 ingest_runs 证据** | 拒绝 | **接受** | ❌ P1 |
| 20 | **扫描后修改 anomaly magnitude/score（真实 DB）** | 拒绝 | **接受** | ❌ P1 |
| 21 | **扫描后修改 opportunity status/score（真实 DB）** | 拒绝 | **接受** | ❌ P1 |
| 22 | **扫描后修改 price open/high/low/volume（真实 DB，close 不变）** | 拒绝 | **接受** | ❌ P1 |
| 23 | **伪造 report，仅保留 4 个 token** | 拒绝 | **接受** | ❌ P2 |
| 24 | 验证失败时是否先写 manifest | 不写 | 目录为空 | ✅ |

真实 DB 复核输出摘录：

```
counts match manifest: True
hashes match manifest: True
scan_id match: True as_of 2026-11-13
POST-TAMPER ACCEPTED: anomaly/opportunity content + future indicator fetched_at
data_hash unchanged: True
PRICE TAMPER REJECTED: scan data_hash does not match recomputed DB content
OHLCV TAMPER ACCEPTED (bypass); data_hash 9ddd93ef… prices 358310
```

（`PRICE TAMPER` 指 close 变动；OHLCV 指 close 之外的 open/high/low/volume。）

---

## 3. 发现

### P0

无。未构造出“空库/无数据/假哈希/未验证 scan”生成 manifest 的路径；真实 release 未被伪造。

### P1

**P1-1 扫描后 DB 内容篡改不可见（“DB changed after scan”成功）**

- 根因：`Store.data_fingerprint()` 只哈希 `prices(instrument_id,date,close,adj_close,source_id)` 与 `indicators(series_id,date,value,source_id)`（`goe/db.py:938-958`）。不含：
  - prices 的 `open/high/low/volume/fetched_at/run_id`
  - `anomalies`、`transmissions`、`opportunities` 全表
- 复现：真实 DB 副本上 `UPDATE anomalies SET magnitude=-999, score=999`、`UPDATE opportunities SET status='excluded', score=999`、`UPDATE prices SET open=open+5, high=high+5, low=low-5, volume=0` 后，`verify_scan_evidence` 仍返回 ACCEPTED，`data_hash` 不变；只有 close 变动被拒绝。
- 影响：manifest 声称的 “verified scan evidence” 只能证明 close/indicator value 未变，不能证明扫描输出（anomaly、transmission、opportunity）与 OHLCV 未被事后改写；研究/发布结论可在 scan 后被替换。
- 建议：对扫描实际读取的所有列与输出表做内容哈希（或落 scan 时刻快照哈希），manifest 同时记录输出表哈希；`prices` 至少覆盖 OHLCV + source。

**P1-2 stale scan 被接受（“old success”成功）**

- 根因：`verify_scan_evidence` 没有任何 wall-clock 新鲜度检查；`check_data_readiness(as_of=...)` 在显式 as_of 下只比较“数据最后日期 vs as_of”（`readiness.py:123-139`），不比较 `today - as_of`。
- 复现：合成 DB 的 prices/indicators/anomalies/artifact 全部对齐 2020-01-03，`scan_runs` 哈希按该 as_of 重算 → ACCEPTED。未用真实数据重建 2020 快照，但门禁逻辑上无时间上限。
- 影响：任何年代的旧成功扫描，只要 DB/报告自洽，都可被今天的 `build_manifest` 接受为 release 证据。
- 建议：增加 `as_of` 距今天上限（如 7–14 天）与 scan `started_at` 距今上限；或 release 明确要求 `as_of` 在窗口内。

**P1-3 live ingest 成功仅来自 `stats_json` 声明**

- 根因：`ingest_status = stats.get("ingest").status`（`scan_evidence.py:129`），未查 `ingest_runs`/`quality_issues`/覆盖率；live 模式只要求该字符串等于 `success`。
- 复现：合成 DB 设 `mode='live'`、`stats_json.ingest.status='success'`，无任何 `ingest_runs` 记录 → ACCEPTED。
- 影响：无法区分“真实完整 ingest”与“scan 行自报成功”；与模块 docstring “独立重建证据”不一致。
- 建议：要求存在对应 `ingest_runs` success 记录、finished_at、覆盖率/质量证据，并与 as_of 对齐。

### P2

1. **报告/流水线内容未做语义校验**：report 只检查 4 个 token 是否存在（`scan_evidence.py:199-207`），pipeline 只检查 provenance/count/ids；伪造报告（只保留 token）与改写 pipeline 标题/分数（重算哈希）均可通过。manifest 哈希是“生成时现算”，不是 scan 时刻绑定。
2. **未来 `fetched_at` 只查 prices**（`scan_evidence.py:145-147`）：indicator 行 `fetched_at=2099` 被接受。
3. **artifact mtime 容差 120s**（`scan_evidence.py:187`）：扫描后重新生成的 report/pipeline 只要 mtime 不早于 scan start-120s 即被接受；manifest 以现算哈希记录，无法证明 artifact 是 scan 原产物。
4. **fresh clone / CI 无法复验 manifest artifact**：`.gitignore` 忽略 `data/ reports/ exports/*`；干净 clone 无 DB/报告/导出，manifest 中三个 artifact 哈希无法重算。`verify-release` 只验 proof，不验 manifest/artifact；proof 还要求干净树与精确 Python 3.12（本机 `python3` 3.9 会被拒绝，需 `.venv`）。
5. **未跟踪 `audit/*.md` 会阻塞 proof 验证**：`_EVIDENCE_ALLOWED=("audit/test_evidence/","audit/releases/")`（`release.py:90,159`）。冻结 HEAD 上因兄弟 agent 的 `audit/QA_SCAN_ROUND1.md`，`verify_test_proof` 直接报 `cannot verify a proof on a dirty worktree`；本报告写入后同样会触发。干净 clone 才能通过。

### P3

- `scans[1]["started_at"] > scan["started_at"]`（`scan_evidence.py:93`）在 `ORDER BY started_at DESC` 下恒为假，是死代码；同时间戳的 scan 顺序不确定。
- `ScanEvidence.readiness_ok=True` 硬编码（`scan_evidence.py:234`），丢失 readiness 明细（不影响拒绝，因为前面已 `_reject`）。
- 验证与 `path.write_text` 之间存在 TOCTOU：DB/artifacts 可在 `verify_scan_evidence` 返回后被并发修改，manifest 不复核。本机单进程未复现。
- **路径穿越不成立**：`as_of` 来自 `MAX(date)` 且被 `pd.Timestamp(as_of)` 解析（CORE_SERIES 陈旧检查），`report_{as_of}.md` 的恶意路径会先解析失败；未构造出成功穿越。

---

## 4. Fresh clone / CI 残留

- `git clone` 到 `/tmp/qa_scan_a/clone` 并 checkout `94f632b`：树干净；`data/`、`reports/`、`exports/` 均不存在（被 ignore），所以 **manifest 的 artifact 哈希在 CI 不可复验**；只有 `audit/test_evidence/*` 和 `audit/releases/*.json` 被提交。
- 干净 clone + `.venv/bin/python`（3.12）：`verify_test_proof(proof, rerun=False)` → `PROOF ACCEPTED 215 offline`；证明 commit `1c57cba` 是 `94f632b` 祖先且 diff 仅 audit，符合 `_check_commit`。
- 同一命令在冻结 HEAD 工作树（有未跟踪 `audit/QA_SCAN_ROUND1.md`）→ `REJECTED: cannot verify a proof on a dirty worktree`；这是**本次复核环境的实际阻塞**，不是 proof 本身失效。
- manifest 的 `test_evidence.proof_path` 是绝对路径 `/Users/cast/Downloads/...`，不可移植；`verify-release` 以参数取 proof，故仍可在 clone 使用，但 manifest 自身不能直接指向可复验文件。
- CI 若要复验 scan evidence，需要额外提供 DB + reports + exports（或发布只读证据包），否则 manifest 中 `scan_evidence`/`artifacts` 只能做字段检查。

---

## 5. Phase1 状态

**Phase1：PASS WITH ISSUES（有条件通过）**。

- 真实冻结 release `1c57cba580` 的 scan 计数、config/data 哈希、三份 artifact 哈希、215 proof 均一致，且 manifest 生成严格晚于 scan 验证；可对外声明该 release 的证据字段真实。
- 但 `scan_evidence` 还不能宣称“拒绝 stale / 扫描后篡改”：
  - P1-1 使扫描输出与 OHLCV 可在 scan 后改写而 manifest 仍“verified”；
  - P1-2 使任意旧 as_of 的成功 scan 可被今天发布；
  - P1-3 使 live ingest 成功成为不可验证的自报字段。
- 建议 Phase1 以 **conditional pass** 关闭，P1-1/P1-2 必须修复后才可把该门禁作为 release 的强不变量；P1-3 与 P2 列入 Phase2 前修复清单。

## 6. 复核边界

- 合成攻击的 readiness 用 `SimpleNamespace(ok=True)` 隔离 scan_evidence 逻辑（与仓库既有单测同法）；真实 DB 篡改全部走真实 readiness，结论以真实 DB 结果为准。
- 未在 10 分钟内独立重跑 215 条测试；仅做 `rerun=False` 接受验证与 JUnit/哈希核对。
- 未做多进程并发/TOCTOU 实测；未在 CI 供应商环境执行；未攻击 OS 层（文件锁、权限）。
