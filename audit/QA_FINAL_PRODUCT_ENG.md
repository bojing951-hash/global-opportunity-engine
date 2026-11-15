# QA FINAL PRODUCT / ENGINEERING — 独立终验

- 日期：2026-11-15
- 基线：HEAD `60e1bfc`（代码 `4d06466`），分支 `architecture/research-v2`，工作树 clean
- 范围：只读复核；除本文件外未改任何文件，未跑会写产物的默认命令（dossier 输出至 `/tmp`）

## 结论

**PASS WITH ISSUES（工程发布证据 PASS；研究证据文本有 1 个 P1）**

- **P0 = 0**
- **P1 = 1**：`goe/evidence/cross_asset.py:135` 的 global fit 反证据文案硬编码 `< 0.50`，对
  `R²=0.53 > 0.50`（真正失败项是 `residual_z=1.57 >= 1.5`）写成 `R²=0.53 < 0.50`，属事实错误，
  与上一轮 P1-2「伪造阈值文案」同类，修复不完整。**不影响**当前 hypothesis 状态（仍为 open）、
  队列（20/0 research）或 handoff（0 eligible），但研究证据文本不可原样对外。
- **P2**：`goe cli dossier` 默认只生成 4 个 watch（N225/TAIEX/QQQ/XLV），VIX 需显式 `--id`
  才能复现；README 已披露，但“4 watch + VIX”不是单命令。
- **P2**：本轮未重跑完整 236（约 2 分钟）；以已接受的 proof + CI run 28 重放 + 43 项定向测试为证据，
  完整套件本机执行未被独立重复。

## 1. 发布证明、236、扫描证据、manifest — PASS

- `python -m goe.cli verify-release --proof audit/test_evidence/20261115T102212Z_4d064660ea.proof.json --no-rerun`
  → `status=accepted`，commit `4d064660ea0741f652a37dad24c2840d06f8083b`，`passed=236`，
  `required=executed={count:236, sha256:3d065e58…}`，`skipped=0`，`rerun=null`（结构校验）。
- proof 自带 rerun：`236 passed, 0 skipped`；JUnit/log 同为 236，`10 deselected`。
- `audit/releases/release_4d064660ea.json`：`git_dirty=false`，`git_commit=4d06466`，
  `proof_path` 相对路径；3 个 artifacts 的 SHA-256 全部重算一致：
  `reports/report_2026-11-13.md`、`reports/scan_2026-11-13.json`、`exports/pipeline_2026-11-13.json`。
- 独立 `verify_scan_evidence(store, require_artifacts=True, reference_date=2026-11-15)`
  → **ACCEPTED**：`scan-20261115T044634Z-b68802`，as_of `2026-11-13`，
  prices 358,310 / indicators 159,508 / anomalies 1,506 / transmissions 5 / opportunities 11；
  config `7d4d8ae1a7ca…`、data `9350b109d05e…`、`readiness_ok=true`、`ingest_status=offline`。
- `opportunities_by_status`：watch 2 / excluded 4 / invalidated 2 / low_priority 3（与扫描一致）。
- HEAD 相对代码提交只新增 4 个 proof/manifest 文件（169 行），无代码改动。

## 2. GitHub Actions run 28 / `60e1bfc` — PASS

- 公开 Actions 页面解析：`verify-release` **#28** → run id `43703909698`，commit `60e1bfc`，
  `Status: Success`；工作流页 HTTP 200，title 含 `@60e1bfc`，job 为 `verify-release`。
- 该 workflow 在 `60e1bfc` 上重放 `audit/test_evidence/*.proof.json` 中最新 proof（`4d06466`）。
- 说明：这是公开 HTML 的 UI 状态，不是本机独立读 API；API 已限流。

## 3. Dossier CLI — PASS

- 默认：`goe cli dossier --out /tmp/qa_dossiers` → **4 个 watch**
  （N225 `455ff8e1a32f`、TAIEX `d1be6bcd3313`、QQQ `ed67c9acfee9`、XLV `08992cbc4a1e`）。
