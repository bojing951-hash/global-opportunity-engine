# V3 最终独立 QA（HEAD 20ab4e7 / code 5308058）

- 审计对象：`global-opportunity-engine`，HEAD `20ab4e7e2c483a5b900527eebce9c339ec65c0ab`，代码 `5308058`，分支 `architecture/research-v2`
- 方法：只读静态审阅 + 本地只读 SQL/artifact 核对 + 离线 pytest；仅写本文件，未改代码/配置/测试/DB
- 环境：QA 开始时 `git status --porcelain` 为空；`data/goe.db` 为共享工作副本

## 总判定

**不通过（FAIL，存在 1 项语义 P1 + 1 项产物一致性 P1）；无 P0。**

工程与发布面通过：245 测试全绿、CI run 39 在 `20ab4e7` success、finding 幂等/不可变路径按代码成立、16 条 DB finding/全树 artifact 无未来日期且全部 INCONCLUSIVE。阻断点在 V3 的“动态 unseen case”证据语义：**KOSPI 的 regional 检验把事件资产本身当作 peer，结论循环**；另有 1 条旧 DB finding 的 artifact 路径失效，不能宣称“DB artifact 路径全部匹配”。

## 逐项核查

| # | 检查项 | 结论 | 证据 |
|---|---|---|---|
| 1 | 动态 orchestrator 选真实候选队列；Evidence Planner/Test Registry；TAIEX/KOSPI；事件日；`next_case` 无硬编码 case | **PASS（有 P1 语义缺陷，见下）** | `next_case` 从 `research_v2_candidates` 查询并按 score 排序（`goe/research_orchestrator.py:62-94`），无 ticker/case 常量；回归测试 `tests/test_research_orchestrator.py:33`。TAIEX/KOSPI 均在 DB 候选队列（TW `RC-...-d1be6bcd3313`、KR `RC-...-5710b185e99c`，watch/medium/partial），事件日分别为 2026-11-06、2026-10-15，均来自 anomaly `down`。Evidence Planner 生成 `EvidenceTask`（`goe/research_planner.py:26-52`）；Test Registry 按 asset_class 选模板（`goe/test_registry.py:52-63`）。 |
| 2 | 不可变记忆：ID 含输入 + method/engine hash；同输入不改 artifact；新代码/规则新 revision；DB 路径匹配；rescan 保留状态；不覆盖 | **PARTIAL（P1）** | finding_id = `RF-<research_id>-<input_hash[:8]>`，input_hash 含 observed/rules/event/as_of/data_hash/method/engine（`goe/research_engine.py:297-301`）；engine hash 为 `research_engine.py` 内容哈希（`:25-29`）。同 finding 已存在时只读取并复用，不重写（`:315-324`）；幂等测试校验 bytes 不变（`tests/test_research_exec.py:78-129`）。DB 中 N225/FX/SLV 各有 2–3 个不同 revision，rescan 不重置假设/状态（`tests/test_research_identity.py`）。**但 16 条 DB finding 中 1 条路径不存在**：`RF-RC-20261113-US_EQ_QQQ-ed67c9acfee9-a379204b` → `research_results/2026-11-13/US_EQ_QQQ/.../finding.json`（MISSING；该记录 code_commit `92df1b7`，旧版本；payload 仍在 DB）。其余 15/16 匹配。 |
| 3 | 三/四个 case 真实；无未来数据；INCONCLUSIVE；无 alpha/因果过强；缺失数据语义 | **PASS（KOSPI 证据循环见 P1）** | 16 条 DB finding 全部 `status=INCONCLUSIVE`；脚本核对全树 19 份 `finding.json`（含 4 份未被 DB 链接的历史/临时产物）的 `event_date`、`data_dates` 均 ≤ `decision_as_of`，0 违例。5 个真实 case（N225、DXY、SLV、TAIEX、KOSPI），报告明确 “not alpha/mispricing / not causal identification / DISCOVERY VALUE: NOT VALIDATED”（`research_results/MULTI_CASE.md:4,25`）。缺失项统一 `INSUFFICIENT_DATA`（consensus、supply、policy calendar），不编造。 |
| 4 | CI 最新 run 在 `20ab4e7` success（公开 HTML） | **PASS** | GitHub check-run `132856059108`，head_sha=`20ab4e7e2c...`，status=completed，conclusion=**success**，run 39：https://github.com/bojing951-hash/global-opportunity-engine/actions/runs/43728669638 ；公开页面可访问。本地独立复跑：`245 passed, 10 deselected`（99.15s）；release proof `audit/releases/release_5308058597.json` 同样记录 245 passed / 0 skipped，proof SHA256 一致。 |
| 5 | P0/P1 | 见下 | 无 P0。 |

