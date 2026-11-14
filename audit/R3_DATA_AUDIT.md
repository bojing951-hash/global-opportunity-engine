# ROUND 3 — 独立数据/量化审计（P1-A / P1-B / P2-B 复核 + 新缺陷）

- 仓库：`/Users/cast/Downloads/金融系统/global-opportunity-engine`，HEAD `6755d34` + 未提交修复。
- 运行库：`data/goe.db`（prices 358,310 行；last price 2026-11-13；indicators 159,508 行）。
- Python：`.venv/bin/python`（3.12.13，pandas 3.1.1）。
- 时间：2026-11-14 15:53–16:32 HKT。
- 方式：只读仓库与运行库；只写本文件；对抗性用例全部在 `/tmp` 的库副本/合成库上构造。**未修改任何代码、配置、测试、git。**
- **快照声明**：审计期间工作树被并行修改。主结论（P1-A 全量 A/B、P1-B 矩阵、P2-B）针对冻结快照：
  - `goe/features.py` sha1 `285263950e89cb010f04a60eac4ffae74dc83083`
  - `goe/readiness.py` sha1 `76eac9a714c2248c49e76a92ea52825cead81dba`
  - 冻结副本：`/tmp/r3snap`。
- **最终版本（16:27:24，报告定稿 16:32 复核）**：`features.py` sha1 `4d6c1f31…`、`readiness.py` sha1 `58cbf13d…`。审计期间这些文件被并行修改，且修改内容正好覆盖本报告的 NEW-1（crypto 原生清洗）、NEW-3（宏观 slice）、NEW-4（crypto 同日 bar）、NEW-9（readiness 完成 bar）、NEW-2 的基准期限检查与 NEW-10 的 crypto 特判。我在最终哈希上复核：
  - 全量离线测试 **156 passed / 9 network deselected，exit 0**（含 `test_crypto_same_day_bar_is_not_a_completed_daily_bar`（16:27:24 前为红）、`test_missing_key_tenor_blocks_even_if_other_tenors_exist`、`test_intraday_partial_bar_cannot_refresh_a_dead_market`）；
  - 宏观经济层 `build(2024-09-30)` vs `build(2026-11-13).slice(2024-09-30)` `onlyA=0`（NEW-3 修复）；
  - crypto glitch 用例原生 return/drawdown 已消失、周末冲击仍在（NEW-1 修复）；
  - UST 基准期限 2Y/10Y 缺失 → critical；只剩 2Y+10Y（2/13）仍 `ok=True`（NEW-2 残留部分）；
  - bar 级合成用例（US/EU/CN/JP、DST、回填）8/8 PASS；
  - readiness 关键矩阵（UST 全删、CPI 全删、可选删除、CN 13/23、CN 全删、lab、历史 as_of、节日）结论不变。
  - 未重跑：最新哈希上的全量 A/B long build（`_load_macro` 修复已用宏层对比复核 `onlyA=0`；价格/收益面板逻辑未变）。

## 一、判决

**PASS WITH ISSUES（有条件）：本轮 P1 级新缺陷均在审计期间修复并复测；剩余 NEW-2 残留（P2）与 NEW-5/6/7/8/10/11（P2/P3）不阻断当前数据，但应登记后再关闭数据层。**

- **P1-A：主路径成立**。CSI300/SPY/EU/JP 四市场 `build(t)` 与 `build(T).slice_as_of(t)` 的价格面板、收益面板与 long 行值逐位一致；2024-09-30 CSI300 = **4017.855**（若误用上一有效 bar 会是 3703.685）；DST 夏/冬令时与同日盘中 bar 的丢弃规则全部符合预期。
  冻结快照中 **“exact same long rows” 全局不成立**：`build(2024-09-30)` 比 `build(2026-11-13).slice(2024-09-30)` 多 **663 行**（全部 `EA_HICP`，因 `_load_macro` 在 T 处整条剔除陈旧序列，NEW-3）；收尾版改为“保留历史、只标记 stale”，复核 `onlyA=0`，**现为 PASS**。
