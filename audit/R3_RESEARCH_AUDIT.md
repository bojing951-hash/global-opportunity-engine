# ROUND 3 — 独立全球宏观/量化研究审计（PM 视角）

- 审计对象：`HEAD 6755d34` + 未提交的 `goe/features.py`、`goe/readiness.py`、两个测试文件；`as_of 2026-11-13`。
- 数据/报告：`data/goe.db`，扫描 `scan-20261114T064041Z-5f4fdf`（2026-11-14 06:41 UTC 生成；报告 `reports/report_2026-11-13.md`）。审计时间 2026-11-14 16:03 HKT。
- 方法：只读 SQL/JSON + `.venv/bin/python` 独立复算（FeatureBuilder、expectations、forward_eval、评分公式、案例回放产物）；`goe handoff` 只在 `/tmp` 的数据库副本上运行，B 输出也在 `/tmp`，未写仓库运行库；唯一写入本文件。未改代码、配置、数据、测试或 git。
- **快照限制（重要）**：报告/DB 的扫描是 06:41 UTC；未提交的 readiness 修复 mtime 15:52 HKT、features 16:02 HKT，且审计期间仍有并发修改，因此报告不是“当前 worktree 代码”的重新扫描产物。我在审计时用当时 worktree 代码独立构建 feature，SPY/QQQ/XLP/EEM/N225/DAX 的 gap、残差、市场驱动与 DB 记录逐项一致；但 features.py 随后在 16:02 HKT 又被修改，严格说 top-10 仍需重扫后才能称为“当前代码的 top-10”。本文所有排序/分数以 DB/报告为准，并标明这一点。

## 1. 判决

**工程管线：可运行；研究方法与 PM 可用性：FAIL。**

无 P0（本次未发现前视、伪造数据或把未来价格写进历史特征）；数据是点到点（PIT）的。问题不在“跑不跑得通”，而在：

1. **当前 top-10 不是 10 个独立的研究机会。** 3 个 watch、2 个 low_priority、1 个 invalidated、4 个 excluded；全池 11 个中有 5 个 excluded。`deep_research = 0`。top-3 是“重要资产 + 一次大价格冲击”的三种叙事，不是三个独立的宏观现象；top-10 里至少 5 个直接或间接来自 11-05 的全球风险冲击/随后的反弹。
2. **top-1 是一个追溯性叙事，不是事前机会。** OPP-0001 的“催化”是 2026-10-16 的 BIS 政策利率**数据可用日**（月频观测 2026-09-01），距 as_of 28 天；真实决议日不在库中，且至少早于 10-16。11-05 SPY -4.41%、11-09 +2.37% 是跨资产同日大跌/反弹（global risk-off 形态；触发未在库中）；把它读成“政策未被定价”是方向反了——大跌本身就是“正在定价”的证据，不是“未定价”的证据。
3. **top-2 是日历 + 趋势，不是异常。** DXY 的 0.867 分来自“near 1-year high”（趋势），第二条“异常”强度 0.036；事件是 21 天后的就业数据；预期差只有 47% 覆盖的仓位代理，无法观察一致预期。
4. **top-3 的现象真实但归因陈旧。** N225 1 个月 -9.7%、5 年回撤分位 3.1%，这是真实且重要的；但 BoJ 的“催化”同样是 10-16 的 BIS 可用日，且 11-06 -5.96% 更像全球风险冲击/科技回撤；机制只是 0.30 的通用“政策→流动性→风险溢价”链，没有检验。
5. **7/7 历史回放的“严格 case-entity”有改进，但仍可被绕过。** 当前 7 个案例的 `mechanism_ok` 全部为 false；SVB 只命中 3 个预期检测器中的 1 个（credit_stress，且是 HYG/IEF 派生序列），gold 只命中 price_return_shock（cross_asset_divergence 没有在 case 实体上命中）。案例通过条件是“任一预期检测器 **或** 任一预期 family + 任一相关候选”；family 里的 `price` 几乎必然命中，且没有负面/安慰剂案例。
6. **盲评与前瞻的证据不支持“研究优势”。** 盲评 C 1.250 vs B 1.229（+0.021，约一个对象一个标准 1 分）；2025-06-30 C 0.75 vs B 1.17。前瞻 C +7.12% 的均值被 FXI 单一对象（+58.46%）贡献约 4.67pp；剔除 FXI 后 +2.45%，且 C 的 beat-class 42% 低于 B 的 58%。文档已诚实披露“不稳健”，但标题数字仍容易被误读。
7. **A→B 语义正确，但不是成功交付。** 在 DB 副本上跑 `handoff --limit 1`：`OPP-0001` 返回 `not_ok rc=0 semantic=refused`，CLI exit 2，任务 `not_completed:refused`。B 的报告是 `out_of_scope`（17 条 L2 观点、0 条 L1 事实、L3/L4 未产出）；A 的问题没有再要“买卖建议/赔率”，B 的拒绝是外部能力边界（零模型 intent gate 只支持 4 类问题），不是 A 又在问建议。

值得肯定的修复（避免只列问题）：residual “当前”已从 10-30 采样相位改为 11-12 最新共同日（lag 1）；过去事件不再拿 catalyst 1.0；OPP-0006 的 invalidation 对“仍在当前扫描”的候选也会执行；A→B 已能把 `out_of_scope` 记为 `refused` 而不是 `partial`；`RESEARCH_QUALITY.md`/`FORWARD_RETURNS.md` 对 2025-06-30 的失败和“无稳健 edge”是诚实披露的。这些是实打实的改进。

一句话：**系统能生成“值得看一眼的线索”，但当前 top-10 不是“值得占用 PM 研究预算的 10 个问题”；top-1/top-2 尤其名不副实。**

## 2. Top-10 表

> 分数为 `score`（研究优先级，不是预期收益）。`excluded`/`invalidated` 也在表中，因为报告把它们放进了“候选池”；PM 不应把它们当作可执行研究队列。

