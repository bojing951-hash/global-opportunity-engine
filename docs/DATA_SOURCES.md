# DATA_SOURCES — 数据来源、口径、时效与缺口

> 配套细目：[`docs/DATA_SOURCE_NOTES.md`](DATA_SOURCE_NOTES.md)（各 provider 实测格式、解析细节、踩坑记录）。
> 机器可读登记表：[`config/sources.yaml`](sources.yaml)；曲线/宏观/仓位定义见 `config/curves.yaml`、
> `config/macro.yaml`、`config/positioning.yaml`。

## 1. 来源总表

| source_id | 名称 | 层级 | 数据 | 覆盖范围（实测） | 发布/时效 | 已知缺口 |
|---|---|---|---|---|---|---|
| `yahoo` | Yahoo Finance chart API | aggregator | 股票指数/ETF/行业/国债 ETF/信用 ETF/外汇/期货/加密/波动率 | 120 标的；2015-01 → 2026-11（部分标的仅 5 年） | 延迟/日终，随交易所 | 期货为前月连续合约，未展期调整；部分交易所无复权价（用原始收盘价，行内记录 NULL） |
| `treasury_us` | US Treasury 日度国债收益率曲线 | official | 1M–30Y 名义收益率 | 13 期限；2014-01 → 2026-11 | 日终 | 1.5M 等新期限忽略；非零息曲线；无 TIPS/盈亏平衡 |
| `mof_japan` | 日本财务省 JGB 收益率 | official | 1Y–40Y | 15 期限；2014-01 → 2026-11 | 日终（工作日） | 无期限结构模型；负利率保留 |
| `ecb` | ECB Data Portal (SDMX) | official | 欧元区 AAA 中央政府曲线 | 11 期限；2014-01 → 2026-11 | 日终 | AAA 曲线非单一发行体；无 BTP/Bund 利差直接序列 |
| `akshare_cn_index` | akshare 转发新浪 A 股指数日线 | aggregator | 上证/深证/沪深300/中证500/中证1000 | 5 指数；2015-01 → 2026-11 | 日终 | 仅指数点位，无复权；端点可能被网络阻断（逐标的失败） |
| `akshare_cn_bond` | akshare 转发 ChinaBond 曲线 | aggregator | 中国国债 2/5/10/30Y + 美国 10Y 交叉校验 | 5 序列；2014-01 → 2026-11 | 日终 | 仅 4 个期限；akshare 内部 HTTP 无法走共享客户端，网络失败会记录为 error note |
| `bls` | BLS 公共 API v1 | official | CPI-U、核心 CPI、失业率、非农 | 4 序列；2015-01 → 2026-10 | 月度，约次月中旬 | v1 配额（25 序列/10 年/日）；实测缺 2025-10 CPI |
| `bis` | BIS statistics API | official | 政策利率（US/EA/JP/CN/UK）、长期 CPI、私人部门信贷 | 10 序列；2015 → 2026-Q1/2026-10 | 月度/季度，滞后 1-2 月 | 信贷为季度、会修订；JP 政策利率序列 2013-05..2016-08 缺失 |
| `eurostat` | Eurostat dissemination API | official | 欧元区 HICP 同比 | 1 序列；2015-01 → 2025-12 | 月度 | 镜像止于 2025-12，系统判定为陈旧 |
| `cftc` | CFTC Commitments of Traders 历史文件 | official | 16 个市场的净持仓 + 未平仓量 | 32 序列；2015-01 → 2026-11-03 | 周度（周二数据，周五发布） | 仅期货；2022 年市场更名（别名已处理）；holiday 报告日顺延 |
| `shiller` | Yale Shiller 数据集 | official | CAPE | 1 序列；2015-01 → 2023-09 | 月度 | 数据集自身滞后；末月为估计值 |
| `cboe`（未启用） | CBOE 历史文件 | exchange | VIX 历史 | 备用 | 日终 | 当前 VIX 通过 Yahoo 获取；保留 provider 备选 |

## 2. 数据模型与可追溯性

- 每条价格：`instrument_id, date, open, high, low, close, adj_close, volume, source_id, fetched_at, run_id`。
- 每条指标：`series_id, date, value, unit, source_id, fetched_at, run_id`。
- `date` 是**观测日期**（数据所属日），不是下载日；`fetched_at` 是 UTC 抓取时间。
- `series_meta` 记录序列名称、单位、频率、提供方、层级与说明。
- `ingest_runs` 记录每次运行的 kind/mode/status/stats/errors；`quality_issues` 记录逐项质量问题。

## 3. 关键序列 ID

| 前缀/示例 | 含义 |
|---|---|
| `US_EQ_SPY` 等 | 交易标的（见 `config/universe.yaml`，共 127 个） |
| `UST:2Y`, `UST:10Y`, `UST:30Y` | 美国国债曲线期限（共 13 个） |
| `JGB:10Y`, `EAC:10Y`, `CN:10Y` | 日本/欧元区/中国曲线期限 |
| `US_CPI`, `US_CORE_CPI`, `US_UNRATE`, `US_PAYROLLS` | 美国宏观（BLS） |
| `US_POLICY_RATE` … `UK_POLICY_RATE` | 政策利率（BIS） |
| `CN_CREDIT`, `US_CREDIT` | 私人部门信贷同比（BIS，季度） |
| `US_CAPE` | Shiller CAPE（月度，陈旧时停用） |
| `POS_GOLD_MM`, `POS_SP500_LEV` … | CFTC 净持仓；`:oi` 后缀为未平仓量 |