- **P1-B：删除式对抗矩阵全部按声称工作**（UST 全删 / US_CPI+US_POLICY_RATE 全删 → critical；仅删 EA_HICP+US_CAPE → ok+degraded；13/23 CN → warning；CN 全删 → critical；节日缺口不误报）。
  但 **核心曲线的“部分缺失”只被部分识别**：收尾版新增 `REQUIRED_CURVE_TENORS`，删 2Y 或 10Y → critical（已修）；但只留 2Y+10Y（2/13 期限，3M/30Y 等全丢）仍 `ok=True`、`critical=[]`、无新 warning。见 NEW-2（残留 P2）。
- **P2-B：周末主路径成立**。BTC 周六 −25% 在原生日历保留（206 个周末收益、周六 z=−13.12、周六 `price_return_shock` 命中），SPY 的 Monday 收益/MA200/breadth 与无加密库逐位一致；无重复 crypto 行；周六时点 build 与之后 slice 一致（未发现前视）。
  快照版本中加密原生路径 **绕过了 `clean_price_panel`**（NEW-1），且 **同日 crypto bar 无 partial 保护**（NEW-4）；收尾版已分别修复（原生清洗 + crypto 按“次日抓取才算完成”过滤，实测 CR_BTC return 最后日期 11-12）。仍余 crypto/equity 口径混用（NEW-7）与 FX 的 24/7 完成语义（NEW-10 FX 部分）。
- 独立复算：SPY 收益/波动/回撤、CFTC net/OI、CPI YoY、UST 变化全部一致；VIX 分位差 0.0054（已知行窗口 vs 有效观测口径，非算术错误）。
- 离线测试：**156 passed / 9 network deselected，exit 0**（最终工作树，165 collected；16:22 快照为 153/162，16:27:24 之前一度 154 passed+1 failed）。
- 最终状态：NEW-1 / NEW-3 / NEW-4 / NEW-9 已修复并复测；NEW-2（2/13 期限仍静默）与 NEW-5（lab 模式）、NEW-6、NEW-7、NEW-8、NEW-10（FX）、NEW-11 仍开放，均不阻断当前数据；最重要的仍开放新缺陷是 NEW-2 残留。

## 二、检查表

### 2.1 P1-A 不可用 bar 与 as-of 一致性

| # | 检查 | 实测 | 判定 |
|---|---|---|---|
| A1 | `build(2024-09-30)` vs `build(2026-11-13).slice(2024-09-30)` 价格/收益面板 | 2543×125 vs 2543×125，列/索引完全相同，逐 cell 差异 **0** | PASS |
| A2 | 四市场 long 行值 | 共同键 8,113,080 行，值不一致 **0**；四市场逐特征（return 1d/1m、ann_vol 1m、ma_gap_200d、drawdown）完全相等 | PASS |
| A3 | 2024-09-30 CSI300 | `prices` = **4017.855**（09-27=3703.685）；return 1d=8.4826%、1m=22.2535%、vol 1m=38.7058% | PASS |
| A4 | SPY / EA_EQ_SX5E / JP_EQ_N225 同日 | 560.8178 / 5000.4502 / 37919.5508，两路径一致 | PASS |
| A5 | long 行集合全局一致性 | 冻结快照：`only A = 663`（全部 `EA_HICP`），`only B = 0`，值 mismatch 0；收尾版 `_load_macro` 保留历史后复核 `onlyA=0` | 快照 FAIL → **收尾 PASS**（NEW-3） |
| A6 | 同日盘中 bar（US 10:00Z） | 丢弃（last price 停在上一交易日） | PASS |
| A7 | 历史回填 bar（later date 03:00Z） | 保留 | PASS |
| A8 | DST 边界（合成） | US 夏 20:10Z 丢 / 20:40Z 留；US 冬 21:10Z 丢 / 21:40Z 留；EU 夏 15:20Z 丢 / 16:10Z 留；EU 冬 16:10Z 丢 / 17:10Z 留；CN 07:10Z 丢 / 07:40Z 留；JP 06:10Z 丢 / 06:40Z 留 | PASS |
| A9 | 拆股 P1-A 方向 | 当前快照 `clean_price_panel` 改为“改后段、不动前段”，真实库 A/B slice 0 值差异（含 CN 拆股/份额转换标的） | PASS |

