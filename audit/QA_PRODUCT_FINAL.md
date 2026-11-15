# 产品最终 QA — HEAD 21ec10c / code 7082952 / 236 tests

- 仓库：`global-opportunity-engine`；分支 `architecture/research-v2`；HEAD `21ec10c`（code `7082952`）。
- 方式：只读核查 + 临时目录重生成（未改仓库代码/数据/dossier）；仅新增本文件。审计开始时工作树 clean；结束时另有并行 QA 的未跟踪 `audit/QA_RESEARCH_FIX.md`（不属于本审计）。
- 时限：5 分钟（实际按短时审计执行）。

## 总判定

**FAIL（工程 release 证据可用；研究产品验收不可签署 PASS；P1 = 2）**

- **P0 = 0**：未发现伪造市场事实、伪造独立评审、伪造研究结果。
- **P1 = 2**：P1-1 为上轮 `QA_RESEARCH_PRODUCT.md` 的 **global hypothesis `supported` 与自身 R²>0.5 门槛矛盾未真正关闭**（冻结 artifact 与重生成 dossier 仍 `supported`）；P1-2 为本轮修复新引入的 `evidence_against` 伪阈值文案。
- 本轮工程项（proof / CI / dossier CLI / 18 节 / 相对路径 / 无假评审 / identity/PIT/curve / main/V1）均通过。

## 1. 逐项核对

| # | 检查项 | 结果 | 证据 |
|---|---|---|---|
| 1 | `release_7082952542.json` accepted | **PASS** | `verify-release --proof audit/test_evidence/20261115T100540Z_7082952542.proof.json`（含 rerun）→ `status: accepted`；commit `70829525426ae6d2594b3da0eebc94231b773b32`；passed **236**、rerun 236、skipped 0；required/executed sha256 均为 `3d065e58…` |
| 2 | scan evidence | **PASS** | `scan-20261115T044634Z-b68802`，as_of 2026-11-13，status success，mode offline，readiness_ok=true；prices 358310 / indicators 159508 / anomalies 1506 / transmissions 5 / opportunities 11；report/scan-json/pipeline 三个 sha256 与本地文件逐一相同 |
| 3 | 236 tests | **PASS** | 本机 `.venv` 实跑 `-m "not network and not realdata"`：**236 passed, 10 deselected**；release proof 记录一致 |
| 4 | GitHub Actions 21ec10c | **PASS** | run **#27**（id `43702548083`），workflow `verify-release`，event push，commit `21ec10c`，branch `architecture/research-v2`，conclusion **success**；公共 HTML 标题为 `chore(release): research-product fix proof at 7082952 (236 tests) · …@21ec10c`，页面 Status=`Success`；API 同时确认 head_sha=21ec10c、completed/success |
| 5 | Dossier CLI 4 watch + VIX | **PASS** | 默认 `dossier` → 4 个 watch（N225/TAIEX/QQQ/XLV）；`--id RC-…VIX` → VIX；输出到 `/tmp` 后与 `research_dossiers/2026-11-13/` 已提交文件 **逐字节相同**（JSON+MD，10/10 SAME） |
| 6 | content hash / 相对路径 | **PASS** | 6/6 dossier 的 `content_sha256` 按 `dossier.py` 口径（去 hash 后 sort_keys 序列化）全部复算一致；`artifact_path` 为仓库相对路径（`evaluation/v2_candidates_20_2026-11-13.json`、`data/goe.db#anomalies/…`）；默认 CLI 也已复现（上轮 P2 路径依赖已修） |
| 7 | 18 sections / 无假评审 / 无假结论 | **PASS** | 6/6 dossier 均为 **18** 个 `##` 节；`Independent Quality Review = NOT_INDEPENDENTLY_REVIEWED`；`DISCOVERY VALUE: NOT VALIDATED`；`Result = NOT_EXECUTED` |
| 8 | Case D | **PASS（身份）/ P2（可复现）** | `CM_AGR_CT` 已全部改为 Cotton，`cattle/Cattle/Live Cattle` 在 D 的 MD/JSON 中均为 **0**；scan_id/config_hash/data_hash 已填；D 无法由 `dossier` CLI 复现（无对应候选 artifact，属手工维护），见 P2-3 |
| 9 | identity / PIT / curve | **PASS** | 定向实跑 `test_research_identity/test_time_semantics/test_contracts/test_external_evidence`：**22 passed, 1 skipped**（skip 为 `GOE_SLOW=1` 真实数据集成）；`7082952` 与 `21ec10c` 均未改 `goe/db.py`、`goe/evidence/external.py`；不可变 id/as_of/instruments/theme、终态保护、未来 vintage/observation/curve 拒绝代码与测试仍在 |
| 10 | main / V1 / B | **PASS（仓库侧）** | main = origin/main = `e5da620`，为 HEAD 祖先；V1 annotated tag `v1-frozen-1f2b341` → `1f2b341`（`fix/autonomous-audit-remediation` tip）；B（外部 `investment-agent-dev`）工作区 clean、HEAD `fe38275`，本仓库 adapter 明确不写入 B 仓库；外部工作区无法由本仓库完全证明 |

