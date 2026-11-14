# PROJECT_SPEC — Global Investment Opportunity Discovery Engine

版本：1.0 ｜ 状态：已实现并验证（2026-11-13）｜ 所有者：用户（最高指令原文见 §1）

## 1. 项目目标

在已有的 `investment-agent` 深度研究系统**之上游**，建立一套真正可运行的全球跨资产
投资机会发现系统，解决一个核心问题：

> **在现有 Investment Agent 之前，系统应该知道"接下来最值得研究什么"。**

系统链路：

```
全球金融市场监测 → 异常变化识别 → 宏观传导分析 → 潜在预期差发现
→ 初步机会筛选 → 候选机会池（Opportunity Pipeline）→ investment-agent 深度研究
```

明确边界：

- 本系统负责**发现、筛选、排序、整理研究问题**，输出结构化机会档案。
- 已有 `investment-agent` 负责宏观/中观/微观深度研究、情景分析、定价、赔率与交易决策。
- 本系统**不重写、不替换、不破坏** `investment-agent`；两者通过标准 JSON 与
  `ia_cli.py research-run` 接口对接。
- 本系统**不作出买卖决策、不连接实盘账户、不执行证券交易**。
- 不是"每日全球宏观新闻摘要"，也不是"涨幅榜/跌幅榜"。

## 2. 功能范围（对照用户需求 §5）

| 编号 | 需求 | 实现状态 | 主要实现 |
|---|---|---|---|
| A1 | 全球市场变化监测 | ✅ 已实现 | `goe/ingest.py`, `goe/features.py`, 11 个 source adapters，125 标的/92 指标序列 |
| A2 | 异常现象发现 | ✅ 已实现 | `goe/anomalies.py`（14 检测器，price/cross_asset/valuation/macro/industry/positioning/risk） |
| A3 | 宏观传导机制分析 | ✅ 已实现 | `config/mechanisms.yaml`（15 机制、53 项可执行检验）+ `goe/transmission/evaluator.py` |
| A4 | 潜在投资机会识别 | ✅ 已实现 | `goe/opportunities.py` 五类原型 + 证据/反证/催化/待研究问题/失效条件 |
| A5 | 机会评分与排序 | ✅ 已实现 | `config/scoring.yaml` 八维权重 + 硬门槛 + 历史回放校准记录 |
| — | 时间频率 | ✅ | 日度（价格/曲线）、周度（CFTC）、月度/季度（宏观），回放按发布滞后处理 |
| — | 5 年 / 10 年历史 | ✅ | 价格自 2015；曲线自 2014；宏观 2015 起（部分源自身更短，已记录） |
| — | 时间戳/来源/标识/口径 | ✅ | 每行 `source_id` + `fetched_at`；`date` 为观测日；`series_meta` 记录单位/频率/等级 |
| — | 数据缺失与替代 | ✅ | `quality_issues` 表 + 报告"数据质量"节 + `docs/LIMITATIONS.md`，不虚构 |
| — | 空候选池 | ✅ | 无候选时输出空池并解释原因（测试覆盖） |

## 3. 市场与资产覆盖

- **地理优先级**：美国、中国大陆（第一）；中国香港、日本、欧元区与英国（第二）；
  其他重要市场（韩国、中国台湾、印度、巴西、加拿大、澳大利亚、墨西哥、瑞士）（第三）。
- **资产类别**：股票指数/行业 ETF、国债与收益率曲线、信用（HY/IG/EM 代理）、外汇、
  贵金属、能源、工业金属、农产品、加密资产、波动率。
- **规模**：125 个交易标的（含 11 个美股行业、12 个中国行业/风格 ETF、15 个期货品种、
  4 条收益率曲线共 43 个期限、16 个 CFTC 持仓市场）。
- 研究资源按全球重要性（`importance`）、流动性、数据可得性分配，不做平均主义。

## 4. 输出物

1. **Opportunity Pipeline**：结构化机会档案（JSON + Markdown），可按日期、国家/地区、
   资产类别、行业、状态检索（CLI `goe opp` 与只读仪表盘）。
2. **每次运行的市场变化摘要**：服务于解释"为什么这些机会进入候选池"，不是新闻汇总。
3. **交接文件**：`exports/pipeline_<date>.json`、`exports/research_tasks/RT-*.json`、
   `exports/research_queue_<date>.json`、`exports/HANDOFF_SCHEMA.json`。
