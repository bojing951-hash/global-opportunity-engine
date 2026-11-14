# ROUND 2 — 数据完整性 / 定量正确性独立审计（Audit A + B）

- 审计对象：`HEAD 7c5df4c` + 未提交变更；最终快照 `git diff` sha256 `2a26fa1b7984bbd4d849d5b4fa8edc1dad82aceccb28147afce0c386f89aaba6`（2026-11-14 13:50 HKT）。
- 数据：`data/goe.db` 在审计期间被并发重扫（13:31/13:43 曾读到空表）；生产证据取自 `scan-20261114T054347Z-3dee20`（2026-11-14 05:43:47Z，14 个机会，**0 deep_research**，最高分 0.6702）。readiness/特征复算使用 13:32 的 `/tmp` 只读副本，未改仓库数据；唯一写入本文件。
- 方法：源码阅读 + 原始 SQL/pandas 独立复算 + `/tmp` 副本对抗注入 + 定向 pytest（17 passed / 19.6s，`tests/test_pipeline_e2e.py tests/test_readiness_handoff.py`）。

## 1. 判决

- **Audit A（数据完整性）：FAIL（P1）**。事务性 DB 回滚已修好；但 readiness 门禁存在“完全死亡的小市场不可见”和“健康宏观被误判过期”两类新缺陷，detector 异常仍静默吞掉。
- **Audit B（定量正确性）：PASS（核心数值）**。SPY、黄金净仓位/OI、CPI YoY、UST 10y 的独立复算与特征行逐位一致；VIX 5y 分位有 0.0046 的口径残差。FX 未换算、期货换月、宏观条件双滞后属于 P2 方法问题，不是算术错误。
- **事务性：PASS（DB 行）**。在 `write_reports` 失败和 `persist_drafts` 中途失败两种注入下，`anomalies/transmissions/opportunities/opportunity_events` 均为 0，`scan_runs=failed`；但报告/扫描 JSON 文件会残留（P2，见 #9）。

## 2. 关键复现与数字

### 2.1 死亡小市场被全局覆盖率隐藏（P1）

对 `/tmp` 副本（as_of 2026-11-13）删除 **CA/ES/FR/IT/TW/CH 全部 7 个标的价格**：

```
ok=True  coverage=0.944  critical=[]  regions 里这 6 个市场全部消失
```

删除 UK 全部 3 个标的：`ok=True coverage=0.976 regions['UK']=None`。
只把 CA 唯一标的截断到 2024-12-31：`ok=True coverage=0.992 CA={'n_tracked':1,'n_fresh':0,'coverage':0.0,'age_days':682}`。

原因：`readiness.py:123` 对 `ids` 为空直接 `continue`；`readiness.py:134/138` 只在 `len(ids)>=3` 时检查。全局覆盖率分母固定 `n_configured=125`（`readiness.py:68,107`），阈值 80% 可容忍 25 个死亡标的。新门禁声称“complete outage 会被 last-date age 抓到”，对**零行/1–2 标的**市场不成立。

### 2.2 最新扫描绕过 wall-clock 陈旧检查（P1，既有代码，旧审计未记录）

合成库（最后价格 2024-12-31）上：

```
check_data_readiness(as_of=None, today='2026-11-14')
  -> ok=False, critical=['最新价格距今已 683 天（>10）']
run_scan(as_of=None, ingest=False)
  -> status=success, as_of=2024-12-31, scan_runs=success
```

`pipeline.py:73-76` 先把 `as_of` 推成 `MAX(date)`，再传 `as_of_arg or as_of`（非 None），使 `readiness.py:95-100` 的 `if as_of is None` wall-clock 分支在唯一的扫描入口永远不可达。报告会写 2024-12-31，但 API/自动化若只读 `status/opportunities` 会拿到多年陈旧结论。

### 2.3 Detector 异常静默丢失（P1）

monkeypatch `VolRegimeShift.detect` 抛 `RuntimeError` 后跑 `run_scan`：

```
baseline: status=success n_anomalies=99, vol_regime_shift=21
broken  : status=success n_anomalies=79, vol_regime_shift=None
scan_runs.stats_json / report 均不含 "detector exploded"；stats['anomalies'] 只有 n/by_family/by_detector/top
```

`anomalies.py:848-857` 捕获后写入 `out.attrs['errors']`；`pipeline.py:98` 只调用 `summarize`（`anomalies.py:906-914`，不含 errors），attrs 在持久化前丢失。一个坏 detector 与“今天没有异常”不可区分。

### 2.4 宏观新鲜度把“未到发布日”误判为“停止更新”（P1，NEW）

当前生产扫描 `scan-20261114T054347Z-3dee20`：