| # | 候选（代码） | 状态 / 分数 | 真实现象？ | 主要缺陷 |
|---:|---|---:|---|---|
| 1 | OPP-0001 SPY 政策重定价 | watch 0.6056 | 11-05 全球冲击真实；政策叙事弱 | 事件是 BIS 可用日 10-16（非决议日）、28 天前；20 日失效窗口已到；残差是 SPY vs RSP 的风格价差，不是政策预期差；催化仅 0.10 |
| 2 | OPP-0002 DXY 就业数据前 | watch 0.5927 | 美元近高真实；不是异常 | near_high 0.867 + 0.036 噪声；事件 21 天后；gap 仅仓位 0.175/47%；无一致预期/期权；典型日历+趋势 |
| 3 | OPP-0003 N225 BoJ 政策 | watch 0.5477 | 回撤真实（5 年分位 3.1%） | BoJ 事件同样是 10-16 可用日、28 天前；11-06 大跌更像全球风险冲击；机制 0.30 无检验；无自动失效 |
| 4 | OPP-0004 DAX ECB 前 | low_priority 0.5194 | 高位趋势真实；不是异常 | near_high 0.762；事件 34 天但 catalyst 只有 0.10（文档写 31–90 天 0.20）；DAX 残差用 SPY 而非 SX5E/EUR；距 watch 仅 0.0006 |
| 5 | OPP-0005 USDJPY 机制失效 | low_priority 0.4775 | 汇率趋势真实；“机制失效”是测试问题 | 失败检验是无条件相关，不是 carry 的条件性检验；conditional 检验 n=29 未计入；资产 1 个月仅 +1.2%；无自动失效 |
| 6 | OPP-0006 EEM/VIX 期限 | invalidated 0.4387 | EEM 下跌真实；触发是波动正常化 | VIX3M 1m z=0.963（11-13）在 [-1,1] 内，自动失效已触发；但只检查第一个 trigger、永久失效；仍留在 top-10 报告 |
| 7 | OPP-0007 TAIEX 超跌 | excluded 0.3792 | 1 个月 -9.7% 真实；但已反弹 | 唯一异常是 11-09 **+4.9% 上涨**日；标题却写“价格异常下跌”；方向错配；距 low 门槛仅 0.0008 |
| 8 | OPP-0008 QQQ 超跌 | excluded 0.3738 | 1 个月 -5.6% 真实；但已反弹 | 异常是 11-09 **+3.5% 上涨**日；gap 0.013；FOMC 0.6 催化与“超跌”无关；距 low 门槛 0.0062 |
| 9 | OPP-0009 XLY 过度乐观 | excluded 0.3455 | 1 个月 +8.0% 真实 | `anomalies=[]`、anomaly_strength=0；“过度乐观”没有异常/盈利/资金流证据；gap 0.40 仅来自残差 |
| 10 | OPP-0010 ChiNext 超跌 | excluded 0.3377 | -44.4% 回撤真实 | `anomalies=[]`、anomaly_strength=0；gap 0.06；中国本地估值/盈利缺失；repricing=1.0 只是 200 日线距离；无法区分价值陷阱与超跌 |
| — | OPP-0011 XLK 超跌 | excluded 0.3346 | -8.7% 1 个月真实 | 同样无异常；与 QQQ/科技主题重复；不计入 top-10 |

补充：全池 11 个 = watch 3 + low_priority 2 + invalidated 1 + excluded 5；`deep_research=0`。top-10 中 4 个 excluded + 1 个 invalidated，即一半是终态记录，不是研究队列。

## 3. 逐个候选：八问

| 候选 | 真实？重要？ | 独立证据？ | 宏观机制？ | 可观察预期差？ | 竞争解释排除了吗？ | 可证伪？ | 为什么排在这里？ |
|---|---|---|---|---|---|---|---|
| OPP-0001 SPY | 11-05 -4.41% 真实；SPY 重要 | BIS 政策 + 同一次价格异常；不是独立证据 | 通用链 0.30；无检验 | gap 0.407，但残差是 SPY vs RSP；仓位 30.1 分位不是极端 | 全球风险冲击/科技回撤/月末，未排除 | 无自动检查；20 日窗口已到，文本条件无法判定 | 最大单异常 0.9205 + SPY 重要性 + gap；催化仅 0.10 |
| OPP-0002 DXY | 美元近高真实；重要 | 价格 + CFTC 仓位；没有预期数据 | 事件链 0.30；无检验 | 0.175/47%，仅仓位 68.7 分位；无 residual | 利差/避险/趋势，未排除 | 事件前无检查；事件后无条件过期检查 | 21 天就业 catalyst 0.6 + near_high + 美元重要性 |
| OPP-0003 N225 | -9.7%、5 年回撤分位 3.1% 真实；重要 | BIS + 同一价格异常；日经/TOPIX 残差是本地相对收益 | 通用链 0.30；无检验 | gap 0.314/40%，仅 residual；z=-2.68 | 全球风险冲击/科技/日元 carry，未排除 | 无自动检查；20 日窗口已到 | 最深 drawdown 0.9841 + 日本重要性 + 本地残差 |
| OPP-0004 DAX | +5.8%、接近高点真实；中等重要 | 价格 near_high + ECB 日历；无独立证据 | 事件链 0.30；无检验 | gap 0.245/40%，residual z=+2.42，但市场驱动是 SPY | 欧洲风险偏好/美元/利率，未排除 | 无自动检查 | 价格高位 + ECB 事件 + 重要性；catalyst 0.10 使其卡在 watch 线下 |
| OPP-0005 USDJPY | +1.2% 真实；中等重要 | 机制检验失败 + 价格；负面证据 | M14 unsupported 0.05；失败的是无条件相关 | gap 0.326/47%，仅仓位 84.9 分位；与“失效”论点无关 | 测试设定错误/样本期/非线性，未排除 | 无自动检查；失效条件手工 | 异常 0.657 + 重要性 + 仓位 gap；低优先级 |
| OPP-0006 EEM | EEM -5.0% 真实；重要 | M12 mixed 0.55 + 价格；机制自身 2 项失败 | M12 有 contemporaneous corr，但 lag=0、非因果 | gap 0.123/40%，residual z=-1.96 | EM beta/全球风险，未排除 | `VIX3M z∈[-1,1]` 自动失效已触发 | 机制 + EEM 异常；但已被自己的条件否掉 |
| OPP-0007 TAIEX | -9.7% 真实；中等重要 | 价格 + residual；无机制 | 无 | gap 0.251/40%，residual z=-2.44 | 台湾科技/全球半导体周期，未排除 | 有检查（相对基准再跌 8%/信用恶化），但方向证据错配 | 1 个月跌幅 + residual；excluded 仅差 0.0008 |
| OPP-0008 QQQ | -5.6% 真实；重要 | 价格 + residual；无仓位/估值 | 无 | gap 0.013/40%，z=-1.55，刚好过阈 | 科技/AI 回撤、全球风险，未排除 | 有检查，但“超跌”证据是上涨日 | 重要性 + FOMC 0.6 + 极弱 gap；excluded 仅差 0.0062 |
| OPP-0009 XLY | +8.0% 真实；中等重要 | residual + 价格；无异常 | 无 | gap 0.40/40%，z=3.34 | 消费/盈利/资金流，未排除 | 有检查；但“过度乐观”未被任何异常确认 | gap + repricing；anomaly=0 |
| OPP-0010 ChiNext | -13%、-44% 回撤真实；中等重要 | 价格 + residual；无机制 | 无 | gap 0.061/40%，z=-1.73 | 中国增长/政策/盈利下修，未排除 | 有检查；但“超跌”无异常/估值确认 | repricing 1.0（200 日线距离）+ 经济影响；anomaly=0 |

### top-3 深挖（PM 会追问的三件事）

