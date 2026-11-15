# FINAL RESEARCH P1 QA — frozen HEAD 0d5d6ac (code 983854f)

- Date: 2026-11-15 (Asia/Hong_Kong)
- Branch: `architecture/research-v2`
- Frozen: `HEAD=0d5d6ac` (release proof only), product code `983854f`.
- Scope: read-only independent audit; only this file written. No code/DB/artifact changes.
- **Verdict: PASS (P2 only). No new P0/P1 research defects.**
- **DISCOVERY VALUE: NOT VALIDATED.**

## 1. 四字段与当前 20 条候选

Artifact: `evaluation/v2_candidates_20_2026-11-13.json`（as_of 2026-11-13）；
`goe.contracts.validate_research_candidate` **20/20 pass**.

| 字段 | 实际分布 |
|---|---|
| `research_queue` | **research 0 / watch 4 / archive 16** |
| `research_worthiness` | high 1 / medium 3 / low 16 |
| `evidence_readiness` | ready 0 / partial 4 / missing 16 |
| `handoff_eligibility` | **eligible 0 / a_retained 20** |
| `priority_tier` | intelligence 20 |

- N225（`RC-20261113-JP_EQ_N225-455ff8e1a32f`）：**high / partial / watch / a_retained / intelligence**，`decision_impact` 有 if_true/if_false，quality audit 标记 `decision_value_flag=True`。
- Watch 4 条：N225（high/partial）、TAIEX（medium/missing）、QQQ（medium/missing）、XLV（medium/missing）。
- **worthiness 与 readiness 独立**：存在 high+partial→watch、medium+missing→watch、partial+low→archive；worthiness 计算（`goe/research_triage.py:240-247`）不读取 `discriminating_count`。
- DB 对账：`data/goe.db` 中 20 条 `research_v2_candidates` 与 artifact 的 `research_worthiness / evidence_readiness / handoff_eligibility / research_queue / research_readiness / priority_tier` **逐字段 0 diff**；DB status 全部 `intelligence`（含 4 条 watch，均保留，未删除）。
- 契约校验：`goe/contracts.py:130-148` 强制取值域；`eligible` 必须同时满足非 intelligence 且 `evidence_readiness == "ready"`。

**P2（语义冗余，不阻断）**：`handoff_eligibility` 由 `priority_tier` 唯一决定（`research_triage.py:290`），而 `research_queue == "research"` 也由 `tier A/B/C` 唯一决定（`:291-292`），因此**当前实现中 `eligible` ⟺ `research_queue=="research"`**，两者无法独立取值。四条 watch 全部 `a_retained` 是正确语义，但“独立维度”只对 worthiness/readiness 成立，对 eligibility/queue 不成立。

## 2. A→B guard

- `eligible_for_handoff`（`goe/integration/research_handoff.py:93-106`）要求**显式** `handoff_eligibility == "eligible"` **且** `tier in (A,B,C)` **且** `research_readiness == "evidence_ok"`；仅 tier/readiness 不再足够。
- CLI `triage --handoff`（`goe/cli.py:319-331`）在 `eligible == []` 时直接打印说明并 `return 3`，**不创建 task**。
- DB：`research_v2_tasks = 0`、`research_v2_results = 0`；即**0 eligible 下 0 task**，无绕过 guard 的 handoff。20 条候选（含 intelligence/watch）全部保留。
- 测试：`tests/test_research_v2.py:183-196` 覆盖 intelligence 被排除、B+`evidence_gap` 被排除；227/227 通过（`audit/test_evidence/20261115T064031Z_983854f9a3.proof.json`，commit 983854f，git_dirty=false）。

**P2**：`persist_v2_result` 自身不校验 eligibility（依赖 CLI 调用前过滤）；当前无其他调用点，不构成 P1。

## 3. Research quality audit

- 以 artifact 重新执行 `goe.research_quality.evaluate_candidates`，结果与 `evaluation/research_quality_audit.json` **完全相等**（逐字段，含 rows）。
- 数字：n=20，research 0，watch 4，handoff eligible 0，measured>=2 为 0，decision-value 4，mean measured coverage 0.075，mean question structure 0.988，duplicate claims 0。
- `evaluation/RESEARCH_QUALITY_AUDIT.md` 与 JSON 一致；代码 `discovery_value="NOT VALIDATED"` 为硬编码默认，`note` 明示“descriptive only; no human/expert labels, no independent future window”。
- 未发现把 coverage/question-structure 等描述性指标写成 validation、alpha 或 mispricing 的表述；**DISCOVERY VALUE: NOT VALIDATED** 在代码、JSON、MD 三处一致。

## 4. Curve evidence

- `goe/evidence/external.py:66-133`：要求 `curve_id,currency,region,curve_type,tenor,date,value,available_at,source`；过滤单一 `currency+region+curve_type`，拒绝多 `curve_id`、缺 2Y/10Y、2Y/10Y 观测日或可用日不一致、过期/未来。
- `config/evidence_sources.yaml`：`enabled: false`；`curve_type: policy_path_proxy`；注释明写“FRED SOFR/2Y/10Y is a policy-path proxy, NOT a term OIS curve”。
- `data/policy_curve.csv` 的 `source` 列含“policy-path proxy (not term OIS)”；只有 `curve_type=="ois"` 才输出 `OIS 曲线 2s10s`，当前输出标签为 `政策路径代理 2s10s（非 OIS）`。
- `tests/test_external_evidence.py:30-44` 覆盖同曲线、**跨币种拒绝**、缺 tenor、日期不一致、过期、错类型；未发现跨币种/跨类型拼接，也未发现伪造 OIS 声明。

## 5. P0 / P1

- **P0：无。**
- **P1：无新增。** 983854f 相对 b888303 只新增四字段、显式 eligibility guard、quality audit 字段化及对应 artifacts；tier 规则、假设/证据接线、curve 解析未变（stable ID 与 curve 身份校验在更早的 cd6e801，已由既有 QA 覆盖）。227/227 tests 全绿，契约校验 20/20。
- P2 残留（文档/证据一致性问题，不影响本轮结论）：
  1. `contracts/RESEARCH_CONTRACT.md` 仍未写入四个新字段及其取值域/关系，只有 `goe/contracts.py` 机器校验；契约文档落后于实现。
  2. `handoff_eligibility` 与 `research_queue=="research"` 完全共线（见 §1），无法表达“进入研究队列但暂不得移交”的中间态。
  3. 本地 `exports/research_candidates_2026-11-13.json`（11:06）早于本次代码/DB（14:35），四字段为 `null`；正式 QA 用的是 `evaluation/` artifact 且与 DB 一致。只读审计未重生成该过期导出。
  4. 当前 DB `research_v2_events/tasks/results` 均为 0；Phase-2 早期 refused-task 证据不在本快照中（旧审计 `audit/FINAL_RESEARCH_QA.md` 有记录），本轮“无 fake success”以 0 task 与守卫代码/测试判定。

## 6. Final

**中文结论：RESEARCH P1 独立复核通过（P2 only，无新增 P0/P1）。**
当前 20 条候选为 **0 research / 4 watch / 16 archive、0 handoff eligible**；N225 为 **high worthiness / partial readiness / watch / retained**；A→B 仅接受显式 `eligible` 且当前无 task；quality audit 可由 artifact 精确复现且未把描述指标包装成验证；curve evidence 单曲线/单币种/单类型，proxy 未冒充 OIS。

**DISCOVERY VALUE: NOT VALIDATED**（无人类/专家标签、无独立未来窗口，D 1.000 < C 1.500 的既有结论未改变）。
