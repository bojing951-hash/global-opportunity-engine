# 证据门禁独立研究 QA（冻结 HEAD d914628 / code c4b89ad）

- 范围：证据门禁、20 条候选、跨资产证据、OIS/consensus 诚实性、DISCOVERY 状态
- 方式：只读代码/冻结 JSON/DB；未改代码、未重跑全量管线；仅写本文件
- 判定对象：`evaluation/v2_candidates_20_2026-11-13.json` 的 20 条；对照 `data/goe.db`

## 总判定

**FAIL（无 P0；P1 阻断研究验收）。** 数量结论（20 -> 1 A + 19 intelligence）成立，但唯一研究候选 N225 的“2 条 measured discriminating hypotheses”不成立：其中 H-FX 的 R²=0.0133，是被无条件计入的弱关联，不能区分竞争解释。若严格按“discriminating”定义，N225 只有 1 条（H-LOCAL），应降为 intelligence，即 **0 个研究候选**。

**DISCOVERY VALUE: NOT VALIDATED**（维持，未见虚假验证声明）。

## 逐项结论

| # | 检查项 | 判定 | 关键证据 |
|---|---|---|---|
| 1 | <2 条 measured discriminating -> 降级 | **PASS（机制）/ FAIL（对 N225 的计数口径）** | `research_triage.py` 硬条件 `discriminating_count < 2 -> intelligence`；19 条 artifact 均为 0/1，确为 intelligence。N225 count=2，但 H-FX R²=0.0133、beta=-0.454、z=0.25；`cross_asset.py` 的 fx 分支不设 R² 门槛、无条件写 `discriminating=True`，`count_discriminating` 只查 flag，不查解释力/独立性。 |
| 2 | 是否有基于 availability placeholder 的升级/降级 | **FAIL（升级侧）** | N225 `distinguishability_level=2` 取自 `bundle["tests"]` 的 `data_status=="available"`（LOCAL/GLOBAL/FX）；H-GLOBAL 实际 R²=0.0722、已写 `evidence_against`，却仍 `status=open`、test 仍标 available。A 级的 D2 部分是“数据存在”而非“测量可区分”。19 条降级本身由 count=0/1 决定，不是 availability 升级。 |
| 3 | 跨资产 R²/beta/residual-z、PIT、self-factor | **PARTIAL** | OLS 带截距、252 日、共同观测、残差末值/样本标准差，计算无前视；`compute_fits` 只吃 FeatureSet，DB 最大价 2026-11-13，无 >as_of 行。iid 在 global/local/fx 中均排除，无字面 self-factor。但：local 基准 TOPIX 与 N225 近乎同一日本大盘因子，独立解释力有限；global 为 6 资产等权收益，非结构因子。 |
| 4 | N225 是否真有 2 条可区分假设 | **FAIL** | 实质仅 H-LOCAL（R²=0.7238）一条强测量；H-FX R²=1.3% 不构成区分证据；H-GLOBAL 被同一数据否定（R²=0.07）。按“至少两个可区分解释”语义，N225 不应为 A。 |
| 5 | 证据项是否误导/无支撑 | **FAIL（P1）** | H-FX 把 R²=0.01 的回归放进 `evidence_for` 并称“本币汇率 beta”，暗示支持；实际只能算“测过、近乎无关”。N225 的 `open_hypotheses=4` 含已被 R²=0.07 否定的 H-GLOBAL；H-LOCAL 有支持证据却仍 open（global 有支持则被标 supported），状态语义不一致。candidate `evidence_for` 还聚合 H-POLICY 的“区域属于政策敏感市场”这类配置事实。 |
| 6 | 29 条降级是否都因“缺数据” | **FAIL（文档归因，P1/P2）** | 19 条中不少已有跨资产测量但未挂到假设：SLV global R²=0.4667、VIX global R²=0.4746，均因假设 id 不含 `-GLOBAL`/`-FX` 而未计数；commodity/rates/fx/sector 分支基本没有消费 global/local/fx fit。`docs/EVIDENCE_SOURCES.md` 把结果归因为“until consensus/OIS files supplied”，过度归因；多数是非国别股票假设未接线。 |
| 7 | OIS 诚实性 | **PASS** | 代码/文档一致：FRED SOFR/2Y/10Y 是 policy-path proxy，**不是 term OIS**；`config/evidence_sources.yaml` 默认 disabled；`fetch_external_evidence.py`/CSV `source` 明写 not term OIS。未发现声称 live OIS。启用后 source 字符串 `ois_curve` 仍可能被误读，属 P2。 |
| 8 | consensus 诚实性 | **PASS（无伪造）/ P2（文档过强）** | 仅 file-backed adapter，`enabled: false`，无行则不产出；无 fabricated values。`docs` 称“strict PIT, stale and source checks”，但 `consensus_evidence` 未校验 source 列，属 P2 文档过强。 |
| 9 | 20 条与 DB/导出是否一致 | **FAIL（P1 数据生命周期）** | 冻结 artifact 为 20 条（1 A/19 intel），但 `data/goe.db` 有 21 条：多出 `RC-20261113-21 WORLD_EQ_EEM`，`tier=B, status=active`，payload 无 `research_readiness`、无 cross_asset、无 discriminating 证据。若下游读 DB，会向 B 交付一个未经证据门禁的 B 级候选，直接破坏“仅 N225 研究”的结论。`exports/research_candidates_2026-11-13.json` 仍是旧 1 条无证据版本（P2 provenance）。 |
| 10 | 产品行为与 DISCOVERY | **PASS（方向）/ NOT VALIDATED** | 把证据不足者降为 intelligence、保留可见且不交付 B，是正确产品行为；文档明确“deliberate reduction, not failure”。但当前 1 条不稳健。`evaluation/V2_EVALUATION_RESULTS.md`、`new_window/RESULTS.md`、`audit/V2_FINAL_ACCEPTANCE.md` 均明确 NOT VALIDATED；未发现把门禁收紧冒充 discovery 提升的声明。 |

