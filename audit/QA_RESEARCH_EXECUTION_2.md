# N225 research execution — 独立复审（只读 / 第二轮）

**对象**：`architecture/research-v2`，HEAD `13f2620` + 工作区未提交/未跟踪改动
（`goe/research_exec.py`、`goe/cli.py`、`goe/db.py`、`tests/test_research_exec.py` 均未提交）
**样本**：`research_results/2026-11-13/N225/*`，复审快照 **2026-11-15 20:47:52**
（复审过程中 artifact 于 20:46→20:47:52 被重新生成；DB 与最终 artifact 一致）
**结论**：**方法论 P1 已修复，但闭环仍为 NO-GO（有条件接受）**。
P0 = 0。仍余 **2 个工程 P1（provenance、测试/CI）**；其余为 P2/P3。
“prior-US 2026-11-05、H-GLOBAL supported、INCONCLUSIVE、DB hypotheses 写回”均经独立复核属实。

## 0. 判定摘要

| 验收 | 结果 | 说明 |
|---|---|---|
| A 证据获取 | **PASS** | 原始 close 可复算；同日 Asia + 前一美股 session；`data_hash` 覆盖原始数据 |
| B 实际检验 | **PASS** | 5 项检验均有显式规则/阈值；声明与实现一致；无同日美股 lookahead |
| C 假设更新 | **PASS**（附 P2） | DB hypotheses 已更新（6 条 evidence 评估 + H-EQJP-ASIA-REGIONAL 新建）；candidate 阶段未推进 |
| D Finding | **PASS**（附 P2） | INCONCLUSIVE；无 alpha/mispricing；无 stale “contradicted”；HSI/CSI 弱势未写入 learned |
| E 独立 QA | **本次补齐** | 只读复核；不代表修复 |

## 1. P0

**无。** 未发现伪造价格、未使用 as_of 之后的数据、未伪造政策日期或 consensus。

## 2. PIT lead/lag（核心，已修复）

用 DB 原始 close 独立复算（与 `evidence.json` 全部一致）：

| 资产 | 日期 | close | return |
|---|---|---|---|
| N225 | 11-06 | 57434.77 / 61077.90 | **-5.9647%** |
| TOPIX | 11-06 | 388.60 / 415.60 | **-6.4966%** |
| TAIEX | 11-06 | 39701.64 / 41574.72 | -4.5053% |
| KOSPI | 11-06 | 5059.69 / 5383.80 | -6.0201% |
| HSI | 11-06 | 24481.86 / 24796.98 | -1.2708% |
| CSI300 | 11-06 | 4054.28 / 4113.41 | -1.4376% |
| SPY | **11-05** | 733.00 / 766.81 | **-4.4092%** |
| QQQ | **11-05** | 647.05 / 691.95 | **-6.4889%** |
| VIX | **11-05** | 28.18 / 16.61 | **+69.6568%** |
| USDJPY | **11-05** | 158.357 / 158.469 | -0.0707% |

- 同日（11-06）美股实际为 SPY **+0.31%**、QQQ **+1.40%**、VIX **-9.01%**，代码/artifact **均未使用**；
  `observed.data_date`、`global_lead_test.prior_us_session`、`learned` 全部为 2026-11-05。
- 11-05 美股收盘（美东 16:00 ≈ 东京 11-06 05:00）早于日本 11-06 开盘，lag 方向正确。
- 旧结论“US-global contradicted”已消失；现行文本为 “consistent, not contradicted”，
  H-EQJP-GLOBAL 由 CONTRADICTED 改为 **SUPPORTED_BY_AVAILABLE_EVIDENCE**。与用户口径一致。
- 无未来数据：DB 最大日期 = as_of 2026-11-13；`FeatureBuilder` 以 `end=as_of` 载入并截断；
  reversal 只用 11-09/10/11 三根 bar（+6.6403%），在 as_of frame 内。

## 3. Local vs regional Asia

- TOPIX -6.50%、TAIEX -4.51%、KOSPI -6.02% 均为同日；local/regional 规则实现一致：
  `TOPIX < -3%`、`TAIEX & KOSPI < -3%`，两项 pass=True。
- finding 状态 **INCONCLUSIVE**，learned 明写
  “Japan-local and regional Asia explanations both survive; broad indices cannot separate them.”
- 无 tech-specific 过度归因：tests 写 “tech-specific attribution not identified”，
  hypothesis note 写 “sector/tech channel is not identified”。
- **P2（未修复）**：HSI -1.27%、CSI300 -1.44% 只在 `evidence.json`，**未进入 learned**
  （上一轮已指出）。因此 “regional Asia co-move supported” 口径偏宽，实际更强的是
  北亚（JP/TW/KR）；建议改为 “North Asia co-move；HK/CN 明显较弱”，不应让读者以为全亚洲同跌。

## 4. FX / policy

- FX：使用 prior-session USDJPY（11-05），规则 `|fx| > 2%`，实测 -0.07% → pass=False，
  H-EQJP-FX = WEAKENED。规则声明与实现一致（上一轮“声明/实现不符”已修复）。
- **P2**：2% 阈值无来源/无敏感性；单日 FX 不足以支撑 “JPY/cross-border flow weakened”，
  更准确是 “prior-session FX 无大动，不能作为主解释”；缺失 FX 时也会落到 WEAKENED（缺数据≠反证）。
- **P2**：`global` 规则写作 “VIX > 0”，实际比较的是 VIX **return**（+69.66%）> 0，
  字面有 level/return 歧义，且无幅度阈值；QQQ 被引用但未进入 pass 条件。