## 4. 时间语义（观测日 / 发布日 / 可用日 / 研究 as-of）

| 概念 | 字段/实现 | 示例 |
|---|---|---|
| Observation date | `prices.date` / `indicators.date` | CPI 2026-09 参考期 = 2026-09-01 |
| Ingestion timestamp | `fetched_at`（UTC） | 2026-11-13T13:29:00Z |
| Data available at | 由频率决定的发布滞后：日 0 / 周 4 天 / 月 45 天 / 季 120 天 | CPI 2026-09 可用日 = 2026-10-16 |
| Research as-of | 扫描参数 `--as-of`；默认最后一根**已完成**K线 | 2026-11-13 |

规则：任何 as-of 都不能使用“可用日 > as-of”的数据。异常记录同时保存观测日 `as_of` 与
可用日 `available_date`；筛选/机制触发按可用日 + 频率窗口（日 7d/周 21d/月 75d/季 150d）。
历史回放对每个评估日独立切片，并过滤宏观按可用日（`FeatureSet.slice_as_of`）。

### 时效与发布滞后（回放时强制）

| 频率 | 滞后（日历日） | 用途 |
|---|---|---|
| 日频（价格/曲线） | 0 | 当日数据当日可见（收盘后） |
| 周频（CFTC） | 4 | 周二报告 → 周五发布 |
| 月度（CPI/HICP/政策利率） | 45 | 保守取值，避免抢跑 |
| 季度（信贷） | 120 | BIS 发布滞后 |
| 年度 | 180 | 世界银行等（当前未用于实时判断） |

**陈旧阈值**：日 20 / 周 45 / 月 110 / 季 280 / 年 400 天未更新 → 该序列在当前 as_of 视为不可用，
并写入 `meta.stale_macro_series` 与报告"数据质量"节。

## 5. 质量检查（已实现）

1. 价格非正、重复日期、缺失复权价 → 行级过滤 / 记录
   （缺失复权价时使用原始收盘价并在报告中声明）。
2. 收益率/CPI/信贷量纲校验；BIS `UNIT_MEASURE` 冲突 → `unit_mult_conflict` 记录。
3. 交叉校验：中国国债 provider 同时返回美国 10Y，与 Treasury 官方曲线比对（`CN:US10Y_CHECK`）。
4. 极端值：收益率 0–30%（允许负利率）、单周涨跌幅上限等。
5. CFTC 市场更名别名（2022 年前后名称不同）已在适配器中映射并记录 `market_alias`。
6. 抓取失败：单标的进 `errors`；整个 provider 0 行 → 运行失败并抛出 `IngestError`。

## 6. 明确的数据缺口（不在系统中假装存在）

| 缺口 | 影响 | 当前替代 |
|---|---|---|
| FRED / 圣路易斯联储（网络超时） | 无 DFII10 实际利率、T10YIE 盈亏平衡、BAML OAS、SLOOS | 名义利率 + TIPS ETF 代理；HYG/IEF 代理信用 |
| 分析师一致预期与盈利修正 | 无法验证"预期差"的盈利维度 | 列为 open_question，交给 investment-agent |
| ETF/共同基金资金流、期权隐含分布 | 仓位与情绪判断不完整 | CFTC 期货持仓 + 价格/波动代理 |
| 行业/指数估值（P/E） | 行业估值异常无法计算 | 仅 S&P 500 CAPE（且当前陈旧） |
| 商品库存、期限结构（EIA/LME/CFTC 分月） | 供需冲击识别有限 | 价格 + 持仓 + 美元/利率 |
| 镍期货、离岸人民币（CNH） | Yahoo 无可靠公开历史 | 已从标的池移除；CNH 机制触发改用 USD/CNY（在岸）代理，见 LIMITATIONS |
| 中国社融、PMI、地产、南向资金 | 中国本地宏观驱动缺失 | BIS 信贷、CPI、国债曲线、CNH |
| 英国/欧元区本地利差（BTP-Bund、Gilt） | 财政风险识别有限 | 收益率水平与曲线斜率 |
| 财报日历 | 事件驱动原型仅覆盖宏观事件 | 官方央行/统计日历 |

## 7. 法律与使用限制

- 所有来源均为公开可访问接口；不绕过付费墙，不使用未授权数据。
- Yahoo Finance 数据为交易所数据的再分发，仅用于个人研究/教育；不得用于商业再分发。
- ECB/BIS/Eurostat/BLS/Treasury/MOF/CFTC/Shiller 均要求署名；引用时请标注来源。
- 本项目不构成投资建议；数据可能存在延迟、错误或口径变化，使用前应独立核验。
