# V3 最终确认 QA（HEAD 9f4d25d / code 77dd868 / proof bd4e337）

- 审计对象：`global-opportunity-engine`，HEAD `9f4d25d`（code `77dd868`，proof `bd4e337`），245 tests，CI run41 SUCCESS（外部证据）
- 方法：只读静态审阅 + 只读 DB/artifact 核对 + 定向 pytest；仅写本文件；`git status --porcelain` 为空，未改代码/配置/测试/DB
- 环境：2026-11-15，分支工作副本干净；DB 以 `mode=ro` 只读打开

## 总判定

**通过（PASS）**：无 P0、无 P1。V3 可签署。

## 逐项核查

| # | 检查项 | 结论 | 证据 |
|---|---|---|---|
| 1 | TAIEX 最新 artifact 事件日 | **PASS** | DB 最新 TAIEX revision `RF-...-TW_EQ_TAIEX-d1be6bcd3313-4996b280`（created_at `2026-11-15T15:33:09Z`），`event_date=2026-11-06`，artifact 路径存在；`evidence.json` 的 `event_available_at=2026-11-06`、`decision_as_of=2026-11-13`。 |
| 2 | peers 排除自身 | **PASS** | TAIEX 最新 artifact 的 peer 角色仅取 HK_EQ_HSI（local）、CN_EQ_CSI300（regional A）、JP_EQ_N225（regional B）、US_EQ_SPY/QQQ、US_VOL_VIX、CN_FX_USDCNY；事件资产 TW_EQ_TAIEX 不在任何 peer/regional/global 测试中（仅作事件收益）。KOSPI 最新 `...-3071aa83` 同理，KR_EQ_KOSPI 已排除。 |
| 3 | regional_a/b 标签通用 | **PASS** | `tests.asia_regional_test` 键为 `regional_a_return=-0.014376`、`regional_b_return=-0.059647`（CN/JP 实际收益）；`H-EQ-REGIONAL.value` 为 `{"regional A": -0.014376, "regional B": -0.059647}`；`evidence.json` 标签为 `local`/`regional A`/`regional B`，不再是 TAIEX/KOSPI/TOPIX 硬编码。`goe/research_engine.py:146-149,214-218` 已改用 observed 标签。 |
| 4 | learned 表述 | **PASS** | learned 末条为 “Neither local nor regional thresholds were met; only the global lead is supported.”，与 `local_asia_test.pass=false`、`asia_regional_test.pass=false`、`global_lead_test.pass=true` 完全一致，不再出现上一轮 “Local and regional explanations both survive” 的自相矛盾。 |
| 5 | 代码 commit 当前 | **PASS** | 最新 TAIEX artifact `code_commit=77dd8686e01ebd37b1441012e8f1162a5aa9ef3c`，与 HEAD 9f4d25d 的 code commit 一致；proof `bd4e337` 为 9f4d25d 的父提交。 |
| 6 | KOSPI 正确 | **PASS** | 最新 KOSPI `...-3071aa83`（15:22:54Z）：learned “Neither local nor regional thresholds were met…”，local=false、regional=false、global=true；regional `regional_a_return=-0.01225`、`regional_b_return=-0.048983` 二者不同且均非事件自身 `-0.075654`，事件资产未混入 peer。 |
| 7 | 不可变 / 幂等 | **PASS** | 旧 TAIEX revision `...-720bca53`（code `2dbd52f`，learned 旧矛盾文案）原样保留未被覆盖，新 revision 为新增（不可变）；定向运行 `test_generic_execution_is_idempotent_and_keeps_artifact`：**1 passed**（0.33s）；finding 的 `input_sha256`/`data_hash` 固定，同输入 finding_id 稳定。 |
| 8 | 测试 / CI | **PASS** | 本地 proof `20261115T153430Z_bd4e3373cb.proof.json`：git_commit `bd4e337`、git_dirty=false、exit 0、245 passed / 0 failed / 0 skipped；CI run41 SUCCESS（外部 run 记录；仓库 CI 表最新提交记录为 run 34/39，run41 未入库）。 |
| 9 | P0/P1 | **无** | 见下 P2（非阻断、既有展示命名缺陷）。 |

## P0

无。

## P1

无。

## P2（非阻断，已在上一轮登记）

- 字段命名遗留：`tests.local_asia_test.topix_return` 实际存的是 local peer（TAIEX case 为 HK_EQ_HSI -1.2708%）、`tests.fx_test.prior_usdjpy_return` 实际存 USDCNY、`tests.reversal_test.n225_next_3d` 实际存 TAIEX 三 session 反转；KOSPI 最新 revision 的 `H-EQ-REGIONAL.value` 键仍为 `TAIEX`/`KOSPI` 而值为 CN/JP 收益。均属展示/字段命名，`learned` 与 pass 值真实、无自相矛盾，不影响 V3 结论。

## 最终状态

**PASS**：TAIEX 最新 artifact 事件 2026-11-06、peer 排除自身、regional_a/b 通用标签、learned 与检验一致、code commit 当前、KOSPI 正确、245 tests/CI run41、不可变与幂等均通过；无 P0/P1。P2 命名遗留不阻断签署。
