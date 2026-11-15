# QA_SCAN_ROUND1 — Verified Scan Evidence 独立红队复核

- 日期：2026-11-15
- 审计对象：冻结目标 `9842f21`（`architecture/research-v2`），实际被审代码 `201c3fa` / `9842f21` 两提交的 `goe/scan_evidence.py`（blob sha256 `e7cebcea…`）与 `goe/release.py:build_manifest`
- 方法：`git show <commit>:goe/scan_evidence.py` 只读快照 + `/tmp` 下独立 DB/报告副本；未修改仓库代码、数据、报告。每条用例都复制 `data/goe.db` 后单独注入故障再调用 `verify_scan_evidence`。
- 审计期间分支前进：`9842f21` → `1c57cba`（11:42 提交，新增来源/实时 ingest 校验，215 测试 proof，生成但未提交 `release_1c57cba580.json`）。本报告结论以 `9842f21` 为准；`1c57cba` 仅做 6 个定点复测，不构成对它的完整复核。

## 结论

**PASS WITH ISSUES**（对 `9842f21`）。核心 gate 在真实数据上通过，manifest 的 hash/count/proof 全部可复核；但存在 **2 个新 P1**，因此 **Phase 1 暂不可冻结**。

| 维度 | 结果 |
|---|---|
| 真实有效 scan/report | **PASS**（与 manifest 逐字段一致） |
| manifest `release_201c3fa831.json` | **PASS**（scan_evidence 齐全，hash/count 正确，proof 215/215） |
| 必须拒绝的伪造场景（10 类） | 9 类确实拒绝；"同 row count 改价格"仅覆盖 `close`，`open/high/low/volume` 可绕过 |
| 额外绕过 | 2 个 P1（扫描输出篡改、OHLCV 不进 hash）、3 个 P2、若干 P3 |
| Phase-1 状态 | **CONDITIONAL / 不可冻结**：先修 P1，并在新 HEAD 重新出 proof + manifest |

## 真实数据与 manifest 核验

基线（真实 DB + 真实 `reports/`、`exports/`）：

```
PASS scan-20261115T031540Z-4048c8
prices=358310 indicators=159508 anomalies=1506 transmissions=5 opportunities=11
config_hash=7d4d8ae1a7ca110204f522359f57e8c627c89cdec753eea29b51af4a486fc187
data_hash  =9ddd93ef2a456ee16e94985b1918a820e8415c72596dba8117662287207b39ef
report_sha256   24a50fdde52548a128ceab9f011efbd46d4344cf8b03423eb43bb76059229ed9
scan_json_sha256 391b6b0696e92107ec66846052aa032d4e0880beda06e737dd0c66a438a00f37
pipeline_sha256  8bb95e9175b6e09071e4c2aac286eb59f305d31b58c5a7037a4e77d9c0514047
```

`audit/releases/release_201c3fa831.json`：

- `git_commit=201c3fa831…`，`git_dirty=false`，`scan_evidence.scan_id/as_of/config_hash/data_hash` 与 DB 重算值一致；
- `scan_evidence` 计数 `prices=358310, indicators=159508, anomalies=1506, transmissions=5, opportunities=11`，与 DB `COUNT(*)` 全部一致；
- `artifacts` 三个 sha256 与真实文件逐一相等；`report_path/scan_json_path/pipeline_path` 指向存在文件；
- `test_evidence.passed=215`，proof 的 `required==executed==215`、`skipped=0`，JUnit/log 文件 sha256 与 proof 记录一致，`git_commit=201c3fa…`。
- 注：`9842f21` 本身没有 `release_9842f21d3.json`；manifest 属于其父提交 `201c3fa`，两提交差异仅 `audit/` 证据文件，代码相同。属可解释的 P3 溯源性说明，不是失败。

## 复现总表

所有用例：`cp data/goe.db /tmp/<case>/goe.db` → SQL/文件注入 → `verify_scan_evidence(Store(...), reports_dir=..., exports_dir=...)`。期望栏为任务书要求。