结论：P1-A 的 4 个指定市场与 bar 级规则通过；**P1-A 的“逐行一致”在宏观层被 `_load_macro` 的整条陈旧剔除破坏**（NEW-3）。

### 2.2 P1-B Critical Data Dependency Contract

生产模式 `min_coverage=0.8`，`as_of=2026-11-13`，真实库副本逐项删除：

| 场景 | ok | critical | degraded | critical_degraded | 判定 |
|---|---|---|---|---|---|
| 基线（未删） | True | [] | True（EA_HICP） | False | PASS（与 round-2 验收一致） |
| 删除全部 UST | **False** | 核心收益率曲线缺失：UST | True | False | PASS |
| 删除 US_CPI + US_POLICY_RATE | **False** | 核心宏观数据缺失：2 条 | True | False | PASS |
| 仅删 EA_HICP + US_CAPE | True | [] | True | False | PASS（可选只降级） |
| CN 13/23 有数据（10 个丢失） | True | [] | True（含“CN 市场覆盖下降：13/23”） | False | PASS（warn） |
| CN 10/23 有数据 | False | “CN 市场覆盖流失：仅 10/23” | True | False | PASS（<50% 即 critical） |
| CN 全删 | False | “CN 市场完全没有价格数据：关键市场数据失效” | True | False | PASS |
| **UST 仅留 2Y+10Y（删 11/13 期限）** | **True** | [] | True | False | **FAIL（NEW-2 残留，P2）**：3M/30Y 等丢失不告警 |
| **UST 删 2Y+10Y（剩 11 期限）** | **False** | 核心收益率曲线缺少关键期限：UST:2Y、UST:10Y | True | False | **PASS（收尾版修复）**：UST 级 slope/倒挂/曲率仍全为 0 行，但门禁已拦截 |
| UST 全期限过期（截到 2024） | False | “UST 曲线全部过期：0/13” | True | True | PASS（既有系统级 stale） |
| 节日缺口：as_of=2024-10-03（CN 国庆）/ 2024-12-25 | True | [] | True | False | PASS（无覆盖误报） |
| 历史 as_of=2015-01-30 | **False** | 核心宏观数据缺失：US_CPI、US_POLICY_RATE | True | True | **过阻（NEW-6，P3）** |
| 历史 as_of=2015-02-20 | True | [] | True | False | 边界通过 |

生产 vs lab：`min_coverage=0.0` 时 **删除 UST 或删除 US_CPI+US_POLICY_RATE 都得到 `ok=True`、`critical=[]`**——整个“关键数据合同”被一个覆盖率旋钮静默关闭（NEW-5，P3；设计意图是 lab，但调用方无法从参数名看出会关闭致命合同）。
另：`JP_CPI` 截到只剩 135 天旧观测时，readiness 仍把它算 fresh（`fresh_macro=14`、无 JP_CPI stale），而 FeatureBuilder 的 `STALE_AFTER_DAYS=110` 会整条剔除——这是 round-2 #8 的“已知未修”，非本轮新问题。
收尾版本（16:21）readiness 把 last price/coverage/region 统计改为基于 `FeatureBuilder.bar_is_complete`：在最新代码上重跑本表全部场景，ok/critical/degraded/critical_degraded 与表中一致；`last_price_date` 仍为 11-13（CN/JP），但 US/EA/WORLD 的 `regions.last_date` 已变为 11-12（与特征层一致），NEW-9 据此从“未修”改为“已修复”。

结论：全删/整条过期路径通过；**“部分期限缺失”与“基准期限缺失”是合同未覆盖的静默区**。

### 2.3 P2-B 加密原生日历

合成库：4 只美股 ETF 的 520 个 bday + BTC 727 个自然日（含 2024-12-21 周六 −25% 冲击）。

