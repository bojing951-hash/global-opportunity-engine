# V2 研究层独立 QA（只读复核）

- 对象：`global-opportunity-engine`，冻结提交 `364595132a94aab09002dec19e2ade512eec1f37`（`3645951`），分支 `architecture/research-v2`。
- 复核时间：2026-11-14 23:16–23:40 HKT；范围：P1-C、P1-D、2025-12-31 新窗口评估、A→B、调参/日期常量、剩余研究缺陷。
- 方式：`git show`/静态阅读 + 只读 SQLite（`file:data/goe.db?mode=ro`）+ 解析 `evaluation/*.json` + 定向跑 `tests/test_hypotheses.py tests/test_research_v2.py`（12 passed）；未重跑 scan/triage/全量评估，未改代码/配置/测试/git。
- 说明：本文件是唯一写入；复核开始时 `git status --porcelain` 为空。

## 0. 结论（先给判定）

**PASS WITH ISSUES（研究层）。无 P0；P1-C 仍未关闭；P1-D 结构通过但证据语义仍有 P1；A→B 记录形式上成立但“rejected”语义不成立。`DISCOVERY VALUE: NOT VALIDATED`，不可升级。**

- P1-C 的代码已从“五标签模板”改为按资产类别/地区分支，真实候选人确实出现了 `H-LOCAL/H-GLOBAL/H-POLICY/H-FX/H-ART` 等不同集合；但“现象特定、可观察、可区分”只完成了表面分层：`detector/direction/ddpct/gap` 未进入假设生成，测试不可互斥，且真实候选只有股票类。
- P1-D 的数据库对象、外键、生命周期计数是干净的；但存在“不可检验假设的 evidence_for 仍被计入候选人证据”“unsupported 机制被写成支持性关联”“A→B 环境权限失败被分类为 rejected”三类语义问题。
- 2025-12-31 结果数值与文档一致，文档明确 NOT VALIDATED，未发现 VALIDATED 声明；但评估协议仍只测“资产选择”，不测 V2 的核心“研究问题质量”。新窗口不是未来窗口，且该日期是仓库里早已存在的 V1 验证案例日期，独立性弱于“new frozen window”的表述。

## 1. 判定表