| # | 场景 | 注入 | 期望 | 实测（9842f21） |
|---|---|---|---|---|
| 1 | 空 DB | 新建空 Store | 拒绝 | **拒绝** `no scan_runs evidence` |
| 2 | 假 `scan_runs` success | 清空 scan_runs 后插 success 行 | 拒绝 | **拒绝** `scan stats price_rows disagrees with DB` |
| 3 | 假 config_hash | `UPDATE scan_runs SET config_hash='deadbeef…'` | 拒绝 | **拒绝** `scan config_hash does not match current config` |
| 4 | 假 data_hash | `UPDATE … data_hash='deadbeef…'` | 拒绝 | **拒绝** `scan data_hash does not match recomputed DB content` |
| 5 | 同 row count 改 `close` | `UPDATE prices SET close=123.456789` | 拒绝 | **拒绝** data_hash mismatch |
| 6 | 同 row count 改 `open` | `UPDATE prices SET open=123.456789` | 拒绝 | **PASS（绕过）** |
| 7 | 同 row count 改 `high` | 同上 | 拒绝 | **PASS（绕过）** |
| 8 | 同 row count 改 `low` | 同上 | 拒绝 | **PASS（绕过）** |
| 9 | 同 row count 改 `volume` | 同上 | 拒绝 | **PASS（绕过）** |
| 10 | 错 `as_of`（周日 11-15） | `UPDATE scan_runs SET as_of='2026-11-15'` | 拒绝 | **拒绝** `scan as_of 2026-11-15 != last price date 2026-11-13` |
| 11 | 错 `as_of`（前一交易日 11-12） | 同上 | 拒绝 | **拒绝** data_hash mismatch |
| 12 | 旧 success 成为 latest | 删除最新 scan 行 | 拒绝 | **拒绝** `scan has no anomalies`（非 staleness 检查命中，见 P3） |
| 13 | partial ingest | `stats.ingest.status='partial'` | 拒绝 | **拒绝** `scan ingest status is partial; release requires complete ingest` |
| 14 | failed ingest | `stats.ingest.status='failed'` | 拒绝 | **拒绝** 同上（failed） |
| 15 | live scan 无 ingest 段 | `mode='live'` + 删除 `stats.ingest` | 拒绝 | **PASS（绕过）**；`1c57cba` 已拒绝 |
| 16 | 缺 report | 删 `reports/report_2026-11-13.md` | 拒绝 | **拒绝** `required artifact missing: …report…` |
| 17 | 缺 scan json | 删 `reports/scan_2026-11-13.json` | 拒绝 | **拒绝** `required artifact missing: …scan_…json` |
| 18 | 缺 pipeline | 删 `exports/pipeline_2026-11-13.json` | 拒绝 | **拒绝** `required artifact missing: …pipeline…` |
| 19 | report 早于 scan | `os.utime(report, 2020)` | 拒绝 | **拒绝** `artifact predates scan: …report…` |
| 20 | 伪造 report 内容 | 只写 4 个 provenance token | 拒绝 | **PASS（绕过）**（P2） |
| 21 | scan json 数量不符 | `anomalies` 追加一项 | 拒绝 | **拒绝** `scan json anomaly count disagrees with DB` |
| 22 | scan json meta 不符 | 改 `meta.config_hash` | 拒绝 | **拒绝** `scan json meta.config_hash disagrees with DB` |
| 23 | pipeline provenance 不符 | 改 `provenance.data_hash` | 拒绝 | **拒绝** `pipeline export provenance hashes disagree with DB` |
| 24 | pipeline summary 数量不符 | `n_opportunities=999` | 拒绝 | **拒绝** `pipeline export opportunity count disagrees with DB` |
| 25 | pipeline opportunity ids 不符 | 换一个 `opportunity_id` | 拒绝 | **拒绝** `pipeline export opportunity ids disagree with DB` |
| 26 | stats price_rows 不符 | +1 | 拒绝 | **拒绝** `scan stats price_rows disagrees with DB` |
| 27 | stats indicator_rows 不符 | 置 1 | 拒绝 | **拒绝** `scan stats indicator_rows disagrees with DB` |
| 28 | stats readiness ok=false | 注入 | 拒绝 | **拒绝** `scan stats do not record readiness ok=true` |
| 29 | stats 机会数不符 | `created=5` | 拒绝 | **拒绝** `scan stats opportunity count disagrees with DB` |
| 30 | stats 声称 ingest success | 改成 success | 拒绝 | **PASS（绕过）**（P2，值被信任） |
| 31 | 扫描后删价格行 | 删 1 行 | 拒绝 | **拒绝** data_hash mismatch |
| 32 | 注入 5000 条未来指标（>as_of） | 2026-12-31 | 拒绝 | **PASS（绕过）**（P3，PIT 设计使然） |
| 33 | 5000 条无意义价格行 + 重写全部证据 | 注册来源 + 重写 hash/stats/artifacts | 拒绝 | **PASS（绕过）**（P2，见下） |
| 34 | 篡改扫描输出：改 opportunity status | `watch→excluded` | 拒绝 | **PASS（绕过，P1）** |
| 35 | 篡改扫描输出：改 anomaly score | `score=0.999999` | 拒绝 | **PASS（绕过，P1）** |

