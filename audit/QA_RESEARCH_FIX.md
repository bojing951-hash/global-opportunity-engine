# QA — Research P1 修复复检（HEAD 21ec10c，代码 7082952）

- 分支：`architecture/research-v2`；HEAD `21ec10c`（release proof 指向代码 `7082952`）。
- 只读复检；仅写本文件。时间盒 5 分钟。
- 结论：**部分通过（5 项中 4 项通过，第 2 项失败）**。无 P0；新发现 P1 两项，均在“全局假设支持”链路上。

## 逐项结论

| # | 检查项 | 结论 |
|---|---|---|
| 1 | Case D 改为 Cotton，无 Live Cattle/cattle/slaughter；source refs/scan meta 存在 | **PASS** |
| 2 | H-GLOBAL 仅 R²>0.50 且 \|z\|<1.5 才 supported；VIX/QQQ 不 supported；无臆造解释 | **FAIL（P1-1/P1-2）** |
| 3 | Supporting Evidence 排除 availability/config flag；markdown 有 available_at；Case B 标 no explanatory gap | **PASS（附 P1-1 影响）** |
| 4 | 18 节/6 dossier；236 proof；0/4/16/0；DISCOVERY NOT VALIDATED | **PASS** |
| 5 | 新增 P0/P1 | 无 P0；P1 两项 |

### 1. Case D 身份修复 — PASS
- `research_dossiers/2026-04-30/CASE-D-CM_AGR_CT-20260430.md/.json` 均为 Cotton/CM_AGR_CT；全目录 `grep -riE "cattle|slaughter" research_dossiers/` 无命中（旧 `exports/`、`evaluation/` 中的 `CM_AGR_LE` 是另一个 Live Cattle 候选，不属 Case D）。
- §18 含 `artifact_path`（相对路径 `data/goe.db#anomalies/AN-ef670579d660c2`）、`scan_id=scan-20261115T044634Z-b68802`、`config_hash`、`data_hash`；content SHA 存在。

### 2. H-GLOBAL 支持规则 — FAIL
- 代码已改：`goe/evidence/cross_asset.py:127-135` 为 `r2 > 0.50 and abs(residual_z) < 1.5`，新单测 `test_global_support_requires_r2_above_documented_threshold` 覆盖 R²=0.40 → open。
- 但**产物未按新规则重算**：`evaluation/v2_candidates_20_2026-11-13.json`（mtime 17:46，早于代码修复）仍为：
  - `RC-20261113-US_EQ_QQQ-ed67c9acfee9` / `H-USEQ-GLOBAL`：`status="supported"`，evidence_for `R²=0.38, residual_z=1.12`；
  - `RC-20261113-US_VOL_VIX-c1092d4e5bea` / `H-VOL-GLOBAL`：`status="supported"`，evidence_for `R²=0.47, residual_z=-0.34`。
- 两份 dossier（18:01 生成）原样继承：VIX、QQQ §6 Supporting Evidence 均列出该回归（R²=0.47 / 0.38）；QQQ §10 falsification 明写 “R² > 0.5 且残差 |z|<1.5”，§6 却以 R²=0.38 作支撑——产物自相矛盾。因此“VIX/QQQ H-GLOBAL 不 supported”在产品层未达成。
- **P1-2（新引入/遗留）**：同一函数未同步 evidence_against 文案，仍为 `f"R²={r2:.2f} < 0.30; residual_z=..."`。按新规则，R²=0.47 会被写成 “R²=0.47 < 0.30”（伪陈述），且与 dossier 的 0.5 阈值冲突；在 R²>0.5 但 |z|≥1.5 时同样会输出假的“<0.30”解释。属需修复的事实性文案。

### 3. 证据口径 — PASS（受第 2 项影响）
- 六份 dossier 的 §6 仅含 measured/statistical 项，无 availability/config flag；`_dedupe` 过滤条件为 `discriminating or class=="statistical_association"`。
- markdown 证据后缀均渲染 `(source: ..., available: ...)`（Case D、VIX 等 6/6 可见）。
- VIX `case_label=CASE_B_NO_EXPLANATORY_GAP`，合同 B 行亦改为 “no explanatory gap remains; no causal/explanatory claim is invented”。
- 但 VIX §6 的 R²=0.47 回归在新规则下并非支持项（见 P1-1），该节语义仍待重生成后复核。

### 4. 数量与发布证明 — PASS
- 6 份 dossier（1×Case D + 5×2026-11-13），每份 18 节（`## 1..18`），均带 `DISCOVERY VALUE: NOT VALIDATED`。
- `audit/test_evidence/20261115T100540Z_7082952542.proof.json`：exit 0，passed=236，failed/errors/skipped=0，`git_commit=7082952`，`git_dirty=false`；release `audit/releases/release_7082952542.json` 记录 236 且 rerun 236。
- `evaluation/v2_candidates_20_2026-11-13.json`：20 候选，queue = 4 watch / 16 archive，handoff 全部 `a_retained`，即 **0 research / 4 watch / 16 archive / 0 eligible**。

## 新增问题

- **P0：无。**
- **P1-1（阻塞项，需修）：** H-GLOBAL 新阈值只改了代码，未重生成 `evaluation/v2_candidates_20_2026-11-13.json` 与 6 份 dossier；VIX/QQQ 仍以 R²=0.47/0.38 标 `supported` 并进入 Supporting Evidence，与自身 0.5 阈值及本次修复目标冲突。
- **P1-2（需修）：** `goe/evidence/cross_asset.py` 的 evidence_against 仍写 “< 0.30”，与新 0.50 阈值不一致，会生成伪解释（如 “R²=0.47 < 0.30”）。
- P2（不阻塞）：`audit/TEST_EVIDENCE.md` 仍写 235、`research/RESEARCH_ACCEPTANCE_CONTRACT.md` 仍写 231，均落后于 236 proof；`h["status"]` 三元条件重复判定 support；`residual_z is None` 被当作 0 会通过 |z|<1.5。

## 复检建议
1. 用 7082952 代码重跑候选生成 + 全部 dossier，断言 QQQ/VIX `H-*-GLOBAL.status=="open"`、§6 无该回归、§7 为正确阈值的 against 文案。
2. 修 evidence_against 文案为 0.50，并同步/刷新 TEST_EVIDENCE 与合同中的计数。