| # | 检查项 | 判定 | 关键证据 |
|---|---|---|---|
| 1 | P1-C 资产类别/地区分支 | **PARTIAL（P1 保留）** | `goe/hypotheses.py:38-41` 接收 `detector/direction/ddpct/gap_value`，但函数体内除 `ret1m` 外基本未使用；`:50-52` `mech_bad` 计算后未使用。N225（drawdown_extreme）与 TAIEX（price_return_shock）同属 country_equity，得到同一组 6 个 key。 |
| 2 | P1-C 可观察预测与区分性检验 | **FAIL（P1）** | 真实候选 `RC-20261113-12` 为 tier A，4 个 open 假设，但 H-LOCAL 需“regional benchmark”、H-GLOBAL 需“cross_asset”、H-POLICY 需“policy calendar/rates”；候选人自己的 `evidence_against` 写明这些样本/时点缺失。仅 H-FX 有本地汇率数据。`distinguishability_level=2` 只是统计 `test` 里不同 `hypothesis_id` 的个数（`research_triage.py:207-208`），不是互斥检验。 |
| 3 | P1-C 不可检验假设/证据污染 | **FAIL（P1）** | `RC-20261113-14`（TAIEX）的 H-POLICY 为 `untestable`，但其 `evidence_for` 仍为“区域属于政策敏感市场”，并进入 candidate 级 `evidence_for`（`research_triage.py:195` 聚合全部 hypothesis 的 evidence_for）。同一候选的 H-LOCAL 在 `RC-20261113-12` 中把 `mechanisms=['unsupported']` 写成“有区域/机制关联证据”（`hypotheses.py:56-67`）。 |
| 4 | P1-C 跨资产正确性 | **FAIL（P1/P2）** | 以 GLD（商品 ETF，非期货）复现：H-ART 为 open，证据“连续合约存在换月风险”，测试“原始合约对账”——ETF 没有换月。以 German Bund 复现：H-TERM 证据固定写 `UST 2Y/10Y`，H-POL 固定写 `US_POLICY_RATE`，H-REAL 测试写 `TIPS/breakeven`。Crypto 只有 H-LIQ（经济）+ H-ART（数据伪影）两个 open；H-REG/H-FLOW 均 untestable，不构成两个经济解释的竞争。 |
| 5 | P1-D 对象/外键/生命周期 | **PASS（结构）** | DB：5 candidates / 28 hypotheses / 41 evidence / 1 task / 3 events / 1 result；`research_integrity()` 六个计数器全 0；无 V1 `RC-*` 遗留；RC-12 仍保留，status=`handoff_failed`。 |
| 6 | P1-D “no fake links” | **PARTIAL（P1 语义）** | 结构外键全部有效；但 evidence 表没有 for/against 极性列（`goe/db.py:141-147`，写库时把 `evidence/evidence_for/evidence_against` 合并，`:838-847`），且不可检验假设的 evidence_for 被计入支持证据。语义上是“假链接”，不是外键假链接。 |
| 7 | A→B 实际记录/保留候选 | **PASS（形式）/ P1（语义）** | `research_v2_tasks.status=not_completed:rejected`；`research_v2_results.semantic_status=rejected, run_ok=0`；候选 retained，无 `research_complete`、无成功声明。但 result 的 `stdout_tail` 显示下游错误是 `orchestrator_failed: [Errno 1] Operation not permitted: 'exports'`，不是研究层面的拒答；`ia_adapter.py` 把 `run_ok is False` 一律映射为 `rejected`。 |
| 8 | 评估数值与 P@3 | **PASS（数值）** | 12 张卡重算与 `evaluation/new_window/v2_eval_results.json` 一致：A 1.0833 / B 0.9167 / C 1.5000 / D 1.0000；P@3 0/0/0.6667/0。C 的 0.6667 = 2/3（SI 1.5、HG 2.0、PL 1.0）。 |
| 9 | 评估诚实性/NOT VALIDATED | **PASS** | `evaluation/new_window/RESULTS.md`、`V2_EVALUATION_RESULTS.md`、`v2_eval_results.json`、`audit/V2_FINAL_ACCEPTANCE.md:17,24` 均为 `DISCOVERY VALUE: NOT VALIDATED`；2021 已标 exploratory/reused；未发现正向 VALIDATED 声明。 |
| 10 | 评估协议公平性（选择 vs 问题） | **PARTIAL** | 同一事实卡、方法标签隐藏、同 as-of 是公平的；但 D 预筛、A/B/C 不预筛（协议已披露），n=3/方法，单一 LLM rater；事实卡隐藏 hypotheses/falsifiers，因此只测“资产选择质量”，不测 V2 的研究问题质量。新窗口 12 卡中 9 商品、1 FX、1 行业股、0 rates、0 crypto。 |
| 11 | 新窗口调参/日期常量 | **PASS（未发现调参）** | `83a1160` 只新增评估 artifact + `goe/release.py`，没有策略/配置/测试代码；`goe config tests scripts contracts` 中除 `config/cases.yaml:76-79` 外无 2025-12-31 常量；结果是一次性负结果，无迭代痕迹。 |
| 12 | 评估 artifact 新鲜度 | **FAIL（P1/P2）** | 被跟踪的 `evaluation/v2_candidates_2026-11-13.json`（21:17）仍是旧五标签 `H1`–`H5`，5 个候选全部相同；当前运行时 `exports/research_candidates_2026-11-13.json`（23:10）才是动态 `H-LOCAL...`。冻结提交里唯一被跟踪的候选集与 P1-C 修复后的代码不一致。 |

## 2. 最强反证（足以否定“P1-C 已完全关闭”）

### 2.1 RC-12 的 tier A 是“标签计数”而非“可执行检验”

`RC-20261113-12`（N225，tier A、rank 1）有 4 个 open 假设：