**OPP-0001（SPY）**：报告写“政策变化窗口内资产异常：down，强度 0.92，可用日 11-05”。但 11-05 是 SPY -4.41%、QQQ -6.49%、EEM -5.79% 的同一天；11-09 又反弹 +2.37%/+3.54%/+2.87%（跨资产同日 risk-off 形态；触发未在库中）。这不是“政策未被定价”，而是一次跨资产同日 risk-off 及反弹（触发未在库中）。SPY 的 gap residual 是相对 RSP（等权）的 -5.3%、z=-2.51；经济含义是“大盘/科技相对等权跑输”，不是“政策预期差”。把这段读成 policy repricing，是把风格价差当宏观叙事。

**OPP-0002（DXY）**：DXY 1 个月 +1.1%、距 1 年高点 -0.03%，这是趋势/位置，不是异常。`drawdown_extreme near_high` 的 0.867 衡量“接近高点”，不是“异常变化”；`relative_strength_extreme` 的 0.036 基本是噪声。候选的全部信息是“美元近高 + 21 天后就业数据”。在没有一致预期/期权隐含分布的情况下，系统无法回答“就业数据会不会造成预期差”；它只能回答“有个事件”。这是典型的低信息日历候选。

**OPP-0003（N225）**：这是 top-3 中唯一有真实、重要现象支撑的：1 个月 -9.7%，距 1 年高点 -15.5%，5 年回撤分位 3.1%，residual -6.2%/z=-2.68（相对 TOPIX、JPY、UST、DXY）。但归因“BoJ hike”是 10-16 的 BIS 可用日；11-06 N225 -5.96% 与跨资产 risk-off 同日，且最新一周 +6.5%，说明这是一次全球 risk-off/反弹，不是单向的 BoJ 重定价。它值得研究，但应改写成“日本大盘在 global risk-off 中的超额下跌/反弹”，而不是“BoJ 政策未定价”。

## 4. 方法论逐项复核

### 4.1 催化：过去事件不再 1.0，但仍有 31–90 天空档和同日/时区问题

当前 11 个候选的 catalyst 分数与天数：

| 候选 | 催化日 | 距 as_of 天数 | catalyst | 说明 |
|---|---|---:|---:|---|
| OPP-0001 | 2026-10-16 | -28 | 0.10 | 过去事件，已不再 1.0（修复有效） |
| OPP-0002 | 2026-12-04 | +21 | 0.60 | 21 天，落在 ≤30 |
| OPP-0003 | 2026-10-16 | -28 | 0.10 | 过去事件 |
| OPP-0004 | 2026-12-17 | +34 | 0.10 | **应为 0.20（文档）**；落到 else |
| OPP-0005 | 2026-12-18 | +35 | 0.10 | 同上 |
| OPP-0006 | — | — | 0.10 | 无催化 |
| OPP-0007/9/10 | — | — | 0.10 | 无催化 |
| OPP-0008 | 2026-12-09 | +26 | 0.60 | 26 天，落在 ≤30 |
| OPP-0011 | — | — | 0.10 | 无催化 |

- **没有候选再拿到 1.0**；过去日期现在都是 0.10，修复有效。没有发现当前数据下的时区导致的 1.0。
- **新问题（P2）**：代码/配置只有 `≤10 → 1.0`、`≤30 → 0.6`、`else → 0.1`，没有文档 `docs/SCORING.md` 写的“≤90 → 0.2”。OPP-0004（34 天）和 OPP-0005（35 天）因此是 0.10 而不是 0.20。按文档修正，OPP-0004 从 0.5194 升到 0.5294，**刚好跨过 watch 0.52**；OPP-0005 从 0.4775 到 0.4875（仍 low）。这是一个会改变状态标签的文档/代码不一致。
- **同日/时区（潜在）**：日历只有日期，没有发布时间；`days == 0` 会命中 1.0。若扫描发生在 BLS 8:30 ET 或 FOMC 14:00 ET 发布之后，事件其实已经过去，但代码仍给 1.0。当前候选没有同日事件，所以未触发；这是 latent，不是当前错误。
- **语义问题（P1，见 §5）**：OPP-0001/0003 的“潜在催化”仍是过去事件；报告把它列在“潜在催化”下，读起来像前瞻事件，实际是已发生的 BIS 数据可用日。

### 4.2 失效：OPP-0006 确实触发；但只检查一个 trigger、且是永久失效

- OPP-0006 的自动检查是 `US_VOL_VIX3M` 的 `return_z_3y`（1m）在 `[-1, 1]`。独立复算：11-12 = **0.6619**，11-13 = **0.9633**；11-13 仍在区间内，因此检查成立，状态 `invalidated`、原因“自动失效条件被触发（invalidation_checks；仍在当前扫描中）”。**这次 invalidation 确实执行了**，不是 R2 的“对 current 直接 continue”。
- 但实现仍然太粗：
  1. 只检查 `tx.triggers[:1]`（`goe/opportunities.py:1042`）。OPP-0006 的 trigger 里还有 VIX、VVIX、MOVE；VIX3M 回到常态就整体失效，哪怕 VVIX/MOVE 仍极端。
  2. 失效文本说“或资产对触发变量的滚动敏感度符号翻转”，但 `invalidation_checks` 只做 `|z|<1`，没有敏感度符号检查。声明的可证伪条件只实现了一半。
  3. 1m return z 对 3–12 个月 horizon 的 regime 太短：OPP-0006 的 trigger 是 11-09 VIX3M 单日 -15.2% 的“波动正常化”，不是 regime；用 1m z 很容易在几天内触发。**太容易失效**，因为它本来就不该由单日冲击生成。
  4. `persist_drafts` 把 `invalidated` 当 terminal；`apply_lifecycle` 对 terminal 直接跳过。失效后不会因为新的触发重新激活；同一个 fingerprint 永远不会回到 watch。对 regime 候选这是**太严格**（一次性枪毙）。
- **事件候选和 mechanism_breakdown 没有自动检查**：OPP-0001/0003/0005 的 `invalidation_checks=[]`。OPP-0001/0003 的文本是“事件后 20 个交易日内未显著重定价/政策撤回”，但事件日不是决议日，且 20 日窗口在 as_of 附近已到；系统无法自动判断。这是“可证伪”声明与实际执行的缺口。
- **R2 遗留但当前更严重**：`excluded` 也被当成 terminal（`goe/opportunities.py:1481`、`:1505`）；4 个 top-10 excluded 候选（TAIEX/QQQ/XLY/ChiNext）即使未来分数改善，也不会被自动提升。文档说 `status_source=auto` 可以升级/降级；这与代码矛盾。

### 4.3 expected_direction 矛盾过滤：XLP 被正确丢弃，但规则太钝

