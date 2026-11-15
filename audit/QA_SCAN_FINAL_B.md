# QA_SCAN_FINAL_B — 独立 QA（B 角度：字段独立重算 / 证据自洽）

- 日期：2026-11-15
- 冻结对象：`94f632b`（`architecture/research-v2`），被审代码 `1c57cba`（goe 与 config 自 `1c57cba` 后未变）
- 方法：只读代码与仓库数据；所有注入在 `/tmp` 的 DB/报告副本中进行；除本文件外未修改仓库。
- 与 `QA_SCAN_ROUND1`（故障注入角度）的区别：本轮不重复逐项注入，而是核对"manifest 的每个声明字段是否独立重算"、合成自洽数据、证据可移植性与代码/产物同源。
- 基线与现有结论：`tests/test_scan_evidence.py` 在 HEAD 6 passed；真实 scan 经 `verify_scan_evidence` 复核 **ACCEPTED**（见下）。未发现 P0。

### 0. 并发变更声明（重要）

审计期间（12:09 开始）工作树被其他 agent **并发修改**：`goe/db.py`、`goe/pipeline.py`、`goe/scan_evidence.py` 出现未提交改动，`audit/` 下新增 `QA_SCAN_FINAL_A.md`、`QA_SCAN_ROUND1.md`。这些改动**不是本 agent 所做**。本报告全部结论针对冻结提交 `94f632b`（业务代码 `1c57cba`）的 blob；引用行号均为该提交内容。未提交改动中的 `output_fingerprint`、`ingest_runs` 对账、stale/未来 as_of 检查**不在本轮结论内**。

需要特别提示：未提交的 `scan_evidence.py` 把 `fetched_at` 检查**扩展到 indicators**，但并未修正 P1-B1 的根因（仍以 `as_of` 作为抓取时间基准），因此在本工作树中 P1-B1 反而扩大；同时新增以 `date.today()` 为默认的 7 天 stale 检查，可能误拒"为历史 as_of 补做的合法扫描"。冻结/复核前必须先提交或回滚这些改动，并在新 blob 上重新审计。

## 结论

| 维度 | 结论 |
|---|---|
| Phase 1 工程（证据门禁） | **CONDITIONAL — 不可冻结（NOT FREEZABLE）**：门禁主体逻辑成立、真实 scan 通过、无 P0 绕过；但本轮新增 **1 个 P1**（合法 scan 会被误拒），冻结前必须修复并重出 scan/proof/manifest |
| 研究价值 | **NOT VALIDATED**（0 research / 20 intelligence，`evidence_gap`；与 `RESEARCH_EVIDENCE_AUDIT.md` 一致） |
| 新增 P0 | 0 |
| 新增 P1 | 1（`fetched_at` 误拒，见 P1-B1） |
| 并行 QA A 的 P1 | stale scan 接受、live ingest 纯自报、扫描后输出篡改（`QA_SCAN_FINAL_A`，本轮未重复）；合并后 Phase 1 同样不可冻结 |
| 已知 P1 未修（本轮前） | 2（输出字段未 hash / OHLCV 不进 data_hash，见 `QA_SCAN_ROUND1`）；本轮未重复主张 |
| 新 P2/P3 | 5 项（见下），均不单独阻断冻结，但 P2-1 决定"verified"措辞需降级 |

## 1. 逐字段独立重算核查

真实基线（未修改的 `data/goe.db` + `reports/` + `exports/`）：

```
ACCEPTED scan-20261115T031540Z-4048c8 as_of=2026-11-13
prices=358310 indicators=159508 anomalies=1506 transmissions=5 opportunities=11
config_hash=7d4d8ae1a7ca… data_hash=9ddd93ef2a45… ingest_status=offline
```

`audit/releases/release_1c57cba580.json` 的三个 artifact sha256 与磁盘文件逐一相等（`shasum -a 256` 复核）；`git_commit=1c57cba…` 与 proof 的 `git_commit` 一致；HEAD `94f632b` 仅比它多 `audit/` 证据文件。

