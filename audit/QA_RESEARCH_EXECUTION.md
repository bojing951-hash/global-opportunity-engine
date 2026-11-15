# N225 research execution — independent QA（只读）

**对象**：branch `architecture/research-v2`，HEAD `13f2620` + 工作区未提交改动
（`goe/research_exec.py` 未跟踪，`goe/cli.py`、`goe/db.py` 已修改）
**样本**：`research_results/2026-11-13/N225/*`（2026-11-15 20:42 重新生成）
**结论**：**NO-GO / 未闭环**。无 P0（未发现伪造价格、未发现越过 as_of 的未来数据），
但有 **2 个 P1 方法论 + 2 个 P1 工程/闭环**。`INCONCLUSIVE` 状态本身诚实，不能作为
“研究闭环已验收”的依据。

## 0. 判定摘要

| 验收 | 结果 | 说明 |
|---|---|---|
| A 证据获取 | **PARTIAL** | 数值真实可复算，但“不在原候选内”不成立；来源/可用日期记录不完整 |
| B 检验 | **FAIL** | 4/5 有显式 pass 规则，但 local/global 规则实现与声明不符；reversal 无规则；US 同日比较存在时区错位 |
| C 假设更新 | **PARTIAL** | 更新只在 finding JSON；未写回 `research_v2_hypotheses`；policy 的“无事件”无来源 |
| D Finding | **PARTIAL** | 结构完整、状态诚实、无 alpha 声明；但核心 learned 之一（US-global contradicted）被时区错位推翻 |
| E 独立 QA | **本次补齐** | 此前无独立 QA 产物；本次为只读复核 |

## 1. 证据获取（A）

**通过的部分**：用 DB 原始 close 复算，`evidence.json` 的 8 个同日收益完全一致：
N225 -5.9647%、TOPIX -6.4966%、TAIEX -4.5053%、KOSPI -6.0201%、SPY +0.3124%、
QQQ +1.3987%、VIX -9.0135%、USDJPY -0.5424%。DB 最大日期 `2026-11-13`，
`FeatureBuilder` 在 `features.py:297` 截断到 as_of；**没有 2026-11-13 之后的 bar**。

**问题**：

- **P1（证据新颖性/验收口径）**：“was not in the original candidate” 不成立。
  `research_v2_candidates` 的原始 payload 已含 `cross_asset`：local TOPIX
  R²=0.7238、beta=1.1757、n=252；global（SPY/QQQ/DXY/HYG/GC/IEF）R²=0.0722；
  FX R²=0.0133。新增的只是 **event-day cross-section**（TAIEX/KOSPI/VIX 等）；
  plan 自己写 “cost: low; already stored”（`research_exec.py:113`）。
  因此这是“重算已有数据的当日切片”，不是获取了候选之外的新证据源。
- **P2**：`evidence.source` 只写 “GOE prices DB”，未把 `source_id=yahoo`、
  各资产 `fetched_at`、symbol 写入 artifact；`available_at` 标成 2026-11-06，
  但事件选择与 reversal 用到 11-13 的数据。可复算 ≠ 可审计到原始响应。
- **P2（事件日期选择）**：`_event_date`（`:77-80`）在 **截至 as_of 的 90 个 session**
  里取 |return| 最大，窗口 2026-07-02..2026-11-13，含事件后的 11-09..11-13。
  这是 ex-post 事件选择。本例把窗口截到 11-06 仍选中 11-06，**结果不变**，
  所以不定 P1；但方法本身不是“事件时点独立”，单测只验证了 as_of 上界。
- **P2**：`input_rows=780` 只统计到 event（`:213`），而分析用到 as_of；口径不一致。

## 2. 检验（B）

**关键 P1（方法论，结论级）——US/Asia 同日收益的时区错位**：

- 2026-11-06 日本收盘发生在美股 11-06 开盘之前。finding 用 **11-06 的美股收益**
  （SPY +0.31%、QQQ +1.40%、VIX -9.01%）判定 “US-global risk-off contradicted”。
- 但日本 11-06 之前的**上一个美股 session（11-05）**是：**SPY -4.41%、
  QQQ -6.49%、VIX +69.66%**；N225 11-05 仅 -1.79%（在美股 11-05 收盘前），
  11-06 才 -5.96%。这正是“美股 11-05 冲击 → 亚洲 11-06 补跌”的传导。