## 2. P0 / P1

### P0

无。未发现伪造市场事实、伪造独立评审、伪造研究结果。

### P1-1（阻断，未关闭）：VIX/QQQ 仍以 `supported` 发布，与自身 R²>0.5 门槛矛盾

- 已提交 artifact `evaluation/v2_candidates_20_2026-11-13.json`（自 `9f7e54e` 起未更新）中：
  - VIX `H-VOL-GLOBAL`：`status = supported`，证据 `R²=0.47, residual_z=-0.34`；
  - QQQ `H-USEQ-GLOBAL`：`status = supported`，证据 `R²=0.38, residual_z=1.12`。
- 同 dossier 的 falsification 明写 **`R² > 0.5 且残差 |z|<1.5`**（QQQ），VIX 的 `H-GLOBAL` 甚至没有 falsification 条目。
- 重生成后的真实 dossier（`research_dossiers/2026-11-13/…VIX…json:58-61`、`…QQQ…`）仍是 `supported`，并把 `R²=0.47/0.38` 列为 Supporting Evidence；即 `7082952` 仅在 `goe/evidence/cross_asset.py:127-138` 改了“未来生成”逻辑（新测试只覆盖合成输入 r2=0.40），**未重算/更新冻结 artifact**，产物未体现“VIX/QQQ stay open”。
- 影响：Case B 的“no explanatory gap”与 QQQ Case C 的证据基础仍是一个未达自身阈值的关联，与提交信息及合同不一致；这是上轮 P1-2 的残留，不是新 P0。
- 最小修法：用修复后的代码重生成 `evaluation/v2_candidates_20_2026-11-13.json` 并重生成 6 份 dossier（或在 artifact 中把两者改为 `open`、清空 supporting evidence、补 falsifier），再补“提交 artifact 中所有 `supported` 必须满足 R²>0.5+|z|<1.5”的测试。

### P1-2（新引入，需修）：新规则下的 `evidence_against` 写出假的 “<0.30”

- `goe/evidence/cross_asset.py:127-138` 已把支持门槛改为 `R²>0.50 且 |z|<1.5`，但第 135 行的反证文案仍为 `R²={r2:.2f} < 0.30`。
- 按新规则，`R²=0.47` 会被写成 “R²=0.47 < 0.30”（事实错误），且与 dossier 的 0.5 门槛冲突；`R²>0.5` 但 `|z|≥1.5` 时同样会输出假的 “<0.30” 归因。
- 一旦重生成 artifact/dossier，这条伪陈述会直接进入 §7 Contradicting Evidence；属证据链事实错误，应在重生成前改为 `R² <= 0.50` 或按实际失败原因分支。

## 3. P2（不阻断）

1. **Case D 0.98/0.90 并存**：`CASE-D-…md:11` 写 `near_high 0.90 (not 0.98)`，但 `:18`、`:22` 的 observed_phenomenon/研究问题仍写 `drawdown percentile 0.98`，同一 dossier 两种度量未统一。
2. **Case D 不可由 CLI 复现**：无候选 artifact/生成路径，D 为手工维护，仅 content hash 可复算；作为 A–D 真实案例之一，复现性弱于 A–C。
3. **测试未锁定产物状态**：236 全绿不覆盖“已提交 artifact 的 hypothesis status”，因此上述 P1 可与全绿测试共存。
4. **文档计数未同步**：`audit/TEST_EVIDENCE.md:3` 仍写 235、`research/RESEARCH_ACCEPTANCE_CONTRACT.md:30` 仍写 231（CI run 24/25），落后于 236 proof。

## 4. 结论

- **工程 release（proof/CI/测试/scan evidence）**：PASS。
- **研究产品（dossier/产物一致性/研究价值）**：**FAIL / CONDITIONAL**；P0=0，P1=2（P1-1 未关闭、P1-2 新引入），P2=4。
- **DISCOVERY VALUE = NOT VALIDATED**；A→B 仍 **NO-GO**（0 eligible，dossiers 6/6 `a_retained`）；不得宣称 A–D 验收 PASS。
