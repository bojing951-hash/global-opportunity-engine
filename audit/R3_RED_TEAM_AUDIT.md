# R3 — 独立红队 / QA 审计报告

- 审计者：r3-red-team（独立子代理）
- 审计对象：`global-opportunity-engine`，HEAD `6755d34` + 审计时段工作树中的 uncommitted 修复
- 审计时间：2026-11-14 15:55–16:17 HKT（UTC 07:55–08:17）
- 权限边界：只读仓库；唯一写入本文件。所有破坏性注入均在 `/tmp/r3/` 的 SQLite 副本或合成库上完成，未改源码/配置/测试/`data/goe.db`/git。
- 基准快照：`/tmp/r3/base.db`（15:55 HKT 用 SQLite backup API 从 `data/goe.db` 复制）。快照含 prices 358,310 / indicators 159,508 / anomalies 1,511 / opportunities 11 / 1 条 success scan。
- 代码快照哈希（16:16 HKT，见 `/tmp/r3/final_hashes.txt`）：
  - `pipeline.py` `28928608…`，`readiness.py` `76eac9a7…`，`features.py` `28526395…`
  - `ia_adapter.py` `7f78d2ff…`，`cli.py` `1eb0a955…`，`reports.py` `f47e0c57…`，`db.py` `3fd357cc…`

> **并发修改声明（影响结论口径，必须阅读）**：审计期间工作树被其他进程持续修改——15:52–16:03 `features.py` / `readiness.py` / 测试变更，16:12 `opportunities.py` / `validation.py` / `test_scoring.py` / `test_status_lifecycle.py` 再次变更；16:14 时离线收集数由 143 增至 147。更严重的是，**生产库 `data/goe.db` 在 16:11 被其他进程改写**：prices/indicators 仍为 358,310/159,508，但 `scan_runs` / `anomalies` / `opportunities` 变为 0（15:55 快照为 1 条 success scan / 1,511 / 11）。该写入不是本审计所为（本审计只打开 `/tmp` 副本；对生产库仅用 `mode=ro` 查询）。因此本报告所有数据库证据以 15:55 快照为准；无法对 16:11 之后的生产库状态背书。

---

## 0. 结论（Verdict）

**不签收（NO-GO for acceptance）——未发现 P0，但发现 3 个可复现的新 P1、5 个 P2。**

工程主干比上一轮更稳：扫描事务/回滚、detector 异常中止、readiness 的核心宏观/UST 契约、重复扫描幂等、嵌套事务、读写锁错误路径均通过对抗测试。尤其 DB 事务边界在 7 类注入下没有出现“DB 半写”。

但存在三条会直接造成“**看起来成功、实际不可用/不完整**”的发布路径：

1. **A→B（下游研究）把失败进程或陈旧产物记成 `completed`，CLI 以 0 退出**（P1-1；本报告认定的最危险残留缺陷）。
2. **价格 provider 大面积失败（1/125 更新）时 scan 仍 `success`，报告写“覆盖率 100%”，且从不展示采集失败**（P1-2）。
3. **readiness 用原始价格行判断新鲜度，不套用盘中未完成 bar 过滤器；单根盘中 bar 可以把已断更 10 天的市场“刷新”为 age=0**（P1-3）。

排序/研究层的核心 gate 基本成立：缺预期差的强价格候选在分数 0.7475 时被降为 watch 而非 deep；高异常但无机制/无预期差的候选不会到 deep；11 个真实候选无重复 primary/theme。但 watch 仍可被 handoff 自动执行，因此“不能进 deep”不等于“不会消耗研究预算”。

---

## 1. 方法与边界

- **新输入**：没有重跑仓库里的既有断言作为主要证据；所有用例使用新构造的行情/指标/provider/下游 artifact，或对真实库副本做新注入。
- **真实历史 PIT**：在 `/tmp/r3/base.db` 上分别 `as_of=2025-06-30` 与 `2026-11-13` 构建 8.8M 行特征，再 `slice_as_of(2025-06-30)`，逐行比对 index 与数值。
- **重量扫描纪律**：一次只跑一个生产规模 build；合成库扫描单独执行，未与 PIT build 并发（PIT 15:55–16:02；部分采集扫描 16:07）。
- **未做**：联网 provider 的实时可用性（除一次临时库意外触网外）、真实 investment-agent 运行、UI/浏览器、`goe replay --cases` 全量重放。
- **证据文件**：`/tmp/r3/t1_out.json`、`t3_ab.py` 输出、`t4_out.json`、`t5_ingest.py` 输出、`t7_out.txt`、`t8` 输出、`/tmp/r3/cli_matrix/*`。报告中的数字均由这些输出直接摘录。

### 基线测试

