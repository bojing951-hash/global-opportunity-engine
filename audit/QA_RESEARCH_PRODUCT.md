# 研究产品独立 QA — HEAD `30cb2e4` / code `5c055cc`

- 仓库：`global-opportunity-engine`；分支：`architecture/research-v2`；HEAD：`30cb2e4`（code 提交 `5c055cc`）。
- 方式：只读审查；仅新增本文件，未改代码、数据、dossier 或其它文档。审查前工作树干净；`tests/test_dossier.py`、`tests/test_capabilities.py` 3 passed。
- 结论：**P0 = 0，P1 = 2，P2 = 7**。研究流程 **FUNCTIONAL**；研究价值 **NOT VALIDATED / DISCOVERY NOT VALIDATED**；A→B **NO-GO**；A–D 不可宣称“验收 PASS”。

## 1. 18-section dossier、证据与独立性

| 检查 | 结果 | 证据 |
|---|---|---|
| `goe/dossier.py` 18 个 section | **PASS** | `SECTIONS` 共 18 项（`goe/dossier.py:17-24`）；6 份真实 dossier 的 JSON 均为 18 个 section |
| 事实含 `source` + `available_at` | **PASS（JSON）** | 6 份 dossier 全量校验，`Observed Facts`/`Supporting Evidence`/`Contradicting Evidence` 缺字段数均为 0；如 Case A 3/3、Case B 3/3 |
| 内容哈希可复算 | **PASS** | 6/6 `content_sha256` 重算一致 |
| 无伪造独立评审 | **PASS** | 6/6 `Independent Quality Review = NOT_INDEPENDENTLY_REVIEWED`（`goe/dossier.py:129-133`） |
| 无伪造研究结果 | **PASS（主体）** | `Result = NOT_EXECUTED`、`DISCOVERY VALUE: NOT VALIDATED`（`goe/dossier.py:124-128,144`；各 dossier 末行）；但见 P1-2 的 hypothesis `supported` 状态 |
| Acquisition plan / Falsification | **PASS** | 6/6 均非空；如 Case A `Evidence Acquisition Plan` 3 条、`Falsification Conditions` 4 条 |
| support / refutation 不重复 | **PASS（字面）** | 6/6 `Supporting Evidence ∩ Contradicting Evidence = ∅` |

P2（支持证据口径）：同一 claim 同时出现在 `Observed Facts` 与 `Supporting Evidence`（A 3/3、B 3/3、QQQ 2/2、XLV 1/1）；且 A 的 `区域属于政策敏感市场 JP`、`本地汇率可观察 local FX`，QQQ 的 `利率与估值代理可观察 UST` 是**可得性/配置说明**，却被列为 `Supporting Evidence`。这与 `Evidence Readiness.measured_note`（“availability notes do not.”，`goe/dossier.py:115`）自相矛盾；因 `discriminating` 计数未计入这些条目，未改变 A=partial / C=missing 的结论，但会抬高人类可读 dossier 的“支持”观感。

P2（可读件丢失 PIT）：Markdown 渲染只输出 `source`，不输出 `available_at`（`goe/dossier.py:169-170`）；JSON 有该字段，但人体可读的 `.md` 无法单独核对时点。这是展示缺口，不是数据伪造。

## 2. Case A–D 状态核对

| Case | 声称 | 实测 | 判定 |
|---|---|---|---|
| A N225 | high / partial / watch | worthiness `high`、readiness `partial`、queue `watch`、B unsupported、`a_retained` | **PASS**（`research_dossiers/2026-11-13/RC-20261113-JP_EQ_N225-455ff8e1a32f.md:81-105`） |
| B VIX | explained / gap 0 / archive | gap_score `0.0`、worthiness `low`、readiness `missing`、queue `archive`、result `NOT_EXECUTED` | **状态 PASS；口径 P2**。`CASE_B_EXPLAINED` 由 `gap_score == 0.0` 机械生成（`goe/cli.py:377-378`），dossier 自身却写“No research result is claimed”；`research/RESEARCH_ACCEPTANCE_CONTRACT.md:14` 进一步写“existing global/local factors explain it”，属超出证据的措辞（见 P1-2） |
| C TAIEX/QQQ/XLV | gap / watch | 三份均 medium / missing / watch | **PASS**（`research_dossiers/2026-11-13/` 三份）；QQQ 的 hypothesis 状态问题见 P1-2 |
| D CT | roll artifact / no economic claim | low / archive / `CASE_D_DATA_ARTIFACT`；hypothesis 写明“If roll artifact…”；raw contract/roll date 仍为 unknown | **意图 PASS，身份 FAIL**：`CM_AGR_CT` 是 **Cotton front month**（`CT=F`），不是 Live Cattle；见 P1-1 |

