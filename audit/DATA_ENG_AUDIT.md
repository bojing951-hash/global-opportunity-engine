# DATA_ENG_AUDIT — 数据工程独立审计（红队）

- 目标：`fix/autonomous-audit-remediation` @ `bb02363`（HEAD 快照 `/tmp/goe_head`）；DB 快照 `/tmp/audit.db`（md5 `2f308eb4…`，2026-11-14 09:43 HKT 复制）。
- 方法：只读代码/DB；HEAD 代码在 `/tmp` 快照执行；联网只做只读核对（Yahoo / Treasury / CFTC / BLS / BIS）；未改动仓库，唯一写入本文件。
- 注意：审计期间上游 worktree 被并发修改（P1-03/04 修复、`goe/readiness.py` 等正在写入）。本文结论一律以 HEAD `bb02363` 为准，未提交改动不作为依据。

## 1. 判决

**3 个已报告问题全部独立复现为 REAL**：P1-03，CFTC 先按 `as_of` 截断再 +4 天平移，`as_of=2026-11-04` 时 positioning 含 2026-11-07 行；P1-04，`net_to_oi` 实测等于原始净持仓 `-372,318.0`（正确值 `net/OI=-0.187421`），根因是 `_load_positioning` 只加载 16 条净持仓、从未加载 `:oi`；P1-07，`Ingestor.run()` 捕获并吞掉 `IngestError`，`run_scan` 完全不检查其返回值，空价格源下仍以 `success` 写出 2,935 条异常与 15 个机会。补充：provider 抛非 `IngestError` 时仍会向上抛，被吞掉的是“0 行但返回空帧”这一最常见的故障模式。

**新增 2 个阻断级缺陷**。(N1) 日收益在宽表上 `pct_change`，每个周一和节假日后首个交易日都是 NaN，被 `dropna()` 丢弃：扫描窗口内 122 个周一 `abs(z)≥3` 的日波动（近 30 天 24 个，含 EWZ 2026-10-26 的 -19.8%，已对 Yahoo 复核）在系统内全部没有对应异常；SPY 2026-11-09 的 +2.37% 同样没有 `return_z`，无法触发 1d 冲击。(N2) `trend_break` 用 `sign.fillna(0)` 与全局日历 `shift(10)`，把“10 个全局交易日前该标的休市”误判为均线翻转：1,181/2,935（40.2%）条异常由此产生，其中 88.6% 恰好落在休市日后第 10 行。后果是 OPP-0014、OPP-0015 仅靠假 golden_cross 成立，OPP-0009 的资产异常证据来自假 death_cross，OPP-0007 重复列出 4 条同一 golden_cross。

**另有 6 个 major**：breadth 特征恒为 0、`breadth_extreme` 永不触发；`rel_strength` 与 VIX 的“1m/5y”按含周末的联合日历行数计算（IWM 1m 相对强弱 0.0118 vs 真实 0.0294；VIX 5y 分位 0.9792 vs 按交易日 0.9245，对应 score 0.792 vs 0.245）；CN_SEC_NEWEN 因 3.213 倍份额折算未被识别而被隔离 520 天，仍计入“125 标的”；ERP 直接读 `US_CAPE`、绕过发布滞后与陈旧检查（回放前视）；扫描无事务边界，注入失败后异常行仍落库，且全库无外键；BLS 月度修订永不回补，2025-10 CPI 缺口使 2026-10 的 YoY 为 NaN（最新通胀不可见）。

**数据可信度**：所有已完成 bar 的溯源与官方源逐一吻合（见证据表），但 DB 最新 bar 是盘中快照（SPY 753.11 vs 最终收盘 754.37，成交量 5.9M vs 38.4M），不是日终值；BLS/CFTC/BIS 无 vintage 数据，无法证明“无修订风险”。综合判决：**数据链路基本可信，检测/时间语义层存在阻断级缺陷，系统当前不能宣称“14 类检测器、无前视、全部可复算、无伪机会”。**

## 2. 复现证据表

复现环境：`git archive HEAD | tar -x -C /tmp/goe_head`，`cp data/goe.db /tmp/audit.db`，在 `/tmp/goe_head` 用仓库 `.venv/bin/python` 执行。

