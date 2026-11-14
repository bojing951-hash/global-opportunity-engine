# V2 最终工程/契约 QA（独立，只读）

- 对象：`global-opportunity-engine`，分支 `architecture/research-v2`，冻结提交 `44b95722f6277cea7d34a2e760caa7dcd511ea11`（`44b9572`），release manifest `audit/releases/release_44b95722f6.json`
- V1 tag：`v1-frozen-1f2b341`（annotated，解引用为 `1f2b341`）
- 方式：静态阅读 + 只读测试/查询；未改代码、配置、测试、git
- 说明：持久化语义测试曾临时写入两条 `research_tasks`/`opportunity_events` 记录，随后删除；QA 残留计数为 0。除本文件外无最终写入。
- 结论：**PASS WITH ISSUES**。上一轮 P0 已修复；仍有 3 项 P1 未闭环（下方），且 `DISCOVERY VALUE: NOT VALIDATED` 不变。

## 一、检查总表

| # | 检查项 | 观察 | 结论 |
|---|---|---|---|
| 1 | V2 资产已提交、分支可 checkout、V1 tag 保留 | HEAD=`44b9572`，分支 `architecture/research-v2`，3 个 V2 commit（`4e3f40d`/`7ead637`/`44b9572`）；`git status --porcelain` 仅 `?? audit/releases/`；contracts/`goe/contracts.py`/`research_triage.py`/`release.py`/`test_research_v2.py`/`evaluation/` 均已跟踪；`v1-frozen-1f2b341^{}`=`1f2b341`；`config/`、`goe/scoring.py`、`goe/opportunities.py` 相对 tag 无 diff | **PASS** |
| 2 | release gate 与 manifest | `build_manifest` 拒绝脏树、缺 `test_count`、最新 scan 非 success；产物哈希存在且匹配；同 commit 拒绝覆盖。manifest：commit `44b9572`、branch、scan `scan-20261114T092442Z-5ef9b9`（success）、`test_count=165`、1506 anomalies/11 opportunities、2 个 report artifact SHA256 全部匹配 | **PASS**（P2 见下） |
| 3 | 宏观 anomaly 的 observation/availability 证据 | 当前 DB 14 条 macro anomaly：**14/14 无 `observation_date`**；`available_date` 语义正确（如 `CN_CPI` 观测 2026-04-01，`available_date=2026-05-16`，= +45d）；但 anomaly 行 `date` 仍等于 availability，而非 DETECTION 合同要求的 observation | **FAIL（P1）** |
| 4 | UST 2Y/10Y 新鲜度（删除 2Y） | 在 `/tmp` DB 副本上：基线 `ok=True`；2Y 变旧（最后 2026-09-01）→ critical；删除 2Y（10Y 仍新鲜 2026-11-12）→ critical「缺少关键期限」 | **PASS** |
| 5 | ResearchCandidate validator | 正例通过；`evidence_for/against` 为空、`source` 空、未来 `available_at`、`hours=-1`、重复 hypothesis id、`method`/`evaluation_id` 不符均被拒。**但真实 triage 10 个候选有 5 个无法通过**：`TW_EQ_TAIEX`、`US_SEC_XLV`、`CH_EQ_SMI`、`MX_EQ_IPC`、`US_FAC_MTUM`（`evidence_against=[]`） | **VALIDATOR PASS；真实链路 FAIL（P1）** |
| 6 | triage 序数优先级、H3、falsifier、V1 元数据 | 候选按 tier→M→G→D→I→hours→id 排序；tier A/B/C 与 M/G/D/I 等级一致；H3 只在有可用 positioning 的 DXY 为 open（5 候选中 1/5，旧版为全部 open）；falsifier 数量/阈值/机制按候选变化（N225 2 条、QQQ 3、TAIEX 1、XLV 2、DXY 4）；V1 `score/status` 在一次运行 4/5 有值、V1 excluded 的 TAIEX 仍为 tier B（V1 未决定 tier）；但另一次同 HEAD 运行 V1 全为 null（宽泛 `except` 静默吞读库失败） | **PASS（带 P2：V1 元数据非确定性）** |
| 7 | 测试 | `pytest tests -m "not network"`：**165 passed, 1 skipped, 9 deselected, 57.06s**；`pytest tests/test_contracts.py tests/test_research_v2.py`：**8 passed, 1 skipped**（9 项）。唯一 skipped 的是真实 triage 契约测试；在真实候选上它会失败（见 P1-1） | **PASS（计数）；测试闸门有 P1 漏洞** |
| 8 | A→B fact-only 与持久化 | 真实候选问题无任何 banned 词，事实/来源/未知/证伪齐全；`persist_v2_result` 对 refused → `not_completed:refused`、ok_valid+not_ok → `not_completed:ok_valid`（均非 completed）；**timeout → `not_completed:unknown`（非 `:timeout`）**，task_id 仍为 `RC-RC-...` 双前缀；L2-only artifact（L1=0、L2=17、evidence 非空、S8 answered）仍返回 `ok_valid` | **事实问题 PASS；持久化/L2 语义 FAIL（P1）** |
| 9 | 新 P0/P1 回归 | 无新 P0。新 P1：真实候选违反自身 validator；遗留 P1：macro 证据无 observation_date、A→B timeout/L2-only；默认套件跳过真实契约测试，掩盖 P1-1 | **PASS WITH ISSUES** |

