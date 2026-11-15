# FINAL ENGINEERING CHECK 2 — HEAD ffe4ba8 (code 7943ff7)

- 审计时间: 2026-11-15 18:54–19:00 (+08:00)
- 范围: 只读复核；除本文件外未改动代码/数据/产物（dossier 与 Case D 复现在 `/tmp` 完成）
- 基线: `architecture/research-v2` @ `ffe4ba8`，代码提交 `7943ff7`，审计开始时工作树 clean
- 结论: **PASS（附 P2）**；**P0 = 0，P1 = 0**；**DISCOVERY VALUE: NOT VALIDATED**

## 判定

| 项 | 结果 | 证据 |
|---|---|---|
| 1. proof `release_7943ff7944.json` accepted 237 | **PASS** | `python -m goe.cli verify-release --proof audit/test_evidence/20261115T104654Z_7943ff7944.proof.json --no-rerun` → `status=accepted`，commit `7943ff7944bd32d101faa2956c13c700791b9e4d`，`passed=237`，`required=executed={count:237, sha256:0d334461…}`，`rerun=null` |
| 1a. proof 自身一致性 | **PASS** | proof `exit_code=0`、`git_dirty=false`、`237 passed / 0 failed / 0 skipped`；JUnit `tests=237 errors=0 failures=0 skipped=0`；log 尾部 `237 passed, 10 deselected`；proof 内 rerun 亦为 237/237 |
| 2. Scan evidence | **PASS** | 三个 artifact 本地重算 SHA-256 与 release 全部一致：report `7ac3425521…`、scan_json `cd0bc50200…`、pipeline `9e6bd81adf…`；`scan_id=scan-20261115T044634Z-b68802`，as_of `2026-11-13`，counts prices 358,310 / indicators 159,508 / anomalies 1,506 / transmissions 5 / opportunities 11；`readiness_ok=true`，`ingest_status=offline` |
| 3. CI run 29 @ ffe4ba8 | **PASS** | 公开 Actions 页面独立读取：run **#29** = `actions/runs/43706048825`，head `ffe4ba8`，workflow `verify-release` / job `replay-release-proof`，**Status Success**，1m47s；触发于 2026-11-15 10:50 UTC，与 release `created_at=10:50:42Z` 一致 |
| 4. Dossiers 可复现 | **PASS** | 默认 CLI `goe cli dossier --out /tmp/goe_qa_dossiers2` 重生成 4 个 watch（N225/TAIEX/QQQ/XLV），`cmp` 与仓库 JSON **逐字节一致**；4 份 MD 均 **18 sections** |
| 4a. Case D 可复现 | **PASS** | 在 `/tmp` 复制脚本并软链 `goe/data/reports` 重跑 `scripts/build_case_d_dossier.py`（未写仓库），生成 MD 与仓库文件 **byte-identical**，sha256 `4c860a78211c56b4873502f200cd45a25d9148031f3627129664300551c76c1f`（与上一轮一致） |
| 4b. Artifacts | **PASS** | 见第 2 项；另 `HEAD` 相对代码提交 `7943ff7..ffe4ba8` 仅新增 4 个 proof/manifest 文件（169 行），`goe/ tests/ contracts/ config/ scripts/` 0 diff |
| 5. main / V1 / B 未动 | **PASS（仓库侧）** | `main=e5da620=origin/main` 且为 HEAD 祖先；annotated tag `v1-frozen-1f2b341` 对象 `d626970` 未变，解引用 `1f2b341`，为 HEAD 祖先；B 基线分支 `fix/autonomous-audit-remediation` tip 仍为 `1f2b341`。若 B 指外部 investment-agent 仓库，该仓库不在本工作区，无法从本仓库独立证明（沿用既有 QA 口径的已知边界） |
| 6. 新增 P0/P1 | **无** | `7943ff7` 仅改 `goe/evidence/cross_asset.py` + 1 个测试并重生成 dossiers/artifacts；抽查全部 H-GLOBAL 反证据：QQQ `R²=0.38 < 0.50`、VIX `R²=0.47 < 0.50`；高 R² 失败项 MTUM 现为 `\|residual_z\|=1.57 >= 1.5`，仓库内已无 `R²=0.53 < 0.50` 类事实错误；dossiers 无 hypothesis `status=supported` |

## P0

无。

## P1

无。

## P2（不阻断发布）

1. **文档滞后于最终运行**：`PROJECT_STATE.md`、`TEST_RESULTS.md`、`audit/FINAL_ACCEPTANCE_CURRENT.md` 仍写 236 tests / 旧 proof；`audit/CI_SUCCESS_2026-11-15.md` 只列到 run 24，未记录 run 28 与 **run 29**。均属文档一致性，不影响 proof/CI 事实。
2. **阈值文案的舍入边界**：`goe/evidence/cross_asset.py` 中 `r2 <= 0.50` 分支在 `r2=0.4999`（格式化为 `0.50`）时会写出 `R²=0.50 < 0.50` 这类字面不成立的句子；当前 artifact 无此取值，故不构成现实缺陷，建议后续改为「未达 >0.50」表述。
3. **过期 untracked 导出**：`exports/research_candidates_2026-11-13.json`（11:06）仍含 3 个 `status="supported"`；该文件被 `.gitignore` 忽略、不在本 proof/CI 内，但 `docs/AGENT_OPERATING_MODEL.md:35` 仍指向该路径，勿作为对外验收依据（历史审计已记录）。

## DISCOVERY 状态

**DISCOVERY VALUE: NOT VALIDATED**。20 条候选 0 research / 0 eligible（16 archive、4 watch）；`evaluation/RESEARCH_VALUE_EVALUATION_V4.md` 的四轨结论未改变；Dossier 是研究工作流样例，不是研究 alpha 证明。

---

独立 QA：只读复核，未修改代码或产物；本文件为唯一写入。