- 显式：`--id RC-20261113-US_VOL_VIX-c1092d4e5bea` → **VIX**（archive / Case B，gap 0）。
- 5 个重新生成的 JSON：`content_sha256` 全部可重算，且与冻结的 `research_dossiers/2026-11-13/*.json`
  逐字段一致（含 `content_sha256`）；Markdown 均 **18 sections**。
- 相对内容哈希：`Source & Version References.artifact_path` 为仓库相对
  `evaluation/v2_candidates_20_2026-11-13.json`（不是绝对路径），同名同内容跨目录可复现。
- D script：`scripts/build_case_d_dossier.py` 在 `/tmp` 重跑 → `CASE_D_DATA_ARTIFACT`，
  cotton 2026-04-30，hash 可重算且与冻结 `2026-04-30/CASE-D-…json` 一致；
  `artifact_path=scripts/build_case_d_dossier.py`（相对）。

## 4. Identity / PIT / curve / immutability / P1 修复 — PASS

定向运行：
`test_research_identity.py test_time_semantics.py test_external_evidence.py test_status_lifecycle.py test_dossier.py test_release_gate.py`
→ **43 passed**（0 failed/skipped，40.2s）。

- identity：stable content-hash ID、legacy alias、asset/date retarget 拒绝、theme 跨日稳定、event 跨日变化。
- immutability：`upsert_research_candidate` 拒绝同 id 改 as_of/instruments/theme；completed 不可静默 reopen；
  `set_research_status` 为唯一状态迁移入口。
- PIT：机会 recency 用 available_at；slice_as_of 不带入未来 macro/positioning。
- curve/consensus：cross-currency、mixed curve/type/date、future/stale 拒绝；单曲线身份必需字段。
- P1 前轮：VIX/QQQ 的 global hypothesis 已不再是 `supported`；artifact 中为 open +
  `R²<0.50` 反证据（N225 0.07、QQQ 0.38、VIX 0.47），Case B/C 语义与 R²>0.5 门槛一致。
- main/V1/B 未动：`main=e5da620`（=origin/main，HEAD 祖先）；V1 annotated tag
  `v1-frozen-1f2b341` → `1f2b341`；外部 B `investment-agent-dev` 工作树 clean，HEAD `fe38275`；
  `git status --porcelain` 空。

## 5. 新 P0/P1

- **P0：无。** 未发现伪造扫描/报告/独立评审/研究结果，或 release 门禁绕过。
- **P1：1**（见上）：`goe/evidence/cross_asset.py:135` 对 global fit 失败一律写 `< 0.50`。
  触发实例：`RC-20261113-US_FAC_MTUM-66083bd4ef45` / `H-USEQ-GLOBAL`，
  `value="R²=0.53 < 0.50; residual_z=1.57"`。实际 `R²=0.53` 通过，失败原因是
  `residual_z=1.57 >= 1.5`；文案把通过项说成未通过，与上一轮 P1-2 同类。
  建议改为按实际失败条件生成（R² 与 residual 分开），或输出真实比较。
- 已知残留（P2，非新增）：scan 证据依赖本地 101MB DB/未入库 reports/exports；合成一致 DB
  仍可过门；CI 在 `git clean -fdx` 后只重放测试 proof，不重算 scan；无 licensed consensus/OIS。

## 复现命令

```bash
git rev-parse --short HEAD                      # 60e1bfc
python -m goe.cli verify-release --proof audit/test_evidence/20261115T102212Z_4d064660ea.proof.json --no-rerun
python -m goe.cli dossier --out /tmp/qa_dossiers
python -m goe.cli dossier --id RC-20261113-US_VOL_VIX-c1092d4e5bea --out /tmp/qa_dossiers
python -m pytest tests/test_research_identity.py tests/test_time_semantics.py \
  tests/test_external_evidence.py tests/test_status_lifecycle.py tests/test_dossier.py \
  tests/test_release_gate.py -q -o addopts=
```

**裁决：工程发布链（proof / 236 / scan / manifest / CI / dossier / P1 identity）通过；研究证据文本有 1 个 P1，修复前不应宣称“零 P1”。**
