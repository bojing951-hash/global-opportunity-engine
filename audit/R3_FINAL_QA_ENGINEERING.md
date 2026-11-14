# R3 最终 QA（工程/数据，pass 1）

- 审计对象：`global-opportunity-engine`，HEAD `6755d34` + 工作树未提交修复
- 时间：2026-11-14 16:43–17:14 HKT
- 权限：只读仓库；唯一写入本文件。所有故障注入在 `/tmp/r3qa/` 的 SQLite 副本/合成库与 `/tmp/r3qa/src` 冻结源码副本上完成；未改 `goe/`、`config/`、`tests/`、`data/`、git。
- 冻结源码：16:46:43 HKT 复制到 `/tmp/r3qa/src`；17:12:33 复核仓库关键文件 sha256 与冻结副本一致：
  - `pipeline.py 45f4e62c…`、`reports.py 5656a946…`、`readiness.py 4e5df7be…`、`features.py 12e278cd…`、`ingest.py e26e6ad6…`、`cli.py 864036e8…`、`ia_adapter.py ca5f02e1…`、`db.py d9e7e6b4…`
- 数据快照：`/tmp/r3qa/base.db`（15:55 HKT 的 106MB SQLite backup：prices 358,310 / indicators 159,508 / 11 opportunities / 1,511 anomalies）。原因：生产 `data/goe.db` 在 16:11 被并发进程清空，16:45 仍有 `running` 扫描；审计不依赖该库的当前可变状态。
- 并发声明：审计期间工作树被并行修改（16:46 `pipeline.py` 补入 `meta["ingest"]`；17:12 另有 PROJECT_SPEC/README/TEST_RESULTS 等文档变更）。本报告结论对应上述源码哈希；若之后源码再变，需重跑本报告用例。

## 0. 判决

**PASS WITH ISSUES（NO-GO 级 P0/P1：无；2 个 P2、3 个 P3 残留）。** 九项指定验收全部按预期工作；P1-1（下游假成功）、P1-2（provider 1/125 仍成功）、P1-3（盘中 bar 刷新新鲜度）均已在当前代码修复并复测通过。未发现新的 P0/P1 回归。

## 1. 验收矩阵（全部使用新构造输入）