| 检查 | 命令/方法 | 观察值 | 期望 | 结果 |
|---|---|---|---|---|
| P1-03 CFTC 前视 | `FeatureBuilder(as_of='2026-11-04')._load_positioning()` | 索引最大 2026-11-07，1 行晚于 as_of；feature 行 date=2026-11-07 | ≤ as_of | 复现 REAL |
| P1-04 归一化 | `net_to_oi` vs `net/OI` | `-372,318.0` vs `-0.187421`（16 列无 `:oi`） | 比率 | 复现 REAL |
| P1-07 失败吞没 | 空 provider → `Ingestor.run()`；stub 失败 ingest → `run_scan` | 返回 `{"prices_error":...}` 不抛；scan=success、2,935 异常/15 机会、stats 无 ingest 字段 | 抛错/阻断 | 复现 REAL |
| 溯源完整性 | SQL count null | prices 358,310 行、indicators 159,508 行，`source_id`/`fetched_at` 均 0 缺失 | 0 | 通过 |
| 已完成 bar 对源 | Yahoo/Treasury/CFTC/BLS/BIS | SPY 11-12=757.12；UST 11-12=5.10；CFTC 11-03 net=-372,318/OI=1,986,532；CPI 2026-10=337.511；BIS 2026-Q1=43,604.657 | 完全一致 | 通过 |
| 最新 bar 对源 | Yahoo chart（11-14 取数） | SPY 753.11 vs 754.37（-1.26，-0.167%，量 5.9M vs 38.4M）；GC 3898.40 vs 3887.60（+10.80，+0.278%）；EURUSD 1.105828 vs 1.105021（+0.000807，+0.073%） | 收盘价 | 失败 |
| 幂等 | 两次 `run_scan`（独立 DB 副本） | 2,935 条异常 id/日期/分数全等；15 个机会 fp/分数全等；124–139 s、1.87 GB RSS；DB 106 MB、feature 5.56M 行 | 全等 | 通过 |
| 部分写/FK | 注入 transmission 失败 | 1 条 anomaly 残留、`scan_runs=failed`；`pragma foreign_key_list` 全空 | 回滚 | 失败 |
| 周一收益 | `rets=px.pct_change(fill_method=None)` | SPY 1,095/2,375 为 NaN；2026-11-09 +2.37% 无 `return_z`；窗口内 122 个周一 `abs(z)≥3`，0 条异常 | 无缺口 | 失败 |
| trend_break | 重算 10 个全局行前是否休市 | 1,046/1,181=88.6% 为假翻转；占总异常 40.2% | 仅真翻转 | 失败 |
| breadth | `_breadth(px)` | `breadth_above_ma200` 6,560 行恒 0；`breadth_z_3y` 0 行；`breadth_extreme` 0 条 | 有值/可触发 | 失败 |
| 窗口语义 | rel_strength/VIX | IWM 1m 0.0118 vs 0.0294；HK 2800 -0.000584 vs +0.000069；VIX 5y 0.9792 vs 0.9245 | 同口径 | 失败 |
| CPI 缺口 | `_transform(US_CPI)` | YoY 最后有效 2026-09-01，2026-10=NaN | 最新月可见 | 失败 |
| 离线测试 | `pytest -m "not network"` | HEAD 97 passed | 97 | 通过 |
| E4 凭证/忽略 | `scripts/check_secrets.sh`；`git ls-files`；grep 绝对路径 | 无凭证泄漏、无 `.db`/`.env` 被跟踪、无 `/Users` 绝对路径；无 LICENSE 文件 | 无泄漏/有 LICENSE | 通过（除 LICENSE） |
| E5 调度脚本 | `bash -n scripts/*.sh`；读 `run_daily.sh` | 4 个脚本语法通过；scan 失败→exit 2；ingest-only exit 3 分支不可达；P1-07 使 ingest 失败也 exit 0 | 失败必非 0 | 部分失败 |
| A2 期货展期 | 50,705 条 `=F` 行 `adj_close==close`；换月窗口（15–22 日）尾部占比 | 展期未调整（文档已承认）；换月窗口 `abs(z)≥3` 占比 CL 25.2%、NG 25.3%、GC 21.6%，均匀预期 25.8% | 有/无污染 | 存疑（无法验证） |