- H-LOCAL：测试“对本地基准与全球因子回归后的残差”，数据 `prices/regional benchmark`；候选人自己的 `evidence_against` 写“未建立本地基准对照”。
- H-GLOBAL：测试“同日跨资产 beta 与残差”，数据 `cross_asset`；`evidence_against` 写“未提供同日跨资产横截面”。
- H-POLICY：测试“事件窗口前后的利率/资产反应”，数据 `policy calendar/rates`；`evidence_against` 写“没有可核验的决议/公告时点”。
- H-FX：测试“本币汇率 beta”，数据 `local FX`；这是唯一看起来有数据的一项。

`research_triage.py:207-208` 把 `len({test.hypothesis_id})` 直接映射为 `dist_level=2`，tier A 需要 `dist_level>=2`（`:213-214`）。于是“4 个测试名字”把 3 个无数据检验变成了“高区分度”，并让候选进入 tier A。**这不是“hypothesis 是否 open”的问题，而是“open 是否可执行”没有被 gate 检查。**

### 2.2 不可检验假设仍进入 supporting evidence

`RC-20261113-14`（TAIEX）中 H-POLICY 的 status 是 `untestable`，但 `evidence_for` 仍有：

```json
{"claim": "区域属于政策敏感市场", "value": "TW", "class": "observed_fact", "hypothesis_id": "H-POLICY"}
```

`research_triage.py:195` 对全部 hypotheses 的 `evidence_for` 不做 status 过滤，candidate 级 `evidence_for` 因此包含它（实测 payload 可见）。这直接违反 `hypotheses.py:5-7` 的“untestable ... never counted as supporting evidence”。同类问题在商品：GLD 的 H-SUPPLY 为 untestable，却有 `evidence_for: 价格跳变可观察`，该条也会被聚合。**注意：`open_count` 本身没有把 untestable 算进去（这点是好的），但 evidence 层仍然算进去了。**

### 2.3 反向机制被写成支持性关联

`RC-20261113-12` 的 H-LOCAL：

```json
{"claim": "有区域/机制关联证据", "value": "mechanisms=['unsupported']", "class": "statistical_association"}
```

`mechanism_statuses=['unsupported']` 在机制评估里是“不支持”，却被 `hypotheses.py:56-67` 写成“有区域/机制关联证据”。`mech_bad` 在 `:52` 计算后完全未使用，没有降级或改写。这是实质性的证据分类错误，不是措辞问题。

### 2.4 跨资产分支仍有硬编码/错误假设

用 `build_hypotheses` 直接复现（未改代码）：

- **GLD（commodity ETF，`is_futures=False`）**：H-ART 为 open，`evidence_for=连续合约存在换月风险`，测试 `原始合约对账`。`hypotheses.py:112-114` 只要 `commodity` 就 open，没有要求 `is_futures` 或真实价格问题。
- **German Bund（fixed_income，EA）**：H-TERM 证据写 `UST 2Y/10Y`，H-POL 写 `US_POLICY_RATE`，H-REAL 测试写 `TIPS/breakeven`；这是美国利率数据，不是 EA 利率数据（`hypotheses.py:192-213`）。
- **Crypto**：open 只有 H-LIQ（经济）+ H-ART（数据伪影）；H-REG/H-FLOW 都 untestable。`discriminating=True` 仅因为有两个 test id，并不是两个经济解释互相竞争（`:270-292`）。
- **FX**：H-CARRY 的 threshold 是 `sign consistent`，H-RISK 是 `corr > 0.4`；两者可以同时成立，测试不是互斥的。
- **US ETF / sector**：H-GLOBAL 与 H-RATES / H-STYLE 的测试也都可以同时通过；没有“哪一个被证伪”的判决规则。

这些说明 P1-C 的“phenomenon-specific”目前最多是 **asset-class + region-specific**；对 detector/direction 不敏感，对跨资产数据也缺少真实候选验证。

### 2.5 A→B 的“rejected”是权限失败，不是研究拒绝

`research_v2_results` 唯一一行：