| # | 检查 | 实测 | 判定 |
|---|---|---|---|
| B1 | 周末收益保留 | CR_BTC return/1d 726 行，其中周末 206 行；周六值 = −0.25 | PASS |
| B2 | 周末 z / 异常 | 周六 z=−13.12；`price_return_shock` 在 2024-12-21（周六）命中，score 1.0 | PASS |
| B3 | SPY 不受污染 | SPY return 1d/1m、ann_vol、ma_gap_200d、drawdown、z 与无加密库逐位一致；US breadth 520 行逐位一致；Monday 收益 103 个、最大差 0.0 | PASS |
| B4 | 重复 crypto 行 | CR_BTC 10,955 行，(feature,window,date) 重复 0；周末 3,110 行、工作日 7,845 行 | PASS |
| B5 | 原生特征前视 | 以周六为 as_of 的 build 与 T 后 slice 到周六：10,829 行、索引一致、值差 0 | PASS |
| B6 | 加密价格清洗 | 冻结快照：零价坏点被记录（`nonpositive_price 2024-12-26`），但原生特征仍输出 return=−1.0、drawdown_252d=−1.0。收尾 16:23：原生序列改为独立清洗，复测 glitch 日 return/drawdown 已消失；但同一坏点被记录两次（NEW-11） | 快照 FAIL → **收尾已修复**（NEW-1） |
| B7 | 同日盘中 bar | 冻结快照：合成库最后一天 BTC bar 同日 10:00Z 仍被使用（crypto 豁免 partial guard）。收尾版：`_crypto_raw_native` 也按 `bar_is_complete` 过滤；实测真实库 CR_BTC return 最后日期=11-12；新测试通过 | 快照 FAIL → **收尾 PASS**（NEW-4） |
| B8 | 跨资产窗口混用 | `CR_BTC return/1m` = 30 个自然日（−15.6114%）；同标的 `rel_strength_vs_benchmark/1m` = 21 个 bday（-13.756%，日期还早一天）；crypto `drawdown_252d` = 252 个自然日（≈8.3 个月），报告表头却是“距1年高点”；crypto 无 `momentum_12_1` | **PARTIAL（NEW-7，P2/P3）** |
| B9 | `history_start` 一致性 | pipeline 传 6.5 年 `history_start` 时，crypto long 仍回溯到数据起点（2023-01-02 vs prices min 2024-06-03） | 记录（P3，未单列） |

### 2.4 独立复算（原始 DB，未 import 特征函数）

按 `_drop_incomplete_bars` 后的最后完整 bar（US 11-12，CN/JP 11-13；SPY 11-13 因 15:05Z 同日盘中被丢）复算：

| 指标 | 独立复算 | 特征层 | 结论 |
|---|---|---|---|
| SPY 1d / 1m / 3m / 12m 收益 | −0.354036% / −1.621619% / −2.233551% / +12.048074% | 同 | 一致 |
| SPY ann_vol 1m / 3m / 12m | 21.8393% / 14.62559% / 13.70754% | 同 | 一致 |
| SPY drawdown_252d / drawdown_5y / ma_gap_200d | −2.819961% / −2.819961% / +3.859243% | 同 | 一致 |
| 黄金 CFTC net / OI / net_to_oi | 103,614 / 399,169 / 0.2595743 | 同 | 一致 |
| 黄金 net_change_4w / net_pctile_5y | −2.061881% / 0.5907336 | 同 | 一致 |
| US_CPI YoY（obs 2026-09-01，avail 2026-10-16） | 3.737685% | 3.737685%（date 2026-10-16） | 一致 |
| UST 10Y level / Δ21d / Δ63d / Δ252d / 2s10s | 5.10 / −0.11 / +0.42 / +0.99 / 0.24 | 同 | 一致 |
| VIX level / pctile_5y / z_3y | 18.70 / 0.576648 / 0.784053 | 18.70 / **0.582028** / **0.780611** | 分位 Δ0.00538、z Δ0.00344（行窗口 vs 有效观测；窗口内 46 个 bday 缺口；round-2 #13 已记录） |
| BTC return/1m | −15.6114%（30 个自然日） | −15.6114% | 一致（但见 B8 口径混用） |

**未发现收益/波动/回撤/持仓/CPI/利率的算术错误。** 唯一不一致是 VIX 分位口径（已知）。

### 2.5 静默错误排查

