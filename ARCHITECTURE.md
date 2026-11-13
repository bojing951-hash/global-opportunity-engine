# ARCHITECTURE — Global Investment Opportunity Discovery Engine

## 1. 总览

```
                       ┌─────────────────────────────────────────────┐
                       │ config/  universe, curves, macro,           │
                       │ positioning, mechanisms, scoring,           │
                       │ thresholds, themes, events, cases           │
                       └───────────────┬─────────────────────────────┘
                                       │ 版本化、可审计
┌──────────────┐   fetch   ┌───────────▼──────────┐   upsert   ┌──────────────────┐
│ 10 providers │ ────────► │  Ingestor            │ ─────────► │ SQLite data/goe.db│
│ (官方+聚合)   │  重试/限速 │  provenance/quality  │            │ prices            │
└──────────────┘           └──────────────────────┘            │ indicators        │
                                                                │ ingest_runs       │
                                                                │ quality_issues    │
                                                                └─────────┬────────┘
                                                                          │ load (as-of 截断)
                                                                ┌─────────▼─────────┐
                                                                │ FeatureBuilder     │
                                                                │ 价格/波动/回撤/趋势 │
                                                                │ 曲线/信用代理/仓位  │
                                                                │ 宏观(发布滞后)/估值 │
                                                                └─────┬─────────┬───┘
                                                                      │         │
                                                        ┌─────────────▼──┐  ┌───▼─────────────┐
                                                        │ 14 detectors   │  │ FeatureSet cache │
                                                        │ robust z/pctile│  └─────────────────┘
                                                        └───────┬────────┘
                                                                │ anomalies
                                                ┌───────────────▼────────────────┐
                                                │ MechanismEvaluator (15 机制)    │
                                                │ corr / lead-lag / conditional  │
                                                │ for / against / confidence     │
                                                └───────────────┬────────────────┘
                                                                │ transmissions
                                                ┌───────────────▼────────────────┐
                                                │ OpportunityEngine               │
                                                │ 5 archetypes → score → dedupe  │
                                                │ → lifecycle → persist           │
                                                └───────┬───────────────┬─────────┘
                                                        │               │
                                    ┌───────────────────▼──┐     ┌──────▼────────────────┐
                                    │ reports/ (MD + JSON) │     │ exports/ (handoff)    │
                                    │ web/ (read-only)     │     │ → investment-agent    │
                                    └──────────────────────┘     └───────────────────────┘
```

## 2. 模块职责

| 模块 | 职责 | 关键约束 |
|---|---|---|
| `goe/config.py` | 加载并校验 YAML 配置 | 未知资产类别/地区/流动性直接报错；缺失 benchmark 报错 |
| `goe/sources/base.py` | Provider 协议、规范帧、归一化 | 禁止插值；逐 symbol 错误进 errors 而不中断整批 |
| `goe/sources/http.py` | 共享 HTTP 会话 | 超时、指数退避、按 host 限速、强制 TLS 校验（certifi） |
| `goe/sources/{treasury,mof_japan,ecb,bls,bis,eurostat,cftc,akshare_cn_bond,shiller}.py` | 官方/聚合指标源 | 原始值入库；单位与来源记录；缓存原始下载 |
| `goe/sources/yahoo.py` | 价格适配器（125 标的） | 批量下载 + 单标的回退；429 退避；保留复权/未复权两列 |
| `goe/ingest.py` | 编排抓取、增量窗口、运行记录、失败语义 | 0 行抓取 → 抛错并记 failed；部分失败 → partial |
| `goe/db.py` | SQLite schema 与 Store API | 幂等 upsert；列存 provenance；指纹唯一索引 |
| `goe/features.py` | 时点特征层 | 只使用 `date <= as_of`；宏观发布滞后；陈旧序列剔除 |
| `goe/anomalies.py` | 14 类检测器 + 限流/去重 | 阈值来自 config；证据含公式与原值；单检测器异常不影响整体 |
| `config/mechanisms.yaml` | 15 条传导机制假设 | 触发变量、受影响资产、可执行检验、条件、反证 |
| `goe/transmission/evaluator.py` | 机制激活与证据评估 | 相关性≠因果；失败检验进入反对证据；置信度规则透明 |
| `goe/opportunities.py` | 机会生成/评分/去重/生命周期 | 指纹稳定；主题归并；硬门槛；失效条件可自动评估 |
| `goe/pipeline.py` | 端到端编排 | 每阶段幂等；scan_runs 记录 config/data 哈希；异常回滚状态 |
| `goe/reports.py` | Markdown/JSON 报告 | 报告围绕"为什么进入候选池"；数据质量节 |
| `goe/events.py` | 事件日历 | 空日历合法；只收已核验日期 |
| `goe/validation.py` | 时点回放/案例验证/前视检查 | 不写入正式机会表 |
| `goe/integration/` | 导出与 investment-agent 适配器 | 不修改对方仓库；只通过 CLI 与 JSON |
| `goe/web/app.py` | 只读仪表盘 | stdlib http.server；无写操作；JSON API 与页面同源 |

