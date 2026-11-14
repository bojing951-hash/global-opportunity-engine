# V2 研究方法审查（独立，只读）

- 审查对象：`architecture/research-v2` 工作树；`evaluation/RESEARCH_EVALUATION_PROTOCOL.md`、`goe/research_evaluation.py`、`goe/research_triage.py`、`evaluation/v2_eval_input.json`、`evaluation/v2_eval_mapping.json`、`evaluation/v2_eval_ratings.json`（19:30 出现）、`evaluation/v2_eval_results.json`、`evaluation/V2_EVALUATION_RESULTS.md`、`audit/RESEARCH_V2_RESULTS.md`。
- 审查方式：只读代码/数据/artifact；对 2021-12-31 做了一次只读复现（见附录 A）。未修改代码、配置、测试、git。
- 盲评结果出现后已核对：46 条 ratings 覆盖 46 个 mapping token，无缺失/多余；分数取值仅 0/1/2；test 的 D 对象为 V19（`GX_FX_USDJPY`），四项 `{1,1,2,2}`，均值 1.5。**我没有推断或补造评分。**

## 结论

**DISCOVERY VALUE: NOT VALIDATED。**

这不是“D 分数不够高”的问题。描述统计上 D 确实最高（D 1.350 / P@3 0.60；C 1.292 / 0.50；B 1.188 / 0.25；A 1.167 / 0.25），test 点估计 D 1.50/P@3 1.00 也高于 A/B/C。但 **test 只有 1 个 D 对象**，`score_ratings()` 的 `validated` 条件要求 test D `n>=3`（`goe/research_evaluation.py:183`），因此在任何评分下都只能得到 NOT VALIDATED。该结论是结构性的，不是评分结论。即使把这一条评到 2.0，也仍然 NOT VALIDATED。

更重要的是：**本 protocol 即使换了更大的 test，也不能把“DISCOVERY VALUE”验证为 VALIDATED**，因为盲卡评的是“资产事实卡”，不是 D 的“研究问题/假设/证伪条件”；且 D 的候选池已被 materiality/gap/mechanism 预筛，而 A/B/C 没有同等预筛。详见 P0-3、P0-4。

## P0（阻断性；不修不能签 VALIDATED）

### P0-1 test 退化为 n=1，决策规则结构性不可满足

- `evaluation/v2_eval_mapping.json` 的 test（2021-12-31）计数：A=3、B=3、C=3、**D=1**；全样本 46 个对象（D 10 个，A/B/C 各 12 个）。
- `goe/research_evaluation.py:183`：
  `validated = bool(dt and all(wins) and dt.get("n", 0) >= 3)`
  test D n=1，故 `validated` 恒为 False；`score_ratings()` 已在 19:36 生成 NOT VALIDATED。`test` 的 “D beats B and C” 两项为 `[true, true]`，但这是 1 个对象的点估计；P@3=1.0 的分母是 1，不是 3。
- 复现（附录 A）：2021-12-31 共 50 条 recent anomalies、2 条机制、5 个候选；只有 1 个非 intelligence（tier B），其余 4 个是 intelligence。D 在该日**无法产出 protocol 要求的 top-3**。
- 影响：test 的均值/P@3 比较无统计意义；任何“D 在 test 上更好”的表述都是过度解读。
- 修法（不调 test）：把 2021-12-31 保留为覆盖失败/探索性结果；另设**冻结后**的 prospective test 窗口（多个月末、完整交易日、每个方法每日至少 3 个候选），在运行前预注册“候选不足即 coverage failure、不进入胜负判定”。不要因为看到 n=1 就把 2021 改到 development（protocol 明确禁止）。

### P0-2 唯一的 test 候选是“gap=0 + 不相关机制 unsupported”的 tier B，且是 near-high 单项