- `semantic_status=rejected`，`run_ok=0`；
- `payload.result.stdout_tail` 的 `error` 为 `orchestrator_failed`，`message="[Errno 1] Operation not permitted: 'exports'"`；
- `ia_adapter.py:100-118`：`if run_ok is False: status="rejected"`，理由统一写“下游研究明确返回失败/拒绝（run_ok=false）”。

因此 DB 的 `not_completed:rejected` 是真实记录，候选也确实保留，且没有任何成功声明；但把它解释为“B 拒绝了 V2 的研究问题”不成立。它更像是下游 runner 在写 `exports` 时被沙箱/权限拦住。验收文档 `V2_FINAL_ACCEPTANCE.md:18,29-30` 的“B returned rejected”应按“handoff 环境失败、语义未完成”表述，不能当作 B 对研究质量的负面判断。

### 2.6 新窗口不是“未来/全新”窗口，且评估门槛可被 `test` 标签绕过

- `evaluation/new_window/v2_eval_mapping.json:98-105` 把 `2025-12-31` 放进 `splits.test`；`evaluation/new_window/V2_EVALUATION_RESULTS.md:20-25` 还保留 `## Test split` 和 `D beats ... on test`。这与 `evaluation/RESEARCH_EVALUATION_PROTOCOL.md:13-17` 的“no independent test split remains / NOT VALIDATED by construction”自相矛盾。
- `goe/research_evaluation.py:183`：`validated = bool(dt and all(wins) and dt.n>=3)`；没有检查独立性、未来性、人类标签或窗口是否预注册。只要 2025 这个 `test` 上 D 胜 B/C，代码就会输出 `VALIDATED`。当前 D 输掉，所以结论仍是 NOT VALIDATED；但 **验证门是“一胜即翻”的**，这是 P1 级潜在缺陷，不只是文档措辞。
- `2025-12-31` 并非新日期：`config/cases.yaml:76-79` 在初始提交 `1a7a5f5` 就有 `GOLD_VS_REAL_RATES_2025`，`docs/examples/validation_cases_20261113T152849Z.json:1060-1062` 也以它为 `as_of`。它是 V1 的验证案例日期。它可能没有用于“定义 V2 规则”，但“new frozen window / 未使用过”的独立性弱于文档暗示；V01 又正好是 GLD，和这个 gold case 主题重合。

### 2.7 “P@3”不是 precision@3

`goe/research_evaluation.py:163`：

```python
"precision_at_3": round(float((sub["mean"] >= 1.5).mean()), 4)
```

这是“所有评分对象中 mean≥1.5 的占比”，不是 top-3 的 precision。旧 48 对象评估中它是 12 个对象上的阈值占比；新窗口每个方法只有 3 个对象，C 的 0.667 就是“3 个里 2 个 ≥1.5”，没有排序意义上的 P@3。数值本身与文档一致，但名称/解释会误导。

## 3. 评估：资产选择质量 vs 研究问题质量

### 3.1 资产选择质量

- 数值可信、可重算：A 1.083 / B 0.917 / C 1.500 / D 1.000；D 的 P@3=0，C=0.667。
- 作为“同一事实卡下的资产选择”比较，协议基本公平：同 as-of、同 universe、方法标签隐藏、ID 打乱、每方法 3 个对象；D 没有调用 V1 排名。
- 但这不是干净的 ranking 对照：D 先过 materiality/evidence gate，A/B/C 不过；D 的 3 个对象可能本来就更“事实丰富”。协议已披露“filter vs ranking”混淆。n=3/方法、单一 LLM rater、2025 是历史数据且 rater 可能知道结果，统计与盲性都有限。
- 结论只能支持“**在这个 3 对象/单评分者/预筛不对称的检查里，D 的资产选择没有优于 C/B/A**”，不能支持“V2 更差”或“V2 更好”。

### 3.2 研究问题质量（V2 的核心价值）