## 3. 数据模型

```
sources            source_id, tier(official/exchange/aggregator/proxy), license_note, known_gaps
instruments        id, asset_class, region, currency, source, symbol, importance, liquidity, benchmark
prices             (instrument_id, date) PK, OHLC, adj_close, volume, source_id, fetched_at, run_id
indicators         (series_id, date) PK, value, unit, source_id, fetched_at, run_id
series_meta        系列单位/频率/提供方/等级
ingest_runs        run_id, kind, mode, status, stats_json, errors_json
quality_issues     target, code, severity, detail
anomalies          (anomaly_id) PK, as_of, detector, family, entity, direction, score,
                   percentile, window, evidence_json, fingerprint；唯一索引 (fingerprint, as_of)
transmissions      transmission_id, as_of, mechanism_id, triggers, assets, evidence_for/against,
                   conditions, confidence, status
opportunities      opportunity_id, fingerprint UNIQUE, as_of, first_seen, last_seen, archetype,
                   status, score, score_json, discovery/mechanism/evidence/catalysts/
                   open_questions/invalidation/data_quality JSON, lifecycle_json
opportunity_events 状态变更审计（created/refreshed/status_change/ia_research_run）
scan_runs          scan_id, as_of, status, config_hash, data_hash, stats_json
research_tasks     task_id, opportunity_id, payload_json, export_path, status
```

设计取舍：

- **单文件 SQLite**：单用户研究系统、十万级行、零运维；WAL 支持读写并发；备份=复制文件。
- **JSON 列**：机会档案是半结构化文档，JSON 保留完整证据链，避免过度规范化导致字段爆炸；
  可查询字段（状态、分数、原型、市场）单独建列并建索引。
- **Parquet 导出**（可选）：特征快照可通过 `FeatureSet.save()` 落 Parquet 供外部分析。

## 4. 时点与无前视

1. 价格：`load_prices(end=as_of)`，之后所有滚动统计都是**尾随**窗口。
2. 宏观：每个观测按频率施加保守发布滞后（月度 45 天、季度 120 天、周度 4 天），
   观测日期保留为原始日期；只有 `release_date <= as_of` 的观测可见。
3. CFTC：周二报告 + 4 天（周五发布）后才可见。
4. 陈旧数据：超过 `STALE_AFTER_DAYS` 未更新的序列被判为不可用（写入 `meta.stale_macro_series`），
   不会被 forward-fill 成"当前值"。
5. `no_lookahead_diff(store, date_a, date_b)`：在两个 as-of 构建中比较共同历史，
   最大绝对差 > 1e-5 即判定泄漏（测试与审计使用）。

## 5. 异常检测

- 统一分数公式：`score = clip((|measure| - min) / (cap - min), 0, 1)`，measure 为稳健 z
  或尾随分位；阈值与上限均在 `config/thresholds.yaml`。
- 检测器：`price_return_shock`, `vol_regime_shift`, `drawdown_extreme`, `trend_break`,
  `relative_strength_extreme`, `breadth_extreme`, `valuation_extreme`, `curve_change`,
  `credit_stress`, `cross_asset_divergence`, `macro_shift`, `positioning_extreme`,
  `risk_appetite_shift`, `policy_rate_change`。
- 限流：每日期每家族上限、每实体上限、跨日去重（同 detector+entity+direction 在 5 天内只保留一次）。
- 证据 JSON 包含：度量名、观测值、阈值、公式、原始收益/分位、来源与等级、资产类别/地区。
- **异常不是错误定价**：异常只是"不寻常"的描述性事实，是否构成机会由机会层决定。

## 6. 传导机制

机制 YAML 结构：

