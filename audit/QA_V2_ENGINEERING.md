# V2 工程/红队独立复核（只读）

- 对象：`global-opportunity-engine`，冻结提交 **`3645951`**（代码提交 `83a1160`，`architecture/research-v2`），manifest `audit/releases/release_83a116030c.json`
- 时间：2026-11-14 23:16–23:28 HKT；时间盒 12 分钟
- 方法：两个 `/tmp` 干净 clone（`3645951`，无 `data/`）、`/tmp` DB 副本、只读 SQLite 查询、release gate 篡改矩阵、真实导出候选静态核对。未修改代码/配置/测试/数据/git；本文件是唯一由本代理写入的仓库文件。
- 结论先行：**PASS WITH ISSUES**。无 P0；工程主体、生命周期、A→B 状态语义和干净 clone 测试通过。但 **release 证据链有 3 个 P1，冻结提交的“机器可验证 test evidence”不能成立**；真实候选存在 1 条可复现的“不支持/自相矛盾证据”P1。`DISCOVERY VALUE: NOT VALIDATED` 不变。

## 一、总表

| # | 检查项 | 结果 | 证据 |
|---|---|---|---|
| 1 | P1-A 干净 clone，默认 `pytest tests -q` | **PASS（exit 0）** | clone 无 `data/`；命令 exit 0；`-q` 与 pyproject `addopts=-q` 叠加为 `-qq`，汇总行被抑制；该次运行收集/选择 174 项，与显式命令同一选择集 |
| 2 | P1-A 干净 clone，`-o addopts="" -q -m 'not network and not realdata'` | **PASS** | **174 passed, 10 deselected, 777 warnings in 197.41s，exit 0**；无 skip |
| 3 | P1-A 测试不得静默创建/读取 `data/goe.db` | **PASS** | 两个 clone 运行后均无 `data/`、无 `*.db`；全测试无无参 `Store()`/`default_db_path`；唯一读真实 DB 的 `test_research_v2_real_scan_contract` 标 `realdata`，默认被 deselect（`tests/test_contracts.py:88-97`） |
| 4 | P1-B 真实 proof/log/commit 与 manifest 内部一致 | **PASS（仅内部一致）** | proof：174 passed / 0 failed / 0 skipped / 10 deselected；log SHA256 `5ad0f646…` 匹配；manifest 的 passed/log_sha256/command 与 proof 一致；两个 report artifact SHA256 匹配；DB `1506 anomalies / 11 opportunities`、status 分布与 manifest 一致 |
| 5 | P1-B 在冻结提交可验证 | **FAIL（P1）** | proof/manifest 的 `git_commit=83a1160`，HEAD=`3645951`；`verify_test_proof` 抛 `test proof commit does not match current HEAD`。proof 的 `.log` 被 `.gitignore:19 *.log` 忽略、未提交；`83a1160` 也没有 `release_83a116030c.json`。**不存在任一 commit 可同时满足“proof 存在 + 日志存在 + commit=HEAD”** |
| 6 | P1-B 伪造成本 | **PARTIAL（P1）** | 改 proof 计数（log 不动）→ 拒；改 log（hash 不动）→ 拒；缺 log → 拒；stale commit → 拒；`git_dirty=true` → 拒。但**同时重写 log+proof+sha**（9999 passed）→ **接受**；**log 含 1 error、proof errors=0** → **接受**（errors 不参与交叉校验） |
| 7 | P1-B dirty tree 拒绝 | **FAIL（P1）** | `_dirty_code` 用“路径含 `audit/test_evidence/` 或 `audit/releases/`”做豁免（`goe/release.py:37-40`）。在临时 clone 提交 `tests/audit/test_evidence/test_x.py` 后修改它，`_dirty_code()` 返回 **False**；即“修改过的测试”可生成 `git_dirty:false` 的 proof |
| 8 | P1-D 生命周期 | **PASS** | 真实 DB：5 个 candidate，`RC-20261113-12` task=`not_completed:rejected`、result `rejected/run_ok=0`、candidate=`handoff_failed`，事件与 task 关联；四类 orphan 均 0；V1 表 2 tasks/13 events，RC 残留 0；`tests/test_research_v2.py:132-179` 覆盖 retained/no-orphan/FK/legacy migration |
| 9 | A→B 实际状态 / L2-only / timeout | **PASS** | 真实 task 非 completed；`persist_v2_result` 仅 `status==ok && semantic==ok_valid` 才 completed（`research_handoff.py:75-90`）；L2-only 返回 `insufficient_data`（`ia_adapter.py:105-110`，测试 `test_readiness_handoff.py:252`）；timeout→`not_completed:timeout`（测试 `test_research_v2.py:52`） |
| 10 | P1-C 真实候选差异（20 条） | **PARTIAL（P1/P2）** | 仓库导出仅 5 条；在 `/tmp` DB 副本上 `run_triage(max_candidates=20)` 得到 **20 条**（A1/B4/C7/intelligence8）。但只有 **7 种** hypothesis-ID 序列、**5 种** decision_impact、**7 种** test 签名：4 条 commodity 全同、4 条 sector 全同、2 条 FX 全同、5 条 country-equity（TW/CH/MX/DE/IN）全同；JP 与 TW 的 H-GLOBAL/H-FUND/H-POS/H-ART 逐字相同。存在 1 条自相矛盾证据（JP tier A，见 P1-4）。验收“20-candidate audit has 15 distinct hypothesis signatures”无可复算 artifact；按“假设 ID/类型/状态”定义只有 7 种 |
| 11 | 新 P0/P1 扫描 | **无 P0；P1 见下** | 干净 clone 无 silent skip（skipped=0）；未发现 V1 表回归；发现 release 3 项 P1 + hypothesis 证据 1 项 P1 |