| 时点 | 命令 | 结果 |
|---|---|---|
| 15:53 | `pytest tests -m "not network" -q` | 143 collected，143 passed，0 failed，73.9s，exit 0（当时工作树 4 个修改文件） |
| 16:14 | 定向 6 文件（scoring/data_integrity/readiness_handoff/pipeline_e2e/exporter/opportunities） | exit 0 |
| 16:14 | 收集数 | 147（`opportunities`/`validation`/测试仍在并发编辑，计数已非文档值） |

---

## 2. 故障注入矩阵

### 2.1 数据源故障

| 输入 | 预期 | 实际 | 判定 |
|---|---|---|---|
| `prices` 全删 | critical + 阻断 | `ok=False`，`价格表为空`，无 scan 行 | ✅ |
| `indicators` 全删 | critical + 阻断 | 4 条 critical（指标空/核心宏观缺失/UST 缺失），`ok=False` | ✅ |
| US 全部回移 30 天 | 阻断 | `ok=False`：全局覆盖 70%、`US 市场数据失效 0/37` | ✅ |
| CN 全部回移 30 天 | 阻断 | `ok=False`：`CN 市场数据失效 0/23` | ✅ |
| CN 全部回移 8 天（节假日量级） | 容忍/降级 | `ok=True`，CN 区域 age=8、coverage=1.0，**无 CN warning**；degraded 仅由无关的 EA_HICP 触发 | ⚠ 设计容忍（≤10 天盲区） |
| 全部宏观回移 150 天 | 降级、不阻断、cap deep | `ok=True`，`degraded=True`，`critical_degraded=True`，fresh 2/16 | ✅ |
| UST 13 期限全回移 60 天 | 阻断 | `ok=False`：`UST 曲线全部过期 0/13`，`cdeg=True` | ✅ |
| UST 全删 | 阻断 | `ok=False`：`核心收益率曲线缺失：UST` | ✅ |
| CFTC 全部删除 | 仅 warning + degraded | `ok=True`，`CFTC 持仓缺失`，`cdeg=False` | ✅（按契约） |
| US 仅保留 12/37 标的 | 阻断 | `ok=False`：`US 市场覆盖流失 12/37` | ✅ |
| 真实 provider 抛异常 | 受控阻断 + 记录 | `RuntimeError: provider exploded` 直接穿透 `Ingestor.run` 与 `run_scan`；`scan_runs=0`，仅 `ingest_runs=failed` | ❌ P3（非受控路径） |
| provider 返回空帧（无 error） | 阻断 | `ScanBlockedError`，但 `scan_runs=0`（只有 ingest_runs/quality_issues 证据） | ⚠ P3 |
| provider 只返回 1 行（其余仅 warning） | 至少 degraded/阻断 | `ingest_prices.status=success`；整体 `run_scan` success；报告“覆盖率 100%”，无采集披露 | ❌ **P1-2** |
| `as_of` 早于全部数据 | 阻断 | `ok=False`，提示“价格表为空”（数据其实存在，只是 as_of 前没有） | ⚠ P3 文案 |
| `as_of` 超前 1145 天 | 阻断 | `ok=False`（age/coverage/region 多重 critical） | ✅ |
| `as_of` 超前 2 天 | 阻断或明确提示 | readiness 通过 → FeatureBuilder 静默 clamp 到 11-13，scan success（请求的 11-15 不落库、不告警） | ⚠ P3 |

**P1-2 的额外证据**（生产库副本 + 临时 provider）：fake price 仅返回 `US_EQ_SPY 2026-11-14` 一行、其余 124 个标的只产生 warning；`run_scan` 结果 `scan_status=success`、`scan_as_of=2026-11-14`、`stats.ingest.prices.rows=1`、`failed_targets` 截断为 100 条。报告头为：
`> 数据就绪：覆盖率 100%，最后价格 2026-11-14，降级=True。`
报告中没有 `采集状态` 字样。根因是 `reports.py:206-208` 只为 `scan_meta['ingest']` 渲染，而 `pipeline.py:147-151` 的 meta 从未放入 ingest；`Ingestor.run()` 的 `price_ok` 只看 `rows>0`，不看 `failed_targets`，因此“只成功 1 个标的”不会被判 partial，除非指标也失败。

### 2.2 日历 / 时间语义