| manifest 声明 | 是否独立重算 | 事实与代码位置 |
|---|---|---|
| `config_hash` | **是** | `store.config_fingerprint()` 重算 `config/` 11 个文件（`goe/db.py:926-936`），再与 `scan_runs.config_hash` 比对（`scan_evidence.py:107-112`）。注意：`config/evidence_sources.yaml` 不在清单内，但 scan 主流程不读它（仅独立 `goe triage` 读），故对本 manifest 无影响；属 P3 语义瑕疵 |
| `data_hash` | **是** | 从 DB 重算 prices(5 列)/indicators(3) 的内容指纹（`db.py:938-961`）并与 scan 行比对。已知缺陷：OHLCV 4 列不在指纹内（P1，`QA_SCAN_ROUND1` P1-2），本轮未重复 |
| readiness | **是** | `check_data_readiness(store, as_of)` 重算并要求 `ok`（`scan_evidence.py:115-117`）；stats 只交叉核对 `ok/price_rows/indicator_rows`，不核对 coverage/degraded（P3） |
| 核心序列新鲜度 | **是** | `CORE_SERIES` 从 indicators 表重算最后日期与最大年龄（`:152-158`），不读 stats |
| 价格/指标/异常/传导/机会计数 | **是** | 全部从 DB `COUNT(*)` 重算；异常/传导/机会与 `stats_json`、scan json、pipeline 交叉核对（`:160-178, :199-202, :216-222`） |
| report 内容 | **否（仅 4 个令牌）** | `:203-207` 只要求 `scan_id/as_of/config_hash[:16]/data_hash[:16]` 出现在文本中；数字、结论、限制声明不校验 |
| scan json 内容 | **部分** | meta 四字段 + 异常/机会**数量**；异常 id/分数/证据不校验（P3） |
| pipeline 导出内容 | **部分** | provenance 两 hash、机会**数量与 id 集合**；`scan_id`、status、score、reasons 不校验（P2-2） |
| ingest 状态 | **否（信任 stats）** | `:129-131/149-150`：`stats.ingest.status` 直接采信；offline 扫描缺省为 `offline` 即通过，`ingest_runs` 不参与对账（已知 P2） |
| 来源 provenance | **否（登记即可）** | `:135-150`：`source_id ∈ config ∪ DB sources` 且 prices `fetched_at <= as_of`。DB `sources` 表可写即可"登记"任意来源；只证明登记身份，不证明数据真实（见 P2-1） |
| artifacts sha256 | **自洽哈希** | 对**冻结时磁盘上的文件**取 sha（`:231-233`），manifest 原样记录；与 scan 时内容无基线可比，报告/导出可被重写后"重新背书"（P2-2） |
| `opportunities_by_status` | **是（但全局）** | `release.py:693-696` 直接按全表 group by，不限定 `run_id`；当前 DB 只有最新 run 的 11 条机会，故本次一致；多 run 并存时会混入旧机会（P3） |

## 2. 新增 P1

### P1-B1（新）：`fetched_at > as_of` 会误拒正常增量抓取的合法 scan

`1c57cba` 新增的来源校验（`goe/scan_evidence.py:145-148`）：

```python
future_fetch = store.scalar(
    "SELECT COUNT(*) FROM prices WHERE date<=? AND fetched_at > ?", (as_of, as_of + "T23:59:59Z"))
if future_fetch:
    _reject("price rows have future fetched_at timestamps")
```

问题：`fetched_at` 是**抓取墙钟时间**，不是数据的可用时点。正常增量抓取会把最近 10 天（`goe/ingest.py:39,124-132`）重新 upsert，而 upsert 会把 `fetched_at` 改写成**本次抓取时间**（`goe/db.py:440-447`）。于是只要抓取发生在 `as_of` 所在 UTC 日之后（周末补抓、亚洲时区次日早上抓美股、节假日），这些行的 `fetched_at` 必然大于 `as_of` 当天 23:59:59Z，`goe scan` 生成的真实 scan 会被门禁判为"未来抓取"。

实测（真实 DB 副本，模拟"次日早上抓取 11-13 收盘"这一正常场景）：