## 最强反证（P1）

`goe/evidence/cross_asset.py` 的 fx 分支：

```
h["evidence_for"] = [item("本币汇率 beta", f"R²={f['r2']:.2f}, ...")]
```

该 item 无条件 `discriminating=True`。N225 的 USDJPY 拟合 R²=0.0133、beta=-0.454、residual_z=0.2498（n=252）。R²=1.3% 意味着汇率只能解释 N225 日收益的约 1.3%，无法把“本地汇率/资金流”与其它解释区分开；它只是“测过”。但 `count_discriminating` 只检查 `status=="open"` 和 `discriminating` 标志，于是 N225 得到 count=2，进入 tier A 并通过 `contracts.py` 的 `research_readiness=="evidence_ok" and discriminating>=2` 校验。若把 fx 也要求 R²≥0.30（与 local/global 同门槛）或要求跨解释的增量区分度，N225 count=1，应降为 intelligence -> **0 research candidates**。这是“只有 N225 应为研究”这一验收结论的直接反证。

## 其余 P1 / P2

**P0：无。**

**P1：**
1. N225 的 H-FX 弱拟合被当作第二条 discriminating 证据，唯一研究候选不成立（见上）。
2. `distinguishability_level` 用 test 的 `data_status`（availability）而非已测量证据；N225 的 H-GLOBAL 已被 R²=0.07 否定却仍 open/available，A 级 D2 被抬高。
3. DB 残留 `RC-20261113-21 EEM tier B active`，不含 `evidence_ok`/跨资产证据；冻结 20 条 artifact 与运行库不一致，存在绕过门禁交付 B 的现实路径。
4. 19 条降级中多条已有 global/local 拟合，但因假设 id 未匹配 `-GLOBAL/-FX` 而未计数；“数据缺失”归因不准确，跨资产证据覆盖率被高估。

**P2：**
- TOPIX 与 N225 高度重叠，“local”不是独立第二因子；无字面 self-factor，但独立性弱。
- `H-LOCAL` 有支持仍 open、`H-GLOBAL` 有反对仍 open，假设状态语义不一致。
- `exports/research_candidates_2026-11-13.json` 陈旧（1 条、无 cross_asset），与冻结 20 条 artifact 不同步。
- consensus 文档称 source check，代码未校验 source 列。
- `ois_curve` 命名与“非 term OIS”披露并存，启用时仍可能误读。

## DISCOVERY 状态

**DISCOVERY VALUE: NOT VALIDATED.** 无独立 test split；2025-12-31 已用于 V1，2021 窗口在 gate 改动后复用仅为 exploratory；现有评估测的是资产选择 worthiness，不是 V2 研究问题质量。收紧门禁到 1 条不构成 discovery 验证，也不得据此声称 V2 优于 A/B/C。