`1c57cba` 定点复测（仅 6 项）：`open` 篡改仍 PASS；伪造 report token 仍 PASS；offline 下 stats `ingest=success` 仍 PASS；opportunity status 篡改仍 PASS；live 无 ingest 已 REJECT；未注册来源在改 hash 前被 data_hash 挡住（新来源检查已存在但未做重算 hash 的完整正向验证）。

## 新 P0/P1

### P1-1（新）：扫描输出可被篡改且不被发现

`verify_scan_evidence` 只对**输入** price/indicator 做 hash；`anomalies`、`transmissions`、`opportunities` 只比对 `COUNT(*)`、pipeline 的 id 集合与 summary 数量，不比对分数、状态、证据、优先级等内容。扫描后仅改 DB 输出字段，gate 依然 PASS：

```sql
UPDATE opportunities SET status='excluded'
 WHERE opportunity_id=(SELECT opportunity_id FROM opportunities WHERE status='watch' LIMIT 1);
-- 或 UPDATE anomalies SET score=0.999999 WHERE rowid=(SELECT rowid FROM anomalies LIMIT 1);
```

实测：两者均 **PASS**，而 `reports/`、`exports/` 仍是旧内容；`manifest.opportunities_by_status` 会记录被篡改后的分布，却无任何基线可比。后果：release manifest 可能给一份与报告/导出不一致的研究输出背书。

修复方向：在扫描时落一个覆盖 anomalies/transmissions/opportunities 全字段（或稳定序列化）的 `output_hash`，校验时从 DB 重算；同时把 report/pipeline 的关键内容与 DB 对账，而不只比 token/数量。

### P1-2（新）：`data_fingerprint` 未覆盖 4 个价格列

`goe/db.py:data_fingerprint()` 只 hash `instrument_id,date,close,adj_close,source_id`；`open/high/low/volume`、`fetched_at`、`run_id` 不参与。任务书要求"同 row count 修改价格必须拒绝"，实际 `close` 会拒绝，而 `open/high/low/volume` 全部 **PASS**。`data_fingerprint` 的 docstring 明确声称 "content hash of the point-in-time data … a vendor revision that changes a price … must change the hash"，与实现不符。

影响限定：当前扫描特征只读 `close/adj_close`（已 grep `goe/features.py`、`goe/anomalies.py`，未读 OHLCV 列），因此对本次扫描输出无直接影响；但 manifest 会对一个未被 hash 的数据版本作"已验证"背书，属于证据完整性缺陷。修复：把全部价格列与必要 provenance 纳入 hash（升级 hash 版本并重跑扫描/重签 manifest）。

## 其余问题

| 级别 | 问题 | 证据 |
|---|---|---|
| P2 | **report token 可伪造**：只写 `scan_id/as_of/config_hash[:16]/data_hash[:16]` 四个字符串即通过；report 内容与 DB 不存在绑定 | 用例 20 PASS |
| P2 | **`stats_json.ingest` 被信任**：值写 `success` 即通过，未与 `ingest_runs` 对账；真实 scan 的 `ingest={}`，manifest 的 `ingest_status="offline"` 是默认值而非证据（offline 扫描可接受，但字段语义被夸大）。`partial/failed` 能拒绝 | 用例 30 PASS；真实数据 `ingest={}` |
| P2 | **自洽伪造 DB 可通过**：注入 5000 条注册来源的无意义价格行，同时重写 `scan_runs` hash/stats、report token、scan_json meta、pipeline provenance 后 **PASS**（prices=363310）。说明 gate 只能证明"当前 DB 与证据自洽"，不能证明扫描真的执行过或数据真实 | 用例 33 PASS |
| P2 | `live` + 无 `ingest` 段在 `9842f21` 被当成 offline 通过；`1c57cba` 已修 | 用例 15 |
| P3 | 未来日期（>as_of）注入不检测（PIT 设计使然，但"DB 在扫描后被修改"并非全部可见） | 用例 32 PASS |
| P3 | stale 检查是死代码：`ORDER BY started_at DESC LIMIT 2` 后 `scans[1].started_at > scan.started_at` 恒假；用例 12 的拒绝实际来自旧 run 的输出已不存在（`scan has no anomalies`），不是 staleness 逻辑 | 代码 + 用例 12 |
| P3 | `as_of` 直接插入路径 `f"report_{as_of}.md"`：DB 被篡改时可用 `../` 逃逸读任意文件（本次路径解析验证可逃逸到 `/tmp`）。无可信外部输入时不可达 | 代码审查 |
| P3 | `finished_at` 未校验 ≥ `started_at`；`mode` 未限 offline（但 live 有 ingest 校验） | 代码审查 |
| P3 | 空 `data_readiness`/`ingest` 结构默认值偏宽松；`created` 缺失时机会数检查被跳过（DB count 仍独立计算） | 代码审查 |