Case D 的“no economic claim”方向正确：dossier 未把换月伪影写成基本面结论，且把 `raw contract price and roll date` 保留为 unknown。但其资产身份和全部 cattle 研究内容错误，不能作为可接受的真实案例。

## 3. B capability router 与 A→B

| 检查 | 结果 | 证据 |
|---|---|---|
| FX / rates 事实 supported | **PASS** | `goe/integration/capabilities.py:21-26`；`tests/test_capabilities.py` 覆盖 fx、fixed_income |
| deep equity / sector / commodity unsupported | **PASS（当前数据）** | `capabilities.py:27-31`；6 份 dossier 的 B section 均 `supported: false` / `deep_asset_research_unsupported` / `a_retained` |
| 当前 0 handoff eligible | **PASS** | artifact 20 条全部 `a_retained`，`eligible=[]`；dossier 6/6 `a_retained` |
| 无 A→B research-v2 task | **PASS（限定口径）** | `data/goe.db`：`research_v2_tasks = 0`、`research_v2_results = 0`；无 research-v2 handoff task |

P2（“no task”必须限定）：`data/goe.db` 仍有 **2 条 legacy V1 `research_tasks`**（`RT-20261113-0002` / `RT-20261113-0003`，OPP-0002/0003，已导出 `exports/research_tasks/*.json`）。它们不是 research-v2 handoff task，但 `PROJECT_STATE.md:88` 的“no task created”若不限定范围，与当前 DB 不一致；应写“research-v2 0 task”。

P2（macro 声称）：代码没有 `macro` asset class（`goe/config.py:20-30`），`route_candidate({'asset_class':'macro',...})` 返回 `unknown_asset_class` / `capability_gap`；“macro/rates/FX facts supported”的提交信息/合同比实现宽。当前 20 条候选无 macro，故无当期影响。

P2（优先级潜在误路由）：`capabilities.py:24` 在 asset class 判断前先匹配 instrument 字符串 `UST`/`JGB`；若某个 equity/sector 候选把 UST/JGB 放进 `instruments`，会被误判为 `supported: true`（本地探针已验证），与“deep equity unsupported”冲突。当前候选均单 instrument，未触发。

## 4. 四维、quality audit 与“NOT VALIDATED”

- **四维字段存在且当前状态正确**：worthiness / readiness / queue / handoff 分别为 `high/partial/watch/a_retained`（A）等；当前 20 条 = **0 research / 4 watch / 16 archive / 0 eligible**，tier 全部 intelligence。**PASS**。
- P2：queue 与 handoff eligibility 仍由同一 tier 条件决定（`goe/research_triage.py:290-296`；与既有 `FINAL_RESEARCH_P1_QA.md` 的 P2 一致），四维在 schema 上分离，**语义上未完全独立**；不影响当前“0 eligible”。
- **quality audit 不是 validation**：`evaluation/RESEARCH_QUALITY_AUDIT.md:36` 明确“descriptive audit; no human/expert labels, no independent future window”，并标 `DISCOVERY VALUE: NOT VALIDATED`；6/6 dossier 均有 `DISCOVERY VALUE: NOT VALIDATED`。**PASS**。不得把该 audit 的 coverage/mean 指标当作研究价值已验证。

## 5. P0 / P1

### P0（0 项）

未发现伪造市场事实、伪造独立评审、伪造研究结果或把 simulated 数据写成真实结论。所有市场事实可回溯到 `prices` / `derived/cross_asset` / `CFTC` / `anomaly`，并带 `available_at`。

### P1-1（必须修）：Case D 资产身份错误 — Cotton 写成 Live Cattle