## 二、复现证据

### P1-1（新）：真实 triage 候选违反 `validate_research_candidate`，默认测试不覆盖

```bash
.venv/bin/python -m goe.cli triage --as-of 2026-11-13 --limit 10 --out /tmp/qa_triage
.venv/bin/python - <<'PY'
import json
from goe.contracts import validate_research_candidate
for c in json.load(open('/tmp/qa_triage/research_candidates_2026-11-13.json'))['candidates']:
    try: validate_research_candidate(c); print(c['research_id'], 'PASS')
    except Exception as e: print(c['research_id'], 'FAIL', e)
PY
```

实测：`RC-20261113-16 / -22 / -01 / -15 / -18`（TAIEX、XLV、SMI、IPC、MTUM）失败，错误均为
`research candidate needs evidence_for and evidence_against`。原因：`goe/research_triage.py` 只在
机制冲突、|1m|<3% 或 commodity 时追加 `evidence_against`；强势非商品、无机制冲突的候选得到空列表，
而 `goe/contracts.py` 的校验器硬性要求非空。`tests/test_contracts.py::test_research_v2_real_scan_contract`
以 `max_candidates=3` 校验，第 3 名 TAIEX 即失败；该测试默认因 `GOE_SLOW != 1` 跳过（本次 1 skipped），
所以 165 passed 不能证明 V2 真实链路符合合同。将 `evidence_against` 补为必有（哪怕是一条
“尚无反向证据/待检验”）即可，属 P1 集成缺口。

### P1-2：冻结 DB 中宏观 anomaly 缺 `observation_date`，`date` 仍是 availability

```bash
python3 - <<'PY'
import sqlite3, json
c=sqlite3.connect('data/goe.db'); c.row_factory=sqlite3.Row
rows=c.execute("select as_of,available_date,instrument_id,evidence_json from anomalies").fetchall()
m=[r for r in rows if json.loads(r['evidence_json']).get('entity_kind')=='macro']
print(len(m), sum('observation_date' not in json.loads(r['evidence_json']) for r in m))
print([(r['instrument_id'],r['as_of'],r['available_date']) for r in m[:3]])
PY
```

实测：14 条 macro anomaly，0 条含 `observation_date`。示例 `CN_CPI`：DB `as_of=available_date=2026-05-16`，
指标观测 `2026-04-01`，+45d 的 `available_date` 正确，但 evidence 未写观测日，且 anomaly `date`
按 DETECTION 合同应为 observation 却仍为 availability。代码 `goe/anomalies.py` 已在 `emit_rows`
补写 `observation_date`，但当前 release manifest 固定的是修复前生成的 scan（2026-11-14T09:24:42Z），
冻结证据未重建。需重扫并重签 manifest，否则 DATA 不能按“PASS”签收。

### P1-3：A→B 持久化仍丢 timeout 语义、L2-only 仍可 ok_valid

```bash
.venv/bin/python - <<'PY'
from goe.db import Store
from goe.integration.research_handoff import persist_v2_result
from goe.integration.ia_adapter import parse_research_artifact
s=Store('data/goe.db')
cand={"research_id":"RC-QA","as_of":"2026-11-13"}
for res in ({"status":"timeout","timeout_s":5},{"status":"not_ok","semantic_status":"refused"}):
    persist_v2_result(s,cand,res,'/tmp/qa')
    print(s.conn.execute("select status,task_id from research_tasks where task_id='RC-RC-QA'").fetchone())
PY
```