| 项 | 观测 | 判定 |
|---|---|---|
| `feature_version` | 仍为 `v1`（`goe/features.py:31`），但本轮新增 `_crypto_features`、crypto 窗口改为 30/91/365 自然日、拆股调整方向反转、DST 收盘时间；scan_runs/report 仍写 v1 | **FAIL（NEW-8，P3）**：方法变了版本没变，复现声明失真 |
| `price_data_issues` | 17 项（CN 拆股/份额转换/毛刺、CL 负价、JP_TOPIX 毛刺）只在 scan meta/report 出现；crypto 坏价被记录却不影响加密特征（NEW-1） | 部分静默 |
| 宏观陈旧 | `EA_HICP 347d / US_CAPE 1169d` 在 meta 与 readiness 披露；但“整条序列删除”导致 slice 丢历史（NEW-3） | 部分静默 |
| 期货换月 flag | 仅 `symbol.endswith("=F")` + `day>=27 or day<=2`；连续合约未做展期调整。清洗后收益重算 CL 日 15–23 平均绝对日收益 1.94% vs 其余日 1.96%，本数据上未复现月中换月放大的统计信号；仅保留 round-2 的具体个案（2016-01-21 z=3.96、2026-09-23/10-21 缺口、`near_month_end=False`） | **ROUND-2 #7 未修**（非新） |
| 周末/A 股日历 | bday 面板含 A 股节假日 NaN；`safe_pct_change`/per-instrument 收益按有效观测，breadth 用有效观测，未发现 A 股节日导致的收益错位；CN 国庆/圣诞 as_of 不误报 | PASS |
| readiness vs 特征层 last date | readiness 报 `last_price_date=2026-11-13, coverage=100%`，但特征层因同日盘中丢掉了 US/EU 的 11-13 bar（US 实际 11-12）；报告 as_of=11-13 与快照数据日不一致且无披露 | **P3（NEW-9）** |
| 小市场全灭 | 配置 <3 个标的的市场（CA/ES/FR/IT/TW/CH）全删仍 `ok=True`，仅 warning（round-2 #1 既有） | 已知未修 |

### 2.6 离线测试

- `.venv/bin/python -m pytest tests -m "not network" -q` → **156 passed，9 network deselected，exit 0**（165 collected；16:22 快照 153/162；16:27 修复前曾 154 passed + 1 failed）。
- 新增/相关测试（P1-A backfill、build vs slice、DST、future split、crypto weekend、readiness contract、partial CN）全部通过。
- 注意：`test_build_asof_and_later_slice_are_point_in_time_consistent` 只用了 3 个价格标的、无宏观序列，因此**没有覆盖** NEW-3 的 EA_HICP 场景；建议补一个含“T 处过旧、t 处可用”的宏观序列的断言。

## 三、NEW 问题（按严重度）

### P1 — 审计期间已修复（NEW-1）；NEW-2 已降级为 P2 残留

**NEW-1｜加密原生特征绕过价格清洗（冻结快照 P1；16:23 已修复并复测）**
- 位置：`goe/features.py` `_load_prices()`（快照版在 `clean_price_panel` 之前抓取 `self._crypto_native` 原始值）→ `_crypto_features()`。
- 证据（合成库 `/tmp/r3_c3.db`；快照版复现）：CR_BTC 2024-12-26 close=0.0 →
  - `fs.meta["price_data_issues"]`：`{"instrument_id":"CR_BTC","kind":"nonpositive_price","dates":["2024-12-26"],"count":1}`（清洗器已识别）；
  - 清洗后 bday 面板 2024-12-26 = NaN；
  - 但原生特征：`return/1d = -1.0`、`drawdown_252d = -1.0`，且会参与 `robust_z`、`rolling_percentile` 与 `price_return_shock`（|z| 上限 score=1.0）。
- 影响：一次交易所/聚合层坏点即可生成 100% 假跌幅异常、污染 30/91/365 日波动与 252 日回撤，并在报告里同时出现“价格清洗：非正价格”和“−100% 冲击”两条自相矛盾的证据。当前真实库 CR_BTC/ETH/SOL 尚无此类坏点（本轮 17 项 price issues 无 CR_*），属高可信潜在故障。
- 收尾验证：16:21–16:23 版本改为在 `build()` 内对 `_crypto_raw_native` 再跑一次 `clean_price_panel`；复测 `/tmp/r3_c3.db`（2024-12-26 零价）：原生 return/drawdown 该日已消失、周末 −25% 冲击仍在、周六异常仍命中。**但清洗器对同一 crypto 坏点记录了两条相同 issue（NEW-11）。**

