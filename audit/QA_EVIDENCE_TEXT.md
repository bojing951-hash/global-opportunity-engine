# FINAL QA — EVIDENCE TEXT（HEAD ffe4ba8 / code 7943ff7）

- 审计时间：2026-11-15 19:05 (+08:00)
- 范围：只读复核；仅新增本文件，未改代码/数据/产物
- 基线：`architecture/research-v2` @ `ffe4ba8`（代码提交 `7943ff7`），工作树 clean
- 结论：**PASS**；**P0 = 0，P1 = 0**；**DISCOVERY VALUE: NOT VALIDATED**

## 逐项核对

| # | 项 | 结果 | 证据 |
|---|---|---|---|
| 1 | MTUM `H-USEQ-GLOBAL` 反证文案 | **PASS** | `evaluation/research_candidates_2026-11-13.json` 的 `RC-20261113-US_FAC_MTUM-66083bd4ef45`：`evidence_for=[]`、`evidence_against[0].value="|residual_z|=1.57 >= 1.5"`、`status=open`；`evaluation/v2_candidates_20_2026-11-13.json` 同值。全仓库 artifact 已无 `R²=0.53 < 0.50` 类事实错误 |
| 2 | QQQ / VIX 使用 `R²<0.50` | **PASS** | QQQ dossier/artifact：`H-USEQ-GLOBAL` `evidence_for=[]`、`evidence_against="R²=0.38 < 0.50"`；VIX：`H-VOL-GLOBAL` `evidence_against="R²=0.47 < 0.50"`；均 `status=open`、`discriminating=true` |
| 3 | Artifact / dossiers 重生成 | **PASS** | `7943ff7` 同步更新 5 份 dossier（JSON+MD）与 3 个 evaluation 产物；按 `goe/dossier.py` 算法重算 5 份 dossier 的 `content_sha256` **全部一致**；`7943ff7..ffe4ba8` 仅新增 4 个 proof/manifest 文件（169 行），`goe/ tests/ contracts/ config/ scripts/` 0 diff |
| 4 | 237 tests proof | **PASS** | `audit/releases/release_7943ff7944.json`：commit `7943ff7`、`git_dirty=false`、`passed=237`、`rerun=237/237`；proof `exit_code=0`、`required=executed=237`、0 failed/0 skipped；log 尾部 `237 passed, 10 deselected` |
| 5 | CI run 29 绿色 | **PASS** | 公开 Actions run **#29** `actions/runs/43706048825`，页面标题含 `...final research evidence proof at 7943ff7 (237 tests) · …@ffe4ba8`；分支 `verify-release` badge = `passing`；工程侧独立 QA 记录 conclusion **Success**（1m47s，触发于 10:50 UTC，与 release `created_at=10:50:42Z` 一致） |
| 6 | 队列 / 资格计数 | **PASS** | 20 候选：`research_queue` = **16 archive / 4 watch / 0 research**；`handoff_eligibility` 全为 `a_retained`，**eligible=0**；`research_readiness` 全 `evidence_gap` |
| 7 | DISCOVERY NOT VALIDATED | **PASS** | 5 份 dossier 均 `"discovery_value": "NOT VALIDATED"`；`research_dossiers/README.md` 与 `audit/FINAL_ACCEPTANCE_CURRENT.md` 一致 |
| 8 | 新增 P0 / P1 | **无** | 修复仅改 `goe/evidence/cross_asset.py` 的失败原因分支 + 1 个单测；两个 V2 artifact 中均无 `status=supported` 的 `-GLOBAL` 假设；未发现新的事实性错误 |

## P0

无。

## P1

无。

## P2（不阻断发布）

1. **过期 untracked 导出（既有问题，本轮未修）**：`exports/research_candidates_2026-11-13.json`（11:06）未随 `7943ff7` 重生成；其 MTUM `H-USEQ-GLOBAL` 仍把 `R²=0.53 … residual_z=1.57` 放在 `evidence_for`，`evidence_against` 为空。该文件被 `.gitignore` 忽略、不在 237 proof / CI 内，但 `docs/AGENT_OPERATING_MODEL.md:35` 仍把 research cards 指向该路径。建议重生成或改指针，勿作为对外验收依据。若验收口径把该文件视为对外 artifact，此项应升为 P1；按冻结 artifact / 237 proof / CI 口径维持 P2（与此前 QA 口径一致）。
2. **文档滞后于最终运行**：`audit/TEST_EVIDENCE.md` 仍写 236 passed @ `671f5fa`；`PROJECT_STATE.md` 仍写 236；`audit/CI_SUCCESS_2026-11-15.md` 只列到 run 24（缺 run 28、29）。仅文档一致性。
3. **阈值文案舍入边界（潜在）**：`goe/evidence/cross_asset.py` 在 `r2=0.4999` 时会格式化为 `R²=0.50 < 0.50`；当前 20 候选无此取值，未构成现实缺陷。
4. **`residual_z=None` 按 0 处理（既有 P2）**：R²>0.50 且残差缺失时会被判 `supported`；当前 artifact 无此情形。

## 独立读取边界

GitHub API 返回 403（限流），Actions 单页 HTML 正文被截断；run 29 的身份由公开 run 页面标题 + 分支 badge=`passing` + 工程 QA 独立记录交叉确认，精确 conclusion 未由本 QA 单独解析到。

---

**判定：PASS（附 P2）；P0=0 / P1=0；DISCOVERY NOT VALIDATED。**
