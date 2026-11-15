# QA_SCAN_FINAL_D — 冻结 HEAD 独立复核（扫描证据 v3 / 不同角度）

- 复核对象：`9384b5b`（code `5bcaa5d`，branch `architecture/research-v2`），`goe/scan_evidence.py`、`goe/release.py`、`audit/releases/release_5bcaa5de06.json`
- 环境：macOS，`.venv` Python 3.12；只读仓库；合成/篡改实验全部在 `/tmp/qa_scan_d/`（`real.db` 为 `data/goe.db` 的 sqlite backup）
- 规则：未改任何代码；除本文件外无仓库写入；未触碰 `main` / V1 代码
- 时限：10 分钟，未独立重跑完整 217 条（证据内 rerun=217 已核对，见 §1）；公开 `verify-release` 因当前工作区有他人未提交的文档修改会先被 dirty 检查拒绝，故只在 harness 中绕过 `_dirty_code` 做结构校验

**结论：PASS WITH ISSUES（条件通过）。真实 release 未被伪造，扫描证据计数/哈希/来源/时序/提交祖先均可独立复算；但扫描证据不是“不可伪造”证据。若验收标准是“伪造 report/scan-json/pipeline 内容或移植到干净 clone 后仍可验证”，本次应判 FAIL（P1）。**

---

## 1. 真实 release 独立复算（ACCEPT）

真实 DB 副本 + 真实 artifacts 调 `verify_scan_evidence`：

```
1 real baseline: ACCEPTED scan=scan-20261115T041932Z-50a761
  prices=358310 anomalies=1506 opp=11 data=9350b109d05e
```

- 计数：prices 358,310 / indicators 159,508 / anomalies 1,506 / transmissions 5 / opportunities 11，与 manifest `scan_counts` 及 `opportunities_by_status`（4+2+3+2=11）一致。
- `config_hash=7d4d8ae1…`、`data_hash=9350b109…` 现场由 DB 重算，与 manifest 一致；report/scan-json/pipeline 三个 sha256 现场重算均等于 manifest `artifacts`。
- 真实 readiness：`ok=True`、`critical=[]`，但 `degraded=True`，警告 `EA_HICP` 过期 347 天、`US_CAPE` 过期 1,169 天；门禁只要求 `readiness.ok`，接受该降级扫描（P2，见 §4）。
- 提交链：manifest `git_commit=5bcaa5d`；proof commit 同为 `5bcaa5d`；`HEAD=9384b5b` 为其子提交；`git diff --name-only 5bcaa5d 9384b5b` 仅 4 个 `audit/` 文件（release + junit/log/proof），无 code/config/tests 变更，符合 `_check_commit`。
- 时序：scan `finished_at=04:20:02Z` < proof `ended_at=04:22:08Z` < manifest `created_at=04:23:42Z`。
- 测试证明：结构校验（monkeypatch 仅去掉他人文档修改造成的 dirty 干扰）→ `PROOF ACCEPTED`，`passed=217`、`required_sha256 == executed_sha256 = 9bdf33009238…`、JUnit 217/0 skipped、log/junit 哈希匹配；未发现证明伪造。
- 目标测试实跑：`tests/test_scan_evidence.py + tests/test_release_gate.py` 30 passed；V1 报告/pipeline 测试 8 passed。

## 2. 攻击/边界矩阵（本轮新增）

| # | 场景 | 结果 | 判定 |
|---|---|---|---|
| D1 | 完全自洽的合成 scan：真实数据快照上插入 `scan-FAKE-20261115`、1 条伪造 anomaly、伪造 report/scan-json/pipeline，重算所有哈希 | **ACCEPTED**（`ev.scan_id=scan-FAKE…`，1 anomaly，0 opp） | 信任边界（见 §3） |
| D2 | 只改 DB anomaly + 重算 `stats.output_fingerprint` | REJECTED（scan-json `meta.output_fingerprint` 不符） | 双向锚点有效 ✅ |
| D3 | 只改 DB close + 重算 `scan_runs.data_hash` | REJECTED（scan-json `meta.data_hash` 不符） | 双向锚点有效 ✅ |
| D4 | 保留真实 DB，伪造 report 正文、scan-json 中 anomaly 内容、pipeline 中 opportunity 内容（保留 token/计数/id/meta） | **ACCEPTED；三个 artifact sha256 全部不同于 manifest** | **P1** |
| D5 | 从 `stats_json` 删除 `opportunities` 键 | **ACCEPTED**（`created is not None` 才校验，缺失即跳过） | P2 |
| D6 | 追加一条旧 scan 的 opportunity（`run_id=scan-OLD-2020`） | 校验 ACCEPTED；manifest 风格全局 `by_status` 合计 12 ≠ `scan_counts=11` | P2（latent） |
| D7 | 7 天后重新验证 | 真实 scan 会因 `>7 days` 被判 stale；manifest 未记录 `reference_date`，无 `verify_manifest` 入口 | P2（可复验性） |
| D8 | 伪造 report/scan-json/pipeline 内容后随 release 落盘 | manifest 会冻结伪造件的 sha256（因为它在验证后对文件取哈希） | 与 D4 同一 P1 |

## 3. 信任边界（关键判断）

门禁是**内部一致性/新鲜度校验**，不是真实性证明：

