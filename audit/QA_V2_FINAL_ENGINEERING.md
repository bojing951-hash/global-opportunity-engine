# V2 最终工程 QA（独立，只读）

- 对象：`global-opportunity-engine`，冻结提交 `51f4a62`（代码 `77de558`），分支 `architecture/research-v2`
- 发布产物：`audit/releases/release_77de558c22.json` + `audit/test_evidence/20261114T154925Z_77de558c22.{proof.json,log}`
- 方法：`/tmp/qa_v2_51f4a62` 无数据 clone（`51f4a62`，无 `data/`）跑默认/显式 pytest；release gate 篡改矩阵；真实 `data/goe.db` 只读 SQL；`evaluation/v2_candidates_20_2026-11-13.json` 静态核对；`/tmp` DB 副本跑 V2 CLI。除本文件外未写入代码/配置/测试/git/数据。
- 结论：**PASS WITH ISSUES**。ENGINEERING **PASS**；RELEASE GATE 具备基本抗篡改但仍有 **2 个 P1**（同用户自洽伪造可绕过 rerun、rename 绕过 clean-tree），且 QA 期间工作树被外部写入，当前已非 clean。无 P0。

> 工作树状态（重要）：QA 开始时 `git status --porcelain` 为空；QA 期间开始出现并行进程写入
> （非本代理，且到 QA 结束仍在增加），已观察到 `goe/release.py`、`goe/hypotheses.py`、
> `tests/test_hypotheses.py`、`audit/V2_FINAL_ACCEPTANCE.md`、
> `evaluation/new_window/V2_EVALUATION_RESULTS.md` 以及 `audit/QA_V2_FINAL_RESEARCH.md`。
> 其中 `release.py` 改动给 `build_manifest` 的 rerun 增加落盘日志；`hypotheses.py`/`tests`
> 改动会改变候选生成与测试语义。当前工作树不能按 “clean” 签收，最终状态以 lead 执行的
> `git status --porcelain` 为准，需决定提交/回退后重签。下文所有冻结提交证据均来自
> `51f4a62` 的 git 对象或 `/tmp` clone；P1-C 结论针对冻结 artifact，不含上述未提交改动。

## 一、检查总表

| # | 检查项 | 关键证据 | 结论 |
|---|---|---|---|
| 1 | 无数据 clone 测试 | 显式命令 exit 0：**176 passed, 10 deselected, 0 failed, 0 skipped, 777 warnings, 53.83s**；默认 `pytest tests -q` exit 0，选择集相同（JUnit XML：tests=176, failures=0, errors=0, skipped=0, 54.59s；控制台 summary 因 `-qq` 被抑制，P2） | **PASS** |
| 2 | 测试不得触碰 `data/goe.db` | clone 运行前后无 `data/` 目录；audit hook 对任何以 `data/goe.db` 结尾的 open/sqlite3.connect 记录为空（`NO_DB_ACCESS`）；仓库 `data/goe.db` SHA256 运行前后均为 `ce7d7e56…` | **PASS** |
| 3 | 真实 proof/log/manifest 内部一致性 | proof：`passed=176, failed=0, skipped=0, deselected=10, git_commit=77de558, git_dirty=false`；log SHA256 `675a1a0b…` 与 proof、manifest 一致；manifest 两个 report artifact SHA256 均匹配；scan `scan-20261114T125130Z-574f7b` success，1506 anomalies / 11 opportunities 与 DB 一致；`verify_test_proof` 在 HEAD=`51f4a62` **接受**；`77de558..51f4a62` 仅 3 个 audit 文件 | **PASS** |
| 4 | 篡改必须拒绝 | 改 proof 计数→拒（disagrees）；重写 log→拒（hash mismatch）；缺 log→拒（missing）；stale/伪造 commit→拒（not ancestor）；`git_dirty=true`→拒；旧代码 proof（`5c19289`/`83a1160`）→拒；脏文件 `tests/audit/test_evidence/x.py`→`run_test_proof` 拒（clean worktree） | **PASS（基本矩阵）** |
| 5 | release gate 残余绕过 | ① 自洽伪造 proof（伪造 log+sha+`command=["sh","-c","printf \"176 passed\"","tests","pytest"]`）`verify_test_proof` **接受**，`build_manifest` 的 rerun 也会执行该伪造命令并通过；② staged rename `audit/test_evidence/x.log -> goe/payload.py` 时 `_dirty_code()` 返回 **False**；③ manifest 无任何 verify 函数 | **FAIL（P1，见 P1-1/P1-2）** |
| 6 | P1-D 生命周期/FK/legacy/V1 隔离 | V2：20 candidates（1 A/4 B/7 C/8 intelligence）、100 hypotheses（51 untestable）、161 evidence、1 task、2 results、5 events；`RC-20261113-12` 拒答后保留为 `handoff_failed`（7 hyp/12 ev/1 task/2 results/5 events）；`foreign_key_check` 空、`integrity_check=ok`、6 个 orphan/legacy counter 全 0；V1：11 OPP、2 `research_tasks`（RT-OPP）、13 events，无 RC 泄漏 | **PASS** |
| 7 | A→B 真实语义 | 真实 task=`not_completed:refused`（非 completed）；result 同时保留 `rejected`（rc=1）与 `refused`（rc=0，S8 `no_registry_identity`）；`persist_v2_result` 仅 `status==ok && semantic==ok_valid` 才 completed；L2-only→`insufficient_data`；timeout→`not_completed:timeout`；进程失败（fake CLI rc=2 无 report）→`semantic_status=error`、status=not_ok，与 refused 区分 | **PASS** |
| 8 | P1-C 20 候选差异/证据 | 15 个 distinct (type,label) 签名、7 个 hypothesis-ID/test 签名；按资产类仍模板化（commodity 4↔1、sector 4↔1、FX 2↔1、equity_index 6↔2）；48 条 evidence 中 **20 条（42%）为可得性占位**，非测量值（`local FX`、`VIX/CREDIT_RISK`、`global growth proxies`、`DXY, UST`、`futures`、`UST`、`DXY`）；JP A 级 `本地汇率可观察:local FX` 无汇率数值 | **PARTIAL（P2）** |
| 9 | 测试/契约/V1 回归 | 176 passed 含 V1 scoring/opportunities/DB/contracts；V1 11 OPP 未变；无新增 P0；`mechanisms=['unsupported']` 不再作为支持证据（artifact 中 0 条） | **PASS** |