- 所以 `H-EQJP-GLOBAL: CONTRADICTED_BY_TEST` 与 learned
  “US risk assets moved the other way” 是**错位比较的产物**；用正确的 lag
  （Asia t vs US t-1），全球风险解释是**被支持**而非被否定。这是本次 QA 最重要的发现。
  修正前不得把该条写入 learned/finding。

**其余规则问题**：

- **P1**：`local_asia_test`（`:129-134`）声称的规则是
  “TOPIX/TAIEX/KOSPI same sign and materially negative, US/VIX not risk-off”，
  实现只判 `TOPIX < -0.03`；`asia_negative_count` 算了但没参与 pass。
  因此它只能说明“TOPIX 同跌”，不能区分 Japan-local vs regional Asia。
- **P2**：`H-EQJP-LOCAL` 与 `H-EQJP-ASIA-REGIONAL` 同时
  `SUPPORTED_BY_AVAILABLE_EVIDENCE`，正文又说“cannot separate”；两个标签同时
  supported 可以并存（非互斥），但会夸大区分度。应改为“两项均未被排除”。
- **P1**：`fx_test`（`:149-154`）plan 的规则是“USDJPY move explains a large share
  of N225 return”，实现只判 `|fx| > 2%`，没有估计解释份额/beta；
  且 2% 阈值无来源。`WEAKENED_BY_EVIDENCE` 的证据强度不足。
- **P2**：`global_risk_test` 的 pass 只用 SPY 与 VIX，QQQ 未进入判定；
  同日比较的时区问题见上。
- **P1/P2（reversal）**：`:155-163` 的 `reversal_test` **没有 pass 规则/阈值**，
  `findings.md:17` 打印 `pass=None`。它只描述 3 个 session 的 +6.64% 反弹；
  且若事件后不足 3 个 bar，会静默用更少 bar。用户要求的“reversal”检验没有定义。
  计算本身只取 `iloc[pos+1:pos+4]`，在 as_of 截断的 frame 内，
  **确实只用事件后、as_of 前的 bar**，也没有因果宣称——这一点通过。
- **P2**：HSI -1.27%、CSI300 -1.44%（evidence.json 有）未进入 learned；
  它们明显弱于 TW/KR，削弱“broad regional Asia”叙事，属于选择性引用。

## 3. 假设更新（C）

- **P1（闭环）**：finding 只 upsert 到 `research_v2_findings`
  （`research_v2_findings` 有 `RF-N225-20261113`，created_at `2026-11-15T11:34:43Z`）；
  `research_v2_hypotheses` 里 H-EQJP-LOCAL/GLOBAL/FX/POLICY/FUND **仍是
  open/untestable**，新加的 `H-EQJP-ASIA-REGIONAL` 根本不在 hypotheses 表；
  candidate 状态仍是 `intelligence`。**假设更新没有写回，闭环没有闭合。**
- **P2（policy）**：`:182` 写 “no policy-event calendar in stored data”，
  但仓库有 `config/events.yaml`（35 条，`events --check` 通过，覆盖
  2026-11-20..2027-06-17，含 BOJ 2026-12-18）；它只是不覆盖 11-06。
  因此 “no calendar” 不准确；`still_unknown` 的 “none on 2026-11-06”（`:208`）
  是无来源的否定断言。没有伪造 BoJ 日期/consensus（这点通过），但应改成
  “无法确认 11-06 是否有政策事件”，而不是“没有”。
- **P2**：`H-EQJP-GLOBAL` 的 note “US risk assets rose and VIX fell” 是硬编码，
  不是从 values 推导；数据变化时会失真。

## 4. Finding（D）

**通过**：有 learned / still_unknown / next_action；status `INCONCLUSIVE`；
无 alpha/mispricing/收益承诺；`next_action` 明确不向 B 交接未支持的研究；
`findings.md` 末尾有 `DISCOVERY VALUE: NOT VALIDATED`。

**问题**：
- **P1**：核心 learned “US-global risk-off explanation is contradicted” 与
  “Taiwan and Korea fell … regional co-move supported” 都建立在同日错位比较上；
  前者应被推翻。status 诚实不等于子结论正确。