- 它假设 `scan_runs` 行、DB、`reports/`、`exports/` 由可信扫描器在 scan 时刻产生；没有外部签名/时间戳/WORM 快照。
- 真实语义是“DB、scan-json、pipeline、report 之间的哈希/计数互相对得上”。D2/D3 证明只改一侧会被另一侧锚点抓住；但 D1/D4 证明**同时改写 DB + artifacts（或直接伪造自洽 scan）即可通过**。这属于已声明的信任边界内的 accepted limitation，不是空库/假哈希类的代码绕过。
- 但 D4 落在边界之内：artifact 内容从未与 DB 内容独立比对（report 只查 4 个 token，scan-json 只查 `len(anomalies)`，pipeline 只查 id 集合/计数/provenance），因此“report/scan-json/pipeline verified”应降级表述为“provenance/count verified”。若把 report 当研究结论载体，这是可注入伪造内容的口子（P1）。
- DB 侧输出篡改的锚点 `output_fingerprint` 存放在同一个可写 `scan_runs.stats_json`；只有 scan-json meta 与之交叉才使 D2 失败。也就是说必须至少信任 DB 或 artifacts 一侧不可写；两侧都可写时无检测能力。
- 结论：**合成 DB 被接受是 accepted limitation（信任边界），不是本次要判 FAIL 的代码绕过；但 artifact 内容伪造 + 扫描证据不可移植是 P1 真缺口。**

## 4. 其他发现

- **P1 可移植性/发布证据**：`git ls-files reports exports data` = **0**（全部被 `.gitignore`）。manifest 引用 `reports/report_2026-11-13.md`、`reports/scan_2026-11-13.json`、`exports/pipeline_2026-11-13.json`，但干净 clone 拿不到这些文件，也没有 `verify_manifest`/artifact bundle；`goe verify-release` 只校验测试证明，不校验扫描证据。CI 也只 replay proof。
- **P1 CI/跨 OS**：`.github/workflows/verify-release.yml` 仅 `ubuntu-latest`；只跑 `verify-release --proof`，不跑扫描证据/数据；无 macOS/Windows runner；PROJECT_STATE 记录的 Docker Keychain 阻塞未解除。
- **P1 数据源**：真实扫描是 `mode=offline`、`stats.ingest={}`，无 live ingest；live 路径只要求一条 `ingest_runs(kind=prices,status=success)` 行，不核对覆盖/行数/质量；无 licensed consensus/term-OIS 源。真实 readiness 接受 347/1,169 天的 stale 宏观序列（`degraded=True`），发布物未记录 degraded 警告。
- **P2**：`scan_runs.started_at/finished_at` 未来值未校验（只校验 as_of 未来/7 天）；artifact mtime 的 `-120s` 检查对“复制文件/后写伪造”无意义；`by_status` 未按 scan 限定；`opportunities` stats 键可缺失；7 天窗口使同一 manifest 在 2026-11-20 后不可再验证，且 `reference_date` 未入 manifest。
- **环境备注**：当前工作区有他人未提交的 `PROJECT_STATE.md` / `audit/RELEASE_GATE_ACCEPTANCE.md` / `audit/TEST_EVIDENCE.md` 修改；manifest 构建时 `git_dirty=false`。本次未修改、未 stash、未清理这些文件。
- **V1 / main**：V1 tag `v1-frozen-1f2b341`（annotated tag object `d626970` → commit `1f2b341`）保持；`main` 在 `e5da620`（仅 docs 提交），本轮未改动。V1 report/pipeline 回归 8 passed；V1 扫描/报告路径未见回归。
- **B**：无 B 相关写入；本轮只写 `audit/QA_SCAN_FINAL_D.md`。

## 5. 判定与状态

**Verdict: PASS WITH ISSUES（条件通过）。**

- P0：**无**。未构造出空库/假 proof/无扫描证据生成 manifest 的路径；真实 217-test release 可复算。
- P1（未闭环）：
  1. 真实 DB + 伪造 report/scan-json/pipeline 内容仍 ACCEPTED，manifest 会冻结伪造哈希；artifact 内容未与 DB 交叉校验。
  2. 扫描证据不可移植：reports/exports/data 均未入库，无 manifest/artifact 验证入口，CI 只验证 test proof。
  3. CI 仅 ubuntu + 仅 test proof；无跨 OS/独立 runner。
  4. 数据源/live ingest 证据不足：真实 release 为 offline、无 ingest 记录，degraded readiness 被接受；无 licensed consensus/OIS。
- P2：stats 可缺 `opportunities` 键；`by_status` 未按 scan 限定；7 天新鲜度使 manifest 事后不可复验；未来 `started_at/finished_at` 未拒绝；mtime 检查弱。

**Phase 1 工程状态：CONDITIONALLY ACCEPTED（未关闭）** — 扫描证据 v3 对真实 release 的计数/哈希/来源/时序/祖先链可独立复算，217 条离线证明通过；但 P1-1（artifact 内容）与 P1-2（可移植性）未闭环前，只能按“可信环境内的一致性门禁”验收，不能宣称不可伪造。若不接受该信任边界，则 Phase 1 = FAIL。

**DISCOVERY 状态：NOT VALIDATED（未验证）** — 沿用 `PROJECT_STATE.md`：20 candidates → 0 research / 20 intelligence（`evidence_gap`）；本轮未重开研究评估。Phase 2 不应以“扫描门禁通过”当作发现有效性证据。