## 二、P1（按严重度）

### P1-1 冻结提交的 release 证据不可验证（log 未入库 + commit 过期）

```bash
cd /Users/cast/Downloads/金融系统/global-opportunity-engine
.venv/bin/python - <<'PY'
import goe.release as r
r.verify_test_proof('audit/test_evidence/20261114T151351Z_83a116030c.proof.json')
PY
# ReleaseError: test proof commit does not match current HEAD

git check-ignore -v audit/test_evidence/20261114T151351Z_83a116030c.log
# .gitignore:19:*.log	audit/test_evidence/...log

git ls-tree -r --name-only 3645951 audit/test_evidence
# 只列出两个 *.proof.json，没有 *.log
```

- 证据链：`83a1160` 有旧 proof（commit=`5c19289`，174 passed），但**没有** `release_83a116030c.json`；`3645951` 有 release/proof，但 `verify_test_proof` 用 HEAD 比对 proof 的 `83a1160`，必拒。
- 即便把 commit 改成 `3645951`，干净 clone 里也缺 log（被 gitignore），会抛 `test proof log is missing`。
- 影响：manifest 的 `notes="V2 P1-A/B/C/D fixed"` 和“machine-verifiable test evidence”不能从冻结产物独立复核；需要 checkout `83a1160` + 手工准备未入库 log 才能通过。**这是 P1，不是 P2**：release 的核心卖点就是可复核证据。

### P1-2 gate 只做“内部自洽”，完整重写 log+proof 即被接受；error 计数不交叉校验

在 `/tmp` 对真实 proof/log 做矩阵（`verify_test_proof` 结果）：

| 篡改 | 结果 |
|---|---|
| 真实 proof（commit=83a1160）对 HEAD=3645951 | 拒（commit） |
| 只改 proof `passed=999` | 拒（count disagrees） |
| 只改 log（sha 不更新） | 拒（hash mismatch） |
| 缺 log | 拒（missing） |
| `git_dirty=true` | 拒 |
| **重写 log 为 `9999 passed` + proof 同步 + 重算 sha** | **接受** |
| **log 写 `173 passed, 1 error`、proof `errors=0` + 重算 sha** | **接受** |

根因：`verify_test_proof` 只比对 passed/failed/skipped 与 log（`goe/release.py:121-123`），不比对 `errors`/`deselected`；`exit_code` 也是 proof 自报。proof、log、sha 三者都可写，gate 没有外部签名/CI 信任根，所以“完全伪造的一次运行记录”可通过。测试 `tests/test_contracts.py:106-126` 甚至用一个手写 log 断言 proof 被接受，未覆盖 stale/dirty/error。

### P1-3 dirty-tree 豁免是子串匹配，可被“tests/audit/test_evidence/”跟踪文件绕过

```bash
# 在临时 clone（不碰仓库）：
mkdir -p tests/audit/test_evidence
echo 'def test_ok(): assert True' > tests/audit/test_evidence/test_x.py
git add tests/audit/test_evidence/test_x.py && git commit -qm qa
echo 'def test_ok(): assert False' > tests/audit/test_evidence/test_x.py
python -c "import goe.release as r; print(r._dirty_code(cwd='.'))"
# False   ← 修改后的测试被当作 clean
```

`_dirty_code` 只要 `git status --porcelain` 行内包含 `audit/test_evidence/` 或 `audit/releases/` 就豁免（`goe/release.py:37-40`），而不是限定为这两个目录本身。pytest 会递归收集 `tests/` 下任意子目录，所以“修改测试再出 proof”可以绕过 clean-tree 检查，proof 仍写 `git_dirty:false`。`verify_test_proof` 本身也完全不检查当前工作树，只在 `build_manifest` 里另调 `_dirty_code()`。