4. **审计信息**：`scan_runs`（config/data 哈希）、`anomalies`（证据 JSON）、
   `transmissions`（支持/反对证据）、`opportunity_events`（状态历史）、`quality_issues`。

## 5. 质量与真实性要求（硬约束）

1. 不编造行情、不模拟数据冒充真实数据、不用未来信息。
2. 数据源失败时明确记录，不静默跳过；单源失败不得导致整条管线写出空库。
3. 同一现象与机会不得无限重复生成（指纹去重 + 主题归并 + 生命周期）。
4. 关键计算有单元测试；核心流程有端到端测试；历史案例有回放验证。
5. 明确区分实时/延迟行情、历史数据、示例/合成数据（测试合成数据仅出现在测试中）。
6. 私有密钥、运行数据库、真实研究输出不进入 Git（`.gitignore`）。

## 6. 验收标准对照（用户 §13）

| # | 验收标准 | 状态 | 证据 |
|---|---|---|---|
| 1 | 可运行的全球主要资产监测系统 | ✅（审计后） | `goe doctor`、`goe ingest`、`reports/` 生成；125 标的、10 年历史 |
| 2 | 接入真实金融数据并记录来源/时效/覆盖 | ✅ | `config/sources.yaml`、`docs/DATA_SOURCES.md`、`quality_issues` |
| 3 | 实现市场异常检测 | ✅ | `goe/anomalies.py`；`tests/test_anomalies.py`；本次扫描 2,935 条（200 天窗口） |
| 4 | 实现宏观变量与跨资产传导分析 | ✅ | `config/mechanisms.yaml`（15）+ `goe/transmission/evaluator.py`；本次 6 条被激活（2 supported） |
| 5 | 实现投资机会候选池 | ✅ | `goe/opportunities.py` + `data/goe.db:opportunities` |
| 6 | 每个候选含证据/原因/机制/待研究问题 | ✅ | `tests/test_export.py`、`reports/report_*.md` |
| 7 | 可解释的机会筛选与排序 | ✅（审计后重构） | 预期差改为可测代理，缺失即不可升为重点研究； `config/scoring.yaml` + `tests/test_scoring.py` |
| 8 | 与 investment-agent 的接口 | ✅ | `goe/integration/`；实测 `research-run` rc=0（见 docs/INTEGRATION_INVESTMENT_AGENT.md） |
| 9 | 历史测试、数据质量、端到端测试 | ✅ | 121 项离线 + 9 项联网测试通过；审计后 7 个历史情景在逐日 PIT 切片下 7/7 通过（见 audit/VALIDATION_RESULTS.md）；`TEST_RESULTS.md`、`docs/VALIDATION.md` |
| 10 | 自动运行、失败恢复、状态持久化 | ✅ | `scripts/run_daily.sh` + launchd 模板；SQLite 持久化 + `PROJECT_STATE.md`；`scan_runs` 失败记录 |
| 11 | 可查看的研究结果与运行说明 | ✅ | `reports/`、`goe web`、README 快速开始 |
| 12 | 完整代码上传 GitHub 并可审计 | ✅ | 私有仓库 https://github.com/bojing951-hash/global-opportunity-engine ，提交 `1a7a5f5`，远程与本地一致 |

## 7. 非目标

- 不做交易执行、组合管理、下单接口。
- 不预测收益率、不承诺"发现即盈利"。
- 不替代 `investment-agent` 的深度研究、估值与赔率判断。
- 不做新闻抓取与情绪打分（当前数据源不含可靠新闻/情绪数据；列为缺口）。
- 不追求覆盖所有市场与所有资产；按全球重要性与数据可靠性取舍。

## 8. 成功判据（研究层面）

系统成功 = 在给定数据条件下，能够：

1. 在历史重要情景中**及时识别**异常（检测能力，非收益）；
2. 生成**可读、可核验、有反证**的研究线索，而不是大量同质化文本；
3. 把线索**准确交付**给已有的深度研究系统，并保留完整审计链。

以上三点分别由 `replay --cases`、机会档案结构与 `handoff` 实测证明。
