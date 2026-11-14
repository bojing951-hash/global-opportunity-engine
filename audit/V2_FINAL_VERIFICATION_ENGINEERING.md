# V2 最终工程/契约验收（独立，只读）

- 对象：`global-opportunity-engine`，分支 `architecture/research-v2`，冻结提交 `a31f545dbc1a5e1f4f136604a5b0a09a71e02777`（`a31f545`）
- Manifest：`audit/releases/release_a31f545dbc.json`（`created_at=2026-11-14T13:08:28Z`，`git_dirty=false`）
- 基线：上一轮 `audit/V2_FINAL_QA_ENGINEERING.md`（`44b9572`，3 项 P1）
- 方式：`git show/diff` 静态阅读、冻结 DB 只读查询、临时 DB 副本上的持久化/readiness 复现、离线测试；未改代码/配置/数据，除本文件外无写入
- 结论：**PASS WITH ISSUES**。上轮 3 项 P1 中 2 项完全闭环、1 项部分闭环；另发现 1 项新的冻结后工作树漂移。无 P0。

## 一、检查总表

| # | 检查项 | 观察 | 结论 |
|---|---|---|---|
| 1 | 真实 triage 候选通过 `validate_research_candidate`；hypothesis evidence；>=2 falsifier 带 `hypothesis_id` | 当前导出 `exports/research_candidates_2026-11-13.json` 的 1 个真实候选（`RC-20261113-12` N225）**PASS**：5 个 hypothesis 均含 `evidence_for`/`evidence_against` 键，candidate 级 `evidence_for=2`/`evidence_against=1`，3 条 falsifier 均为 `hypothesis_id=H1`。代码层：`research_triage.py` 对全部 5 个 hypothesis 无条件写入两字段，candidate 级空 `evidence_against` 有兜底，falsifier 强制补足 >=2 且逐条写 `hypothesis_id`；`contracts.py` 校验收紧为字段存在、falsifier>=2、hypothesis_id 必须指向已知 hypothesis。原 5/10 失败的根因（空 `evidence_against`）已消除。注：导出仅 `--limit 1` 的 1 个候选，10 个全量候选未重跑（遵守“不重建/不重扫”约束），以代码保证 + 1 个真实样本验收 | **PASS** |
| 2 | 当前 DB 宏观 anomaly 有 `observation_date`；anomaly date 与 available_date 语义 | 14/14 macro anomaly 均已写 `evidence.observation_date`；`available_date` 语义正确（如 `CN_CPI` 观测 `2026-04-01`、`available_date=2026-05-16`，+45d）。**但 14/14 的 anomaly `as_of`（即 `date`）仍等于 `available_date`，0/14 等于 observation**；`reports/scan_2026-11-13.json` 同样 `date=2026-05-16`、`observation_date=2026-04-01`。`contracts/DETECTION_CONTRACT.md` 明确要求输出 `date (observation)`，故日期列语义仍未对齐 | **PARTIAL（P1 未完全闭环）** |
| 3 | UST 2Y/10Y 关键期限新鲜度 | 冻结 DB baseline `check_data_readiness(as_of=2026-11-13)`：`ok=True`、`critical=[]`；2Y/10Y 最后均为 `2026-11-12`。临时 DB 副本上把 2Y 截到 `2026-09-01`：`ok=False`，critical「核心收益率曲线关键期限过期：UST:2Y 最后 2026-09-01」；删除 2Y（10Y 仍新鲜）：`ok=False`，critical「核心收益率曲线缺少关键期限：UST:2Y」 | **PASS** |
| 4 | V2 A→B：timeout 语义、RC 前缀、L2-only、rejected 不落成功 | 临时 DB 副本实测 `persist_v2_result`：`timeout` → `not_completed:timeout`，`task_id=RC-20261113-12`（无双前缀），event `ia_research_not_completed`；`refused` → `not_completed:refused`；`status=rejected` 与 `status=ok+semantic=rejected` 均 → `not_completed:rejected`，无 completed。`parse_research_artifact`：L2-only（run_ok=true、evidence_index=[1]、L1 rows=0、L2 views=17、S8 answered）→ `insufficient_data`；补充 1 条 L1 事实行后 → `ok_valid`。`goe triage --handoff` 已提供 CLI 入口 | **PASS** |
| 5 | Release gate：clean/test_count/success/artifact hash；V1 tag/branch | 冻结时 `build_manifest` 有 clean-tree、`test_count is required`、latest scan `not successful`、拒绝覆盖四道闸门；manifest scan `scan-20261114T125130Z-574f7b` 在 DB 中 `status=success`、`as_of=2026-11-13`、1506 anomalies/11 opportunities，与 manifest 一致；`test_count=166` 与离线运行一致；两个 artifact SHA256 实测匹配（report `329b1f77…`、scan `dc913bb9…`）。V1 tag `v1-frozen-1f2b341^{}=1f2b341` 保留，`config/`、`goe/scoring.py`、`goe/opportunities.py` 相对 tag 无 diff，分支存在。**但验收时工作树已相对 `a31f545` 变脏**（见下） | **PASS（冻结时）；当前状态 P1** |
| 6 | 测试离线计数；contract tests | `pytest tests -m "not network" -q` 退出码 0；manifest 的 166 与冻结提交的 166 passed + 1 skipped 一致（当前工作树新增 1 个未提交测试后 collect 为 168）。`tests/test_contracts.py + tests/test_research_v2.py` 通过（当前工作树 10 passed, 1 skipped；冻结提交为 9 passed, 1 skipped）。唯一 skipped 仍是慢速真实数据契约测试（`GOE_SLOW!=1` 默认跳过） | **PASS** |

