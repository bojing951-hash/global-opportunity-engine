# V2 最终工程/契约复核 2（独立，只读）

- 对象：`global-opportunity-engine`，分支 `architecture/research-v2`
- 复核起点（原任务目标）：冻结提交 `5db6e33`（代码 `532d819`）+ `audit/releases/release_532d819dcf.json`
- 最终状态（复核期间仓库推进，已按最终状态复验）：`HEAD=bad22cd`（`bad22cd` 仅提交 manifest），代码提交 `85f14d2ff7`，manifest `audit/releases/release_85f14d2ff7.json`
- 方式：`git status/log/show/diff`、冻结 DB 只读 SQL、离线 pytest、artifact SHA256 复算；未改代码/配置/数据，除本文件外无写入
- 结论：**PASS**。两项 P1 均闭环，无 P0；新增 1 项不阻断 P2（测试语义残留）

## 一、检查总表

| # | 检查项 | 证据 | 结论 |
|---|---|---|---|
| 1 | P1-1 宏观 anomaly 日期语义：合同定义、代码、DB、recency | `contracts/DETECTION_CONTRACT.md` 明确 `date` 为 detection/decision date；宏观 `date=availability`、`available_date` 同值、`evidence.observation_date=原始参照期`，并写明 recency/decision 不得使用未发布观测。代码 `goe/anomalies.py::emit_rows` 的 `date` 取 FeatureFrame 行索引、`available_date=ctx.availability(...)`、`observation_date=date-lag`；生产 `FeatureBuilder(point_in_time=True)` 置 `macro_dates_are_availability=True`。DB 14/14 宏观 anomaly `as_of==available_date`，14/14 有 `observation_date`，14/14 `observation_date<=available_date`（0 条未来/未发布观测）。recency 由 `goe/timesemantics.py::filter_recent` 与 `goe/opportunities.py` 使用 `available_date`，未消费 `observation_date` | **PASS** |
| 2 | P1-2 工作树/manifest 漂移 | `git status --porcelain` 为空（0 项）；HEAD 链 `532d819 → 5db6e33 → 85f14d2 → bad22cd`；`git ls-tree HEAD audit/releases` 含 manifest；manifest `git_dirty=false`、`git_commit=85f14d2ff7…`、`test_count=167`、scan `scan-20261114T125130Z-574f7b` 为 `success`；scan_counts 1506/11 与 DB 一致；两个 artifact SHA256 复算匹配。原 `5db6e33` 状态亦为 clean、manifest 钉 `532d819`、同 scan/test_count | **PASS** |
| 3 | 离线测试计数 | `pytest tests -m "not network" -q` 退出码 0；collect 168，1 skipped（`GOE_SLOW!=1` 的真实数据慢测），**167 passed**，与 manifest `test_count=167` 一致 | **PASS** |
| 4 | Release gate 抽查 | `goe/release.py` 四道闸门仍在（dirty 拒绝、`test_count` 必填、latest scan 必须 success、已有 manifest 拒绝覆盖）；`tests/test_contracts.py::test_release_gate_refuses_dirty_or_untested` 随套件通过。manifest 的 commit/scan/hash/count/test_count 逐项与实况匹配，`created_at=13:25:19Z`、`bad22cd=13:25:20Z`，先签 manifest 后提交，顺序正确 | **PASS** |
| 5 | 新增问题 | `tests/test_time_semantics.py::test_macro_anomaly_carries_observation_and_availability_dates` 仍断言宏观 `rec["date"]=="2026-09-01"`（observation），与新合同“date=availability”相反；该测试用不含 `macro_dates_are_availability` 的 fixture，故可继续通过。生产路径/DB 不受影响 | **P2（不阻断）** |

## 二、P1-1 复现证据

```text
contracts/DETECTION_CONTRACT.md:
  date (detection/decision date)
  For macro/valuation, date is the availability date; available_date is the same
  availability timestamp and evidence.observation_date is the original reference period.
  recency/decision logic must never use an unpublished observation date.

DB (data/goe.db, read-only):
  macro anomalies        = 14
  has observation_date   = 14
  as_of == available_date = 14
  obs <= available       = 14   future/unpublished = 0
  示例: 2026-05-16 | 2026-05-16 | observation=2026-04-01

recency: goe/timesemantics.py:69-76 使用 available_date；
         goe/opportunities.py:190/222/1096 使用 available_date；
         observation_date 仅写入 evidence，全库无读取点。
```

