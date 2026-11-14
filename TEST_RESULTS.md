# TEST_RESULTS — 测试与验证结果

> 环境：macOS 15.6.1 arm64 / Python 3.12.13 (uv venv) / 2026-11-13
> 运行方式：仓库根目录，`.venv/bin/python -m pytest ...`

## 1. 离线测试套件（不联网）

```bash
.venv/bin/python -m pytest tests -m "not network" -p no:warnings -q
```

| 指标 | 结果 |
|---|---|
| 通过 | **174** |
| 失败 | 0 |
| 跳过/取消 | 9（标记为 `network` 的联网测试） |
| 耗时 | ~75s |
| 退出码 | 0 |

覆盖模块（`tests/`）：

| 文件 | 测试数 | 覆盖内容 |
|---|---:|---|
| `test_sources_indicators.py` | 20 | 9 个指标 provider 的离线解析（Small fixtures：Treasury/MOF/ECB/BLS/BIS/Eurostat/CFTC/akshare/Shiller）+ 格式/日期/单位 |
| `test_db.py` | 7 | schema 幂等、价格 upsert 幂等与 provenance 刷新、异常唯一索引、机会指纹唯一、状态事件与 lifecycle、OPP 编号递增、scan 记录 |
| `test_features.py` | 11 | 无前视（as_of 对比）、收益/波动/回撤手算、稳健 z 精确公式、曲线斜率、宏观发布滞后、陈旧序列剔除、`point_in_time=False` |
| `test_anomalies.py` | 6 | 阈值边界（2.5 触发 / 1.9 不触发）、方向、分数公式、家族与实体限流、跨日去重（保留最高分）、确定性 ID |
| `test_transmission.py` | 23 | 激活需实体+方向匹配、相关检验符号、交易日窗口换算、条件收益样本不足、失败检验进入反对证据、方向映射 |
| `test_scoring.py` | 7 | 各分量 ∈ [0,1]、权重和 = 1.0、阈值映射、两道硬门槛、评分确定性 |
| `test_opportunities.py` | 6 | 指纹稳定性、重复持久化只更新、主题去重、过期/新鲜、失效条件触发 |
| `test_exporter.py` | 4 | 交接 schema 字段、研究问题自包含、四类导出文件、队列优先级、中文 UTF-8 |
| `test_pipeline_e2e.py` | 2 | 端到端扫描（报告/JSON/导出）、重复扫描不重复建机会、scan 哈希 |
| `test_reports.py` | 3 | Markdown 章节与免责声明、市场快照列、曲线快照 |
| `test_archetypes.py` | 4 | 五类原型的最小触发：相对价值、预期过度（拥挤多头+上涨）、事件修正（已核验/未核验） |
| `test_data_integrity.py` | 11 | CPI 同比按日历月对齐（缺失月）、ETF 拆股调整 vs 指数毛刺隔离、条件收益发布滞后、共线检验不抬升置信度 |

测试暴露并修复的 3 个真实缺陷（已保留为回归测试）：

1. `robust_z` 的 MAD 不是在窗口内计算（rolling median of deviations 的错误实现）→ 已改为窗口内中位数绝对偏差。
2. 异常跨日去重保留"首次"而非"最高分"→ 已改为保留同一事件段内最高分。
3. 传导机制 `corr_test` 把 `window=250`（交易日）错误换算成 12 天 → 已按输入频率正确换算（日/周/月/季）。

## 2. 联网测试（数据源）

```bash
.venv/bin/python -m pytest tests -m network -q -p no:warnings
```

| 指标 | 结果 |
|---|---|
| 通过 | **9** |
| 失败 | 0 |
| 覆盖 | 每个指标 provider 至少 1 个真实端点请求 + 解析结果非空/日期有序/值域合理 |

## 3. 端到端运行（真实数据）

见 `PROJECT_STATE.md` §6 与仓库内 `reports/`（示例拷贝在 `docs/examples/`）：

- `goe ingest --mode backfill`：价格 358,310 行 / 125 标的；指标 159,508 行 / 92 序列；失败 0。
- 审计后最终扫描：异常 1,506；机制 5（2 mixed / 3 unsupported，p 值 + BH-FDR）；机会 11（2 watch / 3 low_priority / 2 invalidated / 4 excluded / 0 deep_research）。
- `goe handoff --ia-path ~/investment-agent-dev --limit 1`：investment-agent 进程 rc=0，但 S8 接地问答返回
  `out_of_scope`；A 记录 `refused` / `not_completed:refused`，CLI exit 2，**不把 rc=0 当研究成功**。
  这与“B 成功完成研究”是不同状态，验收中单列为未达成。

## 4. 历史验证

```bash
.venv/bin/python -m goe.cli replay --cases          # 7 个预注册情景
.venv/bin/python -m goe.cli replay --start ... --step 21  # 逐时点回放
```

审计后最终结果：**7/7**（逐评估日独立 PIT 切片）；归档 `reports/validation_cases_20261114T092812Z.md` + `audit/VALIDATION_RESULTS.md`。
方法与解读见 `docs/VALIDATION.md`；该验证衡量检测能力，不衡量收益。

## 5. 未覆盖 / 已知测试缺口

| 项 | 状态 | 说明 |
|---|---|---|
| 浏览器端 E2E（Playwright 等） | 未做 | 仪表盘做了 HTTP 冒烟：`/` 返回 200 且包含标题，`/api/health` 返回 `{"ok": true}` |
| CI（GitHub Actions） | 未配置 | 测试可在本地一条命令复现；CI 需要仓库授权后添加 |
| 数据源长时间稳定性 | 未做 | 单次运行验证；限速/重试逻辑有测试，但没有 24h 压力测试 |
| 多用户并发写 | 未做 | 单用户设计；SQLite WAL |
| 付费数据源 | 不适用 | 项目仅用公开源 |
| 收益回测 | 明确不做 | 系统不输出收益预测；历史验证只衡量检测 |

## 6. 复现命令（汇总）

```bash
make setup
make test           # 174 passed (offline)
make test-network   # 9 passed
make cases          # 7 historical episodes
make scan           # full pipeline on current data
```