- 只读复现：`B GX_FX_USDJPY ... mat 0.71 gap 0.00 conf True`，rationale 为 `tier B: materiality 0.71, gap 0.00, mechanism_conflict=True, cost=10h`。`gap=0.00` 表示标准驱动已完全解释，按合同“standard drivers do not fully explain the move”不应开“explanatory gap”；它进 tier B 只是因为 `mech_conflict=True`。
- `goe/research_triage.py:152` 把 `status in ("mixed","unsupported","weak")` 全部算作 “mechanism conflict”。该 test 卡片的机制是 `M13_POSITIONING_EXTREMES`，状态 `unsupported`、confidence **0.05**、role secondary；而卡片 `positioning_net_pctile_5y=0.4981`（中性），并不存在“仓位极端”。这是一条**不相关且失败**的机制，却被当成“竞争性解释/未解释缺口”。
- 卡片事实：USD/JPY 1m **+1.9%**，仅 `drawdown_extreme/near_high` 0.86；合同/`contracts/RESEARCH_CONTRACT.md` 明确要求 materiality 是“真实重要变化（不是 near-high alone）”。tier B 的唯一 test 候选恰好是 near-high + 小变动。
- 影响：test 的 D 分数完全由这一个低信息对象决定；即便评到 1.5，也不能代表 D 的常规输出。
- 修法：把“机制不支持”与“存在可区分竞争假设”分开；只有当机制与**该资产该次异动**相关、且触发条件成立时，才能开 gap；`unsupported/weak` 不能单独开 tier；near-high 不能单独过 materiality。用总 expectation gap（positioning/valuation/residual）而不是仅 residual 判断缺口。

### P0-3 被测对象不是 D 的产出：盲卡隐藏了 hypotheses/falsifiers/unknowns/tier

- `evaluation/RESEARCH_EVALUATION_PROTOCOL.md:25-30` 明确：method labels、V1 scores、**V2 tier/rationale and hypotheses are NOT shown**；`goe/research_evaluation.py:33-35` 的 `_v2_fact_sheet()` 只调用 `_instrument_facts()`，即与 A/B/C 相同的“资产事实卡”。D 真正的产出（`ResearchCandidate.card()`：competing_hypotheses、evidence、critical_unknowns、falsification_conditions、decision_impact）在 `goe/research_triage.py:54-68` 存在，但评估没有使用。
- 四项标准里也没有“decision relevance/decision impact”这一项：`real_market_change / beyond_price / falsifiable / data_sufficiency`。协议第 4-5 行问的是 “more valuable, falsifiable, decision-relevant research questions”，但评分只针对资产卡，`decision_impact` 被 hidden。
- 影响：即使 D 得分更高，也只能说“D 选的资产卡看起来更值得研究”，不能验证“V2 生成的研究问题更有价值/更可证伪/更决策相关”。**这是本 protocol 最强的概念失败：outcome 与 treatment 不匹配。**
- 修法：对每个入选对象用**同一中立模板**生成 research brief（事实 + 至少 2 个竞争假设 + 可观测证伪条件 + 未知/数据缺口 + 决策影响），再盲评 brief；或明确把 claim 降级为“资产选择代理”，不要使用 `DISCOVERY VALUE: VALIDATED`。这一步不需要调 test 日期。

### P0-4 D 在“评分维度”上被预筛，A/B/C 没有；比较不是同一候选池

- `goe/research_triage.py:146` 先 `if mat < 0.55: continue`；`:210` 再以 `(not gap_open and not mech_conflict)` 过滤；`:212-217` 用 gap/materiality 阈值分 A/B/C。A/B/C 在 `goe/research_evaluation.py:64-85` 只按各自排序取 top-3，没有 materiality/gap/mechanism 预筛。
- 因此 D 的候选天然是“有机制/有缺口/有重要性”的对象；四项标准里的 `beyond_price`、`falsifiable`、`data_sufficiency` 正好与这些预筛同向。D 的胜出部分可能是**筛选器与评分标准同构**，而不是排序能力。
- 影响：没有 “D-filter-only” 或 “random-within-D-eligible-pool” 基线，无法区分“D 的排序有价值”与“D 只是先筛掉了不可研究的对象”。
- 修法：预注册**共同候选池**，让 A/B/C/D 在同一池上排序；加两个基线：D 的过滤规则 + 池内随机 3 个、D 的过滤规则 + 按简单分数排序。这样无需看 test 结果即可实现。