```
cp data/goe.db /tmp/qaB/goe.db
UPDATE prices SET fetched_at='2026-11-14T01:00:00Z' WHERE date='2026-11-13';
-- 影响 124 行（当日全部标的），不是伪造的极端值
verify_scan_evidence(Store('/tmp/qaB/goe.db'))
→ ScanEvidenceError: price rows have future fetched_at timestamps
```

真实基线之所以通过：`prices.fetched_at` 最大值 `2026-11-13T15:08:41Z`，恰好与 `as_of=2026-11-13` 同一 UTC 日——是时间巧合，不是设计保证。影响：Phase 1 冻结后的下一次默认 `goe scan`（带 ingest）大概率无法通过 release gate；这是**发布可用性 P1**，不是数据被污染。

附带的次要不对称：冻结 blob 只检查 prices，不检查 indicators 的 `fetched_at`（P3）；未提交改动把它扩展到 indicators 但保留了错误基准，见第 0 节。

与并行 `QA_SCAN_FINAL_A` 的关系：A 的 P1-2 是"过旧 scan 被接受"（stale），本项是"合法新 scan 被误拒"（over-reject），方向相反、可同时成立；修复 stale 时不能靠收紧 `fetched_at vs as_of` 来解决，否则会把正常的次日/补抓数据一起拒掉。

建议修复：把判据改为 `fetched_at <= scan.finished_at`（或 manifest 冻结时间），保留"未来抓取"语义但不再把 as_of 当抓取时点；或用单独的 `available_at/first_seen_at` 做 PIT 判断；并把 indicators 纳入对称检查。修复后需要新 scan + 新 proof + 新 manifest。

## 3. P2 / 接受的限制

### P2-1（接受限制，非本轮新 P1）：完全自洽的合成 DB 会通过

在 `/tmp` 构造最小合成 DB：仅 1 条价格（`FAKE_IDX`）、4 条核心指标，来源为**临时插入 `sources` 表的 `minted_source`**，1 条异常，0 传导/机会，stats 与 hash 全部按当前算法生成，report/scan json/pipeline 均写齐 provenance；gate 层（readiness 被替换为 ok，见下）验证结果：

```
SYNTHETIC ACCEPTED: scan-1 1 4 offline source=minted_source
```

结论：门禁只能证明"DB/报告/hash 彼此自洽"，**不能证明**这些行情是真实抓取、扫描真的执行过。`known_sources` 并集包含 DB `sources` 表，因此"来源登记"本身也可伪造。这是**数据真实性不在威胁模型内**的接受限制，不是 P0/P1；但 `release` 文档若把它表述为"verified real data"就属过度声明，应明确写成"internally consistent scan evidence, provenance identity only"。

补充：本次为把范围控制在 gate 层，替换了 `check_data_readiness`（其自身也从同一 DB 重算，伪造数据覆盖 universe 即可通过；`QA_SCAN_ROUND1` 用例 33 用真实 DB 注入 5000 行垃圾价格并重写全部证据也得到 PASS，可交叉印证）。

### P2-2（新细节，已知问题延伸）：report 与 pipeline 的**内容**不被重算

真实 DB 不变，仅篡改产物后 gate 仍 **ACCEPTED**：

- report：把 `1506` 改成 `999999`，保留 4 个 provenance token；
- pipeline：顶层/ provenance `scan_id` 改为 `scan-OLD-forged`，并把 11 条机会的 `status` 全部改成 `excluded`、score 置 0（id 集合与数量不变）。

manifest 会如实记录篡改后文件的 sha256（`build_manifest` 对冻结时磁盘文件取哈希，`release.py:703-707`），但没有任何 DB/scan 基线与之对账。report 的令牌问题 `QA_SCAN_ROUND1` 已列为 P2；本轮新增的是 **pipeline 的 status/score/scan_id 同样不被校验**，与已知 P1-1（DB 输出字段未 hash）同源。建议：pipeline 至少校验 `scan_id`，并对机会的 status/score（或整个稳定序列化）与 DB 对账；report 的关键数字从 DB 渲染后比对。

### P2-3（新）：manifest 未绑定"扫描时的代码提交"

