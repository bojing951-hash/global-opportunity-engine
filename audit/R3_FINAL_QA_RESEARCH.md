# ROUND 3 — 独立最终 QA（研究/验收 · pass 2）

- 审计对象：`HEAD 6755d34` + 未提交修复；运行库 `data/goe.db`；**当前最新扫描 `scan-20261114T090844Z-52b0e7`（2026-11-14 17:09 HKT，`as_of=2026-11-13`）**；16:45 的 `scan-20261114T084506Z-06470b` 作为历史快照保留。
- 审计时间：2026-11-14 16:44–17:15 HKT（16:45 与 17:09 两次扫描；17:09 为 current artifact。审计期间 `PROJECT_SPEC.md`、`README.md`、`TEST_RESULTS.md`、`audit/VALIDATION_RESULTS.md`、`audit/EXECUTION_STATE.md` 仍在被并行修改，本文标注 17:07 时点仍未同步的项）。
- 方法：只读 SQL/JSON + `.venv/bin/python` 独立复算（评分、期望差、残差、driver 替换、前向收益、盲评统计）；`goe handoff` 只在 `/tmp` 数据库副本上运行；validation 只在 `/tmp` 输出；未改代码、配置、测试、数据或 git。
- 写入边界：本文件是唯一仓库写入；其余写入均在 `/tmp`（DB 副本、handoff 输出、validation 输出）。

## 0. 快照漂移（17:01–17:05 并发修复；必须先读）

审计期间工作树被并行修改，并在收尾时完成重扫。时间线：

- 16:45:32：旧代码扫描 `scan-...06470b`，DB/report/export 为 16:45；本文 §2/§3.4 的 16:45 表是这一版。
- 17:01–17:06：代码/测试/盲评 artifacts 被并行修复（见下）。
- **17:08:44–17:09:19：重扫 `scan-...52b0e7`，status success；DB/report/export 更新到 17:09。当前 artifact 是这一版（§0.1）。**

代码/测试/盲评的并发修复：

- `goe/expectations.py`（17:02:24）：DE/FR/IT/ES 加入本地 driver（DE 加 EA_EQ_SX5E，DE/FR/IT/ES 加 EURUSD）。**这是对 P1-1 的代码层修复。**
- `goe/integration/exporter.py`（17:02:24）：queue 只收 `deep_research/watch/new`，不再把 `low_priority` 放进 priority 1。**这是对 P1-5 的代码层修复。**
- `goe/forward_eval.py` + `audit/FORWARD_RETURNS.md`（17:02:09）：增加 `mean fwd 3m ex-top`（C 由 7.12% → 2.45%）。**这是对 P1-4 的部分修复。**
- `tests/test_exporter.py`（17:05:18）：队列期望从 3 个任务改为 2 个。
- `audit/research_quality_input.json` / `research_quality_mapping.json`（17:01:44）被**重新生成**（例如 X24 natural gas → ChiNext，X21 heating oil → VVIX），但 `research_quality_ratings_round2.json`（14:26）与 `audit/RESEARCH_QUALITY.md`（14:32）**没有重评**。17:06 又出现独立的 `research_quality_ratings_r3.json`（untracked），对新 mapping 的评分是 **C 最后**（见 §6.1）。这是本轮最严重的研究质量 artifact 问题。
- `data/goe.db`、`reports/report_2026-11-13.md`、`exports/*` 的 mtime 已更新为 **17:09**（重扫）；`research_queue` 只有 DXY/N225 两条 watch。

因此：

1. **16:45 artifact（历史）**：§2 的 DAX watch/queue priority 1 是真的；**17:09 重扫已把它们修掉**（DAX 不在 11 候选；queue 只有 2 条 watch）。
2. **17:09 artifact（current）**：DAX 问题解决；top-3 只剩 DXY/N225 两个 watch；按分数第一仍是 OPP-0001 stale low 0.6034。研究能力仍不能签收（见 §0.1/§1）。

**结论：16:45 artifact 已被 17:09 重扫取代；17:09 artifact 解决了 P1-1/P1-5，但 top-3 只剩 2 条 watch、盲评 r3 把引擎排最后、handoff 仍 refused、validation artifact 仍旧、README/最终验收仍假成功。研究/验收仍 NO-GO。**

### 0.1 17:09 重扫（当前 artifact；覆盖 §2/§3.4/§5.2 的旧数字）

审计收尾时工作树又完成了一次 **17:09:19 的重扫**（`scan-20261114T090844Z-52b0e7`，status success，1506 anomalies、5 mechanisms、11 candidates），这次扫描**已包含 17:02 的 DAX/queue 修复**：

| # | 候选 | 状态 | 分数 | 说明 |
|---:|---|---|---:|---|
| 1 | OPP-0001 SPY 政策重定价 | low_priority | 0.6034 | 28 天前 BIS 可用日；queue **不再**收录 |
| 2 | OPP-0002 DXY 就业前 | watch | 0.5927 | 唯一 top-3 中的低信息日历候选 |
| 3 | OPP-0003 N225 BoJ 前 | watch | 0.5577 | 唯一稳健 top-3 |
| 4 | OPP-0004 QQQ 政策重定价 | low_priority | 0.5142 | **DAX 已从 11 候选中消失**；QQQ 政策替代，stale/low |
| 5 | OPP-0005 USDJPY 机制失效 | low_priority | 0.4875 | — |
| 6 | OPP-0006 EEM VIX 期限 | invalidated | 0.4387 | — |
| 7 | OPP-0007 TAIEX 超跌 | excluded | 0.3792 | — |
| 8 | OPP-0008 XLY 过度乐观 | excluded | 0.3455 | — |
| 9 | OPP-0009 ChiNext 超跌 | invalidated | 0.3377 | — |
| 10 | OPP-0010 XLK 超跌 | excluded | 0.3346 | — |
| 11 | OPP-0011 India Sensex 过度乐观 | excluded | 0.3281 | — |

- 当前 status = **2 watch / 3 low_priority / 2 invalidated / 4 excluded / 0 deep**；`research_queue` 只有 **DXY（priority 1）/ N225（priority 2）**，low_priority 已被排除；`research_tasks` 只剩 2 条（旧的 `RT-20261113-0001.json` 仍留在磁盘，P2）。
- **P1-1（DAX）在 current artifact 已解决**：DAX 不再进入 11 候选；OPP-0004 变为 QQQ 政策 low 0.5142。**P1-5（queue）在 current artifact 已解决**：queue 只有 watch。也就是说 §2/§3.4/§5.2 的 16:45 表是历史，不是当前状态。
- **但 top-3 仍不成立为“三条独立前瞻线索”**：按状态只有 **2 个 watch**（DXY/N225），没有第三条；按分数第一仍是 **OPP-0001 low_priority 0.6034**（过期政策），第二/第三是 DXY/N225。top-3 的“独立性”问题从“DAX 假 watch”变成“只有两条 watch + 一条 stale 高分 low”。N225 仍是唯一稳健线索；DXY 仍是低信息。
- **open P1 仍为**：blind r3/ratings 不一致（§6.1）、handoff OOS 禁用词（§5.1）、最终 replay artifact/7/7（§4）、README/最终验收假成功/旧数字（§7）、forward class-relative（§6.2）、current top-3 只有 2 个 watch / 分数第一仍是 stale policy low（P1-8）。**P1-1/P1-5 记为“代码 + 重扫已修复”，不再作为 open P1；但 16:45 的审计记录保留为历史。**

## 1. 判决

**工程层：PASS WITH ISSUES（可运行、可审计；未发现 P0）。**
**研究/验收层：NO-GO（不能以当前证据签收“六门”）。**