**NEW-2｜P1-B 合同不覆盖“核心曲线覆盖率”（基准期限已修，2/13 残留）**
- 位置：`goe/readiness.py` 的 `REQUIRED_CURVES` / `REQUIRED_CURVE_TENORS` 块。
- 证据（真实库副本，生产模式）：
  - 冻结快照：删除 11/13 个 UST 期限、只留 2Y+10Y → `ok=True`；删除 2Y+10Y → `ok=True` 且 UST 级 `slope_2s10s / slope_2s10s_change_1m / slope_2s10s_z_3y / slope_2s10s_pctile_5y / curve_inverted / curvature_2_5_10` 全部 0 行，cross-asset `stock_bond` 也因缺 10Y 被跳过。
  - 收尾版（16:25）：新增 `REQUIRED_CURVE_TENORS = {"UST": {"2Y","10Y"}}`，删 2Y 或 10Y → `ok=False, critical=核心收益率曲线缺少关键期限`（已修）。
  - 残留：**只留 2Y+10Y（2/13 期限，3M/30Y 等全丢）仍 `ok=True, critical=[], 无 warning`**；检查仍是“存在性”，不校验 `cdef.tenors` 覆盖率/`benchmark_tenors` 的 30Y。
- 影响：UST 仍可静默退化为 2 个期限；曲线族异常/机制/候选（3M10Y、曲率、30Y、stock_bond 等）缺失而不告警。
- 建议：对 UST 增加 tenors 覆盖率阈值（如 ≥80%）或至少检查 3M/30Y 基准期限；`present_n` 统计同时报 degraded。

### P2 — 本轮新发现

**NEW-3｜`slice_as_of` 的宏观点时不成立（EA_HICP 663 行；收尾版已修复）**
- 位置：`FeatureBuilder._load_macro()` 的 `STALE_AFTER_DAYS` 整条剔除 + `FeatureSet.slice_as_of()` 文档承诺。
- 证据：`build(2024-09-30)` 8,113,743 行 vs `build(2026-11-13).slice(2024-09-30)` 8,113,080 行；多出的 663 行全部 `EA_HICP`（`value/change_1p/change_3p/change_12p/z_3y/pctile_5y`），因为 2026-11-13 处 EA_HICP 最新观测 2025-12-01（347 天）>110 天被整条剔除；2024-09-30 处它仍新鲜。
- 影响：`slice_as_of` docstring 与 `docs/VALIDATION.md` 的“逐时点一致性”声明不成立；`run_case_validation` 正是“期末 build → 逐日 slice”，历史上可用的宏观序列会在所有早期时点消失（当前仅 EA_HICP，未被机制使用，故未影响 7/7；但任何序列一旦在 T 处变陈旧都会重演）。
- 与 round-2 #8 的关系：同源于“`_load_macro` 整条剔除陈旧序列”；#8 指 readiness 与特征层阈值不一致，本条指同一 build 的 `slice_as_of` 时点不一致，是两个不同后果。
- 收尾验证（16:25）：`_load_macro` 改为保留完整历史、只把陈旧序列记录进 `stale_macro`；复测同对比 `onlyA=0 / onlyB=0`。**已修复并复测通过。**

**NEW-4｜加密 24/7 无 partial-bar 保护（收尾版已修复）**
- 位置：`_drop_incomplete_bars` 显式跳过 `asset_class in ("crypto","fx")`。
- 证据：合成库最后一天 BTC bar `fetched_at=同日 10:00Z` → 该 bar 被保留，`return/1d` 正常输出；US 同日 10:00Z bar 则被丢弃。
- 影响：实盘 10:00 UTC 扫描把仍在形成的 UTC 日 bar 当作完整日线，P2-B 之后还会直接进入原生 return/z/anomaly；同一份报告里 crypto 是“盘中”，equity 是“昨收”，且无披露。收尾版 readiness 已把“同日抓取的 crypto bar”判为未完成（`WORLD.last_date=11-12`），而特征层仍使用它（crypto return 到 11-13），**两个层的完成定义现在正相反**。
- 收尾验证（16:27）：`_crypto_raw_native` 与 bday 面板都按 `bar_is_complete` 过滤，crypto 规则为“同日抓取=未完成、次日抓取=完成”；新增测试 `test_crypto_same_day_bar_is_not_a_completed_daily_bar` 由红转绿，真实库 `CR_BTC return/1d` 最后日期 2026-11-12。**已修复并复测通过。**

