# 零研究门禁独立复核（冻结 HEAD fe19ba0 / code 4fac0ec）

- 范围：复核 `audit/QA_EVIDENCE_RESEARCH.md` 的两条 P1（FX 弱拟合计数、DB 残留），以及文档口径、PIT、OIS/consensus、DISCOVERY 状态
- 方式：只读代码、冻结 artifact、DB、文档；未改代码、未重跑管线；仅写本文件
- 时点：2026-11-15；HEAD fe19ba0 仅改 `V2_FINAL_ACCEPTANCE.md` 的 A→B 行（1 行），未触及零门禁；release proof 209 accepted
- 复验：fe19ba0 上 artifact 20×intelligence / 20×evidence_gap、contract 20/20 pass、DB 20 行且 active=0、prices 最大 2026-11-13

## 总判定

**核心零门禁 PASS：0 research / 20 intelligence 成立；无 P0。**
但修复提交 4fac0ec 引入 1 个新 P1（local 证据被 fallback 误挂到 GLOBAL 假设并覆盖原 global 证据），且 `audit/V2_FINAL_ACCEPTANCE.md:46` 仍保留 "only N225 qualifies" 的过期断言。**作为研究签收仍不通过。**

## 逐项核验

| # | 检查项 | 判定 | 证据 |
|---|---|---|---|
| 1 | FX 低 R² 不再计入 discriminating | **PASS** | `goe/evidence/cross_asset.py` fx 分支新增 `float(f.get("r2") or 0.0) >= 0.30`；20 条 artifact 中 `claim=="本币汇率 beta"` 的 discriminating 条目为 0；新增测试 `test_low_r2_fx_is_not_discriminating`。 |
| 2 | 当前 20 条为 0 research / 20 intelligence，全部过 contract | **PASS** | `evaluation/v2_candidates_20_2026-11-13.json`：`priority_tier` 20×intelligence，`research_readiness` 20×evidence_gap；逐条跑 `validate_research_candidate` 20/20 通过；最大 discriminating 计数=1，无候选 >=2。N225（RC-20261113-12）仅 H-EQJP-LOCAL（R²=0.72）1 条 measured，H-EQJP-FX 无 measured，tier=intelligence。 |
| 3 | DB 恰好 20、无残留 active research candidate | **PASS** | `data/goe.db` `research_v2_candidates`：20 行，status 全部= intelligence（active=0），无 `RC-20261113-21`；20 行 `payload_json` 与 artifact 逐条完全一致（0 diff）。 |
| 4 | 文档/验收口径为 0 research/20 intelligence | **FAIL（P1）** | 主口径已更新（`audit/V2_FINAL_ACCEPTANCE.md:6`、`docs/EVIDENCE_SOURCES.md:24`、`audit/EVIDENCE_GATE_DECISION.md:15`）；但 `audit/V2_FINAL_ACCEPTANCE.md:46` 仍写 "with current data only N225 qualifies"，与 0/20 直接冲突，属任务明确禁止的 "claim of 1 N225"。 |
| 5 | 跨资产 PIT、低 R² 不计、无伪造 OIS/consensus | **PASS（PIT/低 R²/伪造）** | `prices` 最大日期 2026-11-13，无 >as_of 行；artifact 所有 `available_at` 均 <=2026-11-13；`_fit` 仅用 FeatureSet 尾部 252 日。OIS 明写 policy-path proxy、非 term OIS；consensus 为 file-backed、默认关闭、无行不产出，未发现伪造值或 live OIS 声明。 |
| 6 | 新 P0/P1 | **1 个新 P1 + 1 个残留 P1** | 见下。 |
| 7 | DISCOVERY 状态 | **NOT VALIDATED（明确）** | `evaluation/V2_EVALUATION_RESULTS.md:20`、`audit/V2_FINAL_ACCEPTANCE.md:7,17,24` 一致；无独立 test split，未发现"门禁收紧=discovery 提升"的声明。 |

## 新 P1（本次修复引入）

**P1-NEW：`by_suffix(suf, typ)` 的 type fallback 把 local 证据误挂到 GLOBAL 假设，并覆盖 global 证据。**

- 现象（冻结 artifact）：RC-20261113-07 `H-SECCE-GLOBAL` 的 `evidence_for` 变为 "本地基准回归 R²=0.48"；RC-20261113-16 `H-USEQ-GLOBAL` 的 `evidence_for` 变为 "本地基准回归 R²=0.62"，而 d914628 时该假设是 "同日跨资产全球因子回归 R²=0.53"。
- 根因：`cross_asset.py` 中 local 分支 `by_suffix("-LOCAL", "global_risk")`；当假设 id 无 `-LOCAL` 后缀时，fallback 选中第一个 open 的 `global_risk` 假设（即 `-GLOBAL`），随后整段覆盖其 `evidence_for/evidence_against`。
- 影响：证据与假设错配，且丢失原 global 拟合记录；虽不改变 0/20 的分级结果，但属已发布 artifact 的证据语义错误，需在下一次冻结前修掉。

## 残留 P1（前次审计未闭环）

**P1-OLD-1：文档把 19 条降级过度归因于 "consensus/OIS files supplied"。**
`docs/EVIDENCE_SOURCES.md:24-25` 称 "intended honest result until consensus/OIS files are supplied"，但多条候选已有 global/local 测量、只是假设接线不足；该归因仍不准确。

**P1-OLD-2：`distinguishability_level` 仍取 availability 而非 measured evidence。**
N225 `materiality.distinguishability_level=2`，实际 measured discriminating 仅 1 条；该字段仍由 test `data_status=="available"` 抬升，A 级 D2 口径未修（当前已无 A 级，故不影响 0/20，但字段语义仍不可信）。

## 其余 P2

- `exports/research_candidates_2026-11-13.json` 仍为旧 1 条无 cross_asset 版本，未与冻结 20 条同步。
- N225 `H-EQJP-FX` 写 "未做汇率 beta / not estimated"，但管线实际已算 R²=0.0133 后被门禁丢弃；低 R² 测量在 artifact 中不可见，属证据披露不足（不影响计数）。
- DB `status` 列值为 `intelligence`（与 tier 同值），语义上混淆了生命周期状态与分级；当前不影响"无 active"结论。

## DB/契约核对摘要

- artifact：20 条；tier=intelligence 20；readiness=evidence_gap 20；contract 20/20 pass。
- DB：20 行；status=intelligence 20；payload 与 artifact 0 diff；无 RC-21。
- discriminating 计数分布：8 条候选各 1 条，12 条 0 条，最大 1。

## DISCOVERY 状态

**DISCOVERY VALUE: NOT VALIDATED.** 无独立 test split；2025-12-31 已用于 V1，2021 窗口为重用/exploratory；现有评估测资产选择而非 V2 研究问题质量。收紧门禁到 0 条不构成 discovery 验证。