### P0-5 “pre-registered” 不可审计；test 日期与 LLM 评审的后见知识冲突

- `git status` 显示 `evaluation/`、`goe/research_evaluation.py`、`goe/research_triage.py` 全部为 untracked；protocol 没有 commit hash、没有 `protocol_sha256`、没有 `input_sha256`/`mapping_sha256`。`v2_eval_mapping.json` 只有 splits 与 diagnostics，没有冻结证据。文件 mtime（protocol 18:35、input 19:27、ratings 19:30）只能说明先后，不能防篡改。
- test 是 **2021-12-31**，比 dev（2022-10-31、2024-09-30）与 validation（2023-03-31）都早。V1 的设计/特征历史覆盖 2015-2026（`V1_FREEZE.md` 的数据快照为 2026-11-13），2021 显然在 V1 的设计历史内；称其 “held out from V1/V2 design” 对 V1 不成立，对 V2 也没有设计日志证明。
- 评审是 2026 年的 `independent-llm-v2`（`v2_eval_ratings.json`）。对一个 2021-12-31 的卡片，LLM 已知道 2022-2026 的结果；“No post-as-of knowledge”（protocol:36-38）无法执行。选最早的日期，反而最大化了评审的后见知识。
- 影响：test 的“独立性”只是日期不重叠，不是设计独立/信息独立；无法排除 test 被用于设计或评审被结果污染。
- 修法：在任何评分前 commit 并 hash protocol/code/input/mapping；记录 rater 模型版本、prompt、日期、原始 ratings；test 用冻结之后的未来窗口（LLM 不可能知道结果），或用严格信息隔离的人类专家。不要在 2021 上补做“验证”。

## P1（重要；影响解释/可复现性）

1. **split 只在日期上不重叠，设计上不独立**：dev/validation（2022-10-31、2023-03-31、2024-09-30）正是 V1 盲评 `audit/research_quality_mapping.json` 使用的日期；V1 自己的盲评结果（engine 1.188 < B 1.521、A 1.312，`V1_FREEZE.md`）已在这些日期上产生。V2 规则若参考了这些结果，dev/validation 对 V2 也不是“新”的。test 2021 的唯一性无法证明。
2. **test 日期不是完整交易日**：DB 在 2021-12-31 只有 **116/125** 个 instrument 有价格行；缺失 9 个市场（DAX、SMI、SX5E、IBEX、FTSEMIB、N225、TOPIX、KOSPI、TAIEX，均为 12-31 休市）。test 的横截面因此偏向美国/英国/中国/香港/加密/商品；A/B/C/D 都无法选欧洲/日本/韩国/台湾。dev/validation 均为 125/125。该日期不是可比的“同一 universe”。
3. **PIT 只是“按 as_of 截断”，不是数据 vintage PIT**：2021-12-31 的 `prices.fetched_at` 是 **2026-11-13**；`adj_close`/universe 都是 2026 快照。对历史 as-of，无法排除 2021 之后的复权、修订、成分变化。protocol/代码没有声明这一点。
4. **有效独立样本远小于 46**：46 张卡、**34 个唯一 entity**、38 个唯一 (date,entity)；6 组跨方法完全相同的卡片（V37/V39/V44 都是 2024-09-30 CSI300；V24/V27/V30 都是 2023-03-31 USDJPY；V08/V16 DXY；V03/V15 BTC；V06/V28 CHINEXT；V07/V25 中国券商）。同一张卡被不同方法重复评分，方法均值不独立；`duplicate_rate` 只按 method 内 theme 统计，全部为 0，**漏掉跨方法重复**。
5. **指标/决策规则实现问题**：
   - `precision_at_3`（`research_evaluation.py:163`）实际是“该 method 所有已选对象中 mean>=1.5 的 share”，不是 top-3 precision；D 的 n=10、A/B/C 的 n=12，分母不同；test D 的分母是 1。
   - 一个 `{2,2,2,0}` 的卡片均值为 1.5，会被算作“worthy”，尽管 data_sufficiency=0，与“data sufficiency to start deep research”矛盾。
   - protocol 的 decision rule 要求“no material regression on evidence sufficiency/falsifiability”（protocol:53-54），代码只比较 mean 与 P@3，**没有检查 evidence/falsifiability 回归**。
   - `score_ratings()` 对未匹配 token 静默跳过、不校验分数 0-2/四项齐全、不校验重复 token；46 条评分若缺一条，均值会悄悄变。没有 CI/配对检验/多重比较；strict `>` 在 n=3、P@3 粒度为 1/3 时极易 ties。
   - `duplicate_rate` 是“有重复的 theme 组数”，不是率；D n=1 时恒为 0。
