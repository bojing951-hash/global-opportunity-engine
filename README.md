# Global Investment Opportunity Discovery Engine

> 上游「投资机会发现」系统：持续监测全球跨资产市场 → 识别异常 → 评估宏观传导 → 生成可审计的**投资机会研究队列**，交给已有的 `investment-agent` 做深度研究。
>
> 本系统负责「接下来最值得研究什么」，不负责买卖决策，也不替代深度研究。

![pipeline](docs/architecture_overview.txt)

```
全球市场数据 (价格/利率/曲线/宏观/仓位)
        │  goe ingest        权威官方源 + 公开聚合源，逐行记录来源与抓取时间
        ▼
SQLite (data/goe.db) ── prices / indicators / 运行与质量记录
        │  goe scan
        ▼
时点特征 (returns/vol/回撤/曲线/信用代理/仓位/估值/广度/相关性)
        ▼
异常检测 (14 类检测器，稳健 z / 历史分位，全部可复算)
        ▼
宏观传导 (15 条机制假设，滚动相关/领先滞后/条件收益；支持 vs 反对证据)
        ▼
机会候选池 (5 类原型 → 评分 → 去重 → 状态生命周期)
        ▼
exports/pipeline_<date>.json + research_tasks/RT-*.json
        │  goe handoff
        ▼
investment-agent: ia_cli.py research-run --question "..."   ← 已实测跑通
```

## 它解决什么问题

每天面对 100+ 个市场的涨跌，真正稀缺的不是数据，而是**值得投入深度研究的问题**。本系统把「市场发生了什么」压缩成少量结构化机会线索，每一条都包含：

- 发现了什么现象（可追溯到具体的异常行与原始数据）
- 为什么值得关注（发生了什么异常、强度、历史分位）
- 可能的经济金融机制（机制库中的链条 + 统计检验的支持/反对证据）
- 哪些资产可能受影响
- 支持证据与反对证据（明确区分相关性与因果假设）
- 潜在催化、仍需回答的研究问题、初步假设的失效条件

并用透明的评分排序（研究优先级，不是预期收益）。

## 快速开始

```bash
cd global-opportunity-engine
make setup                     # uv 创建 .venv (Python 3.12) 并安装依赖
make doctor                    # 环境/配置/数据/依赖体检

make ingest                    # 首次：回填 ~10 年价格 + 全部指标序列（约 5-10 分钟）
make scan                      # 完整管线：检测 → 传导 → 机会 → 报告 → 交接文件
open reports/report_$(date +%F).md
open exports/pipeline_$(date +%F).json

make web                       # 只读仪表盘 http://127.0.0.1:8765
```

日常增量更新：

```bash
.venv/bin/python -m goe.cli scan            # 默认增量抓取 + 扫描
```

只重算不抓取（例如数据已更新后）：

```bash
.venv/bin/python -m goe.cli scan --no-ingest --as-of 2026-11-12
```

## 主要命令

| 命令 | 作用 |
|---|---|
| `goe doctor` | 环境、配置、数据覆盖、各数据源可用性、investment-agent 连通性 |
| `goe ingest --mode backfill\|incremental` | 价格与指标抓取；`--prices-only` / `--indicators-only` |
| `goe scan [--as-of DATE] [--no-ingest]` | 完整扫描；输出报告与机会管线 |
| `goe opp list --status deep_research` | 按状态/评分查看候选池 |
| `goe opp show OPP-0001` | 单条机会的完整档案与事件历史 |
| `goe opp status OPP-0001 --set watch --reason "..."` | 人工更新状态（写入事件日志） |
| `goe handoff --ia-path ~/investment-agent-dev --limit 3` | 生成并（可选）运行 investment-agent 研究任务 |
| `goe replay --cases` | 7 个历史情景的时点回放验证（无前视） |
| `goe replay --start 2024-01-01 --step 21` | 3 年时点回放，检查稳定性 |
| `goe web` | 本地只读仪表盘 |

## 一次真实运行的输出

见 [`docs/examples/report_2026-11-13.md`](docs/examples/report_2026-11-13.md)（示例输出目录 `docs/examples/`，含机会管线 JSON 与研究任务 JSON）。核心结构：