- XLP（必需消费）1 个月 **+5.8%**（独立复算 0.0581），残差 z=+1.85、R²=0.320；M05（能源—通胀—利润率）对 XLP 的 `expected_direction=down`，但 M05 confidence 只有 **0.14**（1 项支持 / 4 项不足或失败；oil→CPI 相关 **-0.26**，期望 +1，近端符号一致率 3%）。代码 `direction_conflict and tx.confidence < 0.5 → continue`，所以 XLP 被静默丢弃（`goe/opportunities.py:866-873`）。
- **在 XLP 这个具体案例上，过滤是合理的**：M05 很弱，且价格方向与机制相反；强行把 XLP +5.8% 说成“能源通胀链的重定价窗口”是错的。若保留，粗算分数约 0.40（low_priority），不会进入 top-3；所以它没有丢掉一个高质量机会。
- **但规则太钝**：
  - 只看 1 个月收益，阈值 1%，不看统计显著性/异常强度；`+1.01%` 与 `+0.99%` 会得到相反结论。
  - 不看 horizon：1w、1-3m、3-12m 的机制都用同一个 1m 收益。
  - 对 `confidence ≥ 0.5` 的方向冲突不丢弃，只在 deep 分支 cap；也就是说，一个 0.55 的混合机制可以在方向相反时仍进入 top-10，只是不能 deep。这可能是**太弱**。
  - 它是静默 `continue`，不记录“因为方向冲突被丢弃”。这会让审计看不到被过滤的对象；建议至少写入 candidate/event log，或把“机制与价格相反”路由到 `mechanism_breakdown`/“机制失效”而不是消失。
- 结论：**当前数据下没有证据说它过度激进地丢掉了好机会；但规则本身既不够可解释，也不够对称。** XLP 是“弱机制 + 反向价格”的正确丢弃；真正需要保留的是“强机制 + 反向价格”的矛盾研究，而当前 `confidence≥0.5` 分支只做 deep cap，没有把矛盾变成研究问题。

### 4.4 预期差：当前行是 11-12，SPY 自身驱动已移除，但换成了 RSP 风格代理；本地驱动只覆盖部分市场

独立复算（当前代码、as_of 2026-11-13、history_start 2020-05-13）：

| 资产 | gap | 覆盖度 | 组件 | residual z | R² | 市场驱动 | 经济解释 |
|---|---:|---:|---|---:|---:|---|---|
| SPY | **0.4074** | **0.75** | positioning 0.3977 + residual 0.6705 | -2.506 | 0.739 | **RSP** | 大盘 vs 等权，不是政策预期 |
| QQQ | **0.0131** | 0.40 | residual 0.0326 | -1.549 | 0.856 | SPY | 成长 vs 宽基 |
| XLP | **0.0930** | 0.40 | residual 0.2324 | +1.849 | 0.320 | SPY | 防御 vs 宽基；R² 低，残差噪声大 |
| EEM | **0.1228** | 0.40 | residual 0.3069 | -1.960 | 0.673 | EFA | EM vs DM |
| DAX | 0.2452 | 0.40 | residual 0.6129 | +2.419 | 0.530 | **SPY** | 德国 vs 美国；不是本地驱动 |
| N225 | 0.3143 | 0.40 | residual 0.7857 | -2.679 | 0.793 | TOPIX + JPY | 本地大盘/汇率，较合理 |

- **时间戳**：residual 的 `as_of_return_date` 是 **2026-11-12**，`lag_days=1`；不是 R2 的 10-30 相位。修复有效。
- **SPY self-driver**：直接 self-driver 已移除（`bench=None` 时跳过 SPY）；但 `region_market["US"] = [SPY, RSP, QQQ]`，SPY 最终用 **RSP** 作市场驱动（`goe/expectations.py:156-171`）。所以“SPY 自身驱动”确实没了，但 residual 变成 SPY vs RSP 的**规模/风格价差**；它测的是“大盘相对等权”，不是“政策意外”。这是 top-1 gap 的核心误读。
- **本地驱动只覆盖部分市场**：JP 有 TOPIX + JPY；CN/HK 有本地指数 + CNY；EEM 用 EFA；US 用 SPY/RSP。**DE/EA/UK/FR 都没有本地替代指数**（DAX 的 region_market 只有 DAX 自己，跳过自身后回退 SPY；SX5E、FTSE、CAC 同理），DAX 甚至没有 EUR 驱动（`local_fx` 有 EA/UK，但没有 DE/FR）。因此 OPP-0004 的 residual +7.35%、z=+2.42 是“DAX vs S&P + 美元 + 美债”，不是“DAX vs 欧洲/欧元”。这会系统性放大欧洲候选的 gap。
- **confidence 的语义**：`confidence = 可用权重/适用权重`，是**覆盖率**，不是统计置信度；`value = 加权均值 × 覆盖率`，缺一个代理会被乘两次。结果是：top-10 里 7 个只有 0.40 覆盖（单一 residual），2 个 0.467（单一 positioning），只有 SPY 0.75（positioning + residual）。`deep_research` 的 `confidence ≥ 0.5` 门槛意味着：**除 SPY 外，其他资产在当前数据下几乎不可能 deep**；这不是研究价值判断，是数据覆盖结构。
- **估值维度长期死亡**：US_CAPE 最后 2023-09（1169 天），所有美国宽基/成长的 valuation 都是 null；0.25 权重从未可用。XLP/QQQ 的 gap 只有 residual；SPY 只有 positioning+residual。
- **残差可解释性**：QQQ = 成长 vs 宽基；XLP = 防御 vs 宽基（R² 0.32，68% 未解释，残差可能是噪声）；EEM = EM vs DM；SPY = 大盘 vs 等权。它们都是**相对价值残差**，不是“市场无法解释的宏观预期差”。R² 门槛 0.10 太低，XLP 0.32 也能过；这会把风格轮动当宏观背离。

### 4.5 evidence_quality / breadth / score：公式能对上，但与文档语义不一致，且排序被“异常+重要性”主导

OPP-0001 复算：

```
0.22×0.9205 + 0.18×0.68 + 0.20×0.4074 + 0.12×0.2573
+ 0.10×0.10 + 0.06×1.0 + 0.06×1.0 + 0.06×0.6392
= 0.203 + 0.122 + 0.081 + 0.031 + 0.010 + 0.060 + 0.060 + 0.038
= 0.6056
```

