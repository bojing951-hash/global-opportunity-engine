# Phase-2 独立工程 QA（冻结 HEAD `3c640dd` / 代码 `671f5fa`）

- 时间：2026-11-15 13:14 +08:00
- 范围：只读审计；除本文件外未改动工作区
- 结论：**Phase-1 工程验收保持有效；Phase-2 工程可接受但需先处理 1 个 P1（工作树未提交文档）；研究结论仍为 NOT VALIDATED**

## 1. Phase-1 扫描闸门：PASS

- `verify_scan_evidence(store, require_artifacts=True)` 接受真实扫描
  `scan-20261115T044634Z-b68802` / as_of `2026-11-13`：358,310 prices、159,508 indicators、
  1,506 anomalies、5 transmissions、11 opportunities，`readiness_ok=True`。
- `reports/report_2026-11-13.md`、`reports/scan_2026-11-13.json`、`exports/pipeline_2026-11-13.json`
  的 SHA-256 与 `release_671f5faa5f.json` 逐项一致。
- Phase-2 未改动扫描模块：`git diff 9d51769..HEAD -- goe/scan_evidence.py tests/test_scan_evidence.py`
  为空；无 Phase-1 回归。
- 本地重跑离线套件：**222 passed, 10 deselected, exit 0**（123.7s），与 proof 一致。

## 2. A→B 资格闸门：PASS（有 1 个 P2 测试缺口）

- `goe/integration/research_handoff.py::eligible_for_handoff` 只放行
  `tier ∈ {A,B,C}` 且 `research_readiness == "evidence_ok"`。
- 当前 DB `research_v2_candidates`：20 条全部 `intelligence/evidence_gap`，重算 eligible = **0**。
- `goe triage --handoff` 在 eligible 为空时打印说明并 **return 3**，位置在 `IAAdapter` 创建与
  `persist_v2_result` 之前；不会创建 handoff task。DB `research_v2_tasks` 当前计数为 **0**。
- 所有 triage 候选先以 `intelligence` 状态 upsert，A 侧智能保留，未被删除。
- P2：`tests/test_research_v2.py::test_handoff_eligibility_excludes_intelligence` 只测过滤器；
  无 CLI 级集成测试断言“空 eligible → exit 3 且不写 task”。代码路径经人工核查安全。

## 3. 研究质量模块 / 产物：PASS（数值准确、无自动验证；2 个 P2）

- `goe/research_quality.py` 为纯函数，仅依赖传入 candidate，不读 DB、不写状态、不 import 到
  pipeline；`discovery_value` 恒为 `NOT VALIDATED`，无自动升级/验证逻辑。测试
  `tests/test_research_quality.py` 两项均通过。
- 用 DB 的 20 条 `payload_json` 重算 `evaluate_candidates`，与
  `evaluation/research_quality_audit.json` 完全一致：8 个汇总字段全部相等，
  20 条 candidate 行零差异（n=20、research=0、≥2 measured=0、decision flags=4、
  mean coverage=0.075、mean question structure=0.988、duplicate=0）。
- 无数据变更导致的运行时耦合：产物是静态审计快照，模块不做运行时读取；当前 DB 与产物一致。
- P2：仓库无 `goe research-quality` CLI/生成脚本，产物 JSON 也未记录 schema/as_of/git_commit，
  生成过程不可由已提交命令直接复现（本次用模块+DB 十行重算）。
- P2：`evaluation/RESEARCH_QUALITY_AUDIT.md` 的表格与 JSON 一致，但产物更新需人工重生成，
  无 stale 检测。

## 4. V1/main/B、工作树、proof/HEAD 溯源

- **V1/main/B：PASS（就本仓库可核验范围）**。Phase-2 改动路径不含 V1 代码；
  `main` = `e5da620`，与 `origin/main` 相同且是 HEAD 祖先；tags
  `v1-frozen-1f2b341`、`v2-frozen-a20ce29`、`v2-phase1-9d51769` 引用未变；
  `~/investment-agent-dev` HEAD `b17b65e`、工作树干净，本仓库 Phase-2 代码不写 B。
- **proof/HEAD 溯源：PASS**。`release_671f5faa5f.json` 的 `git_commit` = `671f5fa`，即 HEAD
  `3c640dd` 的父提交；HEAD 仅追加 proof 证据文件。在 `/tmp` 的 `3c640dd` 干净克隆上执行
  `verify-release --proof ... --no-rerun` **exit 0**，显示 222 passed，required/executed SHA-256
  相同。
- **工作树：FAIL（P1）**。当前工作区有 3 个未提交文档修改：
  `PROJECT_STATE.md`、`audit/FINAL_ACCEPTANCE_CURRENT.md`、`audit/TEST_EVIDENCE.md`（仅文档，
  无代码/测试）。因此在本工作区执行 `verify-release` 被拒绝：
  `RELEASE PROOF REJECTED: cannot verify a proof on a dirty worktree`。干净克隆可验证，
  说明冻结提交本身有效，但“当前树可复现验证”不成立。

## 5. 新增 P0/P1

| 级别 | ID | 问题 | 证据 | 处理 |
|---|---|---|---|---|
| P1 | P2QA-1 | 冻结 HEAD 工作树不干净，`verify-release` 被拒绝 | 3 个文档 `M`；in-place verify exit 1；干净克隆 exit 0 | 提交/还原这 3 个文档后重跑 `verify-release`；不涉及代码改动 |
| P2 | P2QA-2 | 未提交的 `audit/TEST_EVIDENCE.md` 把 222 tests 写成 commit `9d51769`（实际 222 属 `671f5fa`；`9d51769` 为 219） | `git diff -- audit/TEST_EVIDENCE.md` | 提交前改为 `671f5fa` |
| P2 | P2QA-3 | 研究质量产物无 CLI/生成命令与 provenance 字段 | 无 `research-quality` 子命令；JSON 无 schema/as_of/commit | 可选：补生成命令或文档记录命令 |
| P2 | P2QA-4 | handoff 空 eligible 无 CLI 集成测试 | 仅过滤器单测 | 可选：加 exit=3/无 task 断言 |

**P0：无。**

## 总体状态

- **工程（Phase 1）：ACCEPTED**。真实扫描闸门、222/222 proof、发布清单三者一致；Phase-2 未回归。
- **工程（Phase 2）：ACCEPTED WITH P1**。冻结代码与证据可验证；唯一 P1 是当前工作树未提交的
  文档状态，需先提交并重跑发布校验。
- **研究：PARTIAL / NOT VALIDATED**。20 candidates → 0 research、20 intelligence；
  A→B 无候选、无 task、智能保留；研究质量数值真实且已独立复算；无自动验证，发现价值仍未验证。
