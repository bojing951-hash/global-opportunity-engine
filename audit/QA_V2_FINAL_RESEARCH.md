# V2 最终研究 QA（冻结提交 51f4a62）

- 审计对象：`51f4a627353a1d6211f545a325561c62473171ec`（2026-11-14 23:50 +0800）
- 范围：P1-C 假设语义、P1-D 生命周期、P1-F 评估、A→B handoff、20 条候选 artifact 与代码一致性
- 方式：静态读代码/文档 + 已跟踪 JSON + 现有 `data/goe.db` 查询；**未重建、未重跑特征/评估、未改代码**
- 限制：单次独立 QA，未做人工语义评分；DB 为共享工作副本，可能包含历史轮次残留
- 写入：仅本文件。审计期间工作树出现非本代理改动 `goe/release.py`（未提交），本报告不评价该改动，判定针对 `51f4a62` 的已跟踪内容

## 总判定

**FAIL（不可作为 V2 最终研究验收签署）**。无 P0；存在 5 项 P1，其中 **P1-C-1 直接违反“untestable 假设不得有 evidence_for、不得进入 supporting evidence”的硬规则**，是阻断项。工程测试全绿不能覆盖该语义缺陷（现有测试只覆盖 JP equity 的 untestable 情形）。

**DISCOVERY VALUE：NOT VALIDATED**（详见末节，维持不变）。

## 逐项判定