- 与 DB 的 0.6056 一致；权重与 `config/scoring.yaml` 一致。**算术没有错，问题是权重/语义。**
- **排序不是由预期差驱动**：top-3 的 `anomaly_strength + economic_impact` 分别贡献 0.325/0.313/0.317，占总分 **53%/53%/58%**；gap 只贡献 0.035–0.081（6%–13%）；catalyst 0.010–0.060。top-1/top-2 本质是“重要资产 + 大异常”，top-3 是“重要资产 + 深回撤”。这解释了为什么 top-10 看起来像“最大波动/最大异常”榜，而不是预期差榜。
- **evidence_quality 0.6392 的构成**：`0.45×0.70 + 0.25×(2/3) + 0.15×0.30 + 0.15×(1-0.25) = 0.6392`。但：
  - `tier` 用的是 `d.data_quality.score`（0.70），不是文档/配置说的“来源层级”（`goe/opportunities.py:1338`）。
  - `independent` 是“不同 source 字符串数/3”，不是独立数据源；`mechanism` 与 `mechanism_stats` 会被算成 2 个来源，但它们是同一机制证据。
  - 反证据惩罚是 `0.25×条数`，封顶 3 条；1 条强反证据只让 evidence_quality 降 0.0375，总分只降 **0.00225**（约 0.4%）。所以“反证据进入评分”在数值上几乎是装饰。
  - 配置写 `0.45×source_tier`，代码用 data_quality；文档写 `0.15×反证据惩罚`，代码是 `0.15×(1-penalty)`；这是语义不一致，不是纯格式问题。
- **breadth**：OPP-0001 的 economic_impact 0.68 = `0.6×1.0 + 0.4×(1/5)`（mechanism id 为空，`mechanism_assets=1`）。OPP-0006 的 0.592 = `0.6×0.5 + 0.4×[5/5×(0.4+0.6×0.55)]`。文档 `docs/SCORING.md` 说“广度 × 机制置信度”，代码是“× (0.4+0.6×conf)”；config 与代码一致、文档不一致。
- **timing_window 恒为 1.0**：每个 archetype 的 horizon 都由 `ARCHETYPE_HORIZON` 设置，所以 `timing_window` 永远是 1.0，等于给每个候选 **0.06 的固定加分**。去掉它：OPP-0001 0.5456、OPP-0002 0.5327、OPP-0003 0.4877；top-3 会变成 2 watch + 1 low。阈值（0.52/0.68）是按“含 0.06 固定分”校准的，这使分数不可跨版本比较。
- **deep gate 仍未真正执行**：0 个候选达到 0.68；`min_expectation_gap`/`min_expectation_confidence`/`min_deep_research_data_quality`/机制 0.40+2 FDR 都只在 `if d.status == "deep_research"` 内；`require_mechanism_or_divergence` 仍未被读取。这是 R2 遗留，当前仍未修。

### 4.6 7/7 严格回放：case-entity 是改进，但仍不是强验证

当前 `reports/validation_cases_20261114T063037Z.json`：

| 案例 | 预期检测器命中 | 预期 family 命中 | mechanism_ok | 相关候选 | 结论 |
|---|---:|---|---|---|---|
| COVID | 3/3 | cross_asset | false | SPY 信用/仓位/背离 | 宽窗口，容易 |
| RATE_SHOCK | 3/3 | price, macro | false | SPY 信用/政策/仓位 | 宽窗口，容易 |
| UK_GILT | 2/2 | price | false | EWU 政策（low） | 政策动作，非 LDI 机制 |
| SVB | **1/3** | macro, cross_asset | false | TLT VIX（low）、XLF 政策（low） | 只有 credit_stress 命中；无信用候选 |
| JAPAN_CARRY | 3/3 | price, cross_asset | false | N225 政策、USDJPY 机制失效 | 机制 unsupported |
| CHINA_RALLY | 2/3 | price, industry | false | CSI300 政策、KWEB 机制失效 | 政策动作，非机制 |
| GOLD | **1/2** | price | false | gold 机制失效 | cross_asset_divergence 未命中；靠价格+breakdown |

- 严格 case-entity 规则确实比“全市场检测器”有意义：SVB 不再因为全市场 296 条异常里随便命中而通过；`detectors_hit` 只算 case 实体/派生序列。
- 但通过条件仍是 `det_score>0 or fam_score>0` 且 `relevant_candidate`：
  - **SVB 只有 1/3** 预期检测器；`families_on_case_entities` 同时有 `macro` 和 `cross_asset`，即使 credit_stress 没命中，也会因 family 通过。
  - **gold 只有 1/2**；`cross_asset_divergence` 没在 case 实体上命中，只有 `price_return_shock` + `price` family。
  - 7/7 的 `mechanism_ok` **全部 false**；通过完全不以机制成立为条件。把“7/7”读成“机制/传导验证成功”是过度解读。
  - **没有负面/安慰剂案例**：任何高波动窗口都会命中 price/drawdown/vol；7/7 只证明“能在危机窗口找到某种异常”，不证明区分度。
- **derived 映射过度包容**：`derived = {syn for syn, parents in derived_parents.items() if parents & entities}`（`goe/validation.py:90`）是 **any-parent**，不是 all-parent。SVB 有 HYG/IEF/XLF/VIX，于是同时把 `CREDIT_RISK`（HYG/IEF）、`equity_credit`（SPY/HYG）、`stock_bond`（SPY/IEF）、`VIX_TERM`（VIX）算作 case 实体；其中 `equity_credit`/`stock_bond` 只需一个父资产即可进入。`CREDIT_RISK` 由 HYG/IEF 派生，算 SVB 的信用证据是合理的，但它不是独立于 case 资产的新数据；`equity_credit`/`stock_bond` 可能把无关的全市场股债/信用波动带进来。
- **SVB 的“相关候选”是 TLT 的 VIX 和 XLF 的政策候选，不是信用/银行候选**；`credit_stress` 只贡献 detection，不贡献 relevant candidate。gold 的相关候选是通用的 mechanism_breakdown，而不是 `cross_asset_divergence`。这说明 7/7 的“命中”与“研究候选”不是同一件事。
- **是否有 case-specific hardcoding？** 未发现按 `case_id` 的 `if` 分支；`derived_parents` 是硬编码白名单（注释点名 SVB），`cases.yaml` 的 expected 检测器/实体是人工挑选。gold 通过的是通用 `mechanism_breakdown`，不是“gold special case”；这是相对好的部分。但 `derived_parents` 仍是代码级例外，且 any-parent 过宽。

### 4.7 mechanism_breakdown：当前只 1 个，但质量低，门槛宽

- 当前只有 **OPP-0005**（USDJPY/M14），cap=2；所以“泛滥”暂时不成立。
- 但资格门槛很宽：任意 unsupported 机制，只要有 ≥2 个 `n>=100` 的失败检验 + 主资产 1 个月 |收益|≥3% 或有一条异常，就能生成。当前 5 条激活机制中 3 条 unsupported（M01/M09/M14）；M01/M09 也有 ≥2 个 n>=100 的失败检验。当前只出现 1 个，更可能是 theme/score 去重，不是质量门在挡。
- **“失败检验”本身不是现象**：M14 的失败项是 USDJPY–SPY 相关 +0.04、USDJPY–VIX -0.06、JP_POLICY_RATE–USDJPY -0.02，都是**无条件相关**；而 carry unwind 是条件性/尾部现象。真正更相关的 conditional 检验（VIX>25 后 USDJPY 21 日 +0.9%、命中率 38%）n=29，`substantive` 要求 n>=100，被排除。于是候选的“3 项核心检验失败”是**测试设定问题**的候选，不是“结构性变化”的证据。
- 资产侧：USDJPY 1 个月仅 +1.2%，异常是 relative_strength 0.657（1m，z=3.97）；这不是一个重要的宏观现象。gap 0.326 来自 positioning 84.9 分位，与“机制失效”论点无关。
- 失效条件：`invalidation_checks=[]`；文本“60 个交易日内核心滚动相关恢复原符号”没有自动检查。可证伪性弱。
- 结论：**当前不泛滥，但低质量；cap 2 是唯一防泛滥机制。** 若机制目录扩大、theme 更分散，这个 archetype 可以稳定产出“负检验伪线索”。需要求：结构性断点/样本外检验、条件性检验、资产侧显著性，而不是“相关性过弱”。