**无 P0。**

## 逐项 bypass 审查（对应任务第 3 点）

- **从 `scan_runs` 取值而不重算**：`config_hash/data_hash` 由 `Store` 重算后比较；`as_of` 取自 scan 行但被 `last_price == as_of` 约束；counts 由 DB 重算；readiness 由 `check_data_readiness` 重算。`ingest`/`stats readiness` 值仍被信任（P2）。**部分成立，无 P0/P1 级直接伪造**。
- **report token 伪造**：成立（P2），见上。
- **`stats_json` 信任**：`price_rows/indicator_rows/anomaly/transmission` 会与 DB 对账；`ingest.status` 与 `opportunities.created` 例外（P2）。
- **old scan latest**：要求最新行为 success，理论上旧行当最新会被同一逻辑接受；实际因旧 run 输出被清理而拒绝。stale 专用检查是死代码（P3）。
- **partial source 未反映**：`9842f21` 完全不校验 `sources`；`1c57cba` 新增了 `source_id` 注册校验与 `fetched_at` 未来时间校验（代码审查；未完成"重算 hash 后"的正向绕过测试）。
- **DB modified after scan**：`close`/行删除可发现；OHLCV（P1-2）、输出字段（P1-1）、未来日期（P3）不可发现。
- **高但无意义 DB**：单独注入会被 data_hash/stats 拒绝；与证据一起重写则通过（P2）。
- **path traversal**：需要 DB 写权限改 `as_of`，属已失守场景（P3）。
- **manifest 先写后验**：代码顺序为 `verify_test_proof(rerun)` → `verify_scan_evidence` → artifact 存在性检查 → 写 manifest；未发现先写问题。

## Fresh-clone / CI 残留（只记录，不判定为通过）

- 测试 proof 本身可复现：215 passed = required = executed，0 skipped；`1c57cba` 也已有 215/215 的新 proof。
- **scan manifest 无法从 fresh clone 复现**：`build_manifest`/`verify_scan_evidence` 依赖未入库的 `data/goe.db`（101 MB）、`reports/`、`exports/`；git 树中只有代码/配置/证据。CI 的 `verify-release.yml` 只回放测试 proof，不校验 scan evidence。故"新克隆 + CI 可完整复现 release manifest"尚未成立。
- 仓库没有 CI 实际运行记录（只有 workflow 文件），不得据此声称 CI 通过。
- 审计结束时新 HEAD `1c57cba` 的 manifest `release_1c57cba580.json` 尚未提交（untracked）；`9842f21` 冻结目标对应的是 `release_201c3fa831.json`。

## Phase-1 状态

**CONDITIONAL / 不可冻结。** 证据门在真实数据上可用，manifest 与 215 测试 proof 可核验；但：

1. P1-1（输出可篡改）和 P1-2（OHLCV 未 hash）必须先修；
2. 修复后需用新扫描（或明确声明数据未变）重算 config/data hash，重新生成 proof + manifest；
3. 新增回归测试覆盖：OHLCV 四列、opportunity status/priority、anomaly score/evidence、offline 下 ingest success 伪造；
4. HEAD 已从 `9842f21` 前进到 `1c57cba`，需在新 HEAD 上做一次独立复核后再冻结，并明确 manifest 对应的 commit。

建议最终判定：修完 P1-1/P1-2 后 **PASS**；当前为 **PASS WITH ISSUES**。