| 输入 | 预期 | 实际 | 判定 |
|---|---|---|---|
| US 盘中 bar（same-session fetched 10:00Z < 21:30Z） | 丢弃 | 非 FX 列在该日 NaN，最后完整 bar 保持前一日；FX 豁免 | ✅ |
| 历史 bar 稍后回填（fetched 2026，bar date 2025） | 保留 | 保留，SPY 收益可算 | ✅ |
| 同一交易日 bar 同 session 早于收盘、且全市场都只有 partial | 丢弃并阻止用该 as_of 发布 | feature 层丢弃，但 readiness 只看原始行 → `ok=True`、US region `last=2025-01-10, age=0`，而全部 US/CN 特征最后日期 `2024-12-31` | ❌ **P1-3** |
| 中国节假日 8–9 天 | 容忍，不阻断 | CN 无 warning；只有其它市场问题 | ✅（但 outage 盲区，见上） |
| 周末 crypto 冲击 | 保留周末收益/异常 | `CR_BTC` 周六 -22% 的特征、anomaly（shock/drawdown/vol）均进入 `engine.current` | ✅ |
| 同一 as_of 重复扫描 | 幂等 | 2 条 success scan、99 anomalies 不增、2 个机会不增、`created=0 / refreshed=2`、`data_hash` 相同 | ✅ |
| `T>t` PIT（真实库 t=2025-06-30，T=2026-11-13） | build(t) == build(T).slice(t) | 价格/曲线/仓位 8,797,966 行完全相同；宏观缺 717 行（EA_HICP 在 T 已过期被整列剔除） | ⚠ **P2-2** |

**P1-3 复现数字**：合成库 8 标的 + 仅给 US 6 个标的加一根 `2025-01-10T10:00:00Z` 的 intraday bar；readiness：`ok=True`，`regions.US = {last_date: 2025-01-10, age_days: 0, coverage: 1.0}`；FeatureBuilder：`fs.as_of=2025-01-10`，但 `US_EQ_SPY/US_EQ_QQQ/US_FI_IEF/US_VOL_VIX/CN_EQ_CSI300` 的 `return` 最后日期全部是 `2024-12-31`（10 天前）。即“盘中 bar 刷新了新鲜度，却没有任何可用数据”。

### 2.3 DB / 工程故障

| 注入点 | 预期 | 实际 | 判定 |
|---|---|---|---|
| 异常检测后（transmission evaluator 抛错） | 全回滚 + failed | anomalies/transmissions/opportunities/events 全 0，scan=`failed`，无文件 | ✅ |
| opportunities 插入失败（SQLite trigger ABORT） | 全回滚 + failed | 5 表全 0，scan=`failed`，无 report | ✅ |
| 报告写出后失败（md 已落盘再抛） | DB 回滚 + 无残留文件 | DB 全 0，scan=`failed`，但 `report_2024-12-31.md` 保留（内容为伪造的 “LEAKED PARTIAL REPORT”） | ⚠ P2-4 |
| 导出中途失败（pipeline/task 文件已落盘后抛） | DB 回滚 + 文件一致 | DB 全 0，scan=`failed`，但 report+scan JSON+pipeline JSON+`RT-leak.json` 全部残留；`research_tasks=0` | ⚠ P2-4 |
| `research_tasks` 插入失败（export 内 DB trigger） | 全回滚 | DB 全 0，报告/任务文件仍残留 | ⚠ P2-4 |
| `finish_scan(success)` 写失败（trigger 仅拦 success） | 全回滚 + failed | 外层事务回滚；scan=`failed`，DB 计数回到 pre-scan；report/export 文件保留 | ✅ DB / ⚠ 文件 |
| `scan_runs` INSERT 失败 | 不产生半行 | `scan_runs=0`，其余 0 | ✅ |
| 重复扫描 | 幂等 | scan_runs=2、anomalies=99 不变、机会=2 不变、事件 created 2→refreshed 2、`data_hash` 相同 | ✅ |
| 嵌套事务：内层抛错、外层提交 | 仅内层回滚 | 外层 scan 行保留、内层 issue 0 行 | ✅ |
| 嵌套事务：外层抛错 | 全部回滚 | 该 scan 行/issue 均 0（前一已提交 scan 保留） | ✅ |
| 只读 DB（chmod 444） | 明确拒绝 | `Store` 能打开；首次写 `OperationalError: attempt to write a readonly database`；`scan_runs=0`，无 report | ⚠ P3（raw error，无优雅提示） |
| 写锁 DB（另一连接 `BEGIN IMMEDIATE`） | 超时/失败，不坏库 | 0.24s 抛 `database is locked`，`scan_runs=0`，`integrity_check=ok`；释放后恢复 | ✅ |
| 失败扫描的 `scan_runs` 状态 | 不可停在 running | readiness 阻断 → `blocked_data`；异常 → `failed`；无 `running` 残留 | ✅ |

DB 侧结论：**未发现 DB 半写**。唯一“泄露”是文件系统 artifact；该问题 round-2 已记录（`ROUND2_FIX_SUMMARY` 末条），当前仍未修复。

### 2.4 排序 / 研究价值 gate