- 工程上：157 项离线用例已收集、pytest 退出码 0；最新扫描 `success`、11 个候选、1506 条异常、5 条机制在同一事务内落库；handoff 解析器能把下游 `out_of_scope` 记为 `refused`、CLI exit 2、任务 `not_completed:refused`，不再假成功；excluded 可重新激活已有回归测试。
- 研究上（**current 17:09 artifact**）：按 watch 只有 **2 个**，不是三条独立线索：
  1. **DXY（0.5927）**：near-high 0.867 + 0.036 噪声，21 天后的 BLS 事件；典型“日历 + 趋势”，预期差仅仓位代理 0.1748 / 覆盖 47%。
  2. **N225（0.5577）**：唯一稳健的 watch；11-06 的日本本地冲击真实（同日 SPY +0.31%、EEM +2.21%、DAX -1.92%，N225 -5.96%），残差在加入 TOPIX 后仍 z≈-2.5。
  - **没有第三条 watch**。按分数第一仍是 `OPP-0001`（0.6034，28 天前的 BIS 政策可用日，low_priority）；第二名/第三名才是 DXY/N225。16:45 artifact 的 DAX 假 watch 已被 17:09 重扫移除（DAX 不在 11 候选；OPP-0004 变为 QQQ 政策 low 0.5142）。
- `OPP-0001` 的 policy-age cap 正确，**17:09 queue 已只含 DXY/N225**；旧的 16:45 queue priority 1 是历史。但 `OPP-0001` 仍是**分数第一**，报告“其他记录”里第一行就是过期政策；按分数排序的消费者仍会被误导。P2/P1（排序语义）保留。
- `7/7` 历史验证只在“至少命中一个预期检测器”的 OR 口径下成立：3/7 只命中 1 个预期检测器，黄金案例只命中通用 `price_return_shock`（预期 `cross_asset_divergence` 未命中），`mechanism_ok` 7/7 全为 false；且仓库内最新验证 artifact 生成于 06:30Z，早于 `goe/validation.py` 的 16:12 修改，不能称为“current code 的最终 artifact”。
- 研究质量：**当前 artifacts 不一致且结论翻转**。17:01 的 input/mapping 重生成后，14:26 的 ratings 是旧对象（X21 旧评语“三周期大涨”，新对象 VVIX 1 个月 -25.74%），`RESEARCH_QUALITY.md` 14:32 未重评；但 17:06 出现的独立 `research_quality_ratings_r3.json`（36 objects，untracked）对**新** mapping 给出：A 1.312 / B **1.521** / C **1.188**，C 的 Precision@3 0.417 vs B 0.750，2025-06-30 C 0.583 vs B 1.500。**旧“C 1.250 vs B 1.229（+0.021）”被新评分反证，方向相反。** 旧数据下 C 的 +0.021 也被事实卡信息不对称污染（C 9/12 带 mechanism，A 1/12、B 3/12；`beyond_price` 均值 C 0.833 vs B 0.500 vs A 0.083）。前瞻 C +7.12% 中 **4.87pp（约 68%）来自 FXI 单一对象**；17:02 新表已给出 C ex-top +2.45%，但 class-relative 仍是含 FXI 的 +2.99%、ex-FXI 为 **-0.93%**、beat-class 42%→36%（B 为 +5.42% / 58%）。没有稳健研究优势。
- Handoff：`OPP-0002` 实跑 rc=0，但 S8 `out_of_scope` → `refused`，CLI exit 2，任务 `not_completed:refused`——状态语义正确；但 A 的问题正文含 `不构成投资建议`、`仓位`，正好命中下游 `OUT_OF_SCOPE_PATTERNS`（`投资建议`、`仓位`）。受控实验：干净问题可 `answered`，加“不构成投资建议”或“请核对仓位事实”即 `out_of_scope`。**拒答至少部分是 A 自己措辞造成的，不是纯外部能力限制。** 去掉这些词后完整问题变成 `unmapped`，仍不能 `ok_valid`，所以“无成功 handoff”仍成立，但审计归因必须修正。

一句话：**工程可以继续；研究不能签收。当前 17:09 artifact 只有两条 watch——N225 是唯一经得起本地 driver 与同日横截面复核的线索，DXY 是低信息日历；第三席不存在，分数第一仍是过期政策 low。DAX 假 watch 与 queue priority 1 已在 17:09 修复，但盲评 r3 把引擎排最后、handoff 仍 refused、7/7 与文档仍不可签收。**

## 2. 16:45 历史 artifact 与候选（current 17:09 见 §0.1；DB/report 已于 17:09 更新）

> 本节保留 16:45 的审计证据，用于说明“DAX/queue 问题当时确实存在”。**当前状态以 §0.1 的 17:09 表为准。**

最新扫描（`scan_runs`）：

| 字段 | 值 |
|---|---|
| scan_id | `scan-20261114T084506Z-06470b` |
| as_of / status | 2026-11-13 / success |
| 异常 | **1506**（price 935；industry 454；positioning 69；macro 38；cross_asset 10） |
| 机制 | 5 activated（M12 mixed 0.55、M05 mixed 0.14；M01/M09/M14 unsupported 0.05） |
| 候选 | **11 = 3 watch / 2 low_priority / 2 invalidated / 4 excluded / 0 deep_research** |
| 报告/导出 | `reports/report_2026-11-13.md`、`reports/scan_2026-11-13.json`、`exports/pipeline_2026-11-13.json` 三处 16:45 同步 |

| # | 候选 | 状态 | 分数 | 原型 | 现象/事件 | gap（value/conf） | 自动失效检查 |
|---:|---|---|---:|---|---|---|---|
| 1 | OPP-0001 SPY 政策重定价 | low_priority | 0.6034 | event_revision | 2026-10-16 BIS 可用日（28 天前） | 0.4074 / 0.75 | 0 |
| 2 | OPP-0002 DXY 就业前 | watch | 0.5927 | event_revision | 2026-12-04 BLS | 0.1748 / 0.4667 | **0** |
| 3 | OPP-0003 N225 BoJ 前 | watch | 0.5577 | event_revision | 2026-12-18 BoJ | 0.3143 / 0.40 | **0** |
| 4 | OPP-0004 DAX ECB 前 | watch | 0.5294 | event_revision | 2026-12-17 ECB | 0.2452 / 0.40 | **0** |
| 5 | OPP-0005 USDJPY 机制失效 | low_priority | 0.4875 | mechanism_breakdown | BoJ 12-18 | 0.3261 / 0.4667 | **0** |
| 6 | OPP-0006 EEM VIX 期限 | invalidated | 0.4387 | regime_repricing | VIX3M | 0.1228 / 0.40 | 1（仅首个 trigger） |
| 7 | OPP-0007 TAIEX 超跌 | excluded | 0.3792 | price_fundamental_divergence | — | 0.2505 / 0.40 | 2 |
| 8 | OPP-0008 QQQ 超跌 | excluded | 0.3738 | price_fundamental_divergence | FOMC 12-09 | 0.0131 / 0.40 | 2 |
| 9 | OPP-0009 XLY 过度乐观 | excluded | 0.3455 | price_fundamental_divergence | — | 0.4000 / 0.40 | 1 |
| 10 | OPP-0010 ChiNext 超跌 | invalidated | 0.3377 | price_fundamental_divergence | — | 0.0605 / 0.40 | 2 |
| 11 | OPP-0011 XLK 超跌 | excluded | 0.3346 | price_fundamental_divergence | — | 0.2018 / 0.40 | 2 |

