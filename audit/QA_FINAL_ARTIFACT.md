# FINAL ARTIFACT QA — HEAD 60e1bfc (code 4d06466)

- 审计时间: 2026-11-15 18:32 (+08:00)
- 范围: 只读；除本文件外未改动工作树
- 结论: **PASS（附 P2）**；无新增 P0/P1；**DISCOVERY VALUE: NOT VALIDATED**

## 判定

| 项 | 结果 | 证据 |
|---|---|---|
| 1. 20 候选 artifact / contract | **PASS** | `evaluation/v2_candidates_20_2026-11-13.json`：20 条；`research_queue` = 16 archive / 4 watch / 0 research；`handoff_eligibility` 全为 `a_retained`，eligible=0；`goe.contracts.validate_research_candidate` **20/20**，0 error |
| 1a. QQQ H-GLOBAL | **PASS** | `H-USEQ-GLOBAL` status=`open`，`evidence_for=[]`，`evidence_against`=`R²=0.38 < 0.50; residual_z=1.12`（discriminating） |
| 1b. VIX H-GLOBAL | **PASS** | `H-VOL-GLOBAL` status=`open`，`evidence_for=[]`，`evidence_against`=`R²=0.47 < 0.50; residual_z=-0.34`（discriminating） |
| 2. Dossiers 重生成 | **PASS** | N225/TAIEX/QQQ/XLV/VIX 五份 2026-11-13 + cotton Case D 2026-04-30，共 6 份 `.md`，各 **18 sections**；mtime 18:17。全目录无 hypothesis `status=supported`（仅 B capability `supported:false`）；无 cattle/live cattle/牛 文本 |
| 2a. Case D 可复现 | **PASS** | 在临时目录用 `scripts/build_case_d_dossier.py` 重跑（软链 goe/data/reports，未写仓库）：生成 MD 与仓库文件 **byte-identical**，sha256 `4c860a78211c56b4873502f200cd45a25d9148031f3627129664300551c76c1f` |
| 3. 236 proof | **PASS** | `audit/releases/release_4d064660ea.json`：commit 4d06466，dirty=false，passed=236，rerun=236；`audit/test_evidence/20261115T102212Z_4d064660ea.proof.json` exit_code=0，required=executed=236；`4d06466..HEAD` 仅新增 4 个 proof 文件，`goe/tests/contracts/config/scripts` 0 diff |
| 3a. Scan evidence | **PASS** | proof 内 report/scan_json/pipeline 三个 sha256 与本地文件重新计算 **全部一致** |
| 3b. CI #28 | **PASS** | 公开页面 `actions/runs/43703909698`：run **#28**，head `60e1bfc`，结论 **Success**（GitHub Actions 公共 HTML，独立读取；API 限流未能取 JSON） |
| 4. 新增 P0/P1 | **无** | 未发现新的 P0/P1 研究缺陷 |

## P0

无。

## P1

无。

## P2（不阻断发布）

1. **过期 untracked 导出**：`exports/research_candidates_2026-11-13.json`（11:06）仍含 3 个 `status="supported"`（含 QQQ `H-USEQ-GLOBAL`、R²=0.38）。该文件被 `.gitignore` 忽略、不在 60e1bfc/236 proof 内，但 `docs/AGENT_OPERATING_MODEL.md:35` 把 research cards 指向该路径；若被当作对外导出会与冻结 artifact 冲突。建议重生成或删除，勿作为验收依据。（历史审计已记录同类问题）
2. **CI 记录滞后**：`audit/CI_SUCCESS_2026-11-15.md` 只列到 run 24，未记录 run 28；实际 run 28 已成功。建议补一行，仅文档一致性。

## DISCOVERY 状态

**DISCOVERY VALUE: NOT VALIDATED**。20 条候选 0 research / 0 eligible、4 watch、16 archive；无独立人工标签、无真正未来窗口；`evaluation/RESEARCH_VALUE_EVALUATION_V4.md` 的四轨结论（selection 无优势、question 未验证、evidence 不足、decision 部分）本轮未改变。Dossier 是研究工作流样例，不是研究 alpha 证明。

---
独立 QA：只读复核，未修改代码或产物。