- `config/universe.yaml:170`：`CM_AGR_CT` = **Cotton front month**（`CT=F`）；`CM_AGR_LE` 才是 Live Cattle（`:171`）。
- dossier 却写为 “Live Cattle continuous futures”（`research_dossiers/2026-04-30/CASE-D-CM_AGR_CT-20260430.md:18,22`）、`Cattle supply/demand shock`（`:27`）、`CFTC cattle positioning`（`research_dossiers/2026-04-30/CASE-D-CM_AGR_CT-20260430.md:46`）、`slaughter/inventory data`（`:92`）；同 dossier JSON 同样（`research_dossiers/2026-04-30/CASE-D-CM_AGR_CT-20260430.json:40,42,72,120,168`）。
- 影响：这是 6 份“真实 dossier”之一，且是 A–D 验收的 D 案例；其唯一经济侧假设、数据获取计划、falsification 全部针对牛，而标的是棉花。虽然“no economic claim”方向未破坏，但资产身份和研究内容是**错误事实**，不能作为可接受的真实案例。应重新生成/改写 D（棉花或改用 `CM_AGR_LE`），并重算 content hash。

### P1-2（必须修）：hypothesis `status: supported` 与自身 falsification 阈值矛盾

- `goe/evidence/cross_asset.py:136` 仅按 `|residual_z| < 1.5` 置 `supported`，不检查 R²。
- VIX：`H-VOL-GLOBAL` status = `supported`（`research_dossiers/2026-11-13/RC-20261113-US_VOL_VIX-c1092d4e5bea.json:61`），依据 R²=**0.47**、residual_z=-0.34；VIX dossier 甚至没有为 H-GLOBAL 列出 falsification condition。
- QQQ：`H-USEQ-GLOBAL` status = `supported`（`research_dossiers/2026-11-13/RC-20261113-US_EQ_QQQ-ed67c9acfee9.json:54`），依据 R²=**0.38**、residual_z=1.12；同 dossier 的 falsification 阈值明确为 **R² > 0.5 且 |z|<1.5**（`:225`；生成逻辑 `goe/hypotheses.py:90`）。
- 影响：Case B 的 “explained” 和 Case C 的 QQQ “support” 依赖一个未达到自身阈值的关联检验；与合同“R² is association, not causality”（`research/RESEARCH_ACCEPTANCE_CONTRACT.md` Evidence rules）和 dossier 的“No research result is claimed”冲突。应把 `supported` 改为 `open`（或同时要求 R²>0.5），并让 B 的 case label 改为“no research gap / gap 0”而非“explained”。

## 6. P2 清单（不阻断，但应在研究价值评审前收敛）

1. `Supporting Evidence` 混入可得性说明（A 的 JP/local FX、QQQ 的 UST）；应只保留 measured/discriminating 项，把可得性说明移到 acquisition plan/unknowns。
2. Markdown 渲染不显示 `available_at`（`goe/dossier.py:169-170`），PIT 只能从 JSON 核对。
3. Case B 的 `CASE_B_EXPLAINED` 由 `gap_score == 0.0` 机械生成（`goe/cli.py:377-378`）；“explained”是产品口径，不是已执行的解释。
4. Case D 的 `Source & Version References` 中 `scan_id/config_hash/data_hash` 全为 `None`，只有 `data/goe.db#anomalies/...` 指针，复现性弱于 A–C。
5. Case D 的 “drawdown percentile 0.98” 与 fact “near_high 0.90” 是不同度量，正文未区分；不是伪造，但会误读。
6. B router 的 `macro` 无显式映射、且 instrument 字符串先于 asset class 判断（潜在 equity+UST 误 supported）。
7. “no task” 未限定 research-v2：DB 有 2 条 legacy V1 `research_tasks` 且已导出；queue/handoff 仍与 tier 共线。

## 7. 最终允许状态

| 结论项 | 允许状态 |
|---|---|
| 研究流程 | **FUNCTIONAL**：6 份真实 dossier、18/18 section、内容哈希可复算 |
| 研究价值 | **NOT VALIDATED / DISCOVERY NOT VALIDATED**（无 human/expert 标签、无独立未来窗口） |
| A→B | **NO-GO**：0 eligible、0 research-v2 task、6/6 `a_retained`；B 仅 rates/FX fact，deep equity/sector/commodity 留在 A |
| A–D 产品验收 | **NOT PASS（CONDITIONAL）**：P1-1、P1-2 未修前不得宣称“A–D 真实案例全部通过” |
| Case B 表述 | 只能写“**no research gap / gap 0 / archive**”；不得写“已解释/已证实” |
| Case D 表述 | 只能写“**data artifact, no economic claim**”；不得写“已确认 roll artifact”（raw contract/roll date 仍 unknown） |

**最终裁决：研究产品 = FUNCTIONAL + NOT VALIDATED + A→B NO-GO；验收 = CONDITIONAL，2 个 P1 未关闭前不得升级为 PASS。**