原 P1 的“date 仍等于 available_date”不是回归，而是合同修订后的显式语义；本次核对确认代码、DB、合同三者一致，且未用未发布观测做 recency。

## 三、P1-2 复现证据

```text
git status --porcelain          -> (空)
HEAD                            -> bad22cd  chore(v2): re-freeze manifest after P2 cleanup
HEAD^                           -> 85f14d2  docs(v2): close remaining P2 wording drift
HEAD~2                          -> 5db6e33  chore(v2): freeze manifest for final verification commit
532d819 is ancestor of HEAD     -> true

audit/releases/release_85f14d2ff7.json (committed at HEAD):
  git_commit=85f14d2ff78c1f7aa744fba6c88d808c46cd8a16, git_dirty=false
  test_count=167
  scan.status=success, scan_id=scan-20261114T125130Z-574f7b, as_of=2026-11-13
  counts: anomalies=1506, opportunities=11; status 4+2+3+2=11
  report hash 329b1f77… 匹配; scan hash dc913bb9… 匹配

release_532d819dcf.json（原任务目标）: 仍被跟踪、内容完整，git_commit=532d819, test_count=167,
git_dirty=false, scan 同为 success；5db6e33 时工作树 clean。
5db6e33→85f14d2 仅文档（audit/evaluation），无代码/测试改动，故重签 manifest 未改变被钉代码语义。
```

说明：复核期间 HEAD 由 `5db6e33` 前移至 `85f14d2`，随后 `bad22cd` 重签 manifest。当前最终状态 clean，manifest 与 HEAD 自洽；原 `5db6e33` 快照在推进前也已 clean 且自洽。

## 四、测试与 release gate

- 命令：`.venv/bin/python -m pytest tests -m "not network" -q` → exit 0；`168 collected, 1 skipped, 167 passed`。
- manifest 的 167 与实跑 passed 完全一致；skipped 为默认跳过的真实数据慢测，非失败。
- artifact hash、scan_id、config/data hash、as_of、counts、status 均与 DB/文件实况一致。
- `bad22cd` 的 manifest 文件名按被钉代码 `85f14d2` 生成，提交号 `bad22cd` 仅承载该文件；不存在同名覆盖。

## 五、P0 / P1 / P2

**P0：无。P1：无（两项均已闭环）。**

**新增 P2（不阻断）：**

1. `tests/test_time_semantics.py:32-46` 仍以旧语义断言宏观 `date=observation`，与 `DETECTION_CONTRACT.md` 新定义相反；因 fixture 未设置 `macro_dates_are_availability` 而通过，形成“测试固化旧合同”的残留。建议下次变更把该 fixture 改为 point-in-time（或显式设置该 flag）并同步断言 `date=availability`，避免合同回归无测试守卫。

**过程提示（非缺陷）：** 复核期间冻结点两次前移（`5db6e33→85f14d2→bad22cd`）。最终签收应以 `bad22cd` 为准；建议冻结后避免并发写入，以免独立验收目标漂移。

## 六、状态签收

| 维度 | 状态 |
|---|---|
| RELEASE / WORKTREE | **PASS**（clean；HEAD 含 manifest；commit/scan/count/hash/test_count 自洽） |
| DATA（宏观日期语义） | **PASS**（合同、代码、DB 一致；14/14；无未发布观测参与 recency） |
| CONTRACT | **PASS**（合同显式定义三字段；P1 语义闭环） |
| ENGINEERING VALIDATION | **PASS**（离线 167 passed / 1 skipped；release gate 测试通过） |
| 总 verdict | **PASS**（无 P0/P1；1 项 P2 测试语义残留，不阻断） |

> 本文件为验收产出，写出后工作树仅新增本文件（未提交），属只读约束的授权例外；写出前工作树为 clean。