## 二、剩余 P1（含复现）

### P1-1 release gate 的 “独立 rerun” 可被自洽伪造绕过

`verify_test_proof` 只做 proof↔log↔HEAD 的内部自洽；`build_manifest` 的 rerun 直接执行 **proof 自带 command**，且只要求 `passed>0`、不看是否与 proof 计数一致。因此同一用户可同时伪造 proof/log/sha 与一条“假 pytest”命令，使 verify 和 rerun 都通过。

```bash
# 在冻结代码上实测（proof 的 passed 改为 9999 会拒绝；下表最后一项是绕过）
.venv/bin/python - <<'PY'
import json, hashlib, tempfile
from pathlib import Path
import goe.release as rel
base=json.loads(Path('audit/test_evidence/20261114T154925Z_77de558c22.proof.json').read_text())
tmp=Path(tempfile.mkdtemp()); log=tmp/'l.log'
log.write_text('176 passed in 1s\n'); base=dict(base); base['command']=['sh','-c','printf "176 passed\\n"','tests','pytest']
base['log_path']=str(log); base['log_sha256']=hashlib.sha256(log.read_bytes()).hexdigest()
pp=tmp/'p.json'; pp.write_text(json.dumps(base))
print(rel.verify_test_proof(pp)['passed'])   # -> 176，接受
PY
```

影响：`build_manifest` 的 rerun 不能证明“真的跑了仓库套件”；冻结 manifest 的 rerun 计数（176）只对诚实调用者有约束。建议 rerun 使用固定 argv（`sys.executable -m pytest tests -o addopts="" -q -m ...`），忽略 proof.command，并逐项比较 passed/failed/skipped/deselected 与 proof。

### P1-2 `_dirty_code` 可被 staged rename 绕过

`_dirty_code` 取 `git status --porcelain` 的 `line[3:]` 后只做 `startswith(("audit/test_evidence/","audit/releases/"))`；rename 行形如 `R  audit/test_evidence/x -> goe/x.py`，整行以豁免前缀开头，于是新增/改写的代码文件被当作 clean。

```bash
cd /tmp/qa_v2_51f4a62       # 51f4a62 clean clone
git mv audit/test_evidence/20261114T154925Z_77de558c22.log goe/payload_stolen.py
.venv/bin/python -c "import goe.release as r; print(r._dirty_code())"   # -> False
```

影响：可在“tree 与 commit 不一致”的情况下生成 `git_dirty=false` 的 proof（测试确实跑在脏树上，但 proof 绑定的是 HEAD）。建议改用 `git status --porcelain -z` 并对 rename 的**新路径**单独判定，或直接 `git diff --name-only HEAD` + `git diff --cached --name-only` 白名单。

### P1-3（验收状态）当前工作树被外部写入，不再 clean