```
OPP-0001  0.67  watch  US  event_revision
   美国 政策变化后的重定价：Invesco QQQ（Nasdaq 100）（US_POLICY_RATE hike）
OPP-0002  0.66  watch  US  regime_repricing
   VIX 期限结构与波动状态：SPDR S&P 500 ETF 可能处于重定价窗口
```

每条机会包含 `discovery / mechanism / evidence_for / evidence_against / catalysts /
open_questions / invalidation / data_quality / score_breakdown`，均为结构化 JSON（见
`exports/HANDOFF_SCHEMA.json`），可直接被其他程序消费。

## 数据来源与真实性

| 类别 | 来源 | 层级 | 时效 |
|---|---|---|---|
| 全球股票/ETF/期货/汇率/加密/波动率 | Yahoo Finance chart API | 聚合层 | 延迟/日终 |
| 美国国债收益率曲线 | US Treasury 官方 CSV | 官方 | 日终 |
| 日本国债收益率曲线 | 日本财务省 (MOF) | 官方 | 日终 |
| 欧元区 AAA 收益率曲线 | ECB Data Portal (SDMX) | 官方 | 日终 |
| 中国国债收益率 | akshare 转发的 ChinaBond 曲线 | 聚合层 | 日终 |
| 美国 CPI/核心 CPI/失业率/非农 | BLS 官方 API v1 | 官方 | 月度（发布滞后 45 天，回放时强制） |
| 政策利率/长期 CPI/私人部门信贷 | BIS statistics API | 官方 | 月度/季度 |
| 欧元区 HICP | Eurostat API | 官方 | 月度 |
| CFTC 持仓（16 个市场） | CFTC 官方历史文件 | 官方 | 周度（周二数据，周五发布，+4 天滞后） |
| Shiller CAPE | Yale 学术数据集 | 官方 | 月度（该数据集自身滞后） |
| VIX 历史 | Yahoo（CBOE 数据） | 聚合层 | 日终 |

- **不编造、不插值、不填充**：每个观测都带 `source_id` 与 `fetched_at`；缺失就是缺失。
- 每个数据源的授权说明、已知缺口记录在 [`config/sources.yaml`](config/sources.yaml) 与
  [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md)。
- 数据质量检查（陈旧、缺口、量纲冲突、交叉校验）写入 `quality_issues` 表，报告中展示。
- 明确区分 **实时/延迟行情、历史数据、示例数据**；本仓库不包含任何模拟行情冒充真实数据。

## 机会发现逻辑（简要）

五类原型（`goe/opportunities.py`）：

1. **价格-基本面背离** `price_fundamental_divergence`：价格显著下跌，但信用/利率/估值/美元等标准驱动
   并不支持同等程度的恶化（若宏观驱动已能解释下跌，则该候选被明确排除，而不是硬凑）。
2. **预期过度** `expectation_overshoot`：CFTC 仓位处于 5 年极值，同时价格朝拥挤方向延伸（或反向导致浮亏/逼空）。
3. **机制重定价** `regime_repricing`：机制库中的传导链被异常激活，且受影响资产出现异常或机制置信度足够高。
4. **事件修正** `event_revision`：在已核验的官方事件日历临近时出现异常（日历为空时不生成）。
5. **相对价值** `relative_value`：同一资产类别/地区的横截面相对强弱处于 3 年极值且方向相反。

评分（`config/scoring.yaml`，权重合计 1.0）衡量**研究价值**而非预期收益：
异常强度 0.22、经济影响 0.18、预期差 0.20、重定价空间 0.12、催化 0.10、时间窗口 0.06、
流动性与风险 0.06、证据质量 0.06。阈值：`deep_research ≥ 0.68`、`watch ≥ 0.52`、
`low_priority ≥ 0.38`，低于则 `excluded`；证据不足或数据质量不达标时硬性排除。

去重：机会指纹 = `hash(原型, 主要标的集合, 机制)`；同一现象每天重复出现只更新既有记录，
不会无限生成重复项。跨"包装"（期货/ETF/指数）用 `config/themes.yaml` 归并。