**报告内的“watch top-3”= OPP-0002 / OPP-0003 / OPP-0004；按分数 top-3 = OPP-0001 / OPP-0002 / OPP-0003。** 两个口径必须分开看：前者的 #1/#3 是日历/趋势，后者的 #1 是已过期政策叙事。

### 2.1 Top-3 独立性/前瞻性

- **资产/主题层面独立**：DXY（usd）、N225（japan_equity）、DAX（germany_equity）无重复 primary、无重复 theme；事件日期 12-04 / 12-18 / 12-17，全部在未来 21–35 天，**形式上 forward-looking**。
- **方法/机制层面不独立**：三条全是 `event_revision`，`mechanism.id=None`、confidence 0.3、同一条“事件结果 → 预期修正 → 资产重定价”链、同一组 `OPEN_QUESTIONS`；区别只是资产和日历。DXY/DAX 又同属“near 1-year high”（风险偏好/美元利率同一全球因子），N225 是 deep drawdown；是“一个模板 × 三个资产”，不是三个独立的宏观现象。
- **只有 N225 有真实、稳健的本地现象**：11-06 N225 -5.96%、TOPIX -6.5%，同日 SPY +0.31%、QQQ +1.40%、EEM +2.21%、DAX -1.92%；加入 TOPIX 作为本地市场后残差 z≈-2.535（代码 -2.679），5 年回撤分位约 3.1%，1 个月 -9.7%。这是一条值得研究的日本本地冲击线索。
- **DXY 信息量低**：`drawdown_extreme near_high` 0.867 是“接近高点”，不是异常变化；第二条 `relative_strength_extreme` 仅 0.036；1 个月 +1.1%、距 1 年高点 -0.03%。核心信息是“美元近高 + 21 天后 BLS”，不是预期差。
- **DAX 是测量伪影**（详见 §3.4）：去掉伪影后它不应留在 watch。

## 3. 评分、期望差、driver 与状态

> 本节数值是 16:45 artifact 的逐项复算（用于验证公式/日期/状态逻辑）；17:09 current 的候选表见 §0.1。17:09 的 OPP-0004（QQQ low 0.5142）、OPP-0008（XLY 0.3455）、OPP-0011（India 0.3281）分数与 16:45 不同，但评分公式/权重/cap 未变。

### 3.1 逐项复算（11/11）

按 `config/scoring.yaml` 权重（0.22/0.18/0.20/0.12/0.10/0.06/0.06/0.06，和=1.0）和代码语义独立复算：

| 候选 | DB score | 复算 | 最大分量差 |
|---|---:|---:|---|
| OPP-0001 | 0.6034 | 0.6034 | 0 |
| OPP-0002 | 0.5927 | 0.5928 | <1e-4（rounding） |
| OPP-0003 | 0.5577 | 0.5577 | 0 |
| OPP-0004 | 0.5294 | 0.5294 | 0 |
| OPP-0005 | 0.4875 | 0.4875 | 0 |
| OPP-0006 | 0.4387 | 0.4387 | 0 |
| OPP-0007 | 0.3792 | 0.3792 | 0 |
| OPP-0008 | 0.3738 | 0.3738 | 1e-4（gap 四舍五入） |
| OPP-0009 | 0.3455 | 0.3455 | 0 |
| OPP-0010 | 0.3377 | 0.3377 | 0 |
| OPP-0011 | 0.3346 | 0.3346 | 0 |

`economic_impact`、`evidence_quality`、`catalyst`、`timing_window`、`risk_liquidity` 也与代码公式逐项对齐（例如 DXY evidence_quality = 0.45×0.7 + 0.25×2/3 + 0.15×0.3 + 0.15×0.75 = 0.6392）。**评分公式本身没有发现算术错误。**

### 3.2 policy-age cap / catalyst / excluded / invalidated

| 项 | 代码行为 | 当前数据 | 结论 |
|---|---|---|---|
| policy-age cap | `policy_event_age_days>10` 且 `watch/deep` → `low_priority`（`goe/opportunities.py:1414-1421`） | OPP-0001 age=28 → low；reason“BIS 月频可用日不是决议日” | **PASS** |
| 过去事件 catalyst | 不再进入 `catalysts`，`cat=0.1`（`:1337-1347`） | OPP-0001 catalysts=[]，cat=0.1 | **PASS** |
| 31–90 天 catalyst | `0<=days<=90` → 0.2（`:1349`） | N225 35d=0.2；DAX 34d=0.2；OPP-0005 35d=0.2 | **代码 PASS；config/docs 仍写 else 0.1（见 P2）** |
| 同日 catalyst | `days==0` → 0.6（`:1343`） | 当前无同日事件，latent | **代码 PASS；docs/config 仍写 0≤days≤10→1.0** |
| excluded re-arm | terminal 只含 expired/invalidated（`:1505`）；excluded 不在 terminal | `tests/test_status_lifecycle.py::test_excluded_candidate_can_be_re_armed` 通过 | **PASS** |
| invalidated | terminal；`apply_lifecycle` 跳过 | OPP-0006/0010 invalidated；不再进队列 | **PASS（不复活）；但永久、只查首个 trigger，见 P2** |

### 3.3 期望差：数值/日期/置信度

| 候选 | gap value / conf | 组件 | 回归日期 / lag | 备注 |
|---|---|---|---|---|
| OPP-0001 SPY | 0.4074 / 0.75 | positioning 0.3977 + residual 0.6705 | 11-12 / 1d | 残差 driver = **RSP**，不是 SPY 自身；见 §3.5 |
| OPP-0002 DXY | 0.1748 / 0.4667 | positioning 0.3745（11-07 release） | — | 仅 1/3 proxy；conf<0.5，deep gate 会 cap |
| OPP-0003 N225 | 0.3143 / 0.40 | residual 0.7857 | 11-12 / 1d | 仅 1/3 proxy；conf<0.5 |
| OPP-0004 DAX | 0.2452 / 0.40 | residual 0.6129 | 11-12 / 1d | 仅 1/3 proxy；残差 driver 缺 SX5E/EUR |
| OPP-0006 EEM | 0.1228 / 0.40 | residual 0.3069 | 11-12 / 1d | gap<0.15 |
| OPP-0005 USDJPY | 0.3261 / 0.4667 | positioning 0.6988 | — | 仅仓位 proxy |

- 公式：`value = Σ(可用权重×值)/Σ(可用权重) × (可用权重/适用权重)`；`confidence = 可用权重/适用权重`。DXY 0.1748、N225 0.3143、DAX 0.2452 都可从组件精确复算。
- 日期：residual 统一 `as_of_return_date=2026-11-12`（lag 1），不是旧的 10-30 采样相位；CFTC `as_of_report=2026-11-07` 是**发布日**（报告日 11-03），6 天内，仍在 21 天新鲜窗口。
- **报告正文不展示 `${as_of_return_date}`/lag**：N225 报告表写 1 个月 -9.7%（11-13），而残差计算用 11-12 的 -10.22%；读者无法从报告看出这两个日期。P2 透明性问题。

### 3.4 DAX：16:45 artifact 的假 watch；17:02 代码 + 17:09 重扫已移除

**16:45 artifact 的旧代码** `goe/expectations.py:156-169`：

- `region_market["DE"] = ["DE_EQ_DAX"]`；DAX 作为自身被 skip 后，market driver 落到 **US_EQ_SPY**。
- `local_fx` 只有 JP/EA/UK/CH/AU/KR/BR/MX，**没有 DE/FR/IT/ES**；DAX 没有 EURUSD driver。
- 因此 OPP-0004 的 residual drivers 实际是 `SPY + DXY + UST10Y`，不是“德国本地市场 + 欧元”。