| # | 检查项 | 判定 | 关键证据 |
|---|---|---|---|
| 1 | P1-C 假设是否真正 asset-specific | **FAIL（P1）** | 20 条候选只有 **7 种** 结构性 hypothesis 签名（`id/type/status`；test 签名也是 7 种）；按 `id/label/type/status` 才是 15 种。4 条 commodity、4 条 sector、5 条 country-equity 分别逐字同构；QQQ 与 EEM 仅差一个 H-USD。属于 asset-class/region 模板，不是 instrument-specific。 |
| 2 | untestable 假设的 evidence_for / supporting evidence | **FAIL（P1，阻断）** | 20 条中 **6 个 untestable 假设带非空 evidence_for**：`RC-20261113-09/10`（USDBRL/USDKRW）的 H-INT；`RC-20261113-02/03/04/05`（LE/SB/RB/SLV）的 H-SUPPLY。这些 evidence 被 `research_triage.py:212-214` 聚合进 candidate 的 `evidence`/`evidence_for`，因此进入 supporting evidence，并会进入 A→B 问题的事实清单。 |
| 3 | 测试可执行/可用或明确 obtainable | **PARTIAL（P1）** | 49 条 falsifier：32 条标 `available`、17 条标 `obtainable`，字段齐全、且只保留 open 假设的 test。但 `available` 判定很粗：`cross_asset` 只要 SPY/QQQ/DXY/GC 任一存在就算 available；H-STYLE 对全部 sector（含 `CN_SEC_EV`）硬编码 `UST, available`；commodity 的 `DXY/UST` 对农产品/白银 ETF 也标 available。可用性被高估，并直接影响 `dist_level`/tier。 |
| 4 | 跨资产硬编码：Bund 用 UST | **未复现（但存在同类问题）** | 当前 20 条候选中**没有 Bund/DE 固收候选**；`rates` 分支按 region 用本地曲线/本地通胀互换，未发现“Bund 直接使用 UST”的代码路径。实际硬编码在 sector/ETF/commodity：`CN_SEC_EV` 的 H-STYLE 用 UST 且标 available（`goe/hypotheses.py:159`）。 |
| 5 | 跨资产硬编码：commodity ETF 用连续期货 | **FAIL（P1）** | `CM_ETF_SLV` 是白银 ETF，却被套用 commodity 的连续合约模板：H-ART“换月/连续合约数据伪影”、evidence `futures`、test“原始合约对账/exchange”（`goe/hypotheses.py:274-283`；artifact `RC-20261113-05`）。没有 `is_futures` 分支，ETF 与农产品/能源期货得到同一模板。 |
| 6 | 跨资产硬编码：crypto 只有 2 个 open | **PARTIAL（P2，代码层）** | crypto case 只有 H-LIQ（经济解释）+ H-ART（数据伪影）两个 open，H-REG/H-FLOW untestable；`discriminating` 仍为 true。形式上满足“>=2 open”，但实质只有 **1 个**经济假设，另一个是数据质量假设；当前 20 条 artifact 无 crypto 候选，无法在真实候选上复核。 |
| 7 | P1-D candidate/hypothesis/evidence/task/result 生命周期 | **PASS（结构）/ P2** | DB：20 candidates / 100 hypotheses / 161 evidence / 1 task / 2 results / 5 events；`research_integrity()` 六项全 0（无 orphan/FK 断裂、无 V1 `RC-*` 遗留）。refused handoff 后 `RC-20261113-12` 仍保留（status=`handoff_failed`，tier A/rank 1），未出现 `research_complete`。 |
| 8 | P1-D 证据与当前候选一致 | **PARTIAL（P2）** | DB evidence=161，当前 artifact=148；多出的 13 条是旧措辞残留（N225 2、TAIEX 2、CH 2、MX 2、CN1000 1、DAX 2、INDA 2），例如旧 `H-LOCAL/H-POLICY` claim。原因：`upsert_research_candidate` 对 evidence 用 `INSERT OR IGNORE`（`goe/db.py:838-847`），重生成候选时不删除旧 evidence；`research_integrity()` 只查 orphan，查不出“陈旧但外键有效”。 |
| 9 | P1-F 2025-12-31 独立性 | **PASS（独立性判断正确）** | 2025-12-31 确实已用于 V1 验证 case（`docs/examples/validation_cases_20261113T152849Z.json:1060-1062`）。主文档明确写“already used in V1 cases, not independent”，不再当独立 test。 |
| 10 | P1-F 结果与 NOT VALIDATED | **PASS（主文档）/ P1（陈旧子文档）** | 主 `evaluation/V2_EVALUATION_RESULTS.md`：D **1.000** vs C **1.500**（A 1.083/B 0.917），P@3 D 0.00 vs C 0.67；明确 `DISCOVERY VALUE: NOT VALIDATED`。但 `evaluation/new_window/V2_EVALUATION_RESULTS.md:15,25` 仍写 `## Test split` 和“D beats B and C on test”，把非独立窗口标成 test split，与同一目录 `RESULTS.md` 的“not independent”自相矛盾。 |
| 11 | P1-F 是否在 test date 上调参 | **PASS（无证据）** | 无加权和可调权重（字典序规则）；文档明确“no tuning on this window”；2025 run 固定在 snapshot `83a1160`，后续 hypotheses/test-availability 改动未重评，并明确说明结果不代表当前假设质量。无法证明“从未看过”，但无调参痕迹。 |
| 12 | P1-F 问题质量是否被测量 | **PASS（承认未测）** | 主评估明确写“cards measure asset selection, not D's research brief”“question quality still unmeasured”；未把 selection worthiness 冒充 research-question quality。 |
| 13 | A→B 是否真实 refused/not_completed、无成功声明 | **PASS（记录）/ P2（文档）** | DB：task `not_completed:refused`；result 2 `semantic_status=refused, run_ok=0`；result 1 为历史 `rejected, run_ok=0`；候选 retained。无 `run_ok=1`/`research_complete`/成功声明。 |
| 14 | A→B 过程错误 vs 研究拒答 | **PARTIAL（P2）** | 当前 `ia_adapter.py` 已区分：rc!=0 且无报告 → `error`（:195）；S8 `out_of_scope/refused/rejected/unmapped/no_registry_identity` → `refused`（:93-97）。但历史 result 1 仍是 `rejected`（当时 env error），未回填；`V2_FINAL_ACCEPTANCE.md:18` 写“earlier run now mapped to error”，:30 又写 `not_completed:rejected`，与 DB 的 `refused` 不一致；且实际 S8 是 `no_registry_identity`，不是文中的 `out_of_scope`。 |
| 15 | 新 20 条 artifact 是否匹配当前代码（非陈旧） | **PASS（内容）/ P2（provenance）** | `v2_candidates_20_2026-11-13.json` = 20 candidates、100 hypotheses；与当前代码缺陷一致（6 个 untestable 带 evidence_for；SLV 连续期货模板；7 种结构签名），说明不是旧 `H1-H5` 五标签模板，未陈旧。5 条 `v2_candidates_2026-11-13.json` 也已是动态 `H-LOCAL...`。 |
| 16 | artifact 可追溯/无重复 | **PARTIAL（P2）** | `v2_candidates_20_2026-11-13.json` 与 `research_candidates_2026-11-13.json` **字节完全相同**（均 185,772 B），无 `generated_at`/命令/快照 SHA；无法区分主产物与副本，无法独立复算生成过程。 |
| 17 | 无 unsupported claim | **PARTIAL（P2）** | 未发现 DISCOVERY/A→B 成功性虚假声明；top5（N225/XLV/QQQ/TAIEX/EEM）与 artifact rank 1-5 一致。但 `V2_FINAL_ACCEPTANCE.md:6` 的“15 distinct hypothesis signatures”只有按 label 才成立（结构签名只有 7），文档未定义签名口径，容易把“区域名替换”误读为实质差异化。 |

## 最强反证（P1-C-1）

`goe/hypotheses.py:239-242` 对 H-INT 无条件写入 evidence_for：

```
status = "open" if region in ("JP","CN") else "untestable"
_h(..., status, ..., [_ev("区域有干预历史/政策敏感", region, "observed_fact", "config", ...)], ...)
```

于是 USDBRL/USDKRW 的 H-INT 是 `untestable`，却带 evidence_for；`goe/research_triage.py:212-214` 又无条件把每个 hypothesis 的 evidence_for 聚合为 candidate 级 supporting evidence，`evidence = evidence_for[:4]` 还会把它放进候选事实卡。artifact 中 `RC-20261113-09` 的 `evidence`/`evidence_for` 确实包含该条（JSON 约 2863/2919 行），`RC-20261113-02` 等 commodity 的 H-SUPPLY 同理。

