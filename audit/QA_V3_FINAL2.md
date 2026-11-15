# V3 最终独立 QA（第二次，HEAD e354670 / code a6d1d43 / proof 4198a23）

- 审计对象：`global-opportunity-engine`，HEAD `e354670`（QA 请求时为 `df53993`；e354670 仅删除临时残留，`git show e354670` 1 file / -245 行），代码 `a6d1d43`，proof `4198a23`，分支 `architecture/research-v2`
- 方法：只读静态审阅 + 只读 DB/artifact 核对 + 定向 pytest；仅写本文件，未改代码/配置/测试/DB
- 环境：QA 开始时 `git status --porcelain` 为空；`data/goe.db` 为共享工作副本，未写入

## 总判定

**不通过（FAIL，P1 一项）；无 P0。**

KOSPI 上一轮的自指问题已修复，幂等/不可变/DB 路径/CI 均通过；但 **TAIEX 动态 case 的 canonical finding 仍是修复前代码的旧产物，且 learned 与其自身 local 检验矛盾**，不能宣称“V3 动态 case 全部已修正”。

## 逐项核查

| # | 检查项 | 结论 | 证据 |
|---|---|---|---|
| 1 | KOSPI 动态 case | **PASS** | 最新 DB finding `...-3071aa83`（2026-11-15T15:22:54Z）peers 为 HK_EQ_HSI/CN_EQ_CSI300/JP_EQ_N225，事件资产 KR_EQ_KOSPI 已排除；`asia_regional_test` 为 `regional_a_return=-0.01225`、`regional_b_return=-0.048983`，二者不同且都不是事件自身的 `-0.075654`；local=false、regional=false、global=true；learned 末尾为 “Neither local nor regional thresholds were met; only the global lead is supported.”，与 tests 一致。 |
| 1b | TAIEX 动态 case | **P1（阻断）** | DB 最新 TAIEX finding `...-720bca53`（code `2dbd52f`，早于修复；15:03:33Z）`local_asia_test.pass=false`（HK/China -1.27%），但 learned 末尾写 “Local and regional explanations both survive”，**自相矛盾/不真实**；`asia_regional_test` 键名 `taiex_return=-0.059647`、`kospi_return=-0.060201`，实际值为日本/韩国（事件资产 TAIEX -4.51% 已排除），`H-EQ-REGIONAL.value={"TAIEX": -0.059647, "KOSPI": -0.060201}` 把日本收益标成 TAIEX。当前代码 `goe/research_engine.py:225-231` 在 local=false/regional=true 时会输出 “Regional co-move survives; the local peer did not meet its pre-set threshold.”，说明该 artifact 未用最终代码重生成、DB 仍将其作为最新 revision。 |
| 2 | 动态候选选择 / planner / registry / 幂等 | **PASS** | `goe/research_orchestrator.py:96-115` 按候选队列打分、peer pool 先剔除事件资产，无固定 case/ticker 常量；`tests/test_research_orchestrator.py:33` 通过；Evidence Planner `goe/research_planner.py:26-52`、Test Registry `goe/test_registry.py:52-63` 存在且被测试覆盖。定向运行 `test_generic_execution_is_idempotent_and_keeps_artifact` + `test_next_case_selects_real_candidate_queue_not_fixed_cases`：**2 passed in 0.43s**；同输入 finding_id 不变、artifact bytes 不变、DB 仅 1 行。 |
| 3 | 不可变记忆/DB 路径 | **PASS** | DB 19 条 finding 的 `artifact_path` 19/19 存在（上一轮缺失的 US_EQ_QQQ `a379204b` 已由 c3fef00 从 DB payload 物化）；最新 KOSPI 的 DB `payload_json` 与磁盘 `finding.json` 相等；input_hash 含 observed/rules/event/as_of/data_hash/method/engine（`goe/research_engine.py:307-310`）；全树 23 份 finding 的 event/data_date 均 ≤ decision_as_of（0 违例）。 |
| 4 | CI / 测试 | **PASS** | verify-release **#40**（run `43729873215`，head `df53993`）public HTML 显示 completed/**success**、2m16s；本地 proof `audit/test_evidence/20261115T152445Z_4198a236b4.proof.json` 记录 245 passed / 0 failed / 0 skipped，required=executed SHA256 `76dcb16...`；HEAD e354670 之后仅删旧临时 artifact。 |
| 5 | P0/P1 | 无 P0；P1 见下 | — |

## P1

### P1-1（阻断）TAIEX 动态 case 的 canonical 产物未重生成，learned 不真实且 peer 标签错位

- 现象：`research_results/2026-11-13/TW_EQ_TAIEX/RF-RC-20261113-TW_EQ_TAIEX-d1be6bcd3313-720bca53/finding.json`（DB 最新 TAIEX revision，`created_at=2026-11-15T15:03:33Z`，`code_commit=2dbd52f`）
  - `tests.local_asia_test.pass=false`，但 `learned[-1]="Local and regional explanations both survive; broad indices cannot separate."`。
  - `tests.asia_regional_test` 仍用 `taiex_return`/`kospi_return` 旧键；`hypothesis_updates["H-EQ-REGIONAL"].value={"TAIEX": -0.059647, "KOSPI": -0.060201}`，其中 TAIEX 值实为 JP_EQ_N225 收益，TAIEX 自身为 -4.5053%。
- 影响：V3 的第二个 unseen 动态 case 的持久化结论与其自身检验矛盾，且证据字段把日本收益标为 TAIEX；按 DB 路径取证会得到错误语义。虽然事件资产已从 peer 中排除，KOSPI 的自指 P1 已修复，但 TAIEX 属同一类“peer 角色/标签未按最终代码收敛”的残留，且直接落在发布证据里。
- 修复方向：用最终代码（a6d1d43）重新执行 TAIEX case，生成带 `regional_a/b` 和真实 learned 的新 revision 并落库；修正 `goe/research_engine.py:214,218` 中硬编码的 `TAIEX/KOSPI/TOPIX` 标签；旧 artifact 保留不改。

## P2

- KOSPI 最新 `...-3071aa83` 的 `H-EQ-REGIONAL.value` 仍以 `{"TAIEX": -0.01225, "KOSPI": -0.048983}` 命名实际为 CN_EQ_CSI300/JP_EQ_N225 的收益；`local` 的 `new_evidence` 仍写 “TOPIX same-day”（local 实为 HK_EQ_HSI），test key 仍为 `topix_return`。learned 与 test pass 值本身真实，属展示/字段命名缺陷（与 P1-1 同源，`goe/research_engine.py:214-218`）。
- HEAD e354670 已清理 `TW_EQ_TAIEX/.tmp-...` 临时残留（上一轮 P2 关闭）。

## 最终状态

**FAIL（不通过）**：P0 无；P1 一项（TAIEX canonical finding 未按最终代码重生成、learned 与 local test 矛盾、regional 标签错位）。KOSPI 动态 case（peer 排除、非自指、regional_a/b 区分、learned 真实）、动态选案/planner/registry、finding 幂等、19/19 DB artifact 路径、CI run #40（df53993 success，245 tests）均通过。修复 P1-1 并重生成 TAIEX revision 后可复审签署。