独立复算（DB 原始价格，21 个交易日收益，非重叠月度样本，当前 11-12）：

| 模型 | drivers | R² | residual z | gap | score | 状态 |
|---|---|---:|---:|---:|---:|---|
| 16:45 代码口径 | SPY, DXY, UST | 0.530 | **2.419** | 0.2452 | 0.5294 | watch（artifact） |
| 加本地 | SPY, DXY, UST, **SX5E, EURUSD** | **0.886** | **1.352** | **0** | **≈0.4804** | low_priority |
| **17:02 新代码** | **SX5E, DXY, UST, EUR** | **0.858** | **1.401** | **预期 0** | **预期 ≈0.480** | **17:09 重扫：DAX 不在 11 候选；OPP-0004=QQQ low 0.5142** |

（原始 DB 直接复算为 z=2.479 / R²=0.535；与代码 2.419 / 0.530 的差异来自价格面板对齐，结论不变。17:02 代码把 `region_market["DE"]` 扩为 `[DE_EQ_DAX, EA_EQ_SX5E]`，并给 DE/FR/IT/ES 加 EURUSD；用同一回归口径 z=1.401，仍 <1.5；17:09 重扫后 DAX 已消失。）

**影响**：16:45 artifact 的 OPP-0004 DAX watch 完全依赖这个伪残差；修正后 0.5294 − 0.20×0.2452 = 0.4804，跌到 low_priority。**17:09 重扫已确认：DAX 不再进入 11 候选；OPP-0004 变成 QQQ 政策 low 0.5142。** 当前 artifact 的 top-3 不再是 DXY/N225/DAX，而是 **DXY/N225 两个 watch**；P1-1 记为“代码 + 重扫已修复”。

### 3.5 SPY：RSP/QQQ driver 选择导致符号翻转（P2）

- 代码把 SPY 的 market driver 解析为 **RSP**（SPY 的 region benchmark 是自身，被 skip；`cands` 中下一个是 RSP）。于是 residual 是“市值权重 vs 等权”的风格价差，不是“宏观/政策预期差”。
- 代码 z=-2.506、gap 0.4074；把 market driver 换成 QQQ 后 z=**+1.489**（<1.5，value=0），gap 降至约 0.139（仅 positioning），score 约 0.55。**符号翻转**说明该 gap 对 driver 选择不稳健。
- OPP-0001 已被 policy-age cap 降为 low，所以不改变 watch 集合；但它是**分数第一**（0.6034）；17:09 queue 已排除 low（只 DXY/N225），**排序语义问题仍在**：按分数读报告/DB 的消费者仍先看到过期政策（见 P1-8）。

### 3.6 evidence_quality / counter-evidence / caps / theme

- `evidence_quality` 复算精确；但 top-3 都只有 **1 条**反证，内容是通用“事件可能已被定价/缺少期权隐含分布”，没有针对“全球 risk-off / 本地 driver / 同日跨资产同步”的替代解释。反证惩罚上限 0.25×3=0.75，对 0.06 权重最多影响 0.00675 分，几乎不改变排序。P2。
- `independent_evidence` 只数 distinct `source` 字符串：两个 Yahoo 异常算 1 个来源；官方 URL 算 1 个。DXY 3 条证据实际是 2 个来源（2/3=0.667），不是 3 条独立证据。P3（表述/口径）。
- caps：per-archetype event_revision 4、per-mechanism 3、region caps；当前 3 个 event 候选，未触发上限。theme dedupe：11 个候选无重复 primary、无重复 theme，**PASS**。
- **但**最终 exposure cap 与 theme dedupe 都是按 `score` 排序，先于“状态/可研究性”判断；一个被 policy-age cap 成 low 的过期政策候选（0.6034）可以在同 theme 的 event 候选中胜出。当前 SPY 是一个**潜在**案例：11-05 的 SPY 异常距 as_of 已 8 天，是否进入 `_event_revision` 的 7 天 `current` 窗口未被本轮证实；因此这是设计风险，不是已证实的当前丢失。**分数高但已被降级的候选可以挤掉前瞻候选**。P2。17:02 只修了 queue 的 low 过滤，**没有修“分数先于状态”的 theme/exposure cap**，所以这个风险仍在。

## 4. 历史验证 / 7/7 是否有意义

### 4.1 事实

- 仓库最新 artifact：`reports/validation_cases_20261114T063037Z.json`，`generated_at=2026-11-14T06:30:37Z`；`goe/validation.py` mtime **16:12:53 HKT**。artifact 早于当前代码，**不是 current code 的最终 artifact**。
- artifact 结果 7/7；`mechanism_ok` 7/7 全 **false**；`mechanism_evaluated` 7/7 true。
- 逐 case 的预期检测器命中数：

| case | 预期检测器 | 命中 | 备注 |
|---|---|---:|---|
| COVID 2020 | 3 | 3/3 | 强 |
| RATE 2022 | 3 | 3/3 | 强 |
| UK LDI 2022 | 2 | 2/2 | 强 |
| SVB 2023 | 3 | **1/3** | 仅 `credit_stress`（CREDIT_RISK = HYG/IEF，parents 全在 case entities，符合 all-parent 规则） |
| JP carry 2024 | 3 | 3/3 | 强 |
| CHINA 2024 | 3 | **2/3** | `breadth_extreme` 未命中 |
| GOLD 2025 | 2 | **1/2** | 仅通用 `price_return_shock`；预期 `cross_asset_divergence` 未命中 |

- 代码 `detection_ok = det_hit > 0`（`goe/validation.py:222`），即“任一预期检测器命中”即可；`fam_hit` 仍计算但不再使用。`goe/validation.py:295` 的说明仍写“或异常家族”，与代码不一致。
- `derived_parents` 是硬编码的 6 对（`equity_oil/equity_credit/stock_bond/VIX_TERM/equity_vix/CREDIT_RISK`）；**没有 gold_dollar / gold_real_yield**。黄金案例的预期 `cross_asset_divergence` 在 case entities 上不可观测，因此只能靠 price shock 通过。
- 没有 placebo/negative case（例如平静期应不生成候选），也没有“预期检测器全中”的严格判定。

### 4.2 结论

**7/7 是“至少一个预期症状”的 7/7，不是“case 特征现象被完整识别”的 7/7。** 4 个案例（COVID/RATE/UK/JP）是强命中；SVB 是单一信用检测器；CHINA 缺 breadth；GOLD 只命中通用价格冲击。没有负控制，`mechanism_ok` 又从不参与通过，因此 7/7 不足以支持“严格 case-entity 检测能力已验收”的强结论。方法本身（PIT、case entity、all-parent）是改进；**证据强度被高估**。

（本轮在 `/tmp` 启动了一次 current-code replay；由于 7 case × 8 eval date 的重复 feature build 很慢，到 17:07 仍未产出文件，已停止，未作为本轮证据。旧 artifact 的命中集在 `det_hit>0` 规则下不会因 16:12 的 family→detector 改动而改变（7 个 case 的 det_hit 本来就 >0），所以预期仍是 7/7；但“最终 artifact 必须是 current code 生成”这一验收要求仍未满足。）

## 5. Handoff（DB 副本实跑）

命令（只写 `/tmp`）：

```
.venv/bin/python -m goe.cli handoff --db /tmp/goe_r3_handoff.db \
  --ia-path ~/investment-agent-dev --limit 1 --out-dir /tmp/goe_r3_ia
```