实测：timeout → `not_completed:unknown`（合同要求 `not_completed:<semantic>`，至少 `:timeout`），
task_id=`RC-RC-QA`；refused → `not_completed:refused`（正确，且 event 为 `ia_research_not_completed`）。
另外，`parse_research_artifact` 对 `run_ok=true, evidence_index=[1], L1 rows=0, L2 views=17, S8=answered`
返回 `ok_valid`，仍违反 HANDOFF 合同“no path where L2-only artifact is completed”。`handoff_v2` 也仍无
CLI 子命令入口（仅模块/测试调用）。

### 其余 PASS 的复现要点

- release：`build_manifest` 在真实脏树、`test_count=None`、最新 scan 改为 failed 时分别抛
  `dirty worktree` / `test_count is required` / `latest scan ... not successful`；artifact SHA256
  与 `reports/report_2026-11-13.md`、`reports/scan_2026-11-13.json` 一致；重复调用拒绝覆盖。
- UST：在 `/tmp/goe_qa.db` 上将 `UST:2Y` 截到 2026-09-01 或整条删除，`check_data_readiness(as_of=2026-11-13)`
  均 `ok=False` 且 critical 含「关键期限过期/缺少」；10Y 仍为 2026-11-12。
- triage：`/tmp/qa_triage` 10 候选排序为 A(rank1)、B(2-6)、C(7-10)；`materiality.level/gap_level/
  distinguishability_level/decision_impact_level` 单调；`priority_tier` 不读取 `v1_score`（TAIEX 的 V1
  status=excluded、score=0.3792 仍是 tier B），无加权和；H3 仅 DXY open；falsifier 含候选实际
  `credit_z=-0.55`、`rel_z=-2.33/2.46/1.08`、机制 id、CFTC 阈值；N225 的 A→B 问题无 banned 词。
- 测试：`165 passed, 1 skipped, 9 deselected` 与 manifest `test_count=165` 一致；目标套件
  `test_contracts.py + test_research_v2.py` 为 `8 passed, 1 skipped`。

## 三、剩余 P0/P1

**P0：无。**

**P1（必须修复/重签后才能称完整 PASS）：**

1. 真实 triage 候选 5/10 无法通过自身 `validate_research_candidate`（`evidence_against` 为空）；
   `GOE_SLOW=1` 的真实契约测试会在第 3 名 `TW_EQ_TAIEX` 失败，而默认套件跳过该测试。
2. 冻结 DB 的 14 条 macro anomaly 全部缺少 `observation_date`，且 anomaly `date` 仍为 availability；
   代码已修但 release 证据未重扫/未重签 manifest。
3. A→B 持久化：timeout 写成 `not_completed:unknown`（应保留 timeout）、`RC-RC-` 双前缀；
   L2-only artifact 仍可 `ok_valid`；`handoff_v2` 无 CLI 入口。

**P2（记录，不阻断）：** release manifest 未跟踪、`test_count` 仍为调用方自报且无测试证据哈希；
`audit/V2_FINAL_ACCEPTANCE.md` 引用不存在的 `audit/V2_FINAL_QA.md`；V1 元数据读取异常被
`except: pass` 静默吞掉；`_clean` 仍会把候选事实中的「仓位/买入」等改写成「净头寸/研究判断」；
`test_v2_evaluation_decision_rule_is_not_automatic` 仍为恒真断言；protocol 的 test D n=1 文字与
当前 n=3 结果不一致；候选只带 D evaluation id，未落实合同的 A/B/C/D 多 ID；Tier 排序仍以 tier
桶先于 M（严格 M-first 的可解释性存疑）。

## 四、状态签收

| 维度 | 状态 |
|---|---|
| EXECUTION ARCHITECTURE | **PASS**（P0-1/P0-2 已修；分支/提交/tag/release gate/manifest 哈希通过；残留 P2） |
| DATA ARCHITECTURE | **PARTIAL**（UST 关键期限新鲜度已修；宏观证据 observation_date 缺失，需重扫） |
| RESEARCH CONTRACT | **PARTIAL**（schema/validator 已实现并能拒绝坏数据；真实输出 50% 违反自身契约；`DISCOVERY VALUE: NOT VALIDATED` 不变） |
| ENGINEERING VALIDATION | **PASS WITH ISSUES**（165 passed；真实链路被默认 skip，且会失败） |
| A→B INTEGRATION | **PARTIAL**（fact-only 问题通过；timeout/L2-only/CLI 未闭环） |
| 总 verdict | **PASS WITH ISSUES**（无 P0；3 项 P1） |