**NEW-5｜`min_coverage=0` 静默关闭全部 critical 合同**
- 位置：`readiness.py` 的 `if min_coverage > 0:` 块。
- 证据：`min_coverage=0.0` 时删除 UST → `ok=True`；删除 US_CPI+US_POLICY_RATE → `ok=True`。而参数名只表达“覆盖率阈值”，不表达“关闭关键数据合同”。
- 影响：生产/研究调用方为放宽覆盖率而传 0.0 时，核心数据缺失不再阻塞；`run_scan(readiness_min_coverage=0.0)` 即处于此状态。
- 建议：显式 `mode="prod"/"lab"` 参数，critical 合同不受覆盖率旋钮控制。

### P3 — 低风险/口径问题

**NEW-6｜历史 as_of 过阻（2015-02-15 前）**
- 证据：`as_of=2015-01-30/2015-02-10` → `critical=核心宏观数据缺失：US_CPI、US_POLICY_RATE`；`as_of=2015-02-20` 通过。DB 的月度宏观起点是 2015-01-01，发布滞后 45 天，之前不存在“已发布观测”。
- 影响：`goe scan --as-of` 在 2015-02-15 前被合同永久阻塞；这不是“数据缺失”，而是 DB 回填起点 + 发布时点语义，却以“缺失，拒绝发布”报出；同时早期 CN/HK 覆盖 warning 使历史扫描永久 degraded。
- 建议：对“as_of 早于序列首个可用观测”区分 `not_yet_available` 与 `missing`。

**NEW-7｜crypto 与 equity 的特征口径混用但无标签**
- `CR_BTC return/1m` = 30 个自然日（-15.6114%），自身 `rel_strength_vs_benchmark/1m` = 21 个 bday（-13.756%，日期 11-12）——同一 `window="1m"` 键、同一标的，两个窗口/日期；
- `ann_vol` crypto 用 `sqrt(365)`、equity 用 `sqrt(252)`；`drawdown_252d` crypto 是 252 个自然日（≈8.3 个月），报告 1.1 表头写“距1年高点”；
- crypto 未生成 `momentum_12_1`（feature parity 缺口）。
- 影响：报告/证据文本层面不可直接比较；z 与分位是各自内部自洽，故未影响异常判定本身。
- 建议：feature 增加 `calendar="native|bday"` 或 `window_days` 字段；报告表加口径注；crypto `drawdown_252d` 改 365 或改标签。

**NEW-8｜`feature_version` 未随方法变更升级**
- `FEATURE_VERSION = "v1"` 未变；本轮新增 crypto 原生特征、拆股调整方向、DST 收盘时刻、crypto 窗口定义。scan_runs/report/export 仍标 v1。
- 影响：前后扫描的 `feature_version` 相同但特征定义不同，复现/对比声明失真。
- 建议：升 `v2` 并在 scan meta 保留方法哈希。

**NEW-9｜readiness 的 last price / coverage 与特征层不一致且无披露（收尾版本已修复）**
- 冻结快照：readiness `last_price_date=2026-11-13`、`coverage=100%`；特征层同日 15:05Z 抓取的 US/EU bar 被丢，US/EU 特征最后日期 2026-11-12，报告未披露这一天差异。
- 收尾版本（16:21）：readiness 改为基于 `FeatureBuilder.bar_is_complete` 统计，实测 `regions.US.last_date=2026-11-12`、`EA=11-12`、`CN/JP=11-13`，已与特征层对齐；聚合 `last_price_date` 仍为 11-13（CN/JP 确实有完整 bar），属正确口径。未发现新回归。