## P1

### P1-1（阻断）KOSPI 动态 case 的 regional 检验自指，结论循环

- `goe/research_orchestrator.py:107-108` 对 equity 模板固定 `regional_kr = KR_EQ_KOSPI`；KOSPI 事件资产本身也是 `KR_EQ_KOSPI`。
- `goe/research_engine.py` 执行时把 `{spec.asset: ...}` 与 `spec.peers` 合并，事件资产被同时用作 `regional_kr` peer；regional 判定为 `N225 < -3% AND KOSPI < -3%`。KOSPI 事件日 2026-10-15 自身 -7.57%，于是“North Asia co-move supported”由事件资产自身保证。
- 产物 `research_results/2026-11-13/KR_EQ_KOSPI/RF-...-0dd72cfb/finding.json`：regional 报 `taiex_return=-0.048983`（实为 N225）、`kospi_return=-0.075654`（事件自身），`pass=true`；`learned` 写 “Japan -4.90%, Korea -7.57%; regional co-move supported”。若按真实 TAIEX peer，该 support 不成立。
- 同时 `topix_return`/`taiex_return` 键名与所载资产（HSI/N225）不符；KOSPI 的 “local” 实际用 HSI，不能代表 Korea-local。属模板未按事件资产裁剪，直接影响 V3 “unseen case 可泛化”的核心声明。
- 修复方向：peer 角色必须排除事件资产并为 KOSPI 选 N225+TAIEX（TAIEX 选 N225+KOSPI），同时修正键名/本地 peer；重新生成 finding 并以新 revision 落库（不改旧 artifact）。

### P1-2 `data/goe.db` 存在失效 artifact_path

- 唯一不匹配：`RF-RC-20261113-US_EQ_QQQ-ed67c9acfee9-a379204b` → 路径不存在（`research_results/2026-11-13/US_EQ_QQQ/.../finding.json`）；该 finding 的 payload 仍在 DB，code_commit 为旧 `92df1b7`，当前 `next_case` 又按设计跳过 US equity。
- 影响：不能宣称“DB artifact 路径全部匹配/记忆完整”；审计者按 DB 路径取证会失败。建议用 `scripts/repair_research_artifacts.py` 重新物化或删除旧记录并记录原因；重跑后校验 16/16。
- 若将 `data/` 视为非发布物、旧记录视为历史残留，可降为 P2；但本 QA 的检查项明确要求路径匹配，故按 P1 报告。

## P2

- `research_results/2026-11-13/TW_EQ_TAIEX/.tmp-RF-RC-20261113-TW_EQ_TAIEX-d1be6bcd3313-1871bb73/finding.json` 被提交（5308058），是原子写失败残留的临时目录、DB 无链接；建议清理并加入 ignore 规则，避免被误认为有效 revision。
- KOSPI/Taiwan 的 local/regional 键名遗留 N225/TOPIX 语义（与 P1-1 同源），报告层可读性差。

## 最终状态

**FAIL（不通过）**：P0 无；P1 两项（P1-1 为阻断项）。修复 P1-1 并重新生成 KOSPI finding、处理 P1-2 的 DB/artifact 一致性后，可复审签署。工程、CI、245 测试、幂等写入、时间点与 INCONCLUSIVE 语义均通过（注：`data/goe.db` 为共享工作副本，QA 期间未写入）。