### 4.8 A→B：拒绝是外部的，任务状态正确，但不是成功交付

在 DB 副本 `/tmp/goe_r3_audit/goe.db` 上运行（未写仓库库）：

```bash
.venv/bin/python -m goe.cli handoff \
  --db /tmp/goe_r3_audit/goe.db \
  --ia-path /Users/cast/investment-agent-dev \
  --limit 1 --out-dir /tmp/goe_r3_audit/runs
```

结果：`OPP-0001: not_ok rc=0 semantic=refused elapsed=9.31`，CLI 返回 **exit 2**；任务 `not_completed:refused`；事件 `ia_research_not_completed`。

B 的报告：`run_ok=true`，`S8_grounded_qa` 的 `data.status=out_of_scope`；17 条 L2 `VIEW-* [INSUFFICIENT_EVIDENCE]`，L1 `rows=[]`，L3/L4 `produced=false`；S1 `metrics=[]`（问题没有词面命中任何指标），S4/S5 跳过。B 的拒答文本说“该问题属于投资建议/交易类越界范围”，但 A 的问题明确写“不构成投资建议；不要给买卖建议、收益承诺或目标价”，且只要求事实核对、条件情景、数据缺口。**所以：A 的问题没有再要建议；B 的拒绝是外部的（零模型 intent gate 只支持 4 类问题），不是 A 问了建议。**

问题在于：A 仍把 B 当通用 deep-research 端点；问题里的“预期分布/抢跑定价/二阶影响”不在 B 的 4 类 registry 里，S1 零映射，S4/S5 跳过；B 的 17 条证据是泛化的 L2 观点，不是研究结论。A 的 parser 现在能区分 `refused`（不是 `partial`），这是对的；但“handoff 语义正确”不等于“交付了研究”。如果 B 不拒绝，A 也没有调用 `research-attach` 补 L3/L4；交付仍是事实/观点包。**当前状态：正确的拒绝；不可用的端到端研究路径。**

### 4.9 研究质量 / 前瞻：数字对得上，但“优势”与“标题”被高估

**盲评数字**（从 `audit/research_quality_ratings_round2.json` + mapping 独立复算）：

| 方法 | n | mean | Precision@3（实为 12 个对象中均分≥1.5 的比例） |
|---|---:|---:|---:|
| A 最大价格变动 | 12 | 1.0625 | 0.0833 |
| B 最大异常分 | 12 | 1.2292 | 0.3333 |
| C 引擎 | 12 | 1.2500 | 0.4167 |

- 与 `audit/RESEARCH_QUALITY.md` 的 1.062/1.229/1.250、0.083/0.333/0.417 一致；per-date 表也一致（2025-06-30 C 0.75 vs B 1.17）。
- **“Precision@3”是命名误导**：它不是 top-3 precision，而是 12 个对象的阈值通过率；文档括号里解释了，但表头仍容易被误读。
- **卡片不是 treatment-blind**：方法段说“不含引擎状态/假设”，但事实卡包含 `mechanisms`（id/status/confidence/role）；当前输入里 C **9/12** 有机制字段，B 3/12，A 1/12。C 的 beyond_price 优势（0.833 vs B 0.5）至少部分来自“C 卡更有机制结构”，不是独立的研究价值。R2 已指出，当前 RQ 仍未把它作为限制写清楚。
- **+0.021 不是优势**：约等于一个对象一个标准 1 分；RQ 自己说“不是稳定优势”，这是诚实的。C 在 `real_market_change` 上 1.25，低于 A 1.917/B 1.5；C 的胜点在 beyond_price/data_sufficiency，不在“现象更真实”。
- **重复实体**：PL、CSI300、USDJPY 三对跨方法重复；有效独立样本 <36，RQ 已承认。36 个对象全局打乱/匿名编号是修好的；但“n=12/方法”仍是小样本，无置信区间。

**前瞻数字**（独立复算，与 `FORWARD_RETURNS.md` 完全一致）：

| 方法 | mean 3m | median 3m | excess vs SPY | beat SPY | excess vs class | beat class |
|---|---:|---:|---:|---:|---:|---:|
| A | +0.04% | -1.91% | -6.52% | 25% | +2.96% | 50% |
| B | +5.09% | -0.03% | -1.47% | 33% | +5.42% | 58% |
| C | +7.12% | +4.67% | +0.56% | 25% | +2.99% | **42%** |

- **C 的 +7.12% 被一个对象主导**：FXI（X19）+58.46%；剔除 FXI 后 C 均值 **+2.45%**，中位数 +4.67%。FXI 对均值的贡献约 **4.67pp / 7.12pp = 66%**。文档写了“受少数大涨对象影响”，但没有给 ex-outlier；标题“+7.12%”仍容易被读成引擎的稳定优势。
- **C 的资产构成不均衡**：C 12 个对象里 9 个股票（6 equity_etf + 3 equity_index），2 FX，1 商品，且 SPY 出现两次；A 是 6 商品 + 2 波动 + 2 行业 + 1 crypto；B 是 4 FX + 3 指数 + 2 固收 + 2 ETF + 1 商品。C 的“excess vs SPY / beat SPY”与 A/B 不可直接比；文档没有披露这层构成。
- **C 的 beat-class 42% < B 58%**：这是 C 的负结果，文档保留了，应该肯定；但“mean 最高”与“hit rate 更低”同时成立时，不应把 mean 作为主标题。
- 没有成本、仓位、方向调整；n=12；结论应保持“描述性、不证明 edge”。这一点 `FORWARD_RETURNS.md` 写得比 `RESEARCH_QUALITY.md` 更谨慎。

## 5. NEW issues（按严重度）

> “NEW”指本轮新发现或本轮新量化；R2 已指出且仍未修的，标注“R2 遗留”。下面的 P1/P2 中，P1 #1/#3/#4 与 P2 #5–#11 多数是本轮新量化或新证据；R2 已有同类判断的，我在条目里明确写“R2 遗留/当前更严重”，不把旧问题冒充新问题。

### P1

