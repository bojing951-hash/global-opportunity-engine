# 独立终审 QA：Research Value / Discovery / A→B（2026-11-16）

- 仓库：`global-opportunity-engine`；分支 `architecture/research-v2`
- HEAD `48d7f19`（代码 `bc6d21c`；HEAD 仅加 proof/release 文件）
- proof：`audit/test_evidence/20261116T034317Z_bc6d21cabf.proof.json`，254 tests
- 执行方式：只读；仅写本文件。未重跑全套 pytest，以 proof/log 与只读复算为准。

## 总判定

**FUNCTIONAL（功能成立，非 FULL）**：五项交付均有真实工件且口径诚实；但研究价值仍未验证（无独立标签/未来样本），不能签 FULL。**P0：无；P1：无**；P2 4 项，P3 1 项。

## 逐项核验

| # | 项目 | 结论 | 证据 |
|---|---|---|---|
| 1 | Discovery 资格 | PASS（P3 注） | `evaluation/discovery_qualification.json`：20 行，counts 恰为 `RESEARCH_READY 0 / EVIDENCE_TO_COLLECT 4 / INTELLIGENCE_ONLY 16 / DATA_ARTIFACT 0`。用 `goe.discovery.qualify()` 对 `evaluation/v2_candidates_20_2026-11-13.json` 复算，20 行与工件逐字段一致。补充 CT：`evaluation/discovery_cases.json` 21 行、`DATA_ARTIFACT 1`，notes 明示“CT 是真实 2026-04-30 连续期货案例，不属于 20 候选工件”；DB 中 `CM_AGR_CT`（Cotton front month）2026-04-30 收 79.86、前日 76.86（月末跳变），分类为构造/换月伪影、无经济主张。四类可分由 `tests/test_discovery.py::test_four_discovery_classes_are_distinguishable` 覆盖，254 proof 绿。**P3**：真实 20 候选中四类只实例化 3 类，`RESEARCH_READY` 仅单测构造、真实样本为 0（这是正确结果，不是缺陷）。 |
| 2 | Investment intelligence | PASS（P2 注） | `evaluation/investment_intelligence.json`：`MARKET_EXPECTATIONS_NOT_ESTABLISHED`、`MISPRICING_NOT_ESTABLISHED`（direction/magnitude 均 null）；`decision_relevance` 明写 “research priority only; no trade, target price, or mispricing claim”；`discovery_value: NOT VALIDATED`。用 V2 finding 复算 `goe.investment_intel.analyze()`，输出与工件完全相等。**P2**：两个“未建立”状态是模块常量，没有可接入的 implied/consensus 基线路径；结论诚实，但“evidence-gated”目前只是拒绝而非可正向判定的闸门。 |
| 3 | A→B 真实性 | PASS（P2 注） | `evaluation/a_to_b_validation.json`：`semantic_status=ok_valid`、`run_ok=true`、`n_evidence_rows=63`、`s8_status=answered`、`capability_status=SUPPORTED`。按 `report_path` 目录用 `parse_research_artifact()` 只读复算，仍得 `ok_valid`、63 行；S8 `values={"MB-1":4.56,"MB-2":4.88,"MB-3":0.25,"MB-4":2.748}` 与工件一致，L1 行 0、L2 17；适配器改动仅放宽为“有 S8 接地值也可 ok_valid”，且 `test_grounded_s8_values_without_l1_rows_can_be_ok_valid` 覆盖，L2-only 仍判 insufficient_data。B 侧 `/Users/cast/investment-agent-dev` 工作树干净，HEAD `a589095`（10:50:42）早于本次 11:39 运行；提交 `0e005b7` 未改 B 任何文件。无伪造 B 成功。**P2**：B 报告只在 `/tmp/goe_ia_adapter2/...`，未归档进仓库，且未钉 B commit/版本，干净克隆不可复算该 A→B；问题目标日 2026-11-12，实际观测 11-09/11-10，工件已如实披露但回答不是严格同日点。 |
| 4 | 连续性 / Case C | PASS（P2 注） | KOSPI 同事件 `drawdown_extreme|KR_EQ_KOSPI|deep_drawdown|2026-10-15`：V1 `...-cc491d3f`（peers 用 `CN_FX_USDCNY`）与 V2 `...-d756fb85`（peers 用 `GX_FX_USDKRW`）各自独立目录、5 件套齐全、input_sha256 不同、均为 `INCONCLUSIVE`，V1 未被覆盖。DB 价格/指标最大日期均 `2026-11-13`（=唯一 cutoff），`research_results/CASE_C_MULTI_ROUND.md` 明写 V2 是 `EXISTING_DATA_NEWLY_ANALYZED`、真正 post-cutoff 新观测 `OBJECTIVELY_BLOCKED`，未把既有数据新分析冒充新数据。**P2**：“objectively blocked” 只对当前冻结快照成立；若未来接入新 vintage 即可解除，措辞应限定快照范围。 |
| 5 | Proof / CI | PASS（P2 注） | proof `bc6d21c`：`passed=254, failed=0, errors=0, skipped=0, exit_code=0, git_dirty=false`，required/executed 均为 254 且 sha256 相同。GitHub Actions **run 49**（`https://github.com/bojing951-hash/global-opportunity-engine/actions/runs/43800027390`）：SUCCESS，提交 `48d7f19`，分支 `architecture/research-v2`，标题 “254 tests”，1m18s，2026-11-16T03:45:19Z（外部页面核验）。**P2**：仓库内 `audit/CI_SUCCESS_2026-11-15.md` 只记到 run 34/31，run 49 仅外部证据，未落盘。 |

## 问题清单

- **P0：无。**
- **P1：无。**
- **P2-1（文档计数混淆）**：`PROJECT_STATE.md:185` 写 “0 ready / 4 collect / 16 intelligence / 1 data-artifact”，把 20 候选的 0 CT 与补充 CT 的 1 CT 相加成 21；与资格工件 `discovery_qualification.json` 的 0 CT 口径不一致。主工件正确，属文档一致性。
- **P2-2（intel 闸门是常量）**：状态永远为 NOT_ESTABLISHED，无基线接入路径；诚实但能力有限，不能据此宣称已具备期望/错价判定力。
- **P2-3（A→B 证据不可移植）**：`/tmp` 报告 + 未钉 B 版本，干净克隆/CI 无法复算 A→B；决策日与观测日差异已披露，但“11-12 利差”实际是跨日拼接值 -2.132。
- **P2-4（CI 记录滞后）**：CI run49 成功只在 GitHub，仓库台账未更新；不影响结论。
- **P3（READY 未实例化）**：四类可分靠单测，真实 20 候选中 READY=0（符合严格证据门，非缺陷）。

## 最终状态

**FUNCTIONAL**：五项均可复现/可核对，无 P0/P1，无虚假成功、无交易/alpha 主张；但无独立标签、无真正未来样本，`DISCOVERY VALUE: NOT VALIDATED`，不足以签 **FULL**。