结果：

| 项 | 值 |
|---|---|
| 选中 | OPP-0002（watch；CLI 只挑 deep/watch，跳过 low_priority） |
| 下游 rc | 0 |
| semantic | **refused**（S8 `out_of_scope`） |
| CLI exit | **2** |
| research_tasks.status | **not_completed:refused** |
| opportunity_event | `ia_research_not_completed` |
| report.json | S8 `data.status=out_of_scope`，`answer_text=...投资建议/交易类越界范围` |

**语义正确性：PASS**（没有把 rc=0 当成功；P1-1 red-team 修复有效）。

### 5.1 但拒答是 A 自己措辞触发的（P1）

`goe/integration/exporter.py:125-127` 生成的问题含：

- `任务性质：...不构成投资建议；...`
- `需要回答：...仓位提前移动？`
- `请完成...核对宏观/价格/仓位事实...`

下游 `OUT_OF_SCOPE_PATTERNS` 精确包含 `投资建议` 和 `仓位`。受控实验（同一下游、同一 `research` 入口）：

| 问题 | 下游状态 |
|---|---|
| `美国政策利率水平是多少？` | **answered** |
| `美国政策利率水平是多少？不构成投资建议。` | **out_of_scope** |
| `美国政策利率水平是多少？请核对仓位事实。` | **out_of_scope** |

即：**问题语义上没有要建议，但词面上含下游禁用词，必然 `out_of_scope`。** 把 OPP-0002 问题中的禁用词去掉再跑 `research-run`，S8 从 `out_of_scope` 变成 **`unmapped`**（仍非 `ok_valid`）——所以“无成功 handoff”仍是外部能力限制，但当前记录的 `refused` 归因不准确，A 侧可修。

### 5.2 队列与 CLI：16:45 不一致；17:09 已修复

- **16:45（历史）**：`exports/research_queue_2026-11-13.json` priority 1 = **OPP-0001 low_priority**（0.6034）；`RT-20261113-0001.json` 也存在；`goe handoff` 只挑 deep/watch，所以实跑选 OPP-0002。报告说 OPP-0001 是“历史背景”，queue 却把它排第一——**交付契约自相矛盾**。
- **17:09（current）**：`exporter.py` 的 17:02 修复生效，queue 只有 **DXY（priority 1）/ N225（priority 2）**；`research_tasks` DB 只有 2 条；**P1-5 记为已修复**。
- 残留：磁盘上旧的 `RT-20261113-0001.json`（OPP-0001 low）和 `RT-0005` 仍在；`export_all` 不清理旧任务文件。下游若按目录随便读，仍可能读到过期任务。P2。

### 5.3 问题自包含性

- 包含现象、证据、反证、失效条件、待回答问题，数值可核验；这部分 **PASS**。
- **没有显式写数据截止 `as_of=2026-11-13`**；下游报告使用自己的 `research_snapshot_20261112_v2`（11-12），比 A 的 as_of 早一天。问题本身没有告诉 B “数据截止 2026-11-13”。P2。
- 问题包含 `投资建议`/`仓位` 禁用词；P1（见 5.1）。

### 5.4 README / 文档的成功声明

`README.md:150-153` 与 `docs/INTEGRATION_INVESTMENT_AGENT.md:108` 仍写：

```
OPP-0001: ok rc=0 elapsed=7.32  out=.../exports/ia_runs/OPP-0001
```

这与 `FINAL_ACCEPTANCE.md`（refused / not_completed:refused / no ok_valid）和本次实跑（refused / exit 2）矛盾。**这是假的成功声明**，必须改。P1（文档/验收）。

## 6. 研究质量 / 前瞻（数字复核）

### 6.1 盲评：旧 artifact 内部自洽，但 17:01 重生成后已不一致

**重要快照漂移**：`audit/research_quality_input.json`/`research_quality_mapping.json` 在 **17:01:44** 被重新生成（对象变化：X24 natural gas→ChiNext，X21 heating oil→VVIX），而 `research_quality_ratings_round2.json` 仍是 **14:26**、`RESEARCH_QUALITY.md` 仍是 **14:32**。ID→method/rank 标签没变（所以聚合均值“恰好”仍为 A 1.062 / B 1.229 / C 1.250），但 ID→object 已经换人：

- X21 旧评语“三周期大涨，仅价格事实”（旧对象 heating oil 1m +33.25%）；新对象 VVIX 的 1 个月是 **-25.74%**。
- X24 旧评语“月涨50%，无机制”（旧 natural gas +50.36%）；新对象 ChiNext +48.7% 恰好相似，属于巧合。
- X06 旧对象 ChiNext；新对象 China Securities Sector ETF。

因此：**下面的 1.250/1.229/1.062 只能证明“旧 mapping + 旧 ratings”内部自洽，不能证明当前对象的研究价值；当前盲评 artifact 无效，必须重评或恢复旧冻结输入。** 这是本轮新发现的 **P1**。

按**旧** `audit/research_quality_mapping.json` + `research_quality_ratings_round2.json` 独立复算：

| 方法 | mean(0–2) | Precision@3 | 2022-10-31 | 2023-03-31 | 2024-09-30 | 2025-06-30 |
|---|---:|---:|---:|---:|---:|---:|
| A 最大价格变动 | 1.062 | 0.083 | 1.00 | 0.917 | 1.25 | 1.083 |
| B 最大异常分 | 1.229 | 0.333 | 1.167 | 1.083 | 1.50 | 1.167 |
| C 引擎 | 1.250 | 0.417 | 1.583 | 1.00 | 1.667 | **0.75** |

与 `RESEARCH_QUALITY.md`（14:32 版）完全一致；但该报告现在引用的是**旧对象**。ID 全局打乱成立（`ABBABABCBCBAAACACCCCACBAACABBBBBCCAC`，无 round-1 的 X01–03=A 分块；新 mapping 的序列相同，因为 method/rank 标签未变），随机化本身 **PASS**；失效的是“评的是谁”。

**17:01 新 mapping + 17:06 独立 r3 评分（当前 artifacts，untracked）**：

| 方法 | mean(0–2) | Precision@3 | 2022-10-31 | 2023-03-31 | 2024-09-30 | 2025-06-30 |
|---|---:|---:|---:|---:|---:|---:|
| A 最大价格变动 | 1.312 | 0.500 | 1.083 | 1.167 | 1.667 | 1.333 |
| B 最大异常分 | **1.521** | **0.750** | 1.500 | 1.417 | 1.667 | 1.500 |
| C 引擎 | **1.188** | **0.417** | 1.500 | 1.083 | 1.583 | **0.583** |

- C 比 B **低 0.333**、比 A 低 0.124；2025-06-30 C 0.583 vs B 1.500。**旧报告的“C 1.250 vs B 1.229（+0.021）”在新对象上被反证，甚至方向相反。**
- 当前 r3 事实卡：C 9/12 带 mechanism（A 3/12、B 3/12），`beyond_price` C 1.0 vs A 0.5/B 0.833；但 C 的 `real_market_change` 1.083 vs A/B 1.833、`falsifiable` 1.25 vs 1.667/1.833。**机制信息更多，却没有转化为更高的综合研究分**；这比“信息不对称让 C 占便宜”更不利于引擎。
- 结论：当前可用的独立 r3 评分下，引擎不优于两个朴素基准，甚至更差；`RESEARCH_QUALITY.md`（14:32）必须重写，不能继续引用 +0.021。**这是本轮最强的研究质量反证。**

事实卡不对称（旧对象；新对象重评后需重算）：