6. **triage 假设/证伪条件不是候选特定的**：`research_triage.py:155-172` 对每个候选生成同一套 H1-H5；`:195-200` 对每个候选生成同一套 4 条证伪条件。具体问题：
   - H3（仓位/资金流）只看 `positioning` component 是否存在；USDJPY 的仓位是 0.498（中性），H3 仍会是 “open”。
   - H1 仅在 `mech_conflict or gap_open` 时 open，否则 “untestable”；这不是假设的可检验性，而是系统数据可用性。
   - 证伪条件里 `相对基准继续同向跑输 < -8% (1m)` 对上涨异动（如 +48.7% 的 CHINEXT、+40.3% 的中国券商）符号不成立；`CFTC 40%-60%` 对没有 CFTC 映射的 ETF/指数不可观测；`机制 60d 符号` 对没有机制的候选不可观测。
   - `competing_hypotheses` 缺少 contract 要求的 `evidence_for`/`evidence_against`（`contracts/RESEARCH_CONTRACT.md`）；`decision_impact` 是固定文案，未评估是否能改变具体仓位/研究决策。
7. **优先级规则并非纯 lexicographic**：`research_triage.py:219-220` 的 `priority_key` 计算后**未使用**；实际排序 `:247-250` 是 `(tier, -materiality, -gap, cost, research_id)`，而 `tier` 本身由硬编码阈值 0.55/0.65/0.2/0.1 分桶。阈值是隐式权重/门槛，不是“无权重”；`distinguishability`、`decision impact` 两个合同 gate 没有实现。`mat<0.55` 在 `:146` 已 `continue`，`:210` 的同一条件为死代码，低 materiality 项也不会以 intelligence 记录。
8. **D 的召回缺口被 protocol 的 “Relevant Recall = NOT MEASURED” 掩盖**：D 的候选只来自 `recent` anomalies（`:104-106`），没有“大价格变动但未触发 detector”的入口。test 的 A 第一名 `US_VOL_VIX` 1m **-44.67%**，卡片 `recent_anomalies=[]`，因此 D 完全看不到它；这是“高价值变动被排除”的具体案例。D 在 test 的产出是 5 个候选中的 1 个，覆盖率 1/50 recent anomalies，protocol 没有任何 coverage 指标。
9. **事实卡是“schema 相同”而非“信息等价”**：A 的排序变量 `return_1m` 在卡上；B 的排序变量 `recent_anomalies` 分数在卡上；D 的 `gap_score`/residual/competition 被隐藏，只显示可能不相关的 mechanism 状态；C 的 V1 score 被隐藏。D 的机制卡更多（10 个 D 中 6 个有 mechanisms，但多为 `unsupported 0.05`），既可能抬高 `beyond_price/falsifiable`，也可能因机制弱而压低；评审无法看到 D 的真正选择理由。
10. **V1 基线不是完全 as-of clean**：`goe/opportunities.py:256-276` 的 `_dq()` 用 `quality_issues.created_at >= datetime('now','-120 day')`；当前 DB 有 18 条 2026 年创建的 quality_issues。C（V1）在 2021/2022/2023/2024 的评分会读到这些 2026 年的质量惩罚，属于未来信息进入基线（方向不定）。此外 C 在 `research_evaluation.py` 用 8 年 history 构建 fs，而 V1 自己的盲评 `goe/evaluation.py` 用 6 年；C 不是严格复现 V1 冻结基准。
11. **单一 LLM 评审 + 无人类标签 + 无一致性**：`v2_eval_ratings.json` 的 rater 为 `independent-llm-v2`；46 条有 note，但无第二评审、无 inter-rater reliability、无人类仲裁。protocol 允许这种降级，但只能支持 exploratory，不能支持 VALIDATED。
12. **artifact 可复现性/漂移风险**：`write_blind_input()` 没有 CLI 入口，`v2_eval_input.json` 是一次性调用生成；mapping/ratings 没有 input hash；V1 已经发生过“input/mapping 17:01 重生成、14:26 ratings 未重评”的 P1（`audit/R3_FINAL_QA_RESEARCH.md` §6.1）。V2 在 19:27 input、19:30 ratings、19:36 results 的时间顺序上目前自洽，但没有冻结 hash，无法防止同类漂移。