更关键的是测试给了假保证：`tests/test_hypotheses.py:58-62` 只对 JP equity 断言 untestable 的 evidence_for 为空；JP 的 untestable 恰好是 H-FUND/H-POS/H-ART（都为空），所以测试通过。FX 的 H-INT 与 commodity 的 H-SUPPLY 未覆盖；`goe/contracts.py` 也未校验“status=untestable ⇒ evidence_for 为空”。因此 **176 tests 全绿与硬规则违反同时成立**。

## 其他重要反证

1. **SLV 不是期货**：`CM_ETF_SLV` 的 H-ART 写“连续合约存在换月风险”、test 用 exchange 原始合约对账；白银 ETF 没有换月/连续合约，模板把 commodity ETF 与 LE/SB/RB 混为一类。`goe/hypotheses.py:274-283` 无 `is_futures` 判断。
2. **CN sector 用 UST**：`goe/hypotheses.py:159` 对全部 sector 无条件 `_test("H-STYLE", ..., "UST", "available")`；artifact `RC-20261113-07`（CN_SEC_EV）因此获得一个“available”的美国利率 beta 测试，直接抬高 `dist_level` 与 tier。Bund 用 UST 的路径未找到，但这是同一类 cross-asset 硬编码。
3. **非独立窗口仍被标成 test**：`evaluation/new_window/V2_EVALUATION_RESULTS.md` 写 `## Test split`、`D beats B and C on test`，而 `RESULTS.md` 第一行明确“not independent”。若只引用前者，会制造“2025 是独立 test”的错误印象，与 NOT VALIDATED 的结论冲突。
4. **DB 与 artifact 证据不一致**：`RC-20261113-12` DB 12 条 vs artifact 10 条；多出旧 claim“有区域/机制关联证据”“未建立本地基准对照”。外键有效但内容已过时，`research_integrity()` 无法发现。
5. **文档 refusal 口径不一致**：`V2_FINAL_ACCEPTANCE.md:18` 写 `not_completed:refused`/S8 `out_of_scope`，:30 写 `not_completed:rejected`；DB 实际 task=`not_completed:refused`、result=`refused`、S8=`no_registry_identity`，历史 result 1=`rejected`（env error）。结论“无成功声明”成立，但审计追踪仍混淆了两类失败。

## 剩余 P0/P1

**P0：无。**

**P1：**
1. **P1-C-1**：untestable 假设带 evidence_for 并进入 candidate `evidence`/`evidence_for`（FX H-INT、commodity H-SUPPLY）；测试与 contract 均未拦截。阻断验收。
2. **P1-C-2**：假设是 class/region 模板而非真正 asset-specific（20 条仅 7 种结构签名；commodity/sector/country/FX 内部逐字同构）。
3. **P1-C-3**：`available` 可用性被高估（coarse `cross_asset`、CN sector 的 UST、commodity 的 DXY/UST），直接影响 distinguishability 与 tier。
4. **P1-C-4**：commodity ETF（SLV）被当作连续期货，H-ART/test 不适用。
5. **P1-F-1**：`evaluation/new_window/V2_EVALUATION_RESULTS.md` 仍把 2025-12-31 标为 `Test split` 并称“on test”，与非独立窗口/NOT VALIDATED 冲突。

**P2（不阻断，但应在最终签署前修文档/数据）：**
- DB evidence 陈旧残留（13 条，7 个候选），upsert 不 prune。
- A→B 文档 `refused` vs `rejected`、`out_of_scope` vs `no_registry_identity` 不一致；历史 env-error result 仍为 `rejected`。
- 两份 20 条 artifact 字节相同，无生成命令/时间戳/SHA，provenance 不可复核。
- “15 distinct hypothesis signatures”未定义口径；结构定义只有 7。
- crypto 只有 1 个经济假设 + 1 个数据伪影假设；当前无 crypto 候选可复核。
- 工作树在审计期间出现未提交 `goe/release.py` 改动（非本代理），冻结性需由工程侧确认。

## DISCOVERY VALUE

**DISCOVERY VALUE: NOT VALIDATED.**

- 2025-12-31 已用于 V1 验证 case，不是独立 test；该窗口 D **1.000** < C **1.500**（A 1.083/B 0.917），P@3 D **0.00** vs C **0.67**。
- 2021-12-31 在 V2 gate 改动后被复用，只能算 exploratory：该日 D 0.750，C 0.583，A 0.833，D 仍未超过 A；全样本 D 0.833 < C 0.979。
- 无独立 test split；无 human/expert labels；单 LLM rater，且早期/最终评分不稳定（D 1.350 → 0.833）。
- 盲评卡片测的是“资产选择 worthiness”，不是 V2 的 research question/hypotheses/falsifiers；问题质量仍未测量。
- 未发现 test-date tuning；禁止在复用日期上调参。结论保持 **NOT VALIDATED**，不得表述为 V2 优于 A/B/C，也不得把 2025 结果当作独立验证。