| # | 新故障输入 | 预期 | 实测 | 判定 |
|---|---|---|---|---|
| 1a | fake IA CLI：L2-only（`evidence_index=[]`、L1 rows=[]、L2 views.n=17、S8 answered）+ **rc=17**；DB 副本 | CLI exit 2；task 非 completed；无 `ia_research_run` | `OPP-0001: not_ok rc=17 semantic=insufficient_data`；exit 2；`not_completed:insufficient_data`；仅 `ia_research_not_completed` | PASS |
| 1b | 同 out_dir 预置一份 stale ok_valid `report.json`；CLI 不写新报告、rc=0 | 不得复用旧 artifact；exit 2；旧报告被清除 | exit 2；semantic=partial（“未找到可解析的结构化报告”）；stale `report.json` 被 rmtree 清除；同父目录 `OTHER-OPP/report.json` 保留 | PASS |
| 1c | 无报告、rc=0 | exit 2；task 非 completed | exit 2；`not_completed:partial`；无成功事件 | PASS |
| 1d | fake CLI sleep 30s，timeout=1s | exit 2；task 非 completed | exit 2；`not_completed:timeout`；无成功事件 | PASS |
| 1e | 完整 ok_valid artifact + **rc=17** | rc 非 0 仍不得成功 | exit 2；`not_completed:not_ok`；无成功事件 | PASS |
| 1f | 对照：ok_valid + rc=0 | exit 0；completed | exit 0；`completed`；`ia_research_run` | PASS |
| 2a | fake price provider 返回 **1/125** 行（无 error，仅 <20 行 warning） | `Ingestor.run` failed；`run_scan` 阻断并记录 blocked_data；无报告 | `status=failed, price_ok=false, price_coverage=0.0`；`ScanBlockedError`；最新 `scan_runs.status=blocked_data, as_of=2026-11-16`，stats 含 ingest；report/export 目录为空 | PASS |
| 2b | 模拟 partial ingest（100/125，status=partial），数据仍完整 | 扫描可运行；`meta["ingest"]` 存在；报告披露 partial | `scan JSON meta.ingest.status="partial"`；报告头出现 `> 采集状态：partial；错误源：无。`；同时仍有 `> 数据就绪：覆盖率 100%`（见残留 P3-2） | PASS（有披露；100% 行仍在） |
| 3a | 真实库副本：删除 2026-11-04 后全部价格，仅加 1 根 `US_EQ_SPY 2026-11-13` 同日 15:00Z 盘中 bar；as_of=2026-11-13 | `last_price_date` 保持 2026-11-03；age=10；scan 阻断 | `last_price_date=2026-11-03`、`age_days_vs_asof=10`、`ok=false`；`ScanBlockedError`；`scan_runs=blocked_data`；无报告 | PASS |
| 3b | crypto 同日 bar（2026-11-13T23:59Z）vs 次日抓取（11-14T01:00Z） | 同日 partial；次日 complete | `False` / `True` | PASS |
| 3c | 历史 bar 晚抓取（bar 2026-10-30，fetched 2026-11-20） | complete | `True` | PASS |
| 3d | US DST 夏/冬及切换日（2026-07-15、2026-01-15、2026-03-06/10） | 收盘+30min 前丢、后留 | 6/6 全对（20:10Z 丢/20:35Z 留；21:10Z 丢/21:35Z 留；EST 20:45Z 丢、EDT 20:45Z 留） | PASS |
| 3e | 合成 8 标的库：同日盘中 US bar + 次日抓取的历史 backfill bar | 盘中不入 panel；backfill 入 panel | `2025-01-10` 不在 panel；`2025-01-09` 在 panel；最后完整价 2025-01-09 | PASS |
| 4a | 删全部 UST | critical | `核心收益率曲线缺失：UST`，ok=false | PASS |
| 4b | 仅留 UST 2Y/10Y（2/13 期限） | warning，不 critical | ok=true；`UST 曲线期限不完整：仅 2/13 个期限存在` | PASS |
| 4c | 删 UST:2Y/10Y（其余 11 期限在） | critical | 两条 `核心收益率曲线缺少关键期限：UST:2Y/UST:10Y`，ok=false | PASS |
| 4d | 删 US_CPI + US_POLICY_RATE | critical | 两条 `核心宏观数据缺失`，ok=false | PASS |
| 4e | 删可选 EA_HICP + US_CAPE | 仅 degraded，不 critical | ok=true；degraded=true；critical=[] | PASS |
| 4f | lab mode（min_coverage=0） | 明确 warning | `lab mode: critical data dependency contract disabled` | PASS |
| 5a | 真实历史 PIT：t=2025-06-30，T=2026-11-13；`build(t)` vs `build(T).slice(t)` | 价格/收益/宏观/仓位/曲线无缺失、无多余、无值差 | long 各 8,799,879 行；onlyA=0、onlyB=0、value_mismatch=0、max_abs_diff=0；prices 2738×125、returns 2738×125、macro 166×16、positioning 547×32、4 条曲线全部逐 cell 相同（nan mismatch=0） | PASS |
| 5b | 未来 2:1 split 合成：t 在 split 前 / split 当日 / split 后 | 三处均应与后建后切一致 | 前/后 PASS（0 值差）；**split 当日**：build(t) 388 行、最后 2024-12-13，`build(T).slice(t)` 389 行、多出 2024-12-16；build(t) 把 split 日判为 `extreme_move_quarantined` 丢弃，后建后切判为 `split_adjusted` 保留 | **FAIL（P2-1）** |
| 6a | clean DB；report 写出后抛错 | DB 全回滚；报告文件删除；scan=failed | 6 表计数回 0/1 条 failed scan；`report_*.md`、`scan_*.json` 均删除 | PASS |
| 6b | clean DB；export 写出后抛错 | DB 全回滚；report+export 文件删除 | 6 表回 0/1 条 failed scan；report/queue/pipeline/RT 文件均删除；**残留 `HANDOFF_SCHEMA.json`** | PASS（P3-1 残留） |
| 6c | 已成功种子扫描后，再以 failure 重扫（既有 opportunities） | DB 全回滚 | 未复现目标行被写坏（pre/post 相同）；clean 场景已证明回滚 | PASS（探针有限） |
| 7 | 合成 BTC：周六 −25% + 10× 坏价；对照 SPY | 周末冲击保留；坏价隔离；SPY 不受影响；无重复 | 周六 2024-12-21 `return/1d=-0.25`；坏价 2024-12-11 记 `extreme_move_quarantined move=9.0` 且无 return 行；SPY long 6,299 行与无 crypto 库逐行相同；BTC 重复键 0 | PASS |
| 8 | 副本 config 仅改 `themes.yaml`；DB 副本仅改 1 个 SPY close | config_hash 变；data_hash 变 | 均变（`data_fingerprint` 由 `9ddd93ef…`→`10263b85…`） | PASS |
| 9 | `.venv/bin/python -m pytest tests -m "not network"` | 全绿 | **157 passed, 9 deselected, exit 0**（repo，75.43s；冻结副本 183.96s，并发导致变慢） | PASS |