### P1-4 真实候选存在自相矛盾的“支持证据”；模板化仍明显

`exports/research_candidates_2026-11-13.json` 的 `RC-20261113-12`（N225，tier A）：

```json
{"id": "H-LOCAL", "status": "open",
 "evidence_for": [{"claim": "有区域/机制关联证据",
                   "value": "mechanisms=['unsupported']",
                   "class": "statistical_association", ...}]}
```

同一候选 `materiality.mechanism_conflict = true`。`goe/hypotheses.py:51` 把任何非空 `mechanism_statuses` 都当 `mech_open`，`unsupported` 也被写成“有关联证据”（`:57-59`），这是**把“机制不支持”反向标成“支持证据”**，并计入 open hypothesis/distinguishability，可影响 tier A。复现：

```bash
python - <<'PY'
import json
c=json.load(open('exports/research_candidates_2026-11-13.json'))['candidates'][0]
h=[x for x in c['competing_hypotheses'] if x['id']=='H-LOCAL'][0]
print(c['materiality']['mechanism_conflict'], h['evidence_for'][0]['value'])
PY
# True mechanisms=['unsupported']
```

以下仍偏模板/循环的支持证据（P2 级但应在研究结论中披露；均为冻结 `3645951` 行为，复核末期并行工作树已改 `hypotheses.py`，提交后需重测）：
- `H-GLOBAL` 的 evidence_for 用“1m=9.7%”支持“全球共同风险”，这是被解释现象本身，不是同日跨资产联动；`H-FX` 的 evidence_for 是“本地汇率可观察”（source=`prices`），但该候选未实际读取本地汇率；`H-POLICY` 用“区域属于政策敏感市场”（config 事实）支持“政策冲击”；`H-RATES` 用“UST 可观察”支持利率解释。这些是“数据可得性”，不是“证据”。
- JP 与 TW 的 `H-GLOBAL/H-FUND/H-POS/H-ART` 除 region 标签外逐字相同，`decision_impact.if_true/if_false` 完全相同；TW 因 `H-FX` 的 region 白名单（`hypotheses.py:180` 仅 JP/EA/UK/CN）而没有本地汇率假设，尽管 TAIEX 同样有汇率暴露；TW 的 `H-POLICY` 直接 untestable（`POLICY_REGIONS` 不含 TW）。资产类之间有差异（country equity / US ETF / sector / EM），**同一子类内部仍是模板**。

### P1-C 的 20 条结果（真实复跑）

仓库只有 5 条候选导出（CLI 默认 `--limit 5`），`evaluation/v2_candidates_2026-11-13.json` 也是 5 条；因此本代理在 `/tmp` DB 副本上按同一 `as_of=2026-11-13` 运行 `run_triage(..., max_candidates=20)`，输出仅写 `/tmp`。结果：

```text
N=20, tiers: A=1, B=4, C=7, intelligence=8
asset_class: equity_index=6, equity_etf=4, sector_equity=4, fx=2, commodity=4
hypothesis-ID 序列 distinct=7
decision_impact distinct=5（country_equity 7 条同文；US-ETF/EM 3 条同文；sector 4 条同文；FX 2 条同文；commodity 4 条同文）
falsification test 签名 distinct=7
```

- 差异主要来自**资产类分支**（country equity / US-ETF / sector / FX / commodity），不是单个现象。最强的同名组：
  - `TW/CH/MX/DE/IN` 五条 country equity 的 hypothesis 序列、状态、测试完全相同；仅 region 文案不同。
  - `XLV/XLB/XLP/CN_SEC_EV` 四条 sector 的 4 个 hypothesis 与测试完全相同。
  - `USDBRL/USDKRW` 两条 FX 完全相同。
  - 4 条 commodity 完全相同（且全部 intelligence）。
  - `JP/CN` 因 region 进入 FX/POLICY 白名单而比其余 country equity 多一个 H-FX；`QQQ/MTUM` 同；仅 `EEM` 多 H-USD。
- 因而“按假设 ID/类型/状态”的 distinct signature 只有 **7**，不是 15。若把 region/资产名也计入“full hypotheses JSON”，则 20 条必然两两不同（distinct=20），所以 15 这个数字取决于未写明的签名定义；仓库没有该 20 条 artifact/命令，无法复核。**这是 P2 追溯性问题**，但它掩盖了“同子类模板化”的实质：15 不等于 15 种真正不同的研究假设集。
- `audit/V2_FINAL_ACCEPTANCE.md:6` 的“20-candidate audit has 15 distinct hypothesis signatures”应附生成命令、candidate 导出和签名定义；否则不应作为研究差异化证据。