```
readiness.degraded=True, fresh_macro_series=5/16
warnings=['宏观序列新鲜度不足：仅 5/16 条…', '关键宏观序列过期：US_CPI, US_CORE_CPI, US_UNRATE, US_POLICY_RATE, EA_HICP, EA_POLICY_RATE']
stale_indicators: macro:US_CPI last_obs=2026-10-01 available=2026-11-15
```

2026-10 CPI 的发布日 11-15 尚未到；**最近可用**的 2026-09 CPI（可用 10-16）是健康的。`readiness.py:152-161` 取 `MAX(date)<=target` 的最新观测，再要求 `avail<=target`；应改为“取 `date+lag<=target` 的最新可用观测”。同一代码在 2026-11-15 立刻变为 14/16；对历史 as_of 2024-06-03 变成 **0/16**（见 2.5）。13:44 加入的 `data_degraded` 门禁（`opportunities.py:1291-1292`）又把该标志用于 deep_research：同一合成 draft 分数 0.8688 时，`data_degraded=False -> deep_research`，`=True -> watch`。即健康数据日/历史回放会被系统性降级，无法产出重点研究。

### 2.5 历史 as_of 端到端（复现 2.4 的后果）

`run_scan(as_of='2024-06-03')`（117.2s）：`status=success`，1,138 条异常，3 个机会；`readiness ok=True, degraded=True, fresh_macro=0/16`。说明 13:38 的区域 `date<=?` 修复解决了历史 as_of 被 P1 阻塞的问题，但宏观新鲜度在历史路径上把 16/16 全部误报为过期，`data_degraded` 会阻止 deep_research。

### 2.6 期货换月

WTI 前月换月日（到期后首个交易日）：

- 2016-01-21：CL **+11.22%** vs Brent +4.91%（差 **+6.31pp**），1d robust z=**+3.96**（超过 detector 阈值 3.0）；2020-04-23：+19.74% vs +4.71%，z=12.33。
- 当前窗口：2026-09-23 CL -2.57% vs BZ +3.86%（**-6.43pp**）、2026-10-21 CL -4.56% vs BZ +0.03%（**-4.59pp**）为换月缺口，但 z 未到 3；2026-11-04 CL -8.29%/z=-4.01 并非换月日。
- `anomalies.py:258-259` 的 `near_month_end` 只覆盖 `day>=27 or day<=2`，而 WTI 换月在 20/21/23 日 → 上述三例均为 `False`；`opportunities.py:1251-1261` 的 0.9 dq 折扣只作用于 `d.instruments`，不作用于机制 trigger/confidence。报告已披露“期货连续、未展期调整”，但新缓解没有覆盖 WTI 月中换月。

### 2.7 其他数字

- **逐日 guard 的历史副作用**：as_of=2024-06-03 时原始 SPY/DAX/CL 有 6/3 行（`fetched_at=2026-11-13T15:05:43Z`，15:05 < 美股 21:30 UTC 收盘），`_load_prices` 把 US/DE/CL 最后一行丢到 **5/31**，JP/CN 保留 6/3。`features.py:393-412` 把“最后一次批量下载时间”当作每根历史 bar 的 fetched_at，历史 as_of 因此系统性损失美股/欧股/商品最后一天；当前 11-13 也同样把 SPY/GC 截到 11-12（readiness 仍报 last=11-13）。
- **条件收益双滞后**：`evaluator.py:168-177` 的 macro 序列已是 availability 日期；`:333,342` 再加 `RELEASE_LAG_DAYS`。最小 FeatureSet 验证 `CN_CREDIT`：availability 2018-07-29，`first_entry=2018-11-26`，**+120 天**；CN_POLICY_RATE 会是 +45 天。
- **失败扫描文件残留**：monkeypatch `export_all` 抛错后，DB 5 张表均 0、`scan_runs=failed`，但 `report_2024-12-31.md`（12,872 B）与 `scan_2024-12-31.json`（183,759 B）保留，报告内 scan_id 指向失败扫描。
- **质量问题的时点**：`opportunities.py:266` 用 `datetime('now','-120 day')`；历史 as_of 会看到未来（2026）的 quality_issues、看不到 2024 的；`pipeline.py:146` 的 `recent_issues` 无日期过滤，历史报告第 5 节会展示未来问题。
- **FX**：`features.py:524/588` 用本币 adj_close；报告 1.1 表把 CN/JP/EA 与 US 并排且无币种列。按 USDJPY/EURUSD 换算（feature 最后有效 bar：JP 11-13、EA 11-12），JP 1m 本币 **-9.75%** vs USD **-10.61%**，EA **+3.37%** vs **+2.36%**。未发现字面“USD return”声明；问题是隐含可比性与 `_price_fundamental_divergence` 的跨币种解释。

## 3. NEW 问题表