| 方法 | 有 mechanisms | 有 positioning | 有 recent anomalies |
|---|---:|---:|---:|
| A | **1/12** | 2/12 | 8/12 |
| B | **3/12** | 3/12 | 12/12 |
| C | **9/12** | 5/12 | 7/12 |

四项标准均值：

| 方法 | real_market_change | beyond_price | falsifiable | data_sufficiency |
|---|---:|---:|---:|---:|
| A | 1.917 | **0.083** | 1.25 | 1.00 |
| B | 1.500 | **0.500** | 1.583 | 1.333 |
| C | 1.250 | **0.833** | 1.333 | 1.583 |

C 的总分优势 +0.021 正好来自 `beyond_price`（+0.333 vs B）与 `data_sufficiency`（+0.25），被 `real_market_change`（−0.25）和 `falsifiable`（−0.25）抵消；**这不是“研究判断更好”，而是 C 的事实卡更常带机制/仓位字段**。`RESEARCH_QUALITY.md:10` 说“同一模板”技术上没错，但“同一模板 ≠ 等量信息”。样本 n=12/方法、有效独立对象 <36、无显著性检验；2025-06-30 C 0.75 vs B 1.17 是明确反例。**“略优于异常排序”的结论被高估。**

### 6.2 前瞻：FXI 单一对象主导

按 `goe/forward_eval.py` 在 DB 副本上复算。**17:02 的 `FORWARD_RETURNS.md` 已新增 `mean fwd 3m ex-top`**：C 7.12% → **2.45%**，把 FXI 集中度显性化；这是对 P1-4 的部分修复。C/B 行与本文复算一致；A 行因 17:01 mapping 重生成已变化（当前 A 1m +0.0025、3m -0.0011），本文不复算 A 的旧值。补充：

| 指标 | C_engine | 备注 |
|---|---:|---|
| mean 3m | +7.12% | 报告值 |
| FXI（X19）3m | +58.46% | 单一对象 |
| FXI 对均值的贡献 | **4.87pp** | 7.12 的 ~68% |
| 剔除 FXI 的 mean 3m | **+2.45%** | 与 R3 研究审计一致 |
| class-relative 原值 | +2.99% | 报告值 |
| **剔除 FXI 的 class-relative** | **-0.93%** | 低于 B 的 +5.42% |
| beat-class 原值 | 41.7% | 报告 42% |
| **剔除 FXI 的 beat-class** | **36.4%** | B 58.3% |
| 剔除 FXI 的 beat-SPY | 18.2% | 无优势 |

C 的绝对均值仍为正（+2.45%），但相对同类资产为负，且命中率低于 B。**17:02 的新表已给出 C ex-top 2.45%**，但 class-relative 仍是含 FXI 的 +2.99%，**没有给出 ex-top 的 class-relative（-0.93%）与 FXI 名称**；标题数字仍容易被误读为 edge。**应显式标注 ex-FXI/class-relative 结果，或降级为“一个描述性观察”。** P1（研究证据表述，已部分修复）。

## 7. 文档 / 测试 / DB 一致性（17:07 时点）

审计期间文档在并行更新，以下区分“已更新”与“仍未同步”：

| 文档/声明 | 文档值 | 当前 DB/代码 | 状态 |
|---|---|---|---|
| `FINAL_ACCEPTANCE.md:11` 测试 | 137 offline | **157 collected / exit 0** | ❌ 旧 |
| `FINAL_ACCEPTANCE.md:51-52` 扫描 | 1,511；1 invalidated / 5 excluded | **1,506；2 invalidated / 4 excluded** | ❌ 旧 |
| `FINAL_ACCEPTANCE.md:54` top-3 | SPY 0.606 / DXY 0.593 / N225 0.548 | **current 17:09 只有 DXY/N225 两个 watch；OPP-0001 low 0.6034 是分数第一；OPP-0004 QQQ low 0.5142** | ❌ 旧 |
| `TEST_RESULTS.md:14` | 121 passed | **157** | ❌ 旧 |
| `TEST_RESULTS.md:90` | `make test # 89 passed` | **157** | ❌ 旧 |
| `TEST_RESULTS.md:60` 扫描 | 1,506；3/2/2/4 | **17:09：2 watch / 3 low / 2 invalidated / 4 excluded** | ❌ 旧（2/4 数字旧） |
| `audit/VALIDATION_RESULTS.md:20` | 137 passed | **157** | ❌ 旧 |
| `audit/VALIDATION_RESULTS.md:29` | 2 invalidated / 4 excluded；DXY/N225/DAX | 2/4 一致；**DAX 已不在 current 11** | ⚠ 部分旧 |
| `audit/EXECUTION_STATE.md:15` | 121 passing | **157** | ❌ 旧 |
| `audit/EXECUTION_STATE.md:16` | 1 invalidated / 5 excluded | **2 / 4** | ❌ 旧（同文件 26-27 行已是 2/4，内部矛盾） |
| `audit/EXECUTION_STATE.md:21` | 137 tests | **157** | ❌ 旧 |
| `PROJECT_SPEC.md:78` 扫描 | 1,506 | 一致 | ✅（本轮已更新） |
| `PROJECT_SPEC.md:84` 测试 | 157 | 一致 | ✅（本轮已更新） |
| `PROJECT_SPEC.md:83` handoff | `partial` / `not_completed:partial` | **refused / not_completed:refused** | ❌ 旧 |
| `README.md:153` handoff | `OPP-0001: ok rc=0` | **refused / exit 2 / not_completed:refused** | ❌ 假成功 |
| `README.md:169` | 97 offline | **157** | ❌ 旧（同文件 214 行写 157，内部矛盾） |
| `README.md:214` | 157 | 一致 | ✅（本轮已更新） |
| `README.md:90-92` 示例 | OPP-0001 0.67 watch QQQ；OPP-0002 0.66 watch VIX | 当前候选完全不同 | ❌ 旧示例 |
| `README.md:209` / `PROJECT_SPEC.md:87` 提交 | `1a7a5f5` / main | HEAD `6755d34` + uncommitted | ❌ 旧 |
| `docs/VALIDATION.md:41` | 通过标准“或预期异常家族” | 代码 `detection_ok=det_hit>0`，family 不再参与 | ❌ 旧 |
| `docs/VALIDATION.md:51-57` | 7/7 “当前代码”；M01 supported / M11 weak | artifact 06:30Z；M01/M11 unsupported | ❌ 旧 |
| `docs/SCORING.md:77-89` | OPP-0001 0.606 watch；evidence 0.639 | **0.6034 low_priority；0.6017**；缺 policy-age cap 说明 | ❌ 旧 |
| `docs/SCORING.md:20` catalyst | ≤10=1.0；≤30=0.6；≤90=0.2 | 代码同日=0.6；31–90=0.2 | ⚠ 同日未同步 |
| `config/scoring.yaml:56` catalyst | 1.0 if 0≤days≤10；0.6 if 0≤days≤30；else 0.1 | 代码同日 0.6；31–90 0.2 | ❌ 配置旧 |
| `TEST_RESULTS.md` 分文件表 | 12 文件合计 104 | **15 文件合计 157** | ❌ 旧（漏 test_readiness_handoff/status_lifecycle/time_semantics；scoring 7→11、pipeline_e2e 2→5、data_integrity 11→20、anomalies 6→7） |
| `audit/RESEARCH_QUALITY.md:17-21` | C 1.250 / B 1.229 | 17:06 r3：C 1.188 / B 1.521 / A 1.312 | ❌ 旧且被反证 |
| `audit/research_quality_ratings_r3.json` | 17:06 独立 r3，36 objects | 未被 `RESEARCH_QUALITY.md`/`goe/evaluation.py` 引用 | ⚠ 未归档/未合入 |
| `audit/FORWARD_RETURNS.md` | C 7.12 / ex-top 2.45 / class +2.99 | ex-top 已加；class ex-top -0.93 未加 | ⚠ 部分修复 |