**仍未测量。** 12 张事实卡只有收益率、波动分位、回撤、MA gap、近期异常、机制、data gaps；没有 V2 的 `competing_hypotheses`、`falsification_conditions`、`decision_impact`，也没有 B 的研究 brief。评分中的 `falsifiable` 几乎恒定（12 张里 11 张为 1，只有 C 的 SI 为 2），测的是“从事实卡能否形成测试”，不是 V2 的假设/证伪设计。协议新增的 Known design limitations 已明确写出这一点，`evaluation/new_window/RESULTS.md` 也写“Research-question quality still lacks a clean independent measure; a human/expert review is required.” 这是诚实的；但不能用“D 1.000 < C 1.500”去推断 V2 的研究问题差——它没有出现在评分材料里。

### 3.3 协议公平性判断

- 对“资产选择”是 **部分公平**：同卡、盲标签、同数据；但 D 预筛、A/B/C 不预筛，n=3、单 LLM、历史窗口，公平性有限。
- 对“研究问题质量” **不公平/不足**：V2 的输出被隐藏；新窗口覆盖也偏（9 商品、1 FX、1 行业、0 rates、0 crypto），无法检验股票/利率/FX/商品/crypto 的假设特异性。
- “new frozen window” 是事后选择的单一历史日期，且是仓库既有验证案例；协议在 2021 失败后追加该窗口，虽披露，但不是预注册的独立 test。**文档结论 NOT VALIDATED 是对的；不要因为“换了一个窗口”就把它当成独立验证。**

## 4. 新窗口结果是否被“看到后调参”

**未发现调参证据。**

- `83a1160` 的 diff 只有评估 artifact、`evaluation/RESEARCH_EVALUATION_PROTOCOL.md`、`audit/*` 文档和 `goe/release.py` 的小改动；没有改 `goe/hypotheses.py`、`goe/research_triage.py`、`config/scoring.yaml` 或阈值。
- `goe/`、`config/`、`tests/`、`scripts/` 中检索 `2025-12-31` 只命中 `config/cases.yaml` 的既有 V1 验证案例；V2 代码没有 test-date 常量。
- 新窗口结果是负结果（D 输给 C），且只生成一次；没有发现反复重评/改评分/改 mapping 的痕迹。
- 但“未调参”不等于“独立”：窗口是历史数据、单一 LLM、rater 可能知道结果、日期是既有验证案例。`83a1160` 没有新增生成脚本，复算评分只能依赖 `v2_eval_ratings.json` + `v2_eval_mapping.json`；卡片生成路径可复现性一般（脚本未随窗口冻结）。

## 5. A→B 核验

**记录层面：符合“实际 rejected/not_completed、候选保留、无成功声明”。**

- `research_v2_tasks`：`RC-20261113-12` → `not_completed:rejected`。
- `research_v2_results`：1 行，`semantic_status=rejected`，`run_ok=0`。
- candidate：`RC-20261113-12`，status=`handoff_failed`，仍完整保留 hypotheses/evidence，tier A、rank 1；无 `research_complete`。
- events：`ia_research_not_completed`，note 为“V2 handoff: rejected (... run_ok=false)”；另有 `status:handoff_failed`。
- 没有 `ok_valid`、没有 fake end-to-end success。

**语义层面：P1。** 下游实际错误是 `Operation not permitted: 'exports'`（orchestrator_failed），不是研究性拒答；`ia_adapter.py` 的 `run_ok is False -> rejected` 过宽。应该区分为 `failed`/`environment_error`/`refused`/`rejected`，否则“B rejected”会被误读为研究质量判断。候选保留与无成功声明这两点是正确的。

## 6. 数据对象与“假链接”细查