```yaml
M02_GOLD_REAL_YIELD:
  title: ...
  thesis: ...
  causal_status: hypothesis
  mechanism_chain: [实际利率, 持有成本, 投资需求, 金价]
  triggers: [{series: UST:10Y, direction: down}]
  affected_assets: [{id: CM_MET_GC, role: primary, expected_direction: up, horizon: 1-3m}]
  evidence_tests:
    - {type: corr, a: UST:10Y, b: CM_MET_GC, window: 250, expected_sign: -1, min_abs: 0.15}
    - {type: conditional_return, condition_series: US_CPI, operator: ">", threshold: 3.0,
       target: CM_MET_GC, horizon_days: 63, expected_sign: 1}
  conditions: [...]
  falsifiers: [...]
```

评估器：

1. **激活**：触发序列在最近 7 天窗口内存在方向匹配的异常（无异常不激活）。
2. **证据**：滚动相关（符号、幅度、近端符号一致率）、领先滞后互相关、条件收益
   （描述性：样本量、均值、命中率，明确非预测）。
3. **置信度**：`0.25 + 0.18×通过数(≤3) + 0.10(相关通过) + 0.08(条件收益通过)
   - 0.15×矛盾项(≤2) - 0.05×数据不足项`，截断 [0.05, 0.85]。
4. **状态**：`supported / mixed / weak / unsupported / insufficient_data`。
5. 相关性≠因果：每行 `identification` 字段显式声明，条件与反证随档案交付。

## 7. 机会生成与评分

见 README「机会发现逻辑」与 `config/scoring.yaml`。关键实现细节：

- 生成后先按 `fingerprint`（原型+主要标的+机制）去重，再按主题（`config/themes.yaml`）
  归并期货/ETF/指数包装，再按原型与地区上限截断，最后排序取前 N。
- 评分前先做**硬门槛**：证据项 < 2 → excluded；数据质量 < 0.30 → excluded。
- 状态阈值：`deep_research ≥ 0.68`、`watch ≥ 0.52`、`low_priority ≥ 0.38`。
- 人工状态（CLI）优先于自动评分，状态变更写 `opportunity_events`。
- 自动失效：`invalidation_checks` 在后续扫描中评估（如相对基准再跌 8%、信用代理 z < -2），
  触发则 `invalidated`；45 天未被重新检测则 `expired`。

## 8. 失败语义与恢复

| 场景 | 行为 |
|---|---|
| 单个 symbol 抓取失败 | 记录 errors + quality issue；其余继续 |
| 整个 provider 返回 0 行 | `IngestError`；运行状态 failed；不写空库 |
| 部分 provider 失败 | 运行状态 partial；报告展示问题 |
| 检测器抛异常 | 该检测器跳过并记 errors；其他检测器继续 |
| 机制检验异常 | 该检验记为失败（预算不足/错误），机制仍可被评估 |
| 管线中途异常 | `scan_runs.status=failed` + error；特征与机会表不被部分写入（单事务边界） |
| 进程中断 | 数据已落 SQLite；下次运行从 `MAX(date)` 增量继续；状态记录在 `PROJECT_STATE.md` |

## 9. 运行与调度

```bash
scripts/run_daily.sh          # 增量抓取 + 扫描 + 报告，日志写入 logs/
scripts/install_schedule.sh   # macOS launchd（每日 07:30 HKT）或 cron 模板
goe doctor                    # 运行前体检
```

调度器只负责定时调用同一命令；系统本身不假设后台常驻，也不虚构 24 小时无人值守能力。
状态恢复依赖 SQLite + `PROJECT_STATE.md` + `scan_runs`/`ingest_runs` 记录，而不是对话历史。

## 10. 扩展点

| 想增加 | 改哪里 | 注意 |
|---|---|---|
| 新标的 | `config/universe.yaml`（+ `themes.yaml`） | 先跑 `goe doctor` 校验 id/region/liquidity |
| 新宏观/曲线 | `config/macro.yaml` / `curves.yaml` + provider | 必须实现 `fetch_indicators` 并加离线解析测试 |
| 新异常类型 | `goe/anomalies.py` 新增 `Detector` 子类，加入 `DETECTORS` | 阈值进 `thresholds.yaml`；证据 JSON 必须含公式 |
| 新机制 | `config/mechanisms.yaml` | 触发 id 必须存在；至少 1 个 corr 检验；写反证条件 |
| 新机会原型 | `goe/opportunities.py` | 同步更新 scoring 的 horizon/文档与测试 |
| 新评分维度 | `config/scoring.yaml` + `_score()` | 权重和为 1；需说明理由并重跑案例验证 |
| 新数据源 | `goe/sources/<name>.py` + `registry.py` + `sources.yaml` | 只读公开源；禁止绕过付费墙 |