- **P2**：README 说 finding “stores … `DISCOVERY VALUE: NOT VALIDATED`”，
  但 `finding.json` 没有该字段，只在 `findings.md` 里；文档与 artifact 不一致。
- **P2**：`H-EQJP-LOCAL` 的 note “does not prove causality” 是好的；
  但 “broad Japan/local, not idiosyncratic” 仍是从单日 co-move 推出的解释性措辞，
  应与 “co-movement only” 再拉开距离。

## 5. 验收 A–E 与闭环

- **A 获取：PARTIAL** — 数值真实、同日、无 as_of 之后的数据；但证据是“已存储数据”
  的重算，原候选已有 local/global/FX 回归；来源/可用日期只到 DB 级。
- **B 检验：FAIL** — 见 §2：时区错位、local 规则未实现、FX 规则不符、reversal 无规则。
- **C 更新：PARTIAL** — 更新只在 finding JSON，hypotheses 表未写回；policy 否定断言无来源。
- **D Finding：PARTIAL** — 结构/状态/无 alpha 通过；核心 learned 一条错误。
- **E 独立 QA：本次补齐** — 此前没有 `audit/QA_RESEARCH_EXECUTION.md`；
  本报告是只读复核，不代表修复。

**是否为真实闭环？**
**是真实执行，不是真实闭环。** 数据 → 检验 → finding → artifact → DB finding row
确实发生了（不是 plan-only dossier）；但：
1. 假设状态未写回 hypotheses，candidate 状态未更新；
2. `code_commit=13f2620` **无法复现**：`research_exec.py` 未跟踪，
   `git ls-tree HEAD` 无此文件，13f2620 也没有 `research-case` CLI；
   `input_sha256` 只 hash 了 observed returns/event/as_of（`:218`），
   不含原始价格/规则/plan；
3. 单测只有 `_event_date`/`_ret` 两个 helper 测试（`tests/test_research_exec.py`，
   未跟踪，pyc 时间 19:34:58）；没有一条测试覆盖五个决策规则，CI 看不到该文件；
4. 独立 QA 此前缺位。
因此是 **“real execution, not a validated/closed loop”**。

## 6. P0/P1

**P0：无。** 未发现伪造价格、未发现 as_of 之后的 bar、未伪造 BoJ 日期或 consensus。

**P1（方法论）**
1. **时区错位**：同日 US close 用于解释亚洲 event，导致 “US-global contradicted”
   结论反转；应使用 US t-1 / 或明确事件信息到达顺序。
2. **检验规则与声明不符**：local 只判 TOPIX、FX 只判 2% 阈值、
   reversal 无规则；三条都需要显式规则+阈值+结果。
3. **policy 否定断言**：有 calendar 却说没有，且 “none on 2026-11-06” 无来源；
   应改为 INSUFFICIENT_DATA/无法确认。

**P1（工程/闭环）**
4. **provenance**：`code_commit` 指向 HEAD，但真实代码未提交；
   `input_sha256` 不覆盖原始数据/规则；README 的 reproduce 命令在 13f2620 不可执行。
5. **更新未落库**：hypotheses 表仍 open/untestable，candidate 状态未变；
   H-EQJP-ASIA-REGIONAL 不在表中。

**P2（摘要）**：事件选择为 ex-post（本例不影响结果）；`available_at` 口径；
HSI/CSI 选择性遗漏；reversal 少量 bar 静默；missing-data 分支（FX 缺失会落到
WEAKENED，global 缺失会 KeyError）；硬编码 note；finding.json 无 DISCOVERY VALUE 字段；
证据不可追溯到原始 HTTP 响应。

## 7. 缺什么证据才能把 INCONCLUSIVE 变 CONFIRMED/REFUTED

1. **US 11-05 session 的 lagged 对齐**（已有数据，需重算，不需要新源）。
2. **日本行业/成分股 breadth**（TOPIX 行业指数、半导体 vs 内需），带 observation date；
   B 的 request 已提出，但尚无返回。
3. **Asia 半导体供应链暴露**（TW/KR/JP 行业映射），用于区分 regional tech vs Japan-local。
4. **政策日历覆盖 2026-11-06**（或明确声明无法确认）；不要用 “none” 代替。
5. **原始价格响应/row hash** 与规则 hash，才能独立复现。
6. **hypotheses 写回 + 独立 QA 签字**，才算闭环。