## P2（次要/清理）

- `build_candidates` 在 `research_evaluation.py:88` 与 `:98` 各调用一次（diag 重复计算，慢且可能不一致）；`diag["v2_candidates"]` 只数截断后的非 intelligence。
- `priority_key` 死代码；`if mat < 0.55` 死条件；`H3` 的 `components.get("positioning", None) is not None` 对“有 component 但 value=None”也判 open。
- `recent_anomalies` 用 `tail(5)` 依赖 detector 输出顺序；`observed_phenomenon` 对 NaN `return_1m`/`ddpct` 会格式化成 `nan%`；`research_cost` 小时数几乎恒定；`evidence` 把 anomaly 标成 `observed_fact`、把 mechanism status 标成 `statistical_association`，分类不严谨。
- protocol 自身不一致：`:42` 说 “a method's 12 selected objects”，`:59` 说 “4 selected/method/date”，实际 3/date；D 只有 10 个对象，test 只有 1 个。
- `tests/test_research_v2.py:47-69` 的决策规则测试是重言式：`assert res["discovery_value"] in ("VALIDATED","NOT VALIDATED")`，不检验 n=1、不检验 strict 比较、不检验 evidence/falsifiability 非回归；也没有 fact-card 等价、匿名化、D 独立于 V1 的测试。
- contract 要求 `A/B/C/D evaluation IDs` 与 `competing_hypotheses.evidence_for/against`，`ResearchCandidate` 未实现；`v1_score` 只 attach，未证明 tier 对 V1 不变（当前代码确实不用 V1 排序，但无测试守护）。
- mapping 与 input 同目录；若 rater 是能读仓库的 agent，mapping 可直接暴露 method/date。protocol 说 mapping separately stored，未做访问隔离。

## D 候选：3 个相对最佳 / 3 个相对最差（不是盲评分数）

说明：没有用 ratings 来挑选，也不推断分数；以下只依据卡片事实、tier/rank 与 triage 合同做定性判断。D 的完整 hypotheses/falsifiers 不在盲卡里，所以“最佳”也可能被隐藏信息推翻。

### 相对最佳