| 构造候选 | 结果 | 判定 |
|---|---|---|
| 权重和 / 阈值 | 8 项权重和 = 1.0；`low_priority < watch < deep` 有序；组件均 ∈[0,1] | ✅ |
| 高异常（1.0）+ 2 条证据 + 无机制/无预期差/无催化 | score **0.5057 → low_priority**；未到 deep，也未 excluded | ⚠ 未排除；low_priority 仍会写 research_tasks/queue |
| 同上 + 当日事件 | score **0.5557 → watch**；可被 `goe handoff` 选中 | ⚠ 同上（watch 可自动研究） |
| 强价格 + 机制 + 催化 + **无预期差** | score **0.7475 → watch**，原因“预期差无法测量”；未进 deep | ✅（gate 生效；但仍在 watch 队列） |
| 弱机制（conf 0.3）+ `direction_conflict=True` | score **0.7535 → watch**，原因“机制预期方向与资产实际走势相反” | ✅（gate 生效） |
| 真实 11 个候选的 primary/theme | 11 个 primary 全部唯一，theme 全部唯一（无 `us_equity_broad` 等重复） | ✅ |
| 每原型 cap | 8/6/6/4/3/2 = 29 > `max_candidates=25`；最终按分数截断，主题去重再截断 | ✅（上限确实生效） |
| 配置可维护性 | `gates` 只含 3 个键；代码实际读取 `min_expectation_gap`(0.15)/`min_deep_research_data_quality`(0.5) 两个未写入配置的默认值；`status_thresholds.archive_below` 代码从未读取 | ⚠ P3 |
| 方向冲突覆盖 | 只有 `regime_repricing` 计算 `direction_conflict`；其它原型不读机制 `expected_direction`（event_revision 的机制为 None，可接受；但若未来原型挂机制，则无此 gate） | ⚠ 设计缺口 |

补充：代码里的 `degraded` 与 `critical_degraded` 语义与 readiness 文档承诺不一致。`readiness.py` 头注释称 degraded 会让“confidence gates prevent deep-research promotion”，但 pipeline 只传 `critical_degraded`；覆盖下降（50–80%）、CFTC 全缺、单条宏观过期都是 `degraded=True` 而 `critical_degraded=False`，deep 不会被 cap。这是行为/文档不一致，P2。

### 2.5 A→B 下游 artifact / CLI

使用 `/tmp/r3/fake_ia/ia_cli.py` 精确控制返回码和 `report.json`，`goe handoff --db <副本> --ia-path /tmp/r3/fake_ia --limit 1`：

| artifact | `run_task.status` | semantic | CLI exit | research_tasks | 判定 |
|---|---|---|---|---|---|
| ok_valid，rc=0 | ok | ok_valid | 0 | completed | ✅ |
| refused（S8 out_of_scope） | not_ok | refused | 2 | not_completed:refused | ✅ |
| partial（无 S8） | not_ok | partial | 2 | not_completed:partial | ✅ |
| insufficient（answered 但 L1/L2 皆空） | not_ok | insufficient_data | 2 | not_completed:insufficient_data | ✅ |
| rejected（run_ok=false） | not_ok | rejected | 2 | not_completed:rejected | ✅ |
| timeout（sleep>timeout） | timeout | None | 2 | not_completed:unknown | ✅ |
| missing（rc=0/17，无 report） | not_ok | partial | 2 | not_completed:partial | ✅ |
| IA 路径不存在 | unavailable | None | 2 | not_completed:unknown | ✅ |
| **L2-only**：`evidence_index=[]`、L1 rows=[]、L2 views.n=17、S8 answered、rc=0 | ok | **ok_valid** | **0** | **completed** | ❌ P1-1 |
| **同上 + rc=17** | **not_ok** | **ok_valid** | **0** | **completed** | ❌ P1-1 |
| **陈旧 artifact**：先成功写 report，再以 no-report rc=0 重跑同一 out_dir | ok | **ok_valid** | **0** | **completed** | ❌ P1-1 |
| `views` 为 list（类型异常） | error | — | 2 | not_completed:unknown | ⚠ P3（`parse_research_artifact` 直接调用会抛 `AttributeError`） |

**关键代码事实**：
- `ia_adapter.py:176` 的 `overall` 正确要求 `rc==0 AND ok_valid`；
- 但 `persist_result`（:198-225）只看 `semantic_status`，**完全不看 `res["status"]` / `returncode`** → rc=17 也写 `completed` + `ia_research_run`；
- `cmd_handoff`（`cli.py:257-295`）只在 `semantic_status != ok_valid` 时置 exit 2，因此 rc=17 且 semantic ok_valid 时 exit 0；
- `parse_research_artifact` 在 ok_valid 分支只检查 `n_l1_rows==0 and n_l2_views==0`，**不检查 `evidence_index`**，与函数 docstring 的“at least one evidence row”矛盾；
- `report.json` 用 `rglob` 取 mtime 最新，但不校验“本次运行生成”（无 run-start mtime 比较），也不清空 out_dir → 陈旧 artifact 可复用。