## 二、复现证据

### P1-2（未完全闭环）：observation_date 已补，但 anomaly date 仍是 availability

```text
14/14 macro anomaly 有 observation_date
date==observation: 0/14
date==available:   14/14
CN_CPI  as_of=2026-05-16  available_date=2026-05-16  observation_date=2026-04-01
```

`goe/anomalies.py::emit_rows` 只写 `evidence["observation_date"] = date - lag`，输出行 `"date"` 仍取 availability-dated FeatureFrame 的索引；`contracts/DETECTION_CONTRACT.md` 第 4 行要求 `date (observation)`。因此同一 P1 的“日期列语义”部分未修，仅“证据字段缺失”部分已修。

### P1-4（闭环）：临时 DB 副本输出

```text
timeout     task=('RC-20261113-12','not_completed:timeout')  event=ia_research_not_completed
refused     task=('RC-20261113-12','not_completed:refused')  event=ia_research_not_completed
rejected    task=('RC-20261113-12','not_completed:rejected') event=ia_research_not_completed
ok+rejected task=('RC-20261113-12','not_completed:rejected') event=ia_research_not_completed
L2-only  semantic=insufficient_data  reason=下游回答缺少 L1 事实行（不能仅凭观点行判成功）
L1+L2    semantic=ok_valid
```

### P1-3（闭环）：UST 关键期限

```text
baseline                 ok=True  critical=[]
UST:2Y stale 2026-09-01  ok=False critical=核心收益率曲线关键期限过期：UST:2Y 最后 2026-09-01
UST:2Y deleted           ok=False critical=核心收益率曲线缺少关键期限：UST:2Y（研究依赖，拒绝发布）
```

### P1-1（闭环）：真实候选

```text
RC-20261113-12 PASS  cand_ev_for=2 cand_ev_against=1 falsifiers=3 (H1,H1,H1)
H1 ef=1 ea=0 | H2 ef=0 ea=1 | H3 ef=0 ea=1 | H4 ef=1 ea=1 | H5 ef=0 ea=1
```

`H1.evidence_against` 为空列表但字段存在；契约只要求字段存在，故不阻断，列为 P2 语义提示。

## 三、新发现：冻结后工作树漂移（P1，需处理）

验收时 `git status --porcelain`：

```text
 M audit/EXECUTION_STATE.md
 M audit/V2_FINAL_ACCEPTANCE.md
 M evaluation/V2_EVALUATION_RESULTS.md
 M goe/research_evaluation.py
 M tests/test_research_v2.py
?? audit/V2_FINAL_VERIFICATION_RESEARCH.md
?? audit/releases/release_a31f545dbc.json
```

这些修改的 mtime 为 `21:08:53–21:09:00`（manifest 生成于 `21:08:28`，任务开始于 `21:08:38`），即在冻结/签 manifest **之后**产生；其中 `goe/research_evaluation.py` 与 `tests/test_research_v2.py` 是代码/测试改动（非仅文档）。manifest 的 `git_dirty=false` 在生成时成立，但**当前工作树已不是 `a31f545` 的内容**，冻结快照不可按现状复现。若这些是并发收尾改动，必须提交后重跑 release gate/重签 manifest；若不属于交付，应回退。`release_a31f545dbc.json` 本身仍未跟踪（上轮 P2 延续）。

## 四、剩余 P0/P1

**P0：无。**

**P1（2 项）：**

1. **宏观 anomaly 日期语义未闭环**：`observation_date` 14/14 已补，但 anomaly `date/as_of` 仍 14/14 = `available_date`，0/14 = observation，违反 `contracts/DETECTION_CONTRACT.md` 的 `date (observation)` 定义；需在 anomaly 行拆分 `date=observation`、`available_date=availability`（并同步测试/重扫/重签），或正式修订合同并让测试同步。
2. **冻结后工作树漂移**：`a31f545` 之后有 5 个已跟踪文件未提交修改（含 `goe/research_evaluation.py`、`tests/test_research_v2.py`），当前交付与 manifest 的 clean-tree 冻结快照不一致；需提交并重签，或回退后再签收。

**P2（记录，不阻断）：** 导出仅 1 个候选（`--limit 1`），全量 10 候选未重跑；`H1.evidence_against=[]`（字段存在但无反向证据）；默认 `GOE_SLOW!=1` 仍跳过真实 triage 契约测试；`V2_ISSUES.md` V2-09 仍写“CLI integration remains a V3 item / timeout label preserved in result”，与实际已修不符；manifest/report 未跟踪；`test_count` 仍由调用方自报、无测试证据哈希。

## 五、状态签收

| 维度 | 状态 |
|---|---|
| EXECUTION / RELEASE | **PASS WITH ISSUES**（gate、哈希、tag、branch、test_count 均过；冻结后工作树漂移待处理） |
| DATA（宏观证据/UST） | **PARTIAL**（UST 已闭环；macro `observation_date` 已补，`date` 语义仍为 availability） |
| RESEARCH CONTRACT | **PASS**（真实候选通过 validator；falsifier/evidence 字段满足合同；DISCOVERY VALUE 不在本次范围） |
| A→B INTEGRATION | **PASS**（timeout/refused/rejected/L2-only/单前缀/CLI 全部闭环） |
| ENGINEERING VALIDATION | **PASS**（离线 166 passed, 1 skipped；contract/V2 目标套件通过） |
| 总 verdict | **PASS WITH ISSUES**（无 P0；2 项 P1：macro 日期语义、冻结后工作树漂移） |