## 三、A→B 与生命周期证据（PASS）

真实 DB（只读）：

```text
research_v2_candidates: 5
RC-20261113-12  status=handoff_failed
research_v2_tasks: RC-20261113-12 status=not_completed:rejected
research_v2_results: RC-20261113-12 semantic=rejected run_ok=0
research_v2_events: ia_research_not_completed ×2, status:handoff_failed ×1
orphan_h/e/t/r = 0/0/0/0
legacy V1 RC tasks/events = 0/0
V1 research_tasks=2, opportunity_events=13（未被 V2 触碰）
exports/research_v2_ia/RC-* 目录为空（下游没有产出可复用 artifact）
```

- 对应代码：`research_handoff.py:61-90` 先 upsert candidate，再 task/result/event，最后 `set_research_status`；`run_ok` 只认 `status=="ok" and semantic=="ok_valid"`。
- 测试：`tests/test_research_v2.py:132`（保留 candidate、task/result/hypothesis 计数、integrity 全 0）、`:145`（缺失 candidate 时 `upsert_research_task_v2` 抛 `ValueError`，且 FK=ON `goe/db.py:195`）、`:164`（legacy RC 迁移后 V1 RC=0、V2 candidate/task=1）、`:52`（timeout 标签）、`test_readiness_handoff.py:252`（L2-only 不能 ok_valid）。
- 结论：**A→B 没有伪成功**；L2-only、timeout、rejected 都被正确降级。**PASS**。
- 小瑕疵（P3）：`persist_v2_result` 的 timeout 归一化只在 `semantic_status in (None,"unknown")` 时生效；若上游给 `status=timeout, semantic_status="partial"`，会记成 `not_completed:partial`。真实 adapter 不产生该组合，故不影响本次 PASS。

## 四、新 P0/P1 汇总

- **P0：无。**
- 新增/剩余 P1：P1-1 release 证据不可在冻结提交验证；P1-2 完整伪造 log+proof 被接受且 error 不校验；P1-3 dirty 豁免子串绕过；P1-4 真实候选 `mechanisms=['unsupported']` 被标成支持证据。
- P2：验收的“20-candidate audit / 15 distinct signatures”无 artifact 与签名定义（本次复跑仅 7 种 hypothesis-ID 序列）；默认 `pytest -q` 因 `-qq` 抑制汇总（不影响 exit code）；`verify_test_proof` 不检查当前工作树、`git_dirty` 缺失字段可绕过（falsy）；`_dirty_code` 未覆盖未跟踪目录的边界；候选模板化（JP/TW、QQQ/EEM）与“可得性≠证据”；H-FX 区域白名单漏 TW。
- P3：timeout 组合标签；`research_integrity` 的 orphan_results 只校验 task 不校验 candidate（FK 开时不可达）。

## 五、明确状态

- **ENGINEERING：PASS WITH ISSUES**（干净 clone 174 passed / 10 deselected；生命周期、FK、A→B、V1 隔离通过；无 P0）。
- **RELEASE GATE：FAIL（P1-1/P1-2/P1-3）**——冻结 `3645951` 的 release 不能按“machine-verifiable”签收；修复前不应把 `release_83a116030c.json` 当作独立可复核证据。
- **RESEARCH：PARTIAL**；`DISCOVERY VALUE: NOT VALIDATED`（本次未做新评估，也未修改任何研究结论）。

## 六、复核边界与并行改动

- 未运行网络/真实数据 marker（`-m network` / `realdata`）；未重建 scan、未重签 manifest、未改 git。
- 本报告所有结论针对**冻结提交 `3645951`**（测试在 `/tmp` clone 上执行；20 条 triage 在 `/tmp` DB 副本 + 该 commit 代码上执行）。
- 唯一由本代理写文件：本报告。复核末期（约 23:25 之后）工作树被**其他并行代理**修改：`goe/hypotheses.py`、`goe/integration/ia_adapter.py`、`goe/integration/research_handoff.py`、`goe/research_triage.py` 出现未提交改动，并新增 `evaluation/research_candidates_2026-11-13.json`、`evaluation/v2_candidates_20_2026-11-13.json` 与 `audit/QA_V2_RESEARCH.md`。这些改动**不是本代理所做、也未纳入本报告验收**；其中 hypotheses 改动看起来正针对 P1-4（`strong_mech` 替代 `mech_open`），提交后应重跑本报告 P1-4/20 条复核。
- `/tmp` clone 与 DB 副本仅用于红队实验；仓库 `data/` 未写入（仅只读 SQLite 查询）。