1. **事件候选的“过去事件 + 循环论证”仍未解决（OPP-0001/0003）。**
   - `US_POLICY_RATE` 月频观测 2026-09-01 由 3.625→3.875，`available_date=2026-10-16`；候选把 10-16 当事件日。真实决议日不在库中，至少早于 10-16。
   - 候选的支持证据是“事件窗口内价格 down 0.92”；但 11-05 SPY -4.41%、11-06 N225 -5.96%、11-09 反弹，这是一次全球风险冲击/反弹。**政策事件后的下跌是“正在定价”的证据，不是“未定价”的证据**；系统没有事件前预期/意外度量，无法区分两者。
   - 20 个交易日失效窗口以 10-16 计已在 as_of 附近到期；以真实决议日计更早。两个候选的 `invalidation_checks=[]`，文本条件无法自动执行。
   - 影响：top-1/top-3 的核心故事不可检验；这是当前排序最大的研究质量问题。
2. **`excluded` 被当成 terminal，4 个 top-10 候选永久冻结。**
   - `goe/opportunities.py:1481`：`terminal = existing["status"] in ("expired", "invalidated", "excluded")`；`:1482` 只在非 terminal 时更新状态；`:1505` `apply_lifecycle` 直接跳过 excluded。
   - 影响：OPP-0007/0008/0009/0010（以及 OPP-0011）即使后续 gap/机制改善，也不会被自动提升；与 `docs/SCORING.md` 的“status_source=auto 可升级/降级”矛盾。当前 top-10 有一半是“永不复活”的记录。
3. **预期差 misattribution：SPY 用 RSP 作市场驱动，DAX/EA/UK/FR 回退 SPY。**
   - SPY：`resolve_benchmark=None`，跳过 SPY 后选 **RSP**；residual -5.32%、z=-2.506 是“大盘 vs 等权”的风格价差，不是政策预期差。top-1 gap 0.4074 的核心就是它。
   - DAX：`region_market["DE"]` 只有 DAX 自己，跳过自身后回退 **US_EQ_SPY**；没有 EUR 驱动；residual +7.35%、z=+2.419 是“德国 vs 美国”，不是“德国 vs 欧洲”。EA/UK/FR 同理。
   - 影响：top-1 和 #4 的 gap/分数被错误归因；欧洲候选的 residual 系统性放大。
4. **gap 覆盖度结构使跨候选比较失真，且几乎只有 SPY 能 deep。**
   - 7/10 top-10 的 gap confidence = 0.40（只有 residual）；2 个 0.467（只有 positioning）；只有 SPY 0.75（positioning+residual）。`value = 加权均值 × 覆盖率` 把“缺数据”乘两次；`deep_research` 要求 confidence≥0.5，意味着非 SPY 候选在当前数据下几乎不可能 deep。
   - 这不是“研究价值低”，是“数据覆盖结构”；用它排序会把“美国宽基有仓位数据”当成“更有预期差”。同时 valuation 0.25 权重因 CAPE 2023-09 长期不可用，实际只有两维。

### P2

5. **catalyst 31–90 天档缺失（文档/代码不一致，改变状态）。** 代码/配置只有 10/30/else；`docs/SCORING.md` 写 ≤90→0.2。OPP-0004 34 天拿 0.10，按文档 0.20 会从 0.5194→0.5294（watch）；OPP-0005 0.4775→0.4875。当前 #4 的 low_priority 是文档/代码差异造成的。
6. **失效检查只覆盖第一个 trigger，且 permanent；事件/breakdown 没有检查。** `tx.triggers[:1]`；OPP-0006 只查 VIX3M，不查 VIX/VVIX/MOVE；文本的“敏感度符号翻转”未实现；event/mechanism_breakdown `invalidation_checks=[]`。`invalidated` terminal 无 re-arm。
7. **7/7 的 case-entity 仍可被 OR/family/derived 绕过。** 15/19 预期检测器命中；SVB 1/3、gold 1/2；`mechanism_ok=0/7`；`detection_ok` 允许“任一 detector 或任一 family”；`price` family 几乎必中；`derived_parents` any-parent 过宽；SVB 的相关候选是 TLT VIX/XLF 政策，不是信用；无负面/安慰剂案例。
8. **mechanism_breakdown 质量低。** 资格=2 个 n>=100 失败检验 + 3% 移动；M14 的失败是无条件相关，conditional 检验 n=29 被排除；资产 +1.2% 不是重要现象；`invalidation_checks=[]`。当前只 1 个，但 M01/M09 也满足失败数量，cap 2 是唯一防泛滥。
9. **evidence_quality 语义与文档/配置不一致。** `tier = data_quality` 而非 source tier；`independent` 数 source 字符串；1 条反证据只值约 0.002 分；config 写 source_tier，文档写“反证据惩罚”，代码是 `1-penalty`；breadth 文档写“×机制置信度”，代码是 `0.4+0.6×conf`。
10. **“top-10”不是研究队列。** 3 watch + 2 low + 1 invalidated + 4 excluded；`deep_research=0`；报告把 excluded/invalidated 与 watch 混在一张“候选池”表里。对 PM 来说，真正可研究的只有 3 个 watch，且 top-2 是日历/趋势。
11. **研究质量/前瞻的表述高估。** 盲评 C 卡 9/12 有机制（A 1/12、B 3/12），与方法段“不含引擎状态/假设”不一致；C +0.021 在噪声内；前进 C +7.12% 的 66% 来自 FXI，ex-FXI +2.45%，beat-class 42% < B 58%；“Precision@3”是阈值通过率。数字本身对得上，问题在标题/可解释性。

### P3

12. **方向错配仍存在（R2 遗留）**：OPP-0007/0008 的 `discovery.what` 写“价格异常下跌”，但 `discovery.anomalies` 是 11-09 的 **up**（TAIEX +4.9%、QQQ +3.5%）；OPP-0009/0010 `anomalies=[]` 却写“价格异常”。这是“异常必要条件”声明与数据的矛盾。
13. **OPP-0006 是报告里的僵尸**：已 `invalidated`，仍出现在 top-10 候选池；建议单列“已失效/仅存档”，不要与 watch 混排。
14. **报告/DB 与工作树不同步**：扫描 06:41 UTC；未提交 readiness 15:52、features 16:02 HKT（审计期间仍在改）；DB `updated_at` 07:58Z。严格结论需要重扫并 pin `scan_id` + artifact hash。
15. **watch/low 的 `status_reason` 为空**；报告表格“其他记录”原因列也空。自动状态没有可读原因，审计时只能看分数。
16. **research_tasks 语义**：OPP-0002–0005 是 `exported`，不是已完成/已研究；`handoff --limit 1` 只跑 OPP-0001。报告“research queue”为空与“5 个 watch+low”并存，容易让读者以为都已交付。
17. **`OPP-0001` 的 `updated_at` 07:58Z 晚于报告 06:41Z**；DB 在审计前被再次触碰。不是代码 bug，但审计需要固定快照。

## 6. Best / worst