## 3. 新问题

级别：blocker / major / minor / nit。行号为 HEAD `bb02363`。

| 级别 | file:line | 根因 | 复现 | 最小修复 | 对投资结论的影响 |
|---|---|---|---|---|---|
| blocker | `goe/features.py:388,437` | 在含 crypto 周末的宽表上 `pct_change`，周一/节假日后首日必为 NaN，被 `dropna()` 丢弃 | SPY 11-09 +2.37% 无 return_z；122 个周一极端日 0 条异常；EWZ 2026-10-26 -19.8% 漏检 | 按标的 compact 后 `pct_change`，或按各交易所日历重采样 | 1d 冲击漏检约 1/5 交易日；vol/vol_z 样本被截断；“全部可复算”不成立 |
| blocker | `goe/anomalies.py:346-349` | `sign.fillna(0)` + 全局日历 `shift(10)`，休市 NaN 被当作 0 符号 | 1,181 条 trend_break；88.6% 在休市日后第 10 行；OPP-0014/0015 仅由它成立 | 要求前后两端 `cross` 均非空，并按标的自身日历比较 | 40% 异常为假；机会池含 2 条纯伪机会（OPP-0014/0015），另有 4 条含假证据（OPP-0002/0007/0009/0013） |
| major | `goe/features.py:517-519` | 200 行窗口仅 137–141 个观测 < `min_periods=150` → ma200 全 NaN；`(px>NaN)` 变 0 而非缺失 | breadth 恒 0（6,560 行）；breadth_z 0 行；检测器 0 条 | 按本地日历重采样/对 ma 为 NaN 重新掩码 | “广度”证据全部失效，breadth 检测器永不出结果（14 类中 1 类死亡） |
| major | `goe/features.py:487,810-815` | 联合日历行窗口≠交易日；`rolling(200/1260)` 混入周末行 | IWM 1m 0.0118 vs 0.0294；HK 2800 符号翻转；VIX 5y 0.9792（867 观测≈3.44 年） | 统一按标的交易日窗口 | 相对强弱/VIX 分数尺度错误，跨资产不可比 |
| major | `goe/features.py:147,207-216` | 份额折算比 3.213 不在 `_SPLIT_FACTORS`；“回到前高 40% 内”永不满足 | CN_SEC_NEWEN 2024-09-18..2026-11-13 共 520 行被删，仍计入 125 标的 | 补 1.5/3.2 等折算因子；超限则整标的剔除并告警 | 静默丢失 2.2 年数据；真实 -40% 崩盘也会被整段删除 |
| major | `goe/features.py:670-681` | ERP 直接 `store.load_indicator(end=as_of)`，无 45 天滞后/陈旧过滤 | as_of=2023-08-15 的 ERP 使用 2023-08-01 CAPE（约 9 月初发布），行标 2023-08-31 | 走 macro 的 PIT 通道 | 历史回放前视；当前 CAPE 陈旧故未显性化 |
| major | `goe/pipeline.py:63,92,141-143`；`goe/db.py:152-153` | 无顶层事务、逐段 commit；无任何 FK | 注入 transmission 失败后 1 条 anomaly 残留；`foreign_key_list` 为空 | 单事务或先算后写；补 FK | 失败扫描污染异常表；ARCHITECTURE:176 的“单事务边界”不成立 |
| major | `goe/ingest.py:38,207-225`；`goe/sources/bls.py:158` | 增量起点=last_date-10 天，月度前 2 月修订永不回补；CPI 2025-10 缺口传播 12 个月 | payrolls/CPI start=2026-09-21；YoY 最后有效 2026-09-01 | 月度序列回补 3–4 个月；缺口不传播 YoY | 修订值/最新通胀不能进入判断 |
| major | 数据层（无代码行） | 最新 bar 为盘中快照：`fetched_at=15:05:43Z`（10:05 ET） | SPY 753.11/5.9M vs 收盘 754.37/38.4M；GC 3898.40 vs 3887.60 | 丢弃未收盘 bar 或收盘后抓取 | 最新收益/异常依赖抓取时刻；报告非 EOD |
| minor-major | `goe/pipeline.py:140`；`goe/reports.py:268`；`goe/opportunities.py:584,636,716,805,862` | quality_issues 只展示不参与；data_quality 硬编码；证据称 net/OI 但未标准化 | `unit_mult_conflict` 与当前 config 自相矛盾（config 已为 `USD_bn`，BIS 实测 43,604.657 bn，无真实冲突） | 将 issue severity 接入 gate；修正文案 | “数据质量不达标硬性排除”未实现；证据文本与计算不符 |
| minor | `goe/anomalies.py:802-842`；`config/thresholds.yaml:130` | 家族上限按“日”不按“扫描”；单链去重可无限链接 | 100 条同族/10 天全部保留（文档上限 60）；4 天间隔 10 条合并为 1 条且保留最高分 | 按扫描/按事件起点断链 | 异常数量不可比，事件起始日漂移 |
| minor | `config/thresholds.yaml:106` | `min_abs_change_3p=0.10` 未区分单位 | CN_CPI 2026-05-01 以 change=-0.1000035（超阈 2.4e-6）触发；payrolls 的 0.1 千人无意义 | 按序列单位设阈 | 宏观“实质性变化”门槛失效 |
| minor | `goe/ingest.py:175,183,265,273` | `elapsed_s` 在 `to_dict()` 之后才赋值 | 17 条 ingest_runs 的 `stats.elapsed_s` 全为 0.0 | 先赋值再序列化 | 运维/审计计时失真 |
| minor | `goe/anomalies.py:797` | 检测器异常只写 `DataFrame.attrs["errors"]` | pipeline/report 均不读取；单检测器失效不可见 | 写入 quality_issues/scan stats | 死检测器无法发现 |
| nit | 文档/脚本/死代码 | 127 vs 125 标的；breadth 检测器实际死亡；`run_daily.sh` 的 exit 3 不可达且 P1-07 使 ingest 失败也返回 0；无 LICENSE；`lead_lag_test` 无任何配置使用（40 corr + 13 conditional，0 lead_lag）；`load_prices` 文档称“行级记录用了哪列”但实际查询时 COALESCE | 见各节 | 更新文档/加 LICENSE/改文案/删死代码 | 对外声明不准确 |