测试实测：`pytest tests -m "not network"` 收集 **157**；多次运行退出码 0（由于仓库 `addopts=-q` 与额外 `-q` 叠加，pytest 的汇总行被抑制；per-file collect 合计 157）。`TEST_RESULTS` 的 121/89 和 `FINAL_ACCEPTANCE` 的 137 都不是当前值。

## 8. NEW issues（按严重度）

> P0 = 数据损坏/系统性假结论；P1 = 会改变对外结论、核心 gate 或验收证据；P2 = 局部错误/可审计性缺口；P3 = 文案/口径。  
> “NEW”指本轮新量化或新证据；prior R3 已指出但本轮仍成立的标注“R3 遗留”。

### P0

**无。** 未发现把未来价格写入历史特征、伪造数据或系统性假结论。11-13 的美/德/欧盘中 bar（fetched 15:05Z）在 FeatureBuilder 中被正确丢弃（SPY/DAX/SX5E 的 last 为 11-12；JP/CN 为 11-13），readiness 也使用 completed bar。

### P1

| # | 问题 | 证据 | 影响 |
|---:|---|---|---|
| P1-1 | **16:45 artifact 的 DAX watch 是本地 driver 缺失造成的伪残差** | 16:45 代码 `expectations.py` 无 DE local_fx、DE market 自 skip 到 SPY；z 2.419→本地 1.352；17:02 新代码 z=1.401；**17:09 重扫 DAX 已不在 11 候选** | **已在 current artifact 修复**；保留为历史 |
| P1-2 | **Handoff 问题含下游禁用词，拒答至少部分是 A 自己触发** | `exporter.py:125-127` 含 `投资建议`/`仓位`；受控实验 answered→out_of_scope；实跑 refused/exit 2 | 审计归因错误；A 可修；`refused` 不能全记在 B 头上 |
| P1-3 | **盲评 artifact 已不一致；新 r3 评分把引擎排最后** | 17:01 input/mapping 重生成（X21 heating oil→VVIX 1m -25.74%），ratings_round2 14:26 未重评；17:06 `research_quality_ratings_r3.json` 对新 mapping：A 1.312 / B **1.521** / C **1.188**，P@3 0.417 vs 0.750；旧 C 9/12 mechanism vs A 1/12、B 3/12 | 旧 1.250/1.229 失效；“引擎略优”被当前 r3 反证，C 甚至低于两个朴素基准 |
| P1-4 | **前瞻 +7.12% 的 68% 来自 FXI；ex-FXI class-relative 为负** | FXI +58.46%，贡献 4.87pp；17:02 新表已给 C ex-top +2.45%，但未给 class-relative ex-top（-0.93%）、beat-class 36% | 标题数字仍易过度；无稳健优势（部分修复） |
| P1-5 | **16:45 queue priority 1 是过期政策叙事，与报告/CLI 矛盾** | 16:45 queue OPP-0001 0.6034 priority 1；**17:09 queue 只有 DXY/N225 两条 watch**；旧 RT-0001/0005 文件残留 | **已在 current artifact 修复**；旧文件残留 P2 |
| P1-6 | **最终 replay artifact 早于当前 validation 代码；7/7 只是 OR 口径** | artifact 06:30Z vs validation.py 16:12；3/7 只中 1 个 detector；gold 仅 price shock；mechanism_ok 全 false；无 placebo | “严格 case-entity 7/7”被高估 |
| P1-7 | **README/最终验收仍写假成功/旧数字** | README `ok rc=0`；FINAL 1511/137/1 invalidated/5 excluded；docs VALIDATION M01 supported | 验收文档不可作为签收依据 |
| P1-8 | **current top-3 只有 2 个 watch；分数第一仍是过期政策 low** | 17:09：watch 只有 DXY/N225；无第三席；OPP-0001 low 0.6034 仍分数第一；OPP-0004 是 QQQ 政策 low 0.5142 | “三条独立前瞻 top-3”不成立；排序语义仍会误导 |

### P2

1. **top-3 事件候选没有自动失效检查**：OPP-0002/3 `invalidation_checks=[]`；OPP-0004 现在是 QQQ 政策 low，也无检查；文本“事件日期已过且无显著反应”不可执行；只有 OPP-0006/0009 有检查。`apply_lifecycle` 的 45 天过期是唯一兜底。
2. **DXY 的“2 项异常”含 0.036 噪声**：near_high 0.867 是趋势，`relative_strength_extreme` 0.036 基本是噪声；标题“已出现异常变化”过强。
3. **SPY 的 driver=RSP，QQQ 下符号翻转**：z -2.506 vs +1.489；gap 0.4074 vs 0.139；不是稳健的政策预期差。
4. **跨资产快照混用 as-of**：SPY 到 11-12、N225/CN 到 11-13；报告 1 个月 -9.7%（N225）与 gap 用的 -10.22%（11-12）不一致，正文不展示 residual 日期。
5. **非美资产的 deep gate 结构性不可达**：N225 gap confidence=0.40 < 0.50；没有 CFTC/valuation 的非美权益只能靠 residual 0.4，永远不能 deep；0 deep 是数据覆盖的结果，不只是“质量不够”。
6. **invalidated 永久且只查首个 trigger**：`_trigger_invalidation_checks(tx.triggers[:1])`；OPP-0006 用 1m z 0.963 触发，1d z 11-13 为 0.576；如果 1m z 越过 1.0，候选也不会复活；文本中的“敏感度符号翻转”未实现。
7. **derived all-parent 映射不完整**：硬编码 6 对，无 gold_dollar/gold_real_yield；黄金 case 的 `cross_asset_divergence` 在 case entities 上不可观测，只能靠 price shock 通过。
8. **反证太通用**：top-3 都只有 1 条“事件可能已被定价”，没有同日 cross-asset/本地 driver 替代解释；惩罚系数也低。
9. **catalyst 配置/文档未同步**：`config/scoring.yaml:56` 仍写 else 0.1、0≤days≤10=1.0；`docs/SCORING.md:20` 未写同日 0.6。
10. **分数先于状态做 theme/exposure cap**：过期政策候选（0.6034）可在同 theme 挤掉前瞻 event 候选；当前 SPY 是潜在案例（未证实当前已发生）。
11. **测试/扫描数字在多份文档间不一致**：见 §7；`TEST_RESULTS` 分文件表合计 104 vs 157。
12. **research_quality 有效独立样本 <36**：C 有 2 个 SPY 对象（不同日期），A/B/C 之间也有重复实体；报告已承认，但 Precision/mean 未给置信区间。

### P3

1. `as_of_report` 标签是 CFTC **发布日**（11-07），不是报告日（11-03）；字段名易误读。
2. `config/scoring.yaml` 的 `economic_impact` 公式含机制置信度；代码在 `mechanism.id=None` 时不乘 0.4+0.6×conf（OPP-0001/0002 的 0.68 来自 0.6×1.0+0.4×0.2）。口径差异小，但文档应说明。
3. `status_thresholds.archive_below` 未被代码读取；`min_expectation_gap`/`min_deep_research_data_quality` 只在代码默认值，不在 config gates。
4. README/PROJECT_SPEC 的 GitHub 提交仍是 `1a7a5f5`，HEAD 是 `6755d34`；文档示例 OPP-0001 0.67 watch QQQ 已过期。