### 2.6 文档 / 运维

| 检查 | 结果 | 判定 |
|---|---|---|
| 密钥/凭据 | `scripts/check_secrets.sh` exit 0；tracked 无 DB/.env/parquet；无 `sk-`/`ghp_`/私钥模式 | ✅ |
| 绝对路径 | tracked 仅 `.env.example` 的 `/Users/you/...` 占位符；另有 `audit/ROUND2_RESEARCH_AUDIT.md` 中的 `/Users/cast/...` 示例 | ✅（无产品泄漏） |
| 测试数字 | `TEST_RESULTS.md` 写 121 passed/35s，分文件表合计 104 且漏掉 `test_readiness_handoff.py`；README 写 137；PROJECT_STATE 写 93；15:53 实测 143/73.9s，16:14 收集 147 | ❌ P2-5 |
| QA 复核数字自洽 | `QA_ROUND2_FIX_VERIFICATION.md` D1 声称 “TEST_RESULTS...137 离线+9 联网一致”，但 TEST_RESULTS 实际是 121；D2 又称 121 只是 round-1 对照，但 TEST_RESULTS 并未标明历史 | ❌ P2-5 |
| 工作树状态 | `EXECUTION_STATE.md` 15:05 写 “Worktree: clean; all changes committed and pushed”；15:53 起已有 4 个修改文件，16:15 为 8 个 + 未跟踪 R3 文档 | ⚠ P3（时点声明过期） |
| 可复现 hash | `config_fingerprint` 文件列表不含 `config/themes.yaml`、`sources.yaml`；仅改 themes 后 hash 完全不变（`caa1d42…`）。`data_fingerprint` 只 hash 行数与最后日期：把 SPY 某日 close 全部 ×1.5，hash 不变；删一行才变 | ❌ P2-3 |
| 异常数断言 | 快照 1,511 与 README/TEST_RESULTS/FINAL_ACCEPTANCE 一致（16:05 生产库曾出现 1,506，是并发重跑，不作为文档陈旧证据） | ✅ |
| 示例产物 | `docs/examples/report_2026-11-13.md` 的 scan_id `…8ef851` 不在快照 DB；属历史示例，但不可由当前库复现 | ⚠ P3 |
| 文档行为描述 | `docs/INTEGRATION` 失败表写“非零退出 → status=failed”，实际是 `not_ok`；未覆盖 rc=17 + ok_valid、陈旧 artifact 两条路径；`docs/SCORING` 写 catalyst ≤10 天=1.0，当前代码对“当日事件”给 0.6（0 天分支），文档未更新 | ⚠ P3 |

---

## 3. NEW 问题清单

> 严重度按“是否会改变对外结论/审计链”而非代码风格判定。P0=数据损坏/系统性假结论；P1=可复现的假成功或核心 gate 失效；P2=局部错误/可审计性缺口；P3=文案/健壮性。

### P1-1（NEW，最危险）A→B：失败进程/陈旧 artifact 被判为研究完成，CLI exit 0

**证据链**：
1. rc=17 + L2-only（`evidence_index=[]`、L1 rows=[]、L2 `views.n=17`、S8 answered）：
   `OPP-0001: not_ok rc=17 semantic=ok_valid`，**CLI_EXIT=0**，`research_tasks.status=completed`，event=`ia_research_run`。
2. 陈旧 artifact：先以 ok_valid rc=0 生成 `report.json`；再以“无新报告、rc=0”重跑同一 out_dir，第二次仍 `ok rc=0 semantic=ok_valid`、task completed、exit 0。
3. 解析器对 `evidence_index=[]` 但 L1 rows>0 或 L2 views>0 的 artifact 直接判 ok_valid（docstring 明确要求至少 1 条 evidence row）。
**影响**：`research_tasks` 与 `opportunity_events` 是 handoff 的唯一审计记录。一个下游崩溃/超时/空产物会被记成“研究已完成”，并让最终验收误以为 A→B 有过 ok_valid 样本；该路径可每天重复（out_dir 固定为 `exports/ia_runs/OPP-xxxx`）。这不是“下游 refused 被正确记录”的那条已修复路径，而是其反面。
**修复方向（本次不改）**：parser 必须校验 artifact 的生成时间晚于本次进程启动；ok_valid 必须同时满足 `rc==0`、`evidence_index` 非空（或至少 L1 事实行非空且不是 fallback）；`persist_result` 必须用 `res["status"]` 而不是 semantic 单独决定 completed；handoff 的 exit code 必须由 `run_task.status == "ok"` 决定；每次运行前清空/隔离 out_dir。