`scan_runs` 无 code commit/hash 字段（schema：`scan_id, as_of, mode, started_at, finished_at, status, config_hash, data_hash, stats_json`），manifest 的 `git_commit` 只是**冻结时**的 HEAD。时间线证据：

- 扫描：`2026-11-15T03:15:40Z` 开始，`03:16:05Z` 结束；产物 mtime `11:16`（本地）；
- 被声称的代码：`1c57cba` 提交于 `11:42:23 +0800`（`03:42:23Z`）；扫描早于该提交约 26 分钟；
- 缓解事实：`git diff b09f7b8 1c57cba -- goe tests config` 只有 `goe/scan_evidence.py` 与 `tests/test_scan_evidence.py`（验证器本身），**扫描管线代码未变**；`201c3fa`/`9842f21` 亦仅 audit/docs/test 变化。

因此本次 release 的产物**恰好**不受代码差异影响，但门禁无法自动证明这一点：若两次冻结之间改的是管线代码，旧 scan 仍会被新 HEAD 的 manifest 背书。定级 P2（当前无输出影响），修复建议：scan 启动时把 `git rev-parse HEAD`（或 tree hash）写入 `scan_runs`，manifest 校验它等于/祖先于冻结 HEAD，否则要求重扫。

### P2-4（已知未修）：manifest 仍有绝对路径

`release_1c57cba580.json` 的 `test_evidence.proof_path` 为
`/Users/cast/Downloads/金融系统/global-opportunity-engine/audit/test_evidence/20261115T040451Z_1c57cba580.proof.json`。
proof 自身的 `junit_path/log_path` 已相对化，`artifacts`、`scan_evidence` 路径也已相对化，但 manifest 仍不可整体搬移（`QA_EVIDENCE_ENGINEERING` 已记为 P2，94f632b 尚未修）。不影响本机验证。

### P3（工作流/语义）

- `_EVIDENCE_ALLOWED` 只豁免 `audit/test_evidence/`、`audit/releases/`；QA 报告（如 `audit/QA_SCAN_ROUND1.md`，以及本文件）是 untracked，`_dirty_code` 立即返回 True，`build_manifest` 会拒绝冻结。实测：`git status` 仅 `?? audit/QA_SCAN_ROUND1.md` 时 `_dirty_code(cwd='.') == True`。需要在冻结前提交这些报告，或把 `audit/*.md` 纳入豁免。
- `scan_evidence.py:93-94` 的"扫描顺序不一致"检查在 `ORDER BY started_at DESC LIMIT 2` 之后恒为假（已知 P3）。
- `as_of` 直接拼进产物文件名（`report_{as_of}.md`），DB 被篡改时可 `../` 逃逸（已知 P3）。
- `finished_at` 未校验 ≥ `started_at`；`mode` 未限制；scan json 未校验异常 id；`indicators.fetched_at` 未做未来检查；stats readiness 的 coverage/degraded 未对账。

## 4. 用例结果（B 角度）

| 用例 | 结果 |
|---|---|
| 真实 scan + report + pipeline | **ACCEPTED**（数字/hash 与 manifest 一致） |
| 空 DB / 无 scan_runs | REJECTED（`tests/test_scan_evidence.py`，6 passed；代码 `:86-87`） |
| 假 config_hash / 假 data_hash / 改 close | REJECTED（同上测试覆盖） |
| latest 不是 success / partial ingest | REJECTED（测试覆盖） |
| 缺 report / scan json / pipeline | REJECTED（测试覆盖） |
| 合成自洽 DB（含自造 source） | **ACCEPTED**（P2-1 接受限制） |
| 真实 DB + 篡改 report 数字 + pipeline scan_id/status | **ACCEPTED**（P2-2） |
| 正常次日抓取后的真实 scan（fetched_at=as_of+1 日） | **REJECTED（误拒）**（P1-B1） |

## 5. 可移植性与同源核验