| # | 严重度 | 位置 | 证据 | 影响 | 新旧 |
|---|---|---|---|---|---|
| 1 | **P1** | `goe/readiness.py:123,134,138` | 6 个小市场全删：`ok=True coverage=0.944`；UK 3 个全删：`ok=True coverage=0.976 UK=None`；CA 唯一标的 682 天旧：`ok=True CA.coverage=0` | 完全死亡的小市场/零行市场不触发 critical；全局 80% 覆盖率掩盖；新门禁的核心承诺不成立 | NEW（round-2） |
| 2 | **P1** | `goe/readiness.py:152-161`；`goe/opportunities.py:1291-1292` | 2026-11-13 生产扫描 `fresh=5/16`（US_CPI 2026-10 发布日 11-15 未到）；11-15 变为 14/16；2024-06-03 为 0/16；合成 draft 0.8688：degraded=False→deep_research，True→watch | 健康宏观/历史回放被误判降级；新 deep_research 门禁被全局触发，重点研究被错误压制 | NEW（13:38/13:44 改动） |
| 3 | **P1** | `goe/anomalies.py:848-857`；`goe/pipeline.py:98`；`goe/anomalies.py:906-914` | 打爆 `VolRegimeShift`：99→79 条异常、该 detector 消失；status=success，stats/DB/report 均无错误字样 | detector 故障与“无异常”不可区分；信号覆盖静默下降 | NEW（旧审计未记录） |
| 4 | **P1** | `goe/pipeline.py:73-76`；`goe/readiness.py:95-100` | 2024-12-31 旧库：`check_data_readiness(as_of=None,today=2026-11-14)` → critical 683 天；`run_scan(as_of=None)` → success, as_of=2024-12-31, scan_runs=success | “最新”扫描可基于多年陈旧数据；wall-clock 门禁在唯一入口不可达 | 既有代码（旧审计未记录） |
| 5 | **P2** | `goe/features.py:393-412` | as_of 2024-06-03：SPY/DAX/CL 最后 5/31，JP/CN 6/3；原始 6/3 行 fetched_at 是 2026 批量时间 15:05Z | 历史扫描/`scan --as-of` 对美/欧/商品系统性少一天，跨市场 as_of 不齐 | NEW（历史扩展） |
| 6 | **P2** | `goe/transmission/evaluator.py:168-177,333,342` | `CN_CREDIT` 已 availability 日期，仍再加 120 天；first_entry=availability+120d | 宏观条件收益统计晚 1.5–4 个月，机制置信度错误（无前视，但仍错） | NEW（旧审计未记录） |
| 7 | **P2** | `goe/anomalies.py:258-259`；`goe/opportunities.py:1251-1261` | 2016-01-21 WTI 换月 z=3.96；2026-09-23/10-21 缺口 -6.43/-4.59pp；`near_month_end` 在 21/23 日为 False；折扣只覆盖 `d.instruments` | 换月缺口进入收益/波动/相关性并可触发 anomaly；新缓解漏掉 WTI 月中换月，且不影响 trigger/mechanism 置信度 | NEW（缓解） |
| 8 | **P2** | `goe/features.py:43,444` vs `goe/readiness.py:159-161` | US_CPI 截到 2026-07-01（135 天）：readiness 不算 stale；`FeatureBuilder.stale_macro` 含 US_CPI、macro 列 13 而非 14 | readiness 说“新鲜”，特征层却剔除；阈值 110 天 vs lag+60（obs 150 天）不一致 | NEW |
| 9 | **P2** | `goe/pipeline.py:146-152`；`goe/db.py:185-211` | export 失败注入：DB 0 行、scan failed，但 report/scan JSON 仍在；报告 scan_id 为失败 ID | DB 回滚成功，外部 artifact 不一致；同 as_of 会被下一次覆盖 | NEW（round-2 事务边界） |
| 10 | **P2** | `goe/opportunities.py:266`；`goe/pipeline.py:146`；`goe/reports.py:291` | `_dq` 用 wall-clock `now-120d`；历史 as_of 会看到未来 quality_issues；`recent_issues` 无 as_of 过滤 | 历史候选 dq/gate 使用未来元数据；历史报告展示未来问题 | NEW（时点语义） |
| 11 | **P2** | `goe/opportunities.py:248-266` | severity 被忽略，info/warning/error 都是 5%/条，最多 20%；只按 target 精确匹配；US_CAPE 的 `series_stale` 因无候选 entity 匹配而不惩罚 | “质量下降”只在少数候选中生效；CAPE 死亡主要靠 degraded 全局开关 | 既有/未完全覆盖 |
| 12 | **P2** | `goe/features.py:524/588`；`goe/reports.py:50-61`；`goe/opportunities.py:370-375` | JP 1m 本币 -9.75% vs USD -10.61%；EA +3.37% vs +2.36%；无币种列；无字面 USD claim | 跨市场收益不可直接比较；非美资产的“价格下跌/相对强弱”解释可能被汇率污染 | 既有（旧审计提及 forward_eval，本处补充报告/候选口径） |
| 13 | **P3** | `goe/features.py:961` | VIX `pctile_5y`=0.582028 vs 按 1,260 个有效观测 0.577442（Δ0.004586）；z Δ0.003442；business-day 面板含假日 NaN，rolling 按行而非按有效观测 | 分位窗口实际不足 5 年；稀疏标的会放大 | 既有/新量化 |