### P1-2（NEW）价格 provider 大面积失败仍发布 success，报告伪装 100% 覆盖且不披露采集失败

**证据**：fake provider 仅返回 1 行（其余 124 个标的只 warning），`run_scan` → `success`；scan_runs 的 `stats.ingest.prices.rows=1`、`failed_targets`（截断 100 条）；报告头 `覆盖率 100%，最后价格 2026-11-14，降级=True`，3 个机会、1,505 条异常，**无 `采集状态`**。
**根因**：`Ingestor.ingest_prices` 的 status 只由 `errors` 决定；`Ingestor.run` 的 `price_ok` 只看 `rows>0`；`run_scan` 只拦截 `status=="failed"`；`reports.py` 的采集状态行依赖 `meta["ingest"]`，而 `pipeline.py` 的 meta 没有这个键 → 该行是死代码。readiness 的“覆盖率”是 7 天窗口内的 instrument 覆盖，不是“本 as_of 有多少标的成功更新”。
**影响**：一次 provider 半瘫（或 Yahoo 只回部分 symbol）会产出“当天”的完整报告与机会，读报告的人只能看到 100% 覆盖；证据只藏在 scan_runs.stats/ingest_runs，不在报告/CLI 摘要里。

### P1-3（NEW）readiness 新鲜度可被“盘中未完成 bar”刷新，绕过 10 天断更保护

**证据**：合成库中 10 天无完整数据，仅加一根 `2025-01-10T10:00:00Z` 的 US 盘中 bar 后：readiness `ok=True`，US region `last=2025-01-10, age=0, coverage=1.0`；FeatureBuilder 会丢弃该 bar，所有 US/CN 特征最后日期 `2024-12-31`，但 `fs.as_of=2025-01-10`。scan 会以 `as_of=2025-01-10` 成功发布 10 天前数据，并在报告里写“最后价格 2025-01-10”。
**影响**：readiness 的原始 SQL 与 features 的 completed-bar guard 使用两套规则；一次断更后盘中恢复抓取即可重置新鲜度，而实际可用数据仍陈旧。与 round-2 已知的“当前 11-13 盘中 bar 被丢弃但 readiness 报 11-13”同源，但这里是更严重的**gate bypass**（10 天 vs 1 天）。

### P2-1（NEW）crypto 特征绕过 `clean_price_panel`，坏价产生 +900% 收益与 6 条假异常

**证据**：BTC 在 2024-11-01 注入 10×坏价。`price_issues` 正确记录 `extreme_move_quarantined`，清洗后的 `fs.prices["CR_BTC"]` 在该日为 NaN；但 `_load_prices` 在 `clean_price_panel` **之前**把原始 `_crypto_native` 存下，`_crypto_features` 直接从它算：`return 1d` 出现 `+900%` / `-89.9%`，detector 产出 6 条异常（`price_return_shock 1.0`、`drawdown_extreme 1.0`、`vol_regime_shift 1.0`、`trend_break 0.5` 等）。`CR_BTC` 是 M14 的 secondary affected asset。
**影响**：清洗层“已判定坏价”但仍进入特征/异常/报告；新加的周末 crypto 测试只验证周末收益存在，没有覆盖坏价清洗。属于本工作树修复引入的回归（修复前 crypto 使用清洗后的 px）。

### P2-2（NEW evidence）`slice_as_of` 的 PIT 性质对宏观不成立：T 已过期的序列在 t 被整列删掉

**证据**：最小复现：EA_HICP 在 t=2024-06-28 有 207 行特征，T=2024-12-31 时该序列被 `_load_macro` 判 stale（274 天）整列剔除；`build(T).slice(t)` 得到 0 行 EA_HICP，总行数差 207。真实库：t=2025-06-30 vs T=2026-11-13，8.8M 行中仅缺 717 行（全部 EA_HICP），共同行数值差 0（max 2.6e-13）。
**影响**：`slice_as_of` docstring 声称“exactly the information set available at that date”；replay 先用 case as_of 一次 build 再切 evaluation dates，因此“case as_of 时已过期、但 evaluation date 时仍新鲜”的序列会在所有早期评估日丢失。不是前视，而是**回放信号丢失**；新加的 P1-A 回归测试只覆盖 3 个价格标的。

### P2-3（NEW）可复现 hash 不覆盖 themes，且对数值修订不敏感