| token | as_of | entity | 可观察事实 | 判断 |
|---|---|---|---|---|
| V34 | 2022-10-31 | CN_EQ_CSI300 | 1m -9.0%、3m -17.4%、12m -28.0%；drawdown 0.56 百分位；M01/M04 两条机制（均 unsupported 0.05） | 真实、大幅、跨月的中国风险资产下跌；竞争假设（政策/信用/美元）清晰；可用价格、信用代理、政策事件证伪。是 D 中最好的“真变化 + 可研究”对象。 |
| V16 | 2022-10-31 | US_FX_DXY | 12m +18.5%；vol regime expansion 1.0；CFTC 仓位 0.158（偏轻）；M01 机制 unsupported 0.05；1m -0.5% | 美元 regime 变化有宏观重要性；仓位偏轻 + 波动扩张提供可检验问题；缺点是 1m 变化小、机制弱。 |
| V07 | 2024-09-30 | CN_SEC_SEC | 1m +40.3%、3m +41.2%；近高；vol 0.89；3 条异动（price shock 1.0、relative strength 0.75、near_high 0.98）；无机制 | 极强的真实政策型重定价；可研究“政策/资金流/基本面”竞争假设；但卡片只有价格，beyond-price 证据弱。 |

（V06 CHINEXT +48.7% 也属于强变化；但无机制、且与 A 的 V28 完全重复，故列为次选。）

### 相对最差

| token | as_of | entity | 可观察事实 | 判断 |
|---|---|---|---|---|
| V19 | 2021-12-31 | GX_FX_USDJPY | **tier B**；mat 0.71、**gap 0.00**、conflict=True；1m +1.9%；near_high 0.86；仓位 0.498（中性）；M13 unsupported 0.05 | 唯一的 test 候选；near-high + 小变动，按合同不应单独作为 materiality；gap=0，靠一个不相关且 confidence 0.05 的机制进 tier B。是“低信息候选获得 tier B”的直接证据。 |
| V03 | 2023-03-31 | CR_BTC | 1m +20.4%；near_high 0.89；仅 M14_JAPAN_CARRY_UNWIND（secondary, unsupported 0.05）；无仓位 | 涨幅真实，但机制与 BTC 不相关且失败；“机制冲突”是假缺口；卡片没有可区分的竞争假设。 |
| V21 | 2023-03-31 | US_SEC_XLK | 1m +10.3%、3m +21.5%；vol 0.445、drawdown 0.458（中位）；anomaly 仅 0.27；无机制、无仓位；D rank 1 | 卡片信息很薄，只有普通板块反弹；作为该日 D 的第一名，tier A/B 的“可研究性”在卡上不可见。具体 tier 未记录在盲 artifact，需以 triage 输出复核。 |

（V04 DIA 1m +14.0%、无机制、仅相对强度 0.66，是另一个“价格-only”候选，可视为 worst 的候补。）

## 能否由本 protocol 验证 DISCOVERY VALUE？

**不能。** 三点：

1. **当前执行**：test D n=1，`n>=3` 硬门槛使 VALIDATED 不可能；这是 `NOT VALIDATED` 的直接原因。该结果已在 `evaluation/v2_eval_results.json` 中生成，描述统计不作为验证。
2. **测量对象**：盲卡是资产事实卡，D 的问题/假设/证伪条件/未知/决策影响被隐藏；评的是“资产像不像值得研究”，不是“V2 的问题是否更有价值/可证伪/决策相关”。即使 D 均值更高，也不能支撑 `DISCOVERY VALUE: VALIDATED`。
3. **比较设计**：D 的候选池被 materiality/gap/mechanism 预筛，A/B/C 没有；没有共同池/随机池基线，D 的优势与评分标准同构。加上 2021 测试日的后见知识、单评审、跨方法重复卡，任何“VALIDATED”都不可解释。

**最强失败模式**：不是 n=1（那是当前 test 的执行性失败），而是 **construct/criterion mismatch**——outcome 测的是资产卡，treatment 是研究问题生成器；且 D 在评分维度上被预筛。它无法通过“多跑几个日期/多找几个评审”修复，必须改评估对象与比较池。

