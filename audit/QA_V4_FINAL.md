# V4 最终独立 QA（HEAD 09f2d72 / code 4d59063 / proof 09f2d72）

- 审计对象：`global-opportunity-engine`，HEAD `09f2d72`（release proof 锁 `4d59063`），分支 `architecture/research-v2`
- 方法：只读静态审阅 + 只读 DB/artifact 核对 + 本地全量离线 pytest；仅写本文件，未改代码/配置/测试/DB
- 环境：QA 开始时 `git status --porcelain` 为空；`data/goe.db` 为共享工作副本

## 总判定

**不通过（FAIL，1 项 P1）；无 P0。**

V4 的核心路径（事件合同、动态候选、不可变 finding、248 测试）大体成立；但“缺失 SPY/VIX 只能 INSUFFICIENT_DATA，不能 WEAKENED”的语义保证只在 `equity_event` 分支实现，`fx_level` 与 `commodity_event` 仍把缺失当作证伪，属同一类证据语义缺陷，阻断签署。

## 逐项核查

| # | 检查项 | 结论 | 证据 |
|---|---|---|---|
| 1 | 事件合同锁定 TAIEX 2026-11-06 / KOSPI 2026-10-15，无静默漂移 | **PASS（P2 隐患）** | TAIEX 最新 `research_results/2026-11-13/TW_EQ_TAIEX/...-4dece725/plan.json`：`event_start=event_end=2026-11-06`、`detector=price_return_shock`、`direction=down`；KOSPI 最新 `...-cc491d3f/plan.json`：`2026-10-15`、`drawdown_extreme/deep_drawdown`。`resolve_event` 在有 `event_date` hint 时按精确日期查询而非回退最近异常（`goe/research_contract.py:63-68`）；找不到则抛 `EventNotResolved`（不是静默换事件），回归测试 `tests/test_research_contract.py:25`。 |
| 2 | 缺失 SPY/VIX → INSUFFICIENT_DATA（非 WEAKENED） | **P1（阻断）** | `equity_event` 分支用 `hs(pass, ..., "WEAKENED_BY_EVIDENCE")`，`pass is None` 返回 `INSUFFICIENT_DATA`（`goe/research_engine.py:135-142,202-206`），有专项测试 `tests/test_research_contract.py:33`。但 `fx_level` 的 `H-FX-RISK`（`research_engine.py:256`）与 `commodity_event` 的 `H-CMD-RISK`（`:296`）仍写 `... if tests["risk_test"]["pass"] else "WEAKENED_BY_EVIDENCE"`；当 SPY 或 VIX 缺失时 `pass=None`，被落成 `WEAKENED_BY_EVIDENCE`，把“无数据”误作“反证”。该路径无回归测试。 |
| 3 | 动态候选队列 / Evidence Planner | **PASS** | `next_case` 只从 `research_v2_candidates` 的 watch/research 队列按 worthiness+readiness 打分选择，无硬编码 case（`goe/research_orchestrator.py:68-105`）；peer 池先剔除事件资产（`:104-110`）；Evidence Planner 生成 `EvidenceTask`（`goe/research_planner.py:26-52`）；测试 `tests/test_research_orchestrator.py:34` 通过。 |
| 4 | finding 不可变 / 幂等 | **PASS** | 同一输入 finding_id 稳定，已存在 artifact 只复用不重写；新增 revision 走新路径（`goe/research_engine.py:326-343`）；幂等测试校验二次执行的 `finding.json` bytes 不变且 DB 仅 1 行（`tests/test_research_exec.py:78`），通过。DB 24 条 finding 的 `artifact_path` 24/24 存在；多 revision 并存属设计允许的历史保留。 |
| 5 | 248 测试 / CI run43 | **PASS（本地）** | 本地独立运行 `.venv/bin/python -m pytest -q`：exit 0（248 项，约 2 分钟）；仓库 proof `audit/test_evidence/20261115T161430Z_4d59063250.proof.json`：248 passed / 0 failed / 0 skipped，required=executed SHA256 一致。CI run43 为外部证据，仓库 CI 表未更新到 43，本次未能独立复取（GitHub API 限流），按请求方记录采信。 |
| 6 | 无 P0/P1 | **未通过** | 见 P1-1。 |

## P0

无。

## P1

### P1-1（阻断）FX/商品模板仍把缺失 SPY/VIX 落为 WEAKENED_BY_EVIDENCE

- `goe/research_engine.py:256`（FX `H-FX-RISK`）与 `:296`（商品 `H-CMD-RISK`）使用 `if pass else "WEAKENED_BY_EVIDENCE"`，而 `pass` 在 SPY/VIX 缺失时为 `None`；`None` 是假值，因此落成“被证据削弱”，与 V4 的“缺失即 INSUFFICIENT_DATA”契约相矛盾。
- 影响：同样的数据缺口在权益事件里是 `INSUFFICIENT_DATA`，在 FX/商品事件里却变成反向结论，属于跨模板语义漂移；发布声明“missing SPY/VIX -> INSUFFICIENT_DATA not WEAKENED”不能对全部研究模板成立。当前真实 artifact 恰好 SPY/VIX 齐全，未触发，故不影响已有 finding 数值，但未满足验收语义。
- 修复方向：三种模板统一用 `None -> INSUFFICIENT_DATA` 的三态映射（可复用 `hs` 或等价 helper），并为 FX/商品缺失 SPY/VIX 各加回归测试；修复后重跑 248 测试并更新 proof/CI。

## P2

- TAIEX 候选 `data/goe.db` 的 payload 缺少 `event_date`/`detector_id`/`direction`（KOSPI 候选有），`resolve_event` 依赖 `observed_phenomenon` 文本推断 + 最近匹配异常。当前文本含 `price_return_shock（down）` 且 11-06 是最新 down 异常，故复算稳定；未来若出现更晚的 down 异常，同一 `research_id` 可能重新绑定到新事件。建议 triage/orchestrator 落库时持久化 event 字段，或在 `resolve_event` 命中后写回候选，以真正锁定。
- CI run43 未写入仓库 CI 表，审计无法从仓库内证据复核；建议补登 `audit/CI_SUCCESS` 或 release proof。
- `goe/research_exec.py:204/210` 的 legacy `execute_nikkei_case` 仍有 `global_pass=False` 时 `WEAKENED_BY_EVIDENCE` 的旧逻辑；V4 orchestrator 走 `execute_spec`，故当前不改结论，但属同类隐患，建议标记 deprecated/删除。

## 最终状态

**FAIL（不通过）**：P0 无；P1 一项（FX/商品模板缺失 SPY/VIX 仍判 WEAKENED）。事件合同锁定（TAIEX 11-06 / KOSPI 10-15）、动态候选与 Evidence Planner、finding 不可变/幂等、248 本地测试均通过；修复 P1-1 并补 FX/商品缺失数据回归测试后可复审判 PASS。