## 9. 最强反证 / 最强正面证据

**反证（反对当前签收）：**

1. **Current top-3 只有 2 个 watch**：17:09 只有 DXY/N225；没有第三条独立前瞻线索；按分数第一仍是 OPP-0001 **low** 0.6034（28 天前政策），OPP-0004 是 QQQ 政策 low 0.5142。N225 是唯一强线索，DXY 低信息。**“top-3 独立前瞻”不成立。**
2. **Handoff**：干净政策问题 `answered`；加“不构成投资建议”或“仓位”即 `out_of_scope`；A 的问题同时含两者。refused 不是纯外部限制。
3. **盲评/前瞻**：旧 C 的 +0.021 是机制信息不对称；17:06 的 r3 评分对新对象给出 C **1.188** vs B **1.521** / A 1.312，C 最后；+7.12% 的 68% 是 FXI，ex-FXI class-relative -0.93%、beat-class 36%。没有研究 edge，当前 r3 甚至是负 edge。
4. **分数与状态/队列语义**：queue 已修（17:09 只 DXY/N225），但 **OPP-0001 low 0.6034 仍是分数第一**；报告“其他记录”第一行仍是过期政策。按分数排序的消费者/报告读者仍会被误导。
5. **7/7**：3/7 只中 1 个预期检测器；gold 只中通用 price shock；mechanism_ok 全 false；无负控制；artifact 早于代码。

**正面（不应被上述否定）：**

- **N225** 是真实、稳健的日本本地冲击：11-06 日本独跌（同日 SPY/EEM 上涨），TOPIX 本地 driver 下 z≈-2.5、5 年回撤分位约 3.1%；这是本轮唯一经得起横截面与本地 driver 复核的 top-3。
- **PIT/数据**：盘中 bar 被 features/readiness 正确丢弃；宏观 PIT 保留历史；1506 异常、5 机制、11 候选在 DB/report/export 三处一致；扫描事务/回滚测试通过。
- **17:09 修复验证**：DAX 已从 11 候选消失（TOP-3 不再有假 watch）；queue 只剩 DXY/N225 两个 watch，low_priority 不再占 priority 1。**P1-1/P1-5 的代码 + 重扫修复成立。**
- **评分公式**：11/11 可复算；权重和 1.0；policy-age cap、31–90=0.2、同日=0.6、过去事件=0.1、excluded re-arm 都有代码/测试。
- **Handoff 语义**：refused、exit 2、task `not_completed:refused`、event `ia_research_not_completed` 全部正确；没有假成功。
- **测试**：157 项收集、exit 0；数据/生命周期/readiness/导出回归测试在。

## 10. 六门能否签收（工程 vs 研究）

| 门 | 工程层 | 研究/验收层 | 结论 |
|---|---|---|---|
| G1 数据/PIT | PASS（complete-bar、PIT、content hash；P2 跨资产 as-of 混用） | PARTIAL（top-3 日期混用） | 工程可；研究留 P2 |
| G2 扫描/机制 | PASS（1506、5、事务、测试） | PARTIAL（0 supported；机制 confidence 低） | 工程可；研究不可 |
| G3 评分/状态/队列 | PASS（公式/caps/excluded；17:09 queue 2 条） | **FAIL**（current top-3 只有 2 个 watch；#1 分数仍是 stale policy low；无 deep；非美 deep 结构性不可达） | 工程可；研究不可 |
| G4 历史验证 | PASS（harness/测试） | **FAIL**（stale artifact；7/7 弱；无 placebo；gold 通用） | 研究不可 |
| G5 研究质量/前瞻 | N/A | **FAIL**（17:01 盲评 mapping/input 与 14:26 ratings 不一致；17:06 r3 评分 C 1.188 < B 1.521 / A 1.312；FXI；ex-FXI class 负） | 不可 |
| G6 Handoff/文档 | PASS（parser/exit/task） | **FAIL**（问题触发 OOS；无 ok_valid；README 假成功；docs 旧） | 研究不可 |

**总：工程层可继续（PASS WITH ISSUES；无 P0；P1 主要是研究/验收，不是代码阻断）；研究/验收层 NO-GO。17:02 的代码 + 17:09 重扫已修复 P1-1（DAX）与 P1-5（queue），这是实质进展；但 current 17:09 只有 2 个 watch（#1 分数仍是 stale policy low）、17:01 盲评 mapping 与 14:26 ratings 不一致、17:06 r3 把引擎排最后、handoff 仍 refused、validation artifact 仍旧、README/最终验收仍假成功。因此六门不能作为一个整包签收。**

建议的验收措辞（若必须签）：

> 工程：ACCEPTED WITH ISSUES（157 tests；scan success；PIT；parser；17:09 rescan/queue 已验证 DAX/queue 修复；P2 文档/旧 RT 文件/盲评 artifacts 修复前不得宣称“研究已验证”）。
> 研究：NOT ACCEPTED。current 17:09 只有 DXY/N225 两个 watch，N225 是唯一强线索；DXY 低信息、#1 分数是 stale policy low、7/7 仅 OR、盲评新 r3 评分 C 最后、前瞻无 edge、handoff 无 ok_valid。修复/验证 P1-2/3/4/6/7/8 后，再在**冻结代码 + 冻结 DB + 重评盲评**上做最终 replay 与 handoff。

## 11. 复现

```bash
# 只读复算
.venv/bin/python - <<'PY'
# 见本报告 §3 的独立公式；使用 data/goe.db + config/scoring.yaml
PY

# 测试（157 collected；exit 0；汇总行被 -qq 抑制）
.venv/bin/python -m pytest tests -m "not network" -q

# handoff（/tmp DB 副本）
cp data/goe.db /tmp/goe_r3_handoff.db   # 或 sqlite backup
.venv/bin/python -m goe.cli handoff --db /tmp/goe_r3_handoff.db \
  --ia-path ~/investment-agent-dev --limit 1 --out-dir /tmp/goe_r3_ia

# 历史 replay（/tmp 输出；本轮 17:07 仍未完成，已停止）
.venv/bin/python -m goe.cli replay --cases --out /tmp/goe_r3_validation
```

## 12. 限制

- 审计期间文档/工作树在并行修改：16:52–17:00 是 docs；**17:01–17:09 是代码/测试/盲评/重扫**（`expectations.py` 本地 driver、`exporter.py` queue、`forward_eval.py` ex-top、`tests/test_exporter.py`；`research_quality_input/mapping` 17:01；`research_quality_ratings_r3.json` 17:06 untracked；`scan-...52b0e7` 17:09）。本文以 17:09 的 DB/报告/export、17:02 的代码和 17:00 的文档为准；**17:09 artifact 已包含代码修复**，但 17:01 盲评 mapping 与 14:26 ratings 未重评（17:06 r3 是另一套评分，未合入报告），签收前必须再冻结一次。
- current-code replay 在 17:07 仍未完成，已停止；因此“7/7 仍成立”只是代码分析预期，不是本轮实测。
- 未对真实 investment-agent 做模型/人工研究质量评审；handoff 只验证语义/退出/任务状态。
- 盲评是单一 LLM rater、n=12/方法；本文只做描述统计，不做显著性检验。17:01 后盲评 artifacts 不一致；17:06 r3 是 untracked 的独立评分，若作为最终 rater，`RESEARCH_QUALITY.md` 的 1.250 必须作废并改写。
- 未修改任何代码/配置/测试/数据/git；`/tmp` 的 DB/handoff/replay 文件不属于仓库。