## 4. 定量独立复算（原始 DB，未调用特征函数）

按 `_drop_incomplete_bars` 后的最后完整 bar（US/商品 11-12，CN/JP 11-13）复算：

| 指标 | 独立复算 | 特征层 | 结论 |
|---|---|---|---|
| SPY 1m / 3m / 12m 收益 | -1.6216% / -2.2336% / +12.0481% | 同 | 一致 |
| SPY 3m 年化波动 / 252d 回撤 | 14.6256% / -2.81996% | 同 | 一致 |
| SPY z1d / z1m / 1m 分位 / vol z / vol 分位 | -0.682499 / -1.203335 / 0.2454329 / 0.911359 / 0.5901509 | 同 | 一致 |
| 黄金 net / OI / net_to_oi / net_z / net 分位 | 103,614 / 399,169 / 0.2595743 / -0.5359396 / 0.5907336 | 同 | 一致 |
| CPI YoY / change_3p / z_3y | 3.737685% / 0.206260 / 1.710394 | 同（date=2026-10-16） | 一致（需按含 NaN 的月窗算） |
| UST 10Y / change_21d / z | 5.10 / -0.11 / 3.372454 | 同 | 一致 |
| VIX level / pctile_5y / z_3y | 18.70 / 0.577442 / 0.784053 | 18.70 / 0.582028 / 0.780611 | 分位/ z 有小差异（#13） |

说明：若直接用原始 11-13 SPY 盘中 close（753.11）复算 1m 得 -2.4203%，与特征的 -1.6216% 差 80bp；这是 `_drop_incomplete_bars` 有意丢弃 11-13 盘中 bar（US 15:05Z fetched）的结果，不是特征算术错误。但 readiness/报告仍声称 last_price_date=11-13，存在口径透明度问题。

## 5. 已验证修复 / 不能验证

**已验证（不作为缺陷）**
- 事务：失败于 `write_reports` 或 `persist_drafts` 持久化之后，DB 的 anomalies/transmissions/opportunities/events 全部回滚为 0，`scan_runs=failed`；已有机会的 refresh/event 也回滚到扫描前状态。
- 13:38 前的“历史 as_of 被 per-region 全量阻塞”已通过 `WHERE date <= ?` 修复；2024-06-03 历史扫描现在 success（但被 2.4 的宏观误判降级）。
- 金 net/OI、CPI、UST、SPY 的独立复算与特征行一致，未发现新的算术/单位错误。

**不能验证 / 限制**
- CFTC/BLS 的真实发布时刻与 vintage：只能验证报告日 + 配置 lag，无法逐周核对“周五 15:30 发布”或修订值。
- 期货合约元数据/逐日换月：只有连续前月价格；WTI 换月日按“到期前 3 个工作日”启发式，Brent 背离是证据但非合约级证明。
- 完整 121+ 离线测试：本次只跑了 17 项 e2e/readiness 定向；未跑全量。
- 生产库稳定性：`data/goe.db` 审计期间被并发重扫，历史/机会计数会变；本报告以 13:43:47 扫描 + `/tmp` 副本为准。
- `data_degraded` 对“本应 deep_research”的真实候选的影响：生产最高分 0.6702 < 0.68，未自然触发；用合成 draft 0.8688 验证了门禁路径。
- FX 对具体候选评分/结论的完整重算：只量化了 JP/EA 本币 vs USD 的 1m 差，未替换特征后重跑候选。

## 6. 最重要新缺陷

**`readiness.py:152-161` 的宏观新鲜度把“最新观测尚未到发布日”误判为“停止更新”**：2026-11-13 生产扫描只有 **5/16** 宏观新鲜（US_CPI 的 2026-10 发布日 11-15 尚未到），历史 as_of 2024-06-03 为 **0/16**；再叠加 13:44 新增的 `data_degraded` deep_research 门禁，健康数据日/历史回放会被系统性降为 watch，无法产出重点研究。**P1**（不是 P0：没有伪造数据或前视，但会错误阻断最高优先级输出；修复方式是取 `date+lag<=target` 的最新可用观测，而不是拒绝最新未发布观测）。