- **P2/P3**：`_policy_event_on()` 为死代码且分支写错；实际逻辑内联读 `config/events.yaml`。
- policy 结论 **已正确**：真实文件存在（35 条，覆盖 2026-11-20..2027-06-17，`events --check` 通过），
  11-06 无条目；文本为 “No scheduled event ... not proof no policy news occurred”，
  不再声称 “no calendar / none on 11-06”。状态 INSUFFICIENT_DATA 合理。
- **P2**：`learned` 用 `{x:.2%}`，任一资产缺失会 TypeError（当前数据不触发）。

## 5. Hash / provenance / 测试

- `input_sha256 = cfd64d95…`，用 artifact 内
  `{observed, event, prior, as_of, rules, data_hash}` 独立重算 **完全一致**；
  `data_hash = 55e06c14…` 覆盖原始价格输入，`rules` 已纳入 hash。上一轮 “hash 不含 rules/raw” 已修复。
- **P1（工程/provenance，未修复）**：`code_commit = 13f262019…`，但
  `git ls-tree HEAD` 只有旧版 `goe/cli.py`、`goe/db.py`；`goe/research_exec.py`、tests、
  `research_results/` 全部未跟踪/未提交。即 **13f2620 无法复现该 finding**；
  CI 的 `git clean -fdx` 会删除这些未跟踪文件，CI 也看不到该命令。provenance 目前是“工作区快照”，
  不是记录的 commit。
- **P1（工程/测试，未修复）**：`tests/test_research_exec.py` 仅 2 个 helper 测试
  （`_event_date` as_of 上界、`_ret` 未来日期返回 None），已通过；
  但**没有任何测试**覆盖 prior-US lag、同日美股排除、5 条决策规则、reversal 边界、
  hypotheses/finding 写库。核心修正（PIT lag）完全没有回归保护。
- **P2**：event 选择为 ex-post：截至 as_of 的 90 session 取 |return| 最大，窗口含 11-09..11-13；
  本例仍选中 11-06，结果不变，但方法不是 event-time 独立。
- **P2**：`input_rows=780` 是 ≤event 的 3 年行数，而分析用到 as_of；与 “trailing 90” 口径不一致。
- **P2**：`research_v2_findings.created_at=2026-11-15T11:34:43Z` 为首插时间，upsert 不更新、
  无 `updated_at`，无法从表看出对应 20:47 的修正跑；payload（cfd6）与当前 `finding.json` 一致（已核）。
- **P2**：candidate `status/tier` 仍 `intelligence`、`updated_at=10:37`，finding 已产出但生命周期未推进。
- **P2**：hypotheses 行的 `type`/`label` 列未同步：H-EQJP-LOCAL、H-EQJP-FX 的 type 列仍是
  `global_risk`（payload 内为 local_market/fx），label 仍是旧中文。
- **P3**：`_policy_event_on` 死代码；artifact 是工作区生成，未纳入版本控制。

## 6. Finding 内容

- 有 learned / still_unknown / next_action；status INCONCLUSIVE；末尾 `DISCOVERY VALUE: NOT VALIDATED`。
- 无 alpha / mispricing / 收益承诺；`next_action` 明确不向 B 交接未支持研究。
- 无 stale 同日美股 “contradicted” 文本（全文仅 “consistent, not contradicted”）。
- **P2**：H-EQJP-GLOBAL 标签为 SUPPORTED，而 learned 只敢说 “consistent”；
  单日 lead-lag 关联不宜用 “supported” 的强度，至少 note 应保持 “association, not causal”。
- **P2**：ACCEPTANCE.md A 写 “new event cross-section was not in the candidate evidence record”；
  候选 payload 实际已含 TOPIX/SPY/QQQ/USDJPY 的 cross_asset 关系（TAIEX/KOSPI/VIX 确为新增），
  措辞应精确为 “TW/KR/VIX 当日横截面为新增”，否则重复上一轮 “不在候选内” 的夸大。

## 7. P0/P1 清单

**P0：0。**

**P1（工程/闭环，均非本轮新引入，上一轮已提出、仍未修复）**
1. **provenance 不成立**：`code_commit=13f2620` 不含 `research_exec.py`/CLI/DB 改动/tests；
   该 SHA 下无法运行 `research-case`，也无法产出本 finding。
2. **核心规则无测试且在 CI 不可见**：只有 2 个 helper 单测；lag 对齐、同日排除、5 条规则、
   DB 写回均无回归测试；未跟踪文件在 CI `git clean -fdx` 后消失。

**上一轮方法论 P1 状态：全部关闭** —— 时区错位（→ prior-US）、规则声明/实现一致
（local/regional/fx/reversal 均有阈值）、policy 使用真实 `events.yaml` 且措辞不再否定日历、
hypotheses 写回 DB、hash 纳入 rules+data_hash。

## 8. 闭环验收

**A–E：A PASS / B PASS / C PASS（P2 附注）/ D PASS（P2 附注）/ E 本次补齐。**

**闭环是否接受：暂不接受（conditional NO-GO）。**
研究执行本身已真实闭环到 `finding.json` + `research_v2_findings` + `research_v2_hypotheses`，
数值、PIT、结论口径均通过。阻塞项只剩工程侧两条 P1：
把 `research_exec.py`、`goe/cli.py`、`goe/db.py`、`tests/test_research_exec.py`（含 lag/规则/DB 测试）
提交，并以提交后的 SHA 重跑一次；届时 `code_commit` 可复现，即可给 **ACCEPT**。