- 5 个 candidate、28 个 hypothesis、41 条 evidence、1 个 task、3 个 event、1 个 result；`research_integrity()` 的 orphan_hypotheses/orphan_evidence/orphan_tasks/orphan_results/legacy RC 全 0。
- 所有 evidence 的 `hypothesis_id` 都能解析到同一 research 的 hypothesis；没有跨 candidate 的外键错配。
- `research_v2_evidence` 没有 polarity 列；`evidence`、`evidence_for`、`evidence_against` 按同一张表写入。candidate payload 里仍保留 for/against，但规范化表无法区分“支持/反对”，这使下游无法可靠审计“no fake links”。
- 语义上至少有两类假链接：不可检验 H-POLICY 的 evidence_for 进入 candidate evidence_for；unsupported 机制被写成支持性 association。另有一条“可观察事实”被当作解释性证据（H-GLOBAL 的“1m=9.7%”只证明幅度，不证明全球风险解释）。
- `falsification_conditions` 实际是 `bundle["tests"]`（`research_triage.py:189`），不是“什么结果会推翻哪个假设”的判决条件；测试与假设是一对多标签关系，没有 pairwise 的“哪个赢”的判据。

## 7. 剩余 P0/P1

### P0

**无。** 没有发现伪造成功、VALIDATED 声明、未来信息、或 study 级别的致命错误。

### P1（按严重度）

1. **P1-C-1（可执行性/区分性）**：open 假设与测试没有数据可用性门槛。RC-12 的 4 个 open 假设中 3 个测试所需数据在候选人自己的 `evidence_against` 里被标为缺失，但 `dist_level=2` 仍使其进入 tier A。修复方向（代码）：把“test data available”纳入 gate；对缺数据的假设标 `untestable` 或 `open_data_gap`，不计入 distinguishability；测试必须给出互斥结果/判决规则，而不是只数 hypothesis_id。
2. **P1-C-2（证据语义）**：不可检验假设的 `evidence_for` 仍进入 candidate evidence_for（RC-14 H-POLICY）；`mechanisms=['unsupported']` 被写成支持性 association（RC-12 H-LOCAL）；`mech_bad` 未使用。修复方向（代码）：按 status 过滤 evidence_for；unsupported/mixed 不得写成正向关联；补 test 证明。
3. **P1-C-3（现象特异性）**：`detector/direction/ddpct/gap` 未使用，drawdown_extreme 与 price_return_shock 同资产类别得到同一组假设；跨资产分支有硬编码错误（GLD 换月、Bund 用 UST/US_POLICY_RATE/TIPS、crypto 只有一个经济解释）；真实候选只有 equities，rates/FX/commodity/crypto 只有合成单测。修复方向（代码 + 真实运行/未验证研究）：按 detector 生成候选特定假设；按地区/资产修正数据引用；重跑并保留跨资产真实候选。
4. **P1-D-1（A→B 语义）**：`run_ok=false` 一律 `rejected`，但唯一真实记录的错误是 `Operation not permitted: 'exports'`；验收文档“B returned rejected”不成立。修复方向（代码/文档）：区分 environment_error / failed / refused / rejected；保留原错误；重跑一次真实 handoff 或明确写“未完成环境失败，不能判断 B 的研究拒绝”。
5. **P1-E-1（验证门）**：`2025-12-31` 被标记为 `splits.test`，`score_ratings` 只要求 n>=3 和 mean/P@3 双胜，就会输出 VALIDATED；没有检查独立性/未来性/人类标签。当前 D 输，结论正确；但“一胜即 VALIDATED”是潜在漏洞。修复方向（代码）：把该窗口固定为 exploratory；VALIDATED 需要预注册的独立窗口 + 人类/专家标签；或直接移除自动 VALIDATED 分支。
6. **P1-F-1（artifact 一致性）**：被跟踪的 `evaluation/v2_candidates_2026-11-13.json` 仍是旧 `H1`–`H5` 五标签模板，5 个候选完全相同；当前动态输出只在未跟踪的 `exports/` 和 DB 里。它是对 P1-C 修复的“反向证据”，也可能被后续 QA 误用。修复方向（artifact）：重生成并跟踪 5 候选动态版本，或删除旧 artifact 并在文档标明以 DB/导出为准。

### P2（不改变本次结论）