## 2. 关键证据摘录

- P1-1：`persist_result` 现以 `res["status"]=="ok" and semantic=="ok_valid"` 判定 completed；`cmd_handoff` 以 `status!="ok" or semantic!="ok_valid"` 置 exit 2；`run_task` 先清空 out_dir 并以 `min_mtime` 拒绝陈旧 artifact；`parse_research_artifact` 对 answered+空 evidence 返回 `insufficient_data`。四种失败 + rc17/valid 变体均无可成功事件。
- P1-2：`Ingestor.run` 用 `n_failed/targets` 计算 coverage，<0.5 判 failed；`run_scan` 对 failed 先写 `blocked_data` scan 行再抛 `ScanBlockedError`；`pipeline.meta` 已含 `ingest`，报告渲染 `采集状态：partial`。
- P1-3：`readiness` 的 last/coverage/region 全部改用 `FeatureBuilder.bar_is_complete`；10 天旧数据 + 1 根盘中 bar 不再被刷新（age=10，blocked）。
- P1-A：真实库 t/T 全量 long 8.8M 行逐位一致，宏观未再因 T 处 stale 整列剔除（修复生效）。

## 3. 剩余问题（无 P0/P1）

| 级别 | 问题 | 证据/影响 | 建议 |
|---|---|---|---|
| **P2-1** | P1-A 在 split 当日仍不成立 | 合成 2:1 split：`build(2024-12-16)` 丢弃当日（388 行，最后 12-13）；`build(2026-..).slice(2024-12-16)` 保留并调整为 389 行。历史回放若 evaluation date 恰为拆股日，会少一天/一条收益；当前库尚无未来拆股，故不影响当日发布 | split 判定在“无 pos+1 未来观测”时也应结合当日 adj_close/volume 或允许 rebase；或回放日期避开拆股当日并披露 |
| P3-1 | 导出失败残留静态 schema | clean export 失败后 `HANDOFF_SCHEMA.json` 留在 export 目录（`_remove_failed_artifacts` 未列入）；不是扫描结论文件 | 失败清理加入 schema；或 schema 改为仅在成功时写 |
| P3-2 | partial ingest 报告仍显示“覆盖率 100%” | 报告头同时有 `覆盖率 100%`（7 天窗口 readiness）和 `采集状态：partial`；报告未展示 `price_coverage=0.8` 这个采集口径 | 报告头改成“数据就绪覆盖率 / 本次采集覆盖率”双行，避免读者只看 100% |
| P3-3 | ingest failed 阻断的 details 为空 | `run_scan` 的阻断异常 `details={}`（该路径无 `*_error` 键，只有 status/n_failed）；scan_runs.stats 完整 | 异常消息补 `status/price_coverage/n_failed` |
| P3-4 | lab mode 可静默关闭关键数据合同 | `min_coverage=0` 时删 UST 仍 `ok=true`（仅 warning）；本次仅验证“lab warning 存在”，该设计缺口为已知项 | 生产入口禁止 min_coverage=0，或改名为 `allow_missing_critical_data` 并显式审计 |

## 4. 结论

指定 9 项中 8 项全 PASS；第 5 项的主路径（真实历史价格/宏观/曲线/仓位）PASS，仅“未来拆股当日”合成边界为 P2。P1-1/P1-2/P1-3 三条原 P1 均已闭环并有新输入证据；未发现新的 P0/P1 回归。**当前工作树可判 PASS WITH ISSUES，不建议以“零问题”签收。**