**Best（相对最好）：OPP-0003 N225。**
理由：它是 top-3 中唯一同时满足“真实、重要、可测量”的：1 个月 -9.7%、5 年回撤分位 3.1%、residual -6.2%/z=-2.68（相对 TOPIX/JPY/UST/DXY）。它的问题不是现象假，而是叙事错：BoJ 事件是 10-16 的 BIS 可用日，11-06 的下跌与全球 risk-off 同日。若改写成“日本大盘在全球 risk-off 中的超额下跌/反弹，检验 JGB、日元、外资流、TOPIX 相对”，它是值得 PM 花时间的研究对象。当前分数 0.5477 低估了现象、高估了 BoJ 归因。

**Worst（最差）：OPP-0002 DXY。**
理由：它排 #2，但信息量最低：0.867 的“near high”是趋势，0.036 的“relative strength”是噪声；21 天后的就业数据只是一个日历；gap 0.175/47% 只有仓位 68.7 分位，无法观察一致预期；没有 residual。作为“美元近高 + 事件前观察”的 watch 可以，但作为 #2 研究机会名不副实。它比 OPP-0005 更值得点名，因为 OPP-0005 至少被标成 low_priority，而 OPP-0002 占用了 #2 的位置。

**最典型的伪线索：OPP-0005**（把“无条件相关过弱”当成“机制结构性失效”；conditional 检验 n=29 被门槛排除；资产仅 +1.2%）。

## 7. 缺什么证据

**对 top-10 共同缺失：**
- 一致预期/事件 surprise：没有分析师一致预期、期权隐含分布、利率期货隐含路径；当前“预期差”只是仓位/估值/残差代理。
- 事件时间：没有真实决议日/发布时间（FOMC、BoJ、ECB、BLS 的确切 timestamp/timezone）；BIS 月频可用日不能当事件日。
- 事件前价格/仓位路径：无法判断“抢跑定价”还是“事件后反应”；当前 top-1/3 的循环论证正缺这个。
- 本地驱动：DAX 缺 SX5E/EUR，SX5E/FTSE/CAC 缺本地指数/欧元/英镑的完整组合；EEM 缺中国/韩国/台湾本地因子；非美资产缺本地信用利差/估值。
- 估值：US_CAPE 2023-09 后死亡；非美没有估值；0.25 权重长期空转。
- 盈利/资金流：分析师修正、ETF 资金流、期权 skew、空头兴趣、CFTC 期权/OTC 仓位；没有这些，无法区分“超跌”与“盈利下修/价值陷阱”。
- 信用：HYG/IEF 是 ETF 代理，不是 OAS；SVB 的 CREDIT_RISK 是派生序列，不是独立信用数据。
- 期货：连续合约未展期调整；商品候选的“异常”可能是换月跳空（当前只有 roll risk 标记）。
- 因果识别：机制检验是相关性/lead-lag（lag 0 也算“领先”），没有 HAC/结构断点/工具变量；7/7 的 mechanism_ok=0/7 说明机制层没有通过验证。
- 负面控制：7/7 没有“平静期不应触发”的案例；无法证明区分度。
- 人类专家标签：盲评是单一 LLM，无 prompt/模型/对话；n=12；无人类 PM 评分。
- 前瞻稳健性：C +7.12% 受 FXI 单一对象主导；需要 median/ex-outlier、置信区间、成本、资产类分层、重复实体处理。

**对具体候选：**
- OPP-0001：真实 FOMC 决议日/声明/点阵图、事件前 SPY/QQQ 相对定价、期权隐含分布、11-05 全球冲击的分解（AI/科技/宏观）、SPY vs RSP 风格因子。
- OPP-0002：就业数据一致预期/期权隐含、DXY 仓位方向与期权、利差路径、事件前 1-2 周价格路径。
- OPP-0003：BoJ 决议日/声明、JGB 曲线、日元 carry 仓位、TOPIX 相对、外资流、11-06 全球风险冲击分解。
- OPP-0004：ECB 决议日/声明、SX5E/DAX 相对、EUR、欧洲盈利修正、DAX 成分风格。
- OPP-0005：carry 的条件性检验（VIX/日元波动/风险平价）、结构性断点、样本外、USDJPY 期权/仓位。
- OPP-0006：VIX 期限结构全曲线、VVIX/MOVE、EEM 期权/资金流、EM 本地信用；以及“失效后是否允许 re-arm”。
- OPP-0007/0008：台湾/美国科技盈利修正、半导体周期、外资流、期权 skew；确认 11-09 的上涨是反弹还是新信息。
- OPP-0009/0010：XLY/ChiNext 的盈利/估值/资金流、中国本地信用/地产/政策；没有这些，无法判断“过度乐观/超跌”。

## 8. 复现与限制

```bash
# 1) 只读检查
sqlite3 data/goe.db "select scan_id,as_of,status from scan_runs; select opportunity_id,score,status from opportunities order by score desc;"

# 2) 独立复算 gap（当前代码；约 2 分钟）
.venv/bin/python - <<'PY'
from goe.db import Store
from goe.features import FeatureBuilder
from goe.expectations import compute_expectation_gap
fs=FeatureBuilder(Store('data/goe.db'),as_of='2026-11-13',history_start='2020-05-13').build()
for iid in ['US_EQ_SPY','US_EQ_QQQ','US_SEC_XLP','WORLD_EQ_EEM','DE_EQ_DAX','JP_EQ_N225']:
    g=compute_expectation_gap(fs,iid)
    print(iid,g.value,g.confidence,{k:(v.value,v.evidence.get('residual_z'),v.evidence.get('r2')) for k,v in g.components.items()})
PY

# 3) A→B（只写 /tmp）
cp data/goe.db /tmp/goe_r3_audit/goe.db
.venv/bin/python -m goe.cli handoff --db /tmp/goe_r3_audit/goe.db \
  --ia-path /Users/cast/investment-agent-dev --limit 1 --out-dir /tmp/goe_r3_audit/runs
```

限制：
- 没有重跑完整 `goe scan`（会写生产 DB/报告）；当前报告/DB 是 06:41 UTC 快照，未提交 readiness/features 修复在 15:52/16:02 HKT 之后，且审计期间代码仍有并发修改。严格“当前代码”的 top-10 需要一次受控重扫。
- 没有重跑 `no_lookahead_diff` 与完整测试套件；前视判断依据报告/PIT 记录、独立 gap/forward/case artifact 复算，不等于全量代码审计。
- 没有重跑 `goe replay --cases`；使用 06:30:37Z 的正式回放产物。
- 没有独立验证 FOMC/BoJ/ECB 真实决议日、BLS/BIS vintage、CFTC 发布时刻；只能依据 DB 日期/配置滞后推断“BIS 可用日不是决议日”。
- 没有人类 PM 标签；盲评是单一 LLM，无法做显著性。
- 没有修改任何代码；本文件是唯一写入。