QA 开始时 clean；QA 期间出现并行进程写入（非本代理），例如 `goe/release.py`、
`goe/hypotheses.py`、`tests/test_hypotheses.py`、`audit/V2_FINAL_ACCEPTANCE.md`、
`evaluation/new_window/V2_EVALUATION_RESULTS.md`，以及 `audit/QA_V2_FINAL_RESEARCH.md`
和本报告；到 QA 结束时仍在增加。`goe/release.py` 的改动为 `build_manifest` rerun 落盘
（`rerun_<ts>.log` + hash），与 `51f4a62` 的冻结内容不同；`hypotheses.py`/`tests` 改动会改变
候选生成与测试语义。冻结 commit 本身未被改动，但“worktree clean + manifest 可复核”不能对当前
目录成立；最终签收前需由 lead 查看 `git status --porcelain`、提交/回退这些改动并重跑
proof/release，否则 `release_77de558c22.json` 只对 `51f4a62` 的 git 对象有效。
P1-C 审计基于冻结 artifact，不含上述未提交改动。

## 三、P2 / 需披露

1. **manifest 无法机验**：仓库只有 `verify_test_proof`，没有 `verify_manifest`；manifest 自身（计数、commit、rerun）被编辑后无 gate 会拒绝。本次为人工交叉核对。
2. **默认 `pytest tests -q` 无 summary**：`pyproject.toml` 的 `addopts=-q` 叠加命令行 `-q` 得 `-qq`，退出码 0 但看不到计数（JUnit XML 证实 176/0/0/0）。
3. **rerun 计数不比对**：即使命令是真实 pytest，rerun 的 175/176 差异也不会导致拒绝；仅检查 failed/errors/`passed>0`。
4. **P1-C 证据质量**：20 条候选的 48 条 `observed_fact` 中 20 条是“数据可得”占位而非观测值；例：
   - `RC-20261113-12`（JP，tier A）：`本地汇率可观察: local FX`（source=prices，无数值）、`区域属于政策敏感市场: JP`（config）；
   - `RC-20261113-19`（XLV）：`利率与相对强弱可观察: 1m=8.0%` 与 `行业相对表现可观察: 1m=8.0%` 复用同一收益值，未给出利率/相对强弱测量；
   - 9 条 commodity 的 `全球风险代理可观察: global growth proxies`、`DXY/UST 可用: DXY, UST`、`连续合约存在换月风险: futures` 均为标签。
5. **模板残留**：虽达到 15 个 (type,label) 签名，但同子类 falsifier 完全复用（commodity 4 条同一套、sector 4 条同一套、FX 2 条同一套；测试签名仅 7 种）；`H-GLOBAL/H-FUND/H-POS/H-ART` 在 JP/TW 等国家股票间逐字相同。验收“15 distinct signatures”应按公开定义复算，不能等同于 15 种研究设计。
6. **V2 CLI**：`triage --db /tmp 副本 --as-of 2026-11-13 --limit 3 --out /tmp/qa_triage` 正常产出（3 候选，RC=0），但真实 DB 上耗时 >60s；`--handoff` 真实下游路径本次未执行（避免写 exports/DB），仅静态核对。

## 四、A→B / P1-D 证据细节

```text
research_v2_tasks:  RC-20261113-12 | investment-agent | not_completed:refused
research_v2_results: 1 rejected rc=1 run_ok=0 (task RC-20261113-12)
                     2 refused  rc=0 run_ok=0 (S8 no_registry_identity, n_L1=0/n_L2=17)
candidate:           RC-20261113-12 status=handoff_failed，仍保留 7 hypotheses / 12 evidence
events:              ia_research_not_completed + status:handoff_failed（含 task_id）
FK:                  PRAGMA foreign_key_check -> 空；integrity_check -> ok
orphans:             hypotheses/evidence/tasks/results/legacy_v1_rc_tasks/legacy_v1_rc_events = 0
V1:                  opportunities=11、research_tasks=2（RT-OPP）、opportunity_events=13；无 RC 行
```

说明：`refused` 的 result 行 `run_ok=0` 是“整体有效=否”，payload 内 `run_ok:true` 是下游进程成功，两者语义不同但不构成伪成功；`rejected`（进程/artifact 失败）与 `refused`（下游明确拒答）在 result 与 event 中均区分。

## 五、最终状态

- **OVERALL：PASS WITH ISSUES**
- **ENGINEERING：PASS**（176 passed / 10 deselected，无 DB 触碰；生命周期/FK/V1 隔离/A→B 均通过；无 P0）
- **RELEASE GATE：PASS WITH P1**（基本篡改矩阵全部拒绝；自洽伪造 + rerun、rename 绕过未闭环，且当前工作树非 clean）
- **P1-C：PARTIAL**（15 签名可复算，但同子类模板与 42% 可得性占位证据仍在）
- **DISCOVERY VALUE：NOT VALIDATED**（沿用冻结结论，本次未重做评估）

本报告是本次 QA 唯一写入；测试与篡改实验均在 `/tmp` clone/副本上执行，仓库 `data/goe.db` 未被改动。