**证据**：
- `config_fingerprint` 只 hash universe/curves/macro/positioning/thresholds/scoring/mechanisms/events，不含 `themes.yaml`、`sources.yaml`。仅修改 themes 后 hash 完全相同（`caa1d42…`）；修改 universe 才变化。themes 决定候选去重（`theme_of` / 一主题一对象），改主题映射不会改变 config_hash。
- `data_fingerprint` 只 hash `COUNT(*)` 和 `MAX(date)`。把 SPY 2026-11-12 的 close/adj_close 全部 ×1.5，hash 不变；删一行才变。ingest 明确会回补修订（monthly 150 天 / quarterly 420 天），所以“data hash”无法审计数据修订。
**影响**：FINAL_ACCEPTANCE 的“可复现/可审计”承诺只覆盖“行数与日期”，不覆盖会影响候选的配置和数据内容。

### P2-4（已知残留，仍未修复）失败扫描的 report/export 文件残留且无状态标记

**证据**：fail_during_report：DB 0 行、scan=`failed`，`report_2024-12-31.md` 保留；fail_during_export：report+scan JSON+pipeline JSON+`RT-leak.json` 保留，DB research_tasks=0；`finish_scan` 写失败同样保留全套文件。报告本身不写 scan 状态，`write_reports`/`export_all` 直接 `write_text` 非原子。
**影响**：DB 回滚正确，但人/脚本读取 `reports/`/`exports/` 时无法分辨失败扫描；同 as_of 的下一次成功扫描会覆盖，若持续失败则旧文件冒充最新。round-2 已承认（`ROUND2_FIX_SUMMARY` 末条），至今未修。

### P2-5（NEW）文档/QA 的测试数字互相矛盾，且复核文档错误认证

**证据**：`TEST_RESULTS.md`：121 passed / 35s；分文件表合计 104，缺 `test_readiness_handoff.py`。`README`：137 离线。`PROJECT_STATE`：93 项。15:53 实测 143 passed / 73.9s；16:14 收集 147（并发新增测试）。`QA_ROUND2_FIX_VERIFICATION.md` D1 声称 TEST_RESULTS/README/FINAL_ACCEPTANCE 的“137 离线+9 联网全部一致”，但 TEST_RESULTS 实际写 121；D2 又称 121 仅为 round-1 对照，然而文件本身未标“历史”。这属于审计文档的可信度问题：**复核者没有打开 TEST_RESULTS 核对**。
**影响**：后续验收若引用这些数字，会把“当前测试数”说错；更严重的是 QA 的 “PASS” 基于错误的前提。

### P3 汇总（均有复现）

| # | 问题 | 证据 |
|---|---|---|
| P3-1 | provider 抛异常穿透 `Ingestor.run`/`run_scan`（raw RuntimeError，无 scan_runs 行；CLI 会 traceback exit 1） | `raising_run_scan`: `RuntimeError: provider exploded`, `scan_runs=0` |
| P3-2 | provider 返回空帧被阻断，但不写 scan_runs（readiness 阻断会写 `blocked_data`，两条阻断路径证据不一致） | `empty_run_scan`: blocked, `scan_runs=0`, ingest_runs=failed |
| P3-3 | 未来 as_of 静默 clamp：请求 2026-11-15，scan success 且 as_of=2026-11-13，无告警 | `result.as_of=2026-11-13` |
| P3-4 | as_of 早于数据时提示“价格表为空”（实际有数据），可能误导运维 | `9a_asof_before_2015`: `价格表为空` |
| P3-5 | 只读/锁库只抛 raw `OperationalError`，无 scan 记录与友好 CLI 错误 | readonly: `attempt to write a readonly database`；locked: `database is locked`, 0.24s |
| P3-6 | `L2 views` 为 list 时 `parse_research_artifact` 抛 `AttributeError`（run_task 捕获为 error） | `malformed_views: RAISED AttributeError` |
| P3-7 | 当日事件 catalyst=0.6 未写入 docs（docs 仍写 ≤10 天=1.0）；`archive_below` 死配置；`min_expectation_gap`/`min_deep_research_data_quality` 只在代码默认值 | 代码 `_score` vs `docs/SCORING.md`；`config/scoring.yaml` gates |
| P3-8 | docs/INTEGRATION 写“非零退出 → status=failed”，实际 `not_ok`；未记录 rc=17/陈旧 artifact 风险 | `run_task` 返回 `not_ok`；P1-1 |
| P3-9 | 示例 report/scan_id 不可由当前库复现；`EXECUTION_STATE` 的 “clean/all committed” 已过期 | `docs/examples/report_2026-11-13.md`；`git status` |

---

## 4. 单一最危险残留缺陷

**P1-1：A→B 把失败进程或陈旧 `report.json` 记成 `completed`，并以 exit 0 结束。**