**NEW-11｜crypto 清洗 issue 重复记录**
- 收尾版本 `build()` 先对 bday 面板 `clean_price_panel(px)`（含 crypto），再对原生 crypto 面板 `clean_price_panel(cdf)`，两处都 append 到 `self.price_issues`；同一 CR_BTC 零价坏点在 `meta["price_data_issues"]` 中出现 2 条完全相同的 `nonpositive_price`。
- 影响：报告“本次处理 N 项”虚高、同一坏点被重复披露；不影响特征值。
- 建议：crypto 原生清洗的 issues 去重（按 instrument+kind+dates），或只保留原生清洗结果/只保留 bday 清洗结果中的一份。

**NEW-10｜FX 的 24/7 完成语义与 crypto/equity 不一致**
- 位置：`readiness.py` 对所有标的调用 `FeatureBuilder.bar_is_complete(..., asset_class)`；`bar_is_complete` 只对 `crypto` 特判，`fx`（以及 `WORLD` 区域）仍按纽约 16:00 收盘判定；`_drop_incomplete_bars` 则显式跳过 `fx`。
- 证据（最终代码）：`GX_FX_EURUSD` 的 2026-11-13 bar（fetched 15:05Z 同日）`bar_is_complete=False`，readiness `WORLD.last_date=11-12`，而特征层 FX 的 11-13 return 仍可用。crypto 已在 16:25/16:27 修好并与特征层一致。
- 影响：FX 的“最后更新日”被低估一天；当前 7 天窗口下不影响 coverage/critical，但 24/7 资产的完成定义仍不统一。
- 建议：fx 与 crypto 同样按“同日抓取=未完成/次日=完成”处理，或让 `_drop_incomplete_bars` 与 readiness 共用同一 asset_class 策略。

## 四、最重要的新缺陷（一句话）

**本轮最重要的发现是 NEW-1（P2-B 的加密原生特征绕过 `clean_price_panel`：0/坏价可发布 −100% 假冲击并污染 252 日回撤），它已在审计收尾的 16:23 版本被修复并在我的 glitch 用例上复测通过。当前仍开放的最重要新缺陷是 NEW-2 残留：P1-B 虽已补上 2Y/10Y 基准期限，但 UST 只剩 2/13 期限（3M/30Y 等全丢、曲率/3m10y/stock_bond 全消失）仍 `ok=True`、无 warning 发布——核心曲线覆盖率仍可静默退化。**

## 五、已知但本轮仍未修复（不计 NEW）

1. round-2 #7 期货换月：连续合约未展期调整；`near_month_end` 用 `day>=27 or day<=2`，与能源实际换月窗口（约 15–23 日）错位；round-2 已给出 2016-01-21、2026-09-23/10-21 的具体缺口个案，本轮未新增统计证据。
2. round-2 #8 宏观陈旧阈值不一致：readiness 用 availability+60（月频 105 天），FeatureBuilder 用观测+110 天；`JP_CPI` 135 天旧观测被 readiness 当 fresh，特征层剔除。
3. round-2 #13 VIX 分位按 bday 行而非有效观测：特征 0.582028 vs 有效观测 0.576648（Δ0.0054），窗口内 46 个 bday 缺口。
4. round-2 #1 小市场全灭（配置 <3）只 warning；CN 全删仅因配置 23≥3 才 critical。
5. round-2 #5 历史 as_of 跨市场最后 bar 不齐（US/EU/商品早一天）。

## 六、限制

- 只读审计，未运行网络采集；合成库用于故障注入，不代表真实行情。
- 大型全量 build 在 125 标的 × 10 年面板上约 150–280 秒/次；A/B 比较基于同一份冻结快照与同一 DB 快照。
- 报告中的“特征层”数值来自 `FeatureBuilder(...).build()`（当前快照），独立复算仅用 sqlite3+pandas/numpy。
- 工作树在审计期间被并行修改：P1-A/P1-B/P2-B 主矩阵在 16:12 冻结快照上完成；16:21–16:27 的修复（crypto 清洗、crypto 同日 bar、宏观 slice、readiness 完成 bar、UST 基准期限）已在最终哈希 `4d6c1f31…/58cbf13d…` 上逐项复测，全量离线测试 155 passed、exit 0。`opportunities/validation/cli/ingest` 的并行变更不在本报告数据层结论内。