状态生命周期：`new → watch → deep_research`，以及 `low_priority / excluded / expired / invalidated`；
每次状态变化写入 `opportunity_events`，失效条件（`invalidation_checks`）自动评估。

## 与 investment-agent 的集成（已实测）

```bash
.venv/bin/python -m goe.cli handoff --ia-path ~/investment-agent-dev --limit 1
```

实测结果（2026-11-13）：

```
OPP-0001: ok rc=0 elapsed=7.32  out=exports/ia_runs/OPP-0001
```

`ia_cli.py research-run` 读取引擎生成的研究问题，输出四层研究报告
（`report.md` / `report.json`）。集成方式为**适配器 + 标准 JSON 交接文件**，不修改
investment-agent 的任何代码：详见 [`docs/INTEGRATION_INVESTMENT_AGENT.md`](docs/INTEGRATION_INVESTMENT_AGENT.md)。

## 验证与测试

```bash
make test          # 离线测试（不联网）
make test-network  # 数据源联网测试
make cases         # 7 个历史情景的时点回放（无前视）
make replay        # 3 年逐时点回放
```

- 单元/集成测试覆盖：97 项离线测试（DB 幂等、特征、异常、机制、评分、五类原型、去重、生命周期、导出、报告、端到端）+ 9 项联网数据源测试。
- 历史案例检验的是**检测能力**（是否在事件窗口内识别出异常并生成值得研究的线索），
  **不是投资收益**；详见 [`docs/VALIDATION.md`](docs/VALIDATION.md) 与 `reports/validation_cases_*.md`。
- 无前视：特征构建只使用 `as_of` 之前的数据；宏观序列按发布滞后平移；`goe.validation.no_lookahead_diff`
  可对任意两个 as-of 日期的共同历史逐值对比。

## 仓库结构

```
config/         universe / curves / macro / positioning / mechanisms / scoring / thresholds / themes / events / cases
goe/            引擎代码
  sources/      10 个数据源适配器 + 共享 HTTP 客户端（限速/重试/证书）
  features.py   时点特征层
  anomalies.py  14 类异常检测器
  transmission/ 传导机制评估（相关/领先滞后/条件收益）
  opportunities.py  机会生成、评分、去重、生命周期
  pipeline.py   端到端管线
  validation.py 历史回放与案例验证
  reports.py    Markdown/JSON 报告
  integration/  investment-agent 适配器与导出
  web/          只读仪表盘
tests/          离线测试 + 联网测试
docs/           架构、数据源、评分、验证、集成、限制
reports/        运行生成的报告（gitignore，示例见 docs/examples）
exports/        交接 JSON（gitignore，示例见 docs/examples）
```

## 已知限制（摘要，完整见 docs/LIMITATIONS.md）

- Yahoo 为聚合层，不是交易所原始行情；期货为前月连续合约，未做展期调整。
- 信用利差用 HYG/IEF 相对表现代理，不是 OAS；美国以外没有本地信用利差数据。
- 分析师盈利预期、ETF 资金流、期权隐含分布、行业级估值（P/E）未接入——相关结论必须在深度研究中补齐。
- Shiller CAPE 数据集仅更新到 2023-09、Eurostat 镜像止于 2025-12：系统会判定为「陈旧」并停止使用，而不是把旧值当现值。
- 中国宏观为季度/月度代理（BIS 信贷、CPI），缺少社融、PMI、地产等高频数据。
- 事件日历只收录官方可核验日期；未核验的一律不写入。
- 回放验证衡量检测能力，不等于可交易收益；评分是研究优先级，不是预期收益。

## 仓库

- GitHub（private）：https://github.com/bojing951-hash/global-opportunity-engine
- 提交：`1a7a5f5` ｜ 分支 `main`

## 环境

- macOS（Apple Silicon 实测）/ Linux 均可；Python ≥ 3.10（开发环境 3.12）
- 测试：121 离线 + 9 联网（见 TEST_RESULTS.md）
- 2026-11-14 独立审计与修复：见 `audit/ISSUE_LEDGER.md`、`audit/FIX_LOG.md`
- 磁盘占用：SQLite 约 120 MB（10 年全量）；无 GPU、无付费 API、无外部数据库
- 不连接任何实盘交易账户，不下单，不提供投资建议