它是唯一同时污染**状态、事件、CLI 退出码、验收结论**的缺陷：`research_tasks.status=completed` 与 `ia_research_run` 事件会让任何“有过成功 handoff”的查询得到肯定答案；而实际下游可能 rc=17、超时、或根本没有产出新报告。相比 P1-2/P1-3（数据旧或采集不全，仍可从 scan stats/readiness 追溯），P1-1 的假成功只留下“成功”记录，追溯成本最高；且 stale artifact 路径在每天的固定 out_dir 中天然可重复。

**最小验收级复现**（本次已跑）：

```bash
# 1) 生成一次 ok_valid artifact
FAKE_MODE=ok_valid FAKE_RC=0 .venv/bin/python -m goe.cli handoff \
  --db /tmp/r3/abcli2.db --ia-path /tmp/r3/fake_ia --limit 1 \
  --out-dir /tmp/r3/abcli2_runs
# 2) 同 out_dir 重跑，但下游不写任何新报告、rc=0
FAKE_MODE=missing FAKE_RC=0 .venv/bin/python -m goe.cli handoff \
  --db /tmp/r3/abcli2.db --ia-path /tmp/r3/fake_ia --limit 1 \
  --out-dir /tmp/r3/abcli2_runs
# 实际：SECOND_EXIT=0；task=completed；event=ia_research_run；解析的是上一次的 report.json
```

以及 rc=17 变体：

```bash
FAKE_MODE=l2_only FAKE_RC=17 .venv/bin/python -m goe.cli handoff \
  --db /tmp/r3/abcli.db --ia-path /tmp/r3/fake_ia --limit 1 \
  --out-dir /tmp/r3/abcli_runs
# 输出：OPP-0001: not_ok rc=17 semantic=ok_valid；CLI_EXIT=0；
# research_tasks RT-20261113-0001 status=completed；event=ia_research_run
```

---

## 5. 建议的修复顺序（仅建议，本次不改代码）

1. **P1-1**：`persist_result` 用 `res["status"]`；`run_task` 要求 rc==0 且新 artifact 且 evidence 非空；CLI 以 `status=="ok"` 决定 exit；out_dir 每次清空或按 run 隔离。
2. **P1-2**：`Ingestor` 把 `failed_targets` 纳入 price status（全失败=blocked，部分失败=partial+degraded）；`run_scan` 把 ingest partial 写入 `meta` 并在报告渲染；报告不再用 7 天覆盖率冒充“本 as_of 更新率”。
3. **P1-3**：readiness 复用 completed-bar guard（或基于 features 的 `last_complete_date` 计算 region freshness），partial-only bar 不得刷新 age。
4. **P2-1**：`_crypto_native` 在 `clean_price_panel` 之后重建（保留周末行），或 crypto 特征走同一清洗面板。
5. **P2-2**：`_load_macro` 不做 as_of 级整列剔除；把 stale 判定下推到每个观察日，保持 `slice_as_of` 的 PIT 性质。
6. **P2-3**：config hash 加 themes（及影响结果的 sources 允许列表）；data hash 至少纳入内容摘要（或 per-instrument 最大值/校验和）。
7. **P2-4**：report/export 先写 `.tmp` 再 rename；失败时写 `*_FAILED` 标记或 manifest；报告头写 scan status。
8. **P2-5**：冻结工作树后重跑 `pytest -m "not network"` 与 `-m network`，用实际数字更新 README/TEST_RESULTS/PROJECT_STATE，撤回 QA D1/D2 的错误认证。
9. P3：统一 ingest 失败/抛错/空帧的 scan 记录；未来 as_of 显式报错或告警；只读/锁库转成 CLI 可读错误；补 P1-1/P1-2/P1-3 的回归测试。

---

## 6. 本次未能验证 / 限制

- 未对真实 `investment-agent` 运行（只伪造 artifact）；P1-1 的真实触发概率取决于 B 的产物形态，但 stale-artifact 路径对任何“无新报告”的失败都成立。
- 未跑 `goe replay --cases` 全量；P2-2 只验证 `slice_as_of` 与 build 的不一致，未量化 7/7 回放是否改变。
- 未做浏览器/E2E、未验网络 provider 的实时行为；未审计前端。
- 生产库在审计期间被并发改写（16:11 后 scan 表为空），无法验证“当前生产库”的最终扫描；本报告以 15:55 快照为准。
- 工作树持续变动（16:14 后仍有新测试/修改），本报告结论对应 15:53–16:17 的代码快照；冻结后需按同一用例复跑 P1-1/P1-2/P1-3/P2-1。

---

*本文件是本次审计唯一有意写入的仓库文件；未修改任何源码、配置、测试、`data/goe.db` 或 git 状态（仅运行测试产生了忽略的缓存）。*