- artifacts 路径：manifest 中为 repo 相对路径；sha256 与磁盘一致。
- proof/HEAD：proof `git_commit=1c57cba` == manifest `git_commit`；HEAD `94f632b` 是其子提交且差异仅 `audit/` 证据，`_check_commit` 的 ancestor + audit/docs-only 规则允许该 replay（`release.py:508-538`），此链**成立**。
- 但 DB 与 `reports/`、`exports/` 均被 `.gitignore` 排除，fresh clone 只能 replay proof，**无法重放/复核 manifest 的 scan evidence**；这是数据不入库的接受限制，manifest 应显式注明"scan evidence 只在原始数据快照上可复核"。

## 6. Phase-1 工程结论与阻塞项

**Phase 1 ENGINEERING：CONDITIONAL PASS（逻辑）/ HOLD（冻结）。**
门禁的独立重算总体成立：config/data hash、readiness、核心序列、DB 计数、scan json 计数、pipeline id 集合都真正重算；空/伪造/旧/部分/缺件/哈希不符均拒绝；真实 scan 通过；未发现 P0。但 P1-B1 会误拒合法的下一次真实 scan，且 P2-3 暴露"扫描代码同源"无自动证据，故 **94f632b 不可标记 Phase 1 冻结**。

冻结前最小动作：
1. 修 P1-B1（`fetched_at` 判据改为相对 scan 完成/冻结时间，并覆盖 indicators）；
2. 在 `scan_runs` 记录扫描时 code commit，manifest 校验同源（P2-3）；
3. 重跑真实 scan（ingest 后）→ 新 proof → 新 manifest，再独立复核；
4. 修/接受 P2-2：pipeline 至少绑定 scan_id，report 关键数字对账；
5. 提交 `audit/` 下的 QA 报告，避免 untracked 报告直接弄脏冻结树（P3）。

**剩余阻塞项（非本轮代码可解）：**

| 阻塞 | 状态 | 影响 |
|---|---|---|
| CI 跨 OS 复验 | **BLOCKED/UNVERIFIED**：`.github/workflows/verify-release.yml` 存在，但 GitHub Actions 从未实际运行；Docker Linux replay 因 Keychain 凭据失败未启动（`audit/CI_REPLAY.md`） | 只能声明 macOS 本地 replay 通过，不能声明跨平台可复现 |
| 数据源（Phase 2） | **BLOCKED**：consensus 无授权公开历史；term OIS 无授权源，仅 policy-path proxy 且默认关闭（`docs/EVIDENCE_SOURCES.md`、`PROJECT_STATE.md` P2-DATA-1） | 研究候选 0 research / 20 intelligence；Phase 1 工程冻结不依赖它，但"发现价值"不可验证 |
| 行情真实性 | 接受限制：门禁只证明 DB/证据自洽，不认证数据来源真实性（P2-1） | release 文档不得写成"verified real market data" |

## 7. 复现命令

```bash
# 真实基线
.venv/bin/python -c "from goe.db import Store; from goe.scan_evidence import verify_scan_evidence; \
print(verify_scan_evidence(Store('data/goe.db')).scan_id)"
.venv/bin/python -m pytest tests/test_scan_evidence.py -q -o addopts=

# P1-B1：模拟次日早上抓取
cp data/goe.db /tmp/qaB/goe.db
sqlite3 /tmp/qaB/goe.db "UPDATE prices SET fetched_at='2026-11-14T01:00:00Z' WHERE date='2026-11-13';"
.venv/bin/python -c "from goe.db import Store; from goe.scan_evidence import verify_scan_evidence; \
verify_scan_evidence(Store('/tmp/qaB/goe.db'))"   # → future fetched_at

# P2-2：篡改 report/pipeline 后仍 ACCEPTED 的副本
# 见 /tmp/qaB2（复制真实 DB/reports/exports 后改 report 数字、pipeline scan_id/status）
```

## 8. 本轮未做

- 未重跑完整离线套件（只跑 `tests/test_scan_evidence.py`，6 passed）；未重新生成 proof/manifest（只读约束）。
- 未验证 GitHub Actions、未做 Linux replay（环境限制）。
- 未对研究候选的 hypothesis 证据质量做新审（已在 `RESEARCH_EVIDENCE_AUDIT.md` 记录为 NOT VALIDATED）。
