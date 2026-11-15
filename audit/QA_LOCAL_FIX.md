# 本地修复独立复核 — HEAD 1b7aa89 / code d50c10d

- 时间：2026-11-15；仓库 clean（`git status --porcelain` 无输出），HEAD=`1b7aa89`，最近修复提交=`d50c10d`
- 范围：只读复核 `audit/QA_ZERO_GATE.md` 的 P1（GLOBAL 误挂 local、FX 低 R²、20/20 分级与契约、验收文档口径），未改代码、未重跑管线、未改 DB；仅新增本文件
- 方法：读 `goe/evidence/cross_asset.py`、`goe/research_triage.py`、冻结 artifact、`data/goe.db`、验收/证据文档；用 `.venv/bin/python` 对 artifact 与 DB payload 逐条跑 `validate_research_candidate`

## 判定

**PASS WITH ISSUES：零研究门禁核心成立（0 research / 20 intelligence，contract 20/20），无 P0。**
d50c10d 已修掉 GLOBAL 误挂 local 的 P1 和验收文档 "only N225 qualifies" 的 P1；仍有 2 个 P1（1 个文档证据口径新增、1 个前次 `distinguishability_level` 残留），均不改变 0/20 分级。

| # | 检查项 | 判定 | 关键证据 |
|---|---|---|---|
| 1 | local 证据不再挂到 GLOBAL 假设 | **PASS** | `cross_asset.py:142` 已改为 `by_suffix("-LOCAL")`，去掉 type fallback；artifact 中 RC-20261113-15/16 的 `H-USEQ-GLOBAL` 均为 "同日跨资产全球因子回归"（R²=0.38 / 0.53），RC-20261113-07 `H-SECCE-GLOBAL` 为全球因子 R²=0.03 反证；全 artifact 扫描 `claim=本地基准回归` 且 hypothesis_id 不以 `-LOCAL` 结尾的条数=0 |
| 2 | R²<0.30 的 FX 不计入 discriminating | **PASS** | `cross_asset.py:154` 保留 `float(r2 or 0)>=0.30` 门禁；artifact 中 `claim=本币汇率 beta` 且 R²<0.30 的 discriminating 条数=0；单假设最大 discriminating=1，无任何假设≥2 |
| 3 | 当前 artifact/DB = 20 intelligence / 0 research，contract 20/20 | **PASS** | artifact：20 条唯一 research_id，tier 20×intelligence，readiness 20×evidence_gap；DB：`research_v2_candidates` 20 行且 status 20×intelligence，`research_v2_results`=0、`research_v2_tasks`=0；DB payload 与 artifact 0 diff；契约 artifact 20/20、DB 20/20；DB 101 hypotheses 与 artifact 101 一致 |
| 4 | 验收文档不再声称 "only N225 qualifies"，CI 未验证仍披露 | **PASS** | `audit/V2_FINAL_ACCEPTANCE.md:46-48` 已改为 "**no candidate** has two (N225 has one strong local fit)"；`:34-37` 仍明确写 GitHub Actions 未实际执行、cross-OS 未验证；全仓仅 `QA_ZERO_GATE.md` 在引用旧文本 |
| 5 | 该窄区新增 P0/P1 | **无 P0；2 个 P1（见下）** | 代码/artifact/DB 无新增 P0/P1；文档层新增 1 个 P1，另 1 个前次 P1 未闭环 |

## P1

### P1-A（新增，文档证据口径）
`docs/EVIDENCE_SOURCES.md:24-28` 称 "Cross-asset evidence is measured, but **only one strong local fit exists**"。该断言与冻结 artifact 不符：

- RC-20261113-06 `H-EQCN-LOCAL`：R²=0.69，open、discriminating
- RC-20261113-08 `H-EQDE-LOCAL`：R²=0.84，open、discriminating
- RC-20261113-12 `H-EQJP-LOCAL`：R²=0.72，open、discriminating

即至少有 3 条 open 的强 local fit（另有 RC-16 open global R²=0.53），不是 "only one"。0/20 的真实原因是**每个候选的 open measured discriminating 假设<2**，不是全市场只有一条强 local 拟合。此句与已修的 P1-OLD-1（把降级过度归因于缺 consensus/OIS）属同类证据归因错误；不影响 tier，但会误导证据可得性判断，建议按 P1 修正措辞（去掉 "only one"）。

### P1-B（残留 P1-OLD-2，字段语义）
`goe/research_triage.py:235` 的 `distinguishability_level` 仍由 **availability**（`avail_ids`）而非 measured discriminating 计数决定：

- N225（RC-20261113-12）`materiality.distinguishability_level=2`，但其 open measured discriminating 仅 1 条（`H-EQJP-LOCAL` R²=0.72）
- 当前 tier 仍为 intelligence（`discriminating_count<2` 强制降级），故不影响 0/20，但字段语义仍不可信，与前次 QA_ZERO_GATE 判定一致

## P2（不阻塞本次结论）

- `audit/QA_ZERO_GATE.md` 在 d50c10d 中提交，但仍按冻结 `fe19ba0` 写 "P1-NEW 未修 / V2_FINAL_ACCEPTANCE:46 仍为 only N225 / 研究签收不通过"；对当前 HEAD 已过期，读者易误判。建议标注 "已在 d50c10d 关闭"。
- N225 `H-EQJP-FX` 仍写 "未做汇率 beta / not estimated"，而同一假设 `evidence_for` 又写 "本地汇率可观察 / local FX"；QA_ZERO_GATE 指出管线实际算过低 R² 后被门禁丢弃，低 R² 测量在 artifact 中不可见，属披露不足。
- P1-NEW 修复没有新增回归测试：`tests/test_cross_asset_evidence.py` 无 "sector candidate has GLOBAL but no LOCAL，local fit 不得覆盖 GLOBAL" 用例；d50c10d 也未改 tests。
- `exports/research_candidates_2026-11-13.json` 仍为旧 1 条 `RC-20261113-12 / priority_tier=A`（untracked，未同步 20 条）；若作为对外导出会与 0 research 冲突。
- `audit/V2_FINAL_ACCEPTANCE.md:3` 的 "final code `a20ce29`, proof commit `168291d`" 相对 HEAD 1b7aa89/d50c10d 已过期；仅 provenance 陈旧，不影响分级。

## 复验命令摘要

- `git rev-parse HEAD` → 1b7aa896e978fdbfd4f38d4f86106c843caee6f5；`git status --porcelain` → 空
- `validate_research_candidate`：artifact 20/20，DB payload 20/20，DB payload 与 artifact 0 diff
- artifact 扫描：tier 20×intelligence、readiness 20×evidence_gap、本地证据错挂 GLOBAL=0、低 R² FX discriminating=0、单假设最大 discriminating=1
- DB：candidates 20（intelligence 20）、results 0、tasks 0

**结论：核心零门禁 PASS，P1-NEW 与验收文档口径 P1 已关闭；带 2 个 P1（P1-A 文档只承认一条强 local fit、P1-B distinguishability_level 仍取 availability）与 5 个 P2。无 P0。**