- `precision_at_3` 命名/语义（阈值占比，非 top-3 precision）；新窗口 n=3 时尤其容易误读。
- 新窗口日期 `2025-12-31` 早已是 `config/cases.yaml` 的 V1 验证案例；文档“new frozen window”应注明“历史日期、已存在的验证案例、rater 可能知道结果”，而不是暗示全新。
- 商品 H-ART 对 ETF 也 open（GLD/SLV 无换月）；rates 分支美国数据硬编码；H-POS 对中性仓位也可能 open；H-POLICY 对 TW/KR 等政策敏感市场标 untestable（`POLICY_REGIONS` 缺 TW/KR）。
- DB evidence 表无 for/against 极性；`research_v2_events` 首次事件 task_id 为 NULL、后续重跑事件重复，属审计可读性问题。
- `tests/test_research_v2.py::test_v2_evaluation_decision_rule_is_not_automatic` 断言 `in ("VALIDATED","NOT VALIDATED")` 恒真；`test_v2_evaluation_decision_rule_requires_test_and_both_metrics` 反而把“合成单个 test 日期即可 VALIDATED”固化为期望。测试没有覆盖“不可检验假设不能进 evidence_for”和“缺数据不能算 dist_level=2”。
- 验收文档“20-candidate audit has 15 distinct hypothesis signatures”在冻结提交的可见候选 artifact（5 个）中不可复算；需要保留 20-candidate 运行产物才能复核。

## 8. 哪些是代码可修，哪些是尚未验证的研究

| 类型 | 项目 | 说明 |
|---|---|---|
| 代码可修（不需新数据） | evidence_for 按 status 过滤；unsupported/mixed 不得写正向 association；H-ART 只在 futures/真实价格问题时 open；rates 按地区取曲线/政策利率；A→B error 分类；验证门禁止在 post-hoc 2025 窗口自动 VALIDATED；重生成 stale candidate artifact；evidence polarity；P@3 改名 | 这些不改变“V2 研究价值”的事实，但会修正审计口径和 gate 的虚假通过 |
| 需要新数据/新研究（未验证） | 真正的互斥检验（含经济解释的判决规则）；跨资产真实候选集（rates/FX/commodity/crypto）；独立未来窗口；人类/专家标签；研究问题质量（hypothesis/falsifier 的独立评分）；D 的资产选择是否稳定优于 C/B/A | 目前只有资产选择层面的负结果和合成单测；不能据此证明 V2 研究问题好或坏 |

## 9. DISCOVERY VALUE 状态（明确）

**`DISCOVERY VALUE: NOT VALIDATED`（维持，不可升级）。**

理由：

1. 2025-12-31 选择结果 D 1.000 < C 1.500、A 1.083、B 0.917；D 的 P@3=0，未达到“D 胜 B 和 C”的决策规则。
2. 该窗口是历史数据、单一 LLM rater、n=3/方法；不是独立未来窗口；且该日期是既有 V1 验证案例，独立性有限。
3. 评估材料隐藏 V2 的 hypotheses/falsifiers，测的是资产选择，不是研究问题质量；**研究问题质量仍未被测量**，不能用选择层面的失败替代。
4. 代码中不存在 test-date 特定常量，未发现看到结果后调参；D 的失败是诚实的负结果，但仍不足以证明“V2 更差”，只能证明“这组资产选择评分不优于 C/B/A”。
5. 未发现任何正向 VALIDATED 声明；验收文档、结果 JSON、协议均为 NOT VALIDATED。若未来要升级，必须使用预注册的独立未来窗口 + 人类/专家标签 + 研究问题级别的盲评；不能复用 2021/2025，也不能在本窗口上调 V2 权重。

## 10. 复核限制

- 未重跑 scan/triage/全量评估（10 分钟 timebox、无 heavy rebuild）；P1-C 的跨资产问题以 `build_hypotheses` 直接调用复现，未重跑真实 triage。
- 定向测试：`tests/test_hypotheses.py tests/test_research_v2.py` 12 passed；全量 174 项未在本次复核重跑（`TEST_RESULTS.md` 记录 174 passed，但未独立验证）。
- DB 以只读 URI 查询；未改数据、代码、配置、测试或 git。仅新增本文件。