**不调 test 的修法**：
- 保留 2021-12-31 为 exploratory/coverage failure；不移动、不据此改 V2 规则。
- 在任何评分前 commit/hash protocol、code、input、mapping、ratings 生成脚本；用**冻结后的未来多日期窗口**（例如 2026-12 至 2027-06 的完整交易月末，至少 6 个日期；每个方法每日至少 3 个候选）作为新 test；日期选择规则预先写死（完整交易日、覆盖率阈值），不看 D 的输出。
- 共同候选池：同一 eligibility 过滤后让 A/B/C/D 排序；加“D-filter + random 3”和“D-filter + simple score”基线，隔离“筛选”与“排序”。
- 评研究 brief 而非资产卡：所有方法同一中立模板生成 hypotheses/falsifiers/unknowns/decision impact，盲评 brief；或明确降级 claim 为“asset selection proxy”。
- 多评审（≥3，含人类/专家），盲日期/方法，提供 0/1/2 anchor；报告 inter-rater reliability；test 窗口在评审知识截止之后。
- 固定 k=3、报告 coverage/recall；paired by (date,entity) 或 cluster-robust CI；预注册最小效应量与 evidence/falsifiability 非回归；不要用 strict `>` 单点比较。
- Triage 修复：unsupported/weak 不等于 conflict；gap 用总 gap 而非仅 residual；hypotheses 候选特定化并带 evidence_for/against；falsifiers 按假设/资产生成且可观测；materiality 明确排除 near-high alone；加入 price-move-only 候选入口；`priority_key` 真正使用；tier 后再 theme dedupe；加 D 对 V1 不变的测试。
- V1 基线：把 `_dq()` 的 `datetime('now')` 改为 as-of 口径或冻结 quality_issues；C 与 V1 盲评使用同一 history/feature 设置；否则 C 不是纯 as-of baseline。

## 明确建议

**DISCOVERY VALUE: NOT VALIDATED（当前，且按本 protocol 不能转为 VALIDATED）。**

- 不要把 19:36 的 D=1.350/P@3=0.60 写成“V2 优于 V1/基准”；它只是 n=10 vs 12 的描述统计，test n=1。
- 不要为了把 test n 补到 3 而改 test 日期/加候选/调阈值；这会被 protocol 视为 test→development 迁移。
- 研究签收：NO-GO for VALIDATED；可保留“探索性、假设生成”表述。
- 下一步先修 protocol（共同池、brief 评估、冻结与多评审），再开新 test window；工程层无需因此变更。

## 附录 A：只读复现（2021-12-31）

```
FeatureSet 125 cols; anomalies 1064; recent 50;
mechanisms 2: M05_ENERGY_INFLATION_CHAIN mixed 0.17,
              M13_POSITIONING_EXTREMES unsupported 0.05
build_candidates(max_candidates=10) -> 5:
  B GX_FX_USDJPY mat 0.71 gap 0.00 conf True  (tier B)
  intelligence CM_ENE_NG mat 0.598 gap 0.00
  intelligence FR_EQ_CAC mat 0.598 gap 0.00
  intelligence HK_EQ_3067 mat 0.575 gap 0.00
  intelligence UK_EQ_FTSE mat 0.682 gap 0.00
```

- `evaluation/v2_eval_ratings.json`：46/46，rater `independent-llm-v2`，V19 四项 {1,1,2,2}。
- `evaluation/v2_eval_results.json`：D 1.35/P@3 0.60（n=10）；test D 1.5/P@3 1.0（n=1）；`discovery_value=NOT VALIDATED`。
- 数据：`data/goe.db` 2021-12-31 价格行 116/125；缺失 9 个市场；2021 行 fetched_at 为 2026-11-13。
- 重要文件/行：protocol `evaluation/RESEARCH_EVALUATION_PROTOCOL.md:8-16,25-30,36-38,40-56`；`goe/research_evaluation.py:88,98,163,176-183`；`goe/research_triage.py:104-106,146,150-172,195-200,209-220,247-254`；`goe/opportunities.py:256-276`；`tests/test_research_v2.py:47-69`。

## 附录 B：scope

- 只读；除本文件外未写入任何文件；未修改代码/配置/测试/git。
- 盲评文件在审查过程中由其他 agent 生成（19:30/19:36）；本审查只核对了其覆盖、分值范围与 test D 对象，没有重评/补评。