## 4. 我无法验证的事项

- CFTC 实际发布时间（zip 只有报告日）：只能确认报告日与发布滞后逻辑，无法逐周验证周五发布时点。
- BLS/BIS/Eurostat 的历史 vintage：无 vintage 数据，无法量化修订幅度，只能证明当前值与实时接口一致。
- 2026-11-13 盘中那一刻 Yahoo 返回的原始值：只能事后取最终收盘推断（成交量/价差已足够证明是盘中 bar）。
- 期货逐日换月：无合约元数据；CL/NG/GC 的换月窗口（15–22 日）内尾部收益占比 25.2%/25.3%/21.6%，与均匀预期 25.8% 接近，无法证明存在/不存在展期污染。
- investment-agent handoff、web 仪表盘、报告渲染质量：未运行/未审计。
- 并发 worktree 中的未提交修复：未验收；若最终提交，应重跑 P1-03/04/07 与 N1/N2。
- 官方源授权/ToS 的法律效力：仅核对文档声明与公开可访问性。
- 2026 年数据本身是环境模拟数据，结论按“输入数据一致性”而非真实世界可交易性评估。

## 5. 附注

- 审计期间 worktree 新增/修改了 `goe/features.py`（:oi 与截断修复）、`goe/pipeline.py`（readiness 门禁）、`goe/readiness.py` 等；本文未依据这些改动。
- 审计期间只对 `data/goe.db` 做过只读查询（SQLite 可能生成/清理 `-wal`/`-shm`）；所有写入型实验均在 `/tmp` 副本上完成，未写入业务数据行。
- 本文件的唯一写入；未修改源码、配置、测试、数据、导出或 git。
